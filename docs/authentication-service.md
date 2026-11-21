# Authentication Service Orchestration Specification (Step 6F)

**Document Reference:** `docs/authentication-service.md`  
**Milestone:** Step 6F Complete (Authentication Service Orchestration)  
**Applicable Standards:** `requirements-baseline.md` (FR-01, QR-09, QR-13), `docs/auth-data-model.md`, `docs/session-tokens.md`  
**Package:** `backend/internal/authentication`

---

## 1. Executive Summary & Purpose

Step 6F implements the core application authentication service (`authentication.Service`) orchestrating user credential verification, session creation, session validation, and session revocation.

This service acts as the orchestration layer between the credential/user domain (`user.Repository`), cryptographic hashing utilities (`auth`), and session lifecycle persistence (`session.Repository`).

Key architectural invariants established in this step:
- **Credential & Token Isolation:** Passwords and raw session tokens are strictly isolated. Raw session tokens are returned only in a dedicated `LoginResult.RawToken` field with `json:"-"` and masked `String()` formatting for future HTTP cookie delivery.
- **Account Enumeration Defense:** Unknown email addresses, wrong passwords, and inactive user accounts are rejected with the identical sentinel error `ErrInvalidCredentials`. For unknown and inactive users, a precomputed dummy Argon2id verification is executed to mitigate fast-path timing leaks.
- **Consumer-Owned Interfaces:** The service defines small, dedicated repository interfaces (`UserCredentialRepository`, `SessionStore`), completely decoupling orchestration logic from concrete database implementations and preventing circular package dependencies.
- **True Server-Side Revocation:** Logout explicitly revokes the session row in PostgreSQL via `sessionRepo.Revoke`, rather than relying solely on client-side cookie deletion.
- **Strict Scope Boundaries:** No HTTP routes, cookies, middleware, frontend integration, or seed accounts are introduced in this milestone.

---

## 2. GIKI Wallet Codebase Inspection & Adaptation

### 2.1 Inspected Source Files & Functions
1. **`giki-wallet/backend/internal/auth/service.go`**:
   - `Login` (lines 48–70): Transactional orchestration of login request.
   - `authenticateAndIssueTokens` (lines 144–187): Orchestrates user verification, active/verified status checks, and token generation.
   - `checkUserAndPassword` (lines 243–300): Looks up user by email and compares password hash.
   - `issueTokenPair` (lines 189–241): Issues JWT access token and persists SHA-256 refresh token hash.
   - `RefreshToken` (lines 314–372): Validates incoming refresh token, checks revocation, and replaces token.
2. **`giki-wallet/backend/internal/auth/handler.go`**:
   - `Login` (lines 110–172): HTTP handler for login, issuing cookies and responses.
   - `Logout` (lines 174–193): Clears refresh token cookie client-side.

### 2.2 What Was Reused & Adapted
- **Token Hashing Architecture:** Reused the pattern of treating raw client tokens as opaque secrets and persisting strictly their SHA-256 hex digests in the database.
- **Credential Lookup Separation:** Reused the pattern of separating user profile retrieval from sensitive password verification.

### 2.3 What Changed and Why
- **Server-Side Sessions over JWTs:** Wallet issued stateless JWT access tokens and stateful refresh tokens. Sports Complex employs stateful server-side sessions (`giki_sports.sessions`) according to QR-13 and `auth-data-model.md`, allowing immediate session validation and revocation without distributed token lists.
- **Uniform Error Returns:** Wallet returned `ErrUserNotFound` for missing emails and `ErrInvalidPassword` for wrong passwords, creating an observable account enumeration vector. Sports Complex returns a single uniform `ErrInvalidCredentials` error.
- **Dummy Verification Timing Mitigation:** Wallet immediately failed fast when an email did not exist, creating a stark timing difference between non-existent accounts (<1ms) and valid accounts (~50ms Argon2id compute). Sports Complex precomputes a dummy Argon2id hash once at service startup and verifies against it whenever an email is not found or inactive.
- **Server-Side Revocation on Logout:** Wallet's `Logout` handler only cleared the client cookie (`clearRefreshTokenCookie`) without revoking the token in the database. Sports Complex computes the token hash and calls `sessionRepo.Revoke` to ensure true database-level session invalidation.
- **Decoupled Architecture:** Wallet was coupled to background workers (`worker.JobWorker`), mail sending, payment domains, and transport logic. Sports Complex completely omits these dependencies. `giki-wallet` remains 100% untouched.

---

## 3. Architecture & Dependency Direction

To avoid circular imports between `session`, `auth`, and `user`:
- `session` already imports `auth` for token hash validation.
- `authentication` imports `auth` (utilities), `session` (models & errors), and `user` (models & errors).
- Neither `auth`, `session`, nor `user` imports `authentication`.
- `authentication.Service` depends strictly on consumer-owned interfaces:

