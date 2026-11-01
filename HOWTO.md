# How I used AI on this assignment

The brief explicitly allows and encourages AI tools and says the follow-up will discuss
*how* I used them. This document is an honest account of my workflow, the decisions I
owned, and how I kept quality control. It's meant to support that conversation, not
replace it.

## Tooling

- **AI coding assistant (Claude / Claude Code)** — used as a pair-programmer: scaffolding,
  boilerplate, test drafting, and a sounding board for design trade-offs. "Scaffolding"
  here means the repetitive, low-judgment frame — router/model/schema skeletons, config,
  test stubs — not the business logic or the security-critical paths, which I wrote and
  own myself.
- **Data handling.** The brief is marked *Confidential*, so I was deliberate about what
  I fed to an external tool: code and problem framing, never secrets or credentials, and
  I kept the trade-off in mind that anything sent to a third-party service leaves my
  control. For real company IP I'd use a zero-retention/enterprise or locally-hosted
  configuration rather than a public endpoint.
- Everything else is standard: FastAPI, SQLAlchemy, React/Vite, pytest.

## My workflow (in order)

1. **Understood the problem first.** I had the assignment analysed and broke it into the
   data model, the ingestion flow, and the functional requirements *before* writing code.
   I identified that the real evaluation signal is in four areas — signature matching,
   priority calculation, the race condition, and API-level authorization — and decided to
   invest depth there rather than spread effort thin across UI polish.

2. **Made the design decisions myself, explicitly.** The brief deliberately leaves several
   choices open. I decided each one and had the reasoning written down:
   - **Priority formula:** `customer.importance × signature.priority` (1–25). Chosen
     because it's monotonic in both inputs and trivial to defend — vs. a weighted sum
     (needs justifying the weights) or a band/lookup matrix (more code).
   - **Multiple signature matches:** pick the most severe (highest priority), tie-break
     by specificity then id — one detection per incident. Chosen over "one detection per
     match" to keep the analyst workflow clean.
   - **No match:** store in a separate `unmatched_incidents` table rather than drop, so
     nothing is silently lost and unmatched traffic can seed new signatures.
   - **Race condition:** solve it at the *data layer*, not with an app lock.
   - **Stack & scope:** Python/FastAPI + React, SQLite, depth-over-breadth.

3. **Built backend-first, core logic first.** I had the pure matching/priority functions
   (`core.py`) written and **unit-tested before** wiring any HTTP, so correctness was
   pinned down independently of the framework.

4. **Drove the race condition deliberately.** I specified the mechanism — an atomic
   conditional `UPDATE ... WHERE status='open' AND assignee_id IS NULL`, checking
   `rowcount`, plus a partial unique index for "one active detection per analyst". Then I
   had a **concurrency test** written (two threads, a barrier, assert one 200 + one 409)
   to prove it, rather than trusting it by inspection.

5. **Verified continuously.** Ran the full test suite, booted the server, and smoke-tested
   real HTTP calls (login, ingest, queue) end-to-end through the Vite proxy — confirming,
   e.g., that importance 5 × priority 4 actually returned 20.

6. **Refactored to clean architecture after it worked.** Once behaviour was green, I had
   the business logic extracted from the routers into a **service layer** with
   transport-agnostic **domain exceptions** translated to HTTP at the edge — then re-ran
   the suite to confirm no behaviour changed.

## Where AI helped vs. where I exercised judgment

| AI was good at | I owned |
|---|---|
| Scaffolding routers/models/boilerplate fast | Which problems deserve depth (the "core 4") |
| Drafting tests from a spec I described | The actual design decisions and their rationale |
| Remembering framework idioms (FastAPI DI, SQLAlchemy 2 style) | The race-condition *mechanism* and why it's correct |
| Writing the first pass of the README | Verifying every claim by running it |
| Suggesting the service-layer refactor | Deciding *how far* to refactor (not over-engineering CRUD) |

