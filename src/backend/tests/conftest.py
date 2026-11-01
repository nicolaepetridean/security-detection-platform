"""Shared test fixtures.

A temporary SQLite *file* (not in-memory) is used so that multiple connections/threads
see the same database — required to exercise the claim race condition realistically.
DATABASE_URL is set BEFORE importing app modules so config picks it up.
"""
import os
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Customer, Detection, Role, Signature, User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    os.close(_db_fd)
    os.remove(_db_path)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded(db):
    """Fresh known state for each test."""
    for model in (Detection, Customer, Signature, User):
        db.query(model).delete()
    db.commit()

    admin = User(username="admin", password_hash=hash_password("admin123"), role=Role.admin)
    support = User(username="support", password_hash=hash_password("x"), role=Role.readonly)
    alice = User(username="alice", password_hash=hash_password("x"), role=Role.analyst)
    bob = User(username="bob", password_hash=hash_password("x"), role=Role.analyst)
    db.add_all([admin, support, alice, bob])

    acme = Customer(name="Acme", importance=5)
    db.add(acme)

    sig_broad = Signature(name="AuthFail", priority=3, match_fields={"event_type": "auth_fail"})
    sig_specific = Signature(
        name="SSHBrute", priority=4,
        match_fields={"event_type": "auth_fail", "service": "ssh"},
    )
    db.add_all([sig_broad, sig_specific])
    db.commit()
    db.refresh(acme)
    return {"customer": acme}


@pytest.fixture()
def client():
    return TestClient(app)


def token_for(client: TestClient, username: str, password: str = "x") -> str:
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
