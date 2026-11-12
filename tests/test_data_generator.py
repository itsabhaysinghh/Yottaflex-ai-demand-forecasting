import pytest
from decimal import Decimal
from app.engines.data_generator import (
    SyntheticDataGenerator,
    validate_synthetic_dataset,
    DataIntegrityError,
    DEFAULT_SEED,
)


def test_generator_deterministic_reproducibility():
    """
    Verifies that the generator with seed 20261022 produces identical records across runs.
    """
    gen1 = SyntheticDataGenerator(profile_name="dev", seed=DEFAULT_SEED)
    gen1.profile = type("Mini", (), {"name": "mini", "num_skus": 5, "num_stores": 2, "num_days": 10, "num_suppliers": 2})()
    data1 = gen1.generate()

    gen2 = SyntheticDataGenerator(profile_name="dev", seed=DEFAULT_SEED)
    gen2.profile = type("Mini", (), {"name": "mini", "num_skus": 5, "num_stores": 2, "num_days": 10, "num_suppliers": 2})()
    data2 = gen2.generate()

    # Compare first SKU attributes
    assert data1["skus"][0]["sku_code"] == data2["skus"][0]["sku_code"]
    assert data1["skus"][0]["unit_cost"] == data2["skus"][0]["unit_cost"]
    # Compare sales units
    s1 = [s["units_sold"] for s in data1["sales_history"][:20]]
    s2 = [s["units_sold"] for s in data2["sales_history"][:20]]
    assert s1 == s2, "Seed 20261022 did not produce identical sales history sequences!"


def test_labeled_anomalies_present_and_valid():
    """
    Verifies that all 5 explicitly required labeled anomalies are produced:
    1. Stockouts incorrectly interpreted as zero demand
    2. Reorder quantity ignoring pack size
    3. Discontinued SKU receiving a recommendation
    4. Negative lead time
    5. Forecast using future sales
    """
    gen = SyntheticDataGenerator(profile_name="dev")
    gen.profile = type("Mini", (), {"name": "mini", "num_skus": 5, "num_stores": 2, "num_days": 15, "num_suppliers": 2})()
    data = gen.generate()

    exceptions = data["inventory_exceptions"]
    assert len(exceptions) >= 5

    types = {e["exception_type"] for e in exceptions}
    assert "STOCKOUT_AS_ZERO_DEMAND" in types
    assert "PACK_SIZE_VIOLATION" in types
    assert "DISCONTINUED_SKU_ORDER" in types
    assert "NEGATIVE_LEAD_TIME" in types
    assert "FUTURE_LEAKAGE_FORECAST" in types


def test_validator_detects_corrupted_data():
    """
    Verifies that validator raises DataIntegrityError when constraints are violated.
    """
    gen = SyntheticDataGenerator(profile_name="dev")
    gen.profile = type("Mini", (), {"name": "mini", "num_skus": 3, "num_stores": 2, "num_days": 5, "num_suppliers": 2})()
    data = gen.generate()

    # Corrupt SKU unit cost
    data["skus"][0]["unit_cost"] = Decimal("-5.00")
    with pytest.raises(DataIntegrityError):
        validate_synthetic_dataset(data)

