import sys
from pathlib import Path
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Ensure backend directory is in python sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, get_db
from app.main import app, fastapi_app
import app.models as m

# In-memory SQLite engine for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """
    Provides a transactional database session rolled back after test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """
    FastAPI TestClient with overridden get_db dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def sample_master_data(db_session):
    """
    Seeds a minimal master dataset for API and engine tests.
    """
    store = m.Store(
        id=uuid.uuid4(),
        store_code="STR-TEST-001",
        name="Test Store 1",
        store_type="standard",
        warehouse_capacity_units=5000,
        is_active=True,
    )
    sku = m.SKU(
        id=uuid.uuid4(),
        sku_code="SKU-TEST-001",
        name="Test Sparkling Water",
        category="Beverages",
        unit_cost=Decimal("2.50"),
        unit_price=Decimal("4.00"),
        pack_size=12,
        is_active=True,
    )
    supplier = m.Supplier(
        id=uuid.uuid4(),
        supplier_code="SUP-TEST-001",
        name="Test Supplier Ltd",
        default_lead_time_days=7,
        reliability_score=Decimal("0.95"),
        is_active=True,
    )
    db_session.add_all([store, sku, supplier])
    db_session.flush()

    supplier_sku = m.SupplierSKU(
        id=uuid.uuid4(),
        supplier_id=supplier.id,
        sku_id=sku.id,
        contract_lead_time_days=7,
        minimum_order_quantity=24,
        pack_size=12,
        unit_cost=Decimal("2.50"),
        is_primary=True,
    )
    policy = m.ReorderPolicy(
        id=uuid.uuid4(),
        sku_id=sku.id,
        store_id=store.id,
        target_service_level=Decimal("0.950"),
        review_period_days=7,
        min_safety_stock_units=5,
    )
    db_session.add_all([supplier_sku, policy])
    db_session.commit()

    return {
        "store": store,
        "sku": sku,
        "supplier": supplier,
        "supplier_sku": supplier_sku,
        "policy": policy,
    }

