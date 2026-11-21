# PostgreSQL Migration Mechanism: GIKI Sports Complex

**Document Reference:** `docs/database-migrations.md`  
**Current Milestone:** Step 4A.1 Complete (Migration Safety, Coordination & Accuracy Review)  
**Execution Context:** Single-developer sequential implementation.

---

## 1. Overview & Problem Definition

In early development, databases are often created and updated manually via ad-hoc SQL scripts or GUI tools. However, manual schema modifications lead to severe problems:
- **Environment Drift:** One developer or environment has tables or columns that another environment lacks.
- **Irreproducibility:** No reliable record exists of what DDL statements were executed, in what sequence, or when.
- **Deployment Fragility:** New application versions fail in staging or production because database prerequisites are missing or partially applied.

A **database migration mechanism** solves this by treating database schema definitions as version-controlled, testable, and repeatable software code. Each change is encapsulated in an ordered, numbered migration script with an explicit forward path (`Up`) and reverse path (`Down`).

### 1.1 Critical Reality: What Migrations Track vs. What They Cannot Guarantee
> [!IMPORTANT]
> **Migrations Track Applied Versions, Not Database Checksums:**
> - Goose maintains an internal ledger (`goose_db_version`) that records which version IDs have been applied and when.
> - **Migrations do NOT detect or prevent manual database modifications.** If an administrator or developer executes manual `ALTER TABLE`, `DROP TABLE`, or adds columns directly via `psql` or a GUI tool, migrations cannot detect that out-of-band drift.
> - True environment reproducibility requires that **all** DDL changes be executed strictly through migration files and that manual DDL modification on managed databases is forbidden.

---

## 2. Migration Architecture & Explicit Coordination

