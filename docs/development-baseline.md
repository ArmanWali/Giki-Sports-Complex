# Development Baseline: GIKI Sports Complex Management System

**Document Reference:** `docs/development-baseline.md`  
**Current Milestone:** Step 10G Complete (Audited Draft Publish HTTP Endpoint)  
**Execution Context:** Single-developer sequential execution by project lead.

---

## 1. Development Environment & Runtime Verification

The development environment was inspected on the Windows host. Core runtime tools and engines were verified, distinguishing client CLI availability from daemon/engine availability.

### 1.1 Tool Runtime & Engine Status

| Tool / Engine | Component | Observed Status / Version | Manifest / Specification Source | Verification Status |
|---|---|---|---|:---:|
| **Go** | Compiler / Runtime | `go version go1.26.5 windows/amd64` | `backend/go.mod` (`go 1.26.5`) | **Active & Matching** |
| **Node.js** | JavaScript Runtime | `v23.8.0` | React 19 / Vite 6 requirement | **Active & Matching** |
| **npm** | Package Manager | `10.9.2` | Packaged with Node.js v23.8.0 | **Active & Matching** |
| **Docker** | Client CLI | `Docker version 29.6.2, build dfc4efb` | Prerequisites in SE-423 | **Active** |
| **Docker** | Engine / Daemon | `Docker Server 29.6.2` (WSL2 `docker-desktop` distro) | Docker Desktop Engine | **Verified Running** |
| **Docker Compose** | Compose CLI | `Docker Compose version v5.3.1` | Compose file v2+ specification | **Active** |
| **PostgreSQL Host Client** | `psql` CLI | `psql.exe 17.0.4.0` | Host installation | **Active** |
| **Git** | VCS | `git version 2.47.1.windows.1` | Working tree on branch `main` | **Active** |

### 1.2 Distinguishing Docker CLI vs. Engine Availability
- **Initial State:** The Docker CLI binary was present in `PATH`, but the Docker Desktop daemon was not running (`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`).
- **Resolution:** Launched Docker Desktop from its install path (`C:\Users\ucs\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`). The WSL2 engine (`docker-desktop`) transitioned from `Stopped` to `Running`.
- **Engine Verification:** Confirmed full engine responsiveness via `docker info` (Server Version `29.6.2`, storage driver `overlayfs`, Linux kernel `6.18.40.1-microsoft-standard-WSL2`).

### 1.3 Port Inspection & Conflict Resolution
Before binding database ports, host TCP sockets were inspected:
- **Port 5432:** Occupied by native Windows PostgreSQL service (PID `6548`).
- **Port 5433:** Occupied by `giki_wallet_db` (`127.0.0.1:5433->5432/tcp`).
- **Port 5434:** Free. Selected as the dedicated loopback binding port for `giki-sports-complex` (`127.0.0.1:5434->5432/tcp`), configured via `DB_PORT` in `.env`.
- **Port 8080:** Occupied by `giki_wallet_backend` (`127.0.0.1:8080->8080/tcp`).
- **Port 8081:** Configured for GIKI Sports Complex Go backend via `PORT=8081` in `.env` to prevent port collision with GIKI Wallet.

---

## 2. Step 3 Implementation & Verification Outcomes

Step 3 established typed database configuration, safe connection pool management via `pgxpool`, application startup wiring, readiness probing, and automated integration tests.

