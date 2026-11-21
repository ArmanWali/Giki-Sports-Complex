# Read-Only User and Role PostgreSQL Repository Specification (Step 6D)

**Document Reference:** `docs/user-repository.md`  
**Milestone:** Step 6D (Read-Only User and Role PostgreSQL Repository)  
**Applicable Standards:** `requirements-baseline.md` (FR-01, QR-13), `docs/auth-data-model.md`  
**Package:** `backend/internal/user`

---

## 1. Executive Summary & Purpose

Step 6D implements the read-only PostgreSQL repository for user identities, account statuses, and role assignments in Go, backed by `pgxpool.Pool` and targeting schema tables `giki_sports.users` and `giki_sports.user_roles` established in migration 3.

In this chunk:
- Domain read models strictly decouple standard user identity and roles from sensitive credentials.
- Ordinary user queries (`GetByEmail`, `GetByID`) never query or load `password_hash` from PostgreSQL.
- Credential access is isolated behind a narrowly named method (`GetCredentialsByEmail`) strictly for the future authentication service.
- Lookups normalize emails according to the functional unique index `LOWER(TRIM(email))`.
- Single-query `LEFT JOIN` execution provides atomic statement-level snapshot consistency between user profiles and multi-role assignments without N+1 query overhead.
- Scope is strictly bounded to read queries: no account creation, session persistence, login endpoints, middleware, or frontend code are introduced.

---

## 2. GIKI Wallet Codebase Inspection & Adaptation

Before implementation, user query and auth model patterns in the GIKI Wallet codebase were inspected:

### 2.1 Inspected Source Files & Functions
1. **`giki-wallet/backend/internal/user/user_db/queries.sql.go`**:
   - `GetUserByEmail(ctx context.Context, email string) (GetUserByEmailRow, error)` (lines 242–260): Omits `password_hash` from the `SELECT` column list.
   - `GetUserByID(ctx context.Context, id uuid.UUID) (GetUserByIDRow, error)` (lines 283–301): Omits `password_hash` from the `SELECT` column list.
   - `GetUserAuthByEmail(ctx context.Context, email string) (GikiWalletUser, error)` (lines 171–191): Explicitly selects `password_hash` alongside identity fields for credential evaluation.
   - `GetUserAuthByID(ctx context.Context, id uuid.UUID) (GikiWalletUser, error)` (lines 199–218): Selects credentials by UUID.
2. **`giki-wallet/backend/internal/user/user_db/querier.go`**: Querier interface definitions.
3. **`giki-wallet/backend/internal/user/model.go`**: Model mapping functions.

### 2.2 What Was Reused / Adapted
- **Credential Separation Pattern:** Reused Wallet's foundational architectural distinction between ordinary user lookups (`GetUserByEmail`, `GetUserByID`) and authentication credential lookups (`GetUserAuthByEmail`).
- **Parameterized SQL:** Reused parameterized `$1` positional arguments via `pgx`.
- **Clean Sentinel Error Handling:** Reused standard library error wrapping and sentinel matching (`errors.Is`).

### 2.3 What Changed and Why
- **Multi-Role Relational Modeling:** In Wallet, user roles were limited to a single string column (`user_type`). In Sports Complex, users can have multiple roles in `giki_sports.user_roles` (e.g. `faculty` and `sports_director`).
- **Single-Query Snapshot Consistency:** Instead of executing separate queries for users and roles, Sports executes a single parameterized `LEFT JOIN` query ordered by `r.role ASC`. This guarantees atomic statement-level snapshot consistency and eliminates N+1 database round-trips.
- **Strict Email Normalization:** Normalization in Go (`NormalizeEmail`) exactly matches the PostgreSQL index expression `LOWER(TRIM(email))`.
- **Credential Hardening:** In Wallet, the full database row model was sometimes logged or serialized. In Sports, `UserCredentials` tags `PasswordHash` with `json:"-"` and overrides `String()` and `GoString()` to output `[REDACTED]`, completely preventing accidental credential leakage.
- **Complete Isolation:** Wallet's JWT token creation, mail dispatch, worker queues, and payment dependencies were completely excluded. The `giki-wallet/` directory was left 100% untouched.

---

## 3. Domain Models & Credential Separation

### 3.1 Standard User Read Model (`User`)
The standard domain read model represents an account's public profile, status, and assigned roles:

```go
type User struct {
    ID          uuid.UUID     `json:"id"`
    Email       string        `json:"email"`
    DisplayName string        `json:"displayName"`
    Status      AccountStatus `json:"status"`
    Roles       []Role        `json:"roles"`
    CreatedAt   time.Time     `json:"createdAt"`
    UpdatedAt   time.Time     `json:"updatedAt"`
}
```

- **Absence of Credentials:** `User` has no `PasswordHash` field. Ordinary profile queries cannot leak credentials because the field does not exist in the struct and is never selected in SQL.
- **Empty Roles Guarantee:** When a user has no roles in the database, `Roles` is guaranteed to be an empty, non-nil slice (`[]Role{}`).

### 3.2 Credential-Bearing Model (`UserCredentials`)
The internal credential model is scoped exclusively for the login verification workflow:

```go
type UserCredentials struct {
    User         User
    PasswordHash string `json:"-"`
}
```

