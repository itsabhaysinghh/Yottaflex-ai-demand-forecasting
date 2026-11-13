import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class PurchaseRecommendationBase(BaseModel):
    sku_id: uuid.UUID
    store_id: uuid.UUID
    supplier_id: uuid.UUID
    reorder_policy_id: uuid.UUID | None = None
    recommendation_date: date
    current_on_hand: int
    current_on_order: int
    net_inventory_position: int
    lead_time_demand: Decimal
    safety_stock: int
    reorder_point: int
    raw_order_quantity: int
    recommended_units: int
    total_cost: Decimal
    status: str = Field(default="PENDING")
    explanation: Dict[str, Any] = Field(default_factory=dict)


class PurchaseRecommendationResponse(PurchaseRecommendationBase):
    id: uuid.UUID
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    superseded_at: datetime | None = None
    superseded_by_id: uuid.UUID | None = None
    supersession_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    sku_code: str | None = None
    sku_name: str | None = None
    store_code: str | None = None
    supplier_name: str | None = None
    minimum_order_quantity: int | None = None
    pack_size: int | None = None

    model_config = ConfigDict(from_attributes=True)


class RecommendationReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reviewed_by: str = Field(..., min_length=2, max_length=128)
    review_notes: str | None = Field(default=None, max_length=500)


class RecommendationRunRequest(BaseModel):
    store_id: uuid.UUID | None = None
    sku_id: uuid.UUID | None = None
    enforce_capacity: bool = True
