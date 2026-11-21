# Facility Schedule Write Contract Specification

**Document Reference:** `docs/facility-schedule-write-contract.md`  
**Applies To:** Step 7B PostgreSQL Schedule Update Repository Method  
**Module:** Facilities & Scheduling (M2)  
**Requirements Tracking:** Partial implementation of FR-02 (Weekly Schedule Window Management); sets foundation for FR-09 (Administrative Audit Trail).

---

## 1. Architectural Scope & Method Design

Step 7B introduces the first database write operation for facility timetables: updating an existing recurring weekly schedule window. This operation is implemented directly on the PostgreSQL facility repository layer (`facility.Repository.UpdateSchedule`) and is **deliberately not yet exposed via HTTP or the frontend**.

### 1.1 Method Signature & Input Contract

```go
type UpdateScheduleInput struct {
    DayOfWeek int    `json:"dayOfWeek"` // ISO-8601 numeric weekday: 1 = Monday ... 7 = Sunday
    StartTime string `json:"startTime"` // 24-hour local wall-clock format "HH:MM:SS" (e.g. "09:00:00")
    EndTime   string `json:"endTime"`   // 24-hour local wall-clock format "HH:MM:SS" (e.g. "12:00:00" or "24:00:00")
    Audience  string `json:"audience"`  // Allowed: "general", "student", "faculty", "women_only", "staff"
}

UpdateSchedule(ctx context.Context, facilitySlug string, scheduleID uuid.UUID, input UpdateScheduleInput) (*Schedule, error)
```

### 1.2 Invariants & Guarantee Matrix

| Property | Behavior / Invariant | Enforcement Mechanism |
|---|---|---|
| **Dual-Identifier Scoping** | Must match both `f.slug = $2` AND `s.id = $1` AND `s.facility_id = f.id`. A schedule belonging to a different facility returns `ErrScheduleNotFound` without modifying either row. | Scoped SQL `UPDATE ... FROM giki_sports.facilities f WHERE s.id = $1 AND s.facility_id = f.id AND f.slug = $2` |
| **Identity Preservation** | `id`, `facility_id`, and `created_at` are immutable and can never be altered by the update. | Target columns excluded from SQL `SET` clause; original timestamps preserved. |
| **Audit Timestamping** | `updated_at` is refreshed to current database time (`now()`). | SQL `SET updated_at = now()` |
| **Weekday Boundary** | Day of week must be between 1 and 7 inclusive. | Upfront Go validation + PostgreSQL constraint `chk_schedules_day_valid` |
| **Audience Vocabulary** | Strictly limited to provisional contract: `general`, `student`, `faculty`, `women_only`, `staff`. | Upfront Go validation + PostgreSQL constraint `chk_schedules_audience_valid` |
| **Time Order Strictness** | `start_time` must be strictly before `end_time` ($startSeconds < endSeconds$). | Upfront Go validation + PostgreSQL constraint `chk_schedules_time_order` |
| **24:00:00 End-of-Day** | `24:00:00` is permitted strictly as an end time (86,400 seconds), never as a start time. | Upfront Go validation (`allow24` flag) + PostgreSQL `TIME` data type |
| **Collision Prevention** | Proposed window cannot duplicate another window for the same facility on `(facility_id, day_of_week, audience, start_time, end_time)`. | PostgreSQL unique constraint `uq_schedules_window` mapped to `ErrDuplicateSchedule` |

---

## 2. Error Mapping Contract

The repository provides distinct sentinel and typed errors enabling future HTTP handlers to generate accurate HTTP status codes:

```
Domain Error Hierarchy:
├── ErrInvalidInput (sentinel)
│   └── ScheduleValidationError (typed: invalid day, unsupported audience, start >= end, malformed time)
│       ──> Maps to HTTP 400 Bad Request
│
├── ErrScheduleNotFound (sentinel)
│   └── ScheduleNotFoundError (typed: facility slug not found, schedule ID not found, or cross-facility mismatch)
│       ──> Maps to HTTP 404 Not Found
│
├── ErrDuplicateSchedule (sentinel)
│   └── DuplicateScheduleError (typed: window collides with existing schedule on same facility)
│       ──> Maps to HTTP 409 Conflict
│
└── Standard Database Errors (pgx connection errors, context timeouts)
    ──> Maps to HTTP 500 / 503
```

