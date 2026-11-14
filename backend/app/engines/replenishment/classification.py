from typing import Any, Literal
from uuid import UUID

import numpy as np
from sqlalchemy import and_, case, func, null, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.engines.replenishment.formulas import (
    ReorderPointCalculation,
    calculate_reorder_point_details,
)
from app.models.inventory import InventorySnapshot
from app.models.lead_time import LeadTimeObservation
from app.models.recommendation import PurchaseRecommendation
from app.models.reorder_policy import ReorderPolicy
from app.models.sales import SalesHistory
from app.models.sku import SKU
from app.models.store import Store
from app.models.supplier_sku import SupplierSKU


InventoryPair = tuple[UUID, UUID]
InventoryStatus = Literal["STOCKOUT", "LOW", "HEALTHY", "UNKNOWN"]


def load_inventory_reorder_points(
    db: Session,
) -> dict[InventoryPair, ReorderPointCalculation]:
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
    candidate_pairs = (
        select(
            InventorySnapshot.sku_id.label("sku_id"),
            InventorySnapshot.store_id.label("store_id"),
        )
        .join(SKU, SKU.id == InventorySnapshot.sku_id)
        .join(Store, Store.id == InventorySnapshot.store_id)
        .outerjoin(
            latest_recommendations,
            (latest_recommendations.c.sku_id == InventorySnapshot.sku_id)
            & (latest_recommendations.c.store_id == InventorySnapshot.store_id)
            & (latest_recommendations.c.row_num == 1),
        )
        .where(
            SKU.is_active.is_(True),
            Store.is_active.is_(True),
            latest_recommendations.c.reorder_point.is_(None),
        )
        .distinct()
        .subquery()
    )
    pairs = db.execute(
        select(candidate_pairs.c.sku_id, candidate_pairs.c.store_id)
    ).all()
    if not pairs:
        return {}

    sku_ids = {pair.sku_id for pair in pairs}
    store_ids = {pair.store_id for pair in pairs}

    policies = db.scalars(
        select(ReorderPolicy).where(
            ReorderPolicy.sku_id.in_(sku_ids),
            ReorderPolicy.store_id.in_(store_ids),
            ReorderPolicy.is_active.is_(True),
        )
    ).all()
    policies_by_pair: dict[InventoryPair, ReorderPolicy] = {
        (policy.sku_id, policy.store_id): policy for policy in policies
    }

    suppliers = db.scalars(
        select(SupplierSKU)
        .where(
            SupplierSKU.sku_id.in_(sku_ids),
            SupplierSKU.is_primary.is_(True),
        )
        .order_by(SupplierSKU.sku_id, SupplierSKU.id)
    ).all()
    suppliers_by_sku: dict[UUID, SupplierSKU] = {}
    for supplier in suppliers:
        suppliers_by_sku.setdefault(supplier.sku_id, supplier)

    ranked_sales = (
        select(
            SalesHistory.sku_id,
            SalesHistory.store_id,
            SalesHistory.units_sold,
            func.row_number()
            .over(
                partition_by=[SalesHistory.sku_id, SalesHistory.store_id],
                order_by=[SalesHistory.sale_date.desc(), SalesHistory.id.desc()],
            )
            .label("row_num"),
        )
        .join(
            candidate_pairs,
            (candidate_pairs.c.sku_id == SalesHistory.sku_id)
            & (candidate_pairs.c.store_id == SalesHistory.store_id),
        )
        .subquery()
    )
    sales_rows = db.execute(
        select(
            ranked_sales.c.sku_id,
            ranked_sales.c.store_id,
            ranked_sales.c.units_sold,
        ).where(ranked_sales.c.row_num <= 30)
    ).all()
    sales_by_pair: dict[InventoryPair, list[int]] = {}
    for row in sales_rows:
        sales_by_pair.setdefault((row.sku_id, row.store_id), []).append(row.units_sold)

    supplier_ids = {supplier.id for supplier in suppliers_by_sku.values()}
    lead_times_by_supplier: dict[UUID, list[int]] = {}
    if supplier_ids:
        ranked_lead_times = (
            select(
                LeadTimeObservation.supplier_sku_id,
                LeadTimeObservation.actual_lead_time_days,
                func.row_number()
                .over(
                    partition_by=LeadTimeObservation.supplier_sku_id,
                    order_by=[
                        LeadTimeObservation.actual_delivery_date.desc(),
                        LeadTimeObservation.id.desc(),
                    ],
                )
                .label("row_num"),
            )
            .where(LeadTimeObservation.supplier_sku_id.in_(supplier_ids))
            .subquery()
        )
        lead_time_rows = db.execute(
            select(
                ranked_lead_times.c.supplier_sku_id,
                ranked_lead_times.c.actual_lead_time_days,
            ).where(ranked_lead_times.c.row_num <= 10)
        ).all()
        for row in lead_time_rows:
            lead_times_by_supplier.setdefault(row.supplier_sku_id, []).append(
                row.actual_lead_time_days
            )

    calculations: dict[InventoryPair, ReorderPointCalculation] = {}
    for pair in pairs:
        key = (pair.sku_id, pair.store_id)
        policy = policies_by_pair.get(key)
        supplier = suppliers_by_sku.get(pair.sku_id)
        recent_sales = sales_by_pair.get(key)
        if policy is None or supplier is None or not recent_sales:
            continue

        lead_times = lead_times_by_supplier.get(supplier.id, [])
        avg_daily_demand = float(np.mean(recent_sales))
        demand_std_dev = (
            float(np.std(recent_sales)) if len(recent_sales) > 1 else 0.5
        )
        avg_lead_time = (
            float(np.mean(lead_times))
            if lead_times
            else float(supplier.contract_lead_time_days)
        )
        lead_time_std_dev = (
            float(np.std(lead_times)) if len(lead_times) > 1 else 1.0
        )
        calculations[key] = calculate_reorder_point_details(
            avg_daily_demand=avg_daily_demand,
            demand_std_dev=demand_std_dev,
            avg_lead_time_days=avg_lead_time,
            lead_time_std_dev=lead_time_std_dev,
            service_level=float(policy.target_service_level),
            min_safety_stock=policy.min_safety_stock_units,
            max_safety_stock=policy.max_safety_stock_units,
        )

    return calculations


