import { Suspense, lazy, useState } from 'react'
import {
  AlertTriangle,
  Boxes,
  ChevronDown,
  Command,
  LayoutDashboard,
  Menu,
  PackageCheck,
  Search,
  Truck,
  X,
} from 'lucide-react'
import { Toaster } from 'sonner'
import { Button, LoadingState } from './components/ui'

const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const InventoryPage = lazy(() => import('./pages/OperationalPages').then((module) => ({ default: module.InventoryPage })))
const ForecastPage = lazy(() => import('./pages/OperationalPages').then((module) => ({ default: module.ForecastPage })))
const RecommendationsPage = lazy(() => import('./pages/OperationalPages').then((module) => ({ default: module.RecommendationsPage })))
const ExceptionsPage = lazy(() => import('./pages/OperationalPages').then((module) => ({ default: module.ExceptionsPage })))
const SkuCatalogPage = lazy(() => import('./pages/OperationalPages').then((module) => ({ default: () => <module.CatalogPage kind="skus" /> })))
const SupplierCatalogPage = lazy(() => import('./pages/OperationalPages').then((module) => ({ default: () => <module.CatalogPage kind="suppliers" /> })))

type PageKey = 'overview' | 'inventory' | 'forecast' | 'replenishment' | 'exceptions' | 'skus' | 'suppliers'

const navigation: { label: string; key: PageKey; icon: typeof LayoutDashboard; section: string }[] = [
  { label: 'Overview', key: 'overview', icon: LayoutDashboard, section: 'Workspace' },
  { label: 'Inventory', key: 'inventory', icon: Boxes, section: 'Workspace' },
  { label: 'Forecasting', key: 'forecast', icon: Search, section: 'Planning' },
  { label: 'Replenishment', key: 'replenishment', icon: PackageCheck, section: 'Planning' },
  { label: 'Exceptions', key: 'exceptions', icon: AlertTriangle, section: 'Planning' },
  { label: 'SKU catalog', key: 'skus', icon: Boxes, section: 'Master data' },
  { label: 'Suppliers', key: 'suppliers', icon: Truck, section: 'Master data' },
]

const pageTitles: Record<PageKey, string> = {
  overview: 'Overview',
  inventory: 'Inventory',
  forecast: 'Demand forecasting',
  replenishment: 'Replenishment',
  exceptions: 'Exceptions',
  skus: 'SKU catalog',
  suppliers: 'Suppliers',
}

function PageContent({ page }: { page: PageKey }) {
  switch (page) {
    case 'inventory': return <InventoryPage />
    case 'forecast': return <ForecastPage />
    case 'replenishment': return <RecommendationsPage />
    case 'exceptions': return <ExceptionsPage />
    case 'skus': return <SkuCatalogPage />
    case 'suppliers': return <SupplierCatalogPage />
    default: return <DashboardPage />
  }
}

export default function App() {
  const [page, setPage] = useState<PageKey>('overview')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  function navigate(next: PageKey) {
    setPage(next)
    setMobileMenuOpen(false)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }

  const grouped = [...new Set(navigation.map((item) => item.section))]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <aside className={`fixed inset-y-0 left-0 z-30 flex w-[248px] flex-col bg-[#101f2a] text-slate-200 transition-transform md:translate-x-0 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex h-[70px] items-center gap-3 border-b border-white/10 px-5">
          <div className="grid size-9 place-items-center rounded-xl bg-teal-500 text-white shadow-lg shadow-teal-950/30"><Command size={19} strokeWidth={2.2} /></div>
          <div>
            <p className="text-sm font-semibold tracking-wide text-white">YottaFlex</p>
            <p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.17em] text-slate-400">Inventory intelligence</p>
          </div>
          <button type="button" className="ml-auto rounded-md p-1 text-slate-400 hover:bg-white/10 md:hidden" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>

        <div className="px-3 py-5">
          {grouped.map((section) => (
            <div key={section} className="mb-5">
              <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">{section}</p>
              <nav aria-label={section}>
                {navigation.filter((item) => item.section === section).map(({ label, key, icon: Icon }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => navigate(key)}
                    aria-current={page === key ? 'page' : undefined}
                    className={`mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13px] transition ${page === key ? 'bg-teal-500/15 font-semibold text-teal-300' : 'text-slate-400 hover:bg-white/[0.06] hover:text-slate-100'}`}
                  >
                    <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
                  </button>
                ))}
              </nav>
            </div>
          ))}
        </div>

        <div className="mt-auto border-t border-white/10 p-4">
          <div className="flex items-center gap-3 rounded-lg p-2">
            <div className="grid size-8 place-items-center rounded-full bg-slate-700 text-xs font-semibold text-white">YF</div>
            <div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-slate-200">Planning workspace</p><p className="mt-0.5 text-[10px] text-slate-500">Demand & supply team</p></div>
            <ChevronDown size={15} className="text-slate-500" />
          </div>
        </div>
      </aside>

      {mobileMenuOpen && <button className="fixed inset-0 z-20 bg-slate-950/40 md:hidden" aria-label="Close navigation overlay" onClick={() => setMobileMenuOpen(false)} />}
      <div className="min-h-screen md:pl-[248px]">
        <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <button type="button" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden" aria-label="Open navigation" onClick={() => setMobileMenuOpen(true)}><Menu size={19} /></button>
            <div className="hidden text-xs text-slate-400 sm:block">Workspace <span className="mx-1.5">/</span></div>
            <span className="text-sm font-semibold text-slate-800">{pageTitles[page]}</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <Button size="sm" variant="outline" className="hidden sm:inline-flex" onClick={() => navigate('overview')}>Dashboard</Button>
          </div>
        </header>
        <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Suspense fallback={<LoadingState label="Loading workspace…" />}><PageContent page={page} /></Suspense>
          <footer className="mt-9 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200/80 pt-4 text-[11px] text-slate-400">
            <span>YottaFlex Demand Forecasting & Replenishment</span>
          </footer>
        </main>
      </div>
      <Toaster position="bottom-right" richColors closeButton />
    </div>
  )
}
