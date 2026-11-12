# Native Windows PostgreSQL Setup Guide

This guide details how to install and run **PostgreSQL 16** natively as a Windows Service, without requiring Docker or Docker Desktop.

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
- **Password**: Set a master password for user `postgres` (e.g. `postgres` or `yottaflex_secure_password`).
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

Once PostgreSQL is running, open PowerShell or Command Prompt to create the dedicated database and user:

```powershell
# Connect as superuser 'postgres' and create the application database
psql -U postgres -c "CREATE DATABASE yottaflex_demand;"
```

*(Optional)* Create a dedicated `yottaflex` user if you don't wish to use `postgres`:
```powershell
psql -U postgres -c "CREATE USER yottaflex WITH ENCRYPTED PASSWORD 'yottaflex_secure_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE yottaflex_demand TO yottaflex;"
```

---

## 4. Environment Configuration

In the project root, edit `.env` to match your local PostgreSQL credentials:

```ini
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_chosen_password
POSTGRES_DB=yottaflex_demand
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Database URL used by SQLAlchemy
DATABASE_URL=postgresql+psycopg://postgres:your_chosen_password@localhost:5432/yottaflex_demand
```

SQLAlchemy automatically parses this `DATABASE_URL` via environment variables.