---

## 3. SQL Execution Plan

The repository utilizes parameterized SQL with PostgreSQL's `UPDATE ... FROM ... RETURNING` clause. This achieves atomic row-level update and immediate scan without a secondary `SELECT` query:

```sql
UPDATE giki_sports.schedules s
SET 
    day_of_week = $3,
    start_time = $4::time,
    end_time = $5::time,
    audience = $6,
    updated_at = now()
FROM giki_sports.facilities f
WHERE s.id = $1
  AND s.facility_id = f.id
  AND f.slug = $2
RETURNING 
    s.id, 
    s.facility_id, 
    s.day_of_week, 
    to_char(s.start_time, 'HH24:MI:SS') AS start_time, 
    to_char(s.end_time, 'HH24:MI:SS') AS end_time, 
    s.audience, 
    s.created_at, 
    s.updated_at;
```

### 3.1 Why Scoping Checks Both Facility Slug and Schedule ID
1. **URL Semantic Integrity:** In a REST API, mutations occur at `/api/facilities/:slug/schedules/:id`. The URL contract asserts that the schedule resource `:id` belongs to the parent `:slug`.
2. **Cross-Tenant / Cross-Resource Mutation Prevention:** If the query only conditioned on `s.id = $1`, an administrator intending to edit Badminton Court schedule could inadvertently update a Squash Court schedule if a mistaken or manipulated UUID was submitted.
3. **No Phantom Writes:** If a schedule belongs to Facility B, querying with `f.slug = 'facility-a'` yields zero matching rows. PostgreSQL updates nothing, and the repository returns `ErrScheduleNotFound`.

---

## 4. Verification Results & Database Isolation

Automated test suites were executed across unit and disposable database integration suites:

```powershell
# 1. Facility Unit Tests (Input validation, boundary checks, time parsing)
cd backend; go test -v -count=1 ./internal/facility/...
# PASS: 10 unit test functions (21 subtests) in 1.39s

# 2. Facility Integration Tests (Disposable PostgreSQL databases)
cd backend; go test -v -count=1 -tags=integration ./internal/facility/...
# PASS: 13 integration tests in 6.38s
#   - Synthetic row update & read repository roundtrip: PASS
#   - Unrelated rows and parent facility preservation: PASS
#   - Mismatched slug/ID write prevention: PASS
#   - Invalid and duplicate windows leave row intact: PASS
#   - End-time 24:00:00 round-trip preservation: PASS

# 3. Development Database Isolation Probe
docker exec giki-sports-complex-db-1 psql -U giki_sports_app -d giki_sports_complex -c "SELECT count(*) FROM giki_sports.facilities; SELECT count(*) FROM giki_sports.schedules;"
# Result: 2 facilities, 5 schedules (original demo seed completely untouched; updated_at timestamps unchanged)
```

---

## 5. What the Future Protected HTTP Chunk (Step 7C) Still Requires

This step implements the **storage layer write primitive only**. It does not expose public or protected HTTP routes. When schedule mutations are exposed via HTTP in a future step, the following controls must be integrated:

1. **Authentication Session Validation:**
   - Must be protected by `RequireAuth()` middleware, extracting and validating the `giki_session` HttpOnly cookie.
2. **Explicit Role Authorization:**
   - Must be protected by `RequireAnyRole(user.RoleSportsDirector)`.
   - General students, faculty, cashiers, and unauthenticated users must be rejected with HTTP 401/403.
   - **No Super Admin Bypass:** `super_admin` must not automatically bypass facility schedule guards unless explicitly listed.
