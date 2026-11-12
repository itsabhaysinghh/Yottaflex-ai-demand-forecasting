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

    # Seed 30 days of sales & inventory history for this SKU & Store
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

    # 2. Run Replenishment
    rec_res = client.post("/api/v1/recommendations/run", json={
        "store_id": str(store.id),
        "sku_id": str(sku.id),
    })
    assert rec_res.status_code == 200
    assert rec_res.json()["success"] is True
