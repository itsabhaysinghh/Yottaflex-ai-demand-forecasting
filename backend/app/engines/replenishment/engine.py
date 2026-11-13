import math
import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, Any, Tuple, Optional, List

from app.engines.replenishment.formulas import (
    calculate_lead_time_demand,
    calculate_safety_stock,
    calculate_reorder_point,
    enforce_pack_and_moq,
    get_z_score,
)


class ReplenishmentEngine:
    """
    Decision-support replenishment engine calculating statistically rigorous
    inventory policies and explainable purchase recommendations.
    """

    @classmethod
    def evaluate_sku_store_replenishment(
        cls,
        sku: Dict[str, Any],
        store: Dict[str, Any],
        supplier_sku: Dict[str, Any],
        current_inventory: Dict[str, Any],
        reorder_policy: Dict[str, Any],
        avg_daily_demand: float,
        demand_std_dev: float,
        lead_time_days: float,
        lead_time_std_dev: float,
        store_current_total_units: int,
        evaluation_date: date,
        enforce_capacity: bool = True,
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Evaluates a single SKU-Store pair for replenishment need.
        Returns: (recommendation_dict or None, list_of_exceptions)
        """
        exceptions: List[Dict[str, Any]] = []

        # 1. Check for discontinued SKU
        if not sku.get("is_active", True):
            exceptions.append({
                "id": uuid.uuid4(),
                "sku_id": sku["id"],
                "store_id": store["id"],
                "supplier_id": supplier_sku.get("supplier_id"),
                "exception_type": "DISCONTINUED_SKU_ORDER",
                "severity": "CRITICAL",
                "description": f"Replenishment evaluated for inactive SKU {sku.get('sku_code')}. Purchase blocked.",
                "payload": {"sku_code": sku.get("sku_code"), "is_active": False},
                "is_resolved": False,
            })
            return None, exceptions

        # 2. Extract current stock levels
        on_hand = int(current_inventory.get("closing_stock", 0))
        on_order = int(current_inventory.get("in_transit_stock", 0))
        reserved = int(current_inventory.get("reserved_stock", 0))
        net_ip = on_hand + on_order - reserved

        # 3. Parameters from policy and supplier
        service_level = float(reorder_policy.get("target_service_level", 0.95))
        min_ss = int(reorder_policy.get("min_safety_stock_units", 0))
        max_ss = reorder_policy.get("max_safety_stock_units")
        review_days = int(reorder_policy.get("review_period_days", 7))

        pack_size = int(supplier_sku.get("pack_size", sku.get("pack_size", 1)))
        moq = int(supplier_sku.get("minimum_order_quantity", 1))
        unit_cost = Decimal(str(supplier_sku.get("unit_cost", sku.get("unit_cost", "0.00"))))

        # 4. Inventory calculations
        ltd = calculate_lead_time_demand(
            avg_daily_demand=avg_daily_demand,
            avg_lead_time_days=lead_time_days,
        )
        safety_stock, sigma_ltd = calculate_safety_stock(
            avg_daily_demand=avg_daily_demand,
            demand_std_dev=demand_std_dev,
            avg_lead_time_days=lead_time_days,
            lead_time_std_dev=lead_time_std_dev,
            service_level=service_level,
            min_safety_stock=min_ss,
            max_safety_stock=max_ss,
        )
        rop = calculate_reorder_point(lead_time_demand=ltd, safety_stock=safety_stock)

        # 5. Order trigger condition
        if net_ip > rop:
            # Inventory position is healthy, no reorder needed
            return None, exceptions

        # Review cycle demand: demand expected during the review interval
        cycle_demand = avg_daily_demand * review_days
        target_inventory = rop + cycle_demand
        raw_order_quantity = max(1, math.ceil(target_inventory - net_ip))

        # Enforce pack size and MOQ
        recommended_units, units_added, moq_triggered = enforce_pack_and_moq(
            raw_quantity=raw_order_quantity,
            pack_size=pack_size,
            moq=moq,
        )

        # 6. Warehouse capacity validation
        capacity = int(store.get("warehouse_capacity_units", 50000))
        remaining_capacity = max(0, capacity - store_current_total_units)

        status = "PENDING"
        capacity_flag = False

        if enforce_capacity and recommended_units > remaining_capacity:
            capacity_flag = True
            if moq > remaining_capacity:
                status = "FLAGGED_EXCEPTION"
                exceptions.append({
                    "id": uuid.uuid4(),
                    "sku_id": sku["id"],
                    "store_id": store["id"],
                    "supplier_id": supplier_sku.get("supplier_id"),
                    "exception_type": "MOQ_CAPACITY_CONFLICT",
                    "severity": "CRITICAL",
                    "description": (
                        f"Supplier MOQ of {moq} units exceeds store {store.get('store_code')} "
                        f"remaining warehouse capacity of {remaining_capacity} units."
                    ),
                    "payload": {
                        "moq": moq,
                        "remaining_capacity": remaining_capacity,
                        "store_capacity": capacity,
                        "store_code": store.get("store_code"),
                    },
                    "is_resolved": False,
                })
            else:
                status = "FLAGGED_EXCEPTION"
                exceptions.append({
                    "id": uuid.uuid4(),
                    "sku_id": sku["id"],
                    "store_id": store["id"],
                    "supplier_id": supplier_sku.get("supplier_id"),
                    "exception_type": "CAPACITY_OVERFLOW",
                    "severity": "HIGH",
                    "description": (
                        f"Recommended purchase of {recommended_units} units exceeds available "
                        f"capacity ({remaining_capacity} units) for store {store.get('store_code')}."
                    ),
                    "payload": {
                        "recommended_units": recommended_units,
                        "remaining_capacity": remaining_capacity,
                        "store_capacity": capacity,
                    },
                    "is_resolved": False,
                })

        total_cost = round(Decimal(str(recommended_units)) * unit_cost, 2)

        # 7. Formulate structured explainability payload
        explanation = {
            "trigger_reason": f"Net inventory position ({net_ip}) is at or below reorder point ({rop}).",
            "demand_parameters": {
                "avg_daily_demand": round(avg_daily_demand, 2),
                "demand_std_dev": round(demand_std_dev, 2),
                "review_period_days": review_days,
            },
            "lead_time_parameters": {
                "contract_lead_time_days": round(lead_time_days, 1),
                "lead_time_std_dev": round(lead_time_std_dev, 2),
            },
            "policy_parameters": {
                "target_service_level": service_level,
                "z_score": round(get_z_score(service_level), 3),
                "sigma_ltd": round(sigma_ltd, 2),
                "lead_time_demand": round(ltd, 2),
                "safety_stock": safety_stock,
                "reorder_point": rop,
            },
            "order_adjustments": {
                "raw_order_quantity": raw_order_quantity,
                "supplier_pack_size": pack_size,
                "units_added_by_pack_rounding": units_added,
                "supplier_moq": moq,
                "moq_triggered": moq_triggered,
                "final_recommended_units": recommended_units,
            },
            "warehouse_capacity_check": {
                "total_store_capacity": capacity,
                "current_store_utilization": store_current_total_units,
                "remaining_capacity": remaining_capacity,
                "capacity_breached": capacity_flag,
                "enforced": enforce_capacity,
            },
        }

        rec = {
            "id": uuid.uuid4(),
            "sku_id": sku["id"],
            "store_id": store["id"],
            "supplier_id": supplier_sku["supplier_id"],
            "reorder_policy_id": reorder_policy.get("id"),
            "recommendation_date": evaluation_date,
            "current_on_hand": on_hand,
            "current_on_order": on_order,
            "net_inventory_position": net_ip,
            "lead_time_demand": Decimal(str(round(ltd, 2))),
            "safety_stock": safety_stock,
            "reorder_point": rop,
            "raw_order_quantity": raw_order_quantity,
            "recommended_units": recommended_units,
            "total_cost": total_cost,
            "status": status,
            "explanation": explanation,
        }

        return rec, exceptions

