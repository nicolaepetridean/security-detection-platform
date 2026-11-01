"""API-level tests: authentication enforcement, ingestion, claim & close flow."""
from app.models import Detection

from conftest import auth_header, token_for


def _ingest(client, customer_id, fields):
    return client.post("/ingest", json={"customer_id": customer_id, "fields": fields})


def test_queue_requires_auth(client, seeded):
    assert client.get("/detections/queue").status_code == 401


def test_readonly_cannot_claim(client, seeded, db):
    # Create a detection via ingestion.
    cid = seeded["customer"].id
    res = _ingest(client, cid, {"event_type": "auth_fail", "service": "ssh"})
    detection_id = res.json()["detection_id"]

    token = token_for(client, "support")  # readonly role
    resp = client.post(f"/detections/{detection_id}/claim", headers=auth_header(token))
    assert resp.status_code == 403


def test_readonly_cannot_create_customer(client, seeded):
    token = token_for(client, "support")
    resp = client.post(
        "/customers", json={"name": "Nope", "importance": 2}, headers=auth_header(token)
    )
    assert resp.status_code == 403


def test_ingest_matches_most_severe_and_computes_priority(client, seeded):
    cid = seeded["customer"].id  # importance 5
    # Matches both AuthFail(p3) and SSHBrute(p4); SSHBrute wins -> priority 5*4=20.
    res = _ingest(client, cid, {"event_type": "auth_fail", "service": "ssh"})
    body = res.json()
    assert res.status_code == 201
    assert body["matched"] is True
    assert body["priority"] == 20


def test_ingest_no_match_stored_separately(client, seeded):
    cid = seeded["customer"].id
    res = _ingest(client, cid, {"event_type": "totally_unknown"})
    assert res.status_code == 201
    assert res.json()["matched"] is False
    assert res.json()["detection_id"] is None


def test_full_claim_and_close_flow(client, seeded):
    cid = seeded["customer"].id
    detection_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]

    token = token_for(client, "alice")
    claim = client.post(f"/detections/{detection_id}/claim", headers=auth_header(token))
    assert claim.status_code == 200
    assert claim.json()["status"] == "assigned"

    # Active detection overlay reflects it.
    active = client.get("/detections/active", headers=auth_header(token)).json()
    assert active["id"] == detection_id

    close = client.post(
        f"/detections/{detection_id}/close",
        json={"resolution": "Confirmed benign, user typo"},
        headers=auth_header(token),
    )
    assert close.status_code == 200
    assert close.json()["status"] == "closed"
    assert close.json()["resolution"].startswith("Confirmed")

    # Closed detection leaves the queue but stays in the full list.
    queue_ids = [d["id"] for d in client.get(
        "/detections/queue", headers=auth_header(token)).json()]
    assert detection_id not in queue_ids
    all_ids = [d["id"] for d in client.get(
        "/detections", headers=auth_header(token)).json()]
    assert detection_id in all_ids


def test_analyst_one_active_at_a_time(client, seeded):
    cid = seeded["customer"].id
    d1 = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]
    d2 = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]

    token = token_for(client, "alice")
    assert client.post(f"/detections/{d1}/claim", headers=auth_header(token)).status_code == 200
    # Second claim while one is active -> rejected by the DB partial unique index.
    second = client.post(f"/detections/{d2}/claim", headers=auth_header(token))
    assert second.status_code == 409


# --- Authentication (login) ---------------------------------------------------

