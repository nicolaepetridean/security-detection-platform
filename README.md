# Detection Management Platform

A simplified web platform for managing security detections, built for the Bitdefender
MDR Senior SWE technical assignment.

External sources push security **incidents** over HTTP. The platform matches each incident
against a database of **signatures**, correlates it with the relevant **customer**,
computes a **priority**, and creates a **detection** in a prioritized queue. Security
analysts pick detections off the queue (one at a time), investigate, and close them with
a written resolution.

- **Backend:** Python · FastAPI · SQLAlchemy 2 · SQLite
- **Frontend:** React (Vite) · React Router
- **Auth:** JWT bearer tokens, Argon2id password hashing, role enforcement **at the API layer**

---

## Quick start

Two processes: the API (port **8000**) and the web app (port **5173**). The Vite dev
server proxies `/api/*` to the backend, so the browser talks to a single origin.

### 1. Backend

```bash
# from the repo root — a single virtualenv lives here, next to src/
python -m venv .venv && source .venv/bin/activate
pip install -r src/backend/requirements.txt

cd src/backend
python -m app.seed          # create tables + demo users/customers/signatures
uvicorn app.main:app --reload --port 8000
```

API docs (Swagger) live at http://localhost:8000/docs.

### 2. Frontend

```bash
cd src/frontend
npm install
npm run dev                 # http://localhost:5173
```

Open http://localhost:5173 and log in.

### Demo logins

| Username  | Password     | Role               | Can do                                   |
|-----------|--------------|--------------------|------------------------------------------|
| `admin`   | `admin123`   | Admin              | Everything (incl. customer/signature mgmt) |
| `support` | `support123` | Read-only (CST)    | View only                                |
| `alice`   | `analyst123` | Security Analyst   | Claim & close detections                 |
| `bob`     | `analyst123` | Security Analyst   | Claim & close detections (for race demo) |

### Feeding incidents

There is no seeded detection data — detections are *created* by ingestion. Push an
incident (no auth; see note below):

```bash
# Matches "SSH Brute Force" (priority 4) for Acme (importance 5) -> priority 20
curl -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' \
  -d '{"customer_id": 1, "fields": {"event_type": "auth_fail", "service": "ssh"}}'
```

Refresh the **Queue** page to see it appear.

### Tests

```bash
cd src/backend
pytest            # 35 tests: matching, priority, authz, claim/close, race, validation
```

---

## How it works

### Data model

| Entity             | Notes |
|--------------------|-------|
| `User`             | `role ∈ {admin, readonly, analyst}` |
| `Customer`         | `importance` 1–5 (configurable), feeds priority |
| `Signature`        | `priority` 1–5 + `match_fields` (a JSON object of field→expected value) |
| `Detection`        | `signature_id`, `customer_id`, computed `priority`, `status ∈ {open, assigned, closed}`, `assignee_id`, `resolution`, `raw_payload` |
| `UnmatchedIncident`| incidents that matched no signature (see decision below) |

### Ingestion flow (`POST /ingest`)

1. Look up the customer (`404` if unknown).
2. Find the best matching signature (see **matching** below).
3. If none matches → store the incident in `unmatched_incidents`.
4. Otherwise compute `priority = customer.importance × signature.priority` and create a
   `Detection` with `status=open`.

### Separation of concerns: Queue vs. Detections

These are intentionally two different endpoints / pages:

- **Queue** (`GET /detections/queue`) — only `open` detections, ordered by priority desc.
  Answers *"what should I pick up next?"*. This is the landing page.
- **Detections** (`GET /detections`) — the full, filterable history (open + assigned +
  closed). Answers *"what has happened?"*. Closed detections stay here forever.

---

## Key design decisions

### 1. Signature matching — subset match

A signature matches an incident when **every** field/value pair it defines is present in
the incident with an equal value. Extra fields in the incident are ignored. Values are
compared as strings, so `443` (number) and `"443"` (string) match. Logic lives in
`backend/app/core.py` as pure, unit-tested functions.

**Edge cases:**
- **No match** → the incident is stored in `unmatched_incidents` rather than dropped. I
  chose *store separately* over *ignore* so nothing is silently lost and unmatched
  traffic can be triaged / used to author new signatures later. (The brief left this to
  me.)
- **Empty `match_fields`** → treated as **non-matching**. An empty rule would otherwise
  match every incident, which is almost certainly a misconfiguration. Signature creation
  also requires at least one pair.
