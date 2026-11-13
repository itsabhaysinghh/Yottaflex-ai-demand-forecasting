from decimal import Decimal
from datetime import timedelta
from fastapi import APIRouter, Depends, Query
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
from app.models.reorder_policy import ReorderPolicy
from app.models.evaluation import ForecastEvaluation
from app.schemas.dashboard import (
    DashboardTrendsResponse,
    InventoryDistribution,
    OverviewMetricsResponse,
    CategoryMetrics,
    StoreCapacityMetrics,
    TrendPoint,
)

router = APIRouter()


@router.get("", response_model=OverviewMetricsResponse)
def get_overview_metrics(db: Session = Depends(get_db)):
    """
    Returns aggregated KPIs and high-level portfolio metrics for the dashboard.
    """
    total_skus = db.scalar(select(func.count(SKU.id))) or 0
    total_stores = db.scalar(select(func.count(Store.id))) or 0
    total_suppliers = db.scalar(select(func.count(Supplier.id))) or 0
    active_stores = db.scalar(
        select(func.count(Store.id)).where(Store.is_active.is_(True))
    ) or 0

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
        .where(
            PurchaseRecommendation.status == "PENDING",
            PurchaseRecommendation.superseded_at.is_(None),
        )
    ) or 0

    critical_exc = db.scalar(
        select(func.count(InventoryException.id))
        .where(
            InventoryException.is_resolved.is_(False),
            InventoryException.severity.in_(["CRITICAL", "HIGH"]),
        )
    ) or 0

    low_stock_products = 0
    inventory_health_pct = None
    if latest_inv_date:
        latest_recommendations = (
            select(
                PurchaseRecommendation.sku_id,
                PurchaseRecommendation.store_id,
                PurchaseRecommendation.reorder_point,
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
        inventory_rows = db.execute(
            select(
                InventorySnapshot.sku_id,
                InventorySnapshot.closing_stock,
                InventorySnapshot.in_transit_stock,
                InventorySnapshot.reserved_stock,
                InventorySnapshot.stockout_flag,
                latest_recommendations.c.reorder_point,
            )
            .join(SKU, SKU.id == InventorySnapshot.sku_id)
            .join(Store, Store.id == InventorySnapshot.store_id)
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
            .where(
                InventorySnapshot.snapshot_date == latest_inv_date,
                SKU.is_active.is_(True),
                Store.is_active.is_(True),
            )
        ).all()
        low_stock_skus = set()
        known_status_count = 0
        healthy_count = 0
        for row in inventory_rows:
            inventory_position = row.closing_stock + row.in_transit_stock - row.reserved_stock
            #  Stockout status uses physical units.
            is_stockout = row.stockout_flag or (row.closing_stock - row.reserved_stock) <= 0
            if row.reorder_point is None and not is_stockout:
                continue
            known_status_count += 1
            is_low = is_stockout or (
                row.reorder_point is not None
                and inventory_position <= row.reorder_point
            )
            if is_low:
                low_stock_skus.add(row.sku_id)
            else:
                healthy_count += 1
        low_stock_products = len(low_stock_skus)
        if known_status_count:
            inventory_health_pct = round(
                healthy_count / known_status_count * 100, 2
            )

    latest_evaluation_date = db.scalar(
        select(func.max(ForecastEvaluation.evaluation_date))
    )
    average_wape = (
        db.scalar(
            select(func.avg(ForecastEvaluation.wape)).where(
                ForecastEvaluation.evaluation_date == latest_evaluation_date
            )
        )
        if latest_evaluation_date
        else None
    )
    forecast_accuracy_pct = (
        round(max(0.0, min(100.0, (1 - float(average_wape)) * 100)), 2)
        if average_wape is not None
        else None
    )

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
        active_stores_count=active_stores,
        low_stock_products_count=low_stock_products,
        forecast_accuracy_pct=forecast_accuracy_pct,
        inventory_health_pct=inventory_health_pct,
    )


@router.get("/trends", response_model=DashboardTrendsResponse)
def get_dashboard_trends(
    days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    latest_sales_date = db.scalar(select(func.max(SalesHistory.sale_date)))
    latest_inventory_date = db.scalar(
        select(func.max(InventorySnapshot.snapshot_date))
    )

    demand_trend = []
    if latest_sales_date:
        start_date = latest_sales_date - timedelta(days=days - 1)
        demand_rows = db.execute(
            select(
                SalesHistory.sale_date,
                func.sum(SalesHistory.units_sold).label("units"),
            )
            .where(SalesHistory.sale_date >= start_date)
            .group_by(SalesHistory.sale_date)
            .order_by(SalesHistory.sale_date)
        ).all()
        demand_trend = [
            TrendPoint(date=row.sale_date.isoformat(), value=row.units)
            for row in demand_rows
        ]

    stockout_trend = []
    inventory_distribution = []
    if latest_inventory_date:
        start_date = latest_inventory_date - timedelta(days=days - 1)
        stockout_rows = db.execute(
            select(
                InventorySnapshot.snapshot_date,
                func.count(InventorySnapshot.id).label("stockouts"),
            )
            .where(
                InventorySnapshot.snapshot_date >= start_date,
                InventorySnapshot.stockout_flag.is_(True),
            )
            .group_by(InventorySnapshot.snapshot_date)
            .order_by(InventorySnapshot.snapshot_date)
        ).all()
        stockout_trend = [
            TrendPoint(date=row.snapshot_date.isoformat(), value=row.stockouts)
            for row in stockout_rows
        ]

        distribution_rows = db.execute(
            select(
                SKU.category,
                func.sum(InventorySnapshot.closing_stock).label("units"),
            )
            .join(SKU, SKU.id == InventorySnapshot.sku_id)
            .where(InventorySnapshot.snapshot_date == latest_inventory_date)
            .group_by(SKU.category)
            .order_by(SKU.category)
        ).all()
        inventory_distribution = [
            InventoryDistribution(category=row.category, units=row.units)
            for row in distribution_rows
        ]

    return DashboardTrendsResponse(
        demand_trend=demand_trend,
        stockout_trend=stockout_trend,
        inventory_distribution=inventory_distribution,
    )
