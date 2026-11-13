import math
import uuid
from datetime import date
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.inventory import InventorySnapshot
from app.models.sku import SKU
from app.models.store import Store
from app.models.recommendation import PurchaseRecommendation
from app.models.reorder_policy import ReorderPolicy
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
    current_only: bool = False,
    category: Optional[str] = None,
    search: Optional[str] = None,
    status_filter: Optional[Literal["STOCKOUT", "LOW", "HEALTHY", "UNKNOWN"]] = Query(
        default=None, alias="status"
    ),
    sort_by: Literal[
        "snapshot_date",
        "sku_code",
        "category",
        "available_units",
        "incoming_units",
        "reorder_point",
        "inventory_status",
    ] = "snapshot_date",
    sort_order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
):
    latest_recommendations = (
        select(
            PurchaseRecommendation.sku_id,
            PurchaseRecommendation.store_id,
            PurchaseRecommendation.reorder_point,
            PurchaseRecommendation.safety_stock,
            func.row_number()
            .over(
                partition_by=[
                    PurchaseRecommendation.sku_id,
                    PurchaseRecommendation.store_id,
                ],
                order_by=[
                    PurchaseRecommendation.recommendation_date.desc(),
                    PurchaseRecommendation.created_at.desc(),
                ],
            )
            .label("row_num"),
        )
        .where(PurchaseRecommendation.superseded_at.is_(None))
        .subquery()
    )
    available_units = case(
        (
            InventorySnapshot.closing_stock - InventorySnapshot.reserved_stock > 0,
            InventorySnapshot.closing_stock - InventorySnapshot.reserved_stock,
        ),
        else_=0,
    )
    inventory_position = (
        InventorySnapshot.closing_stock
        + InventorySnapshot.in_transit_stock
        - InventorySnapshot.reserved_stock
    )
    inventory_status = case(
        (SKU.is_active.is_(False), "UNKNOWN"),
        (
            InventorySnapshot.stockout_flag.is_(True) | (available_units == 0),
            "STOCKOUT",
        ),
        (latest_recommendations.c.reorder_point.is_(None), "UNKNOWN"),
        (
            inventory_position <= latest_recommendations.c.reorder_point,
            "LOW",
        ),
        else_="HEALTHY",
    )

    query = (
        select(
            InventorySnapshot,
            SKU.sku_code.label("sku_code"),
            SKU.name.label("sku_name"),
            SKU.category.label("category"),
            Store.store_code.label("store_code"),
            available_units.label("available_units"),
            latest_recommendations.c.reorder_point.label("reorder_point"),
            func.coalesce(
                latest_recommendations.c.safety_stock,
                ReorderPolicy.min_safety_stock_units,
            ).label("safety_stock_units"),
            inventory_status.label("inventory_status"),
        )
        .join(SKU, InventorySnapshot.sku_id == SKU.id)
        .join(Store, InventorySnapshot.store_id == Store.id)
        .outerjoin(
            ReorderPolicy,
            (ReorderPolicy.sku_id == InventorySnapshot.sku_id)
            & (ReorderPolicy.store_id == InventorySnapshot.store_id)
            & ReorderPolicy.is_active.is_(True),
        )
        .outerjoin(
            latest_recommendations,
            (latest_recommendations.c.sku_id == InventorySnapshot.sku_id)
            & (latest_recommendations.c.store_id == InventorySnapshot.store_id)
            & (latest_recommendations.c.row_num == 1),
        )
    )

    if current_only and snapshot_date is None:
        latest_date = select(func.max(InventorySnapshot.snapshot_date)).scalar_subquery()
        query = query.where(InventorySnapshot.snapshot_date == latest_date)
    if store_id:
        query = query.where(InventorySnapshot.store_id == store_id)
    if sku_id:
        query = query.where(InventorySnapshot.sku_id == sku_id)
    if snapshot_date:
        query = query.where(InventorySnapshot.snapshot_date == snapshot_date)
    if stockout_only:
        query = query.where(InventorySnapshot.stockout_flag.is_(True))
    if category:
        query = query.where(SKU.category == category)
    if search:
        query = query.where(
            SKU.name.ilike(f"%{search}%") | SKU.sku_code.ilike(f"%{search}%")
        )
    if status_filter:
        query = query.where(inventory_status == status_filter)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    sort_columns = {
        "snapshot_date": InventorySnapshot.snapshot_date,
        "sku_code": SKU.sku_code,
        "category": SKU.category,
        "available_units": available_units,
        "incoming_units": InventorySnapshot.in_transit_stock,
        "reorder_point": latest_recommendations.c.reorder_point,
        "inventory_status": inventory_status,
    }
    sort_column = sort_columns[sort_by]
    sort_expression = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    rows = db.execute(
        query.order_by(
            sort_expression,
            InventorySnapshot.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for (
        snapshot,
        sku_code,
        sku_name,
        category,
        store_code,
        available,
        reorder_point,
        safety_stock,
        status,
    ) in rows:
        resp = InventorySnapshotResponse.model_validate(snapshot)
        resp.sku_code = sku_code
        resp.sku_name = sku_name
        resp.category = category
        resp.store_code = store_code
        resp.available_units = available
        resp.reorder_point = reorder_point
        resp.safety_stock_units = safety_stock
        resp.inventory_status = status
        items.append(resp)

    return PaginatedResponse[InventorySnapshotResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
            