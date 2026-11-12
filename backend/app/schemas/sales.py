import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class SalesHistoryBase(BaseModel):
    sku_id: uuid.UUID
    store_id: uuid.UUID
    sale_date: date
    units_sold: int = Field(..., ge=0)
    revenue: Decimal = Field(..., ge=0)
    is_promotion: bool = False
    promotion_discount_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    day_of_week: int = Field(..., ge=0, le=6)


class SalesHistoryResponse(SalesHistoryBase):
    id: int
    created_at: datetime
    sku_code: str | None = None
    store_code: str | None = None

    model_config = ConfigDict(from_attributes=True)

