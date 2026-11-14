# YottaFlex AI — Demand Forecasting & Inventory Replenishment

A retail demand-planning and inventory decision-support application that forecasts SKU–store demand and turns those forecasts into explainable replenishment recommendations.

The project combines a statistical forecasting engine, a constraint-aware replenishment workflow, a PostgreSQL data model, and a React dashboard. Recommendations remain subject to planner review rather than being treated as automatically approved purchase orders.

## Overview

YottaFlex is designed around the day-to-day decisions involved in retail inventory planning:

1. Generate or load SKU, store, supplier, sales, inventory, and lead-time data.
2. Forecast demand for a selected SKU and store using a supported statistical baseline.
3. Evaluate forecast performance using out-of-sample metrics.
4. Calculate lead-time demand, safety stock, and reorder points.
5. Generate replenishment proposals while enforcing supplier and warehouse constraints.
6. Review recommendations and exceptions with an auditable decision history.

## Key capabilities

### Demand forecasting

Four statistical forecasting approaches are implemented:

- **Moving Average** — rolling-window demand baseline.
- **Seasonal Naive** — repeats the weekly seasonal pattern.
- **Exponential Smoothing** — level and weekly seasonal smoothing.
- **Croston SBA** — intermittent-demand forecasting with Syntetos–Boylan Approximation adjustment.

The forecasting workflow also includes:

- Stockout-censored demand handling to distinguish genuine zero demand from demand that could not be fulfilled.
- A temporal train/test split intended to prevent future information from entering model training.
- Prediction intervals where supported by the selected model.
- Evaluation using **MAE**, **RMSE**, **WAPE**, and **Forecast Bias**.

### Replenishment decision engine

The replenishment engine calculates:

- **Lead-time demand:** average demand multiplied by estimated lead time.
- **Safety stock:** accounts for demand variability and observed lead-time variability.
- **Reorder point:** lead-time demand plus safety stock.
- **Inventory position:** on-hand stock plus on-order stock less reserved stock.

Recommendations are evaluated against the reorder point and supplier/store constraints:

- Supplier minimum order quantity (MOQ).
- Supplier pack-size multiples.
- Store warehouse capacity.
- Existing inbound stock and active pending/approved recommendations.
- SKU and supplier eligibility.

A proposal that exceeds capacity is retained as a flagged exception rather than silently reduced or treated as approvable. A planner can submit a corrected quantity; the original recommendation remains in superseded history and the replacement is validated against the applicable constraints.

Each recommendation includes an explanation of the calculation and constraint decisions. New proposals require human review and can be approved or rejected with reviewer notes.

### Synthetic retail data

The deterministic data generator provides two profiles:

| Profile | SKUs | Stores | History |
|---|---:|---:|---:|
| `dev` | 100 | 10 | 90 days |
| `full` | 2,000 | 100 | 365 days |

The generator uses seed `20261022` for reproducible datasets. It models retail seasonality, promotions, supplier lead-time variation, and inventory movement.

Five labelled anomaly scenarios are included for validation and exception-oriented testing:

- `STOCKOUT_AS_ZERO_DEMAND`
- `PACK_SIZE_VIOLATION`
- `DISCONTINUED_SKU_ORDER`
- `NEGATIVE_LEAD_TIME`
- `FUTURE_LEAKAGE_FORECAST`

## Architecture

```text
React + TypeScript dashboard
          |
          | HTTP / JSON
          v
     FastAPI v1
       /     \
      v       v
Forecasting  Replenishment
  engine       engine
      \       /
       v     v
    SQLAlchemy ORM
          |
          v
      PostgreSQL

Synthetic data generator
          |
          v
   Dataset validation
          |
          v
     PostgreSQL seed
```

### Technology stack

| Layer | Technologies |
|---|---|
| Backend API | Python 3.12+, FastAPI, Pydantic |
| Data access | SQLAlchemy 2.x |
| Database and migrations | PostgreSQL, Alembic |
| Forecasting and data processing | NumPy and Python statistical implementations |
| Frontend | React 19, TypeScript, Vite |
| UI and visualization | Tailwind CSS 4, Recharts, Lucide |
| Frontend testing | Vitest, Testing Library |
| Backend testing | Pytest |