### 2.1 Tool Choice: Goose (`github.com/pressly/goose/v3`)
- **Version:** Pinned to `v3.29.0` in [backend/go.mod](file:///d:/giki%20sports%20complex/backend/go.mod).
- **Driver Integration:** Integrated with `github.com/jackc/pgx/v5/stdlib` for native PostgreSQL compatibility.
- **Decoupled Application Startup:** Normal application startup (`backend/main.go`) **never** executes migrations automatically. Migrations are controlled exclusively via dedicated administrative CLI commands or automated deployment workflows.

### 2.2 Explicit PostgreSQL Advisory Locking Implementation
In Goose v3, package-level convenience functions (such as `goose.Up` or `goose.UpContext`) **do not enable locking by default**, even when the PostgreSQL dialect is selected.

To guarantee true multi-process and multi-instance concurrency safety:
1. We construct a `goose.Provider` using [lock.NewPostgresSessionLocker](file:///d:/giki%20sports%20complex/backend/internal/database/migration.go):
   ```go
   sessionLocker, err := lock.NewPostgresSessionLocker()
   provider, err := goose.NewProvider(
       goose.DialectPostgres,
       db,
       fsys,
       goose.WithSessionLocker(sessionLocker),
   )
   ```
2. **How It Works:** Goose requests an exclusive session-level advisory lock (`pg_advisory_lock` with default lock ID `4097083626`) from PostgreSQL before inspecting or altering migration state.
3. If multiple backend instances or deployment runners attempt to run migrations concurrently:
   - Exactly one runner acquires the lock and applies the pending migrations.
   - Other runners block until the lock is released, after which they detect that all migrations have already been applied and exit safely with zero duplicate executions.
4. **Shared Runner Construction:** Both the CLI runner ([backend/cmd/migrate/main.go](file:///d:/giki%20sports%20complex/backend/cmd/migrate/main.go)) and integration tests ([backend/internal/database/migration_integration_test.go](file:///d:/giki%20sports%20complex/backend/internal/database/migration_integration_test.go)) instantiate migrations through the unified [database.NewMigrationRunnerFromDir](file:///d:/giki%20sports%20complex/backend/internal/database/migration.go), guaranteeing identical locking and dialect behavior.

### 2.3 Credential Protection & Configuration Reuse
The migration CLI reuses the typed configuration package [backend/internal/config](file:///d:/giki%20sports%20complex/backend/internal/config/config.go) created in Step 3:
- Reads `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_SSL_MODE` from the environment or predictable root `.env`.
- Database connections are initialized via [database.NewSQLDB](file:///d:/giki%20sports%20complex/backend/internal/database/database.go), which populates `pgx.ConnConfig` struct fields directly.
- **Zero Credential Exposure:** Credentials are never passed as command-line arguments, formatted into connection string URLs, or printed to stdout/stderr.

### 2.4 Directory Structure
```
backend/
├── cmd/
│   └── migrate/
│       └── main.go       # Go migration CLI runner (status, up, down)
├── migrations/
│   └── 00001_create_giki_sports_schema.sql  # Corrected initial migration
└── internal/
    ├── config/           # Configuration loader and validator
    └── database/
        ├── database.go   # NewPool and NewSQLDB constructors
        ├── migration.go  # Unified MigrationRunner with session advisory locking
        ├── database_integration_test.go
        └── migration_integration_test.go    # Hermetic disposable DB tests
```

---

## 3. Migration Files: PostgreSQL Schema vs. Table & The RESTRICT Correction

### 3.1 Understanding a PostgreSQL Schema
In PostgreSQL, a **schema** is a distinct namespace within a database. It functions like a folder in a filesystem:
- A single PostgreSQL database (e.g. `giki_sports_complex`) contains one or more schemas.
- By default, PostgreSQL provides a `public` schema.
- Creating a dedicated schema (`giki_sports`) isolates application tables, types, and sequences from default schemas and third-party tools, preventing naming collisions.
- **A schema is not a table:** A schema is a container/namespace; tables reside *inside* a schema.

### 3.2 Initial Migration & The RESTRICT Correction
File: [backend/migrations/00001_create_giki_sports_schema.sql](file:///d:/giki%20sports%20complex/backend/migrations/00001_create_giki_sports_schema.sql)
```sql
-- +goose Up
-- Step 4A: Initialize empty giki_sports PostgreSQL schema.
-- Business tables (users, facilities, bookings, etc.) will be added in subsequent migration steps.
CREATE SCHEMA IF NOT EXISTS giki_sports;

-- +goose Down
-- Reverse migration: remove empty giki_sports schema if rolled back.
-- RESTRICT explicitly refuses to remove the schema if it contains any tables or objects,
-- preventing catastrophic accidental data loss.
DROP SCHEMA IF EXISTS giki_sports RESTRICT;
```

#### Why CASCADE Was Replaced with RESTRICT:
- **The Danger of CASCADE:** `DROP SCHEMA ... CASCADE` forcibly and silently drops **all** objects inside the schema, including all tables, views, and stored data. If an administrator mistakenly ran a single-step rollback (`down`) on migration 1, the entire schema along with all production or development tables would be permanently destroyed.
- **The RESTRICT Guarantee:** `DROP SCHEMA ... RESTRICT` instructs PostgreSQL to abort if the schema contains any dependent objects (tables, views, sequences). A rollback of migration 1 will succeed **only** if the schema is completely empty. If tables exist, PostgreSQL returns error `SQLSTATE 2BP01: cannot drop schema giki_sports because other objects depend on it`, aborts the transaction, and leaves all tables and the version record intact.

---

## 4. Migration Commands & Usage

All migration commands must be executed from the `backend/` directory in PowerShell:

### 4.1 Check Migration Status (Read-Only)
Inspects the database migration history table (`goose_db_version`) and displays applied and pending migrations:
```powershell
# Working directory: d:\giki sports complex\backend
go run ./cmd/migrate status
```
**Expected Output:**
```text
2026/10/17 11:19:18 Connecting to PostgreSQL at 127.0.0.1:5434 (database: giki_sports_complex, user: giki_sports_app, sslmode: disable)...
2026/10/17 11:19:18 Running migration command 'status' with PostgreSQL session advisory locking using directory: migrations
    Applied At                  Migration
    =======================================
    Sat Oct 17 05:53:17 2026    -- 00001_create_giki_sports_schema.sql
```

### 4.2 Apply Pending Migrations (`up`)
Applies all unapplied migrations in chronological order under advisory lock:
```powershell
# Working directory: d:\giki sports complex\backend
go run ./cmd/migrate up
```
**Expected Output (when already up to date):**
```text
2026/10/17 11:19:25 Connecting to PostgreSQL at 127.0.0.1:5434 (database: giki_sports_complex, user: giki_sports_app, sslmode: disable)...
2026/10/17 11:19:25 Running migration command 'up' with PostgreSQL session advisory locking using directory: migrations
2026/10/17 11:19:25 goose: no migrations to run.
2026/10/17 11:19:25 ✓ Migrations applied successfully.
```

### 4.3 Roll Back One Migration (`down`)
Reverts the single most recent migration under advisory lock.
> [!CAUTION]
> **Safety Rule:** `down` is **NEVER** run against the main development database (`giki_sports_complex`). Reversal is tested and verified strictly against isolated disposable test databases.
```powershell
# Working directory: d:\giki sports complex\backend
go run ./cmd/migrate down
```

---

## 5. Development Database vs. Disposable Test Database

| Dimension | Development Database (`giki_sports_complex`) | Disposable Test Database (`giki_sports_disposable_*`) |
|---|---|---|
| **Purpose** | Ongoing application development, manual API testing, local state | Automated integration verification of migration lifecycle and edge cases |
| **Lifecycle** | Persistent Docker volume (`giki-sports-complex_pgdata`) | Created dynamically with unique timestamp name; dropped on test completion |
| **Permitted Commands** | `status`, `up` | `up`, repeating `up` (idempotency), `status`, `down`, re-`up`, concurrency testing |
| **Reverse Migrations (`down`)** | **STRICTLY PROHIBITED** (protects development state) | **MANDATORY** (proves rollback capability & failure protections) |
| **Cleanup Protocol** | Never dropped | Bounded cleanup context; connections closed first; errors reported via `t.Errorf` |

---

## 6. Verification & Automated Test Evidence

### 6.1 Automated Integration Tests
File: [backend/internal/database/migration_integration_test.go](file:///d:/giki%20sports%20complex/backend/internal/database/migration_integration_test.go)

All integration tests are executed against disposable databases with bounded cleanup contexts and strict prefix checks:

#### Test 1: `TestMigrationIntegration_DisposableDatabaseCycle`
- Provisions `giki_sports_disposable_cycle_<timestamp>`.
- Verifies initial absence of schema `giki_sports`.
- Executes `runner.Up(ctx)` $\to$ schema created.
- Executes repeat `runner.Up(ctx)` $\to$ returns 0 migrations applied (idempotent).
- Verifies `runner.Status(ctx)` reports version 1 applied.
- Executes `runner.Down(ctx)` on empty schema $\to$ succeeds, schema removed.
- Reapplies `runner.Up(ctx)` $\to$ succeeds, schema restored.
- Closes test connection, executes `DROP DATABASE ... WITH (FORCE)`, and checks for errors.
- **Observed Result:** `PASS (0.96s)`

#### Test 2: `TestMigrationIntegration_NonEmptySchemaRollbackRejected`
- Provisions `giki_sports_disposable_nonempty_<timestamp>`.
- Executes `runner.Up(ctx)` to provision `giki_sports`.
- Injects a probe table: `CREATE TABLE giki_sports.probe_table (id INT PRIMARY KEY, probe_name TEXT); INSERT INTO giki_sports.probe_table VALUES (42, 'critical_production_probe');`.
- Executes `runner.Down(ctx)`.
- **Observed Result:** `Down was rejected as expected: partial migration error: ERROR: cannot drop schema giki_sports because other objects depend on it (SQLSTATE 2BP01)`.
- Verifies `probe_table` and row `(42, 'critical_production_probe')` remain 100% intact.
- Verifies `goose_db_version` still retains version 1 as applied.
- Cleans up probe table, re-runs `Down` on empty schema $\to$ succeeds.
- Drops disposable DB.
- **Observed Result:** `PASS (0.38s)`

#### Test 3: `TestMigrationIntegration_ConcurrentMigrationsCoordinated`
- Provisions `giki_sports_disposable_concurrent_<timestamp>`.
- Spawns 5 concurrent goroutines, each opening an independent connection and `MigrationRunner`.
- All 5 workers execute `runner.Up(ctx)` simultaneously.
- **Observed Result:** Worker 4 acquired the session advisory lock and applied 1 migration. Workers 0, 1, 2, and 3 blocked, waited, and cleanly detected 0 pending migrations upon lock acquisition. Zero errors occurred.
- Verifies `goose_db_version` contains exactly 1 record for version 1.
- Drops disposable DB.
- **Observed Result:** `PASS (1.40s)`

### 6.2 Host Build & Vet Validation
- `go build ./...` $\to$ **Exit 0**
- `go vet ./...` $\to$ **Exit 0**
- `go test ./...` $\to$ **Exit 0**
- `go test -v -tags=integration ./...` $\to$ **All 6 tests passed (Exit 0)**

---

## 7. Host Environment Note: Go Cache & Temp Paths Relocation

During Step 4A, Windows host drive `C:\` reached 0.00 GB free space (48 MB remaining), causing `go build` and module unzipping to fail with `There is not enough space on the disk`.

To avoid deleting user files or performing unauthorized disk cleanup, Go's environment configuration was redirected to drive `D:\` (which has ~20 GB free):
- `GOMODCACHE="D:\go\pkg\mod"`
- `GOCACHE="D:\go\cache"`
- `GOTMPDIR="D:\go\tmp"`

These environment settings are recorded here for transparency and remain active without further modification.

---

## 8. Known Mismatch: Backend Port vs. Frontend Vite Proxy

During the Step 3 review, an explicit configuration mismatch was confirmed:
- In `root .env` and `.env.example`, the Go backend is configured with `PORT=8081` to avoid conflicting with `giki_wallet_backend` running on port `8080`.
- In [frontend/vite.config.ts](file:///d:/giki%20sports%20complex/frontend/vite.config.ts#L13), the Vite dev proxy forwards `/api` to:
  ```typescript
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  }
  ```
- **Impact:** Until the frontend proxy configuration is updated to target `http://localhost:8081` (or the backend port is harmonized), frontend API requests would proxy to `giki_wallet_backend` instead of `giki-sports-backend`.
- **Constraint Compliance:** Per task requirements, this mismatch is recorded here and will be updated during the frontend integration step without altering frontend code during Step 4A.

---

## 9. Current System Boundaries

Even with Step 4A.1 complete, the application still cannot:
1. **Persist Application Data in PostgreSQL:** The database currently contains only the empty `giki_sports` namespace and version tracking table. Business tables (`users`, `sessions`, `facilities`, `bookings`, `memberships`) do not exist yet.
2. **Serve Database-backed Endpoints:** All existing backend API endpoints (`/api/facilities`, `/api/bookings`, `/api/achievements`, etc.) continue to serve and mutate JSON data from `backend/data/store.json`.
3. **Authenticate Users or Authorize Roles:** No session cookies, tokens, or hashed credentials exist in PostgreSQL.
