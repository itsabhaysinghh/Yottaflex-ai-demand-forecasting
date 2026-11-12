import math
import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.inventory import InventorySnapshot
from app.models.sku import SKU
from app.models.store import Store
from app.schemas.inventory import InventorySnapshotResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[InventorySnapshotResponse])
def list_inventory(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    store_id: Optional[uuid.UUID] = None,
    sku_id: Optional[uuid.UUID] = None,
    snapshot_date: Optional[date] = None,
    stockout_only: bool = False,
    db: Session = Depends(get_db),
):
    query = (
        select(
            InventorySnapshot,
            SKU.sku_code.label("sku_code"),
            Store.store_code.label("store_code"),
        )
        .join(SKU, InventorySnapshot.sku_id == SKU.id)
        .join(Store, InventorySnapshot.store_id == Store.id)
    )

    if store_id:
        query = query.where(InventorySnapshot.store_id == store_id)
    if sku_id:
        query = query.where(InventorySnapshot.sku_id == sku_id)
    if snapshot_date:
        query = query.where(InventorySnapshot.snapshot_date == snapshot_date)
    if stockout_only:
        query = query.where(InventorySnapshot.stockout_flag.is_(True))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        query.order_by(InventorySnapshot.snapshot_date.desc(), InventorySnapshot.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for snapshot, sku_code, store_code in rows:
        resp = InventorySnapshotResponse.model_validate(snapshot)
        resp.sku_code = sku_code
        resp.store_code = store_code
        items.append(resp)

    return PaginatedResponse[InventorySnapshotResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

