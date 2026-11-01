"""Signature management. Reads: any authenticated user. Writes: admin only."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import Role, Signature, User
from ..schemas import SignatureCreate, SignatureOut, SignatureUpdate
from ..services.detections import recompute_priorities_for_signature

router = APIRouter(prefix="/signatures", tags=["signatures"])


@router.get("", response_model=list[SignatureOut])
def list_signatures(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Signature).order_by(Signature.name).all()


@router.post("", response_model=SignatureOut, status_code=201)
def create_signature(
    body: SignatureCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.admin)),
):
    sig = Signature(
        name=body.name, priority=body.priority, match_fields=body.match_fields
    )
    db.add(sig)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Signature name already exists")
    db.refresh(sig)
    return sig


@router.patch("/{signature_id}", response_model=SignatureOut)
def update_signature(
    signature_id: int,
    body: SignatureUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.admin)),
):
    sig = db.get(Signature, signature_id)
    if sig is None:
        raise HTTPException(status_code=404, detail="Signature not found")
    if body.name is not None:
        sig.name = body.name
    if body.priority is not None:
        sig.priority = body.priority
        # Keep already-queued detections consistent with the new severity.
        recompute_priorities_for_signature(db, sig)
    if body.match_fields is not None:
        sig.match_fields = body.match_fields
    db.commit()
    db.refresh(sig)
    return sig
