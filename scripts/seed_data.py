import sys
from pathlib import Path

# Ensure backend is on python path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.engines.data_generator import SyntheticDataGenerator, validate_synthetic_dataset
from app.models import (
    InventoryException,
    InventorySnapshot,
    LeadTimeObservation,
    ReorderPolicy,
    SalesHistory,
    SKU,
    Store,
    Supplier,
    SupplierSKU,
)

SEED_MODELS = {
    "skus": SKU,
    "stores": Store,
    "suppliers": Supplier,
    "supplier_skus": SupplierSKU,
    "reorder_policies": ReorderPolicy,
    "lead_time_observations": LeadTimeObservation,
    "sales_history": SalesHistory,
    "inventory_snapshots": InventorySnapshot,
    "inventory_exceptions": InventoryException,
}


def _assert_schema_is_migrated() -> None:
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_config)
    with engine.connect() as connection:
        applied_heads = set(MigrationContext.configure(connection).get_current_heads())
        expected_heads = set(script.get_heads())
        if applied_heads != expected_heads:
            raise RuntimeError(
                "Database migrations are not at the current Alembic head; "
                "run `python -m alembic -c backend/alembic.ini upgrade head` first."
            )

        missing_tables = set(Base.metadata.tables) - set(inspect(connection).get_table_names())
        if missing_tables:
            raise RuntimeError(
                f"Database is missing migrated tables: {', '.join(sorted(missing_tables))}"
            )


def _matches_existing_seed(session: Session, data: dict) -> bool:
    expected_counts = {
        table: len(data[collection])
        for table, collection in (
            ("skus", "skus"),
            ("stores", "stores"),
            ("suppliers", "suppliers"),
            ("supplier_skus", "supplier_skus"),
            ("reorder_policies", "reorder_policies"),
            ("lead_time_observations", "lead_time_observations"),
            ("sales_history", "sales_history"),
            ("inventory_snapshots", "inventory_snapshots"),
        )
    }
    actual_counts = {
        table: session.scalar(select(func.count()).select_from(SEED_MODELS[table])) or 0
        for table in expected_counts
    }
    exception_count = session.scalar(
        select(func.count()).select_from(InventoryException)
    ) or 0
    expected_exception_types = {
        exception["exception_type"] for exception in data["inventory_exceptions"]
    }
    actual_exception_types = set(
        session.scalars(
            select(InventoryException.exception_type).distinct().where(
                InventoryException.exception_type.in_(expected_exception_types)
            )
        )
    )
    has_existing_data = any(actual_counts.values()) or exception_count > 0
    if not has_existing_data:
        return False

    identity_sets_match = (
        set(session.scalars(select(SKU.sku_code)))
        == {record["sku_code"] for record in data["skus"]}
        and set(session.scalars(select(Store.store_code)))
        == {record["store_code"] for record in data["stores"]}
        and set(session.scalars(select(Supplier.supplier_code)))
        == {record["supplier_code"] for record in data["suppliers"]}
    )
    seed_is_complete = (
        all(actual_counts[table] == expected for table, expected in expected_counts.items())
        and expected_exception_types.issubset(actual_exception_types)
        and identity_sets_match
    )
    if not seed_is_complete:
        raise RuntimeError(
            "Database contains data that does not match the complete requested seed profile. "
            "No records were changed; inspect the database before seeding."
        )
    return True


def _save_in_batches(
    session: Session, model: type, records: list[dict], batch_size: int = 5000
) -> None:
    for start in range(0, len(records), batch_size):
        session.bulk_save_objects(
            [model(**record) for record in records[start : start + batch_size]]
        )


def seed_database(profile: str = "dev", seed: int | None = None) -> None:
    engine.echo = False
    _assert_schema_is_migrated()

    if seed is None:
        from app.core.config import settings

        seed = settings.RANDOM_SEED

    print("==================================================")
    print("YottaFlex Demand Forecasting & Replenishment Seed")
    print(f"Profile: {profile} | Seed: {seed}")
    print("==================================================")
    print("1. Generating synthetic retail dataset...")
    data = SyntheticDataGenerator(profile_name=profile, seed=seed).generate()

    print("2. Validating dataset schema and business rules...")
    validate_synthetic_dataset(data)
    print("   Dataset validation passed successfully.")

    with SessionLocal.begin() as session:
        if _matches_existing_seed(session, data):
            print("3. Matching seed data already exists; database left unchanged.")
            return

        print("3. Seeding PostgreSQL in a single transaction...")
        session.add_all(SKU(**record) for record in data["skus"])
        session.add_all(Store(**record) for record in data["stores"])
        session.add_all(Supplier(**record) for record in data["suppliers"])
        session.flush()

        session.add_all(SupplierSKU(**record) for record in data["supplier_skus"])
        session.add_all(ReorderPolicy(**record) for record in data["reorder_policies"])
        session.flush()

        _save_in_batches(session, LeadTimeObservation, data["lead_time_observations"])
        _save_in_batches(session, InventoryException, data["inventory_exceptions"])
        _save_in_batches(session, SalesHistory, data["sales_history"])
        _save_in_batches(session, InventorySnapshot, data["inventory_snapshots"])

    print("   Database seeding completed successfully.")


if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "dev"
    seed_database(profile=profile)
