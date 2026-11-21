# PostgreSQL Session Persistence and Atomic Validation Specification (Step 6E & 6E.1)

**Document Reference:** `docs/session-repository.md`  
**Milestone:** Step 6E.1 Complete (Correct Session Validation Time After Lock Waits)  
**Applicable Standards:** `requirements-baseline.md` (FR-01, QR-13), `docs/auth-data-model.md`  
**Package:** `backend/internal/session`

---

## 1. Executive Summary & Purpose

Step 6E implemented the PostgreSQL session repository backed by `pgxpool.Pool` and targeting `giki_sports.sessions`. It provides atomic session creation, concurrent validation and activity updating (`ValidateAndTouch`), and idempotent revocation (`Revoke`).

Step 6E.1 addresses a concurrency edge case in session validation:
- **Observed Issue:** In the initial Step 6E implementation, `ValidateAndTouch` called `r.clock.Now()` *before* executing the SQL query. If the query waited for a session-row lock (due to concurrent validation or revocation), the timestamp supplied to the query became stale by the time the lock was acquired and validation evaluated.
- **Corrected Architecture:** `ValidateAndTouch` now executes within a short database transaction that locks the session row via `SELECT ... FOR UPDATE OF s`, samples the injected clock `r.clock.Now()` strictly **after** the lock is granted, checks all validity predicates in application logic against the post-lock timestamp, updates activity only when valid, and commits before returning success.
- **Locking & Account-Status Semantics:** `FOR UPDATE OF s` locks *only* the session row `s`. The joined user row `u` is not locked; its status is evaluated under the transaction's snapshot. Concurrent account deactivation does not block on the session lock; once committed, subsequent validations immediately see `status = 'inactive'` and fail.
- **Revocation & In-Flight Request Semantics:** Revocation (`Revoke`) coordinates on the exact same session-row lock. Touching activity never clears or alters revocation. Explicit logout or revocation does not retroactively cancel already authenticated requests that are currently in flight.
- **Clock Injection:** Dynamic clock sampling is preserved via `TestClock`. Explicit-time helpers (`ValidateAndTouchAt`) are strictly labeled as test helpers that bypass dynamic clock sampling.

---

## 2. GIKI Wallet Codebase Inspection & Adaptation

Before implementing, token persistence and revocation patterns in GIKI Wallet were inspected:

### 2.1 Inspected Source Files & Functions
1. **`giki-wallet/backend/internal/auth/sql/queries.sql`**:
   - `CreateRefreshToken` (lines 3–5): Inserts `token_hash`, `expires_at`, `user_id`.
   - `GetRefreshTokenByHash` (lines 14–15): `SELECT * FROM giki_wallet.refresh_tokens WHERE token_hash = $1 LIMIT 1`.
   - `ReplaceRefreshToken` (lines 18–20): Sets `revoked_at = NOW()`.
   - `RevokeAllRefreshTokensForUser` (lines 23–25): Sets `revoked_at = NOW() WHERE user_id = $1 AND revoked_at IS NULL`.
2. **`giki-wallet/backend/internal/auth/service.go`**:
   - `issueTokenPair` (lines 220–233): Computes SHA-256 hash and persists refresh token.
   - `RefreshToken` (lines 318–365): Unprotected `SELECT`, followed by application-level checks, followed by separate `UPDATE`.

### 2.2 What Was Reused / Adapted
- **Token Hash Storage:** Reused the pattern of storing SHA-256 hexadecimal digests in a unique database column (`token_hash VARCHAR(64) NOT NULL UNIQUE`).
- **Explicit Revocation Timestamps:** Reused nullable `revoked_at TIMESTAMPTZ` for immediate invalidation upon logout.

### 2.3 What Changed and Why
- **Dual-Timeout Enforcement:** Wallet only implemented single fixed expirations (`expires_at`). Sports enforces dual timeouts: a rolling 30-minute idle window (`now < last_activity_at + 30m`) and a strict 8-hour absolute ceiling (`now < absolute_expires_at`).
- **Atomic Validation and Touch:** Wallet executed unprotected lookups followed by separate updates, creating race conditions. Sports executes a single atomic conditional SQL statement (`UPDATE ... FROM ... WHERE ... RETURNING ...`) that acquires a row-level lock on `sessions`, checks all validity predicates, and touches `last_activity_at` in one atomic operation.
- **Monotonic Activity Guarantee:** Uses `GREATEST(s.last_activity_at, now)` so clock jitter or concurrent request arrival never moves activity timestamps backward.
- **Idempotent Revocation:** Sports uses `SET revoked_at = COALESCE(revoked_at, now)`, preserving the timestamp of the first revocation even if called repeatedly.
- **Account Status Coordination:** Joins `giki_sports.users` directly in the validation update. Deactivating an account immediately causes subsequent validations to fail without requiring bulk session revocation.
- **Zero Raw Token Leakage:** The repository accepts only valid 64-character token hashes and never exposes them in returned models.
- **Complete Isolation:** Wallet's JWT token creation, mail dispatch, and worker queues were completely excluded. `giki-wallet` remains 100% untouched.

