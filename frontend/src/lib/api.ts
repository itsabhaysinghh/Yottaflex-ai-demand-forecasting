import type {
  DashboardTrends,
  Forecast,
  ForecastEvaluation,
  InventoryException,
  InventoryItem,
  Overview,
  Page,
  Recommendation,
  Sale,
  SKU,
  Store,
  Supplier,
  SupplierSKU,
} from './types'

const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/+$/, '')
const API_ORIGIN = API_BASE.replace(/\/api\/v1$/i, '')

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path.startsWith('http') ? path : `${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown; message?: string } | null
    const detail = typeof body?.detail === 'string'
      ? body.detail
      : Array.isArray(body?.detail)
        ? body.detail.map((issue) => {
          if (typeof issue === 'object' && issue !== null && 'msg' in issue) return String(issue.msg)
          return String(issue)
        }).join('; ')
        : body?.message
    throw new ApiError(detail || `Request failed (${response.status})`, response.status)
  }

  return response.json() as Promise<T>
}

function queryString(params: Record<string, string | number | boolean | null | undefined>): string {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  const value = query.toString()
  return value ? `?${value}` : ''
}

export const api = {
  health: () => request<{ status: string }>(`${API_ORIGIN}/health`),
  overview: () => request<Overview>('/overview'),
  trends: (days = 30) => request<DashboardTrends>(`/overview/trends${queryString({ days })}`),
  skus: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<SKU>>(`/skus${queryString({ page: 1, page_size: 500, ...params })}`),
  sku: (id: string) => request<SKU>(`/skus/${id}`),
  stores: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<Store>>(`/stores${queryString({ page: 1, page_size: 500, ...params })}`),
  suppliers: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<Supplier>>(`/suppliers${queryString({ page: 1, page_size: 500, ...params })}`),
  supplierSkus: (id: string) => request<Page<SupplierSKU>>(`/suppliers/${id}/skus${queryString({ page: 1, page_size: 500 })}`),
  inventory: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<InventoryItem>>(`/inventory${queryString({ page: 1, page_size: 50, current_only: true, ...params })}`),
  sales: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<Sale>>(`/sales${queryString({ page: 1, page_size: 500, ...params })}`),
  forecasts: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<Forecast>>(`/forecasts${queryString({ page: 1, page_size: 500, ...params })}`),
  evaluations: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<ForecastEvaluation>>(`/forecasts/evaluations${queryString({ page: 1, page_size: 500, ...params })}`),
  runForecast: (payload: { sku_id: string; store_id: string; model_name: string; horizon_days: number }) =>
    request<{ message: string; success: boolean }>('/forecasts/run', { method: 'POST', body: JSON.stringify(payload) }),
  recommendations: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<Recommendation>>(`/recommendations${queryString({ page: 1, page_size: 500, ...params })}`),
  runReplenishment: (payload: { store_id?: string; sku_id?: string; enforce_capacity: boolean }) =>
    request<{ message: string; success: boolean }>('/recommendations/run', { method: 'POST', body: JSON.stringify(payload) }),
  reviewRecommendation: (id: string, payload: { status: 'APPROVED' | 'REJECTED'; reviewed_by: string; review_notes?: string }) =>
    request<Recommendation>(`/recommendations/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  exceptions: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
    request<Page<InventoryException>>(`/exceptions${queryString({ page: 1, page_size: 100, ...params })}`),
  resolveException: (id: string, resolved_by: string, resolution_notes?: string) =>
    request<InventoryException>(`/exceptions/${id}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ resolved_by, resolution_notes }),
    }),
}

export function formatCurrency(value: number | string | null | undefined): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatNumber(value: number | string | null | undefined, digits = 0): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(amount)
}
