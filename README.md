# YottaFlex Demand Forecasting & Inventory Replenishment System

A high-performance retail inventory intelligence and decision-support platform built with **Python 3.12**, **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL**, and **NumPy**.

---

## 1. System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI REST API v1                             │
│ ────────────────────────────────────────────────────────────────────── │
│ /overview | /skus | /stores | /suppliers | /inventory | /sales         │
│ /forecasts/run | /forecasts/evaluations | /recommendations | /exceptions│
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼                                 ▼
┌─────────────────────────────────────┐ ┌────────────────────────────────┐
│      Statistical Forecasting        │ │      Replenishment Engine      │
│ ─────────────────────────────────── │ │ ────────────────────────────── │
│ • Moving Average                    │ │ • Lead Time Demand (LTD)       │
│ • Seasonal Naive (7-day seasonality)│ │ • Safety Stock (Z * sigma_LTD) │
│ • Exponential Smoothing             │ │ • Reorder Point (ROP)          │
│ • Croston Intermittent Demand (SBA) │ │ • Pack-Size & MOQ Enforcement  │
│ • Stockout-Censored Unconstraining  │ │ • Warehouse Capacity Guard     │
│ • Out-of-Sample Backtest (WAPE/Bias)│ │ • Explainability Breakdown     │
└──────────────────┬──────────────────┘ └────────────────┬───────────────┘
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  Relational Database (PostgreSQL 16/18)                │
│ ────────────────────────────────────────────────────────────────────── │
│ skus | stores | suppliers | supplier_skus | sales_history              │
│ inventory_snapshots | lead_time_observations | reorder_policies        │
│ forecasts | purchase_recommendations | inventory_exceptions            │
│ forecast_evaluations                                                   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Functional Modules

### A. Synthetic Data Generator (`backend/app/engines/data_generator/`)
- **Profiles**: `dev` (100 SKUs, 10 stores, 90 days) and `full` (2,000 SKUs, 100 stores, 365 days).
- **Deterministic Reproducibility**: Fixed seed `20261022`.
- **Vectorized High Performance**: Generates 90,000 sales records in under 0.6 seconds.
- **Retail Dynamics**: Realistic product categories, day-of-week seasonality, promotional lifts (15-25% discount, 1.5x-2.5x volume), lead-time variability, and inventory conservation.
- **Stockout-Censored Demand Separation**: Separates genuine zero demand from unobserved demand caused by depleted on-hand stock (`closing_stock == 0` and `stockout_flag == True`).
- **5 Labeled Data Anomalies**:
  1. `STOCKOUT_AS_ZERO_DEMAND`: Stockout recorded without stockout flag.
  2. `PACK_SIZE_VIOLATION`: Reorder quantity ignoring supplier pack-size multiple.
  3. `DISCONTINUED_SKU_ORDER`: Procurement proposed for inactive SKU.
  4. `NEGATIVE_LEAD_TIME`: Delivery date preceding purchase order date.
  5. `FUTURE_LEAKAGE_FORECAST`: Model training using sales data beyond forecast cutoff.

### B. Statistical Forecasting Engine (`backend/app/engines/forecasting/`)
- **Baseline Models**:
  - `MovingAverageForecaster`: Rolling window average with prediction intervals.
  - `SeasonalNaiveForecaster`: Day-of-week retail seasonality replication ($L=7$).
  - `ExponentialSmoothingForecaster`: Holt-Winters additive level and weekly seasonal smoothing.
  - `CrostonForecaster`: Intermittent / slow-moving demand forecasting with Syntetos-Boylan Approximation (SBA) debiasing factor.
- **Stockout Censoring Imputation**: Imputes unconstrained demand for stockout periods using unconstrained day-of-week medians.
- **Temporal Leakage Prevention**: Strict out-of-sample temporal split ($\max(T_{\text{train}}) < \min(T_{\text{test}})$) guaranteeing zero lookahead bias.
- **Evaluation Metrics**: MAE, RMSE, WAPE (Weighted Absolute Percentage Error), and Forecast Bias ($\bar{\hat{y}} - \bar{y}$).

