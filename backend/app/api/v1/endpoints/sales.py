import math
import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.sales import SalesHistory
from app.models.sku import SKU
from app.models.store import Store
from app.schemas.sales import SalesHistoryResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SalesHistoryResponse])
def list_sales(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    store_id: Optional[uuid.UUID] = None,
    sku_id: Optional[uuid.UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    promotion_only: bool = False,
    db: Session = Depends(get_db),
):
    query = (
        select(
            SalesHistory,
            SKU.sku_code.label("sku_code"),
            Store.store_code.label("store_code"),
        )
        .join(SKU, SalesHistory.sku_id == SKU.id)
        .join(Store, SalesHistory.store_id == Store.id)
    )

    if store_id:
        query = query.where(SalesHistory.store_id == store_id)
    if sku_id:
        query = query.where(SalesHistory.sku_id == sku_id)
    if start_date:
        query = query.where(SalesHistory.sale_date >= start_date)
    if end_date:
        query = query.where(SalesHistory.sale_date <= end_date)
    if promotion_only:
        query = query.where(SalesHistory.is_promotion.is_(True))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        query.order_by(SalesHistory.sale_date.desc(), SalesHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for sale, sku_code, store_code in rows:
        resp = SalesHistoryResponse.model_validate(sale)
        resp.sku_code = sku_code
        resp.store_code = store_code
        items.append(resp)

    return PaginatedResponse[SalesHistoryResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

