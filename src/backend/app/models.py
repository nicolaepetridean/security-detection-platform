"""SQLAlchemy ORM models.

Roles:
    admin    - full access to everything
    readonly - CST / Support: can view, cannot mutate
    analyst  - Security Analyst: can claim & resolve detections

Detection lifecycle:
    open -> assigned -> closed
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    admin = "admin"
    readonly = "readonly"
    analyst = "analyst"


class DetectionStatus(str, enum.Enum):
    open = "open"
    assigned = "assigned"
    closed = "closed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role))


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # Importance drives detection priority. Configurable, constrained to 1..5 at the API.
    importance: Mapped[int] = mapped_column(Integer, default=1)


class Signature(Base):
    __tablename__ = "signatures"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # Severity of the signature itself, 1..5. Combined with customer importance.
    priority: Mapped[int] = mapped_column(Integer, default=1)
    # The field/value pairs that must ALL be present (with equal values) for a match.
    # Stored as a JSON object: {"field": "expected_value", ...}
    match_fields: Mapped[dict] = mapped_column(JSON, default=dict)


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    signature_id: Mapped[int] = mapped_column(ForeignKey("signatures.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))

    # Computed at ingestion = customer.importance * signature.priority.
    priority: Mapped[int] = mapped_column(Integer, index=True)

    status: Mapped[DetectionStatus] = mapped_column(
        Enum(DetectionStatus), default=DetectionStatus.open, index=True
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The original incident payload, kept for investigation/audit.
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    signature: Mapped["Signature"] = relationship()
    customer: Mapped["Customer"] = relationship()
    assignee: Mapped["User | None"] = relationship()

    __table_args__ = (
        # An analyst works a single detection at a time: at most one *assigned*
        # detection per analyst. A partial unique index enforces this at the DB layer
        # while still allowing many closed detections per analyst.
        Index(
            "uq_one_active_per_analyst",
            "assignee_id",
            unique=True,
            sqlite_where=(status == DetectionStatus.assigned),
            postgresql_where=(status == DetectionStatus.assigned),
        ),
    )


class UnmatchedIncident(Base):
    """Incidents that matched no signature. Stored separately for audit/triage rather
    than dropped, so nothing is silently lost (documented decision in README)."""

    __tablename__ = "unmatched_incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
