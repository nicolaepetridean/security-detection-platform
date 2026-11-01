"""Pydantic request/response schemas (API contract)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import DetectionStatus, Role


# ---- Auth ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: Role


# ---- Customers ----
class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    importance: int = Field(ge=1, le=5)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    importance: int | None = Field(default=None, ge=1, le=5)


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    importance: int


# ---- Signatures ----
class SignatureCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    priority: int = Field(ge=1, le=5)
    # At least one field/value pair is required for a usable signature.
    match_fields: dict[str, object] = Field(min_length=1)


class SignatureUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    priority: int | None = Field(default=None, ge=1, le=5)
    match_fields: dict[str, object] | None = Field(default=None, min_length=1)


class SignatureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    priority: int
    match_fields: dict[str, object]


# ---- Ingestion ----
class IngestRequest(BaseModel):
    """An incoming incident from an external source.

    customer_id identifies which customer the incident belongs to; the remaining fields
    are arbitrary and are matched against signatures.
    """

    customer_id: int
    fields: dict[str, object]


class IngestResult(BaseModel):
    matched: bool
    detection_id: int | None = None
    signature_id: int | None = None
    priority: int | None = None


# ---- Detections ----
class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    signature_id: int
    customer_id: int
    priority: int
    status: DetectionStatus
    assignee_id: int | None
    resolution: str | None
    raw_payload: dict
    created_at: datetime
    resolved_at: datetime | None


class CloseRequest(BaseModel):
    resolution: str = Field(min_length=1)
