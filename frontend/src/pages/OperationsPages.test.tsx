import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api'
import type {
  InventoryException,
  Overview,
  Page,
  Recommendation,
  Store,
} from '../lib/types'
import DashboardPage from './DashboardPage'
import { ExceptionsPage, RecommendationsPage } from './OperationalPages'

vi.mock('../lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../lib/api')>()
  return {
    ...original,
    api: {
      overview: vi.fn(),
      trends: vi.fn(),
      recommendations: vi.fn(),
      exceptions: vi.fn(),
      stores: vi.fn(),
      correctRecommendation: vi.fn(),
      reviewRecommendation: vi.fn(),
      resolveException: vi.fn(),
    },
  }
})

const store: Store = {
  id: 'store-1',
  store_code: 'STR-001',
  name: 'Central',
  store_type: 'RETAIL',
  warehouse_capacity_units: 1000,
  is_active: true,
}

const recommendation: Recommendation = {
  id: 'recommendation-1',
  sku_id: 'sku-1',
  store_id: store.id,
  supplier_id: 'supplier-1',
  recommendation_date: '2026-01-01',
  current_on_hand: 5,
  current_on_order: 0,
  net_inventory_position: 5,
  lead_time_demand: 10,
  safety_stock: 2,
  reorder_point: 12,
  raw_order_quantity: 7,
  recommended_units: 8,
  total_cost: 80,
  status: 'PENDING',
  explanation: {},
  reviewed_by: null,
  reviewed_at: null,
  review_notes: null,
  sku_code: 'SKU-001',
  sku_name: 'Rice',
  store_code: store.store_code,
  supplier_name: 'Supplier One',
  minimum_order_quantity: 4,
  pack_size: 4,
}

const exception: InventoryException = {
  id: 'exception-1',
  sku_id: 'sku-1',
  store_id: store.id,
  exception_type: 'LOW_STOCK',
  severity: 'CRITICAL',
  description: 'Stock is below the reorder point.',
  payload: {},
  is_resolved: false,
  created_at: '2026-01-01T00:00:00Z',
  resolved_at: null,
  sku_code: 'SKU-001',
  store_code: store.store_code,
}

const overview: Overview = {
  total_skus: 1,
  total_stores: 1,
  total_suppliers: 1,
  total_inventory_units: 5,
  total_inventory_valuation: 50,
  active_stockouts_count: 0,
  pending_recommendations_count: 0,
  critical_exceptions_count: 0,
  active_stores_count: 1,
  low_stock_products_count: 0,
  forecast_accuracy_pct: null,
  inventory_health_pct: null,
  categories: [],
  store_capacities: [],
}

function page<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, page_size: 100, total_pages: 1 }
}

describe('dashboard and operational pages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.trends).mockResolvedValue({
      demand_trend: [],
      stockout_trend: [],
      inventory_distribution: [],
    })
    vi.mocked(api.recommendations).mockResolvedValue(page([]))
    vi.mocked(api.exceptions).mockResolvedValue(page([]))
    vi.mocked(api.stores).mockResolvedValue(page([store]))
    vi.mocked(api.correctRecommendation).mockResolvedValue(recommendation)
    vi.mocked(api.reviewRecommendation).mockResolvedValue(recommendation)
    vi.mocked(api.resolveException).mockResolvedValue(exception)
  })

  afterEach(() => {
    cleanup()
  })

  it('shows dashboard API errors and recovers when the user retries', async () => {
    vi.mocked(api.overview)
      .mockRejectedValueOnce(new Error('Backend unavailable'))
      .mockResolvedValueOnce(overview)

    render(<DashboardPage />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Backend unavailable')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    expect(await screen.findByRole('heading', { name: 'Inventory intelligence' })).toBeTruthy()
    expect(await screen.findByText('No demand history')).toBeTruthy()
    expect(api.overview).toHaveBeenCalledTimes(2)
  })

  it('requires a planner name before approving a recommendation', async () => {
    vi.mocked(api.recommendations).mockResolvedValue(page([recommendation]))

    render(<RecommendationsPage />)

    fireEvent.click(await screen.findByTitle('Approve recommendation'))
    const approveButton = await screen.findByRole('button', { name: 'Approve order' })
    expect(approveButton.hasAttribute('disabled')).toBe(true)

    fireEvent.change(screen.getByLabelText(/Reviewer name/), {
      target: { value: 'Planner One' },
    })
    expect(approveButton.hasAttribute('disabled')).toBe(false)
    fireEvent.click(approveButton)

    await waitFor(() => {
      expect(api.reviewRecommendation).toHaveBeenCalledWith(recommendation.id, {
        status: 'APPROVED',
        reviewed_by: 'Planner One',
        review_notes: undefined,
      })
    })
  })

  it('offers an audited correction path for capacity-flagged recommendations', async () => {
    const flaggedRecommendation: Recommendation = {
      ...recommendation,
      status: 'FLAGGED_EXCEPTION',
      explanation: {
        warehouse_capacity_check: { capacity_breached: true },
      },
    }
    vi.mocked(api.recommendations).mockResolvedValue(page([flaggedRecommendation]))

    render(<RecommendationsPage />)

    fireEvent.click(await screen.findByTitle('Correct capacity-flagged recommendation'))
    await screen.findByRole('dialog')
    fireEvent.change(screen.getByLabelText('Corrected quantity'), { target: { value: '8' } })
    fireEvent.change(screen.getByLabelText('Correction planner name'), { target: { value: 'Planner One' } })
    fireEvent.change(screen.getByLabelText('Correction notes'), { target: { value: 'Fits remaining capacity.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create corrected replacement' }))

    await waitFor(() => {
      expect(api.correctRecommendation).toHaveBeenCalledWith(flaggedRecommendation.id, {
        recommended_units: 8,
        corrected_by: 'Planner One',
        correction_notes: 'Fits remaining capacity.',
      })
    })
  })

  it('shows open exceptions and exposes the resolution workflow without changing records', async () => {
    vi.mocked(api.exceptions).mockResolvedValue(page([exception]))

    render(<ExceptionsPage />)

    expect(await screen.findByText('Stock is below the reorder point.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Resolve' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog.textContent).toContain('Resolve exception')
    expect(api.resolveException).not.toHaveBeenCalled()
  })
})