---

## 3. Domain Models & Public Contracts

### 3.1 Public Read Model (`Session`)
```go
type Session struct {
    ID                uuid.UUID `json:"id"`
    UserID            uuid.UUID `json:"userId"`
    CreatedAt         time.Time `json:"createdAt"`
    LastActivityAt    time.Time `json:"lastActivityAt"`
    AbsoluteExpiresAt time.Time `json:"absoluteExpiresAt"`
}
```

- **Credential Omission:** Excludes `token_hash` completely.
- **Role Decoupling:** Does not cache authorization roles; roles remain dynamically managed by the user domain.

### 3.2 Full Lifetime Record (`SessionRecord`)
Used for auditing and deterministic integration verification:
```go
type SessionRecord struct {
    ID                uuid.UUID  `json:"id"`
    UserID            uuid.UUID  `json:"userId"`
    CreatedAt         time.Time  `json:"createdAt"`
    LastActivityAt    time.Time  `json:"lastActivityAt"`
    AbsoluteExpiresAt time.Time  `json:"absoluteExpiresAt"`
    RevokedAt         *time.Time `json:"revokedAt,omitempty"`
}
```

### 3.3 Repository Interface
```go
type Repository interface {
    Create(ctx context.Context, userID uuid.UUID, tokenHash string) (*Session, error)
    CreateAt(ctx context.Context, userID uuid.UUID, tokenHash string, now time.Time) (*Session, error)
    ValidateAndTouch(ctx context.Context, tokenHash string) (*Session, error)
    ValidateAndTouchAt(ctx context.Context, tokenHash string, now time.Time) (*Session, error)
    Revoke(ctx context.Context, tokenHash string) error
    RevokeAt(ctx context.Context, tokenHash string, now time.Time) error
    GetSessionRecord(ctx context.Context, tokenHash string) (*SessionRecord, error)
}
```

---

## 4. Dual-Timeout Lifecycle & Concrete Timeline

A session is valid if and only if **all** of the following conditions hold:
1. `now < last_activity_at + 30 minutes` (Idle timeout not elapsed).
2. `now < absolute_expires_at` (Absolute 8-hour lifetime not elapsed).
3. `revoked_at IS NULL` (Session not explicitly logged out or revoked).
4. `users.status = 'active'` (User account is active).

### Concrete Timeline Example

| Time | Event / Action | `created_at` | `last_activity_at` | `absolute_expires_at` | Result | Explanation |
|---|---|:---:|:---:|:---:|:---:|---|
| **08:00** | User logs in | `08:00` | `08:00` | `16:00` | **Created** | Session created with 8h absolute ceiling. |
| **08:20** | User clicks facility | `08:00` | `08:20` | `16:00` | **Valid** | Idle deadline extended to 08:50; absolute ceiling unchanged. |
| **08:45** | User views schedule | `08:00` | `08:45` | `16:00` | **Valid** | Idle deadline extended to 09:15; absolute ceiling unchanged. |
| **09:15** | User request arrives | `08:00` | `08:45` | `16:00` | **REJECTED** | `now (09:15) >= last_activity (08:45) + 30m`. Idle timeout exceeded. |
| **---** | *(Alternative Scenario: Continuous Activity)* | | | | | |
| **15:55** | Active user request | `08:00` | `15:55` | `16:00` | **Valid** | Within idle and absolute bounds. |
| **16:00** | Active user request | `08:00` | `15:55` | `16:00` | **REJECTED** | `now (16:00) >= absolute_expires_at (16:00)`. Absolute lifetime reached. |

---

## 5. Concurrency & Locking Strategy

### 5.1 Why Separate Lookup and Touch is Unsafe
In a naive design (`SELECT` followed by application logic, followed by `UPDATE`):
1. **Time-of-Check to Time-of-Use (TOCTOU) Race:** Thread A reads session at 08:29 (idle deadline 08:30). Before Thread A updates, Thread B issues a logout request. Revocation commits. Thread A then blindly touches `last_activity_at`, reviving the logged-out session.
2. **Lost Updates:** Two concurrent requests arrive simultaneously. Both read `last_activity_at = 08:00`. Thread A updates to `08:05`. Thread B (delayed) overwrites with `08:04`, moving activity backward.

