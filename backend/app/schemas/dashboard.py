from decimal import Decimal
from typing import List
from pydantic import BaseModel


class CategoryMetrics(BaseModel):
    category: str
    sku_count: int
    total_sales_units: int
    total_revenue: Decimal


class StoreCapacityMetrics(BaseModel):
    store_code: str
    name: str
    warehouse_capacity_units: int
    current_inventory_units: int
    utilization_pct: float


class OverviewMetricsResponse(BaseModel):
    total_skus: int
    total_stores: int
    total_suppliers: int
    total_inventory_units: int
    total_inventory_valuation: Decimal
    active_stockouts_count: int
    pending_recommendations_count: int
    critical_exceptions_count: int
    categories: List[CategoryMetrics]
    store_capacities: List[StoreCapacityMetrics]
    active_stores_count: int
    low_stock_products_count: int
    forecast_accuracy_pct: float | None = None
    inventory_health_pct: float | None = None


class TrendPoint(BaseModel):
    date: str
    value: int


class InventoryDistribution(BaseModel):
    category: str
    units: int


class DashboardTrendsResponse(BaseModel):
    demand_trend: List[TrendPoint]
    stockout_trend: List[TrendPoint]
    inventory_distribution: List[InventoryDistribution]
