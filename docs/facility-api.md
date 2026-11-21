# Facility HTTP API Contract

This document specifies the public REST API contract for sports facility retrieval endpoints in the GIKI Sports Complex application.

---

## 1. Overview & Architectural Boundaries

### 1.1 Read-Only Endpoints
The facility endpoints provide read-only access to facilities and their recurring weekly operating schedules.

- `GET /api/facilities` — Retrieve all facilities and their associated schedules.
- `GET /api/facilities/:slug` — Retrieve a single facility and its schedules by unique URL slug.

### 1.2 Storage Layer Transition State
> [!IMPORTANT]
> **Persistence Boundary:**
> - The two facility GET endpoints (`/api/facilities`, `/api/facilities/:slug`) query the live relational PostgreSQL database (`giki_sports` schema) via [facility.PostgresRepository](file:///d:/giki%20sports%20complex/backend/internal/facility/repository.go).
> - All other business endpoints (`/api/bookings`, `/api/memberships`, `/api/achievements`, `/api/announcements`, `/api/stats`) continue to read from and write to local JSON storage (`backend/data/store.json`).
> - The facility endpoints **never fall back to JSON storage** if PostgreSQL fails.

---

## 2. Endpoints

### 2.1 List Facilities

- **Path:** `/api/facilities`
- **Method:** `GET`
- **URL Parameters:** None
- **Query Parameters:** None
- **Description:** Returns all facilities ordered deterministically by name and slug, including their recurring weekly operating windows.

#### Success Response: HTTP 200 OK
Returns a JSON array of facilities. If no facilities exist in the database, returns an empty array `[]` (HTTP 200 OK).

```json
[
  {
    "id": "d0000001-0000-4000-8000-000000000001",
    "slug": "demo-badminton-court",
    "name": "[Demo] Campus Badminton Court",
    "description": "Synthetic demonstration court for local testing and timetable preview",
    "location": "Demo Sports Hall Wing B",
    "status": "active",
    "schedules": [
      {
        "id": "d0000001-0000-4000-8000-000000000011",
        "dayOfWeek": 1,
        "startTime": "09:00:00",
        "endTime": "12:00:00",
        "audience": "student"
      },
      {
        "id": "d0000001-0000-4000-8000-000000000012",
        "dayOfWeek": 3,
        "startTime": "16:00:00",
        "endTime": "18:00:00",
        "audience": "faculty"
      },
      {
        "id": "d0000001-0000-4000-8000-000000000013",
        "dayOfWeek": 5,
        "startTime": "14:00:00",
        "endTime": "16:00:00",
        "audience": "women_only"
      }
    ]
  },
  {
    "id": "d0000002-0000-4000-8000-000000000002",
    "slug": "demo-table-tennis",
    "name": "[Demo] Table Tennis Arena",
    "description": "Synthetic demonstration table tennis arena for local testing",
    "location": "Demo Activity Center 1st Floor",
    "status": "active",
    "schedules": [
      {
        "id": "d0000002-0000-4000-8000-000000000021",
        "dayOfWeek": 2,
        "startTime": "10:00:00",
        "endTime": "13:00:00",
        "audience": "general"
      },
      {
        "id": "d0000002-0000-4000-8000-000000000022",
        "dayOfWeek": 6,
        "startTime": "18:00:00",
        "endTime": "21:00:00",
        "audience": "student"
      }
    ]
  }
]
```

---

### 2.2 Get Facility by Slug

- **Path:** `/api/facilities/:slug`
- **Method:** `GET`
- **URL Parameters:**
  - `slug` (string, required): The unique URL slug of the facility (e.g. `demo-badminton-court`).
- **Lookup Semantics:**
  - The parameter is a **URL slug**, not an internal UUID.
  - The lookup executes an exact string match against `giki_sports.facilities(slug)`.
  - If a facility with the given slug does not exist, the API returns HTTP 404 Not Found.

#### Success Response: HTTP 200 OK
Returns a single Facility JSON object:

```json
{
  "id": "d0000001-0000-4000-8000-000000000001",
  "slug": "demo-badminton-court",
  "name": "[Demo] Campus Badminton Court",
  "description": "Synthetic demonstration court for local testing and timetable preview",
  "location": "Demo Sports Hall Wing B",
  "status": "active",
  "schedules": [
    {
      "id": "d0000001-0000-4000-8000-000000000011",
      "dayOfWeek": 1,
      "startTime": "09:00:00",
      "endTime": "12:00:00",
      "audience": "student"
    },
    {
      "id": "d0000001-0000-4000-8000-000000000012",
      "dayOfWeek": 3,
      "startTime": "16:00:00",
      "endTime": "18:00:00",
      "audience": "faculty"
    },
    {
      "id": "d0000001-0000-4000-8000-000000000013",
      "dayOfWeek": 5,
      "startTime": "14:00:00",
      "endTime": "16:00:00",
      "audience": "women_only"
    }
  ]
}
```

#### Error Response: HTTP 404 Not Found
Returned when the requested facility slug does not exist in the database:

```json
{
  "error": "facility not found"
}
```

---

### 2.3 Update Schedule Window (Step 7D Protected Endpoint)

- **Path:** `/api/facilities/:slug/schedules/:id`
- **Method:** `PUT`
- **Authentication & Authorization:**
  - Protected by `RequireTrustedOrigin()`, `RequireAuth()`, and `RequireAnyRole(user.RoleSportsDirector, user.RoleSuperAdmin)`.
  - The browser must transmit an `Origin` matching configured trusted frontend origins (`http://127.0.0.1:5173` / `http://localhost:5173`).
  - The session must be active via HttpOnly cookie (`giki_session`).
  - Anonymous or expired requests return **401 Unauthorized**.
  - Student or faculty roles without sports director or super admin privileges return **403 Forbidden**.
  - Missing or untrusted `Origin` headers return **403 Forbidden** before session validation.
- **URL Parameters:**
  - `slug` (string, required): The unique URL slug of the parent facility.
  - `id` (string, required): The UUID of the schedule window to modify.
- **Request Headers:**
  - `Content-Type`: Must be `application/json` (HTTP 415 if missing or non-JSON).
  - `Origin`: Must match trusted origin whitelist (HTTP 403 if missing or untrusted).
  - `Cookie`: Must contain valid `giki_session` cookie (HTTP 401 if missing or invalid).
- **Request Body Limits:**
  - Maximum body size: 4096 bytes (HTTP 413 if exceeded).
  - Unknown fields are strictly disallowed (HTTP 400 if unexpected properties are present).

#### Request Body Schema

```json
{
  "dayOfWeek": 3,
  "startTime": "10:00:00",
  "endTime": "13:00:00",
  "audience": "women_only"
}
```

| Field | Type | Required | Constraints |
|---|---|:---:|---|
| `dayOfWeek` | `integer` | Yes | ISO-8601 numeric weekday: `1` (Monday) through `7` (Sunday). |
| `startTime` | `string` | Yes | 24-hour wall-clock format `"HH:MM:SS"` (`00:00:00` to `23:59:59`). |
| `endTime` | `string` | Yes | 24-hour wall-clock format `"HH:MM:SS"` (`00:00:01` to `24:00:00`). Preserves `"24:00:00"`. Must be strictly after `startTime`. |
| `audience` | `string` | Yes | Target cohort: `"general"`, `"student"`, `"faculty"`, `"women_only"`, `"staff"`. |

#### Success Response: HTTP 200 OK
Returns the updated ScheduleResponse object:

```json
{
  "id": "d0000001-0000-4000-8000-000000000011",
  "dayOfWeek": 3,
  "startTime": "10:00:00",
  "endTime": "13:00:00",
  "audience": "women_only"
}
```

#### Dual-Identifier Scoping & Invariants
- **Dual-Identifier Scoping:** Conditions on both `s.id = $1` and `f.slug = $2`. If a schedule belongs to a different facility, zero rows are updated and the endpoint returns **HTTP 404 Not Found**.
- **Audit Actor Binding:** The audit trail actor ID is extracted **exclusively** from the authenticated principal session (`principal.User.ID`). The client cannot choose or spoof the actor ID.
- **Single-Transaction Atomicity:** The schedule update and administrative audit log entry (`giki_sports.audit_logs`) commit in a single PostgreSQL transaction. If either step fails, the entire transaction rolls back and the schedule row remains untouched.
- **Stale-Editor Conflict Detection Limit:** Stale-editor conflict detection (e.g., optimistic locking using row version numbers, `ETag`, or `If-Match`) is **not implemented** in this chunk. If two administrators submit concurrent edits to the same schedule window, the last write committed under row locking will persist.

#### Error Responses

| HTTP Status | Condition | Example Response Body |
|---|---|---|
| **400 Bad Request** | Malformed JSON, unknown fields, invalid UUID, empty body, or contract validation failure | `{"error": "invalid schedule window: dayOfWeek must be between 1 (Monday) and 7 (Sunday), got 8"}` |
| **401 Unauthorized** | Missing, invalid, revoked, or expired `giki_session` cookie | `{"error": "unauthorized: missing session cookie"}` |
| **403 Forbidden** | Missing/untrusted `Origin`, or authenticated user lacks required roles (`sports_director`, `super_admin`) | `{"error": "forbidden: insufficient permissions"}` |
| **404 Not Found** | Facility slug not found, schedule ID not found, or cross-facility mismatch | `{"error": "schedule not found for facility"}` |
| **409 Conflict** | Proposed window duplicates an existing window on the same facility (`uq_schedules_window`) | `{"error": "schedule window duplicates an existing window for this facility"}` |
| **413 Payload Too Large** | Request body exceeds 4KB limit | `{"error": "request body too large"}` |
| **415 Unsupported Media Type** | `Content-Type` header is not `application/json` | `{"error": "unsupported media type: Content-Type must be application/json"}` |
| **500 Internal Server Error** | Unexpected database error or transaction failure | `{"error": "internal server error"}` |
| **503 Service Unavailable** | Database query deadline exceeded | `{"error": "service unavailable: request timed out"}` |

---

### 2.4 Delete Facility Schedule Window (Audited)

- **Path:** `/api/facilities/:slug/schedules/:id`
- **Method:** `DELETE`
- **Security & Authorization:**
  - **CSRF Defense:** Requires a trusted `Origin` header matching `AUTH_TRUSTED_ORIGINS` (e.g., `http://localhost:5173`, `http://127.0.0.1:5173`). Missing or non-whitelisted Origin requests are terminated immediately with **HTTP 403 Forbidden**.
  - **Session Authentication:** Requires an active, valid `giki_session` HttpOnly cookie. Missing, expired, or revoked sessions return **HTTP 401 Unauthorized**.
  - **Role-Based Access Control:** Strictly restricted to authenticated users holding the **`sports_director`** or **`super_admin`** role. Users holding other roles (e.g. `student`, `faculty`) return **HTTP 403 Forbidden**.
- **URL Parameters:**
  - `slug`: Unique facility URL slug (e.g., `"demo-badminton-court"`).
  - `id`: Canonical UUID of the schedule window to delete.
- **Request Headers:**
  - `Origin: http://localhost:5173` (mandatory for state-changing operations).
  - `Cookie: giki_session=<raw-session-token>` (automatic via browser credentials).
- **Request Body:** None. No payload is accepted or parsed.

#### Success Response: HTTP 204 No Content
Returns HTTP 204 with an empty body and `Cache-Control: no-store` header upon successful commit.

#### Dual-Identifier Scoping & Invariants
- **Dual-Identifier Scoping:** Conditions on both `s.id = $1` and `f.slug = $2`. If a schedule belongs to a different facility, zero rows are deleted and the endpoint returns **HTTP 404 Not Found**.
- **Audit Actor Binding:** The audit trail actor ID is extracted **exclusively** from the authenticated principal session (`principal.User.ID`). The client cannot choose or spoof the actor ID.
- **Single-Transaction Atomicity:** The schedule row deletion and administrative audit log entry (`giki_sports.audit_logs`) commit in a single PostgreSQL transaction. If either step fails (e.g. audit insert failure), the entire transaction rolls back and the schedule row remains visible in public GET queries.
- **Audit Trail Durability:** Because `audit_logs.target_id` is a UUID without a foreign key constraint to `schedules(id)`, deleting the schedule row does not cascade to or delete the audit record. The audit record remains permanently queryable with full previous window details.
- **Idempotence & Repeat Deletions:** A repeated `DELETE` request for an already deleted window returns **HTTP 404 Not Found** and does **not** insert any duplicate audit log entry.

#### Error Responses

| HTTP Status | Condition | Example Response Body |
|---|---|---|
| **400 Bad Request** | Blank facility slug or invalid schedule UUID | `{"error": "invalid schedule id: must be a valid non-nil UUID"}` |
| **401 Unauthorized** | Missing, invalid, revoked, or expired `giki_session` cookie | `{"error": "unauthorized: missing session cookie"}` |
| **403 Forbidden** | Missing/untrusted `Origin`, or authenticated user lacks required roles (`sports_director`, `super_admin`) | `{"error": "forbidden: insufficient permissions"}` |
| **404 Not Found** | Facility slug not found, schedule ID not found, cross-facility mismatch, or already deleted | `{"error": "schedule not found for facility"}` |
| **500 Internal Server Error** | Unexpected database error or transaction failure | `{"error": "internal server error"}` |
| **503 Service Unavailable** | Database query deadline exceeded | `{"error": "service unavailable: request timed out"}` |

---

### 2.5 Create Facility Schedule Window (Audited)

- **Path:** `/api/facilities/:slug/schedules`
- **Method:** `POST`
- **Security & Authorization:**
  - **CSRF Defense:** Requires a trusted `Origin` header matching `AUTH_TRUSTED_ORIGINS` (e.g., `http://localhost:5173`, `http://127.0.0.1:5173`). Missing or non-whitelisted Origin requests are terminated immediately with **HTTP 403 Forbidden**.
  - **Session Authentication:** Requires an active, valid `giki_session` HttpOnly cookie. Missing, expired, or revoked sessions return **HTTP 401 Unauthorized**.
  - **Role-Based Access Control:** Strictly restricted to authenticated users holding the **`sports_director`** or **`super_admin`** role. Users holding other roles (e.g. `student`, `faculty`) return **HTTP 403 Forbidden**.
- **URL Parameters:**
  - `slug` (string, required): The unique URL slug of the parent facility.
- **Request Headers:**
  - `Content-Type`: Must be `application/json` (HTTP 415 if missing or non-JSON).
  - `Origin`: Must match trusted origin whitelist (HTTP 403 if missing or untrusted).
  - `Cookie`: Must contain valid `giki_session` cookie (HTTP 401 if missing or invalid).
- **Request Body Limits:**
  - Maximum body size: 4096 bytes (HTTP 413 if exceeded).
  - Unknown fields are strictly disallowed (HTTP 400 if unexpected properties like `actorId`, `role`, or `id` are present).

#### Request Body Schema

```json
{
  "dayOfWeek": 1,
  "startTime": "09:00:00",
  "endTime": "11:00:00",
  "audience": "student"
}
```

| Field | Type | Required | Constraints |
|---|---|:---:|---|
| `dayOfWeek` | `integer` | Yes | ISO-8601 numeric weekday: `1` (Monday) through `7` (Sunday). |
| `startTime` | `string` | Yes | 24-hour wall-clock format `"HH:MM:SS"` (`00:00:00` to `23:59:59`). |
| `endTime` | `string` | Yes | 24-hour wall-clock format `"HH:MM:SS"` (`00:00:01` to `24:00:00`). Preserves `"24:00:00"`. Must be strictly after `startTime`. |
| `audience` | `string` | Yes | Target cohort: `"general"`, `"student"`, `"faculty"`, `"women_only"`, `"staff"`. |

#### Success Response: HTTP 201 Created
Returns the newly created ScheduleResponse object with its PostgreSQL-generated UUID:

```json
{
  "id": "c71a3964-bca5-4015-89ae-bb7cbaea98cf",
  "dayOfWeek": 1,
  "startTime": "09:00:00",
  "endTime": "11:00:00",
  "audience": "student"
}
```

#### Invariants & Transaction Guarantees
- **Audit Actor Binding:** The audit trail actor ID is extracted **exclusively** from the authenticated principal session (`principal.User.ID`). The client cannot specify or spoof the actor ID.
- **Single-Transaction Atomicity:** The schedule insertion and administrative audit log entry (`giki_sports.audit_logs` with action `schedule.create`) commit in a single PostgreSQL transaction. If either step fails, the entire transaction rolls back and zero rows remain in `giki_sports.schedules`.
- **Immediate Read-Back Consistency:** Once committed, signed-out public GET requests immediately reflect the newly created operating window in the facility timetable.

#### Error Responses

| HTTP Status | Condition | Example Response Body |
|---|---|---|
| **400 Bad Request** | Malformed JSON, unknown fields, empty body, or contract validation failure | `{"error": "invalid schedule window: start_time (15:00:00) must be strictly before end_time (10:00:00)"}` |
| **401 Unauthorized** | Missing, invalid, revoked, or expired `giki_session` cookie | `{"error": "unauthorized: authentication required"}` |
| **403 Forbidden** | Missing/untrusted `Origin`, or authenticated user lacks required roles (`sports_director`, `super_admin`) | `{"error": "forbidden: insufficient permissions"}` |
| **404 Not Found** | Facility slug not found | `{"error": "facility not found"}` |
| **409 Conflict** | Proposed window duplicates an existing window on the same facility (`uq_schedules_window`) | `{"error": "schedule window duplicates an existing window for this facility"}` |
| **413 Payload Too Large** | Request body exceeds 4KB limit | `{"error": "request body too large"}` |
| **415 Unsupported Media Type** | `Content-Type` header is not `application/json` | `{"error": "unsupported media type: Content-Type must be application/json"}` |
| **500 Internal Server Error** | Unexpected database error or transaction failure | `{"error": "internal server error"}` |
| **503 Service Unavailable** | Database query deadline exceeded | `{"error": "service unavailable: request timed out"}` |

---

## 3. Data Transfer Objects (DTO) Contract

All responses use explicit camelCase JSON properties matching the domain read models. Internal database audit columns (`created_at`, `updated_at`) are intentionally omitted from public DTOs.

### 3.1 FacilityResponse
| Property | Type | Nullable | Description |
|---|---|:---:|---|
| `id` | `string` (UUID) | No | Canonical UUID identifier. |
| `slug` | `string` | No | URL-safe slug identifier (e.g. `"demo-badminton-court"`). |
| `name` | `string` | No | Display name of the facility. |
| `description` | `string` \| `null` | **Yes** | Facility description, or `null` if not provided. |
| `location` | `string` \| `null` | **Yes** | Physical location description, or `null` if not provided. |
| `status` | `string` | No | Current operational status: `"active"`, `"maintenance"`, or `"closed"`. |
| `schedules` | `Array<ScheduleResponse>` | No | List of weekly schedule windows. **Always returns `[]`, never `null`.** |

### 3.2 ScheduleResponse
| Property | Type | Nullable | Description |
|---|---|:---:|---|
| `id` | `string` (UUID) | No | Canonical schedule window UUID. |
| `dayOfWeek` | `integer` (1..7) | No | ISO-8601 day of the week (1 = Monday ... 7 = Sunday). |
| `startTime` | `string` ("HH:MM:SS") | No | 24-hour local wall-clock start time. |
| `endTime` | `string` ("HH:MM:SS") | No | 24-hour local wall-clock end time (preserves `"24:00:00"`). |
| `audience` | `string` | No | Target cohort: `"general"`, `"student"`, `"faculty"`, `"women_only"`, `"staff"`. |

---

## 4. Time, Weekday, and Schedule Semantics

### 4.1 Day of Week Convention (ISO-8601)
Operating schedules use integer weekdays matching ISO-8601:
- `1` = Monday
- `2` = Tuesday
- `3` = Wednesday
- `4` = Thursday
- `5` = Friday
- `6` = Saturday
- `7` = Sunday

### 4.2 Local Wall-Clock Time (Asia/Karachi, PKT, UTC+5)
Schedule operating times represent recurring weekly local facility hours in Pakistan Standard Time (PKT, UTC+5). They are intentionally decoupled from calendar dates and daylight shifts, avoiding timezone translation ambiguity.

### 4.3 Preservation of End Time `"24:00:00"`
PostgreSQL allows `TIME` values up to `24:00:00` (representing midnight at the end of the day). Standard Go `time.Time` cannot represent hour 24 and would overflow or wrap to `00:00:00`.
- The repository formats times using PostgreSQL `to_char(time_col, 'HH24:MI:SS')`.
- The API delivers `"24:00:00"` verbatim to clients.
- Clients can reliably calculate duration: e.g. `"22:00:00"` to `"24:00:00"` equals exactly 2 hours.

### 4.4 Overnight Schedule Split
An overnight facility session spanning midnight is represented by two sequential daily rows:
1. Day 6 (Saturday): `startTime = "22:00:00"`, `endTime = "24:00:00"`
2. Day 7 (Sunday): `startTime = "00:00:00"`, `endTime = "02:00:00"`

---

## 5. Operational Status vs. Booking Availability

> [!NOTE]
> **Domain Semantics Clarification:**
> The `status` field (`"active"`, `"maintenance"`, `"closed"`) represents the structural readiness and operational administrative state of the physical facility.
> **It is NOT computed real-time booking availability.**
> An `"active"` facility indicates the court or hall is operational, but specific time slots may be booked, reserved for varsity practice, or subject to user eligibility policies. Real-time slot availability, holds, and booking eligibility will be handled in subsequent booking engine steps.

---

## 6. Error Responses & Fault Tolerance

All error payloads use a standardized, stable JSON structure: `{"error": "<message>"}`.

| HTTP Status | Condition | Response Body |
|---|---|---|
| **404 Not Found** | Facility slug not found in database | `{"error": "facility not found"}` |
| **500 Internal Server Error** | Unexpected database error | `{"error": "internal server error"}` |
| **503 Service Unavailable** | Database query deadline exceeded / pool timeout | `{"error": "service unavailable: request timed out"}` |

### Diagnostic Logging & Credential Safety
- Database errors and timeout diagnostics are logged to server stderr for internal debugging.
- Internal errors are never exposed in JSON responses to prevent SQL injection probing or information leakage.
- Passwords and connection strings are strictly redacted from logs.
