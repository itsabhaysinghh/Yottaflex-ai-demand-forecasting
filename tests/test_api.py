import pytest
import uuid
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone


def test_cors_headers_are_added_to_unhandled_server_errors():
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    from app.main import app, fastapi_app

    def fail_database_dependency():
        raise RuntimeError("test database failure")

    fastapi_app.dependency_overrides[get_db] = fail_database_dependency
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get(
                "/api/v1/overview",
                headers={"Origin": "http://localhost:5173"},
            )
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data


def test_overview_dashboard(client, sample_master_data):
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["total_skus"] >= 1
    assert data["total_stores"] >= 1
    assert data["total_suppliers"] >= 1
    assert "categories" in data
    assert "store_capacities" in data
    assert data["active_stores_count"] == 1
    assert data["low_stock_products_count"] == 0


def test_dashboard_trends_use_persisted_sales_and_inventory(client, sample_master_data, db_session):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    day = date(2026, 11, 12)
    db_session.add_all([
        m.SalesHistory(
            sku_id=sku.id,
            store_id=store.id,
            sale_date=day,
            units_sold=18,
            revenue=Decimal("72.00"),
            is_promotion=False,
            promotion_discount_pct=Decimal("0.00"),
            day_of_week=day.weekday(),
        ),
        m.InventorySnapshot(
            sku_id=sku.id,
            store_id=store.id,
            snapshot_date=day,
            opening_stock=20,
            closing_stock=0,
            in_transit_stock=0,
            reserved_stock=0,
            stockout_flag=True,
            lost_sales_estimate=18,
        ),
    ])
    db_session.commit()

    response = client.get("/api/v1/overview/trends?days=7")
    assert response.status_code == 200
    data = response.json()
    assert {"date": day.isoformat(), "value": 18} in data["demand_trend"]
    assert {"date": day.isoformat(), "value": 1} in data["stockout_trend"]
    assert any(item["category"] == sku.category for item in data["inventory_distribution"])


