from datetime import date, datetime, timezone
from decimal import Decimal
import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.recommendation import PurchaseRecommendation
from app.models.exception import InventoryException
from app.models.sku import SKU
from app.models.store import Store
from app.models.supplier import Supplier
from app.models.supplier_sku import SupplierSKU
from app.models.reorder_policy import ReorderPolicy
from app.models.inventory import InventorySnapshot
from app.models.sales import SalesHistory
from app.models.lead_time import LeadTimeObservation
from app.schemas.recommendation import (
    PurchaseRecommendationResponse,
    RecommendationReviewRequest,
    RecommendationRunRequest,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.engines.replenishment import ReplenishmentEngine

router = APIRouter()
ACTIVE_CYCLE_INDEX = "uq_purchase_recommendations_current_cycle"


def _is_active_cycle_conflict(error: IntegrityError) -> bool:
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    return sqlstate == "23505" and constraint_name == ACTIVE_CYCLE_INDEX


@router.get("", response_model=PaginatedResponse[PurchaseRecommendationResponse])
def list_recommendations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    include_superseded: bool = Query(default=False),
    store_id: Optional[uuid.UUID] = None,
    sku_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    query = (
        select(
            PurchaseRecommendation,
            SKU.sku_code.label("sku_code"),
            SKU.name.label("sku_name"),
            Store.store_code.label("store_code"),
            Supplier.name.label("supplier_name"),
            SupplierSKU.minimum_order_quantity.label("minimum_order_quantity"),
            SupplierSKU.pack_size.label("pack_size"),
        )
        .join(SKU, PurchaseRecommendation.sku_id == SKU.id)
        .join(Store, PurchaseRecommendation.store_id == Store.id)
        .join(Supplier, PurchaseRecommendation.supplier_id == Supplier.id)
        .outerjoin(
            SupplierSKU,
            (SupplierSKU.sku_id == PurchaseRecommendation.sku_id)
            & (SupplierSKU.supplier_id == PurchaseRecommendation.supplier_id),
        )
    )

    if status_filter:
        query = query.where(PurchaseRecommendation.status == status_filter)
    if not include_superseded:
        query = query.where(PurchaseRecommendation.superseded_at.is_(None))
    if store_id:
        query = query.where(PurchaseRecommendation.store_id == store_id)
    if sku_id:
        query = query.where(PurchaseRecommendation.sku_id == sku_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        query.order_by(PurchaseRecommendation.recommendation_date.desc(), PurchaseRecommendation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for (
        rec,
        sku_code,
        sku_name,
        store_code,
        supp_name,
        minimum_order_quantity,
        pack_size,
    ) in rows:
        resp = PurchaseRecommendationResponse.model_validate(rec)
        resp.sku_code = sku_code
        resp.sku_name = sku_name
        resp.store_code = store_code
        resp.supplier_name = supp_name
        resp.minimum_order_quantity = minimum_order_quantity
        resp.pack_size = pack_size
        items.append(resp)

    return PaginatedResponse[PurchaseRecommendationResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.patch("/{rec_id}", response_model=PurchaseRecommendationResponse)
def review_recommendation(
    rec_id: uuid.UUID,
    payload: RecommendationReviewRequest,
    db: Session = Depends(get_db),
):
    """
    Decision support approval workflow: Human planner approves or rejects purchase proposal.
    """
    rec = db.get(PurchaseRecommendation, rec_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {rec_id} not found",
        )

    if rec.superseded_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Superseded recommendations cannot be reviewed.",
        )

    if rec.status in ["APPROVED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recommendation has already been reviewed ({rec.status}).",
        )

    if rec.status == "FLAGGED_EXCEPTION" and payload.status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Capacity-flagged recommendations cannot be approved as purchase "
                "orders. Resolve the associated warehouse-capacity exception first."
            ),
        )

    rec.status = payload.status
    rec.reviewed_by = payload.reviewed_by
    rec.review_notes = payload.review_notes
    rec.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(rec)

    resp = PurchaseRecommendationResponse.model_validate(rec)
    if rec.sku:
        resp.sku_code = rec.sku.sku_code
        resp.sku_name = rec.sku.name
    if rec.store:
        resp.store_code = rec.store.store_code
    if rec.supplier:
        resp.supplier_name = rec.supplier.name

    return resp


@router.post("/run", response_model=MessageResponse)
def run_replenishment_pipeline(
    payload: RecommendationRunRequest,
    db: Session = Depends(get_db),
):
    """
    Executes replenishment calculations: evaluates current inventory against
    ROP, calculates order quantity, rounds to pack size, checks MOQ, enforces
    store warehouse capacity, and flags exceptions.
    """
    stores_query = select(Store).where(Store.is_active.is_(True)).order_by(Store.id)
    if payload.store_id:
        stores_query = stores_query.where(Store.id == payload.store_id)
    stores = db.scalars(stores_query).all()

    latest_date = db.scalar(select(func.max(InventorySnapshot.snapshot_date))) or date.today()

    recommendations_created = 0
    exceptions_created = 0
    existing_cycles_skipped = 0

    for store in stores:
        # Calculate store's current total units on hand
        store_total_inv = db.scalar(
            select(func.coalesce(func.sum(InventorySnapshot.closing_stock), 0))
            .where(
                InventorySnapshot.store_id == store.id,
                InventorySnapshot.snapshot_date == latest_date,
            )
        ) or 0

        # Query all active SKUs
        sku_query = select(SKU).where(SKU.is_active.is_(True)).order_by(SKU.id)
        if payload.sku_id:
            sku_query = sku_query.where(SKU.id == payload.sku_id)
        skus = db.scalars(sku_query).all()

        for sku in skus:
            inv = db.scalar(
                select(InventorySnapshot)
                .where(
                    InventorySnapshot.sku_id == sku.id,
                    InventorySnapshot.store_id == store.id,
                    InventorySnapshot.snapshot_date == latest_date,
                )
                .with_for_update()
            )
            if not inv:
                continue

            existing_cycle = db.scalar(
                select(PurchaseRecommendation.id)
                .where(
                    PurchaseRecommendation.sku_id == sku.id,
                    PurchaseRecommendation.store_id == store.id,
                    PurchaseRecommendation.recommendation_date == latest_date,
                    PurchaseRecommendation.superseded_at.is_(None),
                )
                .limit(1)
            )
            if existing_cycle is not None:
                # A SKU/store/date is one replenishment cycle; keep prior reviews immutable.
                existing_cycles_skipped += 1
                continue

            # Sourcing info
            supp_sku = db.scalar(
                select(SupplierSKU).where(
                    SupplierSKU.sku_id == sku.id,
                    SupplierSKU.is_primary.is_(True),
                )
            )
            if not supp_sku:
                continue

            # Policy
            policy = db.scalar(
                select(ReorderPolicy).where(
                    ReorderPolicy.sku_id == sku.id,
                    ReorderPolicy.store_id == store.id,
                )
            )
            if not policy:
                policy = ReorderPolicy(
                    sku_id=sku.id,
                    store_id=store.id,
                    target_service_level=Decimal("0.950"),
                    review_period_days=7,
                )
                db.add(policy)
                db.flush()

            # Demand history statistics (last 30 days)
            recent_sales = db.scalars(
                select(SalesHistory.units_sold)
                .where(
                    SalesHistory.sku_id == sku.id,
                    SalesHistory.store_id == store.id,
                )
                .order_by(SalesHistory.sale_date.desc())
                .limit(30)
            ).all()

            if not recent_sales:
                continue

            avg_demand = float(np.mean(recent_sales))
            std_demand = float(np.std(recent_sales)) if len(recent_sales) > 1 else 0.5

            # Lead time statistics
            lead_times = db.scalars(
                select(LeadTimeObservation.actual_lead_time_days)
                .where(LeadTimeObservation.supplier_sku_id == supp_sku.id)
                .limit(10)
            ).all()

            avg_lt = float(np.mean(lead_times)) if lead_times else float(supp_sku.contract_lead_time_days)
            std_lt = float(np.std(lead_times)) if len(lead_times) > 1 else 1.0

            sku_dict = {
                "id": sku.id,
                "sku_code": sku.sku_code,
                "name": sku.name,
                "is_active": sku.is_active,
                "pack_size": sku.pack_size,
                "unit_cost": sku.unit_cost,
            }
            store_dict = {
                "id": store.id,
                "store_code": store.store_code,
                "warehouse_capacity_units": store.warehouse_capacity_units,
            }
            supp_sku_dict = {
                "supplier_id": supp_sku.supplier_id,
                "pack_size": supp_sku.pack_size,
                "minimum_order_quantity": supp_sku.minimum_order_quantity,
                "unit_cost": supp_sku.unit_cost,
            }
            inv_dict = {
                "closing_stock": inv.closing_stock,
                "in_transit_stock": inv.in_transit_stock,
                "reserved_stock": inv.reserved_stock,
            }
            policy_dict = {
                "id": policy.id,
                "target_service_level": float(policy.target_service_level),
                "review_period_days": policy.review_period_days,
                "min_safety_stock_units": policy.min_safety_stock_units,
                "max_safety_stock_units": policy.max_safety_stock_units,
            }

            rec_data, exc_list = ReplenishmentEngine.evaluate_sku_store_replenishment(
                sku=sku_dict,
                store=store_dict,
                supplier_sku=supp_sku_dict,
                current_inventory=inv_dict,
                reorder_policy=policy_dict,
                avg_daily_demand=avg_demand,
                demand_std_dev=std_demand,
                lead_time_days=avg_lt,
                lead_time_std_dev=std_lt,
                store_current_total_units=store_total_inv,
                evaluation_date=latest_date,
                enforce_capacity=payload.enforce_capacity,
            )

            db_exceptions = [
                InventoryException(
                    sku_id=exc.get("sku_id"),
                    store_id=exc.get("store_id"),
                    supplier_id=exc.get("supplier_id"),
                    exception_type=exc["exception_type"],
                    severity=exc["severity"],
                    description=exc["description"],
                    payload=exc["payload"],
                    is_resolved=False,
                )
                for exc in exc_list
            ]

            # Persist recommendation
            if rec_data:
                db_rec = PurchaseRecommendation(
                    sku_id=rec_data["sku_id"],
                    store_id=rec_data["store_id"],
                    supplier_id=rec_data["supplier_id"],
                    reorder_policy_id=rec_data["reorder_policy_id"],
                    recommendation_date=rec_data["recommendation_date"],
                    current_on_hand=rec_data["current_on_hand"],
                    current_on_order=rec_data["current_on_order"],
                    net_inventory_position=rec_data["net_inventory_position"],
                    lead_time_demand=rec_data["lead_time_demand"],
                    safety_stock=rec_data["safety_stock"],
                    reorder_point=rec_data["reorder_point"],
                    raw_order_quantity=rec_data["raw_order_quantity"],
                    recommended_units=rec_data["recommended_units"],
                    total_cost=rec_data["total_cost"],
                    status=rec_data["status"],
                    explanation=rec_data["explanation"],
                )
                try:
                    with db.begin_nested():
                        db.add_all(db_exceptions)
                        db.add(db_rec)
                        db.flush()
                except IntegrityError as error:
                    if not _is_active_cycle_conflict(error):
                        raise
                    existing_cycles_skipped += 1
                    continue

                recommendations_created += 1
                exceptions_created += len(db_exceptions)
                if rec_data["status"] != "FLAGGED_EXCEPTION":
                    store_total_inv += rec_data["recommended_units"]
            else:
                db.add_all(db_exceptions)
                exceptions_created += len(db_exceptions)

    db.commit()

    return MessageResponse(
        message=(
            f"Replenishment run complete: generated {recommendations_created} recommendations "
            f"and flagged {exceptions_created} exceptions; "
            f"skipped {existing_cycles_skipped} existing replenishment cycles."
        ),
        success=True,
    )