```
[ authentication.Service ]
       │              │
       ▼              ▼
[ UserCredentialRepository ]  [ SessionStore ]
       ▲                      ▲
       │                      │
[ user.Repository ]    [ session.Repository ]
```

### 3.1 Consumer-Owned Interfaces
```go
type UserCredentialRepository interface {
    GetCredentialsByEmail(ctx context.Context, email string) (*user.UserCredentials, error)
    GetByID(ctx context.Context, id uuid.UUID) (*user.User, error)
}

type SessionStore interface {
    Create(ctx context.Context, userID uuid.UUID, tokenHash string) (*session.Session, error)
    ValidateAndTouch(ctx context.Context, tokenHash string) (*session.Session, error)
    Revoke(ctx context.Context, tokenHash string) error
}
```

---

## 4. Public Models & Sentinel Errors

### 4.1 Sentinel Errors
```go
var (
    ErrInvalidCredentials = errors.New("authentication: invalid email or password")
    ErrInvalidSession     = errors.New("authentication: invalid, expired, or revoked session")
    ErrInternal           = errors.New("authentication: internal error")
)
```

### 4.2 Return Models
```go
// LoginResult is the sensitive result of a successful Login call.
// Excluded from JSON and masked in fmt formatting to prevent credential exposure.
type LoginResult struct {
    RawToken string           `json:"-"`
    User     *user.User       `json:"user"`
    Session  *session.Session `json:"session"`
}

// AuthenticatedPrincipal represents a validated active user session.
// Strictly excludes credentials, password hashes, and session tokens.
type AuthenticatedPrincipal struct {
    User    *user.User       `json:"user"`
    Session *session.Session `json:"session"`
}
```

---

## 5. End-to-End Orchestration Workflows

### 5.1 Login Workflow (`Login(ctx, email, password)`)
1. **Input Normalization**: Trims and lowercases email via `user.NormalizeEmail`. If email or password is empty, executes dummy verification and returns `ErrInvalidCredentials`.
2. **Credential Lookup**: Queries `userRepo.GetCredentialsByEmail(ctx, normalizedEmail)`.
   - If `errors.Is(err, user.ErrNotFound)`: executes dummy password verification and returns `ErrInvalidCredentials`.
   - If database error: wraps and returns genuine failure.
3. **Status Check**: If `creds.User.Status != user.StatusActive`: executes dummy verification and returns `ErrInvalidCredentials`.
4. **Password Verification**: Calls `auth.Verify(password, creds.PasswordHash)`.
   - If hash is malformed: returns internal data integrity error wrapping `ErrInternal`.
   - If password does not match: returns `ErrInvalidCredentials`.
5. **Token Generation**: Generates 32 bytes of cryptographic randomness (43-character URL-safe Base64 token) and 64-character lowercase hexadecimal SHA-256 hash via `auth.GenerateSessionToken()`.
6. **Session Persistence**: Inserts session row via `sessionRepo.Create(ctx, creds.User.ID, tokenHash)`.
   - If account became inactive concurrently: returns `ErrInvalidCredentials`.
   - If database fails: returns wrapped error. No session token is ever returned to caller.
7. **Result Delivery**: Returns `LoginResult` containing `RawToken`, safe public `User` model, and `Session` metadata.

### 5.2 Session Validation Workflow (`ValidateSession(ctx, rawToken)`)
1. **Token Syntax Check**: Verifies raw token structure via `auth.ValidateSessionToken(rawToken)`. Rejects empty, unpadded, or non-canonical strings fast without querying the database.
2. **Hash Derivation**: Computes lowercase hexadecimal SHA-256 digest via `auth.HashSessionToken(rawToken)`.
3. **Atomic Verification & Touch**: Calls `sessionRepo.ValidateAndTouch(ctx, tokenHash)`.
   - Employs the Step 6E.1 short transaction with row lock (`FOR UPDATE OF s`) and post-lock clock sampling.
   - Enforces idle timeout (30 minutes), absolute lifetime (8 hours), revocation (`revoked_at IS NULL`), and user status (`u.status = 'active'`).
   - If invalid: returns `ErrInvalidSession`.
4. **Current Profile & Role Loading**: Queries `userRepo.GetByID(ctx, sess.UserID)` to load up-to-date user roles (`roles`).
   - If user is missing or inactive: returns `ErrInvalidSession`.
5. **Principal Return**: Returns `AuthenticatedPrincipal` with current user profile, roles, and session metadata.

### 5.3 Logout Workflow (`Logout(ctx, rawToken)`)
1. **Token Validation**: Checks format with `auth.ValidateSessionToken(rawToken)`. If malformed, returns `nil` (harmless idempotent logout).
2. **Hash Derivation**: Computes `auth.HashSessionToken(rawToken)`.
3. **Server-Side Revocation**: Calls `sessionRepo.Revoke(ctx, tokenHash)`.
   - Sets `revoked_at = COALESCE(revoked_at, now)`.
   - If session was already revoked, expired, or non-existent (`session.ErrInvalidSession`), returns `nil` (idempotent repeated logout).
   - If genuine database or context error occurs, propagates error.
   - Does NOT touch activity before revocation; expired sessions remain revocable.

