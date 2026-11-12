import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class SupplierBase(BaseModel):
    supplier_code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=255)
    contact_email: str | None = None
    default_lead_time_days: int = Field(default=7, ge=1)
    reliability_score: Decimal = Field(default=Decimal("0.95"), ge=0, le=1)
    is_active: bool = True


class SupplierResponse(SupplierBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierSKUBase(BaseModel):
    supplier_id: uuid.UUID
    sku_id: uuid.UUID
    contract_lead_time_days: int = Field(default=7, ge=1)
    minimum_order_quantity: int = Field(default=1, ge=1)
    pack_size: int = Field(default=1, ge=1)
    unit_cost: Decimal = Field(..., ge=0)
    is_primary: bool = True


class SupplierSKUResponse(SupplierSKUBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    supplier_name: str | None = None
    sku_code: str | None = None

    model_config = ConfigDict(from_attributes=True)