def reorder_point_expression(
    calculations: dict[InventoryPair, ReorderPointCalculation],
    sku_column: ColumnElement[Any],
    store_column: ColumnElement[Any],
    field: Literal["reorder_point", "safety_stock"],
) -> ColumnElement[Any]:
    if not calculations:
        return null()
    return case(
        *[
            (
                and_(sku_column == sku_id, store_column == store_id),
                getattr(calculation, field),
            )
            for (sku_id, store_id), calculation in calculations.items()
        ],
        else_=None,
    )


def inventory_status_expression(
    sku_is_active: ColumnElement[Any],
    store_is_active: ColumnElement[Any],
    stockout_flag: ColumnElement[Any],
    available_units: ColumnElement[Any],
    inventory_position: ColumnElement[Any],
    reorder_point: ColumnElement[Any],
) -> ColumnElement[Any]:
    return case(
        (
            or_(sku_is_active.is_(False), store_is_active.is_(False)),
            "UNKNOWN",
        ),
        (
            or_(stockout_flag.is_(True), available_units <= 0),
            "STOCKOUT",
        ),
        (reorder_point.is_(None), "UNKNOWN"),
        (inventory_position <= reorder_point, "LOW"),
        else_="HEALTHY",
    )


def classify_inventory_position(
    *,
    sku_is_active: bool,
    store_is_active: bool,
    stockout_flag: bool,
    available_units: int,
    inventory_position: int,
    reorder_point: int | None,
) -> InventoryStatus:
    if not sku_is_active or not store_is_active:
        return "UNKNOWN"
    if stockout_flag or available_units <= 0:
        return "STOCKOUT"
    if reorder_point is None:
        return "UNKNOWN"
    if inventory_position <= reorder_point:
        return "LOW"
    return "HEALTHY"