def test_forecast_evaluations_filter_by_sku_store_and_model(client, sample_master_data, db_session):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    db_session.add_all([
        m.ForecastEvaluation(
            sku_id=sku.id,
            store_id=store.id,
            model_name="moving_average",
            evaluation_date=date(2026, 11, 10),
            horizon_days=7,
            mae=Decimal("1.0"),
            rmse=Decimal("1.5"),
            wape=Decimal("0.1"),
            bias=Decimal("0.2"),
            sample_size=7,
        ),
        m.ForecastEvaluation(
            sku_id=sku.id,
            store_id=store.id,
            model_name="seasonal_naive",
            evaluation_date=date(2026, 11, 11),
            horizon_days=7,
            mae=Decimal("1.2"),
            rmse=Decimal("1.7"),
            wape=Decimal("0.12"),
            bias=Decimal("-0.1"),
            sample_size=7,
        ),
    ])
    db_session.commit()

    response = client.get(
        "/api/v1/forecasts/evaluations",
        params={
            "sku_id": str(sku.id),
            "store_id": str(store.id),
            "model_name": "moving_average",
            "page_size": 500,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["sku_id"] == str(sku.id)
    assert data["items"][0]["store_id"] == str(store.id)
    assert data["items"][0]["model_name"] == "moving_average"


def test_inventory_current_view_exposes_policy_context_and_clamps_available(client, sample_master_data, db_session):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    db_session.add(m.InventorySnapshot(
        sku_id=sku.id,
        store_id=store.id,
        snapshot_date=date(2026, 11, 12),
        opening_stock=10,
        closing_stock=5,
        in_transit_stock=3,
        reserved_stock=8,
        stockout_flag=False,
        lost_sales_estimate=0,
    ))
    db_session.commit()

    response = client.get(
        "/api/v1/inventory",
        params={"current_only": True, "sku_id": str(sku.id), "search": sku.sku_code},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sku_name"] == sku.name
    assert item["category"] == sku.category
    assert item["available_units"] == 0
    assert item["safety_stock_units"] == sample_master_data["policy"].min_safety_stock_units
    assert item["inventory_status"] == "STOCKOUT"


def test_skus_endpoints(client, sample_master_data):
    # List SKUs
    res = client.get("/api/v1/skus")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["sku_code"] == "SKU-TEST-001"

    # Get single SKU
    sku_id = str(sample_master_data["sku"].id)
    res_single = client.get(f"/api/v1/skus/{sku_id}")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == sku_id


def test_stores_endpoints(client, sample_master_data):
    res = client.get("/api/v1/stores")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["store_code"] == "STR-TEST-001"


def test_suppliers_endpoints(client, sample_master_data):
    res = client.get("/api/v1/suppliers")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1

    supplier_id = str(sample_master_data["supplier"].id)
    assortment = client.get(f"/api/v1/suppliers/{supplier_id}/skus")
    assert assortment.status_code == 200
    assert assortment.json()["items"][0]["sku_code"] == "SKU-TEST-001"


def test_recommendations_approval_lifecycle(client, sample_master_data, db_session):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    supplier = sample_master_data["supplier"]

    rec = m.PurchaseRecommendation(
        id=uuid.uuid4(),
        sku_id=sku.id,
        store_id=store.id,
        supplier_id=supplier.id,
        recommendation_date=date.today(),
        current_on_hand=5,
        current_on_order=0,
        net_inventory_position=5,
        lead_time_demand=Decimal("50.00"),
        safety_stock=15,
        reorder_point=65,
        raw_order_quantity=60,
        recommended_units=72,
        total_cost=Decimal("180.00"),
        status="PENDING",
        explanation={"trigger_reason": "IP <= ROP"},
    )
    db_session.add(rec)
    db_session.commit()

    # List recommendations
    list_res = client.get("/api/v1/recommendations?status=PENDING")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1
    item = next(row for row in list_res.json()["items"] if row["id"] == str(rec.id))
    assert item["minimum_order_quantity"] == sample_master_data["supplier_sku"].minimum_order_quantity
    assert item["pack_size"] == sample_master_data["supplier_sku"].pack_size

    # Approve recommendation
    review_payload = {
        "status": "APPROVED",
        "reviewed_by": "Senior Inventory Planner",
        "review_notes": "Order approved ahead of weekend spike.",
    }
    approve_res = client.patch(f"/api/v1/recommendations/{rec.id}", json=review_payload)
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"
    assert approve_res.json()["reviewed_by"] == "Senior Inventory Planner"

    rejected = m.PurchaseRecommendation(
        id=uuid.uuid4(),
        sku_id=sku.id,
        store_id=store.id,
        supplier_id=supplier.id,
        recommendation_date=date.today() + timedelta(days=1),
        current_on_hand=8,
        current_on_order=0,
        net_inventory_position=8,
        lead_time_demand=Decimal("35.00"),
        safety_stock=12,
        reorder_point=47,
        raw_order_quantity=39,
        recommended_units=48,
        total_cost=Decimal("120.00"),
        status="PENDING",
        explanation={"trigger_reason": "IP <= ROP"},
    )
    db_session.add(rejected)
    db_session.commit()

    reject_res = client.patch(
        f"/api/v1/recommendations/{rejected.id}",
        json={
            "status": "REJECTED",
            "reviewed_by": "Senior Inventory Planner",
            "review_notes": "Existing stock transfer will cover demand.",
        },
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"
    assert reject_res.json()["review_notes"] == "Existing stock transfer will cover demand."


def test_exceptions_resolution(client, sample_master_data, db_session):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]

    exc = m.InventoryException(
        id=uuid.uuid4(),
        sku_id=sku.id,
        store_id=store.id,
        exception_type="PACK_SIZE_VIOLATION",
        severity="MEDIUM",
        description="Pack size multiple violated",
        payload={"recommended": 47, "pack_size": 12},
        is_resolved=False,
    )
    db_session.add(exc)
    db_session.commit()

    # List unresolved
    res = client.get("/api/v1/exceptions?is_resolved=false")
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    # Resolve exception
    resolve_payload = {
        "resolved_by": "Ops Manager",
        "resolution_notes": "Supplier agreed to ship split cases.",
    }
    resolve_res = client.patch(f"/api/v1/exceptions/{exc.id}/resolve", json=resolve_payload)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["is_resolved"] is True


def test_forecast_and_replenishment_pipeline_api(client, sample_master_data, db_session):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]

    # Seed 30 days of sales & inventory for SKU/store IDs
    from datetime import timedelta
    start_dt = date(2026, 1, 1)
    for i in range(30):
        dt = start_dt + timedelta(days=i)
        sale = m.SalesHistory(
            sku_id=sku.id,
            store_id=store.id,
            sale_date=dt,
            units_sold=15 + (i % 7),
            revenue=Decimal("60.00"),
            is_promotion=False,
            promotion_discount_pct=Decimal("0.00"),
            day_of_week=dt.weekday(),
        )
        inv = m.InventorySnapshot(
            sku_id=sku.id,
            store_id=store.id,
            snapshot_date=dt,
            opening_stock=40,
            closing_stock=25,
            in_transit_stock=0,
            reserved_stock=0,
            stockout_flag=False,
            lost_sales_estimate=0,
        )
        db_session.add(sale)
        db_session.add(inv)
    db_session.commit()

    # 1. Run Forecast
    fc_res = client.post("/api/v1/forecasts/run", json={
        "sku_id": str(sku.id),
        "store_id": str(store.id),
        "model_name": "seasonal_naive",
        "horizon_days": 7,
    })
    assert fc_res.status_code == 200
    assert fc_res.json()["success"] is True

    # Check forecast list
    fc_list = client.get(f"/api/v1/forecasts?sku_id={sku.id}")
    assert fc_list.status_code == 200
    assert fc_list.json()["total"] >= 7

    repeated_fc_res = client.post("/api/v1/forecasts/run", json={
        "sku_id": str(sku.id),
        "store_id": str(store.id),
        "model_name": "seasonal_naive",
        "horizon_days": 7,
    })
    assert repeated_fc_res.status_code == 200
    refreshed_fc_list = client.get(f"/api/v1/forecasts?sku_id={sku.id}")
    assert refreshed_fc_list.status_code == 200
    assert refreshed_fc_list.json()["total"] == fc_list.json()["total"]

    # 2. Run Replenishment
    rec_res = client.post("/api/v1/recommendations/run", json={
        "store_id": str(store.id),
        "sku_id": str(sku.id),
    })
    assert rec_res.status_code == 200
    assert rec_res.json()["success"] is True



def _seed_classification_data(
    db_session, sample_master_data, *, closing_stock=9, reorder_point=10,
    include_policy=True, include_recommendation=True, is_active=True,
    stockout_flag=False, reserved_stock=0, in_transit_stock=0,
):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    sku.is_active = is_active
    if not include_policy:
        db_session.delete(sample_master_data["policy"])
    day = date.today()
    db_session.add(m.InventorySnapshot(
        sku_id=sku.id, store_id=store.id, snapshot_date=day,
        opening_stock=closing_stock + 1, closing_stock=closing_stock,
        in_transit_stock=in_transit_stock, reserved_stock=reserved_stock,
        stockout_flag=stockout_flag,
        lost_sales_estimate=0,
    ))
    if include_recommendation:
        db_session.add(m.PurchaseRecommendation(
            sku_id=sku.id, store_id=store.id,
            supplier_id=sample_master_data["supplier"].id,
            recommendation_date=day, current_on_hand=closing_stock,
            current_on_order=0, net_inventory_position=closing_stock,
            lead_time_demand=Decimal("5.00"), safety_stock=5,
            reorder_point=reorder_point, raw_order_quantity=1,
            recommended_units=12, total_cost=Decimal("30.00"),
            status="PENDING", explanation={},
        ))
    db_session.commit()
    return sku, store


def _seed_classification_history(
    db_session, sample_master_data, *, store=None, lead_time_values=(7, 7, 7, 7),
):
    import app.models as m

    sku = sample_master_data["sku"]
    store = store or sample_master_data["store"]
    today = date.today()
    db_session.add_all([
        m.SalesHistory(
            sku_id=sku.id,
            store_id=store.id,
            sale_date=today - timedelta(days=day_offset),
            units_sold=1,
            revenue=Decimal("4.00"),
            is_promotion=False,
            promotion_discount_pct=Decimal("0.00"),
            day_of_week=(today - timedelta(days=day_offset)).weekday(),
        )
        for day_offset in range(1, 31)
    ])
    supplier_sku = sample_master_data["supplier_sku"]
    db_session.add_all([
        m.LeadTimeObservation(
            supplier_sku_id=supplier_sku.id,
            order_date=(
                today
                - timedelta(days=day_offset + lead_time_days + 1)
            ),
            promised_delivery_date=today - timedelta(days=day_offset + 1),
            actual_delivery_date=today - timedelta(days=day_offset + 1),
            actual_lead_time_days=lead_time_days,
            units_ordered=24,
            units_received=24,
            is_anomaly=False,
        )
        for day_offset, lead_time_days in enumerate(lead_time_values)
    ])
    db_session.commit()


def _inventory_item(client, sku, store):
    response = client.get(
        "/api/v1/inventory",
        params={"current_only": True, "sku_id": str(sku.id), "store_id": str(store.id)},
    )
    assert response.status_code == 200
    return response.json()["items"][0]


@pytest.mark.parametrize(
    ("closing_stock", "expected_status", "expected_low_count"),
    [(9, "LOW", 1), (10, "LOW", 1), (11, "HEALTHY", 0)],
)
def test_inventory_and_overview_use_actual_reorder_point(
    client, sample_master_data, db_session,
    closing_stock, expected_status, expected_low_count,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=closing_stock,
        reorder_point=10,
    )

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["inventory_status"] == expected_status
    assert overview["low_stock_products_count"] == expected_low_count
    assert overview["inventory_health_pct"] == (100.0 if expected_low_count == 0 else 0.0)


def test_inventory_uses_recommendation_rop_without_reorder_policy(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=9,
        reorder_point=10, include_policy=False,
    )

    item = _inventory_item(client, sku, store)

    assert item["reorder_point"] == 10
    assert item["safety_stock_units"] == 5
    assert item["inventory_status"] == "LOW"


def test_superseded_recommendations_do_not_affect_active_inventory_metrics(
    client, sample_master_data, db_session,
):
    import app.models as m

    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=9, reorder_point=10,
    )
    active = db_session.query(m.PurchaseRecommendation).one()
    db_session.add(m.PurchaseRecommendation(
        sku_id=sku.id,
        store_id=store.id,
        supplier_id=sample_master_data["supplier"].id,
        recommendation_date=date.today(),
        current_on_hand=9,
        current_on_order=0,
        net_inventory_position=9,
        lead_time_demand=Decimal("1.00"),
        safety_stock=1,
        reorder_point=1,
        raw_order_quantity=1,
        recommended_units=12,
        total_cost=Decimal("30.00"),
        status="PENDING",
        explanation={},
        created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        superseded_at=datetime.now(timezone.utc),
        superseded_by_id=active.id,
        supersession_reason="Historical recommendation for test.",
    ))
    db_session.commit()

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["reorder_point"] == 10
    assert item["inventory_status"] == "LOW"
    assert overview["low_stock_products_count"] == 1
    assert overview["pending_recommendations_count"] == 1


def test_missing_demand_history_keeps_missing_rop_unknown(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=4,
        include_recommendation=False,
    )

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["reorder_point"] is None
    assert item["safety_stock_units"] == sample_master_data["policy"].min_safety_stock_units
    assert item["inventory_status"] == "UNKNOWN"
    assert overview["low_stock_products_count"] == 0
    assert overview["inventory_health_pct"] is None


def test_healthy_inventory_without_recommendation_uses_calculated_rop(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=13,
        include_recommendation=False,
    )
    _seed_classification_history(db_session, sample_master_data)

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["reorder_point"] == 12
    assert item["safety_stock_units"] == 5
    assert item["inventory_status"] == "HEALTHY"
    assert overview["low_stock_products_count"] == 0
    assert overview["inventory_health_pct"] == 100.0


def test_reorder_point_uses_deterministically_ordered_lead_time_history(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=14,
        include_recommendation=False,
    )
    _seed_classification_history(
        db_session,
        sample_master_data,
        lead_time_values=(20, *([1] * 10)),
    )

    item = _inventory_item(client, sku, store)

    assert item["reorder_point"] == 13
    assert item["inventory_status"] == "HEALTHY"


def test_low_inventory_without_recommendation_uses_calculated_rop(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=12,
        include_recommendation=False,
    )
    _seed_classification_history(db_session, sample_master_data)

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["reorder_point"] == 12
    assert item["inventory_status"] == "LOW"
    assert overview["low_stock_products_count"] == 1
    assert overview["inventory_health_pct"] == 0.0


def test_physical_stockout_without_recommendation_remains_stockout(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=0,
        include_recommendation=False, stockout_flag=True,
    )

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["inventory_status"] == "STOCKOUT"
    assert overview["low_stock_products_count"] == 1
    assert overview["inventory_health_pct"] == 0.0


def test_reserved_stockout_takes_precedence_over_in_transit_stock(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=5,
        include_recommendation=False, reserved_stock=5, in_transit_stock=100,
    )

    item = _inventory_item(client, sku, store)
    stockout_items = client.get(
        "/api/v1/inventory",
        params={
            "current_only": True,
            "stockout_only": True,
            "sku_id": str(sku.id),
            "store_id": str(store.id),
        },
    )

    assert item["available_units"] == 0
    assert item["inventory_status"] == "STOCKOUT"
    assert stockout_items.json()["total"] == 1


def test_missing_reorder_policy_keeps_missing_rop_unknown(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=13,
        include_recommendation=False,
    )
    _seed_classification_history(db_session, sample_master_data)
    db_session.delete(sample_master_data["policy"])
    db_session.commit()

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["reorder_point"] is None
    assert item["inventory_status"] == "UNKNOWN"
    assert overview["inventory_health_pct"] is None


def test_missing_primary_supplier_keeps_missing_rop_unknown(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=13,
        include_recommendation=False,
    )
    _seed_classification_history(db_session, sample_master_data)
    db_session.delete(sample_master_data["supplier_sku"])
    db_session.commit()

    item = _inventory_item(client, sku, store)

    assert item["reorder_point"] is None
    assert item["inventory_status"] == "UNKNOWN"


def test_unknown_positions_are_not_counted_as_healthy(
    client, sample_master_data, db_session,
):
    import app.models as m

    healthy_sku, healthy_store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=13,
        include_recommendation=False,
    )
    _seed_classification_history(db_session, sample_master_data)
    unknown_store = m.Store(
        id=uuid.uuid4(),
        store_code="STR-TEST-UNKNOWN",
        name="Unknown Inventory Store",
        store_type="standard",
        warehouse_capacity_units=5000,
        is_active=True,
    )
    db_session.add(unknown_store)
    db_session.flush()
    db_session.add(m.InventorySnapshot(
        sku_id=healthy_sku.id,
        store_id=unknown_store.id,
        snapshot_date=date.today(),
        opening_stock=14,
        closing_stock=13,
        in_transit_stock=0,
        reserved_stock=0,
        stockout_flag=False,
        lost_sales_estimate=0,
    ))
    db_session.commit()

    unknown_item = _inventory_item(client, healthy_sku, unknown_store)
    overview = client.get("/api/v1/overview").json()

    assert unknown_item["inventory_status"] == "UNKNOWN"
    assert overview["inventory_health_pct"] == 100.0
    assert overview["low_stock_products_count"] == 0