### 5.2 Short Transaction Locking and Post-Lock Clock Sampling
In Step 6E.1, `ValidateAndTouch` executes inside a short transaction that separates row locking from clock sampling:

```sql
-- Step 1: Lock the session row exclusively
SELECT 
    s.id,
    s.user_id,
    s.created_at,
    s.last_activity_at,
    s.absolute_expires_at,
    s.revoked_at,
    u.status
FROM giki_sports.sessions s
JOIN giki_sports.users u ON s.user_id = u.id
WHERE s.token_hash = $1
FOR UPDATE OF s;
```

```go
// Step 2: Sample injected clock strictly AFTER the row lock is granted
now := r.clock.Now().UTC().Truncate(time.Microsecond)

// Step 3: Check revocation, idle timeout, absolute timeout, and user account status
if revokedAt != nil || userStatus != "active" || now.Before(createdAt) ||
   !now.Before(lastActivityAt.Add(IdleTimeout)) || !now.Before(absoluteExpiresAt) {
    return nil, ErrInvalidSession // Rollback occurs via defer tx.Rollback()
}
```

```sql
-- Step 4: Update activity only when valid, preserving monotonicity and fixed absolute expiry
UPDATE giki_sports.sessions
SET last_activity_at = GREATEST(last_activity_at, $2)
WHERE id = $1
RETURNING last_activity_at;

-- Step 5: Commit transaction
COMMIT;
```

#### Why This Resolves Stale Validation Timestamps:
- In the initial Step 6E design, `r.clock.Now()` was sampled before issuing a conditional `UPDATE`. If another transaction held an exclusive lock on that session row (e.g. concurrent validation or revocation), the query blocked in PostgreSQL. By the time the lock was acquired, the pre-sampled timestamp had aged and could erroneously treat an expired session as active, or write an outdated `last_activity_at`.
- In the corrected Step 6E.1 architecture, the clock is sampled strictly **after** `SELECT ... FOR UPDATE OF s` returns to Go. Any time spent waiting in the database lock queue elapses *before* `r.clock.Now()` is evaluated.

### 5.3 Row-Level Locking and Account-Status Semantics
- **Lock Scope (`FOR UPDATE OF s`):** The lock clause explicitly locks *only* the session row `s`. The joined user row `u` is **not locked**. It is improper to claim the user row is locked merely because it appears in an `INNER JOIN`.
- **Concurrent Account Deactivation:** Because `users u` is not locked by `ValidateAndTouch`, administrative user updates (`UPDATE giki_sports.users SET status = 'inactive' WHERE id = ...`) do not block on session validation. Under PostgreSQL's Read Committed isolation level:
  - If the deactivation transaction commits before `ValidateAndTouch` executes its `SELECT`, `ValidateAndTouch` reads `u.status = 'inactive'`, immediately rolls back, and returns `ErrInvalidSession`.
  - If the deactivation commits after `ValidateAndTouch`'s `SELECT`, `ValidateAndTouch` sees `u.status = 'active'`, updates activity, and commits. The very next validation request will see `status = 'inactive'` and fail.
  - Deactivation does not retroactively cancel already authenticated requests that are currently in flight.

### 5.4 Revocation Coordination & In-Flight Request Semantics
- **Coordination via Session Row Lock:** `Revoke` executes an exclusive `UPDATE` on `giki_sports.sessions WHERE token_hash = $1`. Because `ValidateAndTouch` locks the exact same session row via `FOR UPDATE OF s`, the two operations serialize deterministically.
- **Revocation Cannot Be Cleared by Activity Touches:** Touching activity checks `revoked_at IS NULL` under the row lock. If `revoked_at` is set, validation fails immediately, the transaction rolls back, and stored activity is never modified. Touching activity does not and cannot clear or alter a revocation.
- **In-Flight Requests:** User logout or session revocation marks the session record as revoked in the database (`revoked_at = now`). Any subsequent validation attempt fails immediately. However, requests that have already been authenticated and are currently executing inside downstream business logic are not retroactively canceled by the database revocation.

---

## 6. Time Testability & Boundary Precision

- **Injectable Clock Interface:** `NewRepositoryWithClock(pool, clock)` accepts any implementation of `session.Clock`.
- **Production Post-Lock Clock Sampling:** Production validation (`ValidateAndTouch(ctx, tokenHash)`) samples `r.clock.Now()` strictly after acquiring the session row lock.
- **Controllable Fake Clock (`TestClock`):** `session.NewTestClock(initial)` provides thread-safe `.Now()`, `.Set(t)`, and `.Advance(d)` methods for deterministic timing simulation without thread sleeps.
- **Explicit-Time Test Helpers (`ValidateAndTouchAt`):** `ValidateAndTouchAt(ctx, tokenHash, explicitNow)` allows callers to specify a fixed validation timestamp, bypassing `r.clock.Now()`. It is clearly labeled as a test helper so it cannot silently bypass production timing behavior during regression and lock-wait tests.
- **Microsecond Precision:** Go's nanoseconds are truncated via `now.UTC().Truncate(time.Microsecond)` to align with PostgreSQL's 6-digit `TIMESTAMPTZ` resolution.