### C. Replenishment & Decision-Support Engine (`backend/app/engines/replenishment/`)
- **Lead Time Demand**: $\text{LTD} = \bar{D} \times \bar{L}$
- **Safety Stock**: Considers both demand variability ($\sigma_D$) and empirical vendor turnaround variability ($\sigma_L$):
  $$\sigma_{\text{LTD}} = \sqrt{\bar{L} \sigma_D^2 + \bar{D}^2 \sigma_L^2}, \quad SS = \lceil Z \times \sigma_{\text{LTD}} \rceil$$
- **Reorder Point**: $\text{ROP} = \lceil \text{LTD} + SS \rceil$
- **Net Inventory Position**: $\text{IP} = \text{On-Hand} + \text{On-Order} - \text{Reserved}$
- **Trigger**: Replenishment evaluated when $\text{IP} \le \text{ROP}$.
- **Constraint Enforcement**:
  - Rounds up to nearest integer multiple of supplier `pack_size`.
  - Enforces Minimum Order Quantity (MOQ).
  - Validates physical store `warehouse_capacity_units`. If MOQ exceeds remaining capacity, flags a `MOQ_CAPACITY_CONFLICT` exception instead of generating an illegal order.
- **Explainability**: Every recommendation includes a structured audit dictionary explaining exact trigger reasons, math parameters, and constraint adjustments.
- **Human Approval Lifecycle**: Proposals are stored in `PENDING` state and require human planner review (`APPROVED` or `REJECTED`) with audit timestamps and reviewer notes.

---

## 3. Installation & Setup

### Prerequisites
- Python 3.12+
- PostgreSQL 16+ or 18+ (running natively on Windows port 5432)

### Setup Steps

1. **Create and activate a virtual environment** from the repository root:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -r backend/requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` in the repository root and set your local
   PostgreSQL password. Keep `.env` local; it is excluded from Git.
   ```ini
   ENVIRONMENT=development
   POSTGRES_USER=yottaflex
   POSTGRES_PASSWORD=replace-with-your-local-password
   POSTGRES_DB=yottaflex_demand
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   RANDOM_SEED=20261022
   DATASET_PROFILE=dev
   ```
   For Windows installations where Application Control blocks psycopg's
   bundled native library, select the pure-Python implementation and expose
   the installed PostgreSQL `bin` directory to the current PowerShell session:
   ```powershell
   $env:PSYCOPG_IMPL = "python"
   $env:PATH = "C:\Program Files\PostgreSQL\18\bin;" + $env:PATH
   ```
   Adjust the PostgreSQL installation path if you are using another version.

4. **Apply database migrations** from the repository root. This upgrades the
   schema without dropping or recreating the database:
   ```powershell
   python -m alembic -c backend/alembic.ini upgrade head
   python -m alembic -c backend/alembic.ini current
   ```

5. **Seed the development dataset**:
   ```powershell
   python scripts/seed_data.py dev
   ```
   The command requires the schema to be at the current Alembic head. It skips
   insertion when it detects the complete matching seed dataset and refuses to
   write into a partially populated or conflicting database.

6. **Start FastAPI Application Server** from the repository root:
   ```powershell
   python -m uvicorn app.main:app --app-dir backend --reload --port 8000
   ```
   Interactive OpenAPI documentation available at: `http://localhost:8000/docs`

---

## 4. Running Tests

Run the test suite with Pytest:
```powershell
python -m pytest -v tests
```

The test suite runs against an isolated, fast in-memory SQLite engine and tests:
- Data generator seed reproducibility and anomaly presence
- Temporal leakage prevention
- Stockout-censored demand unconstraining
- Forecast baseline models and WAPE/Bias metrics
- Safety stock, ROP, pack rounding, and MOQ constraints
- Warehouse capacity overflow and discontinued SKU exceptions
- REST API endpoint contracts and approval lifecycle

---

## 5. Architectural Decisions & Trade-Offs

1. **Native PostgreSQL**:
   PostgreSQL runs as a native Windows service for local development.
