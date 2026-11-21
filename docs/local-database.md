# Local Database Guide: GIKI Sports Complex

**Document Reference:** `docs/local-database.md`  
**Purpose:** Instructions for running, configuring, and verifying the isolated local PostgreSQL 17 development service and Go database pool.  
**Compose Project Name:** `giki-sports-complex`  
**Dedicated Volume:** `giki-sports-complex_postgres_data`  

---

## 1. Architecture & Port Selection

To prevent port and volume conflicts with other campus services on the developer workstation:
- **Default Database Service:** PostgreSQL 17 (`postgres:17-alpine`).
- **Loopback Binding:** The database container binds strictly to loopback interface `127.0.0.1` (`127.0.0.1:${DB_PORT:-5433}:5432`).
- **Port Allocation Strategy:**
  - Port `5432`: Typically occupied by native host PostgreSQL.
  - Port `5433`: Dedicated to GIKI Wallet (`giki_wallet_db`).
  - Port `5434`: Configured default for GIKI Sports Complex when 5432/5433 are occupied. Configurable via `DB_PORT` in `.env`.
- **Data Volume Isolation:** Persists to dedicated Docker volume `giki-sports-complex_postgres_data`, ensuring zero data sharing with GIKI Wallet or other projects.
- **Bootstrap User:** The user `giki_sports_app` is a local container bootstrap user for development; production least-privilege roles and migrations will be managed separately.
- **Storage Layer Reality:** While the PostgreSQL connection pool is verified at startup via `/api/ready`, existing business domain endpoints (`/api/facilities`, `/api/bookings`, etc.) still read from and write to local JSON storage (`backend/data/store.json`) at this step.

---

## 2. Configuration Variables

Configuration values are managed through the root `.env` file (copied from [.env.example](file:///d:/giki%20sports%20complex/.env.example)). The `.env` file is git-ignored and must never be committed.

| Variable | Description | Default / Example | Notes |
|---|---|---|---|
| `PORT` | HTTP server port for Go Fiber API | `8081` | Set to 8081 to avoid conflict if GIKI Wallet is on 8080 |
| `DB_PORT` | Local host port bound to `127.0.0.1` | `5434` (or `5433` if available) | Assigned to avoid conflicts with 5432 and 5433 |
| `DB_HOST` | Host address for client connections | `127.0.0.1` | Loopback only |
| `DB_NAME` | Initial database name | `giki_sports_complex` | Required |
| `DB_USER` | Bootstrap database user | `giki_sports_app` | Required |
| `DB_PASSWORD` | Database user password | Cryptographically generated local secret | Required, non-empty |
| `DB_SSL_MODE` | SSL/TLS Mode | `disable` | `disable` is for local dev only; production requires `require` or `verify-full` |
| `DB_MAX_CONNS` | Maximum pool connections | `10` | Must be greater than 0 |
| `DB_MIN_CONNS` | Minimum idle connections | `2` | Must be $\ge 0$ and $\le$ `DB_MAX_CONNS` |
| `DB_MAX_CONN_LIFETIME` | Max lifetime of a pooled connection | `1h` | Valid duration string (e.g. `1h`, `30m`) |
| `DB_MAX_CONN_IDLE_TIME` | Max idle duration before closing | `30m` | Valid duration string (e.g. `30m`, `15m`) |
| `DB_CONNECT_TIMEOUT` | Bounded connection timeout | `5s` | Used during startup pool creation and health checks |

---

## 3. PowerShell Operational Procedures

All commands are executed from the repository root: `d:\giki sports complex`.

### 3.1 Initial Setup

If no `.env` file exists, create one from `.env.example` with a secure random password:

```powershell
# Copy template and generate a local random development password (without printing it)
if (-not (Test-Path ".env")) {
    $bytes = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $pwd = [Convert]::ToBase64String($bytes).Replace('+', '').Replace('/', '').Replace('=', '')
    $content = (Get-Content ".env.example" -Raw) -replace "your_secure_development_password_here", $pwd
    [IO.File]::WriteAllText((Join-Path (Get-Location) ".env"), $content)
    Write-Host "Created local .env with generated development password."
} else {
    Write-Host "Local .env already exists; preserving existing configuration."
}
```

### 3.2 Starting the Database Service

Start the containerized PostgreSQL service in the background:

```powershell
docker compose up -d db
```

### 3.3 Checking Health & Container Status

Verify that the container is running and has passed its readiness healthcheck:

```powershell
# Inspect container status and health
docker compose ps

# Check detailed Docker health status
docker inspect --format='{{json .State.Health.Status}}' (docker compose ps -q db)
```

Expected output: `"healthy"`.

### 3.4 Connecting Interactively

#### Option A: Interactive `psql` shell inside the container
```powershell
docker compose exec -it db psql -U giki_sports_app -d giki_sports_complex
```

#### Option B: Connecting from the host machine using host `psql`
```powershell
# Load environment variables into current session without printing secrets
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}
$env:PGPASSWORD = $env:DB_PASSWORD

# Execute query over TCP loopback connection
psql -h 127.0.0.1 -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -c "SELECT current_database(), current_user, now();"
```

### 3.5 Stopping the Service While Retaining Data

To stop the database service without deleting persistent storage:

```powershell
# Stop container without removing volumes
docker compose stop db

# Alternatively, take down containers and network while preserving named volumes:
docker compose down
```

*Warning: Never use `docker compose down -v` as the `-v` flag deletes persistent volumes.*

### 3.6 Automated Go Database Integration Verification

Run the automated integration tests from the `backend/` directory:

```powershell
cd "d:\giki sports complex\backend"

# Unit tests (isolated from real database and .env)
go test -v ./internal/config/...

# Explicit PostgreSQL integration test against running container (requires db to be up)
go test -v -tags=integration ./internal/database/...
```

Expected output for integration test:
```text
=== RUN   TestPostgresIntegration_ConnectAndQuery
--- PASS: TestPostgresIntegration_ConnectAndQuery (0.10s)
=== RUN   TestPostgresIntegration_UnreachableHostBoundedTimeout
--- PASS: TestPostgresIntegration_UnreachableHostBoundedTimeout (0.07s)
PASS
ok      giki-sports-backend/internal/database   1.358s
```

### 3.7 Verifying Application Liveness & Readiness Endpoints

Start the Go backend and probe the liveness and readiness endpoints:

```powershell
cd "d:\giki sports complex\backend"
go run .

# In another terminal window:
# Liveness probe (checks web process):
Invoke-RestMethod -Uri "http://localhost:8081/api/health"

# Readiness probe (checks PostgreSQL pool connection):
Invoke-RestMethod -Uri "http://localhost:8081/api/ready"
```

Expected responses:
- `/api/health`: `{"engine":"Go Fiber v2 / fasthttp","status":"online","time":"...","timestamp":...}`
- `/api/ready`: `{"database":"connected","note":"database connectivity verified; business schema migrations and data persistence remain pending","status":"ready"}`