def test_discontinued_sku_is_unknown_and_excluded_from_overview_health(
    client, sample_master_data, db_session,
):
    sku, store = _seed_classification_data(
        db_session, sample_master_data, closing_stock=0,
        reorder_point=10, is_active=False,
    )

    item = _inventory_item(client, sku, store)
    overview = client.get("/api/v1/overview").json()

    assert item["inventory_status"] == "UNKNOWN"
    assert overview["low_stock_products_count"] == 0
    assert overview["inventory_health_pct"] is None


def _seed_replenishment_run_inputs(db_session, sample_master_data):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    day = date.today()
    db_session.add_all([
        m.InventorySnapshot(
            sku_id=sku.id, store_id=store.id, snapshot_date=day,
            opening_stock=10, closing_stock=0, in_transit_stock=0,
            reserved_stock=0, stockout_flag=True, lost_sales_estimate=10,
        ),
        m.SalesHistory(
            sku_id=sku.id, store_id=store.id, sale_date=day,
            units_sold=10, revenue=Decimal("40.00"), is_promotion=False,
            promotion_discount_pct=Decimal("0.00"), day_of_week=day.weekday(),
        ),
    ])
    db_session.commit()
    return sku, store


def _run_replenishment(client, sku, store):
    return client.post("/api/v1/recommendations/run", json={
        "sku_id": str(sku.id), "store_id": str(store.id),
    })


