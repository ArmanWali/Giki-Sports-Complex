# Current-State Audit: GIKI Sports Complex Management System

**Document Reference:** `docs/current-state-audit.md`  
**Audit Date:** October 2026  
**Baseline Reference:** [docs/requirements-baseline.md](file:///d:/giki%20sports%20complex/docs/requirements-baseline.md)  
**Execution Context:** Single-developer sequential execution by project lead. Historical course submissions list Abdullah Zia, Arman Wali, and Zohaib Malik for academic attribution only.  
**Inspected Artifacts:**
- [SE-423 Milestone 1 Report](file:///d:/giki%20sports%20complex/SE-423%20—%20Software%20Construction%20and%20Development_Milestone_1.pdf)
- [SE-431 Milestone 1 Report](file:///d:/giki%20sports%20complex/SE-431%20—%20Software%20Quality%20Assurance_Milestone_1.pdf)
- [README.md](file:///d:/giki%20sports%20complex/README.md)
- [backend/GIKI_SPORTS_COMPLEX_BACKEND_DESIGN.md](file:///d:/giki%20sports%20complex/backend/GIKI_SPORTS_COMPLEX_BACKEND_DESIGN.md)
- [backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go)
- [backend/data/store.json](file:///d:/giki%20sports%20complex/backend/data/store.json)
- [frontend/src/](file:///d:/giki%20sports%20complex/frontend/src/) (Components, Pages, API, Types)
- [giki-wallet/](file:///d:/giki%20sports%20complex/giki-wallet/) (Backend internal packages and SQL migrations)

---

## 1. Executive Summary

This audit assesses the existing repository state against the updated requirements baseline ([docs/requirements-baseline.md](file:///d:/giki%20sports%20complex/docs/requirements-baseline.md)).

The codebase currently comprises a prototype Go Fiber REST API ([backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go)) backed by a local JSON file ([backend/data/store.json](file:///d:/giki%20sports%20complex/backend/data/store.json)), and a React 19 / Vite / Tailwind v4 client ([frontend/](file:///d:/giki%20sports%20complex/frontend/)).

**Key Audit Takeaways:**
1. **Critical Frontend/Backend Interface Disconnect:** The React frontend expects a hierarchical UI model (`slug`, `shortName`, `icon`, `meta`, `schedule`, `coach`), while the Go backend returns an entirely different flat model. When the frontend attempts to render backend data, it evaluates undefined icon mappings, crashing with unhandled runtime exceptions.
2. **Missing Relational Infrastructure:** The prototype contains no relational database driver, no migrations, no transaction manager, no authentication/session mechanisms, and zero financial ledger code.
3. **Absence of Automated Verification:** The existing backend package contains zero test files (`[no test files]`), and the frontend package contains zero test scripts or test files. Current compilation successes do not constitute business-rule verification.
4. **Reusable Wallet Assets:** The neighboring [giki-wallet](file:///d:/giki%20sports%20complex/giki-wallet/) repository contains production-tested double-entry ledger logic, a JazzCash gateway adapter, and a concurrent hold expiration background worker that directly inform the required architecture.

---

## 2. Existing Functionality vs. Proposed Baseline

| Module | Prototype Implementation ([backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go)) | Proposed Requirements Baseline ([docs/requirements-baseline.md](file:///d:/giki%20sports%20complex/docs/requirements-baseline.md)) | Audit Assessment & Gap Analysis |
|---|---|---|---|
| **M1: User Authentication & Access Control** | Completely absent. No user accounts, sessions, password hashing, or token verification. Endpoints are unauthenticated. | **FR-01, QR-02, QR-13:** Salted Argon2id password hashing; server-side sessions with 30m idle / 8h absolute expiry; RBAC matrix (`student`, `faculty`, `sports_director`, `super_admin`, `cashier`); private record isolation. | **Total Gap:** Must build user accounts, Argon2id credential store, session tracking, and role-checking middleware from the ground up. |
| **M2: Facilities & Scheduling** | Static list of 9 sample facilities loaded from JSON. Read-only timetable strings. No closure models, no calendar blockouts, no user-group access validation. | **FR-02, QR-05:** Dynamic timetable management in PostgreSQL; shared-space restriction enforcement; calendar closures and event blocks; Strategy pattern (`EligibilityPolicy`) for user-group time rules. | **Substantial Gap:** Read operations exist for sample data; schedule write/update operations, closures, and eligibility strategies are absent. |
| **M3: Padel Court Booking** | Naive `POST /api/bookings` allowing reservations for all 9 sports with equipment rental arrays. In-memory conflict checking. Public unauthenticated `DELETE /api/bookings/:id`. | **FR-03, FR-06, QR-01, QR-03, QR-04:** Padel-only booking; 5-minute hold state machine (hold expired when `now >= expiresAt`); background hold release worker; wallet debit upon checkout; ticket code check-in; admin-only cancellation with refund once; idempotency protection. | **Architectural Rework:** Must restrict booking strictly to Padel, replace public deletion with admin refund workflow, eliminate equipment rentals, and implement transactional 5-minute hold engine. |
| **M4: Gym Membership Management** | `POST /api/memberships` creates unauthenticated passes with hardcoded 6-month validity (`AddDate(0,6,0)`), completely bypassing payment. | **FR-04, QR-06:** 30-day passes ($[T, T+30d)$); renewal math adding 30 days to $\max(T_{expiry}, T_{renewal})$; transactional activation strictly contingent on successful wallet debit. | **Logic & Integration Gap:** Rewrite validity calculation from 6 months to 30 days; integrate with digital wallet; require user authentication. |
| **M5: Digital Wallet & Payments** | Completely absent in both backend and frontend. | **FR-05, QR-03, QR-04, QR-12:** Double-entry append-only ledger; derived balances; cashier-authorized cash top-ups; JazzCash adapter; idempotent payment replays; audit logging. | **Total Gap in Sports Complex:** Zero code in place. Fully present in `giki-wallet` and ready for architectural adaptation. |
| **M6: Announcements & Sports Achievements** | Public `POST /api/achievements` and `POST /api/announcements`. Instant public visibility; no draft stage; no role check; public unauthenticated delete. | **FR-07:** Formal `DRAFT` $\to$ `PUBLISHED` state machine; mandatory title/content before publish; role-restricted mutations; public read limited to published items. | **Moderate Gap:** Basic data models exist in prototype; must add draft state machine, access control, and align fields with frontend. |
| **M7: Event Management** | Completely absent. | **FR-08:** University event reservations; facility blockout windows; atomic detection, cancellation, and refund of conflicting Padel bookings. | **Total Gap:** Must implement event booking coordinator and atomic conflict refund transaction. |
| **Cross-Cutting: Audit Trail** | None. | **FR-09:** Structured audit records (`actor`, `action`, `target`, `timestamp`, `outcome`) for administrative actions without leaking credentials. | **Total Gap in Sports Complex:** Ready for reuse from `giki-wallet/backend/internal/audit`. |

---

## 3. Frontend / Backend Contract Mismatches

The sports complex web client ([frontend/](file:///d:/giki%20sports%20complex/frontend/)) and prototype backend ([backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go)) operate on incompatible interface definitions:

### 3.1 Facility Schema Incompatibility (Fatal Runtime Error)
- **Frontend Model ([frontend/src/types.ts](file:///d:/giki%20sports%20complex/frontend/src/types.ts#L31-L43)):**
  ```typescript
  interface Facility {
    slug: string;
    name: string;
    shortName: string;
    tagline: string;
    description: string;
    icon: FacilityIconName;
    meta: FacilityMeta[];
    schedule: ScheduleEntry[];
    coach?: Coach;
    galleryCount: number;
  }
  ```
- **Backend Model ([backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go#L21-L36)):**
  ```go
  type Facility struct {
      ID, Name, Category, Description, Location string
      MaxPlayers int
      StudentTimings, FacultyTimings string
      Slots, Rules, EquipmentAvailable []string
      Image, Badge string
      IsMembershipRequired bool
  }
  ```
- **Failure Mechanism:** In [frontend/src/pages/Home.tsx](file:///d:/giki%20sports%20complex/frontend/src/pages/Home.tsx#L19-L23), calling `api.getFacilities()` replaces local static state with backend JSON. When [frontend/src/components/FacilityCard.tsx](file:///d:/giki%20sports%20complex/frontend/src/components/FacilityCard.tsx#L7) executes:
  ```typescript
  const Icon = FACILITY_ICONS[facility.icon];
  return <Icon size={22} ... />
  ```
  `facility.icon` is `undefined`, causing `FACILITY_ICONS[undefined]` to resolve to `undefined`. React immediately crashes with `TypeError: Icon is not a function / cannot read properties of undefined`.
- **Slug vs. ID Mismatch:** The frontend routes by `slug` (`/facilities/:slug`, e.g., `glass-padel-arena`), whereas the backend routes by `id` (e.g., `padel-court-1`).

### 3.2 Slots and Booking Contract Mismatch
- **Missing Slot Query Route:** [frontend/src/api.ts](file:///d:/giki%20sports%20complex/frontend/src/api.ts#L49-L50) calls `GET /api/facilities/:facilitySlug/slots`. In [backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go), this endpoint does not exist (returns 404 Not Found).
- **Booking Payload Discrepancy:**
  - Frontend sends [CreateBookingInput](file:///d:/giki%20sports%20complex/frontend/src/types.ts#L75-L79): `{ slotId, name, email }`.
  - Backend `POST /api/bookings` expects ([backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go#L561-L571)): `{ facilityId, date, timeSlot, bookerType, bookerName, bookerId, bookerEmail, bookerPhone, equipmentRentals }`.

### 3.3 Achievements Payload & Serialization Mismatch
- **Frontend Submission:** [frontend/src/api.ts](file:///d:/giki%20sports%20complex/frontend/src/api.ts#L59-L67) submits `multipart/form-data` with fields `caption` and `photo`.
- **Backend Handler:** [backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go#L664-L671) attempts `c.BodyParser(&ach)` for JSON fields `title`, `sport`, `date`, `category`, `description`, `teamMembers`, `directorNote`. Submissions fail with HTTP 400 Bad Request.

---

## 4. Authentication, Persistence, and Transaction Gaps

### 4.1 Authentication & Access Control Gaps
1. **Plaintext / No Password Hashing:** Prototype backend contains no authentication logic. Design document 2.0 proposed Bcrypt and JWT, which conflicts with the baseline requirement of **salted Argon2id** and **server-side stateful sessions** (QR-13).
2. **Missing Session Lifetime Enforcement:** No mechanisms exist to enforce the 30-minute idle timeout or 8-hour absolute session ceiling.
3. **No Horizontal Privilege Checks:** No validation exists to ensure a student or faculty member can only query or view their own booking receipts or wallet entries (QR-02).
4. **Unprotected Administrative Mutations:** Schedule creation, announcements, and booking deletions can be triggered anonymously.

### 4.2 Persistence & Storage Gaps
1. **Non-ACID JSON Storage:** All state is held in a single flat file ([backend/data/store.json](file:///d:/giki%20sports%20complex/backend/data/store.json)) guarded by a Go `sync.RWMutex`.
2. **Crash & Data Loss Vulnerability:** `saveUnsafe()` uses `os.WriteFile` without atomic replacement. A process crash during write results in a corrupted, unrecoverable file.
3. **Absence of Relational Schemas:** No foreign keys, no domain constraints, no unique indexes, and no migration tooling exist in the sports complex backend.
4. **No Backup / Recovery Mechanism:** Fails to provide automated daily backup or verified 30-minute restoration as mandated by QR-15.

### 4.3 Transaction & Concurrency Gaps
1. **Cross-Process Concurrency Failure:** The in-memory mutex only synchronizes requests within a single operating system process. Running multiple backend instances results in immediate race conditions and double bookings.
2. **Lack of Atomic UnitOfWork:** Confirming a booking requires writing a booking record, writing a debit ledger entry, and committing an idempotency record. The prototype has no transaction coordinator; any partial failure results in inconsistent state (violating QR-03).
3. **Absence of Hold State Machine:** The prototype immediately confirms bookings without the required 5-minute reservation window or background hold reclamation worker. Hold expiration rule: hold is expired when `now >= expiresAt`.

---

## 5. GIKI-Wallet Reuse Candidates and Required Adaptations

The neighboring [giki-wallet](file:///d:/giki%20sports%20complex/giki-wallet/) project provides established implementations for financial and transactional infrastructure:

### 5.1 Reusable Component Inventory

| Subsystem | Source Location | Reusable Assets | Relevance to Sports Complex Baseline |
|---|---|---|---|
| **Double-Entry Ledger** | [giki-wallet/backend/internal/wallet/](file:///d:/giki%20sports%20complex/giki-wallet/backend/internal/wallet/) | `service.go`: `executeDoubleEntryTransaction`<br/>Sorted UUID locking to prevent deadlocks<br/>HMAC-SHA256 ledger hash chaining<br/>Balance derivation queries | **Direct match for Module 5 (FR-05, QR-03).** |
| **Payment Gateway Adapter** | [giki-wallet/backend/internal/payment/](file:///d:/giki%20sports%20complex/giki-wallet/backend/internal/payment/) | `gateway/interface.go`<br/>`gateway/jazzcash.go`: HMAC signature calculation, callback verification<br/>Idempotent transaction handling | **Direct match for Module 5 & Adapter pattern (FR-05, QR-04, QR-12).** |
| **Hold Cleanup Worker** | [giki-wallet/backend/internal/transport/cleanup.go](file:///d:/giki%20sports%20complex/giki-wallet/backend/internal/transport/cleanup.go) | Background worker ticker<br/>Resilient per-hold transactions<br/>Row-level `SELECT ... FOR UPDATE` locking | **Direct model for Module 3 (FR-03, QR-01).** Adapted from seat holds to Padel court 5-minute holds. |
| **Audit Logging** | [giki-wallet/backend/internal/audit/](file:///d:/giki%20sports%20complex/giki-wallet/backend/internal/audit/) | `audit_logs` schema<br/>Structured logging of actor, action, entity, timestamp | **Direct match for FR-09.** |
| **Auth & Security Utilities** | [giki-wallet/backend/internal/auth/](file:///d:/giki%20sports%20complex/giki-wallet/backend/internal/auth/) | Argon2id hashing utilities<br/>Role checking middleware | **Foundational match for Module 1 (FR-01, QR-13).** |

### 5.2 Required Architectural Adaptations
1. **Deferred Abstract Factory Realization:** The Abstract Factory pattern (`TransactionRepositoryFactory` supplying `BookingRepository` and `LedgerRepository` bound to a `UnitOfWork` database transaction) will be realized at the checkout implementation stage, avoiding premature coupling during early persistence setup.
2. **Web Framework Standardization:** Reusable wallet handlers must be adapted to the sports complex HTTP router cleanly without bringing across unrelated transport/bus dependencies.
3. **Session Adaptation:** Replace wallet's stateless JWT/refresh-token flow with server-side sessions expiring after 30 minutes idle or 8 hours absolute age (QR-13).
4. **Strict Scope Isolation:** Do not copy unrelated subsystems (bus routes, stops, ticketing, driver management, student feedback, MS Graph mailer).
