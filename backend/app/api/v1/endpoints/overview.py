from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.sku import SKU
from app.models.store import Store
from app.models.supplier import Supplier
from app.models.inventory import InventorySnapshot
from app.models.sales import SalesHistory
from app.models.recommendation import PurchaseRecommendation
from app.models.exception import InventoryException
from app.schemas.dashboard import OverviewMetricsResponse, CategoryMetrics, StoreCapacityMetrics

router = APIRouter()


@router.get("", response_model=OverviewMetricsResponse)
def get_overview_metrics(db: Session = Depends(get_db)):
    """
    Returns aggregated KPIs and high-level portfolio metrics for the dashboard.
    """
    total_skus = db.scalar(select(func.count(SKU.id))) or 0
    total_stores = db.scalar(select(func.count(Store.id))) or 0
    total_suppliers = db.scalar(select(func.count(Supplier.id))) or 0

    # Latest inventory snapshot date
    latest_inv_date = db.scalar(select(func.max(InventorySnapshot.snapshot_date)))

    if latest_inv_date:
        total_inv_units = db.scalar(
            select(func.sum(InventorySnapshot.closing_stock))
            .where(InventorySnapshot.snapshot_date == latest_inv_date)
        ) or 0
        active_stockouts = db.scalar(
            select(func.count(InventorySnapshot.id))
            .where(
                InventorySnapshot.snapshot_date == latest_inv_date,
                InventorySnapshot.stockout_flag.is_(True),
            )
        ) or 0
    else:
        total_inv_units = 0
        active_stockouts = 0

    # Total valuation (sum of closing_stock * unit_cost)
    if latest_inv_date:
        inv_val_query = (
            select(func.sum(InventorySnapshot.closing_stock * SKU.unit_cost))
            .join(SKU, InventorySnapshot.sku_id == SKU.id)
            .where(InventorySnapshot.snapshot_date == latest_inv_date)
        )
        total_valuation = db.scalar(inv_val_query) or Decimal("0.00")
    else:
        total_valuation = Decimal("0.00")

    # Recommendations & Exceptions count
    pending_recs = db.scalar(
        select(func.count(PurchaseRecommendation.id))
        .where(PurchaseRecommendation.status == "PENDING")
    ) or 0

    critical_exc = db.scalar(
        select(func.count(InventoryException.id))
        .where(
            InventoryException.is_resolved.is_(False),
            InventoryException.severity.in_(["CRITICAL", "HIGH"]),
        )
    ) or 0

    # Category summaries
    cat_rows = db.execute(
        select(
            SKU.category,
            func.count(SKU.id.distinct()).label("sku_count"),
            func.coalesce(func.sum(SalesHistory.units_sold), 0).label("units_sold"),
            func.coalesce(func.sum(SalesHistory.revenue), Decimal("0.00")).label("revenue"),
        )
        .outerjoin(SalesHistory, SKU.id == SalesHistory.sku_id)
        .group_by(SKU.category)
    ).all()

    categories = [
        CategoryMetrics(
            category=row.category,
            sku_count=row.sku_count,
            total_sales_units=row.units_sold,
            total_revenue=row.revenue,
        )
        for row in cat_rows
    ]

    # Store capacity utilization
    if latest_inv_date:
        store_query = (
            select(
                Store.store_code,
                Store.name,
                Store.warehouse_capacity_units,
                func.coalesce(func.sum(InventorySnapshot.closing_stock), 0).label("current_units"),
            )
            .outerjoin(
                InventorySnapshot,
                (Store.id == InventorySnapshot.store_id) & (InventorySnapshot.snapshot_date == latest_inv_date),
            )
            .group_by(Store.id)
        )
    else:
        store_query = (
            select(
                Store.store_code,
                Store.name,
                Store.warehouse_capacity_units,
                func.coalesce(0, 0).label("current_units"),
            )
            .group_by(Store.id)
        )

    store_rows = db.execute(store_query).all()

    store_capacities = [
        StoreCapacityMetrics(
            store_code=row.store_code,
            name=row.name,
            warehouse_capacity_units=row.warehouse_capacity_units,
            current_inventory_units=row.current_units,
            utilization_pct=round((row.current_units / row.warehouse_capacity_units) * 100, 2)
            if row.warehouse_capacity_units > 0 else 0.0,
        )
        for row in store_rows
    ]

    return OverviewMetricsResponse(
        total_skus=total_skus,
        total_stores=total_stores,
        total_suppliers=total_suppliers,
        total_inventory_units=total_inv_units,
        total_inventory_valuation=Decimal(str(round(total_valuation, 2))),
        active_stockouts_count=active_stockouts,
        pending_recommendations_count=pending_recs,
        critical_exceptions_count=critical_exc,
        categories=categories,
        store_capacities=store_capacities,
    )