def test_replenishment_run_enforces_capacity_when_field_is_omitted(
    client, sample_master_data, db_session,
):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    store.warehouse_capacity_units = 150
    db_session.commit()
    _seed_replenishment_run_inputs(db_session, sample_master_data)
    snapshot = db_session.query(m.InventorySnapshot).filter_by(
        sku_id=sku.id,
        store_id=store.id,
        snapshot_date=date.today(),
    ).one()
    snapshot.in_transit_stock = 50
    db_session.commit()

    response = client.post("/api/v1/recommendations/run", json={
        "sku_id": str(sku.id),
        "store_id": str(store.id),
    })

    assert response.status_code == 200
    recommendation = db_session.query(m.PurchaseRecommendation).one()
    assert recommendation.status == "FLAGGED_EXCEPTION"
    assert recommendation.explanation["warehouse_capacity_check"]["enforced"] is True
    assert db_session.query(m.InventoryException).filter(
        m.InventoryException.exception_type.in_(
            ["CAPACITY_OVERFLOW", "MOQ_CAPACITY_CONFLICT"]
        )
    ).count() == 1


def test_replenishment_run_reserves_existing_pending_cycle_recommendations(
    client, sample_master_data, db_session,
):
    import app.models as m

    sku, store = _seed_replenishment_run_inputs(db_session, sample_master_data)
    store.warehouse_capacity_units = 200
    db_session.commit()
    first = _run_replenishment(client, sku, store)
    assert first.status_code == 200
    existing = db_session.query(m.PurchaseRecommendation).one()
    assert existing.status == "PENDING"

    second_sku = m.SKU(
        sku_code="SKU-TEST-CAPACITY-002",
        name="Capacity Test Item",
        category="Beverages",
        unit_cost=Decimal("2.50"),
        unit_price=Decimal("4.00"),
        pack_size=12,
        is_active=True,
    )
    db_session.add(second_sku)
    db_session.flush()
    db_session.add_all([
        m.SupplierSKU(
            supplier_id=sample_master_data["supplier"].id,
            sku_id=second_sku.id,
            contract_lead_time_days=7,
            minimum_order_quantity=24,
            pack_size=12,
            unit_cost=Decimal("2.50"),
            is_primary=True,
        ),
        m.ReorderPolicy(
            sku_id=second_sku.id,
            store_id=store.id,
            target_service_level=Decimal("0.950"),
            review_period_days=7,
            min_safety_stock_units=5,
        ),
        m.InventorySnapshot(
            sku_id=second_sku.id,
            store_id=store.id,
            snapshot_date=date.today(),
            opening_stock=10,
            closing_stock=0,
            in_transit_stock=0,
            reserved_stock=0,
            stockout_flag=True,
            lost_sales_estimate=10,
        ),
        m.SalesHistory(
            sku_id=second_sku.id,
            store_id=store.id,
            sale_date=date.today(),
            units_sold=10,
            revenue=Decimal("40.00"),
            is_promotion=False,
            promotion_discount_pct=Decimal("0.00"),
            day_of_week=date.today().weekday(),
        ),
    ])
    db_session.commit()

    response = _run_replenishment(client, second_sku, store)

    assert response.status_code == 200
    second_recommendation = db_session.query(m.PurchaseRecommendation).filter_by(
        sku_id=second_sku.id,
    ).one()
    assert second_recommendation.status == "FLAGGED_EXCEPTION"
    assert second_recommendation.explanation["warehouse_capacity_check"]["remaining_capacity"] == (
        store.warehouse_capacity_units - existing.recommended_units
    )


