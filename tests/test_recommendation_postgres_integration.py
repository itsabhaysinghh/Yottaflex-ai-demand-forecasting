import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.recommendations import run_replenishment_pipeline
from app.core.database import Base
from app.engines.replenishment import ReplenishmentEngine
from app.schemas.recommendation import RecommendationRunRequest
import app.models as m


@pytest.fixture
def postgres_schema():
    database_url = os.getenv("YOTTAFLEX_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Set YOTTAFLEX_TEST_POSTGRES_URL to a dedicated PostgreSQL test database.")

    url = make_url(database_url)
    if (
        not url.database
        or "test" not in url.database.lower()
        or url.database.lower() == "yottaflex_demand"
    ):
        pytest.fail(
            "PostgreSQL integration tests require a dedicated database whose name "
            "contains 'test'; the application database is not allowed."
        )
    if (url.host or "").lower() not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("PostgreSQL integration tests are restricted to a local test database.")

    schema_name = f"recommendation_test_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, pool_size=4, max_overflow=2, pool_pre_ping=True)
    schema_engine = admin_engine.execution_options(
        schema_translate_map={None: schema_name},
    )
    schema_created = False
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        schema_created = True
        Base.metadata.create_all(schema_engine)
        yield sessionmaker(bind=schema_engine, expire_on_commit=False)
    finally:
        if schema_created:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        admin_engine.dispose()


def _seed_cycle_inputs(session):
    day = date.today()
    store = m.Store(
        store_code=f"STR-{uuid.uuid4().hex[:12]}",
        name="Concurrency Test Store",
        store_type="standard",
        warehouse_capacity_units=5000,
        is_active=True,
    )
    sku = m.SKU(
        sku_code=f"SKU-{uuid.uuid4().hex[:12]}",
        name="Concurrency Test SKU",
        category="Test",
        unit_cost=Decimal("2.50"),
        unit_price=Decimal("4.00"),
        pack_size=12,
        is_active=True,
    )
    supplier = m.Supplier(
        supplier_code=f"SUP-{uuid.uuid4().hex[:12]}",
        name="Concurrency Test Supplier",
        default_lead_time_days=7,
        reliability_score=Decimal("0.95"),
        is_active=True,
    )
    session.add_all([store, sku, supplier])
    session.flush()

    supplier_sku = m.SupplierSKU(
        supplier_id=supplier.id,
        sku_id=sku.id,
        contract_lead_time_days=7,
        minimum_order_quantity=24,
        pack_size=12,
        unit_cost=Decimal("2.50"),
        is_primary=True,
    )
    policy = m.ReorderPolicy(
        sku_id=sku.id,
        store_id=store.id,
        target_service_level=Decimal("0.950"),
        review_period_days=7,
        min_safety_stock_units=5,
    )
    inventory = m.InventorySnapshot(
        sku_id=sku.id,
        store_id=store.id,
        snapshot_date=day,
        opening_stock=10,
        closing_stock=0,
        in_transit_stock=0,
        reserved_stock=0,
        stockout_flag=True,
        lost_sales_estimate=10,
    )
    sales = m.SalesHistory(
        sku_id=sku.id,
        store_id=store.id,
        sale_date=day,
        units_sold=10,
        revenue=Decimal("40.00"),
        is_promotion=False,
        promotion_discount_pct=Decimal("0.00"),
        day_of_week=day.weekday(),
    )
    session.add_all([supplier_sku, policy, inventory, sales])
    session.commit()
    return sku, store, supplier, policy


def _run_cycle(session_factory, barrier, sku, store):
    with session_factory() as session:
        barrier.wait(timeout=15)
        return run_replenishment_pipeline(
            RecommendationRunRequest(sku_id=sku.id, store_id=store.id),
            session,
        )


