import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Boxes,
  CircleDollarSign,
  PackageCheck,
  PackageSearch,
  ShieldCheck,
  Store,
  Target,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, formatCurrency, formatNumber } from '../lib/api'
import type { DashboardTrends, InventoryException, Overview, Recommendation } from '../lib/types'
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, PageTitle } from '../components/ui'

const chartColors = ['#0f766e', '#38bdf8', '#818cf8', '#f59e0b', '#fb7185', '#94a3b8']
const metricIconClasses: Record<string, string> = {
  teal: 'bg-teal-50 text-teal-700',
  blue: 'bg-sky-50 text-sky-700',
  violet: 'bg-violet-50 text-violet-700',
  rose: 'bg-rose-50 text-rose-700',
  amber: 'bg-amber-50 text-amber-700',
  green: 'bg-emerald-50 text-emerald-700',
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [trends, setTrends] = useState<DashboardTrends | null>(null)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [exceptions, setExceptions] = useState<InventoryException[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [metrics, trendData, recs, excs] = await Promise.all([
        api.overview(),
        api.trends(30),
        api.recommendations({ status: 'PENDING', page_size: 5 }),
        api.exceptions({ is_resolved: false, page_size: 5 }),
      ])
      setOverview(metrics)
      setTrends(trendData)
      setRecommendations(recs.items)
      setExceptions(excs.items)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load dashboard data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  if (loading) return <LoadingState label="Loading portfolio intelligence…" />
  if (error || !overview || !trends) return <ErrorState message={error ?? 'Dashboard data is unavailable.'} onRetry={() => void load()} />

  const metrics = [
    { label: 'Total SKUs', value: formatNumber(overview.total_skus), note: 'In product catalog', icon: Boxes, tone: 'teal' },
    { label: 'Active stores', value: formatNumber(overview.active_stores_count), note: `${formatNumber(overview.total_stores)} total locations`, icon: Store, tone: 'blue' },
    { label: 'Inventory value', value: formatCurrency(overview.total_inventory_valuation), note: `${formatNumber(overview.total_inventory_units)} units on hand`, icon: CircleDollarSign, tone: 'violet' },
    { label: 'Stockouts', value: formatNumber(overview.active_stockouts_count), note: 'Across current inventory', icon: AlertTriangle, tone: 'rose' },
    { label: 'Low-stock products', value: formatNumber(overview.low_stock_products_count), note: 'At or below reorder point', icon: PackageSearch, tone: 'amber' },
    { label: 'Pending orders', value: formatNumber(overview.pending_recommendations_count), note: 'Awaiting planner review', icon: PackageCheck, tone: 'blue' },
    { label: 'Forecast accuracy', value: overview.forecast_accuracy_pct == null ? '—' : `${formatNumber(overview.forecast_accuracy_pct, 1)}%`, note: 'Latest evaluation window', icon: Target, tone: 'teal' },
    { label: 'Inventory health', value: overview.inventory_health_pct == null ? '—' : `${formatNumber(overview.inventory_health_pct, 1)}%`, note: 'Among positions with a known status', icon: ShieldCheck, tone: 'green' },
  ] as const

  const demand = trends.demand_trend.map((point) => ({ ...point, label: point.date.slice(5) }))
  const stockouts = trends.stockout_trend.map((point) => ({ ...point, label: point.date.slice(5) }))
  const distribution = trends.inventory_distribution.filter((item) => item.units > 0)

  return (
    <div>
      <PageTitle
        eyebrow="Portfolio overview"
        title="Inventory intelligence"
        description="A clear view of demand, inventory risk, and replenishment decisions across your network."
        actions={<Button variant="outline" onClick={() => void load()}>Refresh data</Button>}
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ label, value, note, icon: Icon, tone }) => (
          <Card key={label} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-slate-500">{label}</p>
                <p className="mt-2 text-[26px] font-semibold leading-none tracking-tight text-slate-950">{value}</p>
              </div>
              <span className={`grid size-9 place-items-center rounded-lg ${metricIconClasses[tone]}`}>
                <Icon size={18} strokeWidth={1.8} />
              </span>
            </div>
            <p className="mt-3 text-xs text-slate-500">{note}</p>
          </Card>
        ))}
      </div>

      <div className="mb-5 grid gap-5 xl:grid-cols-[1.45fr_1fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Demand trend</h2>
              <p className="mt-1 text-xs text-slate-500">Daily units sold · last 30 days</p>
            </div>
            <Badge tone="info">Sales history</Badge>
          </div>
          {demand.length ? (
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={demand} margin={{ top: 8, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="demandFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#0f766e" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#0f766e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#eef2f6" vertical={false} />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} minTickGap={22} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: 10, borderColor: '#e2e8f0', fontSize: 12 }} />
                  <Area type="monotone" dataKey="value" name="Units sold" stroke="#0f766e" strokeWidth={2.5} fill="url(#demandFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyState title="No demand history" description="Sales data will appear here when available." />}
        </Card>

        <Card className="p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-slate-900">Inventory by category</h2>
            <p className="mt-1 text-xs text-slate-500">Units in the latest snapshot</p>
          </div>
          {distribution.length ? (
            <>
              <div className="h-[218px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={distribution} dataKey="units" nameKey="category" innerRadius={62} outerRadius={88} paddingAngle={3} stroke="white" strokeWidth={3}>
                      {distribution.map((item, index) => <Cell key={item.category} fill={chartColors[index % chartColors.length]} />)}
                    </Pie>
                    <Tooltip formatter={(value) => [formatNumber(Number(value)), 'Units']} contentStyle={{ borderRadius: 10, borderColor: '#e2e8f0', fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-2">
                {distribution.slice(0, 6).map((item, index) => (
                  <div key={item.category} className="flex min-w-0 items-center gap-2 text-xs">
                    <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: chartColors[index % chartColors.length] }} />
                    <span className="truncate text-slate-500">{item.category}</span>
                    <span className="ml-auto font-medium text-slate-800">{formatNumber(item.units)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <EmptyState title="No inventory distribution" description="Inventory data will appear once snapshots are available." />}
        </Card>
      </div>

      <div className="mb-5 grid gap-5 xl:grid-cols-2">
        <Card className="p-5">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Stockout trend</h2>
              <p className="mt-1 text-xs text-slate-500">Stockout-flagged positions by day</p>
            </div>
            {overview.active_stockouts_count > 0
              ? <Badge tone="danger">{overview.active_stockouts_count} active</Badge>
              : <Badge tone="good">No active stockouts</Badge>}
          </div>
          {stockouts.length ? (
            <div className="h-[210px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stockouts} margin={{ top: 8, right: 4, bottom: 0, left: -20 }}>
                  <CartesianGrid stroke="#eef2f6" vertical={false} />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} minTickGap={22} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: 10, borderColor: '#e2e8f0', fontSize: 12 }} />
                  <Area type="monotone" dataKey="value" name="Stockouts" stroke="#e11d48" strokeWidth={2} fill="#ffe4e6" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyState title="No stockout history" description="Stockout signals will be shown when snapshots are available." />}
        </Card>
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Store capacity</h2>
              <p className="mt-1 text-xs text-slate-500">Latest on-hand units against warehouse limits</p>
            </div>
            <span className="text-xs font-medium text-slate-400">{overview.store_capacities.length} stores</span>
          </div>
          <div className="max-h-[210px] space-y-4 overflow-auto pr-1">
            {overview.store_capacities.slice(0, 6).map((store) => (
              <div key={store.store_code}>
                <div className="mb-1.5 flex justify-between text-xs">
                  <span className="font-medium text-slate-700">{store.store_code} <span className="font-normal text-slate-400">· {store.name}</span></span>
                  <span className="tabular-nums text-slate-500">{formatNumber(store.utilization_pct, 1)}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div className={`h-full rounded-full ${store.utilization_pct >= 90 ? 'bg-amber-500' : 'bg-teal-600'}`} style={{ width: `${Math.min(100, Math.max(0, store.utilization_pct))}%` }} />
                </div>
              </div>
            ))}
            {!overview.store_capacities.length && <EmptyState title="No store data" description="Store capacity data is not available." />}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Recent exceptions</h2>
              <p className="mt-1 text-xs text-slate-500">Open signals that may need attention</p>
            </div>
            <ArrowDownRight className="text-slate-400" size={17} />
          </div>
          {exceptions.length ? (
            <div className="divide-y divide-slate-100">
              {exceptions.slice(0, 4).map((item) => (
                <div key={item.id} className="flex items-start gap-3 px-5 py-3.5">
                  <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${item.severity.toUpperCase() === 'CRITICAL' || item.severity.toUpperCase() === 'HIGH' ? 'bg-rose-50 text-rose-600' : 'bg-amber-50 text-amber-700'}`}>
                    <AlertTriangle size={15} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-slate-800">{item.exception_type.replaceAll('_', ' ')}</span>
                      <Badge tone={item.severity.toUpperCase() === 'CRITICAL' || item.severity.toUpperCase() === 'HIGH' ? 'danger' : 'warning'}>{item.severity}</Badge>
                    </div>
                    <p className="mt-1 truncate text-xs text-slate-500">{item.sku_code ?? 'Network'}{item.store_code ? ` · ${item.store_code}` : ''} — {item.description}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : <EmptyState title="All clear" description="No unresolved inventory exceptions." />}
        </Card>

        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Purchase recommendations</h2>
              <p className="mt-1 text-xs text-slate-500">Pending planner decisions</p>
            </div>
            <ArrowUpRight className="text-slate-400" size={17} />
          </div>
          {recommendations.length ? (
            <div className="divide-y divide-slate-100">
              {recommendations.slice(0, 4).map((item) => (
                <div key={item.id} className="flex items-center gap-3 px-5 py-3.5">
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-teal-50 text-teal-700"><PackageCheck size={16} /></span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-slate-800">{item.sku_code} · {item.sku_name ?? 'Product'}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.store_code} · {item.supplier_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold tabular-nums text-slate-800">{formatNumber(item.recommended_units)} units</p>
                    <p className="mt-1 text-xs text-slate-500">{formatCurrency(item.total_cost)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : <EmptyState title="No pending orders" description="New recommendations will appear here after replenishment runs." />}
        </Card>
      </div>
    </div>
  )
}
