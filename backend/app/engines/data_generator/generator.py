import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Any
import numpy as np
from app.engines.data_generator.config import PROFILES, DEFAULT_SEED, DatasetProfile
from app.engines.data_generator.anomalies import generate_labeled_anomalies

CATEGORIES = {
    "Beverages": ["Sparkling Water", "Cold Brew Coffee", "Green Tea", "Fresh Orange Juice", "Almond Milk", "Kombucha"],
    "Snacks": ["Sea Salt Potato Chips", "Pretzel Sticks", "Roasted Almonds", "Granola Bars", "Dark Chocolate Bar", "Rice Crackers"],
    "Dairy": ["Whole Organic Milk", "Greek Yogurt Plain", "Aged Cheddar Cheese", "Salted Sweet Cream Butter", "Cottage Cheese"],
    "Bakery": ["Artisan Sourdough Loaf", "Everything Bagels", "Brioche Burger Buns", "Butter Croissants", "Multigrain Bread"],
    "Produce": ["Organic Cavendish Bananas", "Honeycrisp Apples", "Hass Avocados", "Baby Spinach Bag", "Cherry Tomatoes"],
    "Pantry": ["Extra Virgin Olive Oil", "Organic Pasta Sauce", "Jasmine Rice 5lb", "Canned Black Beans", "Rolled Oats 32oz"],
    "Frozen": ["Stone-Baked Frozen Pizza", "Organic Frozen Berries", "Vanilla Bean Ice Cream", "Sweet Potato Fries"],
    "Household": ["Recycled Paper Towels", "Eco Dish Soap", "Concentrated Laundry Pods", "Heavy Duty Trash Bags"],
}

DOW_SEASONALITY = [0.85, 0.88, 0.92, 0.98, 1.20, 1.30, 1.10]  # Mon to Sun


