import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class InventorySnapshotBase(BaseModel):
    sku_id: uuid.UUID
    store_id: uuid.UUID
    snapshot_date: date
    opening_stock: int = Field(..., ge=0)
    closing_stock: int = Field(..., ge=0)
    in_transit_stock: int = Field(default=0, ge=0)
    reserved_stock: int = Field(default=0, ge=0)
    stockout_flag: bool = False
    lost_sales_estimate: int = Field(default=0, ge=0)


class InventorySnapshotResponse(InventorySnapshotBase):
    id: int
    created_at: datetime
    sku_code: str | None = None
    sku_name: str | None = None
    category: str | None = None
    store_code: str | None = None
    available_units: int | None = None
    reorder_point: int | None = None
    safety_stock_units: int | None = None
    inventory_status: str | None = None

    model_config = ConfigDict(from_attributes=True)
