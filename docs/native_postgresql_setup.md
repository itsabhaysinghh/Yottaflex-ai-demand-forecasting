# Native Windows PostgreSQL Setup Guide

This guide details how to install and run **PostgreSQL 16 or newer** natively as a Windows Service.

---

## 1. Installation Options

### Option A: Install via Winget (Elevated PowerShell)
Open **PowerShell as Administrator** (Right-click Windows Start menu $\to$ **Terminal (Admin)** or **PowerShell (Admin)**) and execute:

```powershell
winget install --id PostgreSQL.PostgreSQL.16 --interactive
```
The official EnterpriseDB graphical setup wizard will launch. Follow the prompts:
- **Installation Directory**: `C:\Program Files\PostgreSQL\16` (default)
- **Data Directory**: `C:\Program Files\PostgreSQL\16\data` (default)
- **Password**: Set a strong, unique password for the PostgreSQL superuser and store it securely.
- **Port**: `5432` (default)
- **Locale**: `[Default locale]`

### Option B: Direct Download (GUI Wizard)
1. Download the Windows x86-64 installer from official PostgreSQL downloads:
   [https://www.postgresql.org/download/windows/](https://www.postgresql.org/download/windows/)
2. Run the `.exe` installer as Administrator and complete the setup wizard with port `5432`.

---

## 2. Managing the Windows Service

Once installed, PostgreSQL runs continuously in the background as a registered Windows Service (`postgresql-x64-16`).

Check service status in PowerShell:
```powershell
Get-Service -Name "*postgres*"
```

Start the service if stopped:
```powershell
Start-Service -Name "postgresql-x64-16"
```

Stop the service:
```powershell
Stop-Service -Name "postgresql-x64-16"
```

---

## 3. Database Initialization for YottaFlex

For a new installation only, create the application database and user if they do not
already exist. Do not rerun these commands against an existing database or role.

```powershell
# Connect as superuser 'postgres' and run these commands for a fresh database
psql -U postgres
CREATE DATABASE yottaflex_demand;
CREATE ROLE yottaflex LOGIN;
\password yottaflex
GRANT ALL PRIVILEGES ON DATABASE yottaflex_demand TO yottaflex;
\q
```

---

## 4. Environment Configuration

In the project root, edit `.env` to match your local PostgreSQL credentials:

```ini
POSTGRES_USER=yottaflex
POSTGRES_PASSWORD=replace-with-your-local-password
POSTGRES_DB=yottaflex_demand
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

The application constructs a psycopg 3 SQLAlchemy URL from these values. Apply
the Alembic migration and seed the database using the commands in the repository
README; do not use `create_all()` as a substitute for migrations.

On Windows systems where Application Control blocks psycopg's bundled native
library, use the pure-Python implementation with the installed PostgreSQL
client library in PowerShell before starting the application:

```powershell
$env:PSYCOPG_IMPL = "python"
$env:PATH = "C:\Program Files\PostgreSQL\18\bin;" + $env:PATH
```
