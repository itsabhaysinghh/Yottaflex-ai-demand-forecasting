import sys
from pathlib import Path
from decimal import Decimal

# Ensure backend is on python path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.engines.data_generator import SyntheticDataGenerator, validate_synthetic_dataset
import app.models  # Register models


def seed_database(profile: str = "dev", seed: int = settings.RANDOM_SEED):
    print(f"==================================================")
    print(f"YottaFlex Demand Forecasting & Replenishment Seed")
    print(f"Profile: {profile} | Seed: {seed}")
    print(f"Database URL: {settings.effective_database_url}")
    print(f"==================================================")

    print("1. Generating synthetic retail dataset...")
    gen = SyntheticDataGenerator(profile_name=profile, seed=seed)
    data = gen.generate()

    print("2. Validating dataset schema and business rules...")
    validate_synthetic_dataset(data)
    print("   Dataset validation passed successfully.")

    print("3. Connecting to database session...")
    db = SessionLocal()
    try:
        # Check if tables exist, create if SQLite or missing
        Base.metadata.create_all(bind=engine)

        # 4. Insert master entities
        print(f"   Inserting {len(data['skus'])} SKUs...")
        for s in data["skus"]:
            db.merge(app.models.SKU(**s))

        print(f"   Inserting {len(data['stores'])} Stores...")
        for st in data["stores"]:
            db.merge(app.models.Store(**st))

        print(f"   Inserting {len(data['suppliers'])} Suppliers...")
        for sup in data["suppliers"]:
            db.merge(app.models.Supplier(**sup))

        db.commit()

        print(f"   Inserting {len(data['supplier_skus'])} Supplier-SKUs...")
        for ss in data["supplier_skus"]:
            db.merge(app.models.SupplierSKU(**ss))

        print(f"   Inserting {len(data['reorder_policies'])} Reorder Policies...")
        for rp in data["reorder_policies"]:
            db.merge(app.models.ReorderPolicy(**rp))

        db.commit()

        print(f"   Inserting {len(data['lead_time_observations'])} Lead Time Observations...")
        for lto in data["lead_time_observations"]:
            db.add(app.models.LeadTimeObservation(**lto))

        print(f"   Inserting {len(data['inventory_exceptions'])} Labeled Anomalies & Exceptions...")
        for exc in data["inventory_exceptions"]:
            db.merge(app.models.InventoryException(**exc))

        db.commit()

        # 5. Insert time-series in batches
        print(f"   Inserting {len(data['sales_history'])} Sales History records...")
        batch_size = 5000
        sales = data["sales_history"]
        for i in range(0, len(sales), batch_size):
            batch = [app.models.SalesHistory(**r) for r in sales[i : i + batch_size]]
            db.bulk_save_objects(batch)
            db.commit()

        print(f"   Inserting {len(data['inventory_snapshots'])} Inventory Snapshots...")
        inv = data["inventory_snapshots"]
        for i in range(0, len(inv), batch_size):
            batch = [app.models.InventorySnapshot(**r) for r in inv[i : i + batch_size]]
            db.bulk_save_objects(batch)
            db.commit()

        print("==================================================")
        print("Database seeding completed successfully!")
        print("==================================================")
    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else settings.DATASET_PROFILE
    seed_database(profile=profile)