- **JSON Omission:** `json:"-"` guarantees `PasswordHash` is never serialized if the struct is marshaled.
- **Formatting Mask:** Implements `fmt.Stringer` and `fmt.GoStringer` returning `[REDACTED]`, preventing leaks in debug logs or stack traces.

---

## 4. Repository Method Contracts & Query Behavior

### 4.1 Interface Definition
```go
type Repository interface {
    GetByEmail(ctx context.Context, email string) (*User, error)
    GetByID(ctx context.Context, id uuid.UUID) (*User, error)
    GetCredentialsByEmail(ctx context.Context, email string) (*UserCredentials, error)
}
```

### 4.2 Query Implementation & Read Consistency
All three queries execute against schema `giki_sports`:

```sql
SELECT 
    u.id, 
    u.email, 
    u.display_name, 
    u.status, 
    u.created_at, 
    u.updated_at, 
    r.role
FROM giki_sports.users u
LEFT JOIN giki_sports.user_roles r ON u.id = r.user_id
WHERE LOWER(TRIM(u.email)) = $1
ORDER BY r.role ASC;
```

- **Statement-Level Snapshot Consistency:** Executing a single parameterized query with `LEFT JOIN` ensures that the user row and role rows are read from the exact same PostgreSQL transaction snapshot. There is zero snapshot drift or race condition between reading the user and reading their roles.
- **Deterministic Role Order:** `ORDER BY r.role ASC` returns roles in deterministic alphabetical order across all queries (`faculty` < `sports_director` < `student` < `super_admin`).
- **No Duplicate Records:** When a user possesses multiple roles, row iteration aggregates the distinct `r.role` values into the single `User.Roles` slice. Exactly one `*User` is returned.
- **Email Normalization:** `NormalizeEmail(email)` trims whitespace and lowercases input before executing the query. If the normalized input is empty, `ErrNotFound` is returned immediately without a database round-trip.
- **No Domain Restrictions:** Repository lookups accept any valid email string without imposing unapproved university domain filters.
- **Inactive Accounts:** Inactive users remain readable; `u.Status` reflects `StatusInactive`. Rejection of inactive accounts is deferred to the authentication service.
- **SQL Injection Defense:** All queries utilize positional bind parameters (`$1`). SQL-like inputs (e.g. `' OR '1'='1`) are treated strictly as literal data.
- **Context Propagation:** Context cancellation is propagated directly to `r.pool.Query(ctx, ...)`.

---

## 5. Automated Verification Results

### 5.1 Unit Tests (`backend/internal/user/model_test.go`)
- `TestUser_NormalizeEmail`: Verified 7 test cases (lowercase conversion, whitespace trimming, tabs, external domains, empty strings).
- `TestUser_CredentialRedactionAndJSONOmission`: Verified `fmt.Sprintf` (`%s`, `%v`, `%+v`, `%#v`) masks password hashes with `[REDACTED]`, and `json.Marshal` excludes `PasswordHash`.
- `TestUser_NotFoundError`: Verified sentinel error matching via `errors.Is`.

### 5.2 Integration Tests (`backend/internal/user/repository_integration_test.go`)
Executed against disposable PostgreSQL database `giki_sports_disposable_userrepo_*` with real migrations applied:
- `ExistingLookupByIDAndEmail`: Verified active user lookup with matching fields.
- `CaseAndWhitespaceEmailNormalization`: Verified lookup matches unnormalized input (`"  \tFaculty.Director@GIKI.EDU.PK \n "`).
- `UnknownUserBehavior`: Verified unknown email, unknown UUID, `uuid.Nil`, and empty email return `ErrNotFound`.
- `MultipleRolesAndDeterministicOrdering`: Verified user with 2 roles (`sports_director`, `faculty`) returns both in deterministic order `[faculty, sports_director]`.
- `UserWithNoRolesReturnsEmptyNonNilSlice`: Verified user with 0 roles returns `Roles = []Role{}`.
- `InactiveAccountStatusRemainsVisible`: Verified inactive user is returned with `StatusInactive`.
- `CredentialLookupReturnsSyntheticHashInternallyWhileOrdinaryReadsExcludeIt`: Verified ordinary reads omit `PasswordHash`, while `GetCredentialsByEmail` returns the synthetic hash.
- `SQLInjectionEmailTreatedAsLiteralData`: Verified 4 SQL injection attack strings safely return `ErrNotFound`.
- `CanceledContextReturnsError`: Verified canceled context returns `context.Canceled`.
- `DevelopmentDatabaseUntouched`: Verified row count in development database remained exactly 0 before and after tests.

### 5.3 Test Suite Execution Summary
- `go build ./...`: **Passed (Exit 0)**
- `go vet ./...`: **Passed (Exit 0)**
- `go test -v -count=1 ./...`: **Passed (Exit 0)** across `config`, `facility`, `auth`, and `user`.
- `go test -v -count=1 -tags=integration ./internal/user/...`: **Passed (Exit 0)** in 5.27s.

---

## 6. Remaining Boundaries

- **No User Creation or Mutation:** Step 6D implements read queries only; registration and account writes remain deferred.
- **No Session Persistence:** Server-side session repository and token storage in `giki_sports.sessions` belong in Step 6E.
- **No Login / Logout HTTP Endpoints:** Authentication HTTP handlers, cookie management, and Fiber routes will be added in subsequent milestones.