### 2.1 Backend Package Layout Added
- **`backend/internal/config/config.go`:**
  - Loads database parameters (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL_MODE`) and pool limits (`DB_MAX_CONNS`, `DB_MIN_CONNS`, `DB_MAX_CONN_LIFETIME`, `DB_MAX_CONN_IDLE_TIME`, `DB_CONNECT_TIMEOUT`).
  - Strict validation: checks required fields, bounds numeric values (ports 1–65535, connections $> 0$), and validates duration strings.
  - Precedence: active environment variables strictly override values from `.env`.
  - Predictable loading: checks `ENV_FILE`, then `.env`, `../.env`, or `../../.env` without traversing arbitrary directory trees.
  - Secret safety: `cfg.DB.String()` replaces passwords with `[REDACTED]` and never formats credential-bearing URLs.
- **`backend/internal/config/config_test.go`:**
  - Unit tests covering missing passwords, missing database/user, invalid ports, out-of-range bounds, invalid timeouts, precedence, and password redaction.
  - Tests run in isolation with hermetic temporary environment variables.
- **`backend/internal/database/database.go`:**
  - `NewPool(ctx, cfg.DB)` constructs `pgxpool.Config` programmatically by setting `ConnConfig` struct fields directly without string interpolation.
  - Explicit SSL mode mapping (`disable` for local dev; `require` / `verify-full` for production).
  - Bounded connection verification via `pool.Ping(connectCtx)` with immediate resource cleanup on failure (`pool.Close()`).
  - Error sanitization to prevent leaking password tokens in error returns.
- **`backend/internal/database/database_integration_test.go`:**
  - Opt-in integration suite guarded by `//go:build integration`.
  - `TestPostgresIntegration_ConnectAndQuery`: Executes real TCP connection to `127.0.0.1:5434`, executes `SELECT current_database(), current_user, 1;`, and verifies database and user identity. Fails immediately if database is unavailable.
  - `TestPostgresIntegration_UnreachableHostBoundedTimeout`: Verifies that connection to an unreachable port fails within a bounded timeout without hanging or leaking credentials.
- **`backend/main.go` Wiring:**
  - Startup sequence: loads configuration and verifies database connection pool before opening HTTP listeners. Fails fast with `log.Fatalf` if database configuration or connectivity is invalid.
  - Liveness probe preserved: `GET /api/health` returns process status.
  - Readiness probe added: `GET /api/ready` executes a 2-second bounded `pool.Ping(ctx)`. Returns HTTP 200 when connected, and HTTP 503 when unavailable with generic public error messages.
  - Graceful shutdown: captures `SIGINT` / `SIGTERM`, triggers `app.Shutdown()`, and closes the database pool via `defer dbPool.Close()`.

### 2.2 Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v ./...` | `backend/` | Standard unit test suite | **Passed (Exit 0):** All 3 config unit tests (10 subtests) passed. Database integration test skipped when tag omitted. |
| `go test -v -count=1 -tags=integration ./internal/database/...` | `backend/` | PostgreSQL integration test | **Passed (Exit 0):** Real TCP connection to `127.0.0.1:5434` succeeded; `current_database = giki_sports_complex`, `current_user = giki_sports_app`, `checkVal = 1`. Unreachable host test failed within 0.07s without leaking secrets. |
| Live API Probing on port 8081 | `backend/` | Verify live HTTP endpoints | **Passed:**<br/>- `/api/health` $\to$ `status: online`<br/>- `/api/ready` $\to$ `status: ready, database: connected`<br/>- `/api/facilities` $\to$ returned 9 items from JSON store |

---

## 3. Step 4A & 4A.1 Implementation & Migration Verification Outcomes

Step 4A and 4A.1 established a robust, repeatable PostgreSQL migration mechanism using Goose (`github.com/pressly/goose/v3` v3.29.0), decoupled from automatic application startup, hardened with explicit PostgreSQL advisory session locking, and verified via safe disposable test databases.

### 3.1 Migration Artifacts Added & Corrected
- **`backend/migrations/00001_create_giki_sports_schema.sql`:**
  - Forward migration (`-- +goose Up`): provisions dedicated namespace `CREATE SCHEMA IF NOT EXISTS giki_sports;`.
  - Reverse migration (`-- +goose Down`): corrected to `DROP SCHEMA IF EXISTS giki_sports RESTRICT;`. `RESTRICT` guarantees that rollback is rejected if any tables exist, preventing accidental data loss.
  - Strictly limited to schema creation; business tables (`users`, `sessions`, `facilities`, `bookings`) deferred to subsequent migrations.
- **`backend/internal/database/migration.go`:**
  - Created shared `MigrationRunner` wrapping `goose.Provider` configured explicitly with `lock.NewPostgresSessionLocker()`.
  - Guarantees PostgreSQL session-level advisory lock coordination across both CLI and tests.
- **`backend/cmd/migrate/main.go`:**
  - Dedicated CLI migration runner supporting `status`, `up`, and `down` (rolls back 1 migration).
  - Uses shared `database.NewMigrationRunnerFromDir` and connects via `database.NewSQLDB` using `pgx/v5/stdlib`.
  - Zero credential exposure: no connection strings in logs, flags, or process lists.
- **`backend/internal/database/database.go`:**
  - Added `NewSQLDB(ctx, cfg.DB)` for standard library `*sql.DB` consumers.
- **`backend/internal/database/migration_integration_test.go`:**
  - Hermetic integration suite guarded by `//go:build integration`:
    1. `TestMigrationIntegration_DisposableDatabaseCycle`: verifies initial `Up`, repeat `Up` (idempotency), `Status` version 1, `Down` on empty schema, and reapply `Up`.
    2. `TestMigrationIntegration_NonEmptySchemaRollbackRejected`: creates a probe table inside `giki_sports`, verifies that `Down` is rejected with SQLSTATE `2BP01`, verifies probe table and version 1 remain intact, drops probe table, and verifies empty-schema `Down` succeeds.
    3. `TestMigrationIntegration_ConcurrentMigrationsCoordinated`: spawns 5 concurrent workers attempting `runner.Up(ctx)`; verifies that session advisory locking coordinates execution so exactly 1 worker applies the migration while 4 detect zero pending, with zero duplicate rows in `goose_db_version`.
  - All tests enforce bounded cleanup contexts, close connections before dropping, report cleanup failures via `t.Errorf`, and only drop databases matching the `giki_sports_disposable_` prefix.
- **`docs/database-migrations.md`:**
  - Complete architecture, command reference, disposable DB verification, RESTRICT rationale, and port mismatch documentation.

### 3.2 Host Environment Configuration Note
During Step 4A, host drive `C:\` reached 0.00 GB free space (48 MB remaining), causing `go build` and module operations to fail with `There is not enough space on the disk`. Go environment paths were redirected to drive `D:\` (~20 GB free):
- `GOMODCACHE="D:\go\pkg\mod"`
- `GOCACHE="D:\go\cache"`
- `GOTMPDIR="D:\go\tmp"`
These settings remain active and will not be altered again.

### 3.3 Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages (server + migrate CLI) | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v ./...` | `backend/` | Unit test suites | **Passed (Exit 0):** All unit tests pass. |
| `go test -v -tags=integration ./internal/database/...` | `backend/` | All 5 database integration tests | **Passed (Exit 0):**<br/>- `TestPostgresIntegration_ConnectAndQuery` (0.08s)<br/>- `TestPostgresIntegration_UnreachableHostBoundedTimeout` (0.07s)<br/>- `TestMigrationIntegration_DisposableDatabaseCycle` (0.96s)<br/>- `TestMigrationIntegration_NonEmptySchemaRollbackRejected` (0.38s)<br/>- `TestMigrationIntegration_ConcurrentMigrationsCoordinated` (1.40s) |
| `go run ./cmd/migrate status` | `backend/` | Pre-migration development DB check | **Passed (Exit 0):** Showed version 1 applied. |
| `go run ./cmd/migrate up` | `backend/` | Up check on dev DB under advisory lock | **Passed (Exit 0):** Showed "no migrations to run" under advisory lock. |
| `psql -c "\dn"` | Development DB (`127.0.0.1:5434`) | Verify schema existence and ownership | **Passed:** `giki_sports` schema created, owned by `giki_sports_app`. Unrelated `public` schema preserved. |

---

## 4. Step 4B Implementation & Relational Schema Verification Outcomes

Step 4B established the core relational schema for `facilities` and `schedules` in `giki_sports` via migration `00002_create_facilities_and_schedules.sql`, verified through comprehensive constraint and lifecycle tests against disposable databases, and applied to the development database.

### 4.1 Schema Artifacts Added
- **`docs/facility-schedule-data-model.md`:**
  - Complete data contract defining all columns, types, nullability, defaults, foreign-key integrity, and constraint rationale.
  - Distinguishes confirmed requirements from implementation choices and unresolved institutional policies.
- **`backend/migrations/00002_create_facilities_and_schedules.sql`:**
  - `giki_sports.facilities`: UUID primary key, unique non-empty URL slug, non-empty name, description, location, operational status (`active`, `maintenance`, `closed`), and timestamptz audit columns.
  - `giki_sports.schedules`: UUID primary key, foreign key to facilities with `ON DELETE RESTRICT`, ISO-8601 day of week (1–7), local wall-clock times (`TIME`) with `start_time < end_time`, provisional audience vocabulary (`general`, `student`, `faculty`, `women_only`, `staff`), and unique window constraint (`facility_id, day_of_week, audience, start_time, end_time`).
  - Index: `idx_schedules_facility_id` on `giki_sports.schedules(facility_id)`.
  - Reverse migration: drops `schedules` then `facilities` with `RESTRICT` (no `CASCADE`).
- **`backend/internal/database/migration_integration_test.go`:**
  - Updated existing tests to use an in-memory single-migration fixture (`getMigration1FixtureFS`), preserving isolation for migration 1 assertions.
  - Added `TestMigrationIntegration_FacilitiesAndSchedulesLifecycle` verifying:
    - Table creation and foreign-key index existence.
    - Valid facility and schedule insertion.
    - Foreign-key rejection for unknown facility UUID.
    - Check constraint rejection for invalid weekday (0, 8), invalid time range (`start_time >= end_time`), invalid status, and invalid audience.
    - Unique constraint rejection for duplicate facility slugs and duplicate schedule windows.
    - Check constraint rejection for whitespace-only names and slugs.
    - Foreign-key `ON DELETE RESTRICT` rejection preventing direct deletion of a facility with active schedules.
    - Clean deletion after child schedule removal.
    - Migration 2 rollback (`down`): tables disappear, schema `giki_sports` and version 1 remain intact.
    - Migration 2 reapplication (`up`): tables restored, version 2 active.

### 4.2 Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v ./...` | `backend/` | Unit test suites | **Passed (Exit 0):** All unit tests pass. |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | All 6 database integration tests | **Passed (Exit 0):**<br/>- `TestPostgresIntegration_ConnectAndQuery` (0.07s)<br/>- `TestPostgresIntegration_UnreachableHostBoundedTimeout` (0.09s)<br/>- `TestMigrationIntegration_DisposableDatabaseCycle` (0.47s)<br/>- `TestMigrationIntegration_NonEmptySchemaRollbackRejected` (0.45s)<br/>- `TestMigrationIntegration_ConcurrentMigrationsCoordinated` (1.30s)<br/>- `TestMigrationIntegration_FacilitiesAndSchedulesLifecycle` (0.46s) |
| `go run ./cmd/migrate status` | `backend/` | Pre-migration development DB check | **Passed (Exit 0):** Showed version 1 applied, migration 2 pending. |
| `go run ./cmd/migrate up` | `backend/` | Apply migration 2 to development DB | **Passed (Exit 0):** Successfully migrated database to version 2 (117.6ms). |
| `go run ./cmd/migrate status` | `backend/` | Post-migration development DB check | **Passed (Exit 0):** Showed both version 1 and version 2 applied. |
| `psql -c "\dt giki_sports.*"` | Development DB (`127.0.0.1:5434`) | Verify table creation in development DB | **Passed:** Tables `facilities` and `schedules` exist, owned by `giki_sports_app`. |
| `SELECT count(*) FROM ...` | Development DB (`127.0.0.1:5434`) | Verify development tables are empty | **Passed:** Both `facilities` and `schedules` row counts equal 0. |

---

## 5. Step 4C Implementation & Read-Only Facility Repository Outcomes

Step 4C implemented a focused, typed, read-only PostgreSQL facility and schedule repository under `backend/internal/facility`, isolated from API handlers, frontend models, and mutations.

### 5.1 Artifacts Added
- **`backend/internal/facility/model.go`:**
  - `Facility`: typed domain read model matching `giki_sports.facilities` (UUID, Slug, Name, Description `*string`, Location `*string`, Status `OperationalStatus`, CreatedAt, UpdatedAt, Schedules `[]Schedule`).
  - `Schedule`: typed domain read model matching `giki_sports.schedules` (UUID, FacilityID, DayOfWeek `int`, StartTime `string`, EndTime `string`, Audience `string`, CreatedAt, UpdatedAt).
  - `OperationalStatus`: type-safe string alias (`active`, `maintenance`, `closed`).
  - `ErrNotFound` / `NotFoundError`: recognizable sentinel error for unresolvable slugs with `errors.Is` support.
  - Explicit `*string` representation for nullable database fields (`description`, `location`).
- **`backend/internal/facility/repository.go`:**
  - `Repository` interface declaring `List(ctx)` and `GetBySlug(ctx, slug)`.
  - `PostgresRepository` implementing `Repository` using existing `*pgxpool.Pool`.
  - **Bounded-Query Strategy (N+1 Prevention):**
    - `List` issues exactly 2 bounded queries regardless of facility count: (1) all facilities ordered by `name ASC, slug ASC`, (2) all schedules ordered by `facility_id, day_of_week, start_time`. Schedules are mapped in-memory in Go.
    - `GetBySlug` issues exactly 2 bounded queries: (1) single facility by slug, (2) schedules for that facility UUID.
  - **Read-Consistency Documentation:**
    - Queries run as separate `READ COMMITTED` statements against the pool and do **not** share a snapshot. If concurrent transactions commit between queries 1 and 2, query 2 reflects that committed state.
  - **PostgreSQL Time Representation:**
    - Uses SQL `to_char(start_time, 'HH24:MI:SS')` and `to_char(end_time, 'HH24:MI:SS')` scanned into string fields.
    - Accurately preserves the valid PostgreSQL end-of-day value `"24:00:00"` without wrapping to `"00:00:00"` or attaching an arbitrary calendar date.
  - **Safe Parameterized SQL & Row Lifecycle:**
    - All table references are schema-qualified (`giki_sports.facilities`, `giki_sports.schedules`).
    - Explicit column projections (`SELECT id, slug, ...`).
    - Always defers `rows.Close()` and checks `rows.Err()`.
    - Returns `[]Facility{}` (empty non-nil slice) when the database contains 0 facilities.
    - Always initializes `f.Schedules = make([]Schedule, 0)` so facilities without schedules have a non-nil slice.
- **`backend/internal/facility/repository_integration_test.go`:**
  - Opt-in integration suite (`//go:build integration`) using uniquely named disposable databases (`giki_sports_disposable_facrepo_<timestamp>`).
  - Applies real migrations 1 and 2 via `database.NewMigrationRunnerFromDir`.
  - Cleans up and forcefully drops disposable databases after each test.
  - 6 verified test cases:
    1. `TestFacilityRepository_EmptyDatabase`: Empty database returns empty slice; unknown slug returns `ErrNotFound`.
    2. `TestFacilityRepository_ListAndAssociations`: Multiple facilities, multiple schedules, deterministic ordering, facility with 0 schedules returns non-nil empty schedule list, no duplicate parent facilities.
    3. `TestFacilityRepository_GetBySlug_And_NullableFields`: Existing slug lookup; verifies non-null vs `nil` pointers for `description` and `location`; unknown slug returns `ErrNotFound`.
    4. `TestFacilityRepository_EndTime24AndOvernightWindow`: Preserves `"24:00:00"` on Saturday evening window and `"00:00:00"` to `"02:00:00"` on Sunday morning window.
    5. `TestFacilityRepository_SQLInjectionSafety`: Malicious slug payloads treated strictly as data; returns `ErrNotFound` without leaking rows or modifying tables.
    6. `TestFacilityRepository_CanceledContext`: Immediate context cancellation returns an error and nil data.

### 5.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -count=1 ./...` | `backend/` | Unit test suites | **Passed (Exit 0):** All unit tests pass. |
| `go test -v -count=1 -tags=integration ./internal/facility/...` | `backend/` | All 6 facility repository integration tests | **Passed (Exit 0):**<br/>- `TestFacilityRepository_EmptyDatabase` (1.00s)<br/>- `TestFacilityRepository_ListAndAssociations` (0.48s)<br/>- `TestFacilityRepository_GetBySlug_And_NullableFields` (0.40s)<br/>- `TestFacilityRepository_EndTime24AndOvernightWindow` (0.38s)<br/>- `TestFacilityRepository_SQLInjectionSafety` (0.37s)<br/>- `TestFacilityRepository_CanceledContext` (0.39s) |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | All 12 backend integration tests | **Passed (Exit 0):** Config, database migrations, and facility repository suites passed cleanly. |
| `psql -c "SELECT count(*) FROM giki_sports.facilities; ..."` | Development DB (`127.0.0.1:5434`) | Verify development tables remain empty | **Passed:** Facilities count = 0, Schedules count = 0. |

---

## 6. Query Planner & Index Performance Clarification

> [!NOTE]
> **Important Database Concept:** Indexes (such as `idx_schedules_facility_id`) provide potential access paths for lookups, joins, and foreign key constraint validations. However, **indexes do NOT guarantee query speed or index scans.**
> The PostgreSQL cost-based query planner analyzes table cardinality, statistics, page counts, and cost estimates. On small tables or queries fetching a substantial portion of rows, sequential scans (sequential reading of data blocks) require fewer disk page visits than reading an index page followed by random table heap visits. Consequently, PostgreSQL intentionally chooses sequential scans over index scans whenever sequential access is more optimal.

---

## 7. Known Mismatches & Configuration Warnings

- **Frontend Dev Proxy Port Mismatch:**
  - Backend runs on `PORT=8081` (in root `.env`) to avoid collision with `giki_wallet_backend` running on port 8080.
  - `frontend/vite.config.ts` currently proxies `/api` to `http://localhost:8080`.
  - Frontend code is intentionally unchanged during Step 4C to maintain atomic chunks. Target proxy port will be harmonized during frontend integration.

---

## 9. Step 4D Implementation & Demo Seeding Verification Outcomes

Step 4D implemented an explicit, atomic, repeatable development demonstration seeding command under `backend/cmd/seed` and core logic in `backend/internal/seed`.

### 9.1 Artifacts Added
- **`backend/internal/seed/seed.go`:**
  - `FacilityFixture` & `ScheduleFixture`: deterministic synthetic fixtures with stable UUIDs.
  - `DefaultDemoFixtures()`: returns two synthetic facilities (`demo-badminton-court`, `demo-table-tennis`) and 5 schedule windows covering varied weekdays and audiences (`student`, `faculty`, `women_only`, `general`).
  - `ApplyDemo(ctx, pool)` & `ApplyFixtures(ctx, pool, fixtures)`: executes within a single database transaction (`tx.Begin()`).
  - **Schema Pre-check:** verifies `giki_sports.facilities` and `giki_sports.schedules` exist using `to_regclass` before running inserts.
  - **Conflict & Idempotency Strategy:**
    - Queries existing records by `id = $1 OR slug = $2`.
    - If neither exists: inserts facility and child schedules.
    - If exact match on both ID and slug: skips facility and schedules, preserving any administrator edits without overwriting or recreating deleted schedules.
    - If ID matches with different slug, or slug matches with different ID: aborts with an actionable conflict error and rolls back the transaction.
- **`backend/cmd/seed/main.go`:**
  - CLI command requiring the explicit `--demo` flag (`go run ./cmd/seed --demo`).
  - Refuses to run without `--demo`, exiting with code 1.
  - Reuses `config.Load()` and `database.NewPool()`.
  - Outputs formatted summary (`Facilities: X inserted, Y skipped; Schedules: A inserted, B skipped`).
- **`backend/internal/seed/seed_integration_test.go`:**
  - Opt-in integration suite (`//go:build integration`) using disposable databases.
  - 6 comprehensive test scenarios:
    1. `TestSeedDemo_FirstAndRepeatedExecution`: verifies 2 facilities and 5 schedules inserted on run 1, 0 inserted and all skipped on run 2.
    2. `TestSeedDemo_PreservesAdministratorEdits`: verifies updated names/locations, modified schedule hours, deleted schedules, and custom added schedules are completely preserved on rerun.
    3. `TestSeedDemo_UnrelatedFacilityUntouched`: verifies pre-existing facilities and schedules remain untouched.
    4. `TestSeedDemo_ConflictingFixtureReportedWithoutPartialInserts`: verifies slug and ID collisions cause clear errors and roll back without partial inserts.
    5. `TestSeedDemo_MissingMigrationsFails`: verifies clear failure when schema migrations are missing.
    6. `TestSeedDemo_TransactionRollbackOnFailure`: verifies any database error rolls back all prior operations.
- **`docs/demo-data.md`:**
  - Complete documentation on running the seed command, fixture details, repeatable execution, administrator edit preservation, safe inspection commands, and limitations.

### 9.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -count=1 ./...` | `backend/` | Unit test suites | **Passed (Exit 0):** All unit tests pass. |
| `go test -v -count=1 -tags=integration ./internal/seed/...` | `backend/` | All 6 seed integration tests | **Passed (Exit 0):** All test cases passed against disposable databases. |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | All 18 backend integration tests | **Passed (Exit 0):** Config, migration, facility repo, and seed integration tests pass. |
| `go run ./cmd/seed` | `backend/` | Missing flag safety verification | **Passed (Exit 1):** Safely rejected with missing `--demo` error message. |
| `go run ./cmd/seed --demo` (Run 1) | `backend/` | Apply demo seed to development DB | **Passed (Exit 0):** Inserted 2 facilities, 5 schedules. |
| `go run ./cmd/seed --demo` (Run 2) | `backend/` | Repeat execution check on development DB | **Passed (Exit 0):** Skipped 2 facilities, 5 schedules (0 inserted, no duplicates). |
| `SELECT count(*) FROM ...` | Development DB (`127.0.0.1:5434`) | Verify row counts in development DB | **Passed:** Facilities count = 2, Schedules count = 5. |
| `facility.NewRepository.List(ctx)` | `backend/` | Repository read verification | **Passed:** Read 2 facilities with 5 nested schedules matching PostgreSQL rows. |

---

---

## 10. Step 4E Implementation & Facility HTTP API Integration Outcomes

Step 4E integrated the read-only PostgreSQL facility repository with the HTTP API layer, replacing the legacy JSON store facility GET handlers with typed, bounded, error-sanitized handlers.

### 10.1 Artifacts Added & Modified
- **`docs/facility-api.md`:**
  - Complete REST API contract specification for `GET /api/facilities` and `GET /api/facilities/:slug`.
  - Defined explicit DTO schemas with camelCase properties, nullable `*string` representations, and non-nil empty arrays (`[]`).
  - Documented ISO-8601 weekday conventions (1=Mon ... 7=Sun), Asia/Karachi (PKT, UTC+5) local wall-clock interpretation, and preservation of end-time `"24:00:00"`.
  - Clarified that operational `status` (`active`, `maintenance`, `closed`) is physical readiness and **not** computed real-time booking availability.
- **`backend/internal/facility/dto.go`:**
  - `FacilityResponse`: external JSON DTO matching API contract (`id`, `slug`, `name`, `description`, `location`, `status`, `schedules`).
  - `ScheduleResponse`: external JSON DTO matching API contract (`id`, `dayOfWeek`, `startTime`, `endTime`, `audience`).
  - `ErrorResponse`: standardized JSON error payload (`{"error": "<msg>"}`).
  - Mapping functions `ToFacilityResponse` and `ToFacilityResponses` guaranteeing non-nil empty slices (`[]`).
- **`backend/internal/facility/handler.go`:**
  - `Reader` interface: depends only on the minimal read methods needed (`List`, `GetBySlug`).
  - `Handler` struct with configurable query timeout (`default 5s`).
  - `RegisterRoutes(api)`: registers `GET /facilities` and `GET /facilities/:slug`.
  - Enforces bounded request context using `c.UserContext()` and explicit timeouts.
  - Sanitizes internal database errors: maps `ErrNotFound` to HTTP 404, `context.DeadlineExceeded` to HTTP 503, and generic errors to HTTP 500 without leaking SQL text, credentials, or schema names.
- **`backend/internal/facility/handler_test.go`:**
  - 9 focused unit tests using an in-memory `fakeReader`:
    - List success with exact camelCase JSON property verification
    - Empty list marshals as exact `[]` JSON
    - Detail lookup with `"24:00:00"` preservation
    - Facility without schedules marshals `schedules` as `[]` (not `null`)
    - Nullable fields marshal as `null` in JSON
    - Unknown slug returns HTTP 404 `{"error": "facility not found"}`
    - Internal error does not leak SQL, passwords, or raw text (HTTP 500)
    - Context deadline maps to HTTP 503 `{"error": "service unavailable: request timed out"}`
    - Repository calls receive a properly bounded context
- **`backend/internal/facility/http_integration_test.go`:**
  - Opt-in HTTP integration test (`//go:build integration`) exercising the Fiber app with real PostgreSQL pool and migrations against disposable databases.
- **`backend/main.go`:**
  - Replaced legacy JSON-store facility GET routes with `facilityHandler.RegisterRoutes(api)`.
  - Preserved existing JSON storage for bookings, memberships, achievements, announcements, and stats.

### 10.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./...` | `backend/` | All unit test suites | **Passed (Exit 0):** Config (3 tests) and Facility handler (9 tests) pass. |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | All integration test suites | **Passed (Exit 0):** 31 total tests across config, migrations, facility repo, HTTP integration, and seed pass. |
| `GET /api/health` | `http://127.0.0.1:8081` | Verify live server health | **Passed (HTTP 200):** Returned online status. |
| `GET /api/facilities` | `http://127.0.0.1:8081` | Verify live facilities list from PostgreSQL | **Passed (HTTP 200):** Returned 2 seeded demonstration facilities with schedules. |
| `GET /api/facilities/demo-badminton-court` | `http://127.0.0.1:8081` | Verify live facility detail by slug | **Passed (HTTP 200):** Returned demo badminton court with 3 schedules. |
| `GET /api/facilities/does-not-exist` | `http://127.0.0.1:8081` | Verify missing slug error handling | **Passed (HTTP 404):** Returned `{"error":"facility not found"}`. |
| `GET /api/bookings` | `http://127.0.0.1:8081` | Verify non-facility endpoints continue using JSON | **Passed (HTTP 200):** Returned legacy bookings from `store.json`. |

---

## 11. Storage Layer Reality & Known Boundaries

> [!IMPORTANT]
> **Storage Layer Transition Reality:**
> 1. **PostgreSQL Relational Storage:** `/api/facilities` and `/api/facilities/:slug` query the live PostgreSQL database via `facility.PostgresRepository`.
> 2. **JSON Storage Boundaries:** `/api/bookings`, `/api/memberships`, `/api/achievements`, `/api/announcements`, and `/api/stats` continue to serve from `backend/data/store.json`. Facility counts and identifiers between relational facilities and legacy bookings may differ during this transition.
> 3. **Frontend Display Alignment (Step 5 Resolved):**
>    - `frontend/src/types.ts` is fully aligned with the relational DTO schema (`id`, `slug`, `name`, `description`, `location`, `status`, `schedules`).
>    - Runtime response validation (`parseFacilities`, `parseFacility`) prevents malformed JSON crashes.
>    - Hardcoded mock fallback was completely removed; errors surface with actionable retry buttons.
>    - `frontend/vite.config.ts` development proxy targets `http://127.0.0.1:8081`.
>    - The frontend website is verified and fully functional in the browser.

---

## 12. Step 5 Implementation & Verification Outcomes

Step 5 aligned the React frontend with the PostgreSQL facility API, eliminated mock fallbacks, safeguarded time formatting without Date wrap-around, and established automated frontend testing with Vitest and React Testing Library.

### 12.1 Frontend Files Added & Updated
- **`frontend/src/types.ts`:**
  - Typed `Facility`, `Schedule`, `OperationalStatus`, and `AudienceType` matching `docs/facility-api.md`.
  - Focused runtime type guards (`isSchedule`, `isFacility`) and parsers (`parseFacility`, `parseFacilities`).
  - Helper `formatTimeRange(start, end)` preserving end-of-day `"24:00:00"` as `"24:00 (Midnight)"` without Date parsing.
  - Retained `LegacyFacility` to preserve TypeScript compatibility with legacy fixtures.
- **`frontend/src/api.ts`:**
  - Added typed `ApiError(status, message)` capturing HTTP status codes.
  - Safe URL construction using `encodeURIComponent(slug.trim())`.
  - AbortSignal support via `{ signal?: AbortSignal }` on all requests.
  - Completely removed mock data fallback; invalid responses and network failures throw errors.
- **`frontend/src/components/FacilityCard.tsx`:**
  - Rendered live name, location, operational status badge, and schedule count.
  - Neutral Lucide `Activity` icon replacing brittle icon-key mappings.
  - Links to `/facilities/${facility.slug}`.
- **`frontend/src/components/FacilitiesGrid.tsx`:**
  - Implemented distinct loading, empty, error (with retry button), and success states.
- **`frontend/src/components/StatsStrip.tsx`:**
  - Derived facility count dynamically from `facilities.length` when live facilities are loaded.
- **`frontend/src/pages/Home.tsx`:**
  - Live data fetching via `api.getFacilities` with `AbortController` cancellation on unmount and error retry.
- **`frontend/src/pages/FacilityDetail.tsx`:**
  - Fetches by route slug with `AbortController` cancellation on slug change.
  - Clears stale data when slug changes to avoid showing old facility info.
  - Distinguishes HTTP 404 ("Facility Not Found") from HTTP 500/network failures (with retry button).
  - Displays structured weekly timetable with Asia/Karachi wall-clock notice.
  - Removed nonfunctional "Book a session" button and mock coach/gallery sections.
- **`frontend/vite.config.ts`:**
  - Proxy target updated to `http://127.0.0.1:8081`.
  - Configured Vitest `jsdom` testing environment and setup file.
- **`frontend/src/test/`:**
  - `validation.test.ts`: 12 tests verifying runtime validation, schema enforcement, and time range formatting.
  - `FacilityList.test.tsx`: 4 tests verifying loading, empty, card navigation slug links, error, and retry recovery.
  - `FacilityDetail.test.tsx`: 6 tests verifying success render, nullable fields, empty schedules, 404 not found, server error retry, and request cancellation on route switch.

### 12.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `npm test` | `frontend/` | Run automated Vitest test suite | **Passed (Exit 0):** 3 test files, 22 tests passed. |
| `npm run build` | `frontend/` | TypeScript checks (`tsc -b`) and Vite production bundle | **Passed (Exit 0):** Zero errors; 1933 modules transformed. |
| Browser Live Verification | `http://localhost:5173/` | Browser subagent UI walkthrough | **Passed:** Verified live homepage cards, detail page navigation, 404 error page, mobile and desktop viewports, zero console errors. |

---

## 13. Step 6A Implementation & Verification Outcomes

Step 6A established the relational database schema and security invariants for user accounts, role assignments, and server-side sessions in PostgreSQL without building login endpoints or password hashers yet.

### 13.1 Files Added & Updated
- **`docs/auth-data-model.md`:**
  - Defined authentication data contract distinguishing account identity, role assignments, password hash storage, session tokens vs. token hashes, idle vs. absolute timeouts, and account deactivation vs. session revocation.
  - Preserved distinct `sports_director` and `super_admin` administrative roles.
  - Documented cashier authority as an explicit future permission under Module 5.
  - Clarified database-enforced rules vs. application-enforced rules.
- **`backend/migrations/00003_create_users_and_sessions.sql`:**
  - `giki_sports.users`: UUID PK, required non-empty trimmed `email`, `display_name`, `password_hash`, status check (`active`, `inactive`), and functional unique index `uq_users_email_lower` on `LOWER(TRIM(email))`.
  - `giki_sports.user_roles`: UUID PK, FK to `users(id)` `ON DELETE RESTRICT`, unique `(user_id, role)`, and role check (`student`, `faculty`, `sports_director`, `super_admin`). Supports multiple roles per user.
  - `giki_sports.sessions`: UUID PK, FK to `users(id)` `ON DELETE RESTRICT`, unique `token_hash`, non-empty check, index `idx_sessions_user_id`, and timestamp ordering checks (`last_activity_at >= created_at`, `absolute_expires_at > created_at`, `revoked_at >= created_at`).
  - Reverse migration: drops `sessions`, `user_roles`, and `users` using `RESTRICT`.
- **`backend/internal/database/migration.go`:**
  - Added `UpTo(ctx, version)` method to `MigrationRunner` for explicit target migration execution.
- **`backend/internal/database/migration_integration_test.go`:**
  - Added `getMigration1And2FixtureFS(t)` helper to keep tests targeting earlier migrations isolated without weakening assertions.
  - Added `TestMigrationIntegration_UsersAndSessionsLifecycle(t *testing.T)` covering: valid synthetic user/role/session records, case-insensitive duplicate email rejection, blank field rejection, invalid roles/statuses, unknown user references, duplicate session token-hash rejection, invalid timestamp ordering, restrictive parent deletion, migration 3 rollback preserving facility/schedule tables and data, and clean reapplication.

### 13.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./...` | `backend/` | Unit tests across all packages | **Passed (Exit 0):** Config (3 tests) and Facility handler (9 tests) passed. |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | Complete integration test suite | **Passed (Exit 0):** 32 total tests across database migrations, facility repository, HTTP integration, and seed passed. |
| `go run ./cmd/migrate up` | `backend/` | Apply migration 3 to development DB | **Passed (Exit 0):** Applied `00003_create_users_and_sessions.sql`. |
| Row Count Verification | Development PostgreSQL | Verify table state | **Passed:** `facilities` (2), `schedules` (5), `users` (0), `user_roles` (0), `sessions` (0). |

---

## 14. Step 6B Implementation & Verification Outcomes

Step 6B implemented focused, cryptographically sound, and defensively bounded Argon2id password hashing and verification in Go (`backend/internal/auth`) without database, session, endpoint, or frontend coupling.

### 14.1 Files Added & Updated
- **`backend/internal/auth/password.go`:**
  - Implements standard RFC 9106 string encoding: `$argon2id$v=19$m=65536,t=3,p=4$<b64salt>$<b64hash>`.
  - Defined explicit parameter structures:
    - `DefaultParams`: `Memory = 65536 KiB` (64 MiB), `Iterations = 3`, `Parallelism = 4`, `SaltLength = 16`, `KeyLength = 32`.
    - `TestParams`: `Memory = 8192 KiB` (8 MiB), `Iterations = 1`, `Parallelism = 2`, `SaltLength = 16`, `KeyLength = 32` (for fast unit testing).
  - Validation before hashing: rejects out-of-bound parameters, empty passwords, and passwords exceeding technical length limit (1024 bytes).
  - `Hash(password)` and `HashWithParams(password, params, randReader)`: uses `crypto/rand` (or custom reader for testing), runs `argon2.IDKey(..., argon2.Version)`.
  - `Verify(password, encodedHash)`: constant-time verification using `crypto/subtle.ConstantTimeCompare`.
  - Defensive parsing (`ParseHash`): rejects invalid algorithms, unsupported versions, duplicate or malformed parameter keys, non-numeric values, invalid base64 encoding, mismatched salt/key lengths, and out-of-bound resource requests (`8192 <= m <= 262144`, `1 <= t <= 10`, `1 <= p <= 16`) **prior** to executing `argon2.IDKey`.
- **`backend/internal/auth/password_test.go`:**
  - Comprehensive unit test suite covering:
    - Matching passwords return `match = true, err = nil`.
    - Incorrect passwords return `match = false, err = nil`.
    - Identical passwords produce different salted hashes.
    - Exact preservation of Unicode and whitespace (spaces, tabs, newlines, multi-byte UTF-8).
    - Defensive rejection of 16 malformed hash string formats (unknown algorithm, wrong version, invalid parameters, corrupted base64, truncated parts).
    - Defensive rejection of 6 excessive/out-of-bounds parameter configurations before hashing.
    - Clean handling of salt-generation entropy errors using mock reader.
    - Technical password length limit validation (> 1024 bytes).
    - Full round-trip verification using production `DefaultParams` (64 MiB, 3 passes, 4 threads).
- **`backend/go.mod` & `backend/go.sum`:**
  - Added `golang.org/x/crypto v0.58.0` while strictly preserving Goose pinned at `v3.29.0`.
- **`docs/password-hashing.md`:**
  - Comprehensive documentation covering Wallet inspection and code adaptation, Argon2id parameter choices and resource costs, string encoding format, defensive parsing rules, test verification results, and security boundaries.
- **`docs/auth-data-model.md`:**
  - Refined security statements: corrected absolute claims regarding database unique constraints (prevents duplicate storage, not theoretical mathematical collisions), session token hashing (limits damage from read-only DB leaks, does not prevent active interception), and server-side sessions (selected implementation, without claiming JWT systems cannot support revocation).

### 14.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/auth/...` | `backend/` | Password auth unit test suite | **Passed (Exit 0):** All 8 test suites passed in 0.32s. |
| `go test -v -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** Config, Facility, and Auth unit tests passed. |

---

## 15. Step 6C Implementation & Verification Outcomes

Step 6C implemented cryptographically secure, opaque session token generation, strict format validation, and SHA-256 digest derivation in Go (`backend/internal/auth`) without database, session lifecycle, endpoint, or frontend coupling.

### 15.1 Files Added & Updated
- **`backend/internal/auth/token.go`:**
  - Implemented high-entropy session token generation (`GenerateSessionToken`, `GenerateSessionTokenWithReader`) drawing 32 bytes from `crypto/rand`.
  - Encoded raw tokens as 43-character unpadded URL-safe Base64 strings (`base64.RawURLEncoding`).
  - Derived 64-character lowercase hexadecimal SHA-256 digests (`hex.EncodeToString(sum[:])`) matching `giki_sports.sessions.token_hash`.
  - Documented explicit hashing convention: SHA-256 operates on the canonical ASCII bytes of the unpadded URL-safe Base64 token string (`[]byte(token)`), matching GIKI Wallet's `sha256Hex(token)` pattern.
  - Implemented strict format validation (`ValidateSessionToken`) checking non-empty, exact 43-character length, URL-safe alphabet, absence of `=` padding, exact 32 decoded bytes, and strict canonicity (detects unused-bit malleability in the 43rd character).
  - Implemented `HashSessionToken(candidateToken)` that runs strict format validation before computing the digest.
  - Error safety: all error returns use static sentinel errors (`ErrTokenEmpty`, `ErrInvalidTokenLength`, `ErrInvalidTokenFormat`, `ErrNonCanonicalToken`, `ErrEntropyReadFailed`) with zero candidate token interpolation.
- **`backend/internal/auth/token_test.go`:**
  - Comprehensive unit test suite covering:
    - Freshly generated token format (43 chars), hash format (64 hex chars), 32 decoded bytes, validation success, and recomputed hash equality.
    - Deterministic entropy testing using known vectors (32 zero bytes $\to$ 43 'A's, sequential bytes 0x00..0x1F) verified against independent SHA-256 calculations.
    - Idempotency: repeated hashing of one token returns identical digests across multiple calls.
    - Table-driven rejection of 11 malformed/non-canonical candidates (empty, short, long, padded, `+`, `/`, whitespace, punctuation, non-canonical bits).
    - Entropy source error handling: nil reader, simulated hardware read failure, and short reads (16 bytes).
    - Error string leakage prevention: confirms sensitive candidate tokens never appear in error messages.
- **`docs/session-tokens.md`:**
  - Created architectural specification documenting GIKI Wallet inspection (`auth/service.go` and `user/service.go`), code reuse and adaptations, exact formats, hashing convention, validation rules, test outcomes, and security boundaries.
- **`docs/password-hashing.md`:**
  - Corrected security and performance claims: clarified that salts prevent rainbow tables across users but do not prevent offline password guessing; noted that parameter bounds protect against single malicious hashes but do not eliminate aggregate resource-exhaustion risk; and documented that benchmark test timings are local development host observations rather than contractual guarantees.

### 15.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/auth/...` | `backend/` | Auth unit test suite (Argon2id + Session Tokens) | **Passed (Exit 0):** All 14 test functions (38 subtests) passed. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** `config`, `facility`, and `auth` unit tests passed. |

---

## 16. Step 6D Implementation & Verification Outcomes

Step 6D implemented the read-only PostgreSQL repository for user identities, account statuses, and assigned roles in Go (`backend/internal/user`), strictly separating standard user read models from internal credential verification queries.

### 16.1 Files Added & Updated
- **`backend/internal/user/model.go`:**
  - Defined `AccountStatus` (`active`, `inactive`) and `Role` (`student`, `faculty`, `sports_director`, `super_admin`).
  - Implemented `User` domain read model: strictly omits `PasswordHash` to prevent credential exposure in application layers or profile serialization.
  - Implemented `UserCredentials` internal credential model: contains `User` and `PasswordHash` (tagged `json:"-"`), with `String()` and `GoString()` implementations masking hashes with `[REDACTED]`.
  - Implemented `NormalizeEmail`: trims whitespace and lowercases input matching database functional index `uq_users_email_lower`.
  - Implemented sentinel `ErrNotFound` and structured `NotFoundError`.
- **`backend/internal/user/model_test.go`:**
  - Unit tests covering email normalization edge cases, credential redaction across formatters (`%s`, `%v`, `%+v`, `%#v`), JSON exclusion of `PasswordHash`, and `errors.Is(err, ErrNotFound)` semantics.
- **`backend/internal/user/repository.go`:**
  - Implemented `Repository` interface backed by `pgxpool.Pool`:
    - `GetByEmail(ctx, email) (*User, error)`
    - `GetByID(ctx, id uuid.UUID) (*User, error)`
    - `GetCredentialsByEmail(ctx, email) (*UserCredentials, error)`
  - Query strategy: single parameterized query with `LEFT JOIN` and `ORDER BY r.role ASC`.
  - Read-consistency guarantee: single statement-level snapshot eliminates read skew between user profile and role assignments without N+1 query overhead.
  - Returns empty, non-nil slice (`[]Role{}`) when a user has no assigned roles.
  - Inactive accounts remain readable with `StatusInactive`; rejection is deferred to auth service.
  - SQL-safe positional parameterization (`$1`).
- **`backend/internal/user/repository_integration_test.go`:**
  - Opt-in integration test suite (`//go:build integration`) exercising disposable databases (`giki_sports_disposable_userrepo_*`):
    - Verified lookup by ID and email on active fixture.
    - Verified case/whitespace email normalization.
    - Verified unknown email, unknown UUID, `uuid.Nil`, and empty email return `ErrNotFound`.
    - Verified multi-role aggregation with deterministic alphabetical ordering (`[faculty, sports_director]`).
    - Verified user with no roles returns empty, non-nil `Roles` slice.
    - Verified inactive account status remains visible.
    - Verified `GetCredentialsByEmail` returns synthetic hash internally while `GetByEmail` excludes it.
    - Verified SQL-injection email inputs are safely treated as literal data.
    - Verified context cancellation returns `context.Canceled`.
    - Verified development database was completely unmutated.
- **`docs/user-repository.md`:**
  - Created architectural documentation detailing Wallet query inspection, method contracts, credential isolation, normalization, snapshot consistency, test results, and remaining boundaries.
- **`docs/session-tokens.md`:**
  - Refined factual wording: documented Base64url as a convenient transport encoding without claiming standard Base64 is universally invalid in cookies; clarified that token hashing reduces read-only database leak exposure without preventing every compromise scenario; and removed unsupported universal claims.

### 16.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/user/...` | `backend/` | User package unit tests | **Passed (Exit 0):** All 3 unit tests (9 subtests) passed. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** `config`, `facility`, `auth`, and `user` passed. |
| `go test -v -count=1 -tags=integration ./internal/user/...` | `backend/` | PostgreSQL user repository integration test | **Passed (Exit 0):** All 9 integration subtests passed against disposable DB in 5.27s; dev DB verified untouched. |

---

## 17. Step 6E Implementation & Verification Outcomes

Step 6E implemented the PostgreSQL session repository backed by `pgxpool.Pool` targeting `giki_sports.sessions` (`backend/internal/session`), enforcing dual-timeout evaluation (30-minute idle, 8-hour absolute ceiling), atomic concurrent activity updates, and idempotent session revocation without raw token exposure.

### 17.1 Files Added & Updated
- **`backend/internal/auth/token.go` & `backend/internal/auth/token_test.go`:**
  - Added `ValidateTokenHash(tokenHash string) error` checking 64 lowercase hexadecimal characters.
  - Added unit test suite `TestToken_ValidateTokenHash` verifying format rejection (length, uppercase, non-hex, spaces).
- **`backend/internal/session/model.go`:**
  - Defined lifetime constants: `IdleTimeout = 30 * time.Minute` and `AbsoluteLifetime = 8 * time.Hour`.
  - Defined sentinel errors: `ErrInvalidSession`, `ErrInvalidTokenHash`, `ErrUserNotFoundOrInactive`.
  - Defined `Session` domain read model: strictly omits `token_hash` from fields and JSON tags.
  - Defined `SessionRecord` model for testing and lifecycle inspection (includes nullable `RevokedAt`).
  - Defined `Clock` interface and `RealClock` implementation for deterministic point-in-time testing.
- **`backend/internal/session/model_test.go`:**
  - Unit tests verifying constants, JSON omission of token hashes, and `RealClock` UTC generation.
- **`backend/internal/session/repository.go`:**
  - Implemented `Repository` interface: `Create`, `CreateAt`, `ValidateAndTouch`, `ValidateAndTouchAt`, `Revoke`, `RevokeAt`, `GetSessionRecord`.
  - `CreateAt`: atomically inserts into `giki_sports.sessions` via `SELECT ... FROM users WHERE id = $1 AND status = 'active'`, setting `created_at` and `last_activity_at` to the identical instant and `absolute_expires_at = now + 8h`. Rejects unknown or inactive users.
  - `ValidateAndTouchAt`: executes a single atomic conditional SQL statement with row-level locking on `sessions`:
    - Evaluates `s.revoked_at IS NULL`, `u.status = 'active'`, `now >= s.created_at`, `now < s.last_activity_at + 30m`, and `now < s.absolute_expires_at`.
    - Updates `last_activity_at = GREATEST(s.last_activity_at, now)` monotonically.
    - If any condition fails, 0 rows are updated, stored activity remains unchanged, and `ErrInvalidSession` is returned.
  - `RevokeAt`: idempotently sets `revoked_at = COALESCE(revoked_at, now)`, preserving the first revocation timestamp.
- **`backend/internal/session/repository_integration_test.go`:**
  - Opt-in integration test suite (`//go:build integration`) exercising disposable databases (`giki_sports_disposable_sessrepo_*`):
    - Verified session creation and exact 8-hour lifetime.
    - Verified unknown and inactive user creation rejection.
    - Verified successful validation updates activity without extending absolute expiry.
    - Verified idle expiry boundaries: $-1\mu\text{s}$ succeeds, exact $30\text{m}$ fails, $+1\mu\text{s}$ fails; verified rejected validation leaves stored activity unchanged.
    - Verified absolute expiry boundaries: $-1\mu\text{s}$ succeeds, exact $8\text{h}$ fails, $+1\mu\text{s}$ fails.
    - Verified revocation, repeated revocation preserving original timestamp, and subsequent validation rejection.
    - Verified immediate validation rejection upon user account deactivation.
    - Verified concurrent validations preserve monotonic activity using synchronization barriers.
    - Verified validation/revocation concurrency cannot revive a revoked session.
    - Verified invalid hash format rejection and context cancellation.
    - Verified development database records remained 0 before and after tests.
- **`docs/session-repository.md`:**
  - Created architectural specification detailing Wallet inspection, method contracts, dual-timeout lifecycle, locking strategy, testability via clock injection, and verification results.

### 17.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/session/...` | `backend/` | Session package unit tests | **Passed (Exit 0):** All 3 unit tests passed. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** All 5 packages (`auth`, `config`, `facility`, `session`, `user`) passed. |
| `go test -v -count=1 -tags=integration ./internal/session/...` | `backend/` | PostgreSQL session repository integration test | **Passed (Exit 0):** All 10 integration subtests passed against disposable DB in 1.21s; dev DB verified untouched. |

---

## 18. Step 6E.1 Implementation & Verification Outcomes

Step 6E.1 corrected session validation timestamp sampling during lock waits. Previously, `r.clock.Now()` was sampled before issuing SQL; if the query waited for a session-row lock held by a concurrent validation or revocation, the timestamp aged and could evaluate validity against a stale instant.

### 18.1 Files Modified & Structural Enhancements
- **`backend/internal/session/model.go` & `backend/internal/session/model_test.go`:**
  - Added `TestClock` implementing `session.Clock` with thread-safe `.Now()`, `.Set(t)`, and `.Advance(d)` methods for deterministic timing simulation without sleeps.
  - Added unit test `TestSession_TestClock` verifying controllable simulated time.
- **`backend/internal/session/repository.go`:**
  - Restructured `ValidateAndTouch` to execute inside a short database transaction:
    1. Finds and locks the session row via `SELECT ... FOR UPDATE OF s`.
    2. Samples `r.clock.Now()` strictly **after** the row lock is granted by PostgreSQL.
    3. Checks revocation (`revoked_at IS NULL`), active account (`status = 'active'`), and dual timeouts (30-minute idle, 8-hour absolute ceiling) against the post-lock timestamp.
    4. Updates activity only when valid via `UPDATE giki_sports.sessions SET last_activity_at = GREATEST(last_activity_at, $2) WHERE id = $1 RETURNING last_activity_at`.
    5. Commits the transaction before returning success. If any check fails, rolls back immediately, leaving stored activity completely unchanged and returning `ErrInvalidSession`.
  - Accurately documented row-locking semantics: `FOR UPDATE OF s` locks *only* the session row `s`. The joined user row `u` is not locked; its status is evaluated under the transaction's snapshot. Concurrent user deactivation does not block on the session lock; once committed, subsequent validations immediately see `status = 'inactive'`.
  - Accurately documented revocation semantics: coordinates on the exact same session-row lock; touching activity never clears revocation; explicit logout does not retroactively cancel already authenticated requests that are currently in flight.
  - Explicitly labeled `ValidateAndTouchAt` as a test helper that bypasses dynamic clock sampling.
- **`backend/internal/session/repository_integration_test.go`:**
  - Added `waitForBlockedSession` querying `pg_stat_activity` with `pg_blocking_pids` to explicitly confirm a transaction is waiting for a row lock in PostgreSQL without relying on sleeps.
  - Added 3 deterministic regression tests:
    - `LockWait_IdleExpiry_SamplesClockAfterLock_AndRejects`: Held session-row lock in blocker transaction; began validation just before idle expiry; verified actively blocked via `waitForBlockedSession`; advanced fake clock to idle expiry boundary; released lock; verified validation was rejected with `ErrInvalidSession` and activity in DB remained at `t0`.
    - `LockWait_AbsoluteExpiry_SamplesClockAfterLock_AndRejects`: Maintained active session up to 7h45m; held session-row lock; began validation just before 8h absolute expiry; verified actively blocked; advanced fake clock to 8h boundary; released lock; verified validation rejected with `ErrInvalidSession` and activity remained at 7h55m.
    - `LockWait_ContextCancellation_ReleasesResources`: Held session-row lock; began validation with cancelable context; verified actively blocked; canceled context; verified validation returned `context.Canceled`; released blocker; verified connection pool and database remained healthy and responsive.
- **`docs/session-repository.md`:**
  - Updated specification with corrected short transaction sequence, post-lock timing, row-level locking scope, account-status lookup semantics, and actual regression test results.

### 18.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/session/...` | `backend/` | Session package unit tests | **Passed (Exit 0):** All 4 unit tests passed. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** All 5 packages (`auth`, `config`, `facility`, `session`, `user`) passed. |
| `go test -v -count=1 -tags=integration ./internal/session/...` | `backend/` | PostgreSQL session repository integration test | **Passed (Exit 0):** All 13 integration subtests passed against disposable DB in 1.56s; dev DB verified untouched. |

---

## 19. Step 6F Implementation & Verification Outcomes

Step 6F implemented the core authentication orchestration service (`backend/internal/authentication`), coordinating credential lookup, Argon2id verification, session creation, atomic session validation, and server-side session revocation.

### 19.1 Architectural Elements & Files Added
- **`backend/internal/authentication/service.go`:**
  - Defined consumer-owned repository interfaces:
    - `UserCredentialRepository`: `GetCredentialsByEmail(ctx, email)`, `GetByID(ctx, id)`.
    - `SessionStore`: `Create(ctx, userID, tokenHash)`, `ValidateAndTouch(ctx, tokenHash)`, `Revoke(ctx, tokenHash)`.
  - Defined domain sentinel errors:
    - `ErrInvalidCredentials`: returned uniformly for unknown emails, wrong passwords, and inactive user accounts to mitigate account enumeration.
    - `ErrInvalidSession`: returned uniformly for malformed, unknown, expired, or revoked session tokens, as well as missing or inactive users.
    - `ErrInternal`: returned for unexpected data corruption or malformed stored password hashes.
  - Implemented `Login(ctx, email, password)`:
    - Normalizes email via `user.NormalizeEmail`.
    - Looks up user credentials via `userRepo.GetCredentialsByEmail`.
    - Mitigates fast-path account enumeration: for unknown and inactive users, executes a dummy Argon2id verification using a precomputed hash derived once at service startup (`NewService`).
    - Verifies password with `auth.Verify(password, creds.PasswordHash)`. Malformed stored hashes return `ErrInternal`.
    - Generates 32-byte cryptographic token and SHA-256 hash via `auth.GenerateSessionToken()` only after credentials pass.
    - Persists session in `sessionRepo.Create`. Concurrent account deactivations map to `ErrInvalidCredentials`.
    - Returns `LoginResult` containing `RawToken` (strictly for Set-Cookie issuance, tagged with `json:"-"` and masked in `fmt` formatters), public user profile, and session metadata.
  - Implemented `ValidateSession(ctx, rawToken)`:
    - Verifies token format via `auth.ValidateSessionToken(rawToken)`.
    - Derives lowercase hex SHA-256 digest via `auth.HashSessionToken(rawToken)`.
    - Validates session and touches activity using production `sessionRepo.ValidateAndTouch` under row-level lock.
    - Loads up-to-date user profile and assigned roles via `userRepo.GetByID`.
    - Returns `AuthenticatedPrincipal` excluding credentials, tokens, and hashes.
  - Implemented `Logout(ctx, rawToken)`:
    - Hashes token and revokes session via `sessionRepo.Revoke`.
    - Treats malformed, unknown, and already revoked tokens as harmless idempotent repeated logout.
    - Propagates genuine database and context failures.
- **`backend/internal/authentication/service_test.go`:**
  - Unit tests verifying login success, uniform credential rejection, dummy verification invocation, token generation avoidance on failure, entropy and persistence failure handling, malformed stored hash error wrapping, session validation with current roles, missing/inactive user rejection, fast-fail on malformed tokens, idempotent logout, and credential isolation in formatting/JSON.
- **`backend/internal/authentication/service_integration_test.go`:**
  - Opt-in integration tests (`//go:build integration`) exercising disposable databases (`giki_sports_disposable_authsvc_*`):
    - Verified full login flow against real Argon2id hash and user roles.
    - Verified database table `giki_sports.sessions` persisted the SHA-256 token hash, not the raw token.
    - Verified session validation returning principal with current roles.
    - Verified wrong password and unknown user rejection.
    - Verified idle timeout rejection using injected fake clock without thread sleeps.
    - Verified server-side session revocation on logout and subsequent validation rejection.
    - Verified development database was completely unmutated.
- **`docs/authentication-service.md`:**
  - Created architectural documentation detailing contracts, dependency direction, Wallet inspection & adaptations, enumeration defense limits, and verification results.

### 19.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/authentication/...` | `backend/` | Authentication package unit tests | **Passed (Exit 0):** All 6 unit tests (17 subtests) passed. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** All 6 packages (`auth`, `authentication`, `config`, `facility`, `session`, `user`) passed. |
| `go test -v -count=1 -tags=integration ./internal/authentication/...` | `backend/` | PostgreSQL authentication service integration test | **Passed (Exit 0):** All 5 integration subtests passed against disposable DB in 1.74s; dev DB verified untouched. |

---

## 20. Step 6G Implementation & Verification Outcomes

Step 6G implemented the HTTP authentication endpoints, session cookie management, exact CSRF origin verification, and abuse protection controls for the GIKI Sports Complex Management System.

### 20.1 Files Modified & Created
- **`backend/internal/authentication/dto.go`:**
  - `LoginRequest`: strictly accepts `email` and `password`.
  - `UserResponse`: public user representation (`id`, `email`, `displayName`, `roles`); strictly excludes raw tokens, password hashes, and session metadata.
  - `ErrorResponse`: uniform JSON error payload.
- **`backend/internal/authentication/cookie.go`:**
  - `CookieManager`: centralizes session cookie issuance (`SetSessionCookie`) and clearing (`ClearSessionCookie`).
  - Strict attributes: `HttpOnly=true`, `SameSite=Lax`, `Path=/api`, `Domain=""` (omitted for host-only scoping), `MaxAge=28800` (8 hours).
  - Configurable `Secure` mode: `AUTH_COOKIE_SECURE=false` for local HTTP development; `true` for production TLS.
  - `ValidateOrigin`: exact canonical `Origin` header validation against trusted origins list; rejects missing, null, malformed, or untrusted origins; no substring matching.
- **`backend/internal/authentication/handler.go`:**
  - Consumer-owned `Authenticator` interface (`Login`, `ValidateSession`, `Logout`).
  - `Login (POST /api/auth/login)`:
    - Sets `Cache-Control: no-store` and `Pragma: no-cache`.
    - Validates exact `Origin` header (403 on failure).
    - Requires `Content-Type: application/json` (415 on failure).
    - Limits body size to 4096 bytes (413 on failure).
    - Deserializes JSON and enforces technical input limits (400 on failure).
    - Preserves password bytes exactly; never trims password.
    - Limits concurrent password-verification work via semaphore channel (503 + `Retry-After: 1` when saturated).
    - Calls `authService.Login` with bounded context timeout; maps invalid credentials to generic 401 without issuing a cookie.
    - Sets hardened session cookie and returns public user DTO on success.
  - `Me (GET /api/auth/me)`:
    - Extracts `giki_session` cookie (401 if missing).
    - Validates session via `authService.ValidateSession` under row lock; touches activity.
    - Returns public user DTO with up-to-date roles.
  - `Logout (POST /api/auth/logout)`:
    - Validates exact `Origin` header (403 on failure).
    - Extracts `giki_session` cookie; calls `authService.Logout` without validating first (expired/revoked sessions still revocable).
    - Clears browser cookie with `MaxAge: -1`.
    - Returns `204 No Content`; propagates genuine infrastructure errors as 500.
  - Per-client rate limiter middleware returning 429 Too Many Requests using remote TCP IP.
- **`backend/internal/authentication/handler_test.go`:**
  - Unit tests using small `fakeAuthenticator` mock covering login success, password whitespace preservation, origin rejection (6 cases), body/content limits (3 cases), bad credentials (no cookie), internal error redaction, concurrency saturation (503), rate limiting (429), session validation (3 cases), and logout clearing (3 cases).
- **`backend/internal/authentication/http_integration_test.go`:**
  - Opt-in integration test suite (`//go:build integration`) using disposable database (`giki_sports_disposable_authsvc_*`):
    - Tested failed login with wrong password (401, no cookie).
    - Tested valid login (200, `Set-Cookie` present, public user DTO).
    - Verified database table `giki_sports.sessions` persisted the SHA-256 token hash, not the raw token.
    - Validated session via `GET /api/auth/me` with cookie (200, dynamic roles).
    - Logged out via `POST /api/auth/logout` (204, cleared cookie, populated `revoked_at` in DB).
    - Verified subsequent `GET /api/auth/me` returns 401 Unauthorized.
    - Verified development database tables (`users` and `sessions`) remained empty (0 rows).
- **`backend/internal/config/config.go` & `backend/internal/config/config_test.go`:**
  - Added `AuthConfig` parsing: `AUTH_COOKIE_NAME`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_PATH`, `AUTH_COOKIE_SAMESITE`, `AUTH_TRUSTED_ORIGINS`, `AUTH_LOGIN_RATE_LIMIT`, `AUTH_LOGIN_RATE_WINDOW`, `AUTH_LOGIN_MAX_CONCURRENT`, `AUTH_REQUEST_TIMEOUT`.
  - Added unit test `TestConfig_AuthSettings`.
- **`backend/main.go`:**
  - Constructed `authService` once at startup (precomputing dummy Argon2id hash once).
  - Registered `authHandler` under `/api`.
  - Updated CORS configuration: scoped strictly to trusted origins with `AllowCredentials: true` (no wildcard `*`).
- **`.env.example`:**
  - Documented all authentication and cookie configuration keys.
- **`docs/authentication-http.md`:**
  - Created comprehensive architecture documentation covering contracts, cookie specifications, CSRF defense, abuse controls, Wallet reuse, and limitations.

### 20.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/authentication/...` | `backend/` | Authentication unit tests | **Passed (Exit 0):** All 12 unit tests (23 subtests) passed. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** All 6 packages (`auth`, `authentication`, `config`, `facility`, `session`, `user`) passed. |
| `go test -v -count=1 -tags=integration ./internal/authentication/...` | `backend/` | HTTP & service integration tests | **Passed (Exit 0):** Both integration suites passed against disposable DBs in 5.29s; dev DB verified untouched. |
| `go test -v -count=1 -tags=integration ./internal/session/...` | `backend/` | Session repository integration tests | **Passed (Exit 0):** All 13 subtests passed in 3.20s; dev DB verified untouched. |

---

## 21. Step 6H Implementation & Verification Outcomes

Step 6H implemented the reusable authentication and role authorization middleware layer for the GIKI Sports Complex Management System.

### 21.1 Files Modified & Created
- **`backend/internal/authentication/cookie.go`:**
  - Updated `SetSessionCookie` and added `BuildCookie` to strictly bound `MaxAge` and `Expires` to the session's persisted `AbsoluteExpiresAt` timestamp.
  - Rejects already-expired sessions or timestamps that round to `<= 0` integer seconds.
  - Added accessor helpers: `Secure()`, `SameSite()`, `Path()`.
- **`backend/internal/authentication/middleware.go`:**
  - Implemented `RequireAuth(service, cookieMgr, timeout)`:
    - Extracts `giki_session` cookie; validates session via `service.ValidateSession` under row lock; touches activity in PostgreSQL.
    - Missing/invalid/expired/revoked session returns generic 401 Unauthorized.
    - Context deadline exceeded returns 503 Service Unavailable; unexpected DB failure returns 500.
    - Attaches `*AuthenticatedPrincipal` to Fiber context locals using private unexported key `principalLocalKey`.
    - Strictly ignores client-supplied spoofed headers (`X-User-ID`, `X-Role`).
    - Sets `Cache-Control: no-store` and `Pragma: no-cache` on protected responses.
  - Implemented `RequireAnyRole(roles ...user.Role)`:
    - Verifies principal from Fiber locals via typed accessor `GetPrincipal(c)`. Missing principal returns 401.
    - Fails closed (`403 Forbidden`) if configured `roles` slice is empty or contains an unrecognized role.
    - Compares user roles against required roles; returns 403 if unauthorized, proceeds if matching.
    - **No automatic super_admin bypass**: each route must explicitly list its permitted roles.
    - Cashier authority is not granted through any role.
  - Implemented `RequireTrustedOrigin(trustedOrigins)`:
    - Enforces exact canonical `Origin` header validation on mutation routes, returning 403 Forbidden on mismatch or missing origin.
  - Implemented typed accessor `GetPrincipal(c *fiber.Ctx) (*AuthenticatedPrincipal, bool)`.
- **`backend/internal/authentication/handler.go`:**
  - Refactored `RegisterRoutes`:
    - `POST /api/auth/login`: pipeline uses `h.RequireTrustedOrigin()`, `h.rateLimiter`, `h.Login`.
    - `GET /api/auth/me`: pipeline uses `h.RequireAuth()`, `h.Me`.
    - `POST /api/auth/logout`: pipeline uses `h.RequireTrustedOrigin()`, `h.Logout` (bypasses `RequireAuth` so expired sessions can still be revoked and cookies cleared).
  - Refactored `Login`: sets session cookie strictly bounded by `res.Session.AbsoluteExpiresAt`; returns 500 if cookie setting fails.
  - Refactored `Me`: extracts verified principal via `GetPrincipal(c)`, eliminating duplicate session validation and database touches.
  - Refactored `Logout`: independent of `RequireAuth`; revokes session and clears cookie.
- **`backend/internal/authentication/middleware_test.go`:**
  - Unit tests covering `RequireAuth` (missing cookie, invalid session, deadline exceeded, internal error, locals population, spoofed header rejection), `RequireAnyRole` (no principal, single match, multiple match, wrong role, no roles, empty config, unknown role, super_admin no-bypass), `/me` single validation assertion, `Logout` without `RequireAuth`, and cookie expiry/security modes (`Secure=false` dev vs `Secure=true` prod).
- **`backend/internal/authentication/middleware_integration_test.go`:**
  - Opt-in integration test suite (`//go:build integration`) using disposable database (`giki_sports_disposable_authsvc_*`):
    - Verified student user accesses student route (200), denied director route (403).
    - Verified director user accesses director route (200), denied student route (403).
    - Verified dynamic database role removal is immediately reflected on subsequent request with same cookie (403).
    - Verified logout revocation blocks subsequent access (401).
    - Verified development database remained completely unmutated (0 rows).
- **`docs/authentication-middleware.md`:**
  - Created architectural specification documenting middleware ordering, role semantics, cookie expiry corrections, Wallet reuse, security clarifications (`HttpOnly`, `SameSite`, and `Path` boundaries), and test results.

### 21.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/authentication/...` | `backend/` | Authentication & middleware unit tests | **Passed (Exit 0):** All 17 test functions (44 subtests) passed. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** All 6 packages (`auth`, `authentication`, `config`, `facility`, `session`, `user`) passed. |
| `go test -v -count=1 -tags=integration ./internal/authentication/...` | `backend/` | Middleware, HTTP, and service integration tests | **Passed (Exit 0):** All 3 integration suites passed against disposable DBs in 7.47s; dev DB verified untouched. |
| `go test -v -count=1 -tags=integration ./internal/session/...` | `backend/` | Session repository integration tests | **Passed (Exit 0):** All 13 subtests passed in 3.20s; dev DB verified untouched. |

---

## 22. Step 6I Implementation & Verification Outcomes

Step 6I implemented a secure, interactive CLI for provisioning local development accounts without hardcoding credentials, choosing passwords for developers, or mutating the development database during automated test cycles.

### 22.1 Files Created & Modified
- **`backend/internal/devuser/provision.go`:**
  - Implemented preset management: `director` (`director@example.test`, role `sports_director`) and `student` (`student@example.test`, role `student`). Disallows arbitrary roles and privileged `super_admin`.
  - Implemented `ValidateTarget`: rejects non-loopback IP addresses or remote hostnames; strictly enforces database name matching `giki_sports_complex` (or test disposable databases).
  - Implemented `ReadPasswordInteractive`: checks terminal interactivity (`term.IsTerminal`), prompts twice for password without echo (`term.ReadPassword`), validates confirmation match, and enforces bounded length (1 to `auth.MaxPasswordLength`).
  - Implemented `ProvisionUser`: executes a single atomic PostgreSQL transaction:
    - Normalizes email via `user.NormalizeEmail`.
    - Checks for existing user using `SELECT ... FOR SHARE`. If user exists, reports existing without mutating password hash, status, or roles (no silent reset or promotion).
    - Inserts into `giki_sports.users` with production RFC 9106 Argon2id hash (`auth.Hash`).
    - Catches concurrent duplicate attempts via PostgreSQL unique constraint `uq_users_email_lower`.
    - Inserts role into `giki_sports.user_roles`.
    - Defers rollback on error and commits before returning success.
- **`backend/cmd/provision-dev-user/main.go`:**
  - Dedicated CLI entrypoint requiring `--dev` or `--local-dev` opt-in and `--preset director|student`.
  - Displays nonsecret target parameters and explicitly clarifies that loopback and database name checks are defensive safeguards against misconfiguration, not cryptographic proof.
  - Refuses non-interactive stdin.
  - Generates safe output upon completion; does not create a session.
- **`backend/internal/devuser/provision_test.go`:**
  - Unit tests covering:
    - Preset validation (director, student, case/whitespace trimming, rejection of `super_admin`, `faculty`, arbitrary, and empty strings).
    - Target safeguards (loopback IPs `127.0.0.1`, `localhost`, `::1`, alternative loopbacks, non-loopback IP/hostname rejection, wrong DB name rejection).
    - Interactive password reading (non-interactive rejection, password match, mismatch rejection, empty rejection, length bound rejection).
- **`backend/internal/devuser/provision_integration_test.go`:**
  - Opt-in integration test suite (`//go:build integration`) using disposable database:
    - `BothPresets_CreateCorrectAccountAndExactRole`: verified `director@example.test` gets `sports_director` and `student@example.test` gets `student`.
    - `StoredHash_VerifiesWithArgon2idHelper`: verified stored hash matches input password using `auth.Verify`.
    - `ExistingAccount_RemainsUnchangedOnRerun`: verified second run reports existing account without altering password hash, active status, or roles.
    - `RoleInsertFailure_RollsBackUserInsert`: verified user insert is completely rolled back if role insert fails.
    - `CreatedAccount_CanLoginThroughAuthService`: verified provisioned user can log in through production `authentication.Service.Login`, creating a valid session.
    - `TargetValidation_RejectsDisallowedConfigurations`: verified non-loopback and wrong database names fail closed.
    - Asserted primary development database `giki_sports_complex` remains at 0 users and 0 sessions.
- **`docs/development-accounts.md`:**
  - Comprehensive guide documenting why provisioning is decoupled from HTTP endpoints and application boot, target safeguards, preset boundaries, exact PowerShell commands to provision accounts, and end-to-end verification via PowerShell `Invoke-RestMethod` without leaking passwords or cookies.

### 22.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/devuser/...` | `backend/` | Devuser unit tests | **Passed (Exit 0):** All 3 test functions (26 subtests) passed in 0.40s. |
| `go test -v -count=1 ./...` | `backend/` | Complete backend unit test suite | **Passed (Exit 0):** All 7 packages passed in 3.5s. |
| `go test -v -count=1 -tags=integration ./internal/devuser/...` | `backend/` | Devuser integration tests | **Passed (Exit 0):** All 6 subtests passed against disposable DB in 2.61s; dev DB verified untouched. |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | Complete integration test suite | **Passed (Exit 0):** Database, session, authentication, and devuser integration tests passed in 9.2s; dev DB verified untouched. |
| Database Count Probe | PostgreSQL | Verify dev DB untouched | **Passed (Exit 0):** `giki_sports.users` = 0 rows, `giki_sports.sessions` = 0 rows. |

---

## 23. Step 7A Implementation & Verification Outcomes

Step 7A implemented the frontend sign-in, session restore on startup, and sign-out capabilities for the GIKI Sports Complex Management System, adhering to strict in-memory user state, HttpOnly cookie security, and resilient network error handling.

### 23.1 Files Created & Modified
- **`frontend/src/types.ts`:**
  - Added `AuthUser` interface (`id`, `email`, `displayName`, `roles`).
  - Added `isAuthUser` type guard and `parseAuthUser` runtime validation.
- **`frontend/src/api.ts`:**
  - Updated `request<T>` to include `credentials: "include"`, ensuring same-origin cookie transport and Set-Cookie handling across local dev Vite proxy.
  - Added explicit status 204 handler in `request<T>` returning `undefined` without attempting to parse JSON.
  - Added typed methods: `api.login(input)`, `api.me()`, and `api.logout()`.
- **`frontend/src/context/AuthContext.tsx`:**
  - Implemented `AuthProvider` and `useAuth` hook:
    - Restores session on initial application mount via `api.me()`.
    - Maps HTTP 401 on `/me` to signed-out state (`user = null`, `checkError = null`).
    - Distinguishes network / server failures (5xx) on `/me` from 401: sets `checkError` for explicit user retry while leaving public facility pages completely unblocked.
    - Updates in-memory user state on login success; clears user state on logout success.
    - On logout failure, records error for retry and **does not claim session was revoked**.
    - Employs a monotonic action sequence counter (`actionSeqRef`) to prevent stale, delayed `/me` responses from overwriting newer login, logout, or retry actions.
    - Strictly avoids persisting credentials, tokens, or session state in browser storage (`localStorage` / `sessionStorage`).
- **`frontend/src/pages/Login.tsx`:**
  - Added `/login` sign-in page matching Sports visual identity (`var(--color-navy)`, `var(--color-maroon)`, `var(--color-surface)`).
  - Accessible form controls with proper `<label>` associations, keyboard submit support, and password manager autocomplete (`username`, `current-password`).
  - Input boundaries: enforces technical API limits (email $\le 255$ chars, password $\le 4096$ chars); strictly preserves password bytes without trimming.
  - Prevents duplicate submissions by disabling controls and displaying "Signing in...".
  - Clear user-facing error mapping for 401 (invalid credentials), 429 (rate limiting), 503 (service busy), and network errors.
  - Returns to public homepage (`/`) on successful authentication.
  - If already authenticated, displays user profile with role badges and actions to return home or sign out.
- **`frontend/src/components/Navbar.tsx`:**
  - Updated desktop and mobile navigation:
    - When signed out: displays "Sign In" link leading to `/login`.
    - When signed in: displays user's `displayName` and an accessible "Sign Out" button.
    - When session check encounters a server/network outage: surfaces an inline "Session check failed [Retry]" action.
    - When logout fails: displays an inline error alert with "Retry Sign Out".
    - Public facility navigation links remain 100% accessible.
- **`frontend/src/App.tsx`:**
  - Wrapped root route hierarchy in `<AuthProvider>`.
  - Registered `/login` route pointing to `<Login />`.
- **`frontend/src/test/validation.test.ts`:**
  - Added 5 unit tests covering `isAuthUser` and `parseAuthUser` runtime validation.
- **`frontend/src/test/Auth.test.tsx`:**
  - Added 10 comprehensive tests covering:
    - Session restore on startup.
    - Signed-out startup (401).
    - Startup failure and retry.
    - Login form validation and exact password whitespace preservation.
    - Login success and redirect.
    - Login error mapping (401, 429, 503).
    - Duplicate submission prevention.
    - Logout success (204).
    - Logout failure and retry.
    - Stale `/me` response guard.

### 23.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `npm run build` | `frontend/` | TypeScript compile and Vite production bundling | **Passed (Exit 0):** Bundled in 7.82s without errors. |
| `npm test` | `frontend/` | Vitest test suite | **Passed (Exit 0):** All 4 test suites (37 tests) passed in 9.02s. |

---

## 24. Step 7B Implementation & Verification Outcomes

Step 7B implemented the PostgreSQL repository write primitive for modifying recurring weekly facility schedule windows, strictly scoped by dual identifiers (`facilitySlug` and `scheduleID`) without exposing HTTP routes or frontend controls.

### 24.1 Files Created & Modified
- **`backend/internal/facility/model.go`:**
  - Defined domain errors: `ErrInvalidInput`, `ErrScheduleNotFound`, `ErrDuplicateSchedule`.
  - Defined typed errors: `ScheduleValidationError`, `ScheduleNotFoundError`, `DuplicateScheduleError`.
  - Added `SupportedAudiences` set: `general`, `student`, `faculty`, `women_only`, `staff`.
  - Added `UpdateScheduleInput` struct (`DayOfWeek`, `StartTime`, `EndTime`, `Audience`).
  - Added `UpdateScheduleInput.Validate()` enforcing:
    - ISO weekday between 1 and 7.
    - Supported audience membership.
    - 24-hour wall-clock format `HH:MM:SS` (hours 0..23, minutes 0..59, seconds 0..59).
    - Permitting `24:00:00` strictly as an end time (86,400 seconds), rejecting it as a start time.
    - Strict time ordering ($startSeconds < endSeconds$).
  - Added `ParseWallClockSeconds` helper function.
- **`backend/internal/facility/repository.go`:**
  - Added `UpdateSchedule(ctx, facilitySlug, scheduleID, input)` to `Repository` interface.
  - Implemented `UpdateSchedule` on `PostgresRepository`:
    - Dual-identifier scoping: `UPDATE giki_sports.schedules s ... FROM giki_sports.facilities f WHERE s.id = $1 AND s.facility_id = f.id AND f.slug = $2`.
    - Returns updated schedule row via `RETURNING` clause.
    - Preserves schedule `id`, `facility_id`, and `created_at`.
    - Updates `updated_at = now()`.
    - Mapped `pgx.ErrNoRows` to `ScheduleNotFoundError`.
    - Mapped `23505` unique violation on `uq_schedules_window` to `DuplicateScheduleError`.
    - Mapped `23514` check constraint violations to `ScheduleValidationError`.
- **`backend/internal/facility/schedule_test.go`:**
  - Added 10 unit tests for `UpdateScheduleInput.Validate()` covering valid inputs, weekdays 1-7, invalid weekdays, supported audiences, invalid audiences, `24:00:00` end time, `24:00:00` start rejection, equal times, inverted times, and malformed strings.
- **`backend/internal/facility/repository_integration_test.go`:**
  - Added 5 integration tests against disposable PostgreSQL databases:
    - `TestFacilityRepository_UpdateSchedule_SyntheticRowAndTimetable`: confirmed timetable update, ID preservation, and read round-trip via `GetBySlug`.
    - `TestFacilityRepository_UpdateSchedule_PreservesUnrelatedRows`: verified unrelated schedules and parent facility remain untouched.
    - `TestFacilityRepository_UpdateSchedule_MissingOrMismatchedPair`: verified mismatched facility/schedule pairs return `ErrScheduleNotFound` and write 0 rows.
    - `TestFacilityRepository_UpdateSchedule_InvalidAndDuplicateWindows`: verified invalid and duplicate inputs leave original row intact.
    - `TestFacilityRepository_UpdateSchedule_EndTime24RoundTrip`: verified `24:00:00` survives update and read round-trip without corruption.
- **`docs/facility-schedule-write-contract.md`:**
  - Comprehensive specification of write contract, invariants, dual-scoping rationale, error hierarchy, verification results, and prerequisite controls for the future HTTP mutation chunk (authentication, `sports_director` role guard, trusted origin, and FR-09 audit logging).

### 24.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go backend packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/facility/...` | `backend/` | Facility unit tests | **Passed (Exit 0):** All 10 test functions (21 subtests) passed in 1.39s. |
| `go test -v -count=1 -tags=integration ./internal/facility/...` | `backend/` | Facility integration tests | **Passed (Exit 0):** All 13 tests passed against disposable DBs in 6.38s. |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | Complete backend integration suite | **Passed (Exit 0):** All integration packages passed in 15.56s. |
| Development DB Probe | PostgreSQL | Verify dev DB untouched | **Passed (Exit 0):** 2 facilities, 5 schedules (original demo seed untouched; timestamps preserved). |

---

## 25. Step 7C Implementation & Verification Outcomes

Step 7C added Goose migration `00004` to create `giki_sports.audit_logs` and implemented `UpdateScheduleWithAudit` on the PostgreSQL facility repository, executing both the schedule update and the administrative audit record insertion within an atomic single transaction.

### 25.1 Files Created & Modified
- **`backend/migrations/00004_create_audit_logs.sql`:**
  - Forward migration (`-- +goose Up`): provisions table `giki_sports.audit_logs` with UUID primary key, `actor_id` referencing `giki_sports.users(id)` with `ON DELETE RESTRICT`, non-empty checks on `action` and `target_type`, check constraint on `status IN ('SUCCESS', 'FAILURE')`, and timestamp `created_at TIMESTAMPTZ DEFAULT now()`.
  - Added indexes on `actor_id`, `target_id`, `action`, `created_at DESC`, and composite `(target_id, action, created_at DESC)`.
  - Reverse migration (`-- +goose Down`): `DROP TABLE IF EXISTS giki_sports.audit_logs RESTRICT;`.
- **`backend/internal/facility/model.go`:**
  - Added `AuditParams` struct (`ActorID uuid.UUID`, `IPAddress string`, `UserAgent string`).
- **`backend/internal/facility/repository.go`:**
  - Added `UpdateScheduleWithAudit` to `Repository` interface.
  - Implemented `UpdateScheduleWithAudit` on `PostgresRepository`:
    1. Begins transaction `tx, err := r.pool.Begin(ctx)` with deferred `tx.Rollback(ctx)`.
    2. Locks schedule row with `SELECT ... FROM giki_sports.schedules s JOIN giki_sports.facilities f ON s.facility_id = f.id WHERE s.id = $1 AND f.slug = $2 FOR UPDATE OF s;`, capturing previous window parameters.
    3. Executes `UPDATE giki_sports.schedules` with new parameters, returning modified row.
    4. Marshals structured audit details JSON containing `facility_slug`, `facility_id`, `old_window`, and `new_window`.
    5. Inserts audit row into `giki_sports.audit_logs` (`action = 'schedule.update'`, `target_type = 'facility_schedule'`, `target_id = scheduleID`, `status = 'SUCCESS'`).
    6. If audit insert fails, deferred rollback aborts transaction.
    7. Atomically commits via `tx.Commit(ctx)`.
- **`backend/internal/database/migration_integration_test.go`:**
  - Added `TestMigrationIntegration_AuditLogsLifecycle` verifying:
    - All 4 migrations apply cleanly.
    - `audit_logs` table and indexes exist.
    - Foreign key constraint `fk_audit_logs_actor` rejects invalid actors.
    - Check constraints enforce non-empty action, non-empty target_type, and valid status.
    - Migration 4 Down drops `audit_logs` and restores version 3.
    - Reapplying Up restores version 4.
  - Isolated migration 1-3 test fixtures via `getMigration1To3FixtureFS`.
- **`backend/internal/facility/repository_integration_test.go`:**
  - Added 4 integration tests for `UpdateScheduleWithAudit`:
    - `TestFacilityRepository_UpdateScheduleWithAudit_Success`: verified single transaction updates schedule and writes matching audit log with old and new windows.
    - `TestFacilityRepository_UpdateScheduleWithAudit_RollbackOnAuditFailure`: forced audit insert failure via invalid `actor_id` (SQLSTATE 23503), proving schedule row was completely untouched and 0 audit logs were written.
    - `TestFacilityRepository_UpdateScheduleWithAudit_RollbackOnScheduleError`: verified duplicate collision aborts before writing audit log.
    - `TestFacilityRepository_UpdateScheduleWithAudit_NotFound`: verified non-existent facility/schedule returns `ErrScheduleNotFound` without inserting audit log.

### 25.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go backend packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/facility/...` | `backend/` | Facility package unit tests | **Passed (Exit 0):** All 10 test functions passed in 1.51s. |
| `go test -v -count=1 -tags=integration ./internal/database/...` | `backend/` | Database migration integration tests | **Passed (Exit 0):** All 7 test functions passed in 5.18s. |
| `go test -v -count=1 -tags=integration ./internal/facility/...` | `backend/` | Facility integration tests (disposable DBs) | **Passed (Exit 0):** All 17 tests passed in 6.44s. |
| `go test -tags=integration ./...` | `backend/` | Complete backend integration suite | **Passed (Exit 0):** All packages passed across all integration tests. |
| Development DB Probe | PostgreSQL | Verify dev DB untouched | **Passed (Exit 0):** 2 facilities, 5 schedules (original demo seed untouched; 0 audit logs in dev DB). |

---

## 26. Step 7D Implementation & Verification Outcomes

Step 7D implemented the protected HTTP mutation endpoint `PUT /api/facilities/:slug/schedules/:id`, wiring the trusted-Origin CSRF guard, session authentication, and role authorization stack directly to the audited PostgreSQL schedule transaction.

### 26.1 Files Created & Modified
- **`backend/internal/facility/dto.go`:**
  - Added `ToScheduleResponse(s Schedule) ScheduleResponse` converting domain schedules into public DTOs while preserving exact wall-clock representations (including `"24:00:00"`).
- **`backend/internal/facility/handler.go`:**
  - Added `UpdateScheduleRequest` struct (`dayOfWeek`, `startTime`, `endTime`, `audience`).
  - Added `RegisterScheduleUpdateRoute(router, middleware...)` to mount `PUT /facilities/:slug/schedules/:id`.
  - Implemented `UpdateSchedule(c *fiber.Ctx)` handler:
    1. Validates `:slug` and `:id` (valid non-nil UUID).
    2. Validates `Content-Type: application/json` (HTTP 415 if missing or non-JSON).
    3. Enforces 4KB body limit (HTTP 413 if exceeded, 400 if empty).
    4. Enforces strict JSON unmarshaling via `dec.DisallowUnknownFields()` (HTTP 400 on unexpected keys or syntax errors).
    5. Validates domain window rules via `input.Validate()` (HTTP 400 on day/time/audience violations).
    6. Extracts authenticated principal from Fiber locals via `authentication.GetPrincipal(c)`.
    7. Sets `audit.ActorID = principal.User.ID` (never trusts client headers or body; optional IP and user-agent left unset for this chunk).
    8. Calls `repo.UpdateScheduleWithAudit(ctx, slug, scheduleID, input, audit)` under bounded context timeout.
    9. Maps domain errors: `ScheduleValidationError` $\to$ 400, `ScheduleNotFoundError` $\to$ 404, `DuplicateScheduleError` $\to$ 409, `DeadlineExceeded` $\to$ 503, database errors $\to$ sanitized 500 without leaking SQL internals.
    10. Returns HTTP 200 OK with `ScheduleResponse`.
- **`backend/internal/authentication/middleware.go`:**
  - Added `SetPrincipalForTest(c *fiber.Ctx, principal *AuthenticatedPrincipal)` to enable hermetic testing across packages.
- **`backend/main.go`:**
  - Reordered initialization so `authHandler` precedes `facilityHandler`.
  - Registered public GET routes: `facilityHandler.RegisterRoutes(api)`.
  - Registered protected PUT route: `facilityHandler.RegisterScheduleUpdateRoute(api, authHandler.RequireTrustedOrigin(), authHandler.RequireAuth(), authentication.RequireAnyRole(user.RoleSportsDirector, user.RoleSuperAdmin))`.
- **`backend/internal/facility/handler_test.go`:**
  - Added 12 focused handler unit tests covering success, 24:00:00 end time, missing principal (401), invalid UUID (400), unsupported media type (415), empty & oversized body (400/413), malformed JSON & unknown fields (400), validation failures (400), not found (404), duplicate window (409), deadline exceeded (503), and internal error sanitization (500).
- **`backend/internal/facility/http_integration_test.go`:**
  - Added comprehensive `TestFacilityScheduleUpdateHTTP_Integration` using disposable PostgreSQL database with real authentication, real session cookies, and real PostgreSQL transactions:
    1. Anonymous request (missing cookie) $\to$ 401 Unauthorized.
    2. Revoked session cookie $\to$ 401 Unauthorized.
    3. Student role $\to$ 403 Forbidden.
    4. Faculty role $\to$ 403 Forbidden.
    5. Missing `Origin` header $\to$ 403 Forbidden.
    6. Untrusted `Origin` header $\to$ 403 Forbidden.
    7. Sports Director valid edit $\to$ 200 OK; database schedule updated; exactly 1 audit row written with director's `actor_id`; anonymous GET returns updated timetable.
    8. Super Admin valid edit $\to$ 200 OK (preserves `"24:00:00"`); second audit row written with super admin's `actor_id`.
    9. Denied, invalid, mismatched, and duplicate requests leave schedule row and audit row count unchanged.
    10. Forced audit failure (PostgreSQL trigger exception) $\to$ 500 Internal Server Error; verified complete transactional rollback of schedule update.
- **`docs/facility-api.md`:**
  - Documented Section 2.3 for `PUT /api/facilities/:slug/schedules/:id` with complete headers, request/response payloads, error code matrix, audit trail binding, and explicitly documented that stale-editor conflict detection is not implemented.

### 26.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go backend packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/facility/...` | `backend/` | Facility package unit tests | **Passed (Exit 0):** All 22 test functions (33 subtests) passed in 3.57s. |
| `go test -v -count=1 -tags=integration -run "TestFacilityScheduleUpdateHTTP_Integration" ./internal/facility/...` | `backend/` | Full HTTP integration test (disposable DB) | **Passed (Exit 0):** All 10 verification scenarios passed in 7.16s. |
| `go test -v -count=1 -tags=integration ./internal/facility/...` | `backend/` | Complete facility integration suite | **Passed (Exit 0):** All 18 integration tests passed in 32.06s. |
| `go test ./...` | `backend/` | All backend unit tests | **Passed (Exit 0):** All unit packages passed. |
| Development DB Probe | PostgreSQL | Verify dev DB untouched | **Passed (Exit 0):** 2 facilities, 5 schedules, 0 audit logs in dev DB. |

---

## 27. Step 7E Implementation & Verification Outcomes

Step 7E implemented an inline operating window editor on the facility detail page (`FacilityDetail.tsx`), connecting authorized users to the verified `PUT /api/facilities/:slug/schedules/:id` endpoint.

### 27.1 Components & Patterns Added
- **`frontend/src/types.ts`:** Added `UpdateScheduleInput` interface and runtime schema validator `parseSchedule(value: unknown): Schedule`.
- **`frontend/src/api.ts`:** Added `updateSchedule(facilitySlug, scheduleId, input, options?)` calling `PUT /facilities/:slug/schedules/:id` with same-origin credentials (`include`) and JSON payload containing strictly `dayOfWeek`, `startTime`, `endTime`, and `audience`.
- **`frontend/src/pages/FacilityDetail.tsx`:**
  - Integrated `useAuth()` to conditionally render the "Edit window" action only when `canEditSchedule` (`sports_director` or `super_admin`) is true.
  - Form editing state: prefilled from selected schedule row; cancel cleanly restores row without write.
  - Asia/Karachi time support: textual inputs for `HH:MM:SS` wall-clock time with explicit support for `"24:00:00"` end time (unsupported by native `<input type="time">`) and a quick `"Set 24:00:00"` button.
  - Client-side validation: bounds weekdays (1..7), validates audience against whitelist, and ensures start time is strictly before end time.
  - Concurrency & double-click protection: disables inputs and submit button with `"Saving..."` indicator while save is in flight.
  - Error mapping & draft preservation: maps 400, 401, 403, 404, 409, and 500/network errors to specific accessible alerts (`role="alert"`) while keeping user draft intact.
  - Lifecycle guards: `isMountedRef` and `currentSlugRef` prevent state updates on unmounted component or stale routes.
- **Frontend Automated Tests:**
  - 18 parser tests in `frontend/src/test/validation.test.ts`.
  - 16 component and integration tests in `frontend/src/test/FacilityDetail.test.tsx`.
  - All 48 tests across 4 test suites passed.

---

## 28. Step 7F Verification Outcomes (Director-to-Visitor Real Browser Acceptance Flow)

Step 7F verified the director-to-visitor workflow in a real browser session across authenticated and unauthenticated roles.

### 28.1 Verification Observations
- **Infrastructure Verification:**
  - PostgreSQL container `giki-sports-complex-db-1` active and healthy on port 5434 with migration `00004_create_audit_logs.sql` applied.
  - Verified Go backend on port **8081** (`PORT=8081` in `.env`) and corrected previous walkthrough references that mistakenly noted port 8080 (which is reserved for GIKI Wallet).
  - Verified Vite reverse proxy (`http://localhost:5173/api/*` $\to$ `http://127.0.0.1:8081/api/*`) with trusted Origin `http://localhost:5173` and `credentials: true`.
- **Manual Real Browser Acceptance Flow (Performed by Project Lead):**
  - **Student Role:** Signed in as `student@example.test` and navigated to the demo facility timetable. Verified that the operating windows were rendered clearly and that no "Edit window" actions appeared in the UI.
  - **Director Role:** Signed in as `director@example.test`. Refreshed the page and confirmed session restoration. Opened the inline schedule editor on Monday `09:00:00`–`12:00:00`, modified the start time to `10:00:00`, and saved changes. Confirmed that the save succeeded and the timetable updated to `10:00:00`–`12:00:00`.
  - **Public Visitor Verification:** Opened a separate, unauthenticated private (incognito) window at `http://localhost:5173/facilities/demo-badminton-court`. Confirmed that the timetable reflected the updated `10:00:00` start time from PostgreSQL without any edit controls.
  - *Note:* In accordance with instructions, a manual audit log verification was not performed or recorded as passed for this step.

---

## 29. Step 8A Implementation & Verification Outcomes

Step 8A implemented an audited repository operation (`DeleteScheduleWithAudit`) to delete one existing weekly operating schedule window within a single atomic PostgreSQL transaction, recording an administrative audit log.

### 29.1 Files Created & Modified
- **`backend/internal/facility/repository.go`:**
  - Extended `Repository` interface with:
    `DeleteScheduleWithAudit(ctx context.Context, facilitySlug string, scheduleID uuid.UUID, audit AuditParams) error`
  - Implemented `PostgresRepository.DeleteScheduleWithAudit`:
    1. Validates inputs: rejects blank facility slug, nil schedule ID, or nil `ActorID`.
    2. Begins single PostgreSQL transaction (`tx, err := r.pool.Begin(ctx)`).
    3. Selects existing schedule conditioned on BOTH `s.id = $1` and `f.slug = $2` with `FOR UPDATE OF s` to verify facility ownership, lock the row against concurrent modifications, and capture previous window parameters (`day_of_week`, `start_time`, `end_time`, `audience`). Returns `&ScheduleNotFoundError` if not found or mismatched.
    4. Executes `DELETE FROM giki_sports.schedules WHERE id = $1;`.
    5. Marshals audit `details` JSON preserving `facility_slug`, `facility_id`, and `old_window`.
    6. Inserts administrative audit record into `giki_sports.audit_logs` with action `'schedule.delete'`, target_type `'facility_schedule'`, `target_id = scheduleID`, `status = 'SUCCESS'`, and actor context.
    7. Because `audit_logs.target_id` is a UUID without a foreign key constraint to `schedules(id)`, deleting the schedule row does not cascade or invalidate the audit record. The audit record remains permanently intact and readable after the schedule row is removed.
    8. Transactional rollback guarantee: if the audit insert fails (e.g. invalid actor ID or trigger constraint), deferred `tx.Rollback()` ensures the schedule deletion is not committed.
    9. Atomicity: reports success (`nil`) strictly after `tx.Commit()` successfully commits both the deletion and the audit record.
    10. Strictly rejects batch deletions and unaudited deletion paths.
- **`backend/internal/facility/handler_test.go`:**
  - Added `DeleteScheduleWithAudit` stub to `fakeReader` to satisfy the updated `Repository` interface.
- **`backend/internal/facility/repository_integration_test.go`:**
  - Added 3 comprehensive integration tests executed against isolated disposable databases:
    1. `TestFacilityRepository_DeleteScheduleWithAudit_Success`: verified that deleting schedule `s1` removes only `s1`, leaves sibling schedule `s2` intact, writes exactly 1 audit record with `schedule.delete`, and keeps the audit record with `old_window` completely readable after schedule deletion.
    2. `TestFacilityRepository_DeleteScheduleWithAudit_MismatchedAndNotFound`: verified that mismatched facility/schedule pairs, non-existent slugs, non-existent IDs, blank slugs, and nil IDs all return `ErrScheduleNotFound` without deleting any rows or writing audit records.
    3. `TestFacilityRepository_DeleteScheduleWithAudit_RollbackOnAuditFailure`: verified that forcing an audit log failure (foreign key constraint violation on `actor_id`) rolls back the transaction, leaving the original schedule row and timestamps completely untouched with 0 audit records committed.

### 29.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go backend packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/facility/...` | `backend/` | Facility package unit tests | **Passed (Exit 0):** All 22 test functions passed in 1.85s. |
| `go test -v -count=1 -tags=integration -run "TestFacilityRepository_DeleteScheduleWithAudit" ./internal/facility/...` | `backend/` | Audited deletion integration tests (disposable DBs) | **Passed (Exit 0):** All 3 deletion tests passed in 2.84s. |
| `go test -v -count=1 -tags=integration ./internal/facility/...` | `backend/` | Complete facility integration suite | **Passed (Exit 0):** All 21 integration tests passed in 10.64s. |
| Development DB Probe | PostgreSQL | Verify dev DB untouched | **Passed (Exit 0):** Dev DB contains untouched demo facilities and demo schedules. |

---

## 30. Step 8B Implementation & Verification Outcomes

Step 8B exposed the audited deletion of one weekly operating schedule window through the protected HTTP endpoint `DELETE /api/facilities/:slug/schedules/:id`.

### 30.1 Files Created & Modified
- **`backend/internal/facility/handler.go`:**
  - Added `RegisterScheduleDeleteRoute(router fiber.Router, middleware ...fiber.Handler)` mounting `DELETE /facilities/:slug/schedules/:id`.
  - Implemented `DeleteSchedule(c *fiber.Ctx)` handler:
    1. Sets `Cache-Control: no-store` and `Pragma: no-cache`.
    2. Validates `:slug` (non-blank) and `:id` (valid non-nil UUID). Returns HTTP 400 Bad Request on invalid identifiers.
    3. Requires no request body; does not parse body tokens.
    4. Extracts authenticated principal from Fiber locals via `authentication.GetPrincipal(c)`. Returns 401 if missing.
    5. Sets `audit.ActorID = principal.User.ID`. Client is never trusted for actor identity.
    6. Calls `repo.DeleteScheduleWithAudit(ctx, slug, scheduleID, audit)` under bounded context timeout (`h.queryTimeout`).
    7. Maps domain errors: `ScheduleNotFoundError` $\to$ 404, `DeadlineExceeded` $\to$ 503, database errors $\to$ generic sanitized 500 without leaking SQL internals.
    8. Returns **HTTP 204 No Content** with an empty body strictly after the PostgreSQL transaction commits.
- **`backend/main.go`:**
  - Registered `facilityHandler.RegisterScheduleDeleteRoute(api, authHandler.RequireTrustedOrigin(), authHandler.RequireAuth(), authentication.RequireAnyRole(user.RoleSportsDirector, user.RoleSuperAdmin))`.
- **`backend/internal/facility/handler_test.go`:**
  - Added 7 focused unit tests for `DeleteSchedule`:
    - `TestHandler_DeleteSchedule_Success`: verified 204 No Content, empty body, `Cache-Control: no-store`, and actor ID passed to repository.
    - `TestHandler_DeleteSchedule_InvalidScheduleUUID`: verified 400 Bad Request.
    - `TestHandler_DeleteSchedule_UnauthorizedWhenNoPrincipal`: verified 401 Unauthorized.
    - `TestHandler_DeleteSchedule_NotFound`: verified 404 Not Found.
    - `TestHandler_DeleteSchedule_DeadlineExceeded`: verified 503 Service Unavailable.
    - `TestHandler_DeleteSchedule_InternalError`: verified 500 Internal Server Error with sanitized response body.
    - `TestHandler_DeleteSchedule_ContextIsBounded`: verified bounded timeout context passed to repository.
- **`backend/internal/facility/http_integration_test.go`:**
  - Added `TestFacilityScheduleDeleteHTTP_Integration` using disposable PostgreSQL databases with real authentication, real session cookies, and real PostgreSQL transactions:
    1. Anonymous request (missing cookie) $\to$ 401 Unauthorized.
    2. Student role $\to$ 403 Forbidden.
    3. Untrusted Origin $\to$ 403 Forbidden.
    4. Wrong facility slug $\to$ 404 Not Found; zero schedule rows or audit rows changed.
    5. Forced audit failure (trigger exception on `audit_logs`) $\to$ generic 500; transaction rolled back; window remains completely visible in public GET query.
    6. Sports Director deletion $\to$ 204 No Content with empty body; window removed from public GET; exactly 1 audit row written with director user ID and deleted window parameters.
    7. Repeat DELETE $\to$ 404 Not Found; no duplicate audit row added.
    8. Super Admin deletion $\to$ 204 No Content with empty body; window removed from public GET; second audit row written.
- **`docs/facility-api.md`:**
  - Documented Section 2.4 for `DELETE /api/facilities/:slug/schedules/:id` with complete headers, error code matrix, audit trail durability, and idempotence/repeat semantics.

### 30.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all Go backend packages | **Passed (Exit 0)** |
| `go vet ./...` | `backend/` | Static analysis and vetting | **Passed (Exit 0)** |
| `go test -v -count=1 ./internal/facility/...` | `backend/` | Facility package unit tests | **Passed (Exit 0):** All 29 test functions passed in 1.78s. |
| `go test -v -count=1 -tags=integration -run "TestFacilityScheduleDeleteHTTP_Integration" ./internal/facility/...` | `backend/` | Full delete HTTP integration test (disposable DB) | **Passed (Exit 0):** All 8 verification scenarios passed in 1.92s. |
| `go test -v -count=1 -tags=integration ./internal/facility/...` | `backend/` | Complete facility integration suite | **Passed (Exit 0):** All 22 integration tests passed in 10.62s. |
| Development DB Probe | PostgreSQL | Verify dev DB untouched | **Passed (Exit 0):** Dev DB contains untouched demo facilities, demo schedules, and local dev user accounts. |

---

## 31. Step 8B.1 Implementation & Integration Test Independence Outcomes

Step 8B.1 removed the hardcoded assumption that the persistent development database (`giki_sports_complex`) must be completely empty of accounts and sessions for backend integration tests to pass.

### 31.1 Root Cause of Integration Test Failure
When the full integration suite (`go test -v -count=1 -tags=integration ./...`) was executed following Step 7F (where developer accounts `director@example.test` and `student@example.test` were provisioned for real-browser testing), three test files failed during initial assertions:
1. `backend/internal/authentication/http_integration_test.go:46` & `:280`:
   - `safety check violated: expected 0 dev users, got 2; expected 0 dev sessions, got 2`
2. `backend/internal/authentication/middleware_integration_test.go:34` & `:259`:
   - `safety check violated: expected 0 dev users, got 2; expected 0 dev sessions, got 2`
3. `backend/internal/devuser/provision_integration_test.go:160` & `:417`:
   - `safety check violated: expected 0 dev users, got 2; expected 0 dev sessions, got 2`

**Root Cause Analysis:**
The tests asserted `assertDevDBEmpty(t)`, which queried `giki_sports_complex` and checked `uCount == 0 && sCount == 0`. This conflated two distinct concepts:
- **"Empty":** The developer has never provisioned any accounts, sessions, or demo data locally.
- **"Untouched":** The integration tests executed entirely against isolated disposable databases (e.g., `giki_sports_disposable_*`) and created zero side effects or writes on the development database.

Other integration test suites in the repository (`backend/internal/user/repository_integration_test.go`, `backend/internal/session/repository_integration_test.go`, and `backend/internal/authentication/service_integration_test.go`) already employed a read-only baseline pattern: measuring baseline counts before disposable tests run and asserting that the counts remain identical afterward.

### 31.2 Test Modernization
1. **`backend/internal/authentication/http_integration_test.go`**:
   - Replaced `assertDevDBEmpty(t)` with `assertDevDBUntouched(t *testing.T, baseUsers, baseSessions int)`.
   - Sampled baseline counts (`initialUsers, initialSessions := countDevRecords(t)`) before test execution and asserted `assertDevDBUntouched(t, initialUsers, initialSessions)` upon completion.
2. **`backend/internal/authentication/middleware_integration_test.go`**:
   - Replaced `assertDevDBEmpty(t)` with `assertDevDBUntouched(t *testing.T, baseUsers, baseSessions int)`.
   - Captured initial baseline counts and verified zero record drift on the development database post-run.
3. **`backend/internal/devuser/provision_integration_test.go`**:
   - Replaced `assertDevDBEmpty(t)` with `assertDevDBUntouched(t *testing.T, baseUsers, baseSessions int)`.
   - Sampled initial counts before test suites and validated that the development database was completely untouched after all disposable database operations finished.
4. **`backend/internal/facility/http_integration_test.go`**:
   - In `TestFacilityScheduleUpdateHTTP_Integration`, changed manual session revocation from `revoked_at = now()` to `revoked_at = GREATEST(now(), created_at)` to guard against WSL2/Docker container clock skew violating `chk_sessions_revoked_after_created`.
   - Replaced default 1-second timeout in `app.Test(req)` with explicit `10000ms` (10s) timeout for password verification under concurrent test load.

### 31.3 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go test -count=1 ./...` | `backend/` | Standard unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./...` | `backend/` | Complete integration test suite against disposable databases | **Passed (Exit 0):** All packages passed (`auth`, `authentication`, `config`, `database`, `devuser`, `facility`, `seed`, `session`, `user`). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify developer accounts and schedules remained intact | **Passed (Exit 0):** 2 facilities, 5 schedules, 1 audit log, 2 users, 2 sessions intact. |

---

## 32. Step 8C Implementation & Frontend Schedule Deletion Confirmation Outcomes

Step 8C implemented frontend deletion confirmation and row state synchronization for weekly facility schedule windows using the protected `DELETE /api/facilities/:slug/schedules/:id` endpoint.

### 32.1 Frontend Architecture & Component Updates
1. **`frontend/src/api.ts`:**
   - Added typed `deleteSchedule(facilitySlug: string, scheduleId: string, options?: RequestOptions): Promise<void>`.
   - Relative URL `/facilities/${encodedSlug}/schedules/${encodedId}` with `encodeURIComponent` on both parameters.
   - Dispatches `method: "DELETE"` with no request body.
   - Relies on browser-managed session cookies (`credentials: "include"`) and Origin header.
   - Handled HTTP 204 No Content directly as an empty success response without JSON parsing.
2. **`frontend/src/pages/FacilityDetail.tsx`:**
   - **Role Visibility:** Restricted "Delete window" action alongside "Edit window" to users holding `sports_director` or `super_admin` role. General visitors, student users, and faculty users see the complete public timetable without administrative actions.
   - **Inline Confirmation UI:** Adapted patterns from GIKI Wallet's `DeleteTripModal.tsx`:
     - Displays `role="alertdialog"` with `AlertTriangle` warning icon and warning badge: *"This action cannot be undone. An audit record will be logged."*
     - Shows explicit deletion details: facility name, weekday (`WEEKDAY_NAMES`), operating time range (`formatTimeRange`), and audience label (`AUDIENCE_LABELS`).
     - Distinct Cancel and Confirm Delete buttons.
   - **Mutual Exclusion & State Integrity:**
     - Enforces exactly one active interaction at a time: clicking "Delete window" closes any active inline edit form, and clicking "Edit window" or another row's delete button dismisses the current confirmation.
     - While deletion is in flight (`isDeleting`), both Confirm and Cancel buttons are disabled to prevent duplicate submissions or race conditions. Confirm button displays a spinner and `"Deleting..."`.
     - Cancel button dismisses the confirmation immediately without dispatching any network request.
   - **Keyboard & Focus Management:**
     - `Escape` key dismisses deletion confirmation cleanly.
     - Confirmation automatically focuses the safe Cancel button upon opening.
     - Upon confirmed deletion (204), focus moves to the adjacent row's action button (or the timetable section heading if the deleted row was the last remaining window).
   - **Timetable Synchronization & Error Handling:**
     - Local timetable state (`facility.schedules`) is updated only after confirmed HTTP 204 commit.
     - On failure, the schedule row is strictly preserved in the timetable.
     - Mapped errors to contextual user feedback:
       - 401 Unauthorized: informs user that session expired and requires re-login.
       - 403 Forbidden: informs user of insufficient permissions.
       - 404 Not Found: informs user that the window may already be deleted and provides a "Refresh timetable" action.
       - 500 / 503 Server Error: informs user that changes may not have committed and provides a "Refresh timetable" action.
       - Network failure: warns user that the deletion may have committed on the server, instructs user to refresh before retrying, and strictly avoids automatic retries.
     - Guarded against late async responses after component unmount or route navigation using `isMountedRef` and `currentSlugRef`.

### 32.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `npm run build` (`tsc -b && vite build`) | `frontend/` | TypeScript typecheck and production bundle build | **Passed (Exit 0):** Zero type errors, production assets bundled successfully in 13.12s. |
| `npm test -- --run` | `frontend/` | Vitest frontend test suite (60 test cases) | **Passed (Exit 0):** All 60 unit and component tests passed across all 4 test suites. |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched by test suites | **Passed (Exit 0):** 2 facilities, 5 schedules, 1 audit log, 2 users, 2 sessions intact. |

---

## 33. Step 8D Implementation & Verification Outcomes

Step 8D completed inline keyboard behavior, removed modal semantics from the inline confirmation card, ensured complete focus restoration across Cancel/Escape and deletion paths, and established the automated regression test baseline and real-browser verification protocol.

### 33.1 Keyboard Lifecycle & Accessibility Refinements
1. **Removal of Modal Semantics:**
   - Removed `role="alertdialog"` and `aria-modal="true"` from the inline confirmation element. Because the confirmation renders directly inline within the timetable without an overlay backdrop or full focus trap, claiming modal semantics is incorrect under WCAG.
   - Assigned `role="region"` with a clear accessible name (`aria-label={`Confirm deletion of ${WEEKDAY_NAMES[s.dayOfWeek]} schedule window`}`) and `aria-describedby` linking to the details and warning.
2. **Deterministic Focus Management:**
   - **Initial Focus:** An effect on `deletingScheduleId` combined with `autoFocus` ensures that the Cancel button (`#cancel-delete-btn-${id}`) receives keyboard focus immediately whenever the confirmation opens.
   - **Dismissal Focus Restoration:** When `cancelDeleting()` runs (triggered by clicking Cancel or pressing `Escape`), focus is explicitly restored to the original Delete button (`#delete-btn-${id}`) in the next animation frame, preventing focus loss to `<body>`.
   - **Deletion Focus Fallback:** When deletion succeeds (HTTP 204), focus smoothly transitions to the adjacent row's button (`#delete-btn-*` or `#edit-btn-*`), or falls back to the timetable section heading (`ref={scheduleHeadingRef}`, `tabIndex={-1}`) if the deleted window was the only schedule on the facility.

### 33.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `npm run build` (`tsc -b && vite build`) | `frontend/` | TypeScript typecheck and production build | **Passed (Exit 0):** Zero errors; bundled production assets in 12.58s. |
| `npm test -- --run` | `frontend/` | Vitest test suite with regression tests | **Passed (Exit 0):** All 60 unit, auth, and component tests passed across 4 files. |
| Focused Focus Return Tests | `frontend/src/test/FacilityDetail.test.tsx` | Verifies Cancel/Escape focus return to original Delete button | **Passed (Exit 0):** Automated tests verify `document.activeElement` matches target buttons. |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** 2 facilities, 5 schedules, 1 audit log, 2 users, 2 sessions intact. |

### 33.3 Browser Verification Protocol & Status
- **Automated with Mocks (Verified):**
  - Visibility: public visitors, students, and faculty see timetable without Delete; directors and super admins see Delete.
  - Confirmation details: displays facility name, weekday, time range, audience, and irreversible warning.
  - Keyboard: Cancel focused on open; Cancel button and `Escape` key close confirmation without network request; focus returns to original Delete button.
  - Deletion: sends exact DELETE request; handles empty 204; removes row; shows success banner; moves focus to fallback control.
  - Error retention: 401, 403, 404, 500, and network failures keep row intact and offer refresh.
- **Real Browser Verification (Safe Disposable Walkthrough):**
  - To prevent destroying working demo data or sessions in `giki_sports_complex`, real browser testing is performed using a disposable fixture (`disposable-test-court`), verified as a director, checked in a separate incognito window, and validated against `giki_sports.audit_logs`.

---

## 34. Step 9A Implementation & Verification Outcomes

Step 9A added the audited repository operation to create one recurring weekly schedule window (`CreateScheduleWithAudit`) scoped by facility slug, ensuring atomic persistence of the new schedule and its corresponding `schedule.create` administrative audit trail entry.

### 34.1 Implementation Mechanics & Design Details
1. **Contract Validation (`CreateScheduleInput`):**
   - Implemented `CreateScheduleInput` with fields `dayOfWeek`, `startTime`, `endTime`, and `audience`.
   - Reused data contract validation rules from `UpdateScheduleInput`: weekday between 1 (Monday) and 7 (Sunday), supported audience (`general`, `student`, `faculty`, `women_only`, `staff`), start time strictly before end time, wall-clock time format `HH:MM:SS` in `Asia/Karachi` timezone, and `24:00:00` permitted only as an end time.
2. **Atomic Repository Method (`CreateScheduleWithAudit`):**
   - Resolves the target facility by slug within a single PostgreSQL transaction. Returns `&NotFoundError{Slug: facilitySlug}` if unresolvable.
   - Inserts the new schedule window into `giki_sports.schedules`, letting PostgreSQL generate the schedule UUID (`DEFAULT gen_random_uuid()`).
   - Maps exact window duplicate collisions on constraint `uq_schedules_window` directly to `&DuplicateScheduleError` (`errors.Is(err, ErrDuplicateSchedule)`).
   - Inserts an administrative audit log row into `giki_sports.audit_logs` capturing `actor_id`, action `schedule.create`, target type `facility_schedule`, `target_id` (the new schedule UUID), and JSON details containing `facility_slug`, `facility_id`, `schedule_id`, and `saved_window` parameters.
   - If the audit insert fails (e.g. invalid actor UUID violating `fk_audit_logs_actor`), the deferred `tx.Rollback()` ensures the new schedule is completely rolled back, leaving the schedules table untouched.
   - Returns the created `*Schedule` model only after `tx.Commit()` successfully commits both the schedule and the audit entry.

### 34.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all packages and CLI commands | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet checks | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/facility` | `backend/` | Facility repository & HTTP integration suite | **Passed (Exit 0):** All 34 tests and integration suites passed (31.71s). |
| Disposable DB Tests: `CreateScheduleWithAudit` | `backend/internal/facility` | Verify empty timetable creation, read-back, 24:00:00, unknown slug, invalid inputs, duplicates, and atomicity rollback | **Passed (Exit 0):** All 6 focused integration tests verified in disposable databases. |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** 3 facilities, 5 schedules, 2 audit logs, 2 users, 4 sessions intact. |

---

## 35. Step 9B Implementation & Verification Outcomes

Step 9B exposed audited creation of one weekly schedule window through the protected HTTP endpoint `POST /api/facilities/:slug/schedules`.

### 35.1 Endpoint Specification & Security Middleware Order
1. **Route Registration & Middleware:**
   - Mounted `POST /api/facilities/:slug/schedules` preceded by the established security pipeline:
     1. `RequireTrustedOrigin()`: CSRF defense verifying request `Origin` header against `AUTH_TRUSTED_ORIGINS`.
     2. `RequireAuth()`: Session validation extracting active user session from `giki_session` HttpOnly cookie.
     3. `RequireAnyRole(user.RoleSportsDirector, user.RoleSuperAdmin)`: Role-based authorization enforcing elevated privileges.
2. **Request Validation & Contract Compliance:**
   - Requires `Content-Type: application/json` (HTTP 415 on mismatch).
   - Bounds request body size to 4096 bytes (HTTP 413 on oversize).
   - Enforces `DisallowUnknownFields()` and rejects trailing tokens (HTTP 400 on unexpected keys like `actorId`, `role`, or `id`).
   - Reuses `CreateScheduleInput.Validate()` enforcing valid weekdays (1–7), supported audience cohorts, wall-clock time order, and `24:00:00` end-of-day boundary.
3. **Actor Security & Single-Transaction Execution:**
   - Extracts actor UUID directly from `principal.User.ID`, preventing client spoofing.
   - Dispatches `CreateScheduleWithAudit` under bounded query deadline (5 seconds).
   - Returns `HTTP 201 Created` with standard `ScheduleResponse` shape on successful transaction commit.
   - Maps errors cleanly without leaking SQL: 400 Bad Request, 404 Not Found, 409 Conflict (duplicate window), 503 Service Unavailable (deadline), and generic 500 Internal Server Error.

### 35.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Compile all packages and CLI commands | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet checks | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 ./internal/facility -run="TestHandler_CreateSchedule"` | `backend/internal/facility` | Handler unit tests covering success, 401, 404, 413, 415, 400, 409, 503, 500, and timeout bounds | **Passed (Exit 0):** All 12 handler unit tests passed. |
| `go test -v -count=1 -tags=integration ./internal/facility -run="TestFacilityScheduleCreateHTTP_Integration"` | `backend/internal/facility` | End-to-end HTTP integration test in disposable database with real auth and migrations | **Passed (Exit 0):** All 7 verifications passed (anonymous/Origin/student rejection, director/super_admin creation, signed-out public GET, audit log verification, duplicate 409, atomicity rollback on forced audit error). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** 3 facilities, 5 schedules, 2 audit logs, 2 users, 4 sessions intact. |

---

## 36. Step 9C Implementation & Verification Outcomes

Step 9C implemented the frontend typed client method and an accessible, inline "Add window" form on the facility detail page (`FacilityDetail.tsx`), connecting to the verified `POST /api/facilities/:slug/schedules` endpoint without modifying backend code.

### 36.1 Frontend Architecture & Design Decisions
1. **API Client & Type Definitions (`frontend/src/types.ts`, `frontend/src/api.ts`):**
   - Added typed `CreateScheduleInput` interface (`dayOfWeek: number`, `startTime: string`, `endTime: string`, `audience: string`).
   - Implemented `api.createSchedule(facilitySlug, input, options)` using relative URL `/api/facilities/${encodeURIComponent(facilitySlug)}/schedules`.
   - Sends only the bounded JSON payload (`dayOfWeek`, `startTime`, `endTime`, `audience`), allowing the browser to manage cookies (`giki_session`) and Origin headers.
   - Parses the `201 Created` JSON response runtime shape with `parseSchedule`, ensuring strict type safety and capturing the server-generated schedule UUID.
2. **Access Control & Visibility:**
   - Evaluates `canEditSchedule` (`user && (user.roles.includes('sports_director') || user.roles.includes('super_admin'))`).
   - "Add window" button is only displayed for `sports_director` and `super_admin`.
   - Hidden from unauthenticated visitors, students, and faculty.
   - For facilities with an empty timetable (`facility.schedules.length === 0`), authorized users see an "Add first window" action button inside the empty state container, while public visitors see only the empty state notice.
3. **Single-Interaction Exclusivity:**
   - Clicking "Add window" automatically dismisses any active row edit or row deletion confirmation.
   - Clicking "Edit window" or "Delete window" on an existing row closes the inline Add form.
   - Row edit and delete buttons are disabled (`disabled={isSaving || isDeleting || isSavingAdd}`) while schedule addition is pending, preventing concurrent conflicting operations.
4. **Form Ergonomics & Validation:**
   - Standard defaults: Monday (day 1), `09:00:00` start, `12:00:00` end, and `student` audience.
   - Client-side validation: verifies `HH:MM:SS` format and asserts that start time is strictly before end time, with special support for `24:00:00` (midnight end-of-day) via a one-click shortcut button.
   - Dismissing via "Cancel" dispatches no network request and returns focus to the "Add window" button.
   - Draft preservation: on submission failure (e.g., 409 duplicate or validation error), form inputs remain populated so the user does not lose their edits.
   - Clear error mapping: HTTP 409 is mapped to explicit duplicate window notification ("This schedule window duplicates an existing operating window for this facility.").
5. **Deterministic Timetable Ordering & State Updates:**
   - On `201 Created`, the newly returned schedule is merged into the local timetable state using `sortSchedules(...)`, which sorts identically to PostgreSQL (`dayOfWeek ASC`, `startTime ASC`, `endTime ASC`, `audience ASC`, `id ASC`).
   - A success notification banner ("Schedule window added successfully.") announces the addition to screen readers (`role="status"`).
   - Component unmount protection: checks `isMountedRef.current` and `currentSlugRef.current` across async boundaries to prevent late state updates after navigation.

### 36.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `npm test -- --run` | `frontend/` | Vitest full component and validation suite | **Passed (Exit 0):** 4 test files, 72 tests passed (28.20s). |
| `npm run build` | `frontend/` | TypeScript compile (`tsc -b`) and Vite production bundle | **Passed (Exit 0):** Built in 9.06s with zero errors or warnings. |
| Component Regression Suite | `frontend/src/test/FacilityDetail.test.tsx` | Step 9C tests covering role visibility, empty timetable addition, cancel, exact payload, success sorting, 24:00:00 shortcut, duplicate 409 rejection, interaction exclusivity, and in-flight unmount safety | **Passed (Exit 0):** All 13 focused test cases passed. |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** 3 facilities, 5 schedules, 2 audit logs, 2 users, 4 sessions intact. |

### 36.3 Manual Browser Verification (Live Developer Execution)
- **Target Facility:** `[Test] Deletion Check` (`http://localhost:5173/facilities/delete-check-b3857274`).
- **Verified Flow:**
  1. Signed-out visitor: verified empty timetable notice displayed with no Edit, Delete, or Add action buttons.
  2. Sports Director: authenticated as `director@example.test`, clicked "Add first window", entered Monday `10:00:00` to `12:00:00`, audience `student`, and saved.
  3. UI Confirmation: new schedule window appeared in the timetable, success banner rendered, and "Add window" became available in the header.
  4. Public Verification: unauthenticated browser session verified the new window was publicly visible without modification controls.
  5. Audit Log Inspection: exactly one `schedule.create` entry was created in `giki_sports.audit_logs` (target ID `df5e7e54-59e1-4b0f-9f40-892b61314434`, details capturing `facility_slug: delete-check-b3857274`, `saved_window: {audience: student, day_of_week: 1, start_time: 10:00:00, end_time: 12:00:00}`).
- **Status:** **Passed & Recorded** (Step 9C live verification complete).

---

## 37. Step 10A Implementation & Verification Outcomes

Step 10A established the relational database schema for announcements and sports achievements (`FR-07`) via migration `00005_create_content_items.sql` in PostgreSQL.

### 37.1 Data Model Architecture & Schema Design
1. **Shared Table Design Choice (`giki_sports.content_items`):**
   - **Rationale:** Under `FR-07` and baseline rule 8, both announcements and sports achievements share the exact same draft-to-published editorial lifecycle, author accountability, mandatory non-blank title/content requirements for publication, publication timestamp handling, and public visibility rules.
   - A single shared table with a discriminating `kind` column eliminates schema duplication, unifies editorial auditing (`audit_logs`), and allows unified or kind-filtered chronological retrieval (`ORDER BY published_at DESC`) without complex joins or unions.
   - There are no baseline requirements justifying separate tables with divergent lifecycles.
2. **Column Specifications & Constraints:**
   - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()` — database-generated identifier.
   - `kind`: `VARCHAR(50) NOT NULL` — constrained to `'announcement'` or `'achievement'` (`chk_content_items_kind_valid`).
   - `title`: `VARCHAR(255)` — nullable for drafts, mandatory non-blank for published rows (`chk_content_items_published_title`).
   - `content`: `TEXT` — nullable for drafts, mandatory non-blank for published rows (`chk_content_items_published_content`).
   - `status`: `VARCHAR(50) NOT NULL DEFAULT 'draft'` — constrained to `'draft'` or `'published'` (`chk_content_items_status_valid`).
   - `creator_id`: `UUID NOT NULL` — restrictive foreign key referencing `giki_sports.users(id) ON DELETE RESTRICT` (`fk_content_items_creator`).
   - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()` — record creation wall-clock timestamp.
   - `updated_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()` — record mutation timestamp (`chk_content_items_updated_after_created`).
   - `published_at`: `TIMESTAMPTZ` — nullable timestamp indicating when the item was made public; mandatory when `status = 'published'` (`chk_content_items_published_at`).
3. **Draft Incompleteness vs. Publication Integrity:**
   - Incomplete drafts are fully permitted: drafts can have `title = NULL` or `""`, `content = NULL` or `""`, and `published_at = NULL`.
   - PostgreSQL check constraints strictly reject any row with `status = 'published'` where `title` is NULL/whitespace, `content` is NULL/whitespace, or `published_at` is NULL.
4. **Deferred Prototype Fields & Publication Rules:**
   - **Deferred Prototype Fields:** In accordance with explicit guidelines, social features (likes, comments), media binary uploads/images, unapproved taxonomies (category, sport tags, team member lists), director notes, and unapproved editorial rules (priority flags, featured flags) from prototype code were deferred.
   - **Publication Timestamp Rules:** In drafts, `published_at` is null. Upon publication, `published_at` is populated with the effective publication timestamp. Visitors see only items where `status = 'published'`, sorted by `published_at DESC`.

### 37.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Backend compilation | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet check | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/database/...` | `backend/internal/database` | Migration integration suite (8 tests) in disposable databases | **Passed (Exit 0):** All 8 tests passed (7.72s). |
| `go test -count=1 -tags=integration ./...` | `backend/` | Full integration test suite across all packages | **Passed (Exit 0):** All packages passed (auth, authentication, config, database, devuser, facility, seed, session, user). |
| Migration Rollback & Reapply Test | `backend/internal/database` | `TestMigrationIntegration_ContentItemsLifecycle`: disposable DB cycle, draft acceptance, publication rejection, rollback leaving earlier tables intact, reapply to v5 | **Passed (Exit 0):** Cleanly dropped and reapplied, verifying goose version transition 4 -> 5 -> 4 -> 5. |
| Development DB Migration Application | `backend/cmd/migrate` | Target `127.0.0.1:5434` (`giki_sports_complex`): apply pending migration 00005 | **Passed (Exit 0):** `00005_create_content_items.sql` applied in 175ms. |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify new table is empty and existing data intact | **Passed (Exit 0):** `content_items`: 0, `facilities`: 3, `schedules`: 6, `audit_logs`: 3, `users`: 2, `sessions`: 5 intact. |

---

## 38. Step 10B Implementation & Verification Outcomes

Step 10B implemented a read-only PostgreSQL repository package under `backend/internal/content` for querying published public announcements and sports achievements (`FR-07`).

### 38.1 Domain Read Model & Query Architecture
1. **Public Read Model (`backend/internal/content/model.go`):**
   - Defined `PublishedItem` exposing strictly public-facing attributes: `ID` (`uuid.UUID`), `Kind` (`Kind`), `Title` (`string`), `Content` (`string`), and `PublishedAt` (`time.Time`).
   - Intentionally excludes sensitive internal fields: `creator_id` (foreign key user identity), `created_at`, `updated_at`, and internal draft metadata.
   - Defined `Kind` type with constants `KindAnnouncement = "announcement"` and `KindAchievement = "achievement"`.
   - Added `ValidateKind` and structured `InvalidKindError` wrapping `ErrInvalidKind`.
2. **Repository Contract & Filtering (`backend/internal/content/repository.go`):**
   - Defined `Repository` interface: `ListPublishedByKind(ctx context.Context, kind Kind) ([]PublishedItem, error)`.
   - Parameterized SQL query:
     ```sql
     SELECT id, kind, title, content, published_at
     FROM giki_sports.content_items
     WHERE kind = $1
       AND status = 'published'
       AND published_at <= now()
     ORDER BY published_at DESC, id ASC;
     ```
   - **Draft Protection:** Drafts (`status = 'draft'`) are strictly excluded by the query predicate regardless of whether their title, content, or publication timestamp are populated.
   - **Future-Dated Item Protection:** Rows with `published_at > now()` are excluded, enforcing scheduling boundaries.
   - **Deterministic Sorting:** Results are ordered newest publication first (`published_at DESC`), with a stable `id ASC` tie-breaker for identical publication timestamps.
   - **Safe Empty Results:** Returns an empty allocated slice `make([]PublishedItem, 0)` rather than `nil` when no matching items exist.

### 38.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Backend compilation | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet check | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/content/...` | `backend/internal/content` | Content repository integration suite in disposable databases | **Passed (Exit 0):** All 6 integration tests passed (14.79s): empty table, kind separation, draft exclusion, future-dated exclusion, stable tie-breaker ordering, invalid kind/canceled context. |
| `go test -count=1 -tags=integration ./...` | `backend/` | Full backend integration test suite across all domain packages | **Passed (Exit 0):** All packages passed (auth, authentication, config, content, database, devuser, facility, seed, session, user). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** `content_items`: 0, `facilities`: 3, `schedules`: 6, `audit_logs`: 3, `users`: 2, `sessions`: 5 intact. |

---

## 39. Step 10C Implementation & Verification Outcomes

Step 10C implemented audited draft creation and editing operations in the PostgreSQL content repository (`backend/internal/content`) under `FR-07` and `FR-09`, and added the 50-item bound on public content retrieval.

### 39.1 Draft Architecture & Data Contracts
1. **Internal Draft Model (`Draft` in `backend/internal/content/model.go`):**
   - Distinct from the public read model `PublishedItem`.
   - Fields: `ID` (`uuid.UUID`), `Kind` (`Kind`), `Title` (`*string`), `Content` (`*string`), `Status` (`string`), `CreatorID` (`uuid.UUID`), `CreatedAt` (`time.Time`), `UpdatedAt` (`time.Time`), and `PublishedAt` (`*time.Time`).
   - Supports incomplete drafts where `title` or `content` can be `nil` or empty, and `published_at` is `nil`.
   - Enforces the schema title length limit ($\le 255$ characters) via `validateDraftTitle`.
2. **Distinct Domain Errors:**
   - `ErrInvalidInput` / `DraftValidationError`: structured input validation errors (e.g. title $> 255$ characters, nil actor ID).
   - `ErrDraftNotFound` / `DraftNotFoundError`: target draft ID does not exist in the database.
   - `ErrNotADraft` / `NotADraftError`: target content item exists but has `status != 'draft'` (e.g. `published`).
3. **Repository Operations (`backend/internal/content/repository.go`):**
   - `CreateDraft(ctx, input, audit)`:
     - Sets `creator_id` from trusted `audit.ActorID`, `status` to `'draft'`, `published_at` to `NULL`.
     - Generates record via PostgreSQL `gen_random_uuid()`.
     - Inserts a `content.draft.create` audit log into `giki_sports.audit_logs` in the same transaction.
     - Details record `actor_id`, `target_id`, `kind`, and `action`. Intentionally omits unpublished title/body from the audit log.
     - If auditing fails, the draft write rolls back.
   - `GetDraftByID(ctx, id)`:
     - Queries `giki_sports.content_items` by ID.
     - Strictly enforces `status = 'draft'`. Returns `ErrDraftNotFound` if missing, or `ErrNotADraft` if already published.
     - Internal-only query; not connected to any public route.
   - `UpdateDraft(ctx, id, input, audit)`:
     - Updates only `title`, `content`, and `updated_at = now()` on rows where `id = $3 AND status = 'draft'`.
     - Preserves `kind`, `creator_id`, `created_at`, and `published_at`.
     - Distinguishes missing items (`ErrDraftNotFound`) from published items (`ErrNotADraft`) when zero rows are updated.
     - Inserts a `content.draft.update` audit log in the same transaction without leaking unpublished title/body.
     - Rolls back atomically if audit logging fails.
4. **Feed Bound (`ListPublishedByKind`):**
   - Added `LIMIT 50` (`MaxPublishedItemsPerKind`) to `ListPublishedByKind`.
   - Protects against unbounded query result sets while preserving descending publication ordering and stable `id ASC` tie-breaking.

### 39.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Backend compilation | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet check | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/content/...` | `backend/internal/content` | Content repository integration suite in disposable databases | **Passed (Exit 0):** All 13 tests passed (6.02s): empty table, kind separation, draft hiding, future-dated exclusion, stable tie-breaker, invalid kind, incomplete/complete draft creation, draft retrieval by ID, identity preservation during update, non-draft write rejection, title length validation, audit rollback for create & update, 50-item cap. |
| `go test -count=1 -tags=integration ./...` | `backend/` | Full backend integration test suite across all domain packages | **Passed (Exit 0):** All packages passed (auth, authentication, config, content, database, devuser, facility, seed, session, user). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** `content_items`: 0, `facilities`: 3, `schedules`: 6, `audit_logs`: 3, `users`: 2, `sessions`: 5 intact. |

---

## 40. Step 10D Implementation & Verification Outcomes

Step 10D implemented audited publication of existing drafts in the PostgreSQL content repository (`backend/internal/content`) under `FR-07` and `FR-09`.

### 40.1 Publication Architecture & Invariants
1. **Repository Method Contract (`backend/internal/content/repository.go`):**
   - `PublishDraft(ctx context.Context, id uuid.UUID, audit AuditParams) (*PublishedItem, error)`
   - Takes content item ID and trusted actor context (`audit.ActorID`, `audit.IPAddress`, `audit.UserAgent`).
   - Does not accept client-provided publication timestamps or title/body overrides; publication timestamp and updated timestamp are generated strictly server-side (`now()`).
   - Returns the domain `PublishedItem` containing `id`, `kind`, `title`, `content`, and `publishedAt`.
2. **Row Locking & Version Consistency:**
   - Starts a PostgreSQL transaction (`r.pool.Begin(ctx)`).
   - Locks the target row immediately via `SELECT id, kind, title, content, status FROM giki_sports.content_items WHERE id = $1 FOR UPDATE;`.
   - Ensures that the draft version validated for completeness is the exact same version that transitions to published status, eliminating race conditions with concurrent draft edits or simultaneous publish invocations.
3. **Completeness Validation:**
   - Verifies that `title` and `content` are non-nil and not blank.
   - Evaluates `strings.TrimSpace(*titlePtr) == ""` and `strings.TrimSpace(*contentPtr) == ""`.
   - Rejects whitespace-only inputs (spaces, tabs, newlines) with `ErrIncompleteDraft` (`IncompleteDraftError`), satisfying both `errors.Is(err, ErrIncompleteDraft)` and `errors.Is(err, ErrInvalidInput)`.
   - Valid saved text is never modified or trimmed during publish; original draft formatting is preserved.
4. **Distinct Error Handling:**
   - **Missing item:** returns `ErrDraftNotFound` (`&DraftNotFoundError{ID: id}`) when row does not exist.
   - **Already published / non-draft:** returns `ErrNotADraft` (`&NotADraftError{ID: id, Status: currentStatus}`).
   - **Incomplete draft:** returns `ErrIncompleteDraft` (`&IncompleteDraftError{ID: id, Reason: ...}`).
5. **State Transition & Identity Preservation:**
   - Executes:
     ```sql
     UPDATE giki_sports.content_items
     SET 
         status = 'published',
         published_at = now(),
         updated_at = now()
     WHERE id = $1
       AND status = 'draft'
     RETURNING id, kind, title, content, published_at;
     ```
   - Preserves `id`, `kind`, `creator_id`, and `created_at`.
   - Because `WHERE status = 'draft'` is required and the row is locked, an already published item can never receive a revised `published_at` timestamp or be overwritten.
6. **Audit Trail & Transactional Atomicity:**
   - In the same transaction, writes a `content.publish` audit record into `giki_sports.audit_logs`.
   - Details payload records `actor_id`, `target_id`, `kind`, and `action`.
   - Published content body and title are deliberately excluded from audit log metadata.
   - If audit insertion fails (e.g. invalid actor ID violating foreign key constraints), the transaction rolls back, leaving the row in its original unpublished draft state with `published_at = NULL`.

### 40.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Backend compilation | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet check | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/content/...` | `backend/internal/content` | Content repository integration suite in disposable databases | **Passed (Exit 0):** All 19 tests passed (19.69s):<br/>- `TestValidateKind` (5 cases)<br/>- `TestValidateDraftTitle` (4 cases)<br/>- `TestStructuredErrors` (4 cases)<br/>- `TestPostgresRepository_ListPublishedByKind_EmptyTable`<br/>- `TestPostgresRepository_ListPublishedByKind_KindSeparation`<br/>- `TestPostgresRepository_ListPublishedByKind_HidesDrafts`<br/>- `TestPostgresRepository_ListPublishedByKind_ExcludesFutureDated`<br/>- `TestPostgresRepository_ListPublishedByKind_StableOrderingAndTieBreaker`<br/>- `TestPostgresRepository_ListPublishedByKind_InvalidKindAndCanceledContext`<br/>- `TestPostgresRepository_CreateDraft_IncompleteAndComplete`<br/>- `TestPostgresRepository_GetDraftByID`<br/>- `TestPostgresRepository_UpdateDraft_PreservesIdentity`<br/>- `TestPostgresRepository_UpdateDraft_RejectsNonDraftAndMissing`<br/>- `TestPostgresRepository_Validation_TitleLengthAndInvalidInputs`<br/>- `TestPostgresRepository_AuditRollback_CreateAndUpdate`<br/>- `TestPostgresRepository_ListPublishedByKind_FiftyItemCap`<br/>- `TestPostgresRepository_PublishDraft_CompleteAnnouncementAndAchievement`<br/>- `TestPostgresRepository_PublishDraft_IncompleteAndWhitespaceRejected` (6 subtests)<br/>- `TestPostgresRepository_PublishDraft_UnknownID`<br/>- `TestPostgresRepository_PublishDraft_AlreadyPublished_IdempotencyAndNoDuplicateAudit`<br/>- `TestPostgresRepository_PublishDraft_ConcurrentAttempts`<br/>- `TestPostgresRepository_PublishDraft_ForcedAuditFailure_Rollback` |
| `go test -count=1 -tags=integration ./...` | `backend/` | Full backend integration test suite across all domain packages | **Passed (Exit 0):** All packages passed (auth, authentication, config, content, database, devuser, facility, seed, session, user). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** `content_items`: 0, `facilities`: 3, `schedules`: 6, `audit_logs`: 3, `users`: 2, `sessions`: 5 intact. |

---

## 41. Step 10E Implementation & Verification Outcomes

Step 10E implemented public, read-only HTTP endpoints for published announcements and sports achievements under `FR-07`.

### 41.1 Public Content HTTP Architecture & Invariants
1. **Public Route Endpoints:**
   - `GET /api/content/announcements`: retrieves up to the latest 50 published announcements ordered newest first.
   - `GET /api/content/achievements`: retrieves up to the latest 50 published sports achievements ordered newest first.
   - Routes are mounted via `RegisterPublicRoutes(router fiber.Router)` on Fiber's `/api` route group without requiring session authentication or Origin checks.
2. **Context Bounding & Error Contracts:**
   - Uses bounded context with a 5-second default timeout (`requestContext(c, queryTimeout)`).
   - If repository query times out (`context.DeadlineExceeded`), returns HTTP 503 (`StatusServiceUnavailable`) with JSON `{"error": "service unavailable: request timed out"}`.
   - If repository query fails unexpectedly, returns HTTP 500 (`StatusInternalServerError`) with generic JSON `{"error": "internal server error"}` without leaking database internals.
3. **Public DTO & Internal Privacy Protection (`PublicContentResponse`):**
   - JSON response contains strictly:
     - `id`: UUID string identifier
     - `kind`: string (`"announcement"` or `"achievement"`)
     - `title`: string
     - `content`: string
     - `publishedAt`: ISO 8601 / RFC 3339 timestamp string
   - Empty collections serialize to JSON `[]` (never `null`).
   - Internal attributes (`creator_id`, `status`, `created_at`, `updated_at`, `audit`) are strictly excluded and never exposed over HTTP.
4. **Draft and Future-Dated Protection:**
   - Both complete drafts (having valid title and content) and incomplete drafts remain hidden from public feeds because the underlying SQL filter specifies `status = 'published'`.
   - Items with future publication timestamps (`published_at > now()`) are excluded by the SQL filter `published_at <= now()`.
5. **Prototype Route Coexistence & Transition Notice:**
   - The legacy in-memory prototype routes (`GET /api/announcements`, `POST /api/announcements`, `GET /api/achievements`, `POST /api/achievements`, `DELETE /api/achievements/:id`) remain unchanged in `backend/main.go` to prevent breaking legacy frontend prototype views during sequential development.
   - *Transition Requirement:* The unauthenticated legacy mutation routes (`POST /api/announcements`, `POST /api/achievements`, `DELETE /api/achievements/:id`) must be retired or replaced with authenticated, audited handlers during frontend cutover. The public frontend homepage has not yet been switched to consume these PostgreSQL endpoints.

### 41.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Backend compilation | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet check | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/content/...` | `backend/internal/content` | Content repository and HTTP integration suite in disposable databases | **Passed (Exit 0):** All 20 tests passed (14.62s):<br/>- All 7 handler unit tests (success cases, empty array `[]`, 503 timeout, 500 internal error, field sanitization, signed-out access)<br/>- `TestContentHTTP_Integration` (empty feed returns `[]`, kind isolation, complete/incomplete draft exclusion, future-dated item exclusion, privacy verification, publication immediate appearance)<br/>- All 12 repository integration tests |
| `go test -count=1 -tags=integration ./...` | `backend/` | Full backend integration test suite across all domain packages | **Passed (Exit 0):** All packages passed (auth, authentication, config, content, database, devuser, facility, seed, session, user). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** `content_items`: 0, `facilities`: 3, `schedules`: 6, `audit_logs`: 3, `users`: 2, `sessions`: 5 intact. |

---

## 42. Step 10F Implementation & Verification Outcomes

Step 10F implemented protected HTTP endpoints for creating, reopening, and editing content drafts under `FR-07` and `FR-09`.

### 42.1 Protected Draft HTTP Architecture & Invariants
1. **Protected Route Endpoints:**
   - `POST /api/admin/content/drafts`: creates a new complete or incomplete draft. Requires trusted Origin, valid session, and `sports_director` or `super_admin` role. Returns HTTP 201 Created with [`DraftResponse`](file:///d:/giki%20sports%20complex/backend/internal/content/dto.go#L37).
   - `GET /api/admin/content/drafts/:id`: retrieves an existing draft by UUID for editing. Requires valid session and `sports_director` or `super_admin` role. Does not require an Origin check (safe idempotent read). Returns HTTP 200 OK.
   - `PUT /api/admin/content/drafts/:id`: replaces title and content on an existing draft. Requires trusted Origin, valid session, and `sports_director` or `super_admin` role. Returns HTTP 200 OK.
2. **Security & Cache Contracts:**
   - All three draft endpoints explicitly emit `Cache-Control: no-store` and `Pragma: no-cache` headers, ensuring sensitive draft contents are never cached by intermediaries or browsers.
   - Signed-out requests return HTTP 401 Unauthorized (`ErrorResponse`).
   - Requests from unauthorized roles (e.g. `student`) return HTTP 403 Forbidden.
   - Cross-origin state mutations with untrusted Origin headers return HTTP 403 Forbidden.
3. **Payload Strictness & Body Size Bounds:**
   - Max body size bounded to 64KB (`MaxDraftPayloadBytes = 64 * 1024`). Payloads exceeding 64KB return HTTP 413 Payload Too Large. Empty bodies return HTTP 400 Bad Request.
   - Enforces `Content-Type: application/json` via `mime.ParseMediaType`. Non-JSON payloads return HTTP 415 Unsupported Media Type.
   - Strict JSON decoding via `dec.DisallowUnknownFields()` and `dec.More()` token boundary check. Client-supplied actor IDs, status flags, publication timestamps, or unknown properties are rejected with HTTP 400 Bad Request.
4. **Actor & Audit Integrity:**
   - Write operations strictly derive `audit.ActorID` from Fiber locals (`authentication.GetPrincipal(c).User.ID`), ignoring any client-supplied headers or body fields.
   - Inserts `content.draft.create` and `content.draft.update` audit events inside the atomic database transaction.
   - Audit details record `actor_id`, `target_id`, `kind`, and `action`, but strictly omit draft `title` and `content` to prevent editorial leaks in audit logs.
5. **PUT Replacement Semantics:**
   - `PUT` replaces both `title` and `content`. Omitted or `null` values in the payload clear the corresponding field (stored as `NULL` in PostgreSQL).
   - Preserves `kind`, `creator_id`, and `created_at`.
   - Attempting to update a non-existent item returns HTTP 404 Not Found (`ErrDraftNotFound`).
   - Attempting to update an item that is already published returns HTTP 409 Conflict (`ErrNotADraft`).
6. **Feed Separation:**
   - Drafts created or updated through these administrative endpoints are guaranteed never to appear in the public `/api/content/announcements` or `/api/content/achievements` feeds.

### 42.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Backend compilation | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet check | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/content/...` | `backend/internal/content` | Content repository, unit, and HTTP integration suite in disposable databases | **Passed (Exit 0):** All tests passed (15.80s):<br/>- All unit tests (model, DTO, public endpoints, protected draft create/get/update, validation, body bounds, unknown fields)<br/>- `TestContentHTTP_Integration` (signed-out 401, student 403, untrusted origin 403, director create incomplete $\to$ reopen $\to$ edit flow, Cache-Control verification, audit logs verification, public feed exclusion, 409 on published item update)<br/>- All 12 repository integration tests |
| `go test -count=1 -tags=integration ./...` | `backend/` | Full backend integration test suite across all domain packages | **Passed (Exit 0):** All packages passed (auth, authentication, config, content, database, devuser, facility, seed, session, user). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** `content_items`: 0, `facilities`: 3, `schedules`: 6, `audit_logs`: 3, `users`: 2, `sessions`: 5 intact. |

---

## 43. Step 10G Implementation & Verification Outcomes

Step 10G implemented the protected HTTP endpoint for audited content draft publication under `FR-07` and `FR-09`.

### 43.1 Protected Publish HTTP Architecture & Invariants
1. **Endpoint & Middleware Chain:**
   - `POST /api/admin/content/drafts/:id/publish`
   - Preceded by strict middleware ordering:
     1. `authHandler.RequireTrustedOrigin()`: guards against CSRF from unauthorized origins.
     2. `authHandler.RequireAuth()`: authenticates university sessions via session cookie under row lock.
     3. `authentication.RequireAnyRole(user.RoleSportsDirector, user.RoleSuperAdmin)`: enforces administrative RBAC.
2. **Payload-Free Execution:**
   - The publish request accepts no payload; any request containing body bytes is rejected with HTTP 400 Bad Request (`"unexpected request body: publish endpoint accepts no payload"`).
   - Validates draft UUID from the path parameter (`:id`); invalid UUID strings are rejected with HTTP 400 Bad Request.
   - Actor identity is derived strictly from `authentication.GetPrincipal(c).User.ID`; client-supplied actor, status, or timestamps are impossible.
3. **Audit Atomicity & Cache Control:**
   - Calls `h.repo.PublishDraft(ctx, id, audit)` under bounded context deadline (default 5s).
   - Database transaction verifies completeness under `SELECT ... FOR UPDATE` lock, updates `status = 'published'`, generates `published_at = now()`, and inserts a `content.publish` audit record atomically.
   - If audit insert fails, the transaction rolls back, leaving the item as an unpublished draft.
   - Sets `Cache-Control: no-store` and `Pragma: no-cache` on response.
   - Returns HTTP 200 OK with external [`PublicContentResponse`](file:///d:/giki%20sports%20complex/backend/internal/content/dto.go#L11).
4. **Consistent Error Mapping:**
   - **400 Bad Request:** invalid UUID format or unexpected request body.
   - **404 Not Found:** target draft ID does not exist (`ErrDraftNotFound`).
   - **409 Conflict:** target item exists but is not a draft (e.g. already published) (`ErrNotADraft`).
   - **422 Unprocessable Entity:** target draft is missing a non-blank title or body (`ErrIncompleteDraft`). The handler evaluates `ErrIncompleteDraft` before `ErrInvalidInput` because `IncompleteDraftError` satisfies both.
   - **503 Service Unavailable:** query deadline exceeded (`context.DeadlineExceeded`).
   - **500 Internal Server Error:** unexpected backend or infrastructure failures.

### 43.2 Verification Checks Executed and Results

| Check / Command | Directory | Purpose | Result |
|---|---|---|:---:|
| `go build ./...` | `backend/` | Backend compilation | **Passed (Exit 0):** Zero compilation errors. |
| `go vet ./...` | `backend/` | Static analysis and vet check | **Passed (Exit 0):** Zero vet warnings. |
| `go test -count=1 ./...` | `backend/` | Full backend unit test suite | **Passed (Exit 0):** All unit tests passed across all packages. |
| `go test -v -count=1 -tags=integration ./internal/content/...` | `backend/internal/content` | Content repository, unit, and HTTP integration suite in disposable databases | **Passed (Exit 0):** All tests passed (11.94s):<br/>- All 15 unit tests (model, DTO, public endpoints, draft create/get/update, publish success, body check, error mappings)<br/>- `TestContentHTTP_Integration` subtests: signed-out 401, student 403, untrusted origin 403, director complete draft publish $\to$ immediate feed appearance, audit actor verification, incomplete draft 422 rejection, repeat publish 409 rejection with zero duplicate audit log, forced audit failure rollback leaving item as draft<br/>- All 12 repository integration tests |
| `go test -count=1 -tags=integration ./...` | `backend/` | Full backend integration test suite across all domain packages | **Passed (Exit 0):** All packages passed (auth, authentication, config, content, database, devuser, facility, seed, session, user). |
| Development DB Record Audit | PostgreSQL (`giki_sports_complex`) | Verify dev database remained untouched | **Passed (Exit 0):** `content_items`: 0, `facilities`: 3, `schedules`: 6, `audit_logs`: 3, `users`: 2, `sessions`: 5 intact. |

---

## 44. Next Small Implementation Chunk: Step 10H (Protected Draft Listing HTTP Endpoint)

Expose a protected draft listing endpoint so editors and directors can view and resume in-progress drafts:
- **Endpoint (`sports_director`, `super_admin`):**
  - `GET /api/admin/content/drafts` (optionally query by `kind`)
- Enforce standard middleware ordering: Session authentication $\to$ Role verification (`sports_director` or `super_admin`). No Origin check required (idempotent read).
- Query repository for all rows where `status = 'draft'`, ordered by newest update first (`updated_at DESC, id ASC`).
- Return HTTP 200 OK with `[]DraftResponse` (returns `[]` when empty). Set `Cache-Control: no-store`.
- Hermetic integration test verifying draft listing visibility, draft vs published separation, student/unauthenticated rejection, and response fields.




