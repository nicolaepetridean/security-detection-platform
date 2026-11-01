"""Detection service: queue, listing, race-safe claim, and close.

All business rules (including the claim race condition) live here so they are reusable
and testable independently of the HTTP layer. Errors are raised as domain exceptions.
"""
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import compute_priority
from ..errors import ConflictError, ForbiddenError, NotFoundError
from ..models import Customer, Detection, DetectionStatus, Signature, User

# Non-closed detections still live in the queue, so their priority must track later
# edits to customer importance / signature severity. Closed ones are historical.
_ACTIVE_STATUSES = (DetectionStatus.open, DetectionStatus.assigned)


def recompute_priorities_for_customer(db: Session, customer: Customer) -> int:
    """Re-derive priority for a customer's non-closed detections after its importance
    changes, so the queue reflects the new importance. Returns the number updated.

    Priority is denormalized onto the row at ingestion for fast, indexed ordering; this
    keeps that denormalized value consistent when the inputs change. Mutations are
    flushed within the caller's transaction (the router commits).
    """
    detections = (
        db.query(Detection)
        .filter(
            Detection.customer_id == customer.id,
            Detection.status.in_(_ACTIVE_STATUSES),
        )
        .all()
    )
    for d in detections:
        d.priority = compute_priority(customer.importance, d.signature.priority)
    return len(detections)


def recompute_priorities_for_signature(db: Session, signature: Signature) -> int:
    """Re-derive priority for non-closed detections of a signature after its priority
    changes. Returns the number updated. See recompute_priorities_for_customer."""
    detections = (
        db.query(Detection)
        .filter(
            Detection.signature_id == signature.id,
            Detection.status.in_(_ACTIVE_STATUSES),
        )
        .all()
    )
    for d in detections:
        d.priority = compute_priority(d.customer.importance, signature.priority)
    return len(detections)


def get_queue(db: Session) -> list[Detection]:
    """Open detections only, most urgent first. The analyst worklist."""
    return (
        db.query(Detection)
        .filter(Detection.status == DetectionStatus.open)
        .order_by(Detection.priority.desc(), Detection.created_at.asc())
        .all()
    )


def get_active_detection(db: Session, analyst: User) -> Detection | None:
    """The single detection the given analyst is actively working, if any."""
    return (
        db.query(Detection)
        .filter(
            Detection.assignee_id == analyst.id,
            Detection.status == DetectionStatus.assigned,
        )
        .one_or_none()
    )


def list_detections(
    db: Session,
    *,
    status: DetectionStatus | None = None,
    customer_id: int | None = None,
    assignee_id: int | None = None,
    signature_id: int | None = None,
) -> list[Detection]:
    """Full history, filterable. Distinct from the queue (which is the worklist)."""
    q = db.query(Detection)
    if status is not None:
        q = q.filter(Detection.status == status)
    if customer_id is not None:
        q = q.filter(Detection.customer_id == customer_id)
    if assignee_id is not None:
        q = q.filter(Detection.assignee_id == assignee_id)
    if signature_id is not None:
        q = q.filter(Detection.signature_id == signature_id)
    return q.order_by(Detection.created_at.desc()).all()


def claim(db: Session, detection_id: int, analyst: User) -> Detection:
    """Atomically claim an open detection for `analyst`.

    Race condition handled at the DATA layer via a single conditional UPDATE that
    transitions the row only while it is still open and unassigned:

        UPDATE detections SET assignee_id=:me, status='assigned'
        WHERE id=:id AND status='open' AND assignee_id IS NULL

    Exactly one concurrent caller affects a row (rowcount==1 => winner); the loser sees
    rowcount==0 and gets a ConflictError. No application-level lock.

    A partial unique index (assignee_id WHERE status='assigned') additionally enforces
    "one active detection per analyst"; a second concurrent claim raises IntegrityError,
    surfaced here as ConflictError.
    """
    detection = db.get(Detection, detection_id)
    if detection is None:
        raise NotFoundError("Detection not found")

    try:
        result = db.execute(
            update(Detection)
            .where(
                Detection.id == detection_id,
                Detection.status == DetectionStatus.open,
                Detection.assignee_id.is_(None),
            )
            .values(assignee_id=analyst.id, status=DetectionStatus.assigned)
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            "You already have an active detection. Close it before claiming another."
        )

    if result.rowcount == 0:
        raise ConflictError(
            "This detection has already been claimed by another analyst."
        )

    db.refresh(detection)
    return detection


def close(db: Session, detection_id: int, analyst: User, resolution: str) -> Detection:
    detection = db.get(Detection, detection_id)
    if detection is None:
        raise NotFoundError("Detection not found")
    if detection.status != DetectionStatus.assigned:
        raise ConflictError("Only an assigned detection can be closed")
    if detection.assignee_id != analyst.id:
        raise ForbiddenError("You can only close a detection assigned to you")

    detection.status = DetectionStatus.closed
    detection.resolution = resolution
    detection.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(detection)
    return detection
