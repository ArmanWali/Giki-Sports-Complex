# Implementation Plan: GIKI Sports Complex Management System

**Document Reference:** `docs/implementation-plan.md`  
**Plan Version:** 1.1.0 (Sequential Execution Plan)  
**Authoritative Baseline:** [docs/requirements-baseline.md](file:///d:/giki%20sports%20complex/docs/requirements-baseline.md)  
**Audit Reference:** [docs/current-state-audit.md](file:///d:/giki%20sports%20complex/docs/current-state-audit.md)  

---

## 1. Implementation Framework & Quality Constraints

This plan establishes a sequential, test-driven roadmap to construct the GIKI Sports Complex Management System.

### 1.1 Execution Responsibility & Historical Provenance
- **Current Implementation Lead:** The user is responsible for the entire project and will implement all milestones sequentially.
- **Historical Attribution:** Original academic reports for SE-423 and SE-431 list Abdullah Zia, Arman Wali, and Zohaib Malik as authors and outline historical lead rotations. That provenance is preserved for context; historical assignments and rotations do not control current execution.
- **Scope Discipline:** Sample facilities, timetables, and pricing present in prototype fixtures are developmental defaults, not institutionally approved university policies. Unresolved policies (exact pricing, ordinary cancellation refund deductions, official schedule matrices) remain open pending stakeholder confirmation.

### 1.2 Test-Driven Development (TDD) Protocol
In compliance with SE-423 Minimum Requirement 7:
1. **Red-Green-Refactor:** For every business rule, a failing test must be committed first (**Red**), followed by the minimal implementation to pass (**Green**), followed by clean refactoring while tests stay passing (**Refactor**).
2. **Commit History Preservation:** Incremental TDD commits must be preserved in feature branches using merge commits. Squash merges are strictly avoided where they would eliminate visible red-green-refactor history.
3. **Coverage Floor:** Core packages (`booking`, `wallet`, `membership`, `scheduling`, `event`) must achieve $\ge 60\%$ aggregate statement coverage prior to release (QR-10). Note: compilation success or empty test suites do not constitute business-rule verification.

### 1.3 Design Patterns Integration
The plan implements and verifies three mandatory design patterns (SE-423 Section 6):
1. **Strategy Pattern (Behavioral):** `EligibilityPolicy` interface (`CanAccess(user, window) bool`), realized by `StudentPolicy`, `FacultyPolicy`, and `TeamPolicy` for facility timetable access.
2. **Adapter Pattern (Structural):** `PaymentGateway` interface (`InitiateTopUp()`, `VerifyCallback()`), realized by `JazzCashAdapter` translating between external provider schemas and normalized internal records.
3. **Abstract Factory Pattern (Creational):** Realized at the checkout implementation stage (Phase 6), providing transaction-bound `BookingRepository` and `LedgerRepository` products from a shared `UnitOfWork` database transaction.

### 1.4 Continuous Integration (CI) and Static Analysis Gates
Automated checks on every push via GitHub Actions (SE-423 Table 1 No. 9, SE-431 QR-14):
- **Go Compilation & Vetting:** `go vet ./...` reports zero errors.
- **TypeScript Type Safety:** `npm run typecheck` (or `tsc -b`) reports zero errors.
- **Static Analyzer:** Pinned linter (`golangci-lint`) reports zero unresolved High/Critical findings.
- **Complexity Gate:** Core functions with cyclomatic complexity $> 10$ require peer-reviewed justification and branch tests.
- **Automated Test Suite:** All unit, integration, and contract tests must pass.

### 1.5 Traceability, Defect Tracking, and Cost of Quality (CoQ)
- **Requirements Traceability Matrix (RTM v1):** Maintained in version control. Each PR references its target FR/QR and links test cases (`TC-FR-*`, `TC-QR-*`).
- **Defect Register:** Maintained throughout implementation; all failed tests or production defects are assigned severity and tracked to verified closure.
- **CoQ Effort Ledger:** Logs person-hours across Prevention (20h budget), Appraisal (26h budget), Internal Failure (10h contingency), and External Failure (4h contingency).

### 1.6 AI Usage Logging
Every significant AI interaction is recorded with:
`[Entry ID, Date, Tool/Model, Purpose, Prompt Summary, Material Adopted, Modifications Made, Verification Performed]`.

---

## 2. Ordered Implementation Chunks (Sequential Execution)

*Note on Verification Commands: Commands referencing test files, migrations, or scripts that do not yet exist in the codebase are explicitly designated as **[Planned - not yet created]**.*

---

### Phase 0: Foundations & Continuous Integration

#### Chunk 0.1: CI Pipeline & PostgreSQL Development Container
- **Module:** Cross-cutting Infrastructure
- **Requirements Linked:** QR-10, QR-14
- **Dependencies:** None
- **Scope & Deliverables:**
  - Create `.github/workflows/ci.yml` running Go tests, `go vet`, and frontend type checks on every push and pull request.
  - Create `docker-compose.yml` defining an isolated PostgreSQL 17 service and persistent volumes for development and testing.
  - Pin tool versions in documentation (Go 1.26+, Node.js 20+, PostgreSQL 17).
- **Acceptance Criteria:**
  - Pushing a commit triggers the CI workflow and succeeds.
  - `docker compose up -d db` starts a healthy PostgreSQL instance.
- **Verification Commands:**
  - *Existing:*
    ```powershell
    go vet ./...
    cd frontend; npm run build
    ```
  - *Planned - not yet created:*
    ```powershell
    docker compose up -d db
    ```

---

### Phase 1: Database Schema & Foundational Persistence

#### Chunk 1.1: Core Database Migrations & Connection Pooling
- **Module:** Cross-cutting Persistence
- **Requirements Linked:** FR-01, FR-02, QR-13, QR-15
- **Dependencies:** Chunk 0.1
- **Scope & Deliverables:**
  - Set up migration framework (Goose or standard SQL migration runner).
  - Write foundational migrations: `users`, `sessions`, `role_assignments`, `facilities`, `schedules`, `audit_records`.
  - Configure `pgxpool.Pool` connection lifecycle and health check endpoint.
- **Acceptance Criteria:**
  - Forward and reverse migrations execute cleanly against a fresh PostgreSQL instance.
  - Connection pool connects and executes `SELECT 1` successfully.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/infrastructure/database/...
    ```

---

### Phase 2: User Authentication & Access Control (Module 1)

#### Chunk 2.1: Salted Argon2id Hashing & User Registration
- **Module:** User Authentication and Access Control (M1)
- **Requirements Linked:** FR-01, QR-13 (`TC-FR-01`, `TC-QR-13`)
- **Dependencies:** Chunk 1.1
- **Scope & Deliverables:**
  - Implement Argon2id password hashing and verification utility (unique salt per credential).
  - Create user repository and service for account creation with university email format validation.
  - Write TDD unit tests verifying hash generation, salt uniqueness, and rejection of plaintext passwords.
- **Acceptance Criteria:**
  - Two identical test passwords produce distinct hash strings. Plaintext password is never persisted.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/auth/hasher/...
    ```

#### Chunk 2.2: Stateful Server-Side Sessions & Role-Based Middleware
- **Module:** User Authentication and Access Control (M1)
- **Requirements Linked:** FR-01, QR-02, QR-13 (`TC-FR-01`, `TC-QR-02`, `TC-QR-13`)
- **Dependencies:** Chunk 2.1
- **Scope & Deliverables:**
  - Implement session creation upon successful login with cryptographic session tokens.
  - Implement server-side session expiration: 30 minutes idle timeout and 8 hours absolute lifetime.
  - Implement `POST /api/auth/logout` with immediate server-side session invalidation.
  - Implement RBAC middleware checking roles (`student`, `faculty`, `sports_director`, `super_admin`) and permissions (e.g. `cashier`).
- **Acceptance Criteria:**
  - Session older than 30 minutes idle is rejected with HTTP 401.
  - Session older than 8 hours absolute is rejected with HTTP 401.
  - Unauthorized role request returns HTTP 403.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/auth/session/...
    go test -v ./internal/auth/middleware/...
    ```

---

### Phase 3: Facilities, Timetables & Strategy Pattern (Module 2)

#### Chunk 3.1: Facilities Data Model & PostgreSQL Persistence
- **Module:** Facilities and Scheduling (M2)
- **Requirements Linked:** FR-02, QR-05 (`TC-FR-02`, `TC-QR-05`)
- **Dependencies:** Chunk 1.1
- **Scope & Deliverables:**
  - Create `Facility` domain entity, repository interface, and PostgreSQL repository implementation.
  - Populate PostgreSQL with facility specification records.
  - Implement `GET /api/facilities` and `GET /api/facilities/:id` reading directly from PostgreSQL.
- **Acceptance Criteria:**
  - API returns facility specifications matching PostgreSQL records.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/facility/...
    ```

#### Chunk 3.2: Schedule Engine & Strategy Pattern (EligibilityPolicy)
- **Module:** Facilities and Scheduling (M2)
- **Requirements Linked:** FR-02, QR-05, SE-423 Section 6.2 (`TC-FR-02`, `TC-QR-05`)
- **Dependencies:** Chunk 3.1
- **Scope & Deliverables:**
  - Define `EligibilityPolicy` interface: `CanAccess(user *User, window *TimeWindow) bool`.
  - Implement concrete strategies: `StudentPolicy`, `FacultyPolicy`, and `TeamPolicy`.
  - Implement `ScheduleService` checking mandatory closures first, followed by the registered policy strategy.
  - TDD tests verifying access grant/denial for each user category and time slot.
- **Acceptance Criteria:**
  - New policy can be added without modifying the core scheduling algorithm (OCP).
  - Mandatory facility closures reject all requests regardless of user policy.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/scheduling/policy/...
    ```

---

### Phase 4: Smallest Vertical Slice Milestone

#### Chunk 4.1: Admin Schedule Update & Visitor Display (End-to-End Vertical Slice)
- **Module:** Facilities & Scheduling (M2) + Auth (M1) + Frontend
- **Requirements Linked:** FR-01, FR-02, QR-02, QR-05, QR-11 (`TC-FR-01`, `TC-FR-02`, `TC-QR-05`)
- **Dependencies:** Chunks 2.2, 3.1, 3.2
- **Scope & Deliverables:**
  - Implement authenticated admin schedule update endpoint: `PUT /api/facilities/:id/schedule` (restricted to `sports_director` and `super_admin`).
  - Align frontend `types.ts` and `api.ts` so `Facility` and `ScheduleEntry` match the backend PostgreSQL response format.
  - Update `FacilityDetail.tsx` to render live weekly schedules retrieved from PostgreSQL.
  - Build minimal schedule editor for authenticated administrators.
- **Acceptance Criteria:**
  - An unauthenticated request to update a schedule returns HTTP 401.
  - A non-admin user receives HTTP 403.
  - An authorized administrator successfully submits a modified schedule, persisting it to PostgreSQL.
  - An anonymous visitor navigating to `http://localhost:5173/facilities/:slug` immediately sees the updated schedule rendered on the page without application crashes.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/facility/api_test.go
    ```
  - *Existing:*
    ```powershell
    cd frontend; npm run build
    ```

---

### Phase 5: Digital Wallet & Payment Adapter (Module 5)

#### Chunk 5.1: Double-Entry Ledger & Balance Derivation
- **Module:** Digital Wallet and Payments (M5)
- **Requirements Linked:** FR-05, QR-03 (`TC-FR-05`, `TC-QR-03`)
- **Dependencies:** Chunk 1.1
- **Scope & Deliverables:**
  - Adapt ledger tables (`wallets`, `ledger_entries`) from `giki-wallet`.
  - Implement `Wallet` entity and `LedgerEntry` append-only operations.
  - Derive wallet balance mathematically as $\sum \text{Credits} - \sum \text{Debits}$.
  - Enforce concurrency safety via sorted UUID row locking (`SELECT ... FOR UPDATE`) to prevent deadlocks.
- **Acceptance Criteria:**
  - Balance query matches exact sum of ledger entries.
  - Direct ledger mutations or negative debits are rejected.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/wallet/ledger/...
    ```

#### Chunk 5.2: Cashier Top-Up & Idempotent Cash Handling
- **Module:** Digital Wallet and Payments (M5)
- **Requirements Linked:** FR-05, QR-02 (`TC-FR-05`, `TC-QR-02`)
- **Dependencies:** Chunk 5.1, Chunk 2.2
- **Scope & Deliverables:**
  - Implement `POST /api/wallet/top-up/cash` restricted to users with `cashier` permission.
  - Record credit in user wallet and corresponding debit in `SYS_LIABILITY` wallet.
  - Require cashier receipt reference for tracking.
- **Acceptance Criteria:**
  - Non-cashier users receive HTTP 403 on cash top-up attempts.
  - Cash top-up immediately reflects in derived wallet balance.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/wallet/cashier_test.go
    ```

#### Chunk 5.3: JazzCash Adapter (Adapter Pattern) & Idempotent Webhooks
- **Module:** Digital Wallet and Payments (M5)
- **Requirements Linked:** FR-05, QR-04, QR-12, SE-423 Section 6.3 (`TC-FR-05`, `TC-QR-04`, `TC-QR-12`)
- **Dependencies:** Chunk 5.1
- **Scope & Deliverables:**
  - Define `PaymentGateway` interface (`InitiateTopUp()`, `VerifyCallback()`).
  - Implement `JazzCashAdapter` adapting provider requests/responses.
  - Implement webhook signature verification with HMAC-SHA256 salt.
  - Store payment reference with unique constraints to ensure idempotency.
- **Acceptance Criteria:**
  - Submitting an identical verified payment reference 20 times produces exactly one credit (QR-04).
  - Malformed or forged signatures produce zero credits and are rejected.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/payment/gateway/...
    ```

---

### Phase 6: Padel Court Booking Engine, Concurrency & Abstract Factory (Module 3) — Completed (Steps 12A–12I)

*Status: **Fully Implemented & Verified***  
*Design Reference: [`docs/padel-booking-design.md`](file:///d:/giki%20sports%20complex/docs/padel-booking-design.md)*  
*Source Code: [`backend/internal/padel/`](file:///d:/giki%20sports%20complex/backend/internal/padel/) & [`frontend/src/pages/PadelBooking.tsx`](file:///d:/giki%20sports%20complex/frontend/src/pages/PadelBooking.tsx)*

#### Step 12A: Architecture & Technical Design Document
- **Deliverable:** `docs/padel-booking-design.md` detailing domain lifecycle, concurrency locking, Abstract Factory pattern, double-entry wallet atomicity, and approved product parameters (60-min default slot duration, admin dynamic pricing, 100% full refund on cancellation).
- **Status:** **Complete**

#### Step 12B: Relational Database Schema & Migrations
- **Deliverable:** Migration `backend/migrations/00007_create_padel_booking_tables.sql` defining `giki_sports.padel_slots`, `giki_sports.padel_bookings`, partial unique index `uq_active_slot_booking`, and idempotency constraints.
- **Verification:** Forward and rollback migration tests in disposable PostgreSQL container (`backend/internal/database/migration_integration_test.go`).
- **Status:** **Complete**

#### Step 12C: Slot Inventory Engine & Availability Read API
- **Deliverable:** `GET /api/padel/slots?date=YYYY-MM-DD` and `GET /api/padel/facilities`. Discrete 60-minute slot matrix generator with Pakistan timezone (PKT) wall-clock formatting and lazy hold expiration evaluation.
- **Verification:** Unit tests in `service_test.go` and integration tests in `repository_integration_test.go`.
- **Status:** **Complete**

#### Step 12D: 5-Minute Hold State Machine (FR-03, QR-01)
- **Deliverable:** `POST /api/padel/slots/:id/hold` and `POST /api/padel/slots/:id/release-hold`. Concurrency-safe slot reservation enforcing `SELECT ... FOR UPDATE` row locks, 5-minute strict timeout, and conflict rejection.
- **Verification:** Concurrency integration tests in `repository_integration_test.go` verifying 2 competing users on 1 slot.
- **Status:** **Complete**

#### Step 12E: Resilient Background Hold Cleanup Worker (SE-423 §2 Table 1 No. 4)
- **Deliverable:** `HoldCleanerWorker` in `backend/internal/padel/worker.go` with periodic ticker and graceful shutdown releasing abandoned held slots where `hold_expires_at <= now()`.
- **Verification:** Unit tests in `worker_test.go` and integration tests in `worker_integration_test.go`.
- **Status:** **Complete**

#### Step 12F: Abstract Factory Pattern & Atomic Checkout (FR-03, QR-01, QR-03, QR-04, SE-423 §6.1)
- **Deliverable:** Creational Abstract Factory (`TransactionRepositoryFactory`) with `Bookings()` and `Ledger()` family of repositories, `UnitOfWork` transaction boundary, and `POST /api/padel/checkout`.
- **Verification:**
  - 50 concurrent contenders for 1 slot producing exactly 1 confirmed booking and 49 conflict rejections with 0 unwanted debits (`TestCheckout_Concurrency_50Contenders_Integration`).
  - Transaction failure injection before commit leaving 0 bookings and 0 partial debits (`TestCheckout_AtomicRollback_FailureInjection_Integration`).
  - 20 sequential idempotency replays returning identical confirmation without duplicate debits (`TestCheckout_IdempotencyReplay_Integration`).
- **Status:** **Complete**

#### Step 12G: Attendant Ticket Check-In Verification API (FR-03, TC-FR-03-03)
- **Deliverable:** `POST /api/padel/bookings/verify-ticket` restricted to `sports_director` and `super_admin`. Transitions booking from `CONFIRMED` to `CHECKED_IN`, saves attendant UUID/timestamp, records audit log, and serializes gate scanners with row-level locks.
- **Verification:** Integration tests in `ticket_integration_test.go` verifying happy path, re-check conflict, and role authorization rejection for students (`403 Forbidden`).
- **Status:** **Complete**

#### Step 12H: Administrative Cancellation & 100% Wallet Ledger Refund (FR-06, TC-FR-06-01, TC-FR-06-02)
- **Deliverable:** `POST /api/admin/bookings/:id/cancel` and `POST /api/padel/bookings/:id/cancel`. Rejects student self-cancellation attempts with HTTP 403. Releases slot back to `AVAILABLE` and credits 100% of paid fee back to user wallet ledger via atomic `UnitOfWork` double-entry transfer.
- **Verification:** Integration tests in `cancellation_integration_test.go` verifying happy path 100% refund, single-refund invariant, and role authorization.
- **Status:** **Complete**

#### Step 12I: Frontend Padel Booking Client Interface (QR-08, QR-09, QR-11)
- **Deliverable:** React/Vite interface in `frontend/src/pages/PadelBooking.tsx` mounted at `/padel`:
  - Interactive court and date matrix with availability badges.
  - Real-time 5-minute hold countdown banner.
  - Accessible wallet checkout modal with BigInt paisa balance check, zero keyboard traps, and Escape dismissal.
  - Digital entrance ticket confirmation with 4-digit code.
  - Attendant gate check-in tool and admin cancellation tool.
- **Verification:** Vitest component tests in `frontend/src/test/PadelBooking.test.tsx` and production build (`tsc -b && vite build`).
- **Status:** **Complete**

#### Verification Commands (Phase 6 / Steps 12A–12I)
```powershell
# Backend Unit Tests
cd backend; go test -v ./internal/padel/...

# Backend Integration Tests (Real PostgreSQL container on port 5434)
cd backend; go test -v -tags=integration ./internal/padel/...

# Frontend Tests
cd frontend; npx vitest run src/test/PadelBooking.test.tsx

# Frontend Production Build
cd frontend; npm run build
```

---

### Phase 7: Gym Membership Management (Module 4) — Completed

*Status: **Fully Implemented & Verified***  
*Source Code: [`backend/internal/membership/`](file:///d:/giki%20sports%20complex/backend/internal/membership/) & [`frontend/src/pages/Membership.tsx`](file:///d:/giki%20sports%20complex/frontend/src/pages/Membership.tsx)*  
*Database Migration: [`backend/migrations/00008_create_gym_memberships_tables.sql`](file:///d:/giki%20sports%20complex/backend/migrations/00008_create_gym_memberships_tables.sql)*

#### Chunk 7.1: 30-Day Pass Validity Engine & Controlled Clock Tests
- **Module:** Gym Membership Management (M4)
- **Requirements Linked:** FR-04, QR-06 (`TC-FR-04`, `TC-QR-06`), CR-06
- **Deliverables:**
  - Database table `giki_sports.gym_memberships` with period check constraints, price check constraints, user-scoped idempotency unique constraint, and relational foreign keys with `ON DELETE RESTRICT`.
  - Pure domain validity engine in `backend/internal/membership/validity.go` enforcing the half-open interval $[T_{\text{start}}, T_{\text{start}} + 30\text{ days})$ (QR-06).
  - Controlled clock interface `Clock` with `SystemClock` and `ControlledClock` implementations for exact-second validity testing.
  - Continuous renewal mathematics: $\max(T_{\text{existing\_expiry}}, T_{\text{renewal}}) + 30\text{ days}$. Early renewal creates contiguous coverage without gap or penalty.
- **Verification:** Unit tests in `backend/internal/membership/validity_test.go` and schema lifecycle tests in `backend/internal/database/migration_integration_test.go`.
- **Status:** **Complete**

#### Chunk 7.2: Membership Purchase via Wallet Debit
- **Module:** Gym Membership Management (M4) + Digital Wallet (M5)
- **Requirements Linked:** FR-04, QR-03, QR-04, QR-06, CR-06
- **Deliverables:**
  - Atomic double-entry wallet debit in `backend/internal/membership/service.go`: debits user personal wallet (`PERSONAL`), credits System Revenue (`SYS_MEMBERSHIP_REVENUE`), records `type: "GYM_MEMBERSHIP"`, and writes an immutable audit log entry in `giki_sports.audit_logs`.
  - Transaction rollback: insufficient user balance halts activation; 0 passes and 0 ledger entries created.
  - Replay protection: user-scoped idempotency key returns the existing pass without duplicate debits (QR-04).
  - REST endpoints mounted on Fiber API in `backend/internal/membership/handler.go`:
    - `GET /api/memberships/me`: Authenticated user's active pass status, days remaining, and history.
    - `POST /api/memberships/purchase`: Authenticated pass purchase/renewal via wallet debit.
    - `POST /api/memberships`: Backward-compatible alias.
    - `GET /api/admin/memberships`: Staff-restricted pass queries.
- **Verification:** Integration tests against real PostgreSQL in `backend/internal/membership/purchase_integration_test.go`.
- **Status:** **Complete**

#### Chunk 7.3: Frontend Gym Membership Client Interface
- **Module:** Frontend Client (React 19 / TypeScript / Vite)
- **Requirements Linked:** FR-04, QR-06, QR-08, QR-11, CR-06
- **Deliverables:**
  - Dedicated page in `frontend/src/pages/Membership.tsx` mounted at `/membership` with navigation links in `Navbar.tsx`.
  - Live active pass countdown card (`X Days Left`, expiration date/time, and active/inactive status pills).
  - Wallet balance integration with integer paisa comparison against pass cost (PKR 3,000.00 / 300,000 paisa).
  - Confirmation checkout modal with insufficient funds warning and top-up link.
  - Complete historical pass ledger table with past terms and transaction references.
- **Verification:** Vitest component tests in `frontend/src/test/Membership.test.tsx` (5/5 tests passing) and production build (`tsc -b && vite build`).
- **Status:** **Complete**

#### Verification Commands (Phase 7)
```powershell
# Backend Unit Tests (Validity engine & ControlledClock)
cd backend; go test -v ./internal/membership/...

# Backend Integration Tests (Real PostgreSQL container on port 5434)
cd backend; go test -v -tags=integration ./internal/membership/...

# Database Migration 8 Lifecycle Test
cd backend; go test -v -tags=integration -run TestMigrationIntegration_GymMembershipLifecycle ./internal/database

# Frontend Component Tests
cd frontend; npx vitest run src/test/Membership.test.tsx

# Frontend Production Build
cd frontend; npm run build
```

---

### Phase 8: Announcements & Sports Achievements (Module 6)

#### Chunk 8.1: Draft-to-Published State Machine & Public Feed Filtering
- **Module:** Announcements and Sports Achievements (M6)
- **Requirements Linked:** FR-07 (`TC-FR-07`)
- **Dependencies:** Chunk 1.1, Chunk 2.2
- **Scope & Deliverables:**
  - Create `announcements` and `achievements` PostgreSQL tables with status column (`draft`, `published`).
  - Implement validation requiring non-empty title and content prior to publication.
  - Implement public read endpoints returning only `published` items.
  - Implement admin creation, editing, and publishing endpoints restricted to authorized staff.
- **Acceptance Criteria:**
  - Unauthenticated visitor cannot see `draft` announcements or achievements.
  - Attempting to publish without title or body returns HTTP 400.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/announcement/...
    go test -v ./internal/achievement/...
    ```

---

### Phase 9: Event Management & Clash Resolution (Module 7)

#### Chunk 9.1: Event Reservations & Atomic Clash Refund Transaction
- **Module:** Event Management (M7) + Facilities (M2) + Booking (M3) + Wallet (M5)
- **Requirements Linked:** FR-08, QR-05 (`TC-FR-08`, `TC-QR-05`)
- **Dependencies:** Chunks 3.1, 6.3, 6.5
- **Scope & Deliverables:**
  - Implement event creation and facility blockout reservation.
  - Query for any active Padel bookings overlapping the event time window.
  - Atomically cancel all conflicting bookings, issue corresponding wallet refunds, and persist event blockout inside a single database transaction.
  - If any refund or update fails, abort the entire transaction.
- **Acceptance Criteria:**
  - Event blockout cancels all overlapping bookings and refunds affected users.
  - Injected refund failure leaves zero partial blockouts and keeps existing bookings intact.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/event/clash_test.go
    ```

---

### Phase 10: Administrative Audit Trail (FR-09)

#### Chunk 10.1: Immutable Audit Trail Middleware & Interceptor
- **Module:** Cross-cutting Audit
- **Requirements Linked:** FR-09, QR-02 (`TC-FR-09`, `TC-QR-02`)
- **Dependencies:** Chunks 1.1, 2.2
- **Scope & Deliverables:**
  - Adapt `audit_logs` service from `giki-wallet/backend/internal/audit`.
  - Create interceptor capturing `(actor_id, action, target_entity, timestamp, outcome)` across all administrative handlers (schedules, top-ups, cancellations, event reservations, user role edits).
  - Explicitly sanitize payloads to ensure passwords, tokens, and secrets are excluded.
- **Acceptance Criteria:**
  - Every administrative mutation inserts an immutable audit log record.
  - No secret tokens or credentials appear in audit records.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v ./internal/audit/...
    ```

---

### Phase 11: Frontend Realignment & Quality Verification

#### Chunk 11.1: Frontend Contract Harmonization & Keyboard Accessibility
- **Module:** Frontend Client
- **Requirements Linked:** QR-08, QR-09, QR-11 (`TC-QR-08`, `TC-QR-09`, `TC-QR-11`)
- **Dependencies:** All previous chunks
- **Scope & Deliverables:**
  - Harmonize TypeScript interfaces with backend REST contracts.
  - Fix `FacilityCard.tsx` and `FacilityDetail.tsx` icon resolution to eliminate crash risks.
  - Add user login, wallet balance, and booking management views.
  - Audit keyboard navigation across all interactive elements (zero keyboard traps).
  - Verify responsive layouts at 390px and 1366px viewports in Chrome, Firefox, and Safari.
- **Acceptance Criteria:**
  - TypeScript build succeeds with 0 errors.
  - Core user booking flow completes within 3 minutes by representative test users.
  - Viewports render without horizontal scrolling or broken controls.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    cd frontend; npm run test
    ```
  - *Existing:*
    ```powershell
    cd frontend; npm run build
    ```

#### Chunk 11.2: Concurrency, Performance & Backup Recovery Drill
- **Module:** System-Wide Verification
- **Requirements Linked:** QR-01, QR-07, QR-15 (`TC-QR-01`, `TC-QR-07`, `TC-QR-15`)
- **Dependencies:** All previous chunks
- **Scope & Deliverables:**
  - Execute automated concurrency test: 50 concurrent booking attempts $\times$ 100 trials across $\ge 2$ backend processes (QR-01).
  - Run synthetic load test (100 concurrent users for 10 min): measure p95 latency $\le 2\text{s}$ for reads and $\le 3\text{s}$ for checkouts (QR-07).
  - Perform disaster recovery drill: restore daily PostgreSQL backup in isolated staging DB within 30 minutes, reconciling all balances and bookings (QR-15).
- **Acceptance Criteria:**
  - Concurrency test produces zero double bookings and zero erroneous debits.
  - Load test meets p95 latency and $<1\%$ error rate thresholds.
  - Restored database passes 100% data reconciliation.
- **Verification Commands:**
  - *Planned - not yet created:*
    ```powershell
    go test -v -tags=concurrency ./tests/concurrency/...
    go test -v -tags=load ./tests/performance/...
    ./scripts/restore-dr-drill.ps1
    ```

---

## 3. The Smallest Implementation Milestone

To establish immediate vertical traceability and de-risk the architectural shift from static JSON to relational PostgreSQL, the implementation begins with this minimal end-to-end slice before booking, payment, or complex domain features are built:

### Milestone Scope: Authorized Administrator Facility Schedule Update in PostgreSQL & Visitor Live Display

#### 1. Objective
Enable an authenticated administrator with the `sports_director` or `super_admin` role to update a facility's schedule in PostgreSQL, and allow an anonymous public visitor to see that updated schedule live on the web client.

#### 2. Components Involved
- **PostgreSQL Database:** Running locally via Docker Compose, containing tables `facilities`, `schedules`, `users`, and `sessions`.
- **Backend Service (Go):**
  - Session verification middleware enforcing authenticated administrator access.
  - `PUT /api/facilities/:id/schedule` accepting updated timetable entries, validating time windows, and saving to PostgreSQL.
  - `GET /api/facilities` and `GET /api/facilities/:id` reading current facility specifications and schedules from PostgreSQL.
- **Frontend Client (React/TypeScript):**
  - Updated `types.ts` and `api.ts` harmonizing the facility and schedule contracts.
  - `FacilityDetail.tsx` displaying the live weekly schedule from PostgreSQL.
  - Simple administrator schedule editing interface.

#### 3. Execution Sequence & Acceptance Criteria
1. **Database Setup:** Initialize PostgreSQL schema with `facilities` and `schedules` tables.
2. **Admin Authentication:** Seed an administrator account (`sports_director`). Admin logs in, receives a valid session token.
3. **Admin Mutation:** Admin submits a schedule update to `PUT /api/facilities/:id/schedule`.
   - *Security Check:* An unauthenticated request is rejected with HTTP 401. A standard student account is rejected with HTTP 403.
   - *Persistence Check:* The update commits to PostgreSQL.
4. **Visitor Verification:** An anonymous user visits `http://localhost:5173/facilities/:slug`.
   - The browser fetches live data from `GET /api/facilities/:slug`.
   - The updated schedule renders visibly on the page.
   - Zero console errors or unhandled exceptions occur.

#### 4. Verification Commands for the Smallest Milestone
- *Planned - not yet created:*
  ```powershell
  docker compose up -d db
  go run ./cmd/migrate up
  go test -v ./internal/facility/api_schedule_test.go
  ```
- *Existing:*
  ```powershell
  cd frontend
  npm run build
  ```
