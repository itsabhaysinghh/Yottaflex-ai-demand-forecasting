import * as Dialog from '@radix-ui/react-dialog'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Play,
  Search,
  X,
} from 'lucide-react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { toast } from 'sonner'
import { api, formatCurrency, formatNumber } from '../lib/api'
import type {
  Forecast,
  ForecastEvaluation,
  InventoryException,
  InventoryItem,
  Page,
  Recommendation,
  Sale,
  SKU,
  Store,
  Supplier,
  SupplierSKU,
} from '../lib/types'
import { Badge, Button, Card, EmptyState, ErrorState, Input, LoadingState, PageTitle, Select } from '../components/ui'

function TableFrame({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto"><table className="w-full border-collapse text-left text-sm">{children}</table></div>
}

function TableHead({ labels }: { labels: string[] }) {
  return <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500"><tr>{labels.map((label) => <th key={label} className="whitespace-nowrap px-4 py-3">{label}</th>)}</tr></thead>
}

function Pagination({ page, totalPages, total, onPage }: { page: number; totalPages: number; total: number; onPage: (page: number) => void }) {
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
      <p className="text-xs text-slate-500">{formatNumber(total)} records <span className="mx-1.5 text-slate-300">·</span> Page {page} of {totalPages}</p>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft size={15} /> Previous</Button>
        <Button size="sm" variant="outline" aria-label="Next page" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>Next <ChevronRight size={15} /></Button>
      </div>
    </div>
  )
}

function statusTone(value: string | null | undefined): 'good' | 'warning' | 'danger' | 'neutral' | 'info' {
  switch (value?.toUpperCase()) {
    case 'HEALTHY':
    case 'APPROVED':
    case 'RESOLVED':
    case 'ACTIVE':
      return 'good'
    case 'LOW':
    case 'PENDING':
    case 'MEDIUM':
      return 'warning'
    case 'STOCKOUT':
    case 'REJECTED':
    case 'CRITICAL':
    case 'HIGH':
      return 'danger'
    case 'UNKNOWN':
    case 'INACTIVE':
      return 'neutral'
    default:
      return 'info'
  }
}

export function InventoryPage() {
  const [data, setData] = useState<Page<InventoryItem> | null>(null)
  const [stores, setStores] = useState<Store[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [storeId, setStoreId] = useState('')
  const [sortBy, setSortBy] = useState('snapshot_date')
  const [sortOrder, setSortOrder] = useState('desc')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.inventory({
        page,
        page_size: 25,
        search,
        status: status || undefined,
        category: category || undefined,
        store_id: storeId || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      })
      setData(result)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load inventory.')
    } finally {
      setLoading(false)
    }
  }, [page, search, status, category, storeId, sortBy, sortOrder])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    void Promise.all([api.stores({ is_active: true }), api.skus()])
      .then(([storeResult, skuResult]) => {
        setStores(storeResult.items)
        setCategories([...new Set(skuResult.items.map((sku) => sku.category))].sort())
      })
      .catch((reason: unknown) => toast.error(reason instanceof Error ? reason.message : 'Unable to load inventory filters.'))
  }, [])

  const sortOptions = [
    ['snapshot_date', 'Snapshot date'],
    ['sku_code', 'SKU'],
    ['category', 'Category'],
    ['available_units', 'Available units'],
    ['incoming_units', 'Incoming units'],
    ['reorder_point', 'Reorder point'],
    ['inventory_status', 'Status'],
  ]

  return (
    <div>
      <PageTitle eyebrow="Operations" title="Inventory" description="Current stock positions, inbound supply, and policy thresholds across stores." />
      <Card className="mb-5 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(220px,1.5fr)_repeat(4,minmax(145px,1fr))_auto]">
          <label className="relative block">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input aria-label="Search inventory" placeholder="Search SKU or product…" className="pl-9" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} />
          </label>
          <Select aria-label="Filter by category" value={category} onChange={(event) => { setCategory(event.target.value); setPage(1) }}>
            <option value="">All categories</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </Select>
          <Select aria-label="Filter by store" value={storeId} onChange={(event) => { setStoreId(event.target.value); setPage(1) }}>
            <option value="">All stores</option>{stores.map((item) => <option key={item.id} value={item.id}>{item.store_code} · {item.name}</option>)}
          </Select>
          <Select aria-label="Filter by inventory status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
            <option value="">All statuses</option><option value="STOCKOUT">Stockout</option><option value="LOW">Low stock</option><option value="HEALTHY">Healthy</option><option value="UNKNOWN">Unknown</option>
          </Select>
          <Select aria-label="Sort inventory by" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            {sortOptions.map(([value, label]) => <option key={value} value={value}>Sort: {label}</option>)}
          </Select>
          <Button variant="outline" className="px-3" aria-label="Toggle sort order" onClick={() => setSortOrder((current) => current === 'asc' ? 'desc' : 'asc')}>
            {sortOrder === 'asc' ? <ArrowUp size={16} /> : <ArrowDown size={16} />}
          </Button>
        </div>
      </Card>
      <Card className="overflow-hidden">
        {loading ? <LoadingState label="Loading inventory…" /> : error ? <div className="p-4"><ErrorState message={error} onRetry={() => void load()} /></div> : data?.items.length ? (
          <>
            <TableFrame>
              <TableHead labels={['SKU / product', 'Category', 'Store', 'Available', 'Incoming', 'Reorder point', 'Safety stock', 'Status']} />
              <tbody className="divide-y divide-slate-100">
                {data.items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70">
                    <td className="whitespace-nowrap px-4 py-3"><p className="font-semibold text-slate-800">{item.sku_code ?? '—'}</p><p className="mt-0.5 max-w-48 truncate text-xs text-slate-500">{item.sku_name ?? 'Product'}</p></td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">{item.category ?? '—'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">{item.store_code ?? '—'}</td>
                    <td className="whitespace-nowrap px-4 py-3 font-medium tabular-nums text-slate-800">{formatNumber(item.available_units ?? item.closing_stock)}</td>
                    <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{formatNumber(item.in_transit_stock)}</td>
                    <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{item.reorder_point == null ? '—' : formatNumber(item.reorder_point)}</td>
                    <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{item.safety_stock_units == null ? '—' : formatNumber(item.safety_stock_units)}</td>
                    <td className="whitespace-nowrap px-4 py-3"><Badge tone={statusTone(item.inventory_status)}>{(item.inventory_status ?? 'UNKNOWN').replaceAll('_', ' ')}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </TableFrame>
            <Pagination page={data.page} totalPages={data.total_pages} total={data.total} onPage={setPage} />
          </>
        ) : <EmptyState title="No inventory matches" description="Try adjusting the search or filters, or check that inventory snapshots are available." />}
      </Card>
    </div>
  )
}

