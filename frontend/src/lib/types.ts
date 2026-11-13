export type Numeric = number | string

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface Overview {
  total_skus: number
  total_stores: number
  total_suppliers: number
  total_inventory_units: number
  total_inventory_valuation: Numeric
  active_stockouts_count: number
  pending_recommendations_count: number
  critical_exceptions_count: number
  active_stores_count: number
  low_stock_products_count: number
  forecast_accuracy_pct: number | null
  inventory_health_pct: number | null
  categories: { category: string; sku_count: number; total_sales_units: number; total_revenue: Numeric }[]
  store_capacities: { store_code: string; name: string; warehouse_capacity_units: number; current_inventory_units: number; utilization_pct: number }[]
}

export interface TrendPoint {
  date: string
  value: number
}

export interface DashboardTrends {
  demand_trend: TrendPoint[]
  stockout_trend: TrendPoint[]
  inventory_distribution: { category: string; units: number }[]
}

export interface SKU {
  id: string
  sku_code: string
  name: string
  category: string
  subcategory: string | null
  unit_cost: Numeric
  unit_price: Numeric
  pack_size: number
  is_active: boolean
}

export interface Store {
  id: string
  store_code: string
  name: string
  store_type: string
  warehouse_capacity_units: number
  is_active: boolean
}

export interface Supplier {
  id: string
  supplier_code: string
  name: string
  contact_email: string | null
  default_lead_time_days: number
  reliability_score: Numeric
  is_active: boolean
}

export interface SupplierSKU {
  id: string
  supplier_id: string
  sku_id: string
  contract_lead_time_days: number
  minimum_order_quantity: number
  pack_size: number
  unit_cost: Numeric
  is_primary: boolean
  supplier_name?: string | null
  sku_code?: string | null
}

export interface InventoryItem {
  id: number
  sku_id: string
  store_id: string
  snapshot_date: string
  opening_stock: number
  closing_stock: number
  in_transit_stock: number
  reserved_stock: number
  stockout_flag: boolean
  lost_sales_estimate: number
  sku_code?: string | null
  sku_name?: string | null
  category?: string | null
  store_code?: string | null
  available_units?: number | null
  reorder_point?: number | null
  safety_stock_units?: number | null
  inventory_status?: 'STOCKOUT' | 'LOW' | 'HEALTHY' | 'UNKNOWN' | null
}

export interface Sale {
  id: number
  sku_id: string
  store_id: string
  sale_date: string
  units_sold: number
  revenue: Numeric
  is_promotion: boolean
}

export interface Forecast {
  id: string
  sku_id: string
  store_id: string
  model_name: string
  forecast_date: string
  target_date: string
  horizon_days: number
  predicted_units: Numeric
  confidence_lower: Numeric | null
  confidence_upper: Numeric | null
  sku_code?: string | null
  store_code?: string | null
}

export interface ForecastEvaluation {
  id: number
  sku_id: string
  store_id: string
  model_name: string
  evaluation_date: string
  horizon_days: number
  mae: Numeric
  rmse: Numeric
  wape: Numeric | null
  bias: Numeric
  sample_size: number
  sku_code?: string | null
  store_code?: string | null
}

export interface Recommendation {
  id: string
  sku_id: string
  store_id: string
  supplier_id: string
  recommendation_date: string
  current_on_hand: number
  current_on_order: number
  net_inventory_position: number
  lead_time_demand: Numeric
  safety_stock: number
  reorder_point: number
  raw_order_quantity: number
  recommended_units: number
  total_cost: Numeric
  status: string
  explanation: Record<string, unknown>
  reviewed_by: string | null
  reviewed_at: string | null
  review_notes: string | null
  sku_code?: string | null
  sku_name?: string | null
  store_code?: string | null
  supplier_name?: string | null
  minimum_order_quantity?: number | null
  pack_size?: number | null
}

export interface InventoryException {
  id: string
  sku_id: string | null
  store_id: string | null
  exception_type: string
  severity: string
  description: string
  payload: Record<string, unknown>
  is_resolved: boolean
  created_at: string
  resolved_at: string | null
  sku_code?: string | null
  store_code?: string | null
}

export interface SupplierSKUDetail extends SupplierSKU {
  sku_name?: string | null
}
