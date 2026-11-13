import pytest
from datetime import timedelta
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




def _mini_dataset(seed=DEFAULT_SEED):
    gen = SyntheticDataGenerator(profile_name="dev", seed=seed)
    gen.profile = type("Mini", (), {"name": "mini", "num_skus": 5, "num_stores": 2, "num_days": 10, "num_suppliers": 2})()
    gen.start_date = gen.end_date - timedelta(days=gen.profile.num_days - 1)
    return gen.generate()


def test_generator_ids_and_values_are_deterministic_for_same_seed():
    first = _mini_dataset()
    second = _mini_dataset()

    assert first == second
    assert validate_synthetic_dataset(first)


def test_generator_different_seed_changes_ids_and_values():
    first = _mini_dataset(DEFAULT_SEED)
    second = _mini_dataset(DEFAULT_SEED + 1)

    assert first["skus"][0]["id"] != second["skus"][0]["id"]
    assert first["skus"][0]["unit_cost"] != second["skus"][0]["unit_cost"]
    assert [row["units_sold"] for row in first["sales_history"]] != [row["units_sold"] for row in second["sales_history"]]


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda data: data["skus"][1].update(id=data["skus"][0]["id"]),
        lambda data: data["sales_history"].append(data["sales_history"][0].copy()),
        lambda data: data["skus"][0].update(name=None),
        lambda data: data["skus"][0].update(unit_cost=float("nan")),
        lambda data: data["sales_history"][0].update(sku_id="missing-sku"),
        lambda data: data["sales_history"].__setitem__(slice(0, 2), reversed(data["sales_history"][:2])),
        lambda data: data["lead_time_observations"][0].update(actual_delivery_date=data["lead_time_observations"][0]["order_date"] - timedelta(days=1)),
    ],
    ids=["duplicate-primary-key", "duplicate-sales-key", "null-required-field", "nan-value", "foreign-key", "date-order", "lead-time-date-order"],
)
def test_validator_rejects_integrity_corruption(corrupt):
    from copy import deepcopy

    data = deepcopy(_mini_dataset())
    corrupt(data)
    with pytest.raises(DataIntegrityError):
        validate_synthetic_dataset(data)