### Repository layout

```text
.
├── backend/
│   ├── alembic/                 # Database migrations
│   └── app/
│       ├── api/                 # Versioned FastAPI routes
│       ├── core/                # Configuration and database setup
│       ├── engines/
│       │   ├── data_generator/  # Synthetic data and validation
│       │   ├── forecasting/     # Forecast models and evaluation
│       │   └── replenishment/   # Inventory formulas and decisions
│       ├── models/              # SQLAlchemy entities
│       └── schemas/             # Pydantic request/response schemas
├── docs/                        # Architecture and setup documentation
├── frontend/
│   └── src/
│       ├── components/
│       ├── lib/                 # API client, types, and utilities
│       └── pages/
├── scripts/                     # Data seeding utilities
├── tests/                       # Backend tests
├── .env.example
└── README.md
```

## Getting started

The instructions below use **Windows PowerShell** and a locally running PostgreSQL instance. The application database is expected to be named `yottaflex_demand`.

### Prerequisites

- Python 3.12 or newer
- PostgreSQL 16 or newer
- Node.js version supported by the installed Vite toolchain
- npm

### 1. Clone the repository

```powershell
git clone https://github.com/itsabhaysinghh/Yottaflex-ai-demand-forecasting.git
Set-Location .\Yottaflex-ai-demand-forecasting
```

### 2. Set up the backend

Create and activate a virtual environment, then install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

Create a local environment file from the example:

```powershell
Copy-Item .env.example .env
```

Update the database settings in `.env` to match your local PostgreSQL user and password:

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

Keep the real `.env` file local. It is excluded from version control.

On Windows installations where the bundled psycopg native library is blocked by Application Control, use the pure-Python implementation and expose the PostgreSQL client binaries to the current PowerShell session:

```powershell
$env:PSYCOPG_IMPL = "python"
$env:PATH = "C:\Program Files\PostgreSQL\18\bin;" + $env:PATH
```

Adjust the PostgreSQL path to match your installation.

### 3. Apply database migrations

For a **new, empty application database**, run:

```powershell
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini current
```

For an **existing database being upgraded from the earlier schema**, first apply the recommendation-supersession metadata migration:

```powershell
python -m alembic -c backend/alembic.ini upgrade e74b2c19a6f1
```

Review any duplicate active recommendation cycles and explicitly supersede the non-canonical rows while preserving their history. Then apply the remaining migrations:

```powershell
python -m alembic -c backend/alembic.ini upgrade head
```

The active-cycle uniqueness migration checks for duplicate active rows and aborts if any remain. It does not automatically select or discard recommendation history.

> **Database safety:** Do not drop or recreate an existing application database to apply migrations. Review the current Alembic revision and back up important data before changing a database.

### 4. Seed the development dataset

After the schema is at the current Alembic head:

```powershell
python scripts/seed_data.py dev
```

The seeding command checks for a complete matching dataset and avoids inserting it again. It refuses to seed a partially populated or conflicting database.

### 5. Start the backend

From the repository root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

The API is available at:

- API base: `http://127.0.0.1:8000/api/v1`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

### 6. Set up and start the frontend

Open a second PowerShell terminal:

```powershell
Set-Location .\frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

The frontend environment example points to `http://127.0.0.1:8000/api/v1`. If the backend uses a different address, update `VITE_API_URL` in the local `frontend/.env.local` file.

The dashboard is available at `http://localhost:5173`.

## Application areas

| Area | Functionality |
|---|---|
| **Overview** | Portfolio KPIs, demand and stockout trends, category inventory, store capacity, open exceptions, and pending recommendations |
| **Inventory** | Search, filters, sorting, pagination, stock availability, inbound units, reorder points, and safety stock |
| **Demand Forecasting** | Select SKU/store, run a forecasting model, inspect historical demand and predictions, and review evaluation metrics |
| **Replenishment** | Generate proposals, inspect calculation explanations and supplier constraints, and review pending recommendations |
| **Exceptions** | Review exceptions by severity and resolution state, and record resolution |
| **SKU Catalog** | Browse SKU information and available details |
| **Suppliers** | Browse suppliers and supplier assortment, including lead time, MOQ, pack size, and cost |