def test_replenishment_run_rejects_legacy_capacity_bypass(
    client, sample_master_data,
):
    sku = sample_master_data["sku"]
    store = sample_master_data["store"]

    response = client.post("/api/v1/recommendations/run", json={
        "sku_id": str(sku.id),
        "store_id": str(store.id),
        "enforce_capacity": False,
    })

    assert response.status_code == 422


def test_replenishment_runs_are_idempotent_for_same_inventory_cycle(
    client, sample_master_data, db_session,
):
    import app.models as m

    sku, store = _seed_replenishment_run_inputs(db_session, sample_master_data)

    first = _run_replenishment(client, sku, store)
    assert first.status_code == 200
    assert db_session.query(m.PurchaseRecommendation).count() == 1
    generated = db_session.query(m.PurchaseRecommendation).one()
    generated_id = generated.id

    second = _run_replenishment(client, sku, store)

    assert second.status_code == 200
    assert "skipped 1 existing replenishment cycles" in second.json()["message"]
    assert db_session.query(m.PurchaseRecommendation).count() == 1
    assert db_session.query(m.PurchaseRecommendation).one().id == generated_id


def _create_superseded_recommendation_pair(db_session, sample_master_data):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    supplier = sample_master_data["supplier"]
    active = m.PurchaseRecommendation(
        sku_id=sku.id,
        store_id=store.id,
        supplier_id=supplier.id,
        recommendation_date=date.today(),
        current_on_hand=0,
        current_on_order=0,
        net_inventory_position=0,
        lead_time_demand=Decimal("70.00"),
        safety_stock=5,
        reorder_point=75,
        raw_order_quantity=100,
        recommended_units=108,
        total_cost=Decimal("270.00"),
        status="PENDING",
        explanation={},
    )
    db_session.add(active)
    db_session.flush()

    superseded = m.PurchaseRecommendation(
        sku_id=sku.id,
        store_id=store.id,
        supplier_id=supplier.id,
        recommendation_date=date.today(),
        current_on_hand=0,
        current_on_order=0,
        net_inventory_position=0,
        lead_time_demand=Decimal("70.00"),
        safety_stock=5,
        reorder_point=75,
        raw_order_quantity=100,
        recommended_units=108,
        total_cost=Decimal("270.00"),
        status="PENDING",
        explanation={},
        superseded_at=datetime.now(timezone.utc),
        superseded_by_id=active.id,
        supersession_reason="Duplicate cycle retained for audit history.",
    )
    db_session.add(superseded)
    db_session.commit()
    return active, superseded


