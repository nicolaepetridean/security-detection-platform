"""Ingestion service: turn an incoming incident into a detection (or store it unmatched).

This is the "imperative shell" around the pure matching/priority logic in core.py. It
owns the orchestration and persistence; the decision-making stays pure and unit-tested.
"""
from sqlalchemy.orm import Session

from ..core import SignatureView, compute_priority, select_best_signature
from ..errors import NotFoundError
from ..models import Customer, Detection, Signature, UnmatchedIncident
from ..schemas import IngestRequest, IngestResult


def ingest_incident(db: Session, req: IngestRequest) -> IngestResult:
    customer = db.get(Customer, req.customer_id)
    if customer is None:
        raise NotFoundError("Unknown customer")

    views = [
        SignatureView(id=s.id, priority=s.priority, match_fields=s.match_fields)
        for s in db.query(Signature).all()
    ]
    best = select_best_signature(views, req.fields)

    if best is None:
        # Documented decision: store unmatched incidents rather than drop them.
        db.add(UnmatchedIncident(raw_payload=req.model_dump()))
        db.commit()
        return IngestResult(matched=False)

    priority = compute_priority(customer.importance, best.priority)
    detection = Detection(
        signature_id=best.id,
        customer_id=customer.id,
        priority=priority,
        raw_payload=req.model_dump(),
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)

    return IngestResult(
        matched=True,
        detection_id=detection.id,
        signature_id=best.id,
        priority=priority,
    )
