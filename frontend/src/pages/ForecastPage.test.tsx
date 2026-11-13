import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api'
import type { Page, SKU, Store } from '../lib/types'
import { ForecastPage } from './OperationalPages'

vi.mock('../lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../lib/api')>()
  return {
    ...original,
    api: {
      stores: vi.fn(),
      skus: vi.fn(),
      sales: vi.fn(),
      forecasts: vi.fn(),
      evaluations: vi.fn(),
      runForecast: vi.fn(),
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

const sku: SKU = {
  id: 'sku-1',
  sku_code: 'SKU-001',
  name: 'Rice',
  category: 'Grocery',
  subcategory: null,
  unit_cost: 10,
  unit_price: 15,
  pack_size: 1,
  is_active: true,
}

function page<T>(items: T[], currentPage = 1, totalPages = 2): Page<T> {
  return {
    items,
    page: currentPage,
    page_size: 50,
    total: totalPages * 50,
    total_pages: totalPages,
  }
}

describe('ForecastPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.stores).mockResolvedValue(page([store]))
    vi.mocked(api.skus).mockImplementation(async (params = {}) => page([sku], Number(params.page ?? 1)))
    vi.mocked(api.sales).mockResolvedValue(page([]))
    vi.mocked(api.forecasts).mockResolvedValue(page([]))
    vi.mocked(api.evaluations).mockResolvedValue(page([{
      id: 1,
      sku_id: sku.id,
      store_id: store.id,
      model_name: 'moving_average',
      evaluation_date: '2026-01-01',
      horizon_days: 14,
      mae: 0,
      rmse: 0,
      wape: null,
      bias: 0,
      sample_size: 0,
    }]))
  })

  afterEach(() => {
    cleanup()
  })

  it('searches and paginates active SKUs and displays undefined WAPE as N/A', async () => {
    render(<ForecastPage />)

    await waitFor(() => {
      expect(api.skus).toHaveBeenCalledWith(expect.objectContaining({
        page: 1,
        page_size: 50,
        is_active: true,
      }))
    })
    await waitFor(() => expect(screen.getByText('N/A')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => {
      expect(api.skus).toHaveBeenCalledWith(expect.objectContaining({
        page: 2,
        page_size: 50,
        is_active: true,
      }))
    })

    fireEvent.change(screen.getByRole('textbox', { name: 'Search active SKUs by code or name' }), {
      target: { value: 'rice' },
    })
    await waitFor(() => {
      expect(api.skus).toHaveBeenCalledWith(expect.objectContaining({
        page: 1,
        search: 'rice',
      }))
    }, { timeout: 1000 })
  })
})
