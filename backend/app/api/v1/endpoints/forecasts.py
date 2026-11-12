import math
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.forecast import Forecast
from app.models.evaluation import ForecastEvaluation
from app.models.sales import SalesHistory
from app.models.inventory import InventorySnapshot
from app.models.sku import SKU
from app.models.store import Store
from app.schemas.forecast import ForecastResponse, ForecastRunRequest, ForecastEvaluationResponse
from app.schemas.common import PaginatedResponse, MessageResponse
from app.engines.forecasting import ForecastingEngine

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ForecastResponse])
def list_forecasts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    store_id: Optional[uuid.UUID] = None,
    sku_id: Optional[uuid.UUID] = None,
    model_name: Optional[str] = None,
    forecast_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    query = (
        select(
            Forecast,
            SKU.sku_code.label("sku_code"),
            Store.store_code.label("store_code"),
        )
        .join(SKU, Forecast.sku_id == SKU.id)
        .join(Store, Forecast.store_id == Store.id)
    )

    if store_id:
        query = query.where(Forecast.store_id == store_id)
    if sku_id:
        query = query.where(Forecast.sku_id == sku_id)
    if model_name:
        query = query.where(Forecast.model_name == model_name)
    if forecast_date:
        query = query.where(Forecast.forecast_date == forecast_date)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        query.order_by(Forecast.target_date.asc(), Forecast.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for fc, sku_code, store_code in rows:
        resp = ForecastResponse.model_validate(fc)
        resp.sku_code = sku_code
        resp.store_code = store_code
        items.append(resp)

    return PaginatedResponse[ForecastResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/evaluations", response_model=PaginatedResponse[ForecastEvaluationResponse])
def list_forecast_evaluations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    model_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = (
        select(
            ForecastEvaluation,
            SKU.sku_code.label("sku_code"),
            Store.store_code.label("store_code"),
        )
        .join(SKU, ForecastEvaluation.sku_id == SKU.id)
        .join(Store, ForecastEvaluation.store_id == Store.id)
    )

    if model_name:
        query = query.where(ForecastEvaluation.model_name == model_name)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        query.order_by(ForecastEvaluation.evaluation_date.desc(), ForecastEvaluation.wape.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for ev, sku_code, store_code in rows:
        resp = ForecastEvaluationResponse.model_validate(ev)
        resp.sku_code = sku_code
        resp.store_code = store_code
        items.append(resp)

    return PaginatedResponse[ForecastEvaluationResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/run", response_model=MessageResponse)
def run_forecasting_pipeline(
    payload: ForecastRunRequest,
    db: Session = Depends(get_db),
):
    """
    Executes demand forecast generation for specified SKU/Store pair or all active pairs.
    Persists predictions and out-of-sample backtest evaluations.
    """
    # Fetch distinct active pairs
    pair_query = select(SalesHistory.sku_id, SalesHistory.store_id).distinct()
    if payload.sku_id:
        pair_query = pair_query.where(SalesHistory.sku_id == payload.sku_id)
    if payload.store_id:
        pair_query = pair_query.where(SalesHistory.store_id == payload.store_id)

    pairs = db.execute(pair_query).all()
    if not pairs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sales history found matching the specified parameters.",
        )

    forecasts_created = 0

    for sku_id, store_id in pairs:
        sales_records = db.execute(
            select(
                SalesHistory.sale_date,
                SalesHistory.units_sold,
                SalesHistory.day_of_week,
                InventorySnapshot.stockout_flag,
            )
            .outerjoin(
                InventorySnapshot,
                (SalesHistory.sku_id == InventorySnapshot.sku_id)
                & (SalesHistory.store_id == InventorySnapshot.store_id)
                & (SalesHistory.sale_date == InventorySnapshot.snapshot_date),
            )
            .where(SalesHistory.sku_id == sku_id, SalesHistory.store_id == store_id)
            .order_by(SalesHistory.sale_date.asc())
        ).all()

        if len(sales_records) < 14:
            continue

        df = pd.DataFrame([
            {
                "sale_date": r.sale_date,
                "units_sold": r.units_sold,
                "day_of_week": r.day_of_week,
                "stockout_flag": r.stockout_flag or False,
            }
            for r in sales_records
        ])

        # 1. Backtest Evaluation
        try:
            eval_res = ForecastingEngine.run_temporal_evaluation(
                history_df=df,
                model_name=payload.model_name,
                test_horizon_days=min(14, len(df) // 4),
                adjust_censoring=payload.adjust_censored_demand,
            )
            m = eval_res["metrics"]
            db_eval = ForecastEvaluation(
                sku_id=sku_id,
                store_id=store_id,
                model_name=payload.model_name,
                evaluation_date=eval_res["test_min_date"],
                horizon_days=eval_res["test_horizon_days"],
                mae=Decimal(str(m["mae"])),
                rmse=Decimal(str(m["rmse"])),
                wape=Decimal(str(m["wape"])),
                bias=Decimal(str(m["bias"])),
                sample_size=m["sample_size"],
            )
            db.merge(db_eval)
        except Exception:
            pass

        # 2. Future Forecast Projections
        future_preds = ForecastingEngine.generate_future_forecast(
            history_df=df,
            model_name=payload.model_name,
            horizon_days=payload.horizon_days,
            adjust_censoring=payload.adjust_censored_demand,
        )

        for p in future_preds:
            fc = Forecast(
                sku_id=sku_id,
                store_id=store_id,
                model_name=payload.model_name,
                forecast_date=p["forecast_date"],
                target_date=p["target_date"],
                horizon_days=p["horizon_days"],
                predicted_units=Decimal(str(p["predicted_units"])),
                confidence_lower=Decimal(str(p["confidence_lower"])),
                confidence_upper=Decimal(str(p["confidence_upper"])),
                model_params=p["model_params"],
            )
            db.merge(fc)
            forecasts_created += 1

    db.commit()

    return MessageResponse(
        message=f"Forecasting pipeline completed successfully. Generated {forecasts_created} projections.",
        success=True,
    )

