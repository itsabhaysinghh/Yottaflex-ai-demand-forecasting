import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class StoreBase(BaseModel):
    store_code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=128)
    store_type: str = Field(default="standard", max_length=32)
    warehouse_capacity_units: int = Field(..., gt=0)
    is_active: bool = True


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: str | None = None
    store_type: str | None = None
    warehouse_capacity_units: int | None = None
    is_active: bool | None = None


class StoreResponse(StoreBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