export function ForecastPage() {
  const [skus, setSkus] = useState<SKU[]>([])
  const [selectedSku, setSelectedSku] = useState<SKU | null>(null)
  const [skuSearch, setSkuSearch] = useState('')
  const [skuPage, setSkuPage] = useState(1)
  const [skuTotalPages, setSkuTotalPages] = useState(1)
  const [skuTotal, setSkuTotal] = useState(0)
  const [stores, setStores] = useState<Store[]>([])
  const [skuId, setSkuId] = useState('')
  const [storeId, setStoreId] = useState('')
  const [model, setModel] = useState('moving_average')
  const [horizon, setHorizon] = useState(14)
  const [sales, setSales] = useState<Sale[]>([])
  const [forecasts, setForecasts] = useState<Forecast[]>([])
  const [evaluations, setEvaluations] = useState<ForecastEvaluation[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void api.stores({ is_active: true })
      .then((result) => {
        setStores(result.items)
        setStoreId((current) => current || result.items[0]?.id || '')
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unable to load forecasting stores.'))
  }, [])

  useEffect(() => {
    let active = true
    const timeout = window.setTimeout(() => {
      void api.skus({
        page: skuPage,
        page_size: 50,
        is_active: true,
        search: skuSearch.trim() || undefined,
      })
        .then((result) => {
          if (!active) return
          setSkus(result.items)
          setSkuTotal(result.total)
          setSkuTotalPages(result.total_pages)
          const selected = result.items.find((item) => item.id === skuId)
          if (selected) setSelectedSku(selected)
          else if (!skuId && result.items[0]) {
            setSelectedSku(result.items[0])
            setSkuId(result.items[0].id)
          }
        })
        .catch((reason: unknown) => {
          if (active) setError(reason instanceof Error ? reason.message : 'Unable to load forecasting SKUs.')
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }, 200)
    return () => {
      active = false
      window.clearTimeout(timeout)
    }
  }, [skuPage, skuSearch, skuId])

  const loadPair = useCallback(async () => {
    if (!skuId || !storeId) return
    setLoading(true)
    setError(null)
    try {
      const [salesResult, forecastResult, evaluationResult] = await Promise.all([
        api.sales({ sku_id: skuId, store_id: storeId, page_size: 500 }),
        api.forecasts({ sku_id: skuId, store_id: storeId, page_size: 500 }),
        api.evaluations({ sku_id: skuId, store_id: storeId, model_name: model, page_size: 500 }),
      ])
      setSales(salesResult.items)
      setForecasts(forecastResult.items)
      setEvaluations(evaluationResult.items)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load forecast history.')
    } finally {
      setLoading(false)
    }
  }, [skuId, storeId, model])

  useEffect(() => { void loadPair() }, [loadPair])

  const evaluation = evaluations[0]
  const chartData = useMemo(() => {
    const points = new Map<string, { date: string; actual?: number; forecast?: number; lower?: number; upper?: number }>()
    sales.forEach((item) => points.set(item.sale_date, { date: item.sale_date, actual: item.units_sold }))
    forecasts.forEach((item) => {
      const point = points.get(item.target_date) ?? { date: item.target_date }
      point.forecast = Number(item.predicted_units)
      point.lower = item.confidence_lower == null ? undefined : Number(item.confidence_lower)
      point.upper = item.confidence_upper == null ? undefined : Number(item.confidence_upper)
      points.set(item.target_date, point)
    })
    return [...points.values()].sort((a, b) => a.date.localeCompare(b.date))
  }, [sales, forecasts])

  async function runForecast() {
    if (!skuId || !storeId || !Number.isInteger(horizon) || horizon < 1 || horizon > 90) {
      toast.error('Choose a SKU, store, and a forecast horizon from 1 to 90 days.')
      return
    }
    setRunning(true)
    try {
      const result = await api.runForecast({ sku_id: skuId, store_id: storeId, model_name: model, horizon_days: horizon })
      toast.success(result.message)
      await loadPair()
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : 'Forecast run failed.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <PageTitle eyebrow="Planning" title="Demand forecasting" description="Generate a forecast from persisted sales history and inspect backtest performance." />
      <Card className="mb-5 p-4">
        <div className="grid items-end gap-3 md:grid-cols-2 xl:grid-cols-[1.4fr_1.2fr_1fr_0.7fr_auto]">
          <label className="block text-xs font-medium text-slate-600">Find SKU
            <Input
              className="mt-1.5"
              aria-label="Search active SKUs by code or name"
              placeholder="Search SKU code or product name"
              value={skuSearch}
              onChange={(event) => { setSkuSearch(event.target.value); setSkuPage(1) }}
            />
            <Select
              className="mt-1.5"
              aria-label="Select SKU for forecasting"
              value={skuId}
              onChange={(event) => {
                const nextId = event.target.value
                setSkuId(nextId)
                setSelectedSku(skus.find((item) => item.id === nextId) ?? null)
              }}
              disabled={!skus.length}
            >
              {selectedSku && !skus.some((item) => item.id === selectedSku.id) && (
                <option value={selectedSku.id}>{selectedSku.sku_code} ? {selectedSku.name}</option>
              )}
              {skus.map((item) => <option key={item.id} value={item.id}>{item.sku_code} ? {item.name}</option>)}
            </Select>
            <span className="mt-1 flex items-center justify-between text-[11px] font-normal text-slate-500">
              <span>{formatNumber(skuTotal)} active SKUs ? page {skuPage} of {skuTotalPages}</span>
              <span className="flex gap-2">
                <button type="button" className="underline disabled:no-underline disabled:opacity-40" disabled={skuPage <= 1} onClick={() => setSkuPage((page) => page - 1)}>Previous</button>
                <button type="button" className="underline disabled:no-underline disabled:opacity-40" disabled={skuPage >= skuTotalPages} onClick={() => setSkuPage((page) => page + 1)}>Next</button>
              </span>
            </span>
          </label>
          <label className="block text-xs font-medium text-slate-600">Store
            <Select className="mt-1.5" value={storeId} onChange={(event) => setStoreId(event.target.value)} disabled={!stores.length}>
              {stores.map((item) => <option key={item.id} value={item.id}>{item.store_code} · {item.name}</option>)}
            </Select>
          </label>
          <label className="block text-xs font-medium text-slate-600">Forecast model
            <Select className="mt-1.5" value={model} onChange={(event) => setModel(event.target.value)}>
              <option value="moving_average">Moving average</option><option value="seasonal_naive">Seasonal naive</option><option value="exponential_smoothing">Exponential smoothing</option><option value="croston">Croston (intermittent)</option>
            </Select>
          </label>
          <label className="block text-xs font-medium text-slate-600">Horizon (days)
            <Input className="mt-1.5" type="number" min={1} max={90} value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} />
          </label>
          <Button onClick={() => void runForecast()} disabled={running || !skuId || !storeId} className="w-full"><Play size={15} />{running ? 'Running…' : 'Run forecast'}</Button>
        </div>
      </Card>

      {error && <div className="mb-5"><ErrorState message={error} onRetry={() => void loadPair()} /></div>}
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['MAE', evaluation ? formatNumber(evaluation.mae, 2) : '—', 'Mean absolute error'],
          ['RMSE', evaluation ? formatNumber(evaluation.rmse, 2) : '—', 'Root mean square error'],
          ['WAPE', evaluation?.wape == null ? 'N/A' : `${formatNumber(Number(evaluation.wape) * 100, 1)}%`, 'Undefined when actual demand is zero'],
          ['Bias', evaluation ? formatNumber(evaluation.bias, 2) : '—', 'Average forecast minus actual'],
        ].map(([label, value, note]) => (
          <Card key={label} className="p-4">
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
            <p className="mt-1 text-xs text-slate-500">{note}</p>
          </Card>
        ))}
      </div>
      <Card className="mb-5 p-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="text-sm font-semibold text-slate-900">Historical and forecast demand</h2><p className="mt-1 text-xs text-slate-500">Sales history and persisted projections for the selected SKU-store pair</p></div>
          <div className="flex flex-wrap gap-2"><Badge tone="info">Actual demand</Badge><Badge tone="good">Forecast</Badge><Badge>Confidence interval</Badge></div>
        </div>
        {loading ? <LoadingState label="Loading forecast history…" /> : chartData.length ? (
          <div className="h-[330px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="#eef2f6" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(value: string) => value.slice(5)} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} minTickGap={24} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip labelFormatter={(value) => String(value)} contentStyle={{ borderRadius: 10, borderColor: '#e2e8f0', fontSize: 12 }} />
                <Area type="monotone" dataKey={(point: { lower?: number; upper?: number }) => point.lower != null && point.upper != null ? [point.lower, point.upper] : undefined} name="Confidence interval" stroke="none" fill="#99f6e4" fillOpacity={0.45} connectNulls={false} />
                <Line type="monotone" dataKey="actual" name="Actual units" stroke="#64748b" strokeWidth={2} dot={false} connectNulls={false} />
                <Line type="monotone" dataKey="forecast" name="Predicted units" stroke="#0f766e" strokeWidth={2.5} dot={{ r: 2 }} connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : <EmptyState title="No history for this selection" description="Choose a SKU and store with sales records, then run a forecast." />}
      </Card>
      <Card className="overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">Latest forecast points</h2>
          <p className="mt-1 text-xs text-slate-500">{forecasts.length} persisted projections · {evaluation ? `evaluation sample size ${evaluation.sample_size}` : 'no evaluation metrics yet'}</p>
        </div>
        {forecasts.length ? (
          <TableFrame>
            <TableHead labels={['Target date', 'Model', 'Predicted units', 'Lower bound', 'Upper bound', 'Forecast date']} />
            <tbody className="divide-y divide-slate-100">{forecasts.slice(0, 25).map((item) => <tr key={item.id}><td className="px-4 py-3 text-slate-700">{item.target_date}</td><td className="px-4 py-3"><Badge tone="info">{item.model_name.replaceAll('_', ' ')}</Badge></td><td className="px-4 py-3 font-medium tabular-nums">{formatNumber(item.predicted_units, 2)}</td><td className="px-4 py-3 tabular-nums text-slate-500">{item.confidence_lower == null ? '—' : formatNumber(item.confidence_lower, 2)}</td><td className="px-4 py-3 tabular-nums text-slate-500">{item.confidence_upper == null ? '—' : formatNumber(item.confidence_upper, 2)}</td><td className="px-4 py-3 text-slate-500">{item.forecast_date}</td></tr>)}</tbody>
          </TableFrame>
        ) : <EmptyState title="No forecast saved yet" description="Choose a SKU, store, and model, then run the forecasting workflow." />}
      </Card>
    </div>
  )
}

function ReviewDialog({
  open,
  title,
  description,
  confirmLabel,
  destructive,
  busy,
  onOpenChange,
  onConfirm,
}: {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  destructive?: boolean
  busy?: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (reviewer: string, notes: string) => Promise<void>
}) {
  const [reviewer, setReviewer] = useState('')
  const [notes, setNotes] = useState('')
  useEffect(() => {
    if (open) { setReviewer(''); setNotes('') }
  }, [open])
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-32px)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-slate-200 bg-white p-5 shadow-xl focus:outline-none">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div><Dialog.Title className="text-base font-semibold text-slate-900">{title}</Dialog.Title><Dialog.Description className="mt-1 text-sm text-slate-500">{description}</Dialog.Description></div>
            <Dialog.Close asChild><button type="button" className="rounded-md p-1 text-slate-400 hover:bg-slate-100" aria-label="Close"><X size={17} /></button></Dialog.Close>
          </div>
          <label className="mb-3 block text-xs font-medium text-slate-600">Reviewer name <span className="text-rose-600">*</span>
            <Input className="mt-1.5" value={reviewer} minLength={2} maxLength={128} onChange={(event) => setReviewer(event.target.value)} placeholder="Enter your name" />
          </label>
          <label className="block text-xs font-medium text-slate-600">Review notes
            <textarea className="mt-1.5 min-h-20 w-full resize-y rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/10" maxLength={500} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Optional context for this decision" />
          </label>
          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild><Button variant="outline">Cancel</Button></Dialog.Close>
            <Button variant={destructive ? 'destructive' : 'default'} disabled={reviewer.trim().length < 2 || busy} onClick={() => void onConfirm(reviewer.trim(), notes.trim())}>{busy ? 'Saving…' : confirmLabel}</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function RecommendationsPage() {
  const [items, setItems] = useState<Recommendation[]>([])
  const [stores, setStores] = useState<Store[]>([])
  const [storeId, setStoreId] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reviewItem, setReviewItem] = useState<Recommendation | null>(null)
  const [reviewStatus, setReviewStatus] = useState<'APPROVED' | 'REJECTED'>('APPROVED')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.recommendations({ page_size: 500, status: status || undefined, store_id: storeId || undefined })
      setItems(result.items)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load recommendations.')
    } finally {
      setLoading(false)
    }
  }, [status, storeId])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    void api.stores({ is_active: true }).then((result) => setStores(result.items))
      .catch((reason: unknown) => toast.error(reason instanceof Error ? reason.message : 'Unable to load stores.'))
  }, [])

  async function run() {
    setRunning(true)
    try {
      const result = await api.runReplenishment({ store_id: storeId || undefined, enforce_capacity: true })
      toast.success(result.message)
      await load()
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : 'Replenishment run failed.')
    } finally {
      setRunning(false)
    }
  }

  async function submitReview(reviewer: string, notes: string) {
    if (!reviewItem) return
    setBusy(true)
    try {
      await api.reviewRecommendation(reviewItem.id, { status: reviewStatus, reviewed_by: reviewer, review_notes: notes || undefined })
      toast.success(`Recommendation ${reviewStatus.toLowerCase()}.`)
      setReviewItem(null)
      await load()
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : 'Unable to save recommendation review.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageTitle eyebrow="Planning" title="Replenishment" description="Explainable purchase proposals with supplier terms and review controls." actions={<Button onClick={() => void run()} disabled={running}><Play size={15} />{running ? 'Calculating…' : 'Run replenishment'}</Button>} />
      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs font-medium text-slate-600">Filter by store
            <Select className="mt-1.5" value={storeId} onChange={(event) => setStoreId(event.target.value)}><option value="">All stores</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.store_code} · {store.name}</option>)}</Select>
          </label>
          <label className="block text-xs font-medium text-slate-600">Recommendation status
            <Select className="mt-1.5" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option value="PENDING">Pending</option><option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option></Select>
          </label>
        </div>
      </Card>
      {error && <div className="mb-4"><ErrorState message={error} onRetry={() => void load()} /></div>}
      <Card className="overflow-hidden">
        {loading ? <LoadingState label="Loading recommendations…" /> : items.length ? (
          <TableFrame>
            <TableHead labels={['SKU', 'Store', 'Supplier', 'Inventory position', 'Lead-time demand', 'Safety stock', 'Reorder point', 'Order qty', 'MOQ / pack', 'Est. value', 'Status', 'Review']} />
            <tbody className="divide-y divide-slate-100">
              {items.map((item) => (
                <tr key={item.id} className="align-top hover:bg-slate-50/70">
                  <td className="min-w-40 px-4 py-3"><p className="font-semibold text-slate-800">{item.sku_code}</p><p className="mt-0.5 max-w-40 truncate text-xs text-slate-500">{item.sku_name}</p></td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{item.store_code}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{item.supplier_name ?? '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-700">{formatNumber(item.net_inventory_position)}<p className="mt-0.5 text-[11px] text-slate-400">On hand {formatNumber(item.current_on_hand)} · inbound {formatNumber(item.current_on_order)}</p></td>
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{formatNumber(item.lead_time_demand, 1)}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">{formatNumber(item.safety_stock)}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">{formatNumber(item.reorder_point)}</td>
                  <td className="px-4 py-3 font-semibold tabular-nums text-teal-800">{formatNumber(item.recommended_units)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs tabular-nums text-slate-600">{item.minimum_order_quantity ?? '—'} / {item.pack_size ?? '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3 font-medium tabular-nums text-slate-800">{formatCurrency(item.total_cost)}</td>
                  <td className="whitespace-nowrap px-4 py-3"><Badge tone={statusTone(item.status)}>{item.status}</Badge></td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {item.status === 'PENDING' ? <div className="flex gap-1">
                      <Button size="sm" variant="outline" title="Approve recommendation" onClick={() => { setReviewStatus('APPROVED'); setReviewItem(item) }}><Check size={14} /></Button>
                      <Button size="sm" variant="outline" title="Reject recommendation" onClick={() => { setReviewStatus('REJECTED'); setReviewItem(item) }}><X size={14} /></Button>
                    </div> : <span className="text-xs text-slate-400">{item.reviewed_by ?? 'Reviewed'}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableFrame>
        ) : !error ? <EmptyState title="No recommendations found" description="Run replenishment to calculate purchase proposals from current inventory and demand." /> : null}
      </Card>
      <Card className="mt-5 p-5">
        <div className="mb-3 flex items-center gap-2"><ClipboardCheck size={17} className="text-teal-700" /><h2 className="text-sm font-semibold text-slate-900">Why this order?</h2></div>
        <p className="text-sm leading-6 text-slate-600">Recommendations include an engine-generated explanation describing the reorder trigger and any quantity constraints. Open a row’s explanation below to review the calculation; approval and rejection are recorded through the backend review workflow.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {items.slice(0, 4).map((item) => (
            <details key={item.id} className="group rounded-lg border border-slate-200 p-3">
              <summary className="cursor-pointer list-none text-xs font-semibold text-slate-700">{item.sku_code} · {item.store_code} <span className="float-right text-slate-400 group-open:rotate-180">⌄</span></summary>
              <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap break-words rounded-md bg-slate-50 p-3 text-[11px] leading-5 text-slate-600">{JSON.stringify(item.explanation, null, 2)}</pre>
            </details>
          ))}
        </div>
      </Card>
      <ReviewDialog open={Boolean(reviewItem)} title={reviewStatus === 'APPROVED' ? 'Approve recommendation' : 'Reject recommendation'} description={reviewItem ? `${reviewItem.sku_code} · ${reviewItem.store_code} · ${formatNumber(reviewItem.recommended_units)} units` : ''} confirmLabel={reviewStatus === 'APPROVED' ? 'Approve order' : 'Reject order'} destructive={reviewStatus === 'REJECTED'} busy={busy} onOpenChange={(open) => { if (!open) setReviewItem(null) }} onConfirm={submitReview} />
    </div>
  )
}

export function ExceptionsPage() {
  const [items, setItems] = useState<InventoryException[]>([])
  const [severity, setSeverity] = useState('')
  const [resolved, setResolved] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [active, setActive] = useState<InventoryException | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.exceptions({
        page_size: 100,
        severity: severity || undefined,
        is_resolved: resolved === '' ? undefined : resolved === 'true',
      })
      setItems(result.items)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load exceptions.')
    } finally {
      setLoading(false)
    }
  }, [severity, resolved])

  useEffect(() => { void load() }, [load])

  async function resolve(reviewer: string, notes: string) {
    if (!active) return
    setBusy(true)
    try {
      await api.resolveException(active.id, reviewer, notes || undefined)
      toast.success('Exception marked as resolved.')
      setActive(null)
      await load()
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : 'Unable to resolve exception.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageTitle eyebrow="Risk management" title="Exceptions" description="Monitor inventory and data-quality signals and track resolution status." />
      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs font-medium text-slate-600">Severity
            <Select className="mt-1.5" value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="">All severities</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></Select>
          </label>
          <label className="block text-xs font-medium text-slate-600">Resolution
            <Select className="mt-1.5" value={resolved} onChange={(event) => setResolved(event.target.value)}><option value="">All exceptions</option><option value="false">Open</option><option value="true">Resolved</option></Select>
          </label>
        </div>
      </Card>
      {error && <div className="mb-4"><ErrorState message={error} onRetry={() => void load()} /></div>}
      <Card className="overflow-hidden">
        {loading ? <LoadingState label="Loading exceptions…" /> : items.length ? (
          <TableFrame>
            <TableHead labels={['Exception type', 'SKU', 'Store', 'Severity', 'Description', 'Detected', 'Resolution', 'Action']} />
            <tbody className="divide-y divide-slate-100">{items.map((item) => (
              <tr key={item.id} className="hover:bg-slate-50/70">
                <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-800">{item.exception_type.replaceAll('_', ' ')}</td>
                <td className="px-4 py-3 text-slate-600">{item.sku_code ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600">{item.store_code ?? '—'}</td>
                <td className="px-4 py-3"><Badge tone={statusTone(item.severity)}>{item.severity}</Badge></td>
                <td className="min-w-64 max-w-lg px-4 py-3 text-xs leading-5 text-slate-600">{item.description}</td>
                <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">{new Date(item.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3"><Badge tone={item.is_resolved ? 'good' : 'warning'}>{item.is_resolved ? 'Resolved' : 'Open'}</Badge></td>
                <td className="px-4 py-3">{!item.is_resolved && <Button size="sm" variant="outline" onClick={() => setActive(item)}>Resolve</Button>}</td>
              </tr>
            ))}</tbody>
          </TableFrame>
        ) : !error ? <EmptyState title="No exceptions match" description="Try another severity or resolution filter." /> : null}
      </Card>
      <ReviewDialog open={Boolean(active)} title="Resolve exception" description={active ? `${active.exception_type.replaceAll('_', ' ')} · ${active.sku_code ?? 'Network'}` : ''} confirmLabel="Mark resolved" busy={busy} onOpenChange={(open) => { if (!open) setActive(null) }} onConfirm={resolve} />
    </div>
  )
}

export function CatalogPage({ kind }: { kind: 'skus' | 'suppliers' }) {
  const [skus, setSkus] = useState<SKU[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [supplierItems, setSupplierItems] = useState<SupplierSKU[]>([])
  const [skuPageInfo, setSkuPageInfo] = useState<Page<SKU> | null>(null)
  const [selectedSku, setSelectedSku] = useState<SKU | null>(null)
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null)
  const [search, setSearch] = useState('')
  const [skuPage, setSkuPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (kind === 'skus') {
        const result = await api.skus({ page: skuPage, page_size: 50, search: search || undefined })
        setSkus(result.items)
        setSkuPageInfo(result)
        setSelectedSku((current) => result.items.find((sku) => sku.id === current?.id) ?? result.items[0] ?? null)
      } else {
        const result = await api.suppliers({ page_size: 500, search: search || undefined })
        setSuppliers(result.items)
        setSelectedSupplier((current) => result.items.find((supplier) => supplier.id === current?.id) ?? result.items[0] ?? null)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load catalog.')
    } finally {
      setLoading(false)
    }
  }, [kind, search, skuPage])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (kind !== 'suppliers' || !selectedSupplier) { setSupplierItems([]); return }
    void api.supplierSkus(selectedSupplier.id).then((result) => setSupplierItems(result.items))
      .catch((reason: unknown) => toast.error(reason instanceof Error ? reason.message : 'Unable to load supplier assortment.'))
  }, [kind, selectedSupplier])

  const title = kind === 'skus' ? 'SKU catalog' : 'Supplier network'

  return (
    <div>
      <PageTitle eyebrow="Master data" title={title} description={kind === 'skus' ? 'Browse products, categories, and unit economics.' : 'Review supplier relationships, reliability, and contracted assortment.'} />
      <div className="mb-4 max-w-md">
        <label className="relative block">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input aria-label={`Search ${kind}`} className="pl-9" placeholder={kind === 'skus' ? 'Search SKU or product…' : 'Search supplier…'} value={search} onChange={(event) => { setSearch(event.target.value); setSkuPage(1) }} />
        </label>
      </div>
      {error && <div className="mb-4"><ErrorState message={error} onRetry={() => void load()} /></div>}
      {loading ? <Card><LoadingState label={`Loading ${kind}…`} /></Card> : kind === 'skus' ? (
        <div className="grid gap-5 xl:grid-cols-[1.45fr_0.8fr]">
          <Card className="overflow-hidden">
            {skus.length ? <><TableFrame><TableHead labels={['SKU', 'Product', 'Category', 'Unit cost', 'Unit price', 'Pack size', 'Status']} /><tbody className="divide-y divide-slate-100">{skus.map((sku) => <tr key={sku.id} onClick={() => setSelectedSku(sku)} className={`cursor-pointer ${sku.id === selectedSku?.id ? 'bg-teal-50/60' : 'hover:bg-slate-50'}`}><td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-800">{sku.sku_code}</td><td className="min-w-40 px-4 py-3 text-slate-700">{sku.name}</td><td className="px-4 py-3 text-slate-600">{sku.category}</td><td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{formatCurrency(sku.unit_cost)}</td><td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{formatCurrency(sku.unit_price)}</td><td className="px-4 py-3 tabular-nums text-slate-600">{sku.pack_size}</td><td className="px-4 py-3"><Badge tone={sku.is_active ? 'good' : 'neutral'}>{sku.is_active ? 'Active' : 'Inactive'}</Badge></td></tr>)}</tbody></TableFrame>{skuPageInfo && <Pagination page={skuPageInfo.page} totalPages={skuPageInfo.total_pages} total={skuPageInfo.total} onPage={setSkuPage} />}</> : <EmptyState title="No products found" description="Try a different search term." />}
          </Card>
          <Card className="h-fit p-5">
            {selectedSku ? <><div className="mb-4 flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-teal-700">Product details</p><h2 className="mt-1 text-lg font-semibold text-slate-900">{selectedSku.name}</h2><p className="mt-1 text-sm text-slate-500">{selectedSku.sku_code}</p></div><Badge tone={selectedSku.is_active ? 'good' : 'neutral'}>{selectedSku.is_active ? 'Active' : 'Inactive'}</Badge></div><dl className="grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 text-sm"><Detail label="Category" value={selectedSku.category} /><Detail label="Subcategory" value={selectedSku.subcategory ?? '—'} /><Detail label="Unit cost" value={formatCurrency(selectedSku.unit_cost)} /><Detail label="Unit price" value={formatCurrency(selectedSku.unit_price)} /><Detail label="Pack size" value={`${selectedSku.pack_size} units`} /><Detail label="SKU ID" value={selectedSku.id} /></dl><p className="mt-5 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">Product records are read-only here; catalog changes are not exposed by the current API.</p></> : <EmptyState title="Select a product" description="Choose a SKU to view its master data." />}
          </Card>
        </div>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
          <Card className="overflow-hidden">
            {suppliers.length ? <TableFrame><TableHead labels={['Supplier', 'Lead time', 'Reliability', 'Contact', 'Status']} /><tbody className="divide-y divide-slate-100">{suppliers.map((supplier) => <tr key={supplier.id} onClick={() => setSelectedSupplier(supplier)} className={`cursor-pointer ${supplier.id === selectedSupplier?.id ? 'bg-teal-50/60' : 'hover:bg-slate-50'}`}><td className="px-4 py-3"><p className="font-semibold text-slate-800">{supplier.supplier_code}</p><p className="mt-0.5 text-xs text-slate-500">{supplier.name}</p></td><td className="whitespace-nowrap px-4 py-3 text-slate-600">{supplier.default_lead_time_days} days</td><td className="px-4 py-3 tabular-nums text-slate-600">{formatNumber(Number(supplier.reliability_score) * 100, 1)}%</td><td className="px-4 py-3 text-xs text-slate-500">{supplier.contact_email ?? '—'}</td><td className="px-4 py-3"><Badge tone={supplier.is_active ? 'good' : 'neutral'}>{supplier.is_active ? 'Active' : 'Inactive'}</Badge></td></tr>)}</tbody></TableFrame> : <EmptyState title="No suppliers found" description="Try a different search term." />}
          </Card>
          <Card className="h-fit overflow-hidden">
            {selectedSupplier ? <><div className="border-b border-slate-100 p-5"><p className="text-xs font-semibold uppercase tracking-wider text-teal-700">Supplier profile</p><h2 className="mt-1 text-lg font-semibold text-slate-900">{selectedSupplier.name}</h2><p className="mt-1 text-sm text-slate-500">{selectedSupplier.supplier_code} · {selectedSupplier.contact_email ?? 'No contact email'}</p><div className="mt-4 flex gap-2"><Badge tone={selectedSupplier.is_active ? 'good' : 'neutral'}>{selectedSupplier.is_active ? 'Active' : 'Inactive'}</Badge><Badge tone="info">{selectedSupplier.default_lead_time_days} day default lead</Badge><Badge>Reliability {formatNumber(Number(selectedSupplier.reliability_score) * 100, 1)}%</Badge></div></div><div className="p-5"><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-800">Contracted assortment</h3><span className="text-xs text-slate-400">{supplierItems.length} SKUs</span></div>{supplierItems.length ? <div className="space-y-2">{supplierItems.map((item) => <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2.5"><div><p className="text-xs font-semibold text-slate-700">{item.sku_code ?? item.sku_id.slice(0, 8)} {item.is_primary && <span className="ml-1 text-[10px] font-medium text-teal-700">PRIMARY</span>}</p><p className="mt-1 text-[11px] text-slate-500">{item.contract_lead_time_days} day lead · MOQ {item.minimum_order_quantity} · pack {item.pack_size}</p></div><span className="text-xs font-medium tabular-nums text-slate-700">{formatCurrency(item.unit_cost)}</span></div>)}</div> : <EmptyState title="No supplier SKUs" description="No contracted assortment is linked to this supplier." />}</div></> : <EmptyState title="Select a supplier" description="Choose a supplier to inspect contracted products." />}
          </Card>
        </div>
      )}
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 truncate text-sm font-medium text-slate-800">{value}</dd></div>
}