def _active_cycle_count(session_factory, sku, store):
    with session_factory() as session:
        return session.scalar(
            select(func.count())
            .select_from(m.PurchaseRecommendation)
            .where(
                m.PurchaseRecommendation.sku_id == sku.id,
                m.PurchaseRecommendation.store_id == store.id,
                m.PurchaseRecommendation.recommendation_date == date.today(),
                m.PurchaseRecommendation.superseded_at.is_(None),
            )
        )


def test_concurrent_replenishment_runs_create_one_active_cycle(postgres_schema):
    session_factory = postgres_schema
    with session_factory() as session:
        sku, store, _, _ = _seed_cycle_inputs(session)

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_run_cycle, session_factory, barrier, sku, store)
            for _ in range(2)
        ]
        responses = [future.result(timeout=30) for future in futures]

    assert all(response.success for response in responses)
    assert _active_cycle_count(session_factory, sku, store) == 1
    assert sum("generated 1 recommendations" in response.message for response in responses) == 1
    assert sum("skipped 1 existing replenishment cycles" in response.message for response in responses) == 1


def test_concurrent_replenishment_runs_reserve_capacity_across_skus(postgres_schema):
    session_factory = postgres_schema
    with session_factory() as session:
        first_sku, store, supplier, _ = _seed_cycle_inputs(session)
        store.warehouse_capacity_units = 300
        second_sku = m.SKU(
            sku_code=f"SKU-{uuid.uuid4().hex[:12]}",
            name="Second Capacity Test SKU",
            category="Test",
            unit_cost=Decimal("2.50"),
            unit_price=Decimal("4.00"),
            pack_size=12,
            is_active=True,
        )
        session.add(second_sku)
        session.flush()
        session.add_all([
            m.SupplierSKU(
                supplier_id=supplier.id,
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
        session.commit()

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_run_cycle, session_factory, barrier, sku, store)
            for sku in (first_sku, second_sku)
        ]
        responses = [future.result(timeout=30) for future in futures]

    assert all(response.success for response in responses)
    with session_factory() as session:
        recommendations = session.scalars(
            select(m.PurchaseRecommendation).where(
                m.PurchaseRecommendation.store_id == store.id,
                m.PurchaseRecommendation.recommendation_date == date.today(),
                m.PurchaseRecommendation.superseded_at.is_(None),
            )
        ).all()

    assert len(recommendations) == 2
    assert sorted(rec.status for rec in recommendations) == [
        "FLAGGED_EXCEPTION",
        "PENDING",
    ]
    assert sum(
        rec.recommended_units
        for rec in recommendations
        if rec.status in {"PENDING", "APPROVED"}
    ) <= store.warehouse_capacity_units


def test_unique_conflict_is_skipped_without_aborting_run(postgres_schema, monkeypatch):
    session_factory = postgres_schema
    with session_factory() as session:
        sku, store, supplier, policy = _seed_cycle_inputs(session)

    evaluated = Event()
    continue_run = Event()
    evaluate = ReplenishmentEngine.evaluate_sku_store_replenishment

    def pause_after_evaluation(**kwargs):
        result = evaluate(**kwargs)
        evaluated.set()
        if not continue_run.wait(timeout=15):
            raise TimeoutError("Timed out waiting to resume the uniqueness-conflict test.")
        return result

    monkeypatch.setattr(
        ReplenishmentEngine,
        "evaluate_sku_store_replenishment",
        staticmethod(pause_after_evaluation),
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _run_cycle,
            session_factory,
            Barrier(1),
            sku,
            store,
        )
        try:
            assert evaluated.wait(timeout=15)
            with session_factory() as competing_session:
                competing_session.add(
                    m.PurchaseRecommendation(
                        sku_id=sku.id,
                        store_id=store.id,
                        supplier_id=supplier.id,
                        reorder_policy_id=policy.id,
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
                )
                competing_session.commit()
        finally:
            continue_run.set()

        response = future.result(timeout=30)

    assert response.success
    assert "generated 0 recommendations" in response.message
    assert "skipped 1 existing replenishment cycles" in response.message
    assert _active_cycle_count(session_factory, sku, store) == 1
