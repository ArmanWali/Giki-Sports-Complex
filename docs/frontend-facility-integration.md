# Frontend Facility Integration (Step 5)

**Document Reference:** `docs/frontend-facility-integration.md`  
**Milestone:** Step 5 Complete (React Facility Pages Aligned with PostgreSQL Backend)  
**Applicable API Contract:** `docs/facility-api.md`

---

## 1. Executive Summary & Purpose

In Step 5, the React frontend application was aligned with the read-only PostgreSQL-backed Facility REST API (`GET /api/facilities` and `GET /api/facilities/:slug`).

Prior to this step:
1. The frontend depended on legacy mock attributes (`icon`, `shortName`, `tagline`, `meta`, `schedule`) in `data/facilities.ts`.
2. Rendering live data crashed at runtime on `FACILITY_ICONS[facility.icon]`.
3. The API client silently caught network errors and fell back to hardcoded mock data, concealing broken database connections and port mismatches.
4. The Vite development proxy routed `/api` to port `8080` (GIKI Wallet), whereas the Sports Complex backend runs on port `8081`.
5. Schedule time strings were vulnerable to JavaScript `Date` parsing wrap-around bugs when handling `"24:00:00"` (midnight end-of-day).

All five issues have been resolved while preserving the existing visual styling, brand palette, and responsive layout.

---

## 2. Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                       Browser Client                        │
│   React 19 + React Router v7 + Tailwind CSS Design System   │
└──────────────┬──────────────────────────────▲───────────────┘
               │ 1. Request relative /api/..  │ 6. Render live DTOs
               ▼                              │
┌─────────────────────────────────────────────┴───────────────┐
│              Vite Dev Server (Port 5173)                    │
│   Proxy /api -> http://127.0.0.1:8081 (Backend)            │
└──────────────┬──────────────────────────────▲───────────────┘
               │ 2. Forward HTTP request      │ 5. Relay JSON DTOs
               ▼                              │
┌─────────────────────────────────────────────┴───────────────┐
│            Go Fiber Backend (Port 8081)                     │
│   Handler: internal/facility/handler.go                     │
└──────────────┬──────────────────────────────▲───────────────┘
               │ 3. Query PostgreSQL Pool     │ 4. Scan sql.Rows
               ▼                              │
┌─────────────────────────────────────────────┴───────────────┐
│     PostgreSQL 17 (Port 5434 in Docker Engine)              │
│   Tables: giki_sports.facilities & recurring_schedules     │
└─────────────────────────────────────────────────────────────┘
```

### Trace: From React to PostgreSQL and Back
1. **Homepage Mount:** `frontend/src/pages/Home.tsx` mounts and invokes `api.getFacilities({ signal })`.
2. **Relative Request:** The browser sends `GET /api/facilities` to the Vite dev server (`http://localhost:5173/api/facilities`).
3. **Vite Reverse Proxy:** Vite's dev server matches the `/api` prefix and proxies the request to `http://127.0.0.1:8081/api/facilities`.
4. **Fiber Routing & Repository:** The Go backend Fiber app handles the request via `internal/facility/handler.go`, executing `repo.List(ctx)` against the `pgxpool.Pool` targeting PostgreSQL on `127.0.0.1:5434`.
5. **Database Query:** PostgreSQL executes a query joining `giki_sports.facilities` and `giki_sports.recurring_schedules`, returning rows ordered by `name ASC` and schedule start time.
6. **JSON Serialization:** The backend maps domain records into camelCase DTOs (`FacilityResponse`, `ScheduleResponse`) and writes JSON with HTTP 200.
7. **Frontend Validation:** `frontend/src/api.ts` parses the JSON, validates its shape via `parseFacilities` (rejecting malformed data), and passes the validated `Facility[]` to state.
8. **UI Rendering:** `FacilitiesGrid` renders cards with live facility names, locations, and schedule counts. `StatsStrip` derives total facility count from the live list.

---

## 3. Key Technical Decisions & Patterns