## How I kept quality control

- **Tests as the contract.** 35 tests cover matching edge cases (no match, multiple
  matches, type coercion, empty rule), priority, authz across all roles (readonly &
  analyst → 403, close-by-non-assignee → 403), login failures, error/state paths
  (404/409), input validation (422), queue ordering, filtering, and the concurrency
  race. AI-generated code only counts once it's green *and* I understand why.
- **I read and can defend every line.** Particularly the atomic claim, the partial unique
  index, and the auth dependency — these are the parts an interviewer will push on.
- **I caught and corrected AI output.** Examples: the first draft used a plain
  `UniqueConstraint(assignee_id, status)` which would have *blocked an analyst from having
  multiple closed detections* — I changed it to a partial unique index. I also replaced a
  deprecated `@app.on_event("startup")` with a lifespan handler.
- **I documented trade-offs honestly** in the README (unauthenticated ingestion, no
  migrations, minimal UI) rather than hiding them.

## Treating AI output with a security mindset

Working in a security domain, I applied the same **zero-trust** posture to the assistant's
output that I'd apply to any untrusted input: useful, but verified before it's trusted.
I actively watched the places where AI tends to be unsafe, because that's where delegating
blindly does real damage:

- **Insecure defaults.** AI happily emits weak crypto, permissive CORS, or hardcoded
  secrets. I checked these explicitly. Known limitation I'm surfacing myself: the demo
  `JWT_SECRET` is short (the test run even raises an `InsecureKeyLengthWarning`) — fine for
  a local demo, but in production it'd be a 32+ byte secret from the environment / a vault.
- **Authorization — never delegated blindly.** The riskiest thing to hand to an AI. I wrote
  and own `require_role`, enforced it at the API layer (not just the UI), and pinned it with
  a test that proves a readonly user gets a real `403` from the endpoint directly.
- **Hallucinated APIs / wrong framework idioms.** Caught and corrected, e.g. the deprecated
  `@app.on_event("startup")` replaced with a lifespan handler.
- **Logic bugs that look correct.** The `UniqueConstraint(assignee_id, status)` the first
  draft suggested would have blocked an analyst from ever having multiple *closed*
  detections — I changed it to a partial unique index and proved the behaviour with the
  concurrency test.
- **Supply chain.** I didn't install suggested dependencies blindly; the dependency list is
  small, pinned, and every package is one I can justify.

The principle: AI accelerates the mechanical work, but I am the last line of defence, and I
can defend every security-critical line without reference to the tool.

## Likely follow-up questions I'm ready for

- *Walk me through the race condition.* → atomic conditional UPDATE + rowcount; why no
  app-level lock; how it behaves on Postgres vs SQLite; the partial-index second guarantee.
- *What if two signatures match?* → the deterministic resolution policy and why.
- *How is authz actually enforced?* → `require_role` dependency on each route; UI hiding
  is UX only; the test that proves a readonly user gets 403 from the API directly.
- *Why multiply for priority?* → monotonicity and defensibility; what I'd change if the
  business wanted customer importance weighted more heavily.
- *What would you do with more time?* → authenticate ingestion (HMAC/mTLS), Alembic
  migrations, resolve IDs to names in the UI, frontend tests, pagination on the lists.
- *Where did AI slow you down or mislead you?* → the unique-constraint bug above; the
  value of tests to catch exactly that.
- *What did you send to AI tools, and how did you handle the confidential brief?* → code
  and framing, never secrets; aware that third-party submission leaves my control; for real
  IP I'd use zero-retention/enterprise or a local model.
- *Show me a decision where you went against the AI's suggestion.* → the partial unique
  index over `UniqueConstraint`; solving the race at the data layer rather than an app lock.

## One-line summary

I used AI to move faster on scaffolding, tests, and boilerplate, while personally owning
the architecture, the design decisions, and verification — and I can defend every part of
the result.
