"""Seed the database with demo users, customers and signatures.

Run with:  python -m app.seed   (from the backend/ directory)

Idempotent-ish: it clears existing rows then re-inserts, so you always get a known
demo state. Safe for a local assignment; never run against real data.
"""
from .db import Base, SessionLocal, engine
from .models import Customer, Signature, User
from .auth import hash_password
from .models import Role

DEMO_USERS = [
    ("admin", "admin123", Role.admin),
    ("support", "support123", Role.readonly),
    ("alice", "analyst123", Role.analyst),
    ("bob", "analyst123", Role.analyst),
]

DEMO_CUSTOMERS = [
    ("Acme Corp", 5),
    ("Globex", 3),
    ("Initech", 1),
]

DEMO_SIGNATURES = [
    ("Brute Force SSH", 4, {"event_type": "auth_fail", "service": "ssh"}),
    ("Port Scan", 2, {"event_type": "scan"}),
    ("Malware Beacon", 5, {"event_type": "c2", "protocol": "https", "severity": "high"}),
    ("Suspicious Login", 3, {"event_type": "auth_fail"}),
]


def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.add_all(
            [
                User(username=u, password_hash=hash_password(p), role=r)
                for u, p, r in DEMO_USERS
            ]
        )
        db.add_all(
            [Customer(name=n, importance=i) for n, i in DEMO_CUSTOMERS]
        )
        db.add_all(
            [
                Signature(name=n, priority=p, match_fields=f)
                for n, p, f in DEMO_SIGNATURES
            ]
        )
        db.commit()
        print("Seeded users, customers and signatures.")
        print("Logins: admin/admin123  support/support123  alice/analyst123  bob/analyst123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