### 3.1 Compile-Time Types vs. Runtime Validation
TypeScript types (e.g. `interface Facility`) exist exclusively at compile-time and are completely erased during JavaScript bundle generation. They cannot validate incoming JSON at runtime.

To safeguard against silent UI failures or malformed payloads, focused runtime type guards and parsers were implemented in `frontend/src/types.ts`:
- `isSchedule(val: unknown): val is Schedule`: Checks `id`, `dayOfWeek` (1–7 integer), 24h `startTime` / `endTime` format (`HH:MM:SS`), and non-empty `audience`.
- `isFacility(val: unknown): val is Facility`: Verifies non-empty `id`, `slug`, `name`, nullable `description`/`location`, allowed `status` enum (`active`, `maintenance`, `closed`), and an array of valid `Schedule` objects.
- `parseFacility(payload: unknown): Facility` and `parseFacilities(payload: unknown): Facility[]`: Throws descriptive, actionable runtime errors if an API response does not conform to the schema, preventing `undefined` property crashes in React components.

### 3.2 Safe URL Construction & Request Cancellation
- **URL Encoding:** In `api.ts`, detail lookups use `encodeURIComponent(slug.trim())` to protect against path traversal or illegal URL characters.
- **Request Cancellation:** All API methods accept `{ signal?: AbortSignal }`. In `Home.tsx` and `FacilityDetail.tsx`, `useEffect` instantiates an `AbortController` and returns `() => controller.abort()`. When a component unmounts or the route slug changes, pending HTTP requests are canceled immediately.
- **Stale State Prevention:** In `FacilityDetail.tsx`, changing route from slug A to slug B clears old facility data (`setFacility(null)`), shows a spinner, and aborts in-flight requests for slug A, ensuring late-arriving responses for slug A cannot overwrite slug B.

### 3.3 HTTP Status Distinction (404 vs. 500)
- `api.ts` defines `ApiError(status, message)`.
- If the backend returns HTTP 404, `FacilityDetail.tsx` renders a dedicated **"Facility Not Found"** banner with a direct link back to `#facilities`.
- If the backend returns 500 or network connection errors, the page displays an **"Unable to Load Facility"** alert with a prominent **Retry** button.

### 3.4 Elimination of Mock Fallback Anti-Pattern
Previous frontend code caught API errors and substituted hardcoded mock data from `data/facilities.ts`. This created a false impression that the live backend was functioning when it was actually disconnected or colliding on ports.
The fallback was eliminated completely:
- Real network and server errors surface directly in the UI.
- Users are provided with clear, actionable retry mechanisms.

### 3.5 End-of-Day Time Formatting (`24:00:00`)
Standard JavaScript `new Date("1970-01-01T24:00:00")` either wraps around to `00:00:00` next day or parses as invalid.
`formatTimeRange(start, end)` directly formats time strings:
- Extracts `HH:MM` directly (`"09:00:00"` $\to$ `"09:00"`).
- Explicitly detects `"24:00:00"` and renders it as `"24:00 (Midnight)"`.
- The detail page explicitly documents that times are displayed in local wall-clock **Asia/Karachi (PKT, UTC+5)** time.

### 3.6 Operational Status Semantics
- Operational `status` (`active`, `maintenance`, `closed`) reflects physical facility readiness, **not** real-time booking availability.
- The UI explicitly renders an informative badge and note explaining this distinction.
- The nonfunctional "Book a session" button was removed from facility detail pages to maintain an honest, read-only interface until booking flows are implemented.

### 3.7 Derived Statistics & Legacy Boundaries
- `StatsStrip.tsx` accepts an optional `facilityCount?: number`. When live facilities are successfully loaded, the component derives the count dynamically from `facilities.length`, replacing the static count.
- Other statistics (national titles, tournaments hosted, members) remain as legacy UI elements and are not falsely presented as live PostgreSQL aggregations.

---

## 4. Vite Development Proxy Configuration

