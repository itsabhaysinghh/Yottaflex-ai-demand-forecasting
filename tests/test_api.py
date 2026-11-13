import pytest
import uuid
from decimal import Decimal
from datetime import date


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
        recommendation_date=date.today(),
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
        in_transit_stock=0, reserved_stock=0, stockout_flag=False,
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


def test_missing_recommendation_is_unknown_even_with_safety_stock_policy(
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
        "sku_id": str(sku.id), "store_id": str(store.id), "enforce_capacity": True,
    })


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
    db_session.refresh(recommendation)
    db_session.refresh(exception)
    assert recommendation.status == "FLAGGED_EXCEPTION"
    assert exception.exception_type == "CAPACITY_OVERFLOW"


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