def test_login_wrong_password_returns_401(client, seeded):
    resp = client.post("/auth/login", data={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect username or password"


def test_login_unknown_user_returns_401(client, seeded):
    # Same message as wrong-password: don't reveal which part was invalid.
    resp = client.post("/auth/login", data={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


# --- Authorization completeness (API-level enforcement) -----------------------

def test_analyst_cannot_create_customer(client, seeded):
    token = token_for(client, "alice")  # analyst, not admin
    resp = client.post(
        "/customers", json={"name": "Nope", "importance": 2}, headers=auth_header(token)
    )
    assert resp.status_code == 403


def test_analyst_cannot_create_signature(client, seeded):
    token = token_for(client, "alice")
    resp = client.post(
        "/signatures",
        json={"name": "X", "priority": 2, "match_fields": {"a": "b"}},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_readonly_cannot_create_signature(client, seeded):
    token = token_for(client, "support")
    resp = client.post(
        "/signatures",
        json={"name": "X", "priority": 2, "match_fields": {"a": "b"}},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_readonly_cannot_close(client, seeded):
    # The role dependency rejects before any handler logic, so the id need not exist.
    token = token_for(client, "support")
    resp = client.post(
        "/detections/999/close",
        json={"resolution": "x"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_close_by_non_assignee_forbidden(client, seeded):
    cid = seeded["customer"].id
    detection_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]

    alice = token_for(client, "alice")
    bob = token_for(client, "bob")
    assert client.post(
        f"/detections/{detection_id}/claim", headers=auth_header(alice)
    ).status_code == 200

    # Bob is an analyst but not the assignee -> 403.
    resp = client.post(
        f"/detections/{detection_id}/close",
        json={"resolution": "not mine"},
        headers=auth_header(bob),
    )
    assert resp.status_code == 403


# --- Error / state paths ------------------------------------------------------

def test_claim_nonexistent_returns_404(client, seeded):
    token = token_for(client, "alice")
    resp = client.post("/detections/999999/claim", headers=auth_header(token))
    assert resp.status_code == 404


def test_close_open_detection_returns_409(client, seeded):
    # A detection that was never claimed cannot be closed.
    cid = seeded["customer"].id
    detection_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]
    token = token_for(client, "alice")
    resp = client.post(
        f"/detections/{detection_id}/close",
        json={"resolution": "x"},
        headers=auth_header(token),
    )
    assert resp.status_code == 409


def test_ingest_unknown_customer_returns_404(client, seeded):
    resp = _ingest(client, 999999, {"event_type": "auth_fail"})
    assert resp.status_code == 404


# --- Input validation ---------------------------------------------------------

def test_close_empty_resolution_rejected(client, seeded):
    cid = seeded["customer"].id
    detection_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]
    token = token_for(client, "alice")
    client.post(f"/detections/{detection_id}/claim", headers=auth_header(token))
    resp = client.post(
        f"/detections/{detection_id}/close",
        json={"resolution": ""},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


def test_create_signature_requires_at_least_one_pair(client, seeded):
    token = token_for(client, "admin", "admin123")
    resp = client.post(
        "/signatures",
        json={"name": "Empty", "priority": 1, "match_fields": {}},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


# --- Behavioral: queue ordering & filtering -----------------------------------

def test_queue_ordered_by_priority_desc(client, seeded):
    cid = seeded["customer"].id  # importance 5
    # AuthFail(p3) only -> 15 ; SSHBrute(p4) -> 20. Queue must put 20 first.
    _ingest(client, cid, {"event_type": "auth_fail"})
    _ingest(client, cid, {"event_type": "auth_fail", "service": "ssh"})
    token = token_for(client, "alice")
    rows = client.get("/detections/queue", headers=auth_header(token)).json()
    priorities = [d["priority"] for d in rows]
    assert priorities == sorted(priorities, reverse=True)
    assert priorities[0] == 20


def test_detections_filter_by_status(client, seeded):
    cid = seeded["customer"].id
    open_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]
    assigned_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]
    token = token_for(client, "alice")
    client.post(f"/detections/{assigned_id}/claim", headers=auth_header(token))

    open_rows = client.get("/detections?status=open", headers=auth_header(token)).json()
    assigned_rows = client.get(
        "/detections?status=assigned", headers=auth_header(token)
    ).json()
    assert {d["id"] for d in open_rows} == {open_id}
    assert {d["id"] for d in assigned_rows} == {assigned_id}


# --- Admin CRUD (positive paths) ----------------------------------------------

def test_admin_can_create_and_update_customer(client, seeded):
    token = token_for(client, "admin", "admin123")
    created = client.post(
        "/customers", json={"name": "Globex", "importance": 2}, headers=auth_header(token)
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]

    updated = client.patch(
        f"/customers/{customer_id}", json={"importance": 5}, headers=auth_header(token)
    )
    assert updated.status_code == 200
    assert updated.json()["importance"] == 5


def _priority_of(client, token, detection_id):
    rows = client.get("/detections", headers=auth_header(token)).json()
    return next(d["priority"] for d in rows if d["id"] == detection_id)


def test_customer_importance_update_reprioritizes_open_detections(client, seeded):
    cid = seeded["customer"].id  # importance 5
    # AuthFail(p3) -> 5*3 = 15.
    det_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]
    admin = token_for(client, "admin", "admin123")
    alice = token_for(client, "alice")
    assert _priority_of(client, alice, det_id) == 15

    # Lower the customer's importance; the open detection must follow: 2*3 = 6.
    client.patch(f"/customers/{cid}", json={"importance": 2}, headers=auth_header(admin))
    assert _priority_of(client, alice, det_id) == 6


def test_signature_priority_update_reprioritizes_open_detections(client, seeded):
    cid = seeded["customer"].id  # importance 5
    det_id = _ingest(
        client, cid, {"event_type": "auth_fail", "service": "ssh"}
    ).json()["detection_id"]  # SSHBrute(p4) -> 5*4 = 20
    admin = token_for(client, "admin", "admin123")
    alice = token_for(client, "alice")
    assert _priority_of(client, alice, det_id) == 20

    sig_id = next(
        s["id"]
        for s in client.get("/signatures", headers=auth_header(admin)).json()
        if s["name"] == "SSHBrute"
    )
    # Raise the signature severity to 5; the open detection follows: 5*5 = 25.
    client.patch(f"/signatures/{sig_id}", json={"priority": 5}, headers=auth_header(admin))
    assert _priority_of(client, alice, det_id) == 25


def test_closed_detection_priority_is_frozen(client, seeded):
    cid = seeded["customer"].id  # importance 5
    det_id = _ingest(client, cid, {"event_type": "auth_fail"}).json()["detection_id"]
    alice = token_for(client, "alice")
    admin = token_for(client, "admin", "admin123")
    client.post(f"/detections/{det_id}/claim", headers=auth_header(alice))
    client.post(
        f"/detections/{det_id}/close",
        json={"resolution": "done"},
        headers=auth_header(alice),
    )
    # Changing importance must NOT rewrite history on a closed detection.
    client.patch(f"/customers/{cid}", json={"importance": 1}, headers=auth_header(admin))
    assert _priority_of(client, alice, det_id) == 15


def test_admin_can_create_signature(client, seeded):
    token = token_for(client, "admin", "admin123")
    resp = client.post(
        "/signatures",
        json={"name": "Beacon", "priority": 5, "match_fields": {"event_type": "c2"}},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["match_fields"] == {"event_type": "c2"}


def test_duplicate_customer_name_conflict(client, seeded):
    token = token_for(client, "admin", "admin123")
    # "Acme" already exists from the seed fixture.
    resp = client.post(
        "/customers", json={"name": "Acme", "importance": 1}, headers=auth_header(token)
    )
    assert resp.status_code == 409