In `frontend/vite.config.ts`:
```ts
server: {
  proxy: {
    "/api": {
      target: "http://127.0.0.1:8081",
      changeOrigin: true,
      secure: false,
    },
  },
},
```
- **Target:** `http://127.0.0.1:8081` (GIKI Sports Complex Go Fiber backend).
- **Security:** No database credentials or secrets exist in the frontend configuration.
- **Vite Restart:** Modifying `vite.config.ts` requires restarting the Vite development process (`npm run dev`) for proxy changes to take effect.

---

## 5. Verification Results

### 5.1 Automated Frontend Tests (Vitest & React Testing Library)
Ran `npm test` in `frontend/`:
- **`src/test/validation.test.ts` (12 tests):** Validates conforming facilities/schedules, rejects out-of-range days, malformed times, non-array schedules, invalid statuses, tests `formatTimeRange` and `"24:00:00"` preservation.
- **`src/test/FacilityList.test.tsx` (4 tests):** Tests loading state, empty state, success state with card navigation slug links, and error state with retry recovery.
- **`src/test/FacilityDetail.test.tsx` (6 tests):** Tests detail success, 404 not found, server error with retry, nullable fields (`description: null`, `location: null`), empty schedules, and route switching with request cancellation.
- **Result:** **3 test files passed, 22 tests passed (Exit 0)**.

### 5.2 TypeScript Compilation & Production Build
Ran `npm run build` (`tsc -b && vite build`) in `frontend/`:
- **Modules Transformed:** 1933 modules.
- **Output:** `dist/index.html` (1.07 kB), `dist/assets/index-*.css` (21.24 kB), `dist/assets/index-*.js` (295.30 kB).
- **Result:** **Passed with zero errors (Exit 0)**.

### 5.3 Browser Subagent Verification
Ran full browser session on `http://localhost:5173/`:
1. **Homepage:** Rendered header, hero banner, stats strip with live count, and "Explore facilities" section displaying the 2 seeded PostgreSQL facilities:
   - `[Demo] Campus Badminton Court` (`Demo Sports Hall Wing B`, Active)
   - `[Demo] Table Tennis Arena` (`Demo Activity Center 1st Floor`, Active)
2. **Card Navigation:** Clicked Badminton Court; cleanly navigated to `/facilities/demo-badminton-court`.
3. **Detail Timetable:** Displayed name, location, active badge, and weekly schedules for Monday, Wednesday, and Friday with Asia/Karachi note.
4. **Direct Navigation:** Visited `/facilities/demo-table-tennis`; displayed Tuesday and Saturday schedules.
5. **404 Handling:** Visited `/facilities/non-existent-facility-slug`; rendered "Facility Not Found" banner with back navigation link.
6. **Console Health:** Verified zero facility-related runtime warnings or errors in the browser console.

---

## 6. How to Run Locally

### Prerequisites
- Docker engine running with PostgreSQL container (`127.0.0.1:5434`).
- Applied database migrations (`00001` and `00002`).
- Applied development seed fixture (`go run ./cmd/seed --demo`).

### Step 1: Start the Backend Server
```bash
cd backend
go run .
```
Backend will start on `http://127.0.0.1:8081`. Confirm readiness at `http://127.0.0.1:8081/api/ready`.

### Step 2: Start the Frontend Development Server
```bash
cd frontend
npm run dev
```
Vite will start on `http://localhost:5173/`.

### Pages to Visit
1. **Homepage:** `http://localhost:5173/`  
   Scroll to "Explore facilities" to view the live PostgreSQL facility cards.
2. **Badminton Court Detail:** `http://localhost:5173/facilities/demo-badminton-court`  
   Inspect the structured weekly operating timetable and Asia/Karachi local time note.
3. **Table Tennis Arena Detail:** `http://localhost:5173/facilities/demo-table-tennis`
4. **404 Error Demonstration:** `http://localhost:5173/facilities/non-existent-facility-slug`

---

## 7. Remaining Limitations & Boundaries
1. **Scope Boundary:** Step 5 only aligned read-only facility display pages.
2. **Legacy Sections:** Achievements, announcements, memberships, and bookings remain backed by `backend/data/store.json`.
3. **No Booking Action:** Facility detail pages are strictly informative; booking integration will be implemented in subsequent milestones.