---

## 7. Automated Verification Results

### 7.1 Unit Tests (`backend/internal/session/model_test.go`)
- `TestSession_ConstantsAndInvariants`: Verified `IdleTimeout = 30m` and `AbsoluteLifetime = 8h`.
- `TestSession_JSONExcludesHash`: Confirmed `token_hash` is not present in serialized JSON.
- `TestSession_RealClock`: Verified non-zero UTC time generation.
- `TestSession_TestClock`: Verified thread-safe initial time, `.Set(t)`, and `.Advance(d)`.

### 7.2 Integration Tests (`backend/internal/session/repository_integration_test.go`)
Executed against disposable PostgreSQL database `giki_sports_disposable_sessrepo_*` with migration 3 applied:
- `ActiveUserCreationAndExactEightHourLifetime`: Verified creation, initial activity, and exact 8-hour expiry.
- `UnknownAndInactiveUserCreationRejection`: Verified unknown user, inactive user, and `uuid.Nil` are rejected with `ErrUserNotFoundOrInactive`.
- `SuccessfulValidationUpdatesActivityWithoutExtendingAbsoluteExpiry`: Verified activity updates while absolute ceiling remains fixed.
- `IdleExpiryBoundaries_Before_Exact_After_AndLeavesActivityUnchanged`: Verified $-1\mu\text{s}$ succeeds, exact $30\text{m}$ fails with `ErrInvalidSession`, $+1\mu\text{s}$ fails, and rejected validation leaves stored activity unchanged.
- `AbsoluteExpiryBoundaries_Before_Exact_After`: Kept session active via periodic touches, verified $-1\mu\text{s}$ succeeds, exact $8\text{h}$ fails, and $+1\mu\text{s}$ fails.
- `Revocation_RepeatedRevocation_PreservesOriginalTimestamp_AndRejectsLaterValidation`: Verified revocation, confirmed repeated revocation preserves first timestamp, and confirmed subsequent validation is rejected.
- `InactiveAccountRejectionOnValidation`: Verified active session immediately fails validation upon user deactivation.
- `ConcurrentValidationsPreserveMonotonicActivity`: 10 concurrent goroutines with barrier release verified monotonic final activity.
- `ValidationRevocationConcurrencyCannotReviveRevokedSession`: Concurrent validation and revocation verified that once revoked, session cannot be revived.
- `InvalidHashFormatAndCanceledContext`: Verified malformed hashes return `ErrInvalidTokenHash` before query execution, and canceled context returns `context.Canceled`.
- `LockWait_IdleExpiry_SamplesClockAfterLock_AndRejects`: Held session-row lock in blocker transaction; initiated validation just before idle expiry; verified validation was actively blocked in PostgreSQL via `pg_blocking_pids` without sleeps; advanced fake clock to idle expiry boundary; released lock; verified validation rejected with `ErrInvalidSession` and persisted `last_activity_at` remained at `t0`.
- `LockWait_AbsoluteExpiry_SamplesClockAfterLock_AndRejects`: Maintained active session up to 7h45m; held session-row lock; initiated validation just before 8h absolute expiry; confirmed waiting on lock in PostgreSQL; advanced fake clock to 8h boundary; released lock; verified validation rejected with `ErrInvalidSession` and activity remained unchanged.
- `LockWait_ContextCancellation_ReleasesResources`: Held session-row lock; initiated validation with cancelable context; confirmed waiting on lock; canceled context; verified validation returned `context.Canceled`; released blocker; verified connection pool and database remained healthy and unblocked.
- `DevelopmentDatabaseUntouched`: Verified development database rows remained 0 before and after tests.

### 7.3 Test Execution Command & Results
```bash
go test -v -count=1 -tags=integration ./internal/session/...
```
**Result:** All 13 integration subtests passed in **1.56s** (total package run 3.31s). Full backend test suite (`go test -v -count=1 ./...`) passed across all packages.

---

## 8. Remaining Boundaries

- **No HTTP Layer:** No cookies, headers, or Fiber middleware exist yet.
- **No Login / Logout Endpoints:** High-level authentication orchestration belongs in subsequent steps.
- **No Periodic Cleanup Worker:** Stale expired sessions remain in the database until explicitly pruned or revoked.
