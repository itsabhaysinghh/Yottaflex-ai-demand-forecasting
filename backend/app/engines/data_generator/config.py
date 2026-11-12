from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetProfile:
    name: str
    num_skus: int
    num_stores: int
    num_days: int
    num_suppliers: int


PROFILES = {
    "dev": DatasetProfile(
        name="dev",
        num_skus=100,
        num_stores=10,
        num_days=90,
        num_suppliers=15,
    ),
    "full": DatasetProfile(
        name="full",
        num_skus=2000,
        num_stores=100,
        num_days=365,
        num_suppliers=80,
    ),
}

DEFAULT_SEED = 20261022

