"""Incident ingestion endpoint. Thin: delegates to the ingestion service.

Note on auth: ingestion models an external/machine source. For the scope of this
assignment it is open (no bearer token). A real deployment would authenticate sources
with a shared secret / HMAC / mTLS — called out in the README limitations.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import IngestRequest, IngestResult
from ..services.ingestion import ingest_incident

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def ingest(req: IngestRequest, db: Session = Depends(get_db)):
    return ingest_incident(db, req)