def test_recommendation_list_hides_superseded_by_default_and_includes_history(
    client, sample_master_data, db_session,
):
    active, superseded = _create_superseded_recommendation_pair(
        db_session, sample_master_data,
    )

    active_response = client.get("/api/v1/recommendations")
    assert active_response.status_code == 200
    active_items = active_response.json()["items"]
    assert [item["id"] for item in active_items] == [str(active.id)]
    assert active_items[0]["superseded_at"] is None

    history_response = client.get(
        "/api/v1/recommendations?include_superseded=true",
    )
    assert history_response.status_code == 200
    history_items = history_response.json()["items"]
    assert {item["id"] for item in history_items} == {
        str(active.id),
        str(superseded.id),
    }
    superseded_item = next(
        item for item in history_items if item["id"] == str(superseded.id)
    )
    assert superseded_item["superseded_by_id"] == str(active.id)
    assert superseded_item["supersession_reason"] == (
        "Duplicate cycle retained for audit history."
    )


def test_superseded_recommendation_cannot_be_reviewed(
    client, sample_master_data, db_session,
):
    active, superseded = _create_superseded_recommendation_pair(
        db_session, sample_master_data,
    )

    response = client.patch(
        f"/api/v1/recommendations/{superseded.id}",
        json={"status": "APPROVED", "reviewed_by": "Planner"},
    )

    assert response.status_code == 409
    db_session.refresh(superseded)
    assert superseded.status == "PENDING"
    assert superseded.reviewed_by is None
    assert active.status == "PENDING"


