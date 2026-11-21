# Requirements Baseline: GIKI Sports Complex Management System

**Document Reference:** `docs/requirements-baseline.md`  
**Baseline Version:** 1.1.0 (Sequential Execution Baseline)  
**Authoritative Sources:** 
- `SE-423 — Software Construction and Development_Milestone_1.pdf` (Version 1.0, 10 Oct 2026, Lead: Zohaib Malik)
- `SE-431 — Software Quality Assurance_Milestone_1.pdf` (Version 1.0, 10 Oct 2026, Lead: Arman Wali)

---

## 1. Executive Summary & Project Execution Authority

This document establishes the formal requirements baseline for the **GIKI Sports Complex Management System**.

### 1.1 Project Ownership & Execution Model
- **Current Implementation Responsibility:** The user is solely responsible for the end-to-end implementation of the system and will execute all phases sequentially. 
- **Historical Provenance & Attribution:** The original academic course submissions for SE-423 and SE-431 list Abdullah Zia, Arman Wali, and Zohaib Malik as authors, along with historical lead rotations. That attribution is preserved solely for provenance and context; historical team assignments and lead rotations do not control or govern current implementation work.
- **Precedence of Requirements:** The October 2026 course milestone specifications serve as the authoritative baseline for functional and quality targets. Prototype code ([backend/main.go](file:///d:/giki%20sports%20complex/backend/main.go)), early draft designs ([GIKI_SPORTS_COMPLEX_BACKEND_DESIGN.md](file:///d:/giki%20sports%20complex/backend/GIKI_SPORTS_COMPLEX_BACKEND_DESIGN.md)), and promotional documentation ([README.md](file:///d:/giki%20sports%20complex/README.md)) are treated strictly as historical references.

---

## 2. Seven Functional Modules

The system is decomposed into seven functional domain modules:

1. **User Authentication and Access Control (M1):** University user accounts, credential hashing, session lifetime management, and role-based access control (RBAC).
2. **Facilities and Scheduling (M2):** Facility specification records, recurring timetable rules, maintenance closures, calendar blocks, and user-group access validation.
3. **Padel Court Booking (M3):** Temporary slot hold management, concurrency protection, check-in ticket verification, and authorized administrative cancellation.
4. **Gym Membership Management (M4):** Membership plans, purchase and renewal rules, 30-day validity tracking, and payment-linked activation.
5. **Digital Wallet and Payments (M5):** Append-only double-entry financial ledger, cashier cash credits, verified payment gateway credits, service debits, refunds, and derived balances.
6. **Announcements and Sports Achievements (M6):** Curated editorial lifecycle (draft-to-published) for campus sports notices and match victories, mandatory field validation, and public visibility filters.
7. **Event Management (M7):** Campus athletic event reservations, facility blockouts, and atomic detection/cancellation/refunding of conflicting slot bookings.

---

## 3. Requirements Specification: Functional & Quality

### 3.1 Functional Requirements (FR-01 to FR-09)

| Req ID | Requirement Summary | Target Module | Verification Status | Implementation & Test Files |
|---|---|---|:---:|---|
| **FR-01** | **Authenticate and Restrict Access:** Authenticate university users using salted Argon2id hashes and restrict protected operations according to user role and private record ownership. Enforce session expiration. | User Authentication & Access Control | Verified | `backend/internal/authentication/` |
| **FR-02** | **Publish Schedules and Enforce Restrictions:** Publish facility timetables, rules, and recurring hours; enforce user-group eligibility windows, emergency closures, and shared-space restrictions. | Facilities & Scheduling | Verified | `backend/internal/facility/` |
| **FR-03** | **Padel Court Booking Lifecycle:** Provide temporary 5-minute slot holds, prevent conflicting holds, confirm eligible funded bookings with wallet debit, and verify booking tickets upon check-in. | Padel Court Booking | **Verified (Step 12A–12I)** | `backend/internal/padel/checkout_integration_test.go`, `ticket_integration_test.go`, `frontend/src/test/PadelBooking.test.tsx` |
| **FR-04** | **30-Day Gym Membership Purchases & Renewals:** Enable purchase and renewal of 30-day gym passes; activate or extend membership validity strictly upon successful payment. | Gym Membership Management | Planned (Phase 7) | `TC-FR-04` |
| **FR-05** | **Ledger-Based Digital Wallet Operations:** Record cashier cash credits, verified gateway credits, and service debits; maintain an immutable append-only transaction ledger; calculate balances dynamically from ledger records. | Digital Wallet & Payments | Verified | `backend/internal/wallet/`, `frontend/src/test/Wallet.test.tsx` |
| **FR-06** | **Authorized Booking Cancellation & Single Refund:** Permit authorized administrators to cancel confirmed Padel bookings and issue the applicable refund to the user's wallet once; reject user-initiated cancellations. | Padel Court Booking; Digital Wallet | **Verified (Step 12H–12I)** | `backend/internal/padel/cancellation_integration_test.go`, `frontend/src/test/PadelBooking.test.tsx` |
| **FR-07** | **Curated Announcements and Achievements:** Enable authorized staff to draft, edit, and publish campus sports notices and match achievements; enforce mandatory title/content; expose only published records to the public. | Announcements & Achievements | Verified | `backend/internal/content/`, `frontend/src/test/AdminContent.test.tsx` |
| **FR-08** | **Event Reservations & Conflict Resolution:** Reserve sports facilities for university events; automatically detect and resolve conflicting individual bookings (with refunds) before committing the event blockout. | Event Management; Facilities; Booking | Planned (Phase 8) | `TC-FR-08` |
| **FR-09** | **Administrative Audit Trail:** Maintain an immutable audit log capturing actor, action, target entity, timestamp, and outcome for all administrative operations across all modules. | All modules with Admin ops | Verified | `giki_sports.audit_logs`, `backend/internal/padel/unit_of_work.go` |

### 3.2 Quality Requirements (QR-01 to QR-15) — ISO/IEC 25010:2023

| QR ID | ISO 25010 Characteristic | Requirement Specification | Measurable Acceptance Target | Planned Test ID |
|---|---|---|---|:---:|
| **QR-01** | **Reliability** | Concurrency safety in Padel bookings | In each of 100 trials, 50 simultaneous booking attempts for a single slot produce at most 1 confirmed booking; exactly 1 succeeds if contenders are eligible/funded. Rejected attempts incur zero wallet debit. Tested against PostgreSQL with $\ge 2$ backend processes. | `TC-QR-01` (Verified in Step 12F: `TestCheckout_Concurrency_50Contenders_Integration`) |
| **QR-02** | **Security** | Access control & private record isolation | 100% of unauthorized requests in the role-and-permission matrix are rejected without state alteration or info disclosure. Covers direct API parameter tampering and horizontal privilege escalation. | `TC-QR-02` (Verified) |
| **QR-03** | **Functional Suitability** | Correct pricing & atomic debit | Confirmed charge equals independently calculated fee from approved pricing rules. Receipt matches ledger debit. If failure is injected before commit, both booking and debit roll back completely. Balance equals sum of credits minus debits. | `TC-QR-03` (Verified in Step 12F: `TestCheckout_AtomicRollback_FailureInjection_Integration`) |
| **QR-04** | **Reliability** | Idempotency of checkouts & top-ups | Submitting an identical user-scoped idempotency key 20 times produces exactly 1 booking and 1 charge; reuse with modified payload is rejected. Replaying 1 verified payment reference 20 times produces exactly 1 wallet credit. Forged notifications produce 0 credits. | `TC-QR-04` (Verified in Step 12F: `TestCheckout_IdempotencyReplay_Integration`) |
| **QR-05** | **Functional Suitability** | Schedule rule & closure enforcement | All cases in schedule decision table match expected availability. Boundary conditions and overlapping events correctly evaluated. Checkouts submitted from stale client pages after a closure is committed must be rejected. | `TC-QR-05` (Verified) |
| **QR-06** | **Functional Suitability** | Membership validity & renewal math | Passes valid from start instant up to, but excluding, end instant 30 days later ($[T_{start}, T_{start} + 30\text{d})$). Renewal adds 30 days from $\max(T_{expiry}, T_{renewal})$. Payment failure leaves validity unchanged. | `TC-QR-06` |
| **QR-07** | **Performance Efficiency** | Response latency under concurrent load | Under synthetic load (100 concurrent users, 10 min, 1,000 users, 10,000 historical bookings, 70/20/10 read/hold/checkout mix): p95 latency $\le 2\text{s}$ for reads, $\le 3\text{s}$ for holds/checkouts; unexpected server errors $< 1\%$. | `TC-QR-07` |
| **QR-08** | **Interaction Capability** | First-time user booking efficiency | $\ge 4$ of 5 representative campus users complete an eligible funded Padel booking within 3 minutes without assistance, starting from logged-in home page. | `TC-QR-08` (Verified in Step 12I: `frontend/src/pages/PadelBooking.tsx`) |
| **QR-09** | **Interaction Capability** | Keyboard accessibility & error clarity | Zero keyboard traps in login, schedule filtering, slot booking, and membership purchase. 100% of validation failures display explanatory text with specific corrective actions. | `TC-QR-09` (Verified in Step 12I: `frontend/src/test/PadelBooking.test.tsx`) |
| **QR-10** | **Maintainability** | Automated test regression & coverage | Core business logic packages (`booking`, `wallet`, `membership`, `scheduling`, `event`) achieve $\ge 60\%$ aggregate statement coverage in CI. All critical business tests pass on every push. | `TC-QR-10` |
| **QR-11** | **Compatibility** | Cross-browser & viewport responsiveness | Workflows pass in Chrome, Firefox, Safari at 390px (mobile) and 1366px (desktop) viewport widths with no horizontal scroll or overlapping interactive controls. | `TC-QR-11` (Verified in Step 12I: responsive Tailwind UI) |
| **QR-12** | **Compatibility** | Payment gateway contract compliance | Payment adapter contract tests verify success, rejection, timeout, duplicate reference, and malformed payload mappings. Unverified responses remain uncredited. | `TC-QR-12` |
| **QR-13** | **Security** | Credential, session & input hygiene | Passwords hashed with salted Argon2id. Sessions expire after 30 minutes idle or 8 hours absolute age; immediate destruction on logout. SQL injection and XSS fixtures show zero vulnerability. | `TC-QR-13` |
| **QR-14** | **Maintainability** | Static analysis & complexity thresholds | `go vet` and TypeScript type check pass with zero errors. Pinned static analyzer reports zero unresolved High/Critical findings under documented severity mapping. Core functions with cyclomatic complexity $> 10$ require peer-reviewed rationale and branch tests. | `TC-QR-14` |
| **QR-15** | **Reliability** | Database backup restoration & verification | Restore daily backup into isolated staging DB within 30 minutes. Restored ledger balances, active booking uniqueness, and membership dates reconcile 100% with snapshot. | `TC-QR-15` |

---

## 4. Separation of Baseline Elements

To avoid conflating formal baseline rules with provisional developmental data, elements are categorized into four distinct categories:

### 4.1 Confirmed Business Rules (Authoritative)
1. **Padel-Only Booking Scope:** Online advance slot reservations are strictly limited to Padel court facilities. Other sports facilities operate under published schedules, walk-in queues, or gym passes.
2. **Hold Expiry Invariant:** A slot hold is valid for up to 5 minutes. A hold is strictly considered **expired when `now >= expiresAt`**. Only the active hold owner can confirm checkout before this expiry threshold.
3. **Double-Booking Invariant:** At most one active confirmed booking per slot ID and time window may exist simultaneously in PostgreSQL, guarded by unique constraints and row locks.
4. **Derived Wallet Balances:** Digital wallet balances are derived dynamically from an append-only double-entry ledger ($\sum \text{Credits} - \sum \text{Debits}$). Balances are never updated in place.
5. **Gym Membership Validity Calculation:** Gym passes span exactly 30 days ($[T_{start}, T_{start} + 30\text{d})$). Renewal adds 30 days to $\max(T_{expiry}, T_{renewal})$. Activation requires verified payment debit.
6. **Administrative Cancellation Exclusivity:** Standard users cannot initiate self-service cancellations of confirmed Padel bookings. Cancellations must be performed by authorized administrators.
7. **Single Cancellation Refund:** An administrative booking cancellation triggers at most one refund credit to the user's wallet ledger with a reference linking the cancellation.
8. **Editorial Draft States:** Announcements and achievements originate as `DRAFT` and require mandatory title and body before transitioning to `PUBLISHED`. Visitors only see `PUBLISHED` content.
9. **Atomic Event Blockout:** Creating an event blockout that conflicts with existing bookings must atomically cancel and refund those bookings. Any failure aborts the entire blockout.
10. **Sanitized Audit Trail:** Administrative mutations record `(actor, action, target, timestamp, outcome)` without logging credentials, tokens, or plaintext secrets.
11. **Credential & Session Security:** Salted Argon2id credential hashing; server-side sessions expiring after 30 minutes idle or 8 hours absolute age; immediate invalidation upon logout.

### 4.2 Implementation Choices (Architecture & Technical Decisions)
- **Modular Monolith in Go:** Domain-isolated packages communicating via Go interfaces.
- **Relational Storage:** PostgreSQL 17 with relational constraints, row locking (`SELECT ... FOR UPDATE`), and transactional migrations.
- **Design Patterns (SE-423):**
  - *Strategy Pattern (Behavioral):* `EligibilityPolicy` interface (`CanAccess(user, window) bool`) for user-group timetable rules.
  - *Adapter Pattern (Structural):* `PaymentGateway` interface (`InitiateTopUp()`, `VerifyCallback()`) adapting external provider payloads.
  - *Abstract Factory (Creational):* Coordinated repository creation for transactional workflows, deferred to the checkout implementation stage.
- **Frontend Architecture:** React 19 / TypeScript / Vite client consuming typed REST API contracts.

### 4.3 Sample Data (Provisional Test Fixtures — NOT Institutionally Approved)
The following items present in current prototypes or seed data are **purely illustrative sample fixtures** and must not be cited as approved university policies:
- **Sample Facilities List:** The 8 or 9 specific sports facilities (e.g. Glass Padel Arena, Badminton Championship Hall, Olympic Pool) seeded in [store.json](file:///d:/giki%20sports%20complex/backend/data/store.json) and [facilities.ts](file:///d:/giki%20sports%20complex/frontend/src/data/facilities.ts).
- **Sample Timetables & Schedules:** The student timings, faculty hours, and slot increments in prototype JSON.
- **Sample Email Domains & Identifiers:** Formats such as `@giki.edu.pk` or student IDs like `2023-CS-104` used in mocks.
- **Sample Pricing & Fees:** Hourly slot fees, membership fees, or top-up amounts present in test fixtures.

### 4.4 Unresolved Policy Questions (No Invented Answers)
The following items remain open institutional decisions requiring stakeholder clarification:
1. **Padel Pricing Schedule:** Approved monetary amounts for Padel court bookings, including peak vs. off-peak rates and student vs. faculty pricing.
2. **Gym Membership Price:** Official fee for the 30-day gym membership pass.
3. **Ordinary Cancellation Refund Policy:** What exact refund amount or percentage applies when a booking is cancelled? Does an administrative fee or cancellation penalty apply, or is it a 100% principal return? (Left unresolved pending authoritative policy).
4. **Institutional Schedule & Eligibility Boundaries:** Official campus timetable defining student-only, faculty-only, and open hours across facilities.
5. **Event Conflict Resolution Workflow:** Should overlapping bookings be cancelled and refunded automatically on event confirmation, or should the admin review a confirmation modal listing affected bookings first?
6. **Authentication & Identity Integration:** Whether authentication should integrate with university LDAP/SSO or use self-contained email registrations restricted by domain.
7. **Attendant Verification Hardware/Protocol:** Operational workflow and interface used by desk staff for ticket check-in at the facility entrance.

---

## 5. Explicit Exclusions

The following areas are confirmed as **OUT OF SCOPE**:
1. Native Android or iOS applications.
2. Direct hardware integration with turnstiles, smart gates, or physical entry barriers.
3. Services, accounts, bookings, or memberships for external non-university visitors.
4. User-initiated cancellation of confirmed Padel bookings.
5. Advance online reservations for sports other than Padel courts.
6. Equipment rental tracking and fee management (explicitly excluded).
7. Dedicated Cashier module (modeled as an RBAC permission).

---

## 6. Conflict Register: October Baseline vs. Prototype

| Conflict ID | Domain Area | October Course Report Baseline | Prototype / V1 Design Document Behavior | Baseline Status & Action |
|---|---|---|---|---|
| **CR-01** | **Booking Scope Across Facilities** | Online advance booking is **strictly for Padel courts** (FR-03, Scope 1.6). Other facilities follow published schedules or passes. | Prototype (`backend/main.go`, `README.md`) permits booking all 9 facilities (Badminton, Futsal, Squash, Tennis, etc.). | **October Baseline Precedes:** Limit booking workflows and models exclusively to Padel courts. |
| **CR-02** | **Equipment Rentals** | Equipment rentals **explicitly excluded** (SE-423 Section 8 AI Usage Log: removed equipment-related functionality). | Prototype `main.go` and `README.md` accept `equipmentRentals` array in `POST /api/bookings`. | **October Baseline Precedes:** Deprecate `equipmentRentals` fields from booking contracts. |
| **CR-03** | **Booking Cancellation Authority** | Cancellations are **strictly administrator-initiated** with single refund (FR-06, Out of Scope). | Prototype `main.go` exposes `DELETE /api/bookings/:id` publicly without authentication. | **October Baseline Precedes:** Remove public delete endpoint; restrict cancellation to admin-authenticated refund flow. |
| **CR-04** | **Persistence & Database Engine** | **PostgreSQL** relational database with strict schema, migrations, constraints, and transactions (SE-423 Section 1.3, SE-431 QR-15). | Prototype uses local JSON file (`data/store.json`) with Go in-memory `sync.RWMutex`. | **October Baseline Precedes:** Transition from JSON store to PostgreSQL schema with migrations. |
| **CR-05** | **Authentication & Password Security** | **Salted Argon2id** password hashing with server-side sessions (30m idle / 8h absolute expiry) (QR-13). | Design doc specifies Bcrypt + JWT tokens; prototype `main.go` has no authentication at all. | **October Baseline Precedes:** Implement Argon2id password hashing and stateful server-side sessions. |
| **CR-06** | **Gym Membership Term & Logic** | **30-day validity window** ($[T_{start}, T_{start}+30d)$) linked strictly to successful wallet payment (FR-04, QR-06). | Prototype `main.go` creates 6-month memberships (`AddDate(0,6,0)`) with no payment or wallet link. | **October Baseline Precedes:** Enforce 30-day period and link activation to wallet payment. |
| **CR-07** | **Digital Wallet & Ledger** | Append-only double-entry ledger with derived balances; JazzCash payment adapter (FR-05, QR-03, QR-12). | Prototype backend has zero wallet or payment code. Backend design doc 2.0 defers payments to "Phase 2". | **October Baseline Precedes:** Adopt and adapt GIKI-Wallet ledger and payment subsystems. |
| **CR-08** | **Content Publication States** | Announcements and achievements require **draft-to-published** lifecycle; unapproved drafts hidden (FR-07). | Prototype exposes public `POST /api/achievements` and `POST /api/announcements` that immediately make records live without draft state. | **October Baseline Precedes:** Implement editorial status field (`draft` / `published`) and access filters. |
| **CR-09** | **Frontend/Backend Contract Alignment** | Strict schema matching between client and API (QR-11, QR-14). | Frontend `types.ts` and `api.ts` expect `slug`, `shortName`, `tagline`, `schedule`, and `coach`, while backend returns flat Go struct fields, causing UI crashes. | **October Baseline Precedes:** Harmonize API schemas and TypeScript definitions. |
