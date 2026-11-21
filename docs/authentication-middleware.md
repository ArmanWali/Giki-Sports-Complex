# Reusable Authentication and Role Middleware (Step 6H)

## 1. Overview & Architecture

Step 6H implements the reusable authentication and role authorization middleware layer for the GIKI Sports Complex Management System. Built upon Go Fiber v2 and the underlying PostgreSQL session repository, this middleware provides route-level authentication (`RequireAuth`), role-based access control (`RequireAnyRole`), exact CSRF origin verification (`RequireTrustedOrigin`), and safe context propagation without credential leakage.

```
Incoming HTTP Request (:8081)
       │
       ├── Middleware Pipeline
       │     ├── 1. RequireTrustedOrigin() [On mutation routes]
       │     │      └── Exact canonical Origin comparison against trusted whitelist -> 403 Forbidden
       │     │
       │     ├── 2. RequireAuth()
       │     │      ├── Extracts 'giki_session' cookie (401 if missing)
       │     │      ├── Validates session via service.ValidateSession under PostgreSQL row lock
       │     │      ├── Checks dual timeouts (30m idle, 8h absolute ceiling) and active account status
       │     │      ├── Touches activity timestamp in DB
       │     │      ├── Bounded context deadline (503 on timeout, 500 on unexpected DB error)
       │     │      ├── Sets Cache-Control: no-store, Pragma: no-cache
       │     │      └── Stores *AuthenticatedPrincipal in Fiber locals using private key
       │     │
       │     ├── 3. RequireAnyRole(roles ...user.Role)
       │     │      ├── Retrieves principal from locals via GetPrincipal(c) (401 if absent)
       │     │      ├── Validates configured roles: empty or unknown roles fail closed (403)
       │     │      ├── Compares principal.User.Roles against required roles
       │     │      │     ├── Match found -> c.Next()
       │     │      │     └── No match -> 403 Forbidden
       │     │      └── No super_admin bypass: routes must explicitly list permitted roles
       │     │
       │     └── 4. Protected Business Handler
       │            └── Accesses verified identity via GetPrincipal(c)
```

---

## 2. Authentication vs. Authorization

