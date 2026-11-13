import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List
from pydantic import BaseModel, ConfigDict, Field


class ForecastBase(BaseModel):
    sku_id: uuid.UUID
    store_id: uuid.UUID
    model_name: str = Field(..., max_length=64)
    forecast_date: date
    target_date: date
    horizon_days: int = Field(..., ge=1)
    predicted_units: Decimal = Field(..., ge=0)
    confidence_lower: Decimal | None = None
    confidence_upper: Decimal | None = None
    model_params: Dict[str, Any] = Field(default_factory=dict)


class ForecastResponse(ForecastBase):
    id: uuid.UUID
    created_at: datetime
    sku_code: str | None = None
    store_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ForecastRunRequest(BaseModel):
    sku_id: uuid.UUID | None = None
    store_id: uuid.UUID | None = None
    model_name: str = Field(default="moving_average")
    horizon_days: int = Field(default=14, ge=1, le=90)
    adjust_censored_demand: bool = True


class ForecastEvaluationResponse(BaseModel):
    id: int
    sku_id: uuid.UUID
    store_id: uuid.UUID
    model_name: str
    evaluation_date: date
    horizon_days: int
    mae: Decimal
    rmse: Decimal
    wape: Decimal | None
    bias: Decimal
    sample_size: int
    sku_code: str | None = None
    store_code: str | None = None

    model_config = ConfigDict(from_attributes=True)