class SyntheticDataGenerator:
    """
    Vectorized high-performance synthetic data generator producing realistic retail records.
    Reproducibility guaranteed by fixed seed (default: 20261022).
    """

    def __init__(self, profile_name: str = "dev", seed: int = DEFAULT_SEED, end_date: date | None = None):
        self.profile: DatasetProfile = PROFILES.get(profile_name, PROFILES["dev"])
        self.seed = seed
        self._id_namespace = uuid.uuid5(
            uuid.NAMESPACE_URL, f"yottaflex:synthetic-data:{seed}"
        )
        self.rng = np.random.default_rng(seed)
        self.end_date = end_date or date(2026, 11, 12)
        self.start_date = self.end_date - timedelta(days=self.profile.num_days - 1)

    def _make_id(self, entity: str, identity: str) -> uuid.UUID:
        return uuid.uuid5(self._id_namespace, f"{entity}:{identity}")

    def generate(self) -> Dict[str, Any]:
        """
        Executes full generation run and returns structured dictionary of domain entities.
        """
        skus = self._generate_skus()
        stores = self._generate_stores()
        suppliers = self._generate_suppliers()
        supplier_skus = self._generate_supplier_skus(skus, suppliers)
        reorder_policies = self._generate_reorder_policies(skus, stores)
        lead_time_obs = self._generate_lead_time_observations(supplier_skus)
        sales_records, inventory_records = self._generate_sales_and_inventory(skus, stores, supplier_skus)

        anomalies = generate_labeled_anomalies(
            skus=skus,
            stores=stores,
            suppliers=suppliers,
            supplier_skus=supplier_skus,
            sales_records=sales_records,
            inventory_records=inventory_records,
            reference_date=self.end_date,
            id_factory=self._make_id,
        )

        return {
            "skus": skus,
            "stores": stores,
            "suppliers": suppliers,
            "supplier_skus": supplier_skus,
            "lead_time_observations": lead_time_obs,
            "sales_history": sales_records,
            "inventory_snapshots": inventory_records,
            "reorder_policies": reorder_policies,
            "inventory_exceptions": anomalies,
            "metadata": {
                "profile": self.profile.name,
                "seed": self.seed,
                "start_date": str(self.start_date),
                "end_date": str(self.end_date),
                "num_days": self.profile.num_days,
            },
        }

    def _generate_skus(self) -> List[Dict[str, Any]]:
        skus = []
        cat_names = list(CATEGORIES.keys())
        pack_choices = [1, 4, 6, 12, 24]

        for i in range(self.profile.num_skus):
            cat = cat_names[i % len(cat_names)]
            item_names = CATEGORIES[cat]
            item_name = item_names[i % len(item_names)]
            sku_code = f"SKU-{cat[:3].upper()}-{i+1:04d}"

            # Pricing: realistic margins (30% to 55%)
            cost = round(float(self.rng.uniform(1.50, 45.00)), 2)
            margin = self.rng.uniform(1.30, 1.55)
            price = round(cost * margin, 2)
            pack_size = int(self.rng.choice(pack_choices, p=[0.35, 0.20, 0.25, 0.15, 0.05]))

            # Discontinue 3% of SKUs
            is_active = bool(self.rng.random() > 0.03)

            skus.append({
                "id": self._make_id("sku", sku_code),
                "sku_code": sku_code,
                "name": f"{item_name} #{i+1}",
                "category": cat,
                "subcategory": f"{cat} General",
                "unit_cost": Decimal(str(cost)),
                "unit_price": Decimal(str(price)),
                "pack_size": pack_size,
                "is_active": is_active,
            })
        return skus

    def _generate_stores(self) -> List[Dict[str, Any]]:
        stores = []
        types = ["flagship", "standard", "express", "warehouse"]

        for i in range(self.profile.num_stores):
            st_type = types[i % len(types)]
            store_code = f"STR-{i+1:03d}"
            # Capacity calibrated to stock holding
            if st_type == "warehouse":
                capacity = int(self.rng.integers(80000, 150000))
            elif st_type == "flagship":
                capacity = int(self.rng.integers(40000, 75000))
            elif st_type == "standard":
                capacity = int(self.rng.integers(20000, 40000))
            else:
                capacity = int(self.rng.integers(10000, 20000))

            stores.append({
                "id": self._make_id("store", store_code),
                "store_code": store_code,
                "name": f"Yotta Store {store_code} ({st_type.capitalize()})",
                "store_type": st_type,
                "warehouse_capacity_units": capacity,
                "is_active": True,
            })
        return stores

    def _generate_suppliers(self) -> List[Dict[str, Any]]:
        suppliers = []
        vendor_names = [
            "Apex Global Distribution", "BlueHarbor Logistics", "Cascade Supply Partners",
            "Delta Prime Wholesale", "Evergreen Merchant Co", "Frontier Food Corp",
            "Glacier Cold Chain", "Heritage Brands Ltd", "Imperial Consumer Goods",
            "Keystone Freight & Supply", "Liberty Logistics Group", "Monarch Trading Hub",
            "Nexus Distribution", "Olympus CPG Partners", "Pinnacle Supply Network"
        ]

        for i in range(self.profile.num_suppliers):
            code = f"SUP-{i+1:03d}"
            name = vendor_names[i % len(vendor_names)]
            lead_time = int(self.rng.integers(3, 15))
            reliability = round(float(self.rng.uniform(0.88, 0.99)), 2)

            suppliers.append({
                "id": self._make_id("supplier", code),
                "supplier_code": code,
                "name": f"{name} {i+1}",
                "contact_email": f"orders@{code.lower()}.yottaflex.internal",
                "default_lead_time_days": lead_time,
                "reliability_score": Decimal(str(reliability)),
                "is_active": True,
            })
        return suppliers

    def _generate_supplier_skus(
        self, skus: List[Dict[str, Any]], suppliers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        supplier_skus = []
        moq_options = [1, 5, 10, 20, 50, 100]

        for sku in skus:
            # Assign primary supplier
            supp = suppliers[int(self.rng.integers(0, len(suppliers)))]
            contract_lt = max(2, supp["default_lead_time_days"] + int(self.rng.integers(-2, 3)))
            moq = int(self.rng.choice(moq_options, p=[0.1, 0.2, 0.3, 0.2, 0.15, 0.05]))
            pack_size = sku["pack_size"]

            supplier_skus.append({
                "id": self._make_id(
                    "supplier_sku", f"{supp['supplier_code']}:{sku['sku_code']}"
                ),
                "supplier_id": supp["id"],
                "sku_id": sku["id"],
                "contract_lead_time_days": contract_lt,
                "minimum_order_quantity": moq,
                "pack_size": pack_size,
                "unit_cost": sku["unit_cost"],
                "is_primary": True,
            })
        return supplier_skus

    def _generate_reorder_policies(
        self, skus: List[Dict[str, Any]], stores: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        policies = []
        service_levels = [Decimal("0.900"), Decimal("0.950"), Decimal("0.980")]

        for store in stores:
            for sku in skus:
                sl = self.rng.choice(service_levels, p=[0.2, 0.7, 0.1])
                policies.append({
                    "id": self._make_id(
                        "reorder_policy", f"{sku['sku_code']}:{store['store_code']}"
                    ),
                    "sku_id": sku["id"],
                    "store_id": store["id"],
                    "target_service_level": sl,
                    "review_period_days": 7,
                    "lead_time_override_days": None,
                    "min_safety_stock_units": int(self.rng.integers(5, 15)),
                    "max_safety_stock_units": int(self.rng.integers(50, 150)),
                    "is_active": True,
                })
        return policies

    def _generate_lead_time_observations(
        self, supplier_skus: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        observations = []
        obs_per_sku = 4

        for ss in supplier_skus:
            contract_lt = ss["contract_lead_time_days"]
            max_order_day = max(2, self.profile.num_days - 10)
            for o in range(obs_per_sku):
                day_offset = int(self.rng.integers(1, max_order_day))
                order_dt = self.start_date + timedelta(days=day_offset)
                promised_dt = order_dt + timedelta(days=contract_lt)

                # Realistic delivery variance around contract SLA
                delay = int(np.round(self.rng.normal(0.5, 1.5)))
                actual_lt = max(1, contract_lt + delay)
                actual_dt = order_dt + timedelta(days=actual_lt)

                qty = int(ss["minimum_order_quantity"] * self.rng.integers(1, 5))
                # 97% on-time full fulfillment
                received_qty = qty if self.rng.random() > 0.03 else int(qty * 0.9)

                observations.append({
                    "supplier_sku_id": ss["id"],
                    "order_date": order_dt,
                    "promised_delivery_date": promised_dt,
                    "actual_delivery_date": actual_dt,
                    "actual_lead_time_days": actual_lt,
                    "units_ordered": qty,
                    "units_received": received_qty,
                    "is_anomaly": False,
                })
        return observations

    def _generate_sales_and_inventory(
        self,
        skus: List[Dict[str, Any]],
        stores: List[Dict[str, Any]],
        supplier_skus: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sales_records = []
        inventory_records = []

        supp_sku_map = {ss["sku_id"]: ss for ss in supplier_skus}

        # Store multiplier matrix
        store_scales = {store["id"]: float(self.rng.uniform(0.7, 1.4)) for store in stores}
        # SKU base mean demand matrix (lambdas between 2.0 and 25.0)
        sku_lambdas = {sku["id"]: float(self.rng.uniform(2.0, 22.0)) for sku in skus}

        for store in stores:
            store_id = store["id"]
            store_scale = store_scales[store_id]

            for sku in skus:
                sku_id = sku["id"]
                base_lambda = sku_lambdas[sku_id]
                unit_price = sku["unit_price"]
                pack_size = sku["pack_size"]
                ss = supp_sku_map.get(sku_id, {})
                lead_time = ss.get("contract_lead_time_days", 7)

                # Running simulation state
                on_hand = int(self.rng.integers(30, 80))
                pipeline_orders: List[Dict[str, Any]] = []

                current_dt = self.start_date
                for day_idx in range(self.profile.num_days):
                    dow = current_dt.weekday()
                    dow_factor = DOW_SEASONALITY[dow]

                    # Process incoming deliveries arriving today
                    arrivals_today = 0
                    remaining_orders = []
                    for order in pipeline_orders:
                        if order["delivery_date"] == current_dt:
                            arrivals_today += order["units"]
                        else:
                            remaining_orders.append(order)
                    pipeline_orders = remaining_orders

                    opening_stock = on_hand + arrivals_today

                    # Promotional event check (sporadic 5% probability)
                    is_promo = bool(self.rng.random() < 0.05)
                    promo_lift = float(self.rng.uniform(1.5, 2.5)) if is_promo else 1.0
                    discount_pct = Decimal(str(round(float(self.rng.uniform(10.0, 25.0)), 2))) if is_promo else Decimal("0.00")

                    # Calculate unconstrained true customer demand
                    expected_demand = base_lambda * store_scale * dow_factor * promo_lift
                    actual_demand = int(self.rng.poisson(max(0.5, expected_demand)))

                    # Constrained sales by physical inventory
                    units_sold = min(opening_stock, actual_demand)
                    closing_stock = opening_stock - units_sold
                    stockout_flag = bool(closing_stock == 0 and actual_demand > opening_stock)
                    lost_sales = actual_demand - units_sold if stockout_flag else 0

                    revenue = Decimal(str(units_sold)) * unit_price * (Decimal("1.00") - (discount_pct / Decimal("100.00")))
                    revenue = round(revenue, 2)

                    # Periodic replenishment trigger (e.g. weekly or when stock is low)
                    if closing_stock < (base_lambda * store_scale * lead_time) and len(pipeline_orders) == 0:
                        order_qty = int(max(ss.get("minimum_order_quantity", 1), base_lambda * store_scale * 14))
                        # Round to pack size
                        order_qty = ((order_qty + pack_size - 1) // pack_size) * pack_size
                        delivery_dt = current_dt + timedelta(days=lead_time)
                        pipeline_orders.append({
                            "delivery_date": delivery_dt,
                            "units": order_qty,
                        })

                    in_transit = sum(o["units"] for o in pipeline_orders)

                    sales_records.append({
                        "sku_id": sku_id,
                        "store_id": store_id,
                        "sale_date": current_dt,
                        "units_sold": units_sold,
                        "revenue": revenue,
                        "is_promotion": is_promo,
                        "promotion_discount_pct": discount_pct,
                        "day_of_week": dow,
                    })

                    inventory_records.append({
                        "sku_id": sku_id,
                        "store_id": store_id,
                        "snapshot_date": current_dt,
                        "opening_stock": opening_stock,
                        "closing_stock": closing_stock,
                        "in_transit_stock": in_transit,
                        "reserved_stock": 0,
                        "stockout_flag": stockout_flag,
                        "lost_sales_estimate": lost_sales,
                    })

                    on_hand = closing_stock
                    current_dt += timedelta(days=1)

        return sales_records, inventory_records
