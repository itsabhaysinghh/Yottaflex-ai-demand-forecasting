# YottaFlex Demand Forecasting & Inventory Replenishment System

A high-performance retail inventory intelligence and decision-support platform built with **Python 3.12**, **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL**, **Polars**, and **NumPy**.

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

1. **Activate Virtual Environment**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -r backend/requirements.txt
   ```

3. **Configure Environment Variables**:
   Create or verify `.env` in the repository root:
   ```ini
   ENVIRONMENT=development
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=yottaflex_demand
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/yottaflex_demand
   RANDOM_SEED=20261022
   DATASET_PROFILE=dev
   ```

4. **Seed Database**:
   ```powershell
   python scripts/seed_data.py dev
   ```

5. **Start FastAPI Application Server**:
   ```powershell
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```
   Interactive OpenAPI documentation available at: `http://localhost:8000/docs`

---

## 4. Running Tests

Run the test suite with Pytest:
```powershell
pytest -v tests
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

1. **Native PostgreSQL vs. Containerization**:
   PostgreSQL is configured as the primary production-grade database running as a native Windows service, eliminating Docker Desktop engine overhead during local development.
2. **Deterministic Seed (20261022)**:
   Guarantees that test assertions and benchmark runs remain reproducible across machines.
3. **WAPE over MAPE**:
   Retail demand frequently includes zero-demand days (especially for slow-moving SKUs). Standard MAPE divides by zero ($y=0$), causing division errors or infinite penalties. WAPE ($\sum |y - \hat{y}| / \sum y$) provides a robust, scale-sensitive volume metric.
4. **Decision-Support Guardrails**:
   Automated replenishment proposals remain in `PENDING` status and require human planner approval. Conflicting constraints (such as supplier MOQ exceeding store warehouse capacity) generate explicit `inventory_exceptions` rather than generating invalid purchase orders.