2. **Deterministic Seed (20261022)**:
   Guarantees that test assertions and benchmark runs remain reproducible across machines.
3. **WAPE over MAPE**:
   Retail demand frequently includes zero-demand days (especially for slow-moving SKUs). Standard MAPE divides by zero ($y=0$), causing division errors or infinite penalties. WAPE ($\sum |y - \hat{y}| / \sum y$) provides a robust, scale-sensitive volume metric.
4. **Decision-Support Guardrails**:
   Automated replenishment proposals remain in `PENDING` status and require human planner approval. Conflicting constraints (such as supplier MOQ exceeding store warehouse capacity) generate explicit `inventory_exceptions` rather than generating invalid purchase orders.

---

## 6. Web Dashboard

The `frontend/` application is a React 19, TypeScript, Vite, Tailwind CSS 4,
shadcn-style component, Recharts, and Lucide-based dashboard. It uses the
FastAPI API for overview metrics, inventory snapshots, forecasts and evaluation,
purchase recommendations, exceptions, SKUs, stores, and suppliers. It does not
ship with mocked dashboard values. Monetary values are displayed in Indian
Rupees (INR) using Indian number grouping.

### Prerequisites

- Node.js 22.12 or newer (Node.js 24 is also supported by the current Vite toolchain)
- npm
- The configured FastAPI service and native PostgreSQL database

### Configure and run

Keep the backend running as described above. In a separate PowerShell terminal:

```powershell
Set-Location .\frontend
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm run dev
```

By default, `.env.example` points to `http://127.0.0.1:8000/api/v1`. Set
`VITE_API_URL` in the local, untracked `frontend/.env.local` if the API runs at a
different URL. The backend's default CORS configuration allows Vite at
`localhost:5173` and `127.0.0.1:5173`.

The dashboard is served at `http://localhost:5173`. FastAPI's interactive
documentation is at `http://localhost:8000/docs`.

### Frontend checks

```powershell
Set-Location .\frontend
npm run lint
npm run build
```

### Dashboard areas

- **Overview**: API-backed portfolio KPIs, 30-day demand and stockout trends,
  category inventory distribution, store capacity, open exceptions, and pending
  recommendations.
- **Inventory**: current snapshot search, category/store/status filters, sorting,
  pagination, availability, inbound units, reorder point, and safety stock.
- **Demand forecasting**: select an active SKU and store, choose one of the
  supported models and horizon, run the persisted forecast/evaluation API, and
  inspect historical demand, predictions, confidence bounds, MAE, RMSE, WAPE,
  and bias.
- **Replenishment**: run the existing capacity-aware replenishment API, inspect
  its explanation and supplier MOQ/pack size, and approve or reject pending
  recommendations with reviewer notes.
- **Exceptions**: filter by severity and resolution state and record resolution.
- **SKU catalog and suppliers**: read-only listings and available detail views;
  supplier assortment includes contracted lead time, MOQ, pack size, and cost.

### Known limitations

- The API does not provide authentication or role-based access; reviewer names
  are supplied by the planner.
- SKU and supplier pages are read-only because the current API does not expose
  catalog CRUD operations.
- Forecast accuracy metrics are unavailable until the backend has persisted an
  evaluation for the selected SKU/store pair.
- Forecast and replenishment runs execute synchronously through the current API.

---

## 7. Submission Checklist

- [ ] Start the backend and frontend locally and verify the live database is connected.
- [ ] Capture test output from `python -m pytest -v tests`, `npm run lint`, and `npm run build`.
- [ ] Record a demo of the overview, inventory, forecast, replenishment review, and exception workflows.
- [ ] Prepare a short technical walkthrough of the forecasting, replenishment, data model, and API decisions.
- [ ] Review the GitHub working tree and decide which local changes to stage and publish; changes from this work have not been committed or pushed.
- [ ] Include the actual prompt history from the Copilot conversation if required by the submission; do not reconstruct or invent prompts.
- [ ] Disclose AI assistance according to the submission's policy and include genuine test evidence.
