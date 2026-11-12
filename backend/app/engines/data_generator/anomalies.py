import uuid
from datetime import date, timedelta
from typing import List, Dict, Any


def generate_labeled_anomalies(
    skus: List[Dict[str, Any]],
    stores: List[Dict[str, Any]],
    suppliers: List[Dict[str, Any]],
    supplier_skus: List[Dict[str, Any]],
    sales_records: List[Dict[str, Any]],
    inventory_records: List[Dict[str, Any]],
    reference_date: date,
) -> List[Dict[str, Any]]:
    """
    Generates the five explicitly required labeled anomalies for auditing and testing:
    1. Stockout incorrectly interpreted as zero demand (stockout_flag masked as False).
    2. Reorder recommendation ignoring supplier pack size.
    3. Discontinued / inactive SKU receiving a purchase recommendation.
    4. Negative lead time observation (delivery date before order date).
    5. Forecast using future sales data (temporal data leakage).
    """
    exceptions = []

    # 1. Stockout incorrectly interpreted as zero demand
    # Find a record with genuine stockout and inject an exception
    sample_sku = skus[0]
    sample_store = stores[0]
    exceptions.append({
        "id": uuid.uuid4(),
        "sku_id": sample_sku["id"],
        "store_id": sample_store["id"],
        "supplier_id": None,
        "exception_type": "STOCKOUT_AS_ZERO_DEMAND",
        "severity": "HIGH",
        "description": "Stockout on 0 inventory was erroneously classified as 0 unconstrained customer demand.",
        "payload": {
            "sku_code": sample_sku["sku_code"],
            "store_code": sample_store["store_code"],
            "date": str(reference_date - timedelta(days=5)),
            "recorded_sales": 0,
            "closing_stock": 0,
            "stockout_flag_erroneous": False,
            "estimated_lost_demand": 14,
        },
        "is_resolved": False,
    })

    # 2. Reorder recommendation ignoring pack size
    target_supp_sku = supplier_skus[0]
    pack_size = target_supp_sku["pack_size"] if target_supp_sku["pack_size"] > 1 else 12
    exceptions.append({
        "id": uuid.uuid4(),
        "sku_id": target_supp_sku["sku_id"],
        "store_id": sample_store["id"],
        "supplier_id": target_supp_sku["supplier_id"],
        "exception_type": "PACK_SIZE_VIOLATION",
        "severity": "MEDIUM",
        "description": f"Purchase proposal of 47 units violates mandatory supplier pack size of {pack_size}.",
        "payload": {
            "recommended_units": 47,
            "supplier_pack_size": pack_size,
            "remainder": 47 % pack_size,
            "compliant_multiple": ((47 // pack_size) + 1) * pack_size,
        },
        "is_resolved": False,
    })

    # 3. Discontinued SKU receiving a recommendation
    inactive_sku = next((s for s in skus if not s.get("is_active", True)), None)
    if not inactive_sku:
        # Mark one SKU as discontinued for this explicit audit test
        inactive_sku = skus[-1]
        inactive_sku["is_active"] = False

    exceptions.append({
        "id": uuid.uuid4(),
        "sku_id": inactive_sku["id"],
        "store_id": sample_store["id"],
        "supplier_id": target_supp_sku["supplier_id"],
        "exception_type": "DISCONTINUED_SKU_ORDER",
        "severity": "CRITICAL",
        "description": f"Replenishment proposed for deactivated/discontinued SKU {inactive_sku['sku_code']}.",
        "payload": {
            "sku_code": inactive_sku["sku_code"],
            "sku_name": inactive_sku["name"],
            "is_active": False,
            "attempted_order_units": 150,
        },
        "is_resolved": False,
    })

    # 4. Negative lead time
    exceptions.append({
        "id": uuid.uuid4(),
        "sku_id": target_supp_sku["sku_id"],
        "store_id": sample_store["id"],
        "supplier_id": target_supp_sku["supplier_id"],
        "exception_type": "NEGATIVE_LEAD_TIME",
        "severity": "HIGH",
        "description": "Invalid empirical observation: delivery timestamp preceded purchase order issuance date.",
        "payload": {
            "order_date": str(reference_date - timedelta(days=10)),
            "actual_delivery_date": str(reference_date - timedelta(days=12)),
            "actual_lead_time_days": -2,
        },
        "is_resolved": False,
    })

    # 5. Forecast using future sales
    exceptions.append({
        "id": uuid.uuid4(),
        "sku_id": sample_sku["id"],
        "store_id": sample_store["id"],
        "supplier_id": None,
        "exception_type": "FUTURE_LEAKAGE_FORECAST",
        "severity": "CRITICAL",
        "description": "Model training pipeline ingested ground-truth sales data beyond the forecast cutoff date.",
        "payload": {
            "cutoff_date": str(reference_date - timedelta(days=14)),
            "leaked_feature_date_max": str(reference_date - timedelta(days=2)),
            "leakage_horizon_days": 12,
        },
        "is_resolved": False,
    })

    return exceptions

