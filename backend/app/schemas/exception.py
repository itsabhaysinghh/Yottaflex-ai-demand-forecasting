import uuid
from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class InventoryExceptionBase(BaseModel):
    sku_id: uuid.UUID | None = None
    store_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    exception_type: str
    severity: str = "MEDIUM"
    description: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    is_resolved: bool = False


class InventoryExceptionResponse(InventoryExceptionBase):
    id: uuid.UUID
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    sku_code: str | None = None
    store_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExceptionResolveRequest(BaseModel):
    resolved_by: str = Field(..., min_length=2, max_length=128)
    resolution_notes: str | None = Field(default=None, max_length=500)

