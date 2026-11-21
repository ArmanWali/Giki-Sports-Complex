# Authentication HTTP Endpoints and Session Cookies (Step 6G)

## 1. Overview & Architecture

Step 6G implements the HTTP authentication layer for the GIKI Sports Complex Management System. Built upon Go Fiber v2 and the underlying `authentication.Service` (Step 6F), this layer provides production-grade HTTP handlers, centralized session cookie management, strict CSRF origin verification, and bounded abuse controls.

```
Browser Client (Vite: http://localhost:5173)
       │
       │ HTTP Request + Origin Header + Cookie
       ▼
Go Fiber HTTP Engine (:8081)
       │
       ├── CORS Middleware (Narrowly scoped to trusted origins, AllowCredentials: true)
       │
       ├── Handler Layer (backend/internal/authentication/handler.go)
       │     ├── 1. Cache-Control: no-store, Pragma: no-cache
       │     ├── 2. Exact Canonical Origin Verification (CSRF Defense) -> 403 on untrusted/missing
       │     ├── 3. Content-Type Enforcement (application/json) -> 415 on mismatch
       │     ├── 4. Bounded Body Size (<= 4096 bytes) -> 413 on oversized
       │     ├── 5. JSON Deserialization & Technical Input Bounds -> 400 on malformed
       │     ├── 6. Per-Client Rate Limiter (Fiber Limiter) -> 429 on abuse
       │     ├── 7. Concurrency Semaphore (Argon2id CPU/RAM protection) -> 503 + Retry-After: 1
       │     └── 8. Service Invocation with Bounded Request Context
       │
       ▼
Authentication Service (backend/internal/authentication/service.go)
       │
       ├── User Repository (PostgreSQL giki_sports.users & user_roles)
       └── Session Repository (PostgreSQL giki_sports.sessions under row lock)
```

---

## 2. Endpoint Contracts & Public DTOs

### 2.1 Route Table

| Method | Path | Required Headers | Request Body | Success Response | Error Responses |
|---|---|---|---|---|---|
| `POST` | `/api/auth/login` | `Content-Type: application/json`<br>`Origin: <trusted-origin>` | `{"email": "...", "password": "..."}` | `200 OK`<br>`Set-Cookie: giki_session=...`<br>`UserResponse` JSON | `400` Malformed/oversized JSON<br>`401` Invalid email or password<br>`403` Untrusted/missing Origin<br>`413` Body > 4KB<br>`415` Unsupported Media Type<br>`429` Rate limit exceeded<br>`503` Concurrency saturated |
| `GET` | `/api/auth/me` | `Cookie: giki_session=<rawToken>` | None | `200 OK`<br>`UserResponse` JSON | `401` Missing/invalid/expired cookie<br>`500` Infrastructure error |
| `POST` | `/api/auth/logout` | `Origin: <trusted-origin>`<br>`Cookie: giki_session=<rawToken>` (optional) | None | `204 No Content`<br>`Set-Cookie: giki_session=; Max-Age=-1` | `403` Untrusted/missing Origin<br>`500` Database failure |

### 2.2 Public Data Transfer Objects (DTOs)

```go
// LoginRequest defines the public JSON payload required for user login.
// Strictly restricted to email and password; no role or profile parameters accepted.
type LoginRequest struct {
    Email    string `json:"email"`
    Password string `json:"password"`
}

// UserResponse defines the safe public JSON representation of an authenticated user.
// Strictly excludes password hashes, raw session tokens, token hashes, and internal metadata.
type UserResponse struct {
    ID          string   `json:"id"`
    Email       string   `json:"email"`
    DisplayName string   `json:"displayName"`
    Roles       []string `json:"roles"`
}

// ErrorResponse defines the uniform error payload across all auth endpoints.
type ErrorResponse struct {
    Error string `json:"error"`
}
```

### 2.3 Secret Isolation & Sensitive Result Handling
- **No Token in Response JSON**: The raw session token is returned by `service.Login` strictly for cookie issuance and is never included in the JSON response payload.
- **No LocalStorage**: Tokens are never exposed to browser client-side scripts, preventing XSS-based session hijacking.
- **Masked Formatting**: `LoginResult.RawToken` is marked `json:"-"` and masked as `[REDACTED]` in `fmt.Stringer` and `fmt.GoStringer`.
- **Diagnostics**: Log messages redact passwords, tokens, and hashes, recording only normalized email addresses and sanitized error classifications.

---

## 3. Centralized Session Cookie Configuration

Session cookies are issued and cleared exclusively through `CookieManager` (`backend/internal/authentication/cookie.go`).