- **Authentication (`RequireAuth`)**: Establishes **who** is making the request. It extracts the ambient `giki_session` cookie, verifies the token against the PostgreSQL `giki_sports.sessions` table under row lock, confirms the user is active, touches activity, and stores the verified [`AuthenticatedPrincipal`](file:///d:/giki%20sports%20complex/backend/internal/authentication/service.go#L85) into Fiber locals. Unauthenticated, expired, revoked, or inactive sessions receive `HTTP 401 Unauthorized`.
- **Authorization (`RequireAnyRole`)**: Determines **what** an authenticated user is permitted to do. It inspects the dynamic roles loaded on the principal (`principal.User.Roles`) and compares them against the roles explicitly configured for the route. Authenticated principals lacking the required role receive `HTTP 403 Forbidden`.

---

## 3. Middleware Ordering & Composition

```go
// Public read endpoints (unprotected)
api.Get("/facilities", facilityHandler.List)

// Public authentication mutations (CSRF origin verified, unauthenticated)
api.Post("/auth/login", authHandler.RequireTrustedOrigin(), authHandler.rateLimiter, authHandler.Login)
api.Post("/auth/logout", authHandler.RequireTrustedOrigin(), authHandler.Logout)

// Protected endpoints (authenticated, any valid session)
api.Get("/auth/me", authHandler.RequireAuth(), authHandler.Me)

// Role-protected endpoints (authenticated + role authorized)
api.Get("/director/reports", authHandler.RequireAuth(), authentication.RequireAnyRole(user.RoleSportsDirector), directorReportHandler)
api.Get("/member/bookings", authHandler.RequireAuth(), authentication.RequireAnyRole(user.RoleStudent, user.RoleFaculty), memberBookingHandler)
```

### Execution Rules:
1. `RequireAuth` **must** execute before `RequireAnyRole`. If `RequireAnyRole` runs without an established principal in Fiber locals, it fails closed with `401 Unauthorized`.
2. `RequireTrustedOrigin` **must** be applied to state-changing mutation endpoints (`POST`, `PUT`, `DELETE`).
3. `Logout` **bypasses** `RequireAuth`. Expired or revoked sessions can still be revoked server-side and have their client cookies cleared without requiring valid authentication.

---

## 4. Fiber Locals & Typed Principal Accessor

Fiber's `c.Locals(key, value)` allows request-scoped values to be shared across middleware and handlers. However, storing values with generic string keys (e.g. `c.Locals("principal", ...)`) creates collision risks where third-party middleware or handlers could inadvertently overwrite or spoof identity data.

### 4.1 Private Context Key
GIKI Sports Complex uses an unexported, zero-size struct type as the dictionary key:
```go
type contextKey struct{}

var principalLocalKey = contextKey{}
```
Because the type and variable are unexported, external packages and middleware cannot forge or collide with the key.

### 4.2 Typed Principal Accessor
Downstream handlers extract the verified identity using the typed helper:
```go
func GetPrincipal(c *fiber.Ctx) (*AuthenticatedPrincipal, bool) {
    val := c.Locals(principalLocalKey)
    if val == nil {
        return nil, false
    }
    principal, ok := val.(*AuthenticatedPrincipal)
    return principal, ok && principal != nil
}
```
Client-supplied request headers (such as `X-User-ID`, `X-Role`, or `X-Director-Key`) are **strictly ignored**.

---

## 5. Status Codes: 401 vs. 403 vs. Infrastructure Errors

| Status Code | Reason | Meaning & Client Expectation |
|---|---|---|
| **401 Unauthorized** | Missing cookie, malformed token, expired session, revoked session, inactive user account, or missing principal in `RequireAnyRole`. | The client is not authenticated. Redirect to login or re-authenticate. |
| **403 Forbidden** | Authenticated user lacks required roles, empty/unknown role configuration, or untrusted/missing `Origin` header. | The client identity is recognized, but access to this specific resource is denied. Re-authenticating with the same account will not resolve this. |
| **503 Service Unavailable** | Context deadline exceeded or concurrency semaphore saturated. | Temporary saturation or timeout. The response includes a `Retry-After: 1` header. |
| **500 Internal Server Error** | Unexpected PostgreSQL connection failure, query error, or data integrity issue. | Server-side fault. Details are redacted from client response and logged to server error stream. |

---

## 6. Cookie Expiry Correction in Login

In Step 6G, the cookie helper issued cookies using a static 8-hour duration from `time.Now()`. This had edge-case vulnerabilities where database clock skew or delayed issuance could issue cookies extending beyond the server's persisted absolute expiry ceiling.

### 6.1 Bounded Cookie Expiry
In Step 6H, [`CookieManager.SetSessionCookie`](file:///d:/giki%20sports%20complex/backend/internal/authentication/cookie.go#L62) accepts the persisted session's [`AbsoluteExpiresAt`](file:///d:/giki%20sports%20complex/backend/internal/session/model.go#L40) timestamp:
```go
func (cm *CookieManager) BuildCookie(rawToken string, absoluteExpiresAt time.Time, now time.Time) (*fiber.Cookie, error) {
    remaining := absoluteExpiresAt.Sub(now)
    if remaining <= 0 {
        return nil, errors.New("cannot issue cookie for already expired session")
    }

    maxAgeSec := int(remaining.Seconds())
    if maxAgeSec <= 0 {
        return nil, errors.New("cannot issue cookie: session lifetime remaining rounds to zero seconds")
    }

    cookie := new(fiber.Cookie)
    cookie.Name = cm.name
    cookie.Value = rawToken
    cookie.Path = cm.path
    cookie.Domain = cm.domain
    cookie.MaxAge = maxAgeSec
    cookie.Expires = absoluteExpiresAt
    cookie.Secure = cm.secure
    cookie.HTTPOnly = true
    cookie.SameSite = cm.sameSite
    return cookie, nil
}
```
- **Never extends past absolute ceiling**: `cookie.Expires` is set to `absoluteExpiresAt`, and `cookie.MaxAge` truncates integer seconds toward zero.
- **Fail-safe on already expired sessions**: If a session's `AbsoluteExpiresAt` is in the past, `BuildCookie` returns an error, preventing the server from ever issuing an expired cookie as a successful login.

---

## 7. Clarifications & Security Corrections

### 7.1 HttpOnly Limits
> [!IMPORTANT]
> `HttpOnly` prevents client-side JavaScript (`document.cookie`) from reading the cookie value directly. However, **`HttpOnly` does NOT prevent XSS attacks from sending authenticated HTTP requests**. If an attacker injects malicious JavaScript via XSS, the browser will still automatically attach `HttpOnly` cookies to `fetch()` or `XMLHttpRequest` calls made by that script to `/api`. `HttpOnly` prevents token exfiltration, not ambient request forgery from an already compromised origin.

### 7.2 SameSite Concerns Sites, Not Origins
> [!NOTE]
> `SameSite` enforces boundaries based on **registrable domains (eTLD+1)**, not full origins. For example, `https://sports.giki.edu.pk` and `https://portal.giki.edu.pk` share the same site (`giki.edu.pk`) despite being different origins (different hosts). Therefore, `SameSite=Lax` permits cookies across subdomains of the same site. This is why GIKI Sports Complex combines `SameSite=Lax` with **exact canonical `Origin` verification** on mutation routes.

### 7.3 Cookie Path is Delivery Scoping, Not an Authorization Boundary
> [!WARNING]
> Setting `Path=/api` instructs the browser to attach the cookie only to requests whose path begins with `/api`. However, **cookie `Path` does NOT provide security isolation against JavaScript on the same origin**. Any script running on `http://localhost:5173/` or `https://app.giki.edu.pk/` can initiate a `fetch('/api/...')` call, and the browser will attach the `/api`-scoped cookie. Path is an optimization and delivery scope, never an access control mechanism.

---

## 8. GIKI Wallet Inspection & Adaptations

| Component | GIKI Wallet (`auth/middleware.go`) | GIKI Sports Complex (`internal/authentication`) |
|---|---|---|
| **Inspected Functions** | • `RequireRole(allowedRoles ...string)`<br>• `getTokenFromRequest`<br>• `GetUserIDFromContext`<br>• `GetUserRoleFromContext` | • `RequireAuth()`<br>• `RequireAnyRole(roles ...user.Role)`<br>• `RequireTrustedOrigin()`<br>• `GetPrincipal(c)` |
| **Framework** | Standard library `net/http` (`http.Handler`, `context.Context`). | Go Fiber v2 (`fiber.Handler`, `c.Locals()`). |
| **Locals Storage** | String-typed context keys (`"user_id"`, `"user_role"`). | Unexported private struct key (`principalLocalKey`) preventing key collision. |
| **SuperAdmin Bypass** | Hardcoded bypass: `if userRole == RoleSuperAdmin { next.ServeHTTP(...) }`. | **No automatic bypass**. Every route must explicitly declare permitted roles; unlisted roles fail closed. |
| **Role Representation** | Single string per user. | Slice of typed domain roles (`[]user.Role`) dynamically loaded from PostgreSQL. |
| **Empty/Unknown Roles** | Did not check for empty or unknown role values. | Fails closed (`403 Forbidden`) if configured roles slice is empty or contains an unrecognized role. |
| **Session Model** | Stateless JWT claims. | Stateful PostgreSQL sessions (`giki_session`) validated under database row lock. |
| **Wallet Status** | Left 100% unchanged. | No modifications to `giki-wallet/`. |

---

## 9. Verification Checks & Results

All tests executed with caching disabled (`-count=1`):

| Test Suite | Package | Scope / Tests | Result | Duration |
|---|---|---|:---:|:---:|
| `go build ./...` | `backend/` | Full compilation across all packages | **Passed** | 0.8s |
| `go vet ./...` | `backend/` | Static analysis across all packages | **Passed** | 0.5s |
| `middleware_test.go` | `internal/authentication` | Unit tests: missing cookie, invalid session, deadline exceeded (503), infrastructure error (500), locals population, spoofed header rejection, role matching (single, multiple, none, empty, unknown, super_admin no-bypass), /me single validation, logout bypass, cookie expiry & secure modes | **Passed (21 subtests)** | 0.05s |
| `handler_test.go` | `internal/authentication` | Unit tests: login, me, logout, CSRF origin, rate limiting, concurrency semaphore | **Passed (17 subtests)** | 0.05s |
| Complete Unit Suite | `backend/` | All 6 backend packages (`auth`, `authentication`, `config`, `facility`, `session`, `user`) | **Passed** | 2.8s |
| `middleware_integration_test.go` | `internal/authentication` | Disposable PostgreSQL DB (`giki_sports_disposable_authsvc_*`): migration, synthetic student & director, student access (200), student denied director route (403), director access (200), director denied student route (403), immediate dynamic DB role removal reflection (403), logout revocation (401), dev DB empty check | **Passed** | 1.35s |
| `http_integration_test.go` | `internal/authentication` | Disposable PostgreSQL DB: login/me/logout HTTP flows | **Passed** | 1.95s |
| `service_integration_test.go` | `internal/authentication` | Disposable PostgreSQL DB: core authentication service integration | **Passed** | 1.83s |
| `repository_integration_test.go` | `internal/session` | Disposable PostgreSQL DB: session repository locking & timeout integration | **Passed (13 subtests)** | 1.79s |

---

## 10. Remaining Limitations & Prototype Scope

1. **Legacy Mutation Routes Unprotected**: Prototype endpoints (`POST /api/bookings`, `POST /api/announcements`, `POST /api/memberships`) remain in-memory unprotected prototype routes. They will be protected by `RequireAuth()` and role guards when business database persistence is implemented.
2. **No Development Seed Accounts**: Development database tables (`users` and `sessions`) in PostgreSQL remain completely empty (0 rows). Test accounts are provisioned strictly inside disposable databases during automated integration test execution.