@pytest.mark.parametrize("existing_status", ["APPROVED", "REJECTED"])
def test_replenishment_run_preserves_reviewed_recommendation(
    client, sample_master_data, db_session, existing_status,
):
    import app.models as m

    sku, store = _seed_replenishment_run_inputs(db_session, sample_master_data)
    existing = m.PurchaseRecommendation(
        sku_id=sku.id, store_id=store.id,
        supplier_id=sample_master_data["supplier"].id,
        recommendation_date=date.today(), current_on_hand=0,
        current_on_order=0, net_inventory_position=0,
        lead_time_demand=Decimal("70.00"), safety_stock=5,
        reorder_point=75, raw_order_quantity=100, recommended_units=108,
        total_cost=Decimal("270.00"), status=existing_status,
        reviewed_by="Planner", review_notes="Previously reviewed", explanation={},
    )
    db_session.add(existing)
    db_session.commit()
    existing_id = existing.id

    response = _run_replenishment(client, sku, store)

    assert response.status_code == 200
    assert db_session.query(m.PurchaseRecommendation).count() == 1
    preserved = db_session.get(m.PurchaseRecommendation, existing_id)
    assert preserved.status == existing_status
    assert preserved.reviewed_by == "Planner"
    assert preserved.review_notes == "Previously reviewed"


def test_capacity_flagged_recommendation_cannot_be_approved(
    client, sample_master_data, db_session,
):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    recommendation = m.PurchaseRecommendation(
        sku_id=sku.id, store_id=store.id,
        supplier_id=sample_master_data["supplier"].id,
        recommendation_date=date.today(), current_on_hand=0,
        current_on_order=0, net_inventory_position=0,
        lead_time_demand=Decimal("70.00"), safety_stock=5,
        reorder_point=75, raw_order_quantity=100, recommended_units=108,
        total_cost=Decimal("270.00"), status="FLAGGED_EXCEPTION",
        explanation={"warehouse_capacity_check": {"capacity_breached": True}},
    )
    exception = m.InventoryException(
        sku_id=sku.id, store_id=store.id,
        supplier_id=sample_master_data["supplier"].id,
        exception_type="CAPACITY_OVERFLOW", severity="HIGH",
        description="Insufficient warehouse capacity.", payload={"remaining_capacity": 10},
    )
    db_session.add_all([recommendation, exception])
    db_session.commit()

    response = client.patch(
        f"/api/v1/recommendations/{recommendation.id}",
        json={"status": "APPROVED", "reviewed_by": "Planner"},
    )

    assert response.status_code == 409
    assert "cannot be approved" in response.json()["detail"]

    resolved = client.patch(
        f"/api/v1/exceptions/{exception.id}/resolve",
        json={"resolved_by": "Planner", "resolution_notes": "Capacity reviewed."},
    )
    assert resolved.status_code == 200

    response = client.patch(
        f"/api/v1/recommendations/{recommendation.id}",
        json={"status": "APPROVED", "reviewed_by": "Planner"},
    )

    assert response.status_code == 409
    assert "correct the quantity" in response.json()["detail"].lower()
    db_session.refresh(recommendation)
    db_session.refresh(exception)
    assert recommendation.status == "FLAGGED_EXCEPTION"
    assert exception.is_resolved is True
    assert exception.exception_type == "CAPACITY_OVERFLOW"


