from datetime import date, datetime
from decimal import Decimal
import math
from numbers import Real
from typing import Any, Dict, Iterable


class DataIntegrityError(Exception):
    pass


def _require_fields(records: Iterable[Dict[str, Any]], fields: tuple[str, ...], collection: str) -> None:
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise DataIntegrityError(f"{collection}[{index}] must be a mapping")
        for field in fields:
            if field not in record or record[field] is None:
                raise DataIntegrityError(f"{collection}[{index}].{field} is required")


def _check_finite(value: Any, path: str) -> None:
    if isinstance(value, Decimal) and not value.is_finite():
        raise DataIntegrityError(f"{path} contains a non-finite number")
    if isinstance(value, Real) and not isinstance(value, bool) and not math.isfinite(float(value)):
        raise DataIntegrityError(f"{path} contains a non-finite number")
    if isinstance(value, dict):
        for key, nested in value.items():
            _check_finite(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _check_finite(nested, f"{path}[{index}]")


def _check_unique(records: list[Dict[str, Any]], fields: tuple[str, ...], collection: str) -> None:
    seen: set[tuple[Any, ...]] = set()
    for index, record in enumerate(records):
        key = tuple(record[field] for field in fields)
        if key in seen:
            raise DataIntegrityError(f"Duplicate {collection} identity {key}")
        seen.add(key)


def _check_non_negative(record: Dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    for field in fields:
        if record[field] < 0:
            raise DataIntegrityError(f"{label} has negative {field}")


def _check_chronological_records(
    records: list[Dict[str, Any]], pair_fields: tuple[str, str], date_field: str, collection: str
) -> None:
    last_dates: dict[tuple[Any, Any], date] = {}
    for record in records:
        record_date = record[date_field]
        if not isinstance(record_date, date):
            raise DataIntegrityError(f"{collection}.{date_field} must be a date")
        pair = (record[pair_fields[0]], record[pair_fields[1]])
        if pair in last_dates and record_date < last_dates[pair]:
            raise DataIntegrityError(f"{collection} dates are out of order for {pair}")
        last_dates[pair] = record_date


def validate_synthetic_dataset(data: Dict[str, Any]) -> bool:
    """Validate required values, keys, foreign keys, chronology, and numeric bounds.

    Optional nullable fields (for example an exception's supplier_id) are allowed;
    required entity fields cannot be null and all numeric values must be finite.
    """
    if not isinstance(data, dict):
        raise DataIntegrityError("Dataset must be a mapping")

    collection_fields = {
        "skus": ("id", "sku_code", "name", "category", "unit_cost", "unit_price", "pack_size", "is_active"),
        "stores": ("id", "store_code", "name", "warehouse_capacity_units", "is_active"),
        "suppliers": ("id", "supplier_code", "name", "default_lead_time_days", "reliability_score", "is_active"),
        "supplier_skus": ("id", "sku_id", "supplier_id", "contract_lead_time_days", "minimum_order_quantity", "pack_size", "unit_cost", "is_primary"),
        "reorder_policies": ("id", "sku_id", "store_id", "target_service_level", "review_period_days", "min_safety_stock_units", "is_active"),
        "lead_time_observations": ("supplier_sku_id", "order_date", "promised_delivery_date", "actual_delivery_date", "actual_lead_time_days", "units_ordered", "units_received", "is_anomaly"),
        "sales_history": ("sku_id", "store_id", "sale_date", "units_sold", "revenue", "is_promotion", "promotion_discount_pct", "day_of_week"),
        "inventory_snapshots": ("sku_id", "store_id", "snapshot_date", "opening_stock", "closing_stock", "in_transit_stock", "reserved_stock", "stockout_flag", "lost_sales_estimate"),
        "inventory_exceptions": ("id", "exception_type", "severity", "description", "payload", "is_resolved"),
    }
    collections: dict[str, list[Dict[str, Any]]] = {}
    for name, fields in collection_fields.items():
        records = data.get(name)
        if not isinstance(records, list):
            raise DataIntegrityError(f"Dataset collection {name} must be a list")
        _require_fields(records, fields, name)
        collections[name] = records

    skus = collections["skus"]
    stores = collections["stores"]
    suppliers = collections["suppliers"]
    if not skus or not stores or not suppliers:
        raise DataIntegrityError("Dataset missing essential master entity collections")

    for name, fields in {
        "skus": ("id",), "stores": ("id",), "suppliers": ("id",),
        "supplier_skus": ("id",), "reorder_policies": ("id",),
        "inventory_exceptions": ("id",),
    }.items():
        _check_unique(collections[name], fields, name)
    for name, fields in {
        "skus": ("sku_code",), "stores": ("store_code",),
        "suppliers": ("supplier_code",),
        "supplier_skus": ("sku_id", "supplier_id"),
        "reorder_policies": ("sku_id", "store_id"),
        "sales_history": ("sku_id", "store_id", "sale_date"),
        "inventory_snapshots": ("sku_id", "store_id", "snapshot_date"),
    }.items():
        _check_unique(collections[name], fields, name)

    sku_ids = {row["id"] for row in skus}
    store_ids = {row["id"] for row in stores}
    supplier_ids = {row["id"] for row in suppliers}
    supplier_sku_ids = {row["id"] for row in collections["supplier_skus"]}

    for name, records in collections.items():
        for index, record in enumerate(records):
            _check_finite(record, f"{name}[{index}]")

    for sku in skus:
        if sku["unit_cost"] < 0 or sku["unit_price"] < sku["unit_cost"]:
            raise DataIntegrityError(f"SKU {sku['sku_code']} has invalid unit pricing")
        if sku["pack_size"] < 1:
            raise DataIntegrityError(f"SKU {sku['sku_code']} has invalid pack_size")
    for store in stores:
        if store["warehouse_capacity_units"] <= 0:
            raise DataIntegrityError(f"Store {store['store_code']} has invalid warehouse capacity")
    for supplier in suppliers:
        _check_non_negative(supplier, ("default_lead_time_days",), "Supplier")
        if not 0 <= supplier["reliability_score"] <= 1:
            raise DataIntegrityError(f"Supplier {supplier['supplier_code']} has invalid reliability_score")

    for supplier_sku in collections["supplier_skus"]:
        if supplier_sku["sku_id"] not in sku_ids or supplier_sku["supplier_id"] not in supplier_ids:
            raise DataIntegrityError("SupplierSKU references a missing SKU or Supplier")
        _check_non_negative(supplier_sku, ("contract_lead_time_days", "unit_cost"), "SupplierSKU")
        if supplier_sku["minimum_order_quantity"] < 1 or supplier_sku["pack_size"] < 1:
            raise DataIntegrityError("SupplierSKU has invalid MOQ or pack_size")
    for policy in collections["reorder_policies"]:
        if policy["sku_id"] not in sku_ids or policy["store_id"] not in store_ids:
            raise DataIntegrityError("ReorderPolicy references a missing SKU or Store")
        if policy["target_service_level"] <= 0 or policy["target_service_level"] > 1:
            raise DataIntegrityError("ReorderPolicy has invalid target_service_level")
        if policy["review_period_days"] < 1 or policy["min_safety_stock_units"] < 0:
            raise DataIntegrityError("ReorderPolicy has invalid review period or minimum safety stock")
        maximum = policy.get("max_safety_stock_units")
        if maximum is not None and maximum < policy["min_safety_stock_units"]:
            raise DataIntegrityError("ReorderPolicy maximum safety stock is below its minimum")
        override = policy.get("lead_time_override_days")
        if override is not None and override < 0:
            raise DataIntegrityError("ReorderPolicy has negative lead-time override")

    for observation in collections["lead_time_observations"]:
        if observation["supplier_sku_id"] not in supplier_sku_ids:
            raise DataIntegrityError("Lead-time observation references a missing SupplierSKU")
        order_date = observation["order_date"]
        promised_date = observation["promised_delivery_date"]
        delivery_date = observation["actual_delivery_date"]
        if not all(isinstance(value, date) for value in (order_date, promised_date, delivery_date)):
            raise DataIntegrityError("Lead-time observation dates must be dates")
        if promised_date < order_date or delivery_date < order_date:
            raise DataIntegrityError("Lead-time observation dates are out of order")
        if observation["actual_lead_time_days"] < 0 or (delivery_date - order_date).days != observation["actual_lead_time_days"]:
            raise DataIntegrityError("Lead-time observation has invalid actual lead time")
        _check_non_negative(observation, ("units_ordered", "units_received"), "Lead-time observation")
        if observation["units_received"] > observation["units_ordered"]:
            raise DataIntegrityError("Lead-time observation received more units than ordered")

    for sale in collections["sales_history"]:
        if sale["sku_id"] not in sku_ids or sale["store_id"] not in store_ids:
            raise DataIntegrityError("Orphan sales history record detected")
        _check_non_negative(sale, ("units_sold", "revenue", "promotion_discount_pct"), "Sales history")
        if not 0 <= sale["day_of_week"] <= 6 or sale["day_of_week"] != sale["sale_date"].weekday():
            raise DataIntegrityError("Sales history has invalid day_of_week")
    _check_chronological_records(collections["sales_history"], ("sku_id", "store_id"), "sale_date", "sales_history")

    for snapshot in collections["inventory_snapshots"]:
        if snapshot["sku_id"] not in sku_ids or snapshot["store_id"] not in store_ids:
            raise DataIntegrityError("Orphan inventory snapshot detected")
        _check_non_negative(snapshot, ("opening_stock", "closing_stock", "in_transit_stock", "reserved_stock", "lost_sales_estimate"), "Inventory snapshot")
        if snapshot["closing_stock"] > snapshot["opening_stock"]:
            raise DataIntegrityError("Inventory closing stock exceeds opening stock")
    _check_chronological_records(collections["inventory_snapshots"], ("sku_id", "store_id"), "snapshot_date", "inventory_snapshots")

    for exception in collections["inventory_exceptions"]:
        if exception.get("sku_id") is not None and exception["sku_id"] not in sku_ids:
            raise DataIntegrityError("Inventory exception references a missing SKU")
        if exception.get("store_id") is not None and exception["store_id"] not in store_ids:
            raise DataIntegrityError("Inventory exception references a missing Store")
        if exception.get("supplier_id") is not None and exception["supplier_id"] not in supplier_ids:
            raise DataIntegrityError("Inventory exception references a missing Supplier")
        if not isinstance(exception["payload"], dict):
            raise DataIntegrityError("Inventory exception payload must be a mapping")

    metadata = data.get("metadata", {})
    if metadata:
        try:
            start_date = date.fromisoformat(metadata["start_date"])
            end_date = date.fromisoformat(metadata["end_date"])
            expected_days = int(metadata["num_days"])
        except (KeyError, TypeError, ValueError) as error:
            raise DataIntegrityError("Dataset metadata has invalid date range") from error
        if end_date < start_date or (end_date - start_date).days + 1 != expected_days:
            raise DataIntegrityError("Dataset metadata date range does not match num_days")
        for name, date_field in (("sales_history", "sale_date"), ("inventory_snapshots", "snapshot_date")):
            for record in collections[name]:
                if not start_date <= record[date_field] <= end_date:
                    raise DataIntegrityError(f"{name} contains a date outside dataset metadata bounds")

    anomaly_types = {item["exception_type"] for item in collections["inventory_exceptions"]}
    expected_anomalies = {
        "STOCKOUT_AS_ZERO_DEMAND", "PACK_SIZE_VIOLATION",
        "DISCONTINUED_SKU_ORDER", "NEGATIVE_LEAD_TIME",
        "FUTURE_LEAKAGE_FORECAST",
    }
    missing = expected_anomalies - anomaly_types
    if missing:
        raise DataIntegrityError(f"Missing required labeled anomalies: {missing}")
    return True
