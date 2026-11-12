import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class SKUBase(BaseModel):
    sku_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    category: str = Field(..., max_length=64)
    subcategory: str | None = Field(default=None, max_length=64)
    unit_cost: Decimal = Field(..., ge=0)
    unit_price: Decimal = Field(..., ge=0)
    pack_size: int = Field(default=1, ge=1)
    is_active: bool = True


class SKUCreate(SKUBase):
    pass


class SKUUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    unit_cost: Decimal | None = None
    unit_price: Decimal | None = None
    pack_size: int | None = None
    is_active: bool | None = None


class SKUResponse(SKUBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