def _create_capacity_flagged_recommendation(db_session, sample_master_data):
    import app.models as m

    sku = sample_master_data["sku"]
    store = sample_master_data["store"]
    supplier = sample_master_data["supplier"]
    day = date.today()
    store.warehouse_capacity_units = 100
    db_session.add(m.InventorySnapshot(
        sku_id=sku.id,
        store_id=store.id,
        snapshot_date=day,
        opening_stock=0,
        closing_stock=0,
        in_transit_stock=0,
        reserved_stock=0,
        stockout_flag=False,
        lost_sales_estimate=0,
    ))
    recommendation = m.PurchaseRecommendation(
        sku_id=sku.id,
        store_id=store.id,
        supplier_id=supplier.id,
        recommendation_date=day,
        current_on_hand=0,
        current_on_order=0,
        net_inventory_position=0,
        lead_time_demand=Decimal("70.00"),
        safety_stock=5,
        reorder_point=75,
        raw_order_quantity=100,
        recommended_units=120,
        total_cost=Decimal("300.00"),
        status="FLAGGED_EXCEPTION",
        explanation={
            "order_adjustments": {"final_recommended_units": 120},
            "warehouse_capacity_check": {
                "total_store_capacity": 100,
                "current_store_utilization": 0,
                "remaining_capacity": 100,
                "capacity_breached": True,
                "enforced": True,
            },
        },
    )
    db_session.add(recommendation)
    db_session.commit()
    return recommendation


def test_capacity_correction_supersedes_flagged_proposal_and_creates_valid_replacement(
    client, sample_master_data, db_session,
):
    recommendation = _create_capacity_flagged_recommendation(
        db_session, sample_master_data,
    )

    response = client.post(
        f"/api/v1/recommendations/{recommendation.id}/correct",
        json={
            "recommended_units": 96,
            "corrected_by": "Planner",
            "correction_notes": "Reduced to fit available capacity.",
        },
    )

    assert response.status_code == 201
    replacement = response.json()
    assert replacement["status"] == "PENDING"
    assert replacement["recommended_units"] == 96
    assert replacement["total_cost"] == "240.00"
    assert replacement["explanation"]["warehouse_capacity_check"]["capacity_breached"] is False
    assert replacement["explanation"]["capacity_correction"]["corrected_by"] == "Planner"

    db_session.refresh(recommendation)
    assert recommendation.status == "FLAGGED_EXCEPTION"
    assert recommendation.superseded_at is not None
    assert recommendation.superseded_by_id == uuid.UUID(replacement["id"])
    assert "Reduced to fit available capacity." in recommendation.supersession_reason

    active_items = client.get("/api/v1/recommendations").json()["items"]
    assert [item["id"] for item in active_items] == [replacement["id"]]
    approval = client.patch(
        f"/api/v1/recommendations/{replacement['id']}",
        json={"status": "APPROVED", "reviewed_by": "Planner"},
    )
    assert approval.status_code == 200


def test_capacity_correction_rejects_pack_invalid_and_over_capacity_quantities(
    client, sample_master_data, db_session,
):
    recommendation = _create_capacity_flagged_recommendation(
        db_session,
        sample_master_data,
    )

    pack_invalid = client.post(
        f"/api/v1/recommendations/{recommendation.id}/correct",
        json={
            "recommended_units": 90,
            "corrected_by": "Planner",
            "correction_notes": "Attempt with a non-pack quantity.",
        },
    )
    assert pack_invalid.status_code == 422

    over_capacity = client.post(
        f"/api/v1/recommendations/{recommendation.id}/correct",
        json={
            "recommended_units": 108,
            "corrected_by": "Planner",
            "correction_notes": "Attempt above available capacity.",
        },
    )
    assert over_capacity.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.superseded_at is None


def test_exception_resolution_notes_persist_after_commit_and_reload(
    client, sample_master_data, db_session,
):
    import app.models as m

    exception = m.InventoryException(
        sku_id=sample_master_data["sku"].id,
        store_id=sample_master_data["store"].id,
        exception_type="CAPACITY_OVERFLOW", severity="HIGH",
        description="Warehouse capacity exceeded.", payload={"context": "test"},
    )
    db_session.add(exception)
    db_session.commit()

    response = client.patch(
        f"/api/v1/exceptions/{exception.id}/resolve",
        json={"resolved_by": "Planner", "resolution_notes": "Capacity checked."},
    )
    assert response.status_code == 200

    db_session.expire_all()
    persisted = db_session.get(m.InventoryException, exception.id)
    assert persisted.is_resolved is True
    assert persisted.payload["resolution_notes"] == "Capacity checked."