- **Multiple matches** → resolved deterministically (next point).

### 2. Multiple matches — pick the most severe

When several signatures match, `select_best_signature` picks:
1. highest **signature priority** (most severe), then
2. most **field/value pairs** (most specific/precise match), then
3. lowest **id** (stable tiebreaker).

One incident produces at most one detection. I preferred "most severe wins" over
"create one detection per match" to keep the analyst workflow clean (no duplicate work
for a single event); the raw payload is retained so context isn't lost.

### 3. Priority — `importance × signature_priority`

Both inputs are on a 1–5 scale, giving a score of **1–25** (higher = more urgent).
Multiplication is monotonic in both inputs (raising either never lowers priority) and
keeps "important customer + severe signature" strictly on top. Simple and easy to
defend. Implemented as a single function (`compute_priority`) and unit-tested across the
matrix.

The score is denormalized onto the detection row at ingestion (indexed, for fast queue
ordering). To keep it from going stale, editing a customer's importance or a signature's
priority **recomputes the score for that entity's non-closed detections**
(`recompute_priorities_for_customer` / `recompute_priorities_for_signature` in the
detection service). Closed detections are historical and left frozen.

### 4. Race condition — atomic conditional UPDATE at the data layer

If two analysts claim the same detection simultaneously, **exactly one** must win. This
is enforced in the database, not in application code, via a single conditional update
(`backend/app/services/detections.py`, `claim()`):

```sql
UPDATE detections SET assignee_id = :me, status = 'assigned'
WHERE id = :id AND status = 'open' AND assignee_id IS NULL
```

The database guarantees this statement is atomic. The winner's update affects one row
(`rowcount == 1`); the loser's `WHERE` no longer matches (`rowcount == 0`) and receives a
clear **`409 Conflict`**. No application-level lock, mutex, or read-then-write race.

`test_race.py` fires two simultaneous claims from two threads against a shared SQLite
file and asserts exactly one `200` and one `409`.

**Also at the data layer:** a *partial unique index* (`assignee_id WHERE status='assigned'`)
enforces "**an analyst works one detection at a time**" — attempting to claim a second
active detection raises an integrity error, surfaced as `409`.

### 5. Authorization enforced at the API layer

Every protected route declares a role requirement via a FastAPI dependency
(`require_role(...)` in `backend/app/auth.py`). The React UI also hides forbidden
actions, but that's UX only — a read-only user calling `POST /detections/{id}/claim`
directly still gets `403`. `test_api.py` proves this (`test_readonly_cannot_claim`,
`test_readonly_cannot_create_customer`). Admin is allowed everywhere.

| Capability                        | admin | analyst | readonly |
|-----------------------------------|:-----:|:-------:|:--------:|
| View queue / detections / etc.    |  ✅   |   ✅    |    ✅    |
| Claim / close detections          |  ✅   |   ✅    |    ❌    |
| Manage customers / signatures     |  ✅   |   ❌    |    ❌    |

### 6. SQLite hardening for concurrency

WAL journal mode + a 5s busy timeout are enabled on connect (`backend/app/db.py`) so
concurrent writers serialize cleanly instead of failing with "database is locked".

---

## Known limitations & trade-offs

Given the ~3-hour budget, these were consciously deferred (and would be the first things
to add for production):

- **Ingestion is unauthenticated.** It models a machine/external source; a real system
  would authenticate sources (shared secret / HMAC signature / mTLS). Called out rather
  than half-done.
- **No DB migrations.** Tables are created with `create_all`. A real project would use
  Alembic. `app.seed` drops & recreates the schema for a known demo state.
- **No refresh tokens / logout revocation.** JWTs are stateless and valid until expiry
  (8h). No rotation.
- **JWT secret.** The default signing secret is an obvious dev placeholder. To prevent it
  reaching production, `settings.validate()` runs at startup (`backend/app/main.py`
  lifespan) and refuses to boot when `APP_ENV` is not `dev` unless a strong (32+ byte)
  `JWT_SECRET` is supplied. In production it must come from a secret manager.
- **Minimal UI polish & no frontend tests.** Effort was concentrated on the backend
  logic the rubric emphasizes (matching, priority, race condition, API-level authz).
  Signature `match_fields` are edited as raw JSON.
- **Analyst/customer/signature display uses IDs** in some tables rather than resolved
  names, to keep payloads simple.