## API surface

The versioned API exposes operations for:

- Overview metrics
- SKUs, stores, and suppliers
- Inventory snapshots and sales history
- Forecast generation and forecast evaluations
- Replenishment recommendations and recommendation review
- Inventory exceptions

Use the interactive OpenAPI page at `http://localhost:8000/docs` to inspect the current routes, request schemas, and response contracts.

## Testing and quality checks

Run the backend tests from the repository root:

```powershell
python -m pytest -v tests
```

The backend suite covers data generation and validation, forecasting behavior and metrics, replenishment calculations and constraints, and API workflows.

Run the PostgreSQL recommendation concurrency tests separately against a **dedicated local test database**. Set `YOTTAFLEX_TEST_POSTGRES_URL` to that database; its name must contain `test`. The test fixture creates and drops uniquely named schemas inside that database and rejects the application database `yottaflex_demand`.

```powershell
python -m pytest -v tests/test_recommendation_postgres_integration.py
```

Run frontend checks from the `frontend/` directory:

```powershell
npm test
npm run lint
npm exec -- tsc --noEmit -p tsconfig.app.json
npm run build
```

The frontend tests mock API calls at the test boundary. Normal application use retrieves data from the configured FastAPI service.

## Design decisions

- **Statistical baselines:** The project uses interpretable forecasting methods that provide a practical baseline for SKU–store demand. It does not require an LLM for the core forecasting or replenishment calculations.
- **WAPE instead of MAPE:** Retail demand can contain zero-demand observations. MAPE is undefined when actual demand is zero; WAPE provides an aggregate, volume-weighted error measure.
- **Temporal evaluation:** Forecast evaluation uses a chronological train/test split to reduce the risk of look-ahead leakage.
- **Human-in-the-loop procurement:** Recommendations are proposals, not automatically issued purchase orders. A planner reviews and approves or rejects them.
- **Explicit constraint handling:** MOQ, pack size, and warehouse capacity are treated as business constraints. Conflicts are surfaced as exceptions instead of silently altering the proposed quantity.
- **Preserved recommendation history:** Superseded recommendations remain available for auditability, while a partial unique index protects the active recommendation cycle.

## Known limitations

- The API does not currently provide authentication or role-based authorization. Reviewer names are supplied by the planner.
- SKU and supplier catalog pages are read-only; catalog create, update, and delete operations are not exposed.
- Forecast evaluation metrics are available only after an evaluation has been persisted for the selected SKU/store pair.
- Forecast and replenishment operations execute synchronously through the API; there is no background worker or job queue.
- The full synthetic-data profile is substantially larger than the development profile and may require additional memory and execution time.

## Security and configuration

- Do not commit `.env`, database passwords, API keys, private certificates, or other secrets.
- Use `.env.example` and `frontend/.env.example` as templates only.
- Keep local databases, virtual environments, dependency folders, and generated build artifacts out of version control.
- The current application is intended for local development and technical evaluation, not direct production deployment without additional authentication, authorization, deployment hardening, and operational controls.

## Project documentation

Additional technical documentation is available in `docs/`:

- `docs/architecture.md` — application architecture and request flow.
- `docs/entity_relationships.md` — database entities and relationships.
- `docs/native_postgresql_setup.md` — native PostgreSQL setup on Windows.
- `docs/requirement_compliance.md` — requirement assessment notes.

## AI-assisted development disclosure

AI coding tools were used to assist with parts of implementation and review. The resulting code, architecture, and behavior should be evaluated through the repository source, tests, and documentation. Any required prompt history or tool-specific disclosure should be provided separately using the actual prompts and records from the development sessions; prompts should not be reconstructed or presented as verbatim if they were not retained.

---

**Repository:** https://github.com/itsabhaysinghh/Yottaflex-ai-demand-forecasting  
**License:** No license file is currently included.