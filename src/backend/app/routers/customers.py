"""Customer management. Reads: any authenticated user. Writes: admin only."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import Customer, Role, User
from ..schemas import CustomerCreate, CustomerOut, CustomerUpdate
from ..services.detections import recompute_priorities_for_customer

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Customer).order_by(Customer.name).all()


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.admin)),
):
    customer = Customer(name=body.name, importance=body.importance)
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer name already exists")
    db.refresh(customer)
    return customer


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.admin)),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if body.name is not None:
        customer.name = body.name
    if body.importance is not None:
        customer.importance = body.importance
        # Keep already-queued detections consistent with the new importance.
        recompute_priorities_for_customer(db, customer)
    db.commit()
    db.refresh(customer)
    return customer