- **Single-node assumptions.** The race-condition approach is DB-level and so works
  across processes/nodes; SQLite itself is the scaling limit — the same code runs on
  Postgres unchanged (the partial-index and conditional-update are standard SQL).

---

## Architecture & layering

The backend is organised in layers so that each concern is isolated and testable:

```
HTTP (routers)  ->  services  ->  core (pure)  +  models (persistence)
     edge           business         domain          SQLAlchemy
```

- **`core.py` — functional core.** Pure, I/O-free matching & priority functions. Trivial
  to unit-test; this is where correctness lives. (Matching/priority are effectively a
  lightweight *Strategy* — swap the function, swap the policy.)
- **`services/` — service layer (imperative shell).** Orchestrates the domain logic and
  persistence (ingestion, claim, close). Transport-agnostic: no FastAPI imports, so the
  same code is reusable from a worker/CLI/test.
- **`errors.py` + exception handlers — error translation at the boundary.** Services
  raise domain exceptions (`NotFoundError`, `ConflictError`, `ForbiddenError`); `main.py`
  maps them to HTTP status codes. HTTP concerns stay at the edge.
- **`routers/` — thin HTTP adapters.** Parse input, enforce role via a dependency,
  delegate to a service. Simple CRUD (customers/signatures) stays inline in its router —
  adding a service there would be ceremony without benefit (a deliberate "don't
  over-engineer" call).
- **Unit of Work / Repository** is provided by the SQLAlchemy `Session` itself, injected
  via FastAPI's dependency system — so no hand-rolled repository layer is needed.

### How this maps to SOLID

The layering above is driven by SOLID. The guiding principle is to apply each principle
where it *earns clarity*, not to manufacture abstraction (speculative interfaces are a
negative for a time-boxed assignment).

- **S — Single Responsibility.** Each module has one job: `core.py` decides (pure
  matching/priority), `services/` orchestrates + persists, `routers/` adapt HTTP,
  `errors.py` models failure, `main.py` wires + translates errors. Services are grouped by
  use case (`ingestion`, `detections`) rather than fragmented per-operation; trivial CRUD
  stays inline — SRP does not mean a class per function.
- **O — Open/Closed.** Matching/priority are swappable pure functions (a lightweight
  Strategy); the domain-error → HTTP mapping is a data-driven dict in `main.py`, so a new
  `DomainError` subclass is handled without editing the handler; `require_role` is a
  factory, so new per-route role policies need no change to the checker.
- **L — Liskov.** A flat, honest exception hierarchy (`NotFoundError` / `ConflictError` /
  `ForbiddenError` under `DomainError`) — every subclass is fully substitutable in the
  single handler. No surprising overrides.
- **I — Interface Segregation.** Per-use-case Pydantic schemas (`*Create` / `*Update` /
  `*Out`) and a minimal `SignatureView` projection mean no caller depends on fields it
  doesn't use; read routes depend on `get_current_user`, mutations on the narrower
  `require_role`.
- **D — Dependency Inversion.** The high-level policy (`core.py`) depends on nothing
  concrete; services depend on the injected `Session` abstraction and raise
  transport-agnostic domain exceptions, so business logic never imports the web framework.

## Project layout

```
src/
  backend/
    app/
      core.py          # ★ pure matching + priority logic (unit-tested)
      models.py        # SQLAlchemy models (+ partial unique index)
      errors.py        # domain exceptions (transport-agnostic)
      auth.py          # JWT, Argon2, require_role dependency
      db.py            # engine/session, SQLite pragmas
      schemas.py       # Pydantic request/response contracts
      seed.py          # demo data
      main.py          # app wiring + domain-error -> HTTP translation
      services/
        ingestion.py   # ★ ingestion flow (match -> priority -> persist)
        detections.py  # ★ queue, list, atomic claim, close
      routers/
        auth.py
        customers.py   # thin CRUD (admin-only writes)
        signatures.py  # thin CRUD (admin-only writes)
        detections.py  # thin HTTP adapters -> detection service
        ingest.py      # thin HTTP adapter -> ingestion service
    tests/
      test_core.py     # matching + priority (pure, no DB)
      test_api.py      # authz + ingestion + claim/close flow
      test_race.py     # concurrent claims -> exactly one winner
  frontend/
    src/
      pages/           # Login, Queue, Detections, Customers, Signatures
      components/       # Layout, ActiveDetectionOverlay, PriorityBadge
      api.js, auth.jsx, active.jsx
```