3. **Cross-Site Request Forgery (CSRF) Protection:**
   - Must enforce `RequireTrustedOrigin()`, verifying that the `Origin` header matches the trusted frontend origin (`http://127.0.0.1:5173` / `http://localhost:5173`).
4. **Administrative Audit Trail (FR-09):**
   - Administrative timetable mutations must record structured audit records (`actor_id`, `action = "schedule.update"`, `target_id = schedule_id`, `timestamp = now()`, `outcome = "success"`, `metadata = { "facility_slug": slug, "old_window": ..., "new_window": ... }`) without leaking passwords or sensitive tokens.

> [!WARNING]
> **Status Disclaimer Regarding FR-02 & FR-09:**
> This repository method updates recurring weekly schedules only. It does **not** constitute complete implementation of:
> - **FR-02:** Does not yet handle dated calendar closures, emergency blockouts, shared-space restrictions, or eligibility strategies (`EligibilityPolicy`).
> - **FR-09:** HTTP mutation handlers have not yet been wired up; storage layer atomicity is established in Step 7C below.

---

## 6. Step 7C: Transactional Schedule Update with Administrative Audit Trail

Step 7C introduces Goose migration `00004` and implements `UpdateScheduleWithAudit` on `PostgresRepository`. This couples the schedule update and administrative audit log insertion into an atomic single PostgreSQL transaction.

### 6.1 Audit Log Schema (`giki_sports.audit_logs`)

Migration `00004_create_audit_logs.sql` provisions the administrative audit trail table:

```sql
CREATE TABLE IF NOT EXISTS giki_sports.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_audit_logs_actor FOREIGN KEY (actor_id) REFERENCES giki_sports.users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_audit_logs_action_nonempty CHECK (length(trim(action)) > 0),
    CONSTRAINT chk_audit_logs_target_type_nonempty CHECK (length(trim(target_type)) > 0),
    CONSTRAINT chk_audit_logs_status_valid CHECK (status IN ('SUCCESS', 'FAILURE'))
);
```

### 6.2 Atomic Transaction Sequence

The method `UpdateScheduleWithAudit` guarantees that a schedule cannot be updated without an associated audit trail:

```mermaid
sequenceDiagram
    participant Repo as PostgresRepository
    participant PG as PostgreSQL (tx)
    
    Repo->>PG: BEGIN
    Repo->>PG: SELECT ... FROM schedules s JOIN facilities f WHERE s.id = $1 AND f.slug = $2 FOR UPDATE OF s
    PG-->>Repo: Returns old window (day, start, end, audience, facility_id)
    Repo->>PG: UPDATE schedules SET day, start, end, audience, updated_at = now() WHERE id = $1 RETURNING ...
    PG-->>Repo: Returns updated schedule
    Repo->>PG: INSERT INTO audit_logs (actor_id, action, target_type, target_id, details, ip_address, user_agent, status)
    alt Audit Insert Succeeds
        Repo->>PG: COMMIT
        PG-->>Repo: Both schedule and audit committed
    else Audit Insert Fails (e.g. Foreign Key / Check Violation)
        PG-->>Repo: ERROR (SQLSTATE 23503 / 23514)
        Repo->>PG: ROLLBACK (deferred)
        Note over PG: Schedule update undone; 0 audit rows written
    end
```

### 6.3 Atomicity & Rollback Verification

In disposable database integration testing (`TestFacilityRepository_UpdateScheduleWithAudit_RollbackOnAuditFailure`), an invalid `actor_id` was supplied to trigger a foreign key violation (`fk_audit_logs_actor`) on the audit log insert:
1. The audit insert failed with `SQLSTATE 23503`.
2. The transaction aborted and was rolled back via `defer tx.Rollback(ctx)`.
3. Direct queries on `giki_sports.schedules` verified that `day_of_week`, `start_time`, `end_time`, `audience`, and `updated_at` remained **100% untouched**.
4. Direct queries on `giki_sports.audit_logs` confirmed **0 audit rows** were written.