---

## 6. Sensitive Data Handling & Enumeration Defense

### 6.1 Dummy Verification & Its Practical Limits
- **Mechanism:** During service initialization (`NewService`), a realistic Argon2id hash is computed once using production parameters (`auth.DefaultParams`). Whenever an email lookup fails or targets an inactive account, `auth.Verify(password, dummyHash)` is executed.
- **Mitigation Scope:** Eliminates obvious fast-path account enumeration where non-existent accounts respond in $<1\text{ms}$ while real accounts require $\sim 50\text{ms}$ of Argon2id computation.
- **Practical Limits:** Dummy verification **does not** guarantee perfectly constant response times. Database query latencies, network packet variance, OS thread scheduling, and CPU frequency scaling introduce variable jitter. Furthermore, dummy verification does not replace HTTP-layer IP rate-limiting, CAPTCHA, or account lockout mechanisms.

### 6.2 Token Security
- Raw session tokens are generated with 256 bits of entropy (`crypto/rand`).
- The database persists strictly the SHA-256 digest (`token_hash`). If the database is compromised read-only, stored hashes cannot be reversed to authenticate sessions.
- In memory, `LoginResult.RawToken` is protected with `json:"-"` and masked in `fmt` formatters (`[REDACTED]`).

---

## 7. Automated Verification Results

### 7.1 Unit Tests (`backend/internal/authentication/service_test.go`)
Executed using lightweight mock implementations and custom test parameters:
- `TestService_Login_Success`: Verified credential lookup, Argon2id verification, token generation, session creation, and safe result fields.
- `TestService_Login_Rejections_And_DummyVerification`: Verified unknown user, inactive account, wrong password, empty email, and empty password; confirmed dummy verification was executed for non-existent and inactive accounts; confirmed token generation was never invoked for rejected attempts.
- `TestService_Login_Failures_And_MalformedHash`: Verified entropy failure returns no token; verified persistence failure returns no token; verified concurrent account deactivation maps to `ErrInvalidCredentials`; verified malformed stored hash returns `ErrInternal` instead of generic credential rejection.
- `TestService_ValidateSession`: Verified successful validation loads current roles; verified invalid token formats fail fast without querying repository; verified expired/revoked sessions return `ErrInvalidSession`; verified inactive user after session validation is rejected.
- `TestService_Logout`: Verified idempotent revocation for valid tokens, already revoked tokens, and malformed tokens; verified infrastructure errors are propagated.
- `TestLoginResult_RedactionAndJSONOmission`: Verified JSON marshaling excludes raw tokens; verified `String()` and `GoString()` formatters mask raw tokens with `[REDACTED]`.

### 7.2 Integration Tests (`backend/internal/authentication/service_integration_test.go`)
Executed against disposable PostgreSQL database `giki_sports_disposable_authsvc_*` with migrations applied:
- `LoginWithValidCredentials_Succeeds_AndStoresHashNotToken`: Verified real login against active synthetic user; verified database table `giki_sports.sessions` stored `sha256(rawToken)`, not the raw token.
- `ValidateSession_ReturnsPrincipalWithCurrentRoles`: Verified real session validation loads profile with `faculty` and `sports_director` roles.
- `LoginRejections_WrongPassword_And_UnknownUser`: Verified real Argon2id password verification and rejection on invalid credentials.
- `IdleExpiryViaInjectedClockRejectsValidation`: Verified session idle timeout rejection using injected fake clock without thread sleeps.
- `Logout_RevokesSession_AndRejectsSubsequentValidation`: Verified real logout sets `revoked_at` in PostgreSQL; verified subsequent validation fails; verified repeated logout is idempotent.
- `DevelopmentDatabaseUntouched`: Verified 0 user and session records in development database before and after test execution.

### 7.3 Test Execution Command & Results
```bash
go test -v -count=1 -tags=integration ./internal/authentication/...
```
**Result:** All 5 integration subtests and all unit tests passed in **4.20s** against disposable database. Complete backend unit test suite (`go test -v -count=1 ./...`) passed across all 6 packages.

---

## 8. Remaining Boundaries

- **No HTTP Layer:** No HTTP handlers, routing, cookies (`Set-Cookie`), or header parsing exist in this milestone.
- **No Middleware:** Authentication middleware (`RequireAuth`, role checking) belongs in Step 6G.
- **No Rate Limiting:** Brute-force and credential-stuffing protections belong in the HTTP middleware layer.
- **No Password Reset / Registration:** Self-service registration and password reset workflows belong in subsequent epics.
