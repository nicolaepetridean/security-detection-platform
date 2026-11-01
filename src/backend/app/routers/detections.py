"""Detection HTTP endpoints. Thin: parse/authorize -> delegate to the service layer."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import DetectionStatus, Role, User
from ..schemas import CloseRequest, DetectionOut
from ..services import detections as service

router = APIRouter(prefix="/detections", tags=["detections"])


@router.get("/queue", response_model=list[DetectionOut])
def get_queue(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Prioritized worklist of open detections (the landing page)."""
    return service.get_queue(db)


@router.get("/active", response_model=DetectionOut | None)
def get_active(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The current analyst's single active detection, for the overlay."""
    return service.get_active_detection(db, user)


@router.get("", response_model=list[DetectionOut])
def list_detections(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status: DetectionStatus | None = Query(default=None),
    customer_id: int | None = None,
    assignee_id: int | None = None,
    signature_id: int | None = None,
):
    """Full, filterable history (distinct from the queue)."""
    return service.list_detections(
        db,
        status=status,
        customer_id=customer_id,
        assignee_id=assignee_id,
        signature_id=signature_id,
    )


@router.post("/{detection_id}/claim", response_model=DetectionOut)
def claim_detection(
    detection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.analyst)),
):
    """Claim a detection (race-safe; see service layer)."""
    return service.claim(db, detection_id, user)


@router.post("/{detection_id}/close", response_model=DetectionOut)
def close_detection(
    detection_id: int,
    body: CloseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.analyst)),
):
    """Close the active detection with a written resolution."""
    return service.close(db, detection_id, user, body.resolution)
