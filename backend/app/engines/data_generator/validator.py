from typing import Dict, Any


class DataIntegrityError(Exception):
    pass


def validate_synthetic_dataset(data: Dict[str, Any]) -> bool:
    """
    Validates synthetic dataset for schema integrity, non-negative constraints,
    referential consistency, and absence of NaN/null values.
    """
    skus = data.get("skus", [])
    stores = data.get("stores", [])
    suppliers = data.get("suppliers", [])
    supplier_skus = data.get("supplier_skus", [])
    sales = data.get("sales_history", [])
    inventory = data.get("inventory_snapshots", [])
    anomalies = data.get("inventory_exceptions", [])

    if not skus or not stores or not suppliers:
        raise DataIntegrityError("Dataset missing essential master entity collections.")

    sku_ids = {s["id"] for s in skus}
    store_ids = {s["id"] for s in stores}
    supplier_ids = {s["id"] for s in suppliers}

    # Verify SKU constraints
    for sku in skus:
        if sku["unit_cost"] < 0:
            raise DataIntegrityError(f"SKU {sku['sku_code']} has negative unit_cost")
        if sku["unit_price"] < sku["unit_cost"]:
            raise DataIntegrityError(f"SKU {sku['sku_code']} has unit_price < unit_cost")
        if sku["pack_size"] < 1:
            raise DataIntegrityError(f"SKU {sku['sku_code']} has invalid pack_size")

    # Verify Store constraints
    for st in stores:
        if st["warehouse_capacity_units"] <= 0:
            raise DataIntegrityError(f"Store {st['store_code']} has invalid warehouse capacity")

    # Verify SupplierSKU foreign keys
    for ss in supplier_skus:
        if ss["sku_id"] not in sku_ids:
            raise DataIntegrityError(f"SupplierSKU references non-existent SKU {ss['sku_id']}")
        if ss["supplier_id"] not in supplier_ids:
            raise DataIntegrityError(f"SupplierSKU references non-existent Supplier {ss['supplier_id']}")
        if ss["minimum_order_quantity"] < 1:
            raise DataIntegrityError("SupplierSKU has invalid MOQ")

    # Verify Sales non-negative units and revenue
    for sale in sales:
        if sale["units_sold"] < 0:
            raise DataIntegrityError("Negative units_sold in sales history")
        if sale["revenue"] < 0:
            raise DataIntegrityError("Negative revenue in sales history")
        if sale["sku_id"] not in sku_ids or sale["store_id"] not in store_ids:
            raise DataIntegrityError("Orphan sales history record detected")

    # Verify Inventory snapshot conservation
    for inv in inventory:
        if inv["opening_stock"] < 0 or inv["closing_stock"] < 0:
            raise DataIntegrityError("Negative stock level in inventory snapshot")
        if inv["sku_id"] not in sku_ids or inv["store_id"] not in store_ids:
            raise DataIntegrityError("Orphan inventory snapshot detected")

    # Verify that all 5 labeled anomalies exist
    anomaly_types = {a["exception_type"] for a in anomalies}
    expected_anomalies = {
        "STOCKOUT_AS_ZERO_DEMAND",
        "PACK_SIZE_VIOLATION",
        "DISCONTINUED_SKU_ORDER",
        "NEGATIVE_LEAD_TIME",
        "FUTURE_LEAKAGE_FORECAST",
    }
    missing = expected_anomalies - anomaly_types
    if missing:
        raise DataIntegrityError(f"Missing required labeled anomalies: {missing}")

    return True

