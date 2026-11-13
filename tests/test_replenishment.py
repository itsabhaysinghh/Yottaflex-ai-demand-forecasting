import uuid
from datetime import date
from decimal import Decimal
import pytest

from app.engines.replenishment import (
    ReplenishmentEngine,
    calculate_lead_time_demand,
    calculate_safety_stock,
    calculate_reorder_point,
    enforce_pack_and_moq,
)


def test_lead_time_demand_and_safety_stock_formulas():
    """
    Verifies LTD = D_bar * L_bar and safety stock calculations.
    """
    avg_d = 20.0
    avg_lt = 5.0
    ltd = calculate_lead_time_demand(avg_d, avg_lt)
    assert ltd == 100.0

    # Demand std dev = 4.0, lead time std dev = 1.0, 95% SL (Z ~ 1.645)
    ss, sigma_ltd = calculate_safety_stock(
        avg_daily_demand=avg_d,
        demand_std_dev=4.0,
        avg_lead_time_days=avg_lt,
        lead_time_std_dev=1.0,
        service_level=0.95,
        min_safety_stock=5,
    )
    assert ss > 5
    rop = calculate_reorder_point(ltd, ss)
    assert rop == 100 + ss


def test_pack_size_rounding_and_moq_enforcement():
    """
    Verifies pack size rounding UP to integer multiples and MOQ floor enforcement.
    """
    # Raw qty = 15, pack size = 12, moq = 10 -> rounded to 24
    qty, added, moq_trig = enforce_pack_and_moq(raw_quantity=15, pack_size=12, moq=10)
    assert qty == 24
    assert added == 9
    assert moq_trig is False

    # Raw qty = 5, pack size = 6, moq = 20 -> rounded to 24 (since 20 rounds up to multiple of 6)
    qty, added, moq_trig = enforce_pack_and_moq(raw_quantity=5, pack_size=6, moq=20)
    assert qty == 24
    assert moq_trig is True


def test_discontinued_sku_blocked():
    """
    Verifies that inactive/discontinued SKUs trigger a DISCONTINUED_SKU_ORDER exception.
    """
    sku = {"id": uuid.uuid4(), "sku_code": "SKU-DISC", "is_active": False}
    store = {"id": uuid.uuid4(), "store_code": "STR-001"}
    supp_sku = {"supplier_id": uuid.uuid4()}
    inv = {"closing_stock": 0}
    policy = {"target_service_level": 0.95}

    rec, exceptions = ReplenishmentEngine.evaluate_sku_store_replenishment(
        sku=sku, store=store, supplier_sku=supp_sku, current_inventory=inv,
        reorder_policy=policy, avg_daily_demand=10.0, demand_std_dev=2.0,
        lead_time_days=5.0, lead_time_std_dev=1.0, store_current_total_units=100,
        evaluation_date=date.today(),
    )
    assert rec is None
    assert len(exceptions) == 1
    assert exceptions[0]["exception_type"] == "DISCONTINUED_SKU_ORDER"


def test_warehouse_capacity_conflict_exception():
    """
    Verifies that when supplier MOQ exceeds store remaining capacity, a critical exception is raised.
    """
    sku = {"id": uuid.uuid4(), "sku_code": "SKU-001", "is_active": True, "pack_size": 10, "unit_cost": Decimal("5.00")}
    # Store capacity = 1000, current units = 950 -> remaining capacity = 50
    store = {"id": uuid.uuid4(), "store_code": "STR-TIGHT", "warehouse_capacity_units": 1000}
    # Supplier MOQ is 200, exceeding available space of 50
    supp_sku = {"supplier_id": uuid.uuid4(), "pack_size": 10, "minimum_order_quantity": 200, "unit_cost": Decimal("5.00")}
    inv = {"closing_stock": 5, "in_transit_stock": 0, "reserved_stock": 0}
    policy = {"target_service_level": 0.95, "review_period_days": 7}

    rec, exceptions = ReplenishmentEngine.evaluate_sku_store_replenishment(
        sku=sku, store=store, supplier_sku=supp_sku, current_inventory=inv,
        reorder_policy=policy, avg_daily_demand=15.0, demand_std_dev=3.0,
        lead_time_days=5.0, lead_time_std_dev=1.0, store_current_total_units=950,
        evaluation_date=date.today(),
    )
    assert rec is not None
    assert rec["status"] == "FLAGGED_EXCEPTION"
    assert any(e["exception_type"] == "MOQ_CAPACITY_CONFLICT" for e in exceptions)


def test_fractional_target_order_quantity_rounds_up():
    sku_id = uuid.uuid4()
    store_id = uuid.uuid4()
    supplier_id = uuid.uuid4()
    sku = {
        "id": sku_id,
        "sku_code": "SKU-FRACTIONAL",
        "is_active": True,
        "pack_size": 1,
        "unit_cost": Decimal("1.00"),
    }
    store = {
        "id": store_id,
        "store_code": "STR-001",
        "warehouse_capacity_units": 1000,
    }
    supplier_sku = {
        "supplier_id": supplier_id,
        "pack_size": 1,
        "minimum_order_quantity": 1,
        "unit_cost": Decimal("1.00"),
    }

    recommendation, _ = ReplenishmentEngine.evaluate_sku_store_replenishment(
        sku=sku,
        store=store,
        supplier_sku=supplier_sku,
        current_inventory={"closing_stock": 0, "in_transit_stock": 0, "reserved_stock": 0},
        reorder_policy={
            "target_service_level": 0.95,
            "review_period_days": 7,
            "min_safety_stock_units": 0,
        },
        avg_daily_demand=1.5,
        demand_std_dev=0,
        lead_time_days=1,
        lead_time_std_dev=0,
        store_current_total_units=0,
        evaluation_date=date.today(),
    )

    assert recommendation is not None
    assert recommendation["raw_order_quantity"] == 13
    assert recommendation["recommended_units"] == 13