| Cookie Attribute | Configuration | Security Purpose & Behavior |
|---|---|---|
| **Name** | `giki_session` (configurable via `AUTH_COOKIE_NAME`) | Dedicated cookie identifier for the sports complex management system. |
| **HttpOnly** | `true` | Prevents client-side scripts (JavaScript) from accessing `document.cookie`, mitigating XSS exfiltration. |
| **SameSite** | `Lax` (configurable via `AUTH_COOKIE_SAMESITE`) | Instructs browser to withhold cookie on cross-site subrequests (such as `<img>`, `<iframe>`, or cross-site AJAX mutations), while allowing it on safe top-level navigations. |
| **Path** | `/api` (configurable via `AUTH_COOKIE_PATH`) | Scopes cookie delivery strictly to API endpoints. Subpaths under `/` (such as static assets) do not receive the cookie. |
| **Domain** | `""` (Empty string) | Omits the `Domain` attribute. Under RFC 6265, an omitted `Domain` attribute restricts the cookie strictly to the host that issued it, preventing broad sharing across subdomains. |
| **Secure** | `false` in local HTTP dev<br>`true` in HTTPS production | In production (`AUTH_COOKIE_SECURE=true`), cookie is transmitted solely over TLS/HTTPS connections. In local development without TLS, `AUTH_COOKIE_SECURE=false` permits local development over plain HTTP. |
| **MaxAge** | `28800` (8 hours) | Set to match `session.AbsoluteLifetime` (8 hours). Browser cookie expiry establishes a client-side retention ceiling; it does not enforce the server-side 30-minute idle timeout. |
| **Deletion** | `MaxAge: -1`<br>`Expires: 1970-01-01` | Cookie clearing uses identical Name, Path, Domain, Secure, and SameSite attributes to ensure the browser drops the cookie. |

---

## 4. Cross-Site Protection: Authentication vs. CSRF vs. CORS

### 4.1 Concept Separation
- **Authentication**: Verifies user identity (e.g. matching credentials against stored Argon2id hashes, or validating a session token).
- **CSRF Protection**: Prevents unauthorized browser-driven mutations from forged third-party contexts where ambient credentials (such as cookies) would automatically be attached by the browser.
- **CORS (Cross-Origin Resource Sharing)**: A browser security mechanism that selectively loosens the Same-Origin Policy for cross-origin AJAX/Fetch requests. **CORS is NOT CSRF protection.** Enabling CORS without strict origin verification allows attackers to trigger state-changing mutations if cookies are accepted.

### 4.2 Exact Canonical Origin Verification
Browser-initiated mutation endpoints (`POST /api/auth/login` and `POST /api/auth/logout`) enforce exact canonical `Origin` header verification:
1. Rejects missing, empty, `"null"`, or malformed `Origin` headers with `403 Forbidden`.
2. Parses the `Origin` URL to ensure valid `http` or `https` scheme, non-empty host, and no path, query, or fragment.
3. Performs exact string comparison against configured trusted origins (`AUTH_TRUSTED_ORIGINS`).
4. **Never uses substring matching** to prevent bypasses like `http://localhost:5173.attacker.com`.

### 4.3 Testing and API Client Usage
Non-browser test runners and API tools (such as curl, Postman, or integration tests) must supply a trusted `Origin` header when calling login or logout:
```bash
curl -X POST http://localhost:8081/api/auth/login \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{"email":"athlete@giki.edu.pk","password":"MyPassword"}'
```

### 4.4 CORS Configuration
Fiber's CORS middleware is configured with:
```go
corsOrigins := strings.Join(cfg.Auth.TrustedOrigins, ", ")
app.Use(cors.New(cors.Config{
    AllowOrigins:     corsOrigins,
    AllowCredentials: true,
    AllowHeaders:     "Origin, Content-Type, Accept, Authorization, X-Director-Key",
    AllowMethods:     "GET, POST, PUT, DELETE, OPTIONS",
}))
```
- Wildcard `AllowOrigins: "*"` is disallowed when `AllowCredentials` is `true`.
- Credentials are permitted only for explicitly declared trusted origins.

---

## 5. Bounded Abuse Controls & Resource Protection

Argon2id password verification requires substantial computational resources (production parameters consume 64MB RAM and 3 passes per verification). Unbounded concurrent login requests could easily exhaust memory or peg CPU cores, resulting in Denial of Service (DoS).

### 5.1 Per-Client Attempt Rate Limiting
- Managed by Fiber's `limiter` middleware.
- Default limit: 10 attempts per minute per remote client IP (`AUTH_LOGIN_RATE_LIMIT=10`, `AUTH_LOGIN_RATE_WINDOW=1m`).
- Returns `HTTP 429 Too Many Requests` with `{"error": "too many login attempts; please try again later"}`.
- Relies on direct TCP connection IP (`c.IP()`), refusing to trust spoofed `X-Forwarded-For` headers unless trusted proxies are explicitly configured.
- Memory storage is automatically bounded via Fiber's periodic TTL eviction.

### 5.2 Concurrency Semaphore for Password Verification
- Implemented as a buffered channel semaphore (`concurrencySem chan struct{}`) inside `Handler`.
- Configurable capacity (`AUTH_LOGIN_MAX_CONCURRENT=4`, default 4 concurrent operations).
- Evaluated **after** syntactic, origin, and payload size validation passes, ensuring invalid requests do not consume concurrency slots.
- When saturated, immediately returns `HTTP 503 Service Unavailable` with `Retry-After: 1` header, preventing CPU/RAM exhaustion.

### 5.3 Technical Input Bounds
- Maximum request body size: 4096 bytes (4KB). Exceeding payloads receive `HTTP 413 Request Entity Too Large`.
- Maximum email length: 255 characters.
- Maximum password length: 4096 characters.
- Password bytes are preserved exactly; passwords are never trimmed.

---

## 6. GIKI Wallet Inspection & Adaptations

| Component | GIKI Wallet Implementation | GIKI Sports Complex Adaptation |
|---|---|---|
| **Inspected Functions** | `auth/handler.go`:<br>• `NewHandler`<br>• `setRefreshTokenCookie`<br>• `clearRefreshTokenCookie`<br>• `Login`<br>• `Logout`<br>• `Me` | Adapted into `backend/internal/authentication`:<br>• `NewHandler`<br>• `CookieManager.SetSessionCookie`<br>• `CookieManager.ClearSessionCookie`<br>• `Handler.Login`<br>• `Handler.Logout`<br>• `Handler.Me` |
| **Framework** | Standard `net/http` (`http.ResponseWriter`, `*http.Request`) | Go Fiber v2 (`*fiber.Ctx`, `c.Cookie()`, `c.JSON()`). |
| **Session Model** | Stateless JWT access tokens + 60-day refresh tokens. | Stateful server-side PostgreSQL sessions (`giki_session`, 8h ceiling, 30m idle timeout). |
| **Cookie Scope** | Hardcoded `Path: "/api/auth/refresh"` with `SameSite: Lax`. | Centralized `CookieManager` with `Path: "/api"`, `SameSite: Lax`, `HttpOnly: true`, and configurable `Secure`. |
| **Response Payload** | Returned tokens and user info in JSON body. | Strictly returns public user DTO (`id`, `email`, `displayName`, `roles`); raw tokens delivered solely via `Set-Cookie`. |
| **CSRF Defense** | No origin validation on login/logout. | Exact canonical `Origin` header validation against trusted origins on all mutations. |
| **Abuse Protection** | No concurrency bounds or request limits. | Per-client IP rate limiter (429) + concurrency semaphore on Argon2id hashing (503). |
| **External Deps** | JWT, mailer, audit loggers, worker queues. | Zero external dependencies; depends only on consumer-owned `Authenticator` interface. |
| **Wallet Status** | Left 100% unchanged. | No modifications to `giki-wallet/`. |

---

## 7. Verification Results

All tests executed with caching disabled (`-count=1`):

| Test Suite | Package | Scope / Tests | Result | Duration |
|---|---|---|:---:|:---:|
| `go build ./...` | `backend/` | Compilation across all backend packages | **Passed** | 0.8s |
| `go vet ./...` | `backend/` | Static analysis across all backend packages | **Passed** | 0.5s |
| `handler_test.go` | `internal/authentication` | Unit tests: login success, whitespace preservation, origin rejection (6 cases), body/content limits (3 cases), 401 on bad credentials, error redaction, concurrency saturation, rate limiting, me validation (3 cases), logout clearing (3 cases) | **Passed (23 subtests)** | 0.05s |
| Complete Unit Suite | `backend/` | All 6 packages (`auth`, `authentication`, `config`, `facility`, `session`, `user`) | **Passed** | 2.7s |
| `http_integration_test.go` | `internal/authentication` | Disposable PostgreSQL DB (`giki_sports_disposable_authsvc_*`): migration, synthetic user, login with wrong password (401), login with valid password (200 + cookie), verify DB has SHA-256 hash not token, me (200), logout (204 + clear cookie), me post-logout (401), dev DB verified untouched | **Passed** | 1.58s |
| `service_integration_test.go` | `internal/authentication` | Disposable PostgreSQL DB: core service integration tests | **Passed** | 1.21s |
| `repository_integration_test.go` | `internal/session` | Disposable PostgreSQL DB: session repository locking & timeout integration tests | **Passed (13 subtests)** | 1.79s |

---

## 8. Remaining Limitations & Prototype Scope

1. **Legacy Mutation Routes Unprotected**: Legacy endpoints (`POST /api/bookings`, `POST /api/announcements`, `POST /api/memberships`, etc.) remain in-memory prototype routes without authentication or role guards. They will be protected by `RequireAuth` and `RequireRole` middleware in future steps.
2. **In-Process Limiter State**: The rate limiter and concurrency semaphore are stored in memory per backend instance. Multi-instance production deployments require a shared store (e.g. Redis) or an API gateway.
3. **No Development Accounts**: Development user and session tables in PostgreSQL remain completely empty (0 rows). Test accounts are provisioned exclusively inside disposable databases during automated integration test execution.
