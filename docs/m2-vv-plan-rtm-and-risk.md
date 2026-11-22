# Milestone 2: IEEE 1012 V&V Plan, Updated RTM v2 & Risk Register

**Course:** SE-431 Software Quality Assurance  
**Milestone:** 2 (Week 10) — Verification, Validation & Risk Governance  
**SE-431 Milestone 2 Lead / Integrator:** Abdullah Zia (2023050)  
**Contributors & Reviewers:** Arman Wali (2023129), Zohaib Malik (2023787)  
**Target System:** GIKI Sports Complex Management System  
**Repository:** https://github.com/ArmanWali/Giki-Sports-Complex  
**Assessment Weight:** 25% of Total SE-431 Milestone Grade (IEEE 1012 V&V: 15%, RTM & Risk Update: 10%)  

---

## 1. Executive Summary

This deliverable establishes the formal **Software Verification and Validation (V&V) Plan** governed by the **IEEE Std 1012-2016** standard, presents the **Updated Requirements Traceability Matrix (RTM v2)** demonstrating actual verified implementation status across all core business modules, and provides the **Milestone 2 Risk Register Review** incorporating post-mitigation residual risk calculations.

With this submission, all quality activities planned during Milestone 1 have been systematically executed, evidenced, and tied to the running software build.

---

## 2. IEEE 1012 Software Verification and Validation (V&V) Plan (15% Weight)

### 2.1 Formal Distinction: Verification vs. Validation

Following **IEEE Std 1012-2016 Section 4**, the quality program maintains a strict conceptual and operational distinction between Verification and Validation:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               IEEE 1012 V&V FRAMEWORK                                  │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│           VERIFICATION (Static & Unit)    │           VALIDATION (Dynamic & System)    │
│  "Are we building the product right?"     │  "Are we building the right product?"      │
├───────────────────────────────────────────┼────────────────────────────────────────────┤
│ • Conformance to architectural specs      │ • Conformance to real user expectations    │
│ • Static code vetting (go vet, tsc -b)    │ • End-to-end checkout & booking flows      │
│ • Formal Fagan inspections (DEF-01..05)   │ • Real digital wallet balance debiting     │
│ • Mathematical Cyclomatic Complexity      │ • Live Google Maps operating status UI     │
│ • Controlled-clock half-open unit tests   │ • WCAG 2.1 AA keyboard accessibility       │
│ • Deterministic deadlock lock ordering    │ • Cross-browser rendering on 390/1366px    │
└───────────────────────────────────────────┴────────────────────────────────────────────┘
```

### 2.2 Software Integrity Level (SIL) Assignment
Under IEEE 1012 risk-based classification, the **Financial Ledger & Booking Subsystem** is assigned **SIL 3 (High Integrity)** due to the potential for monetary inconsistency or double-booking conflicts during campus rushes. The **Announcements & Public Directory Subsystem** is assigned **SIL 1 (Basic Integrity)**.

### 2.3 Master V&V Activity Matrix

| Lifecycle Stage | Activity Name | Activity Type | Target Requirement | Method & Tooling | Responsible Member | Verifiable Evidence |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **Requirements** | RTM Consistency Review | **Verification** | `FR-01` to `FR-09` | Bidirectional cross-reference check | Abdullah Zia | `docs/requirements-baseline.md` |
| **Design** | Pattern Integrity Audit | **Verification** | OOD Criteria | Abstract Factory, Strategy, Adapter audit | Arman Wali | `backend/GIKI_SPORTS_COMPLEX_BACKEND_DESIGN.md` |
| **Implementation**| Static Code Vetting | **Verification** | `QR-14` | `go vet -v ./...`, `tsc -b` | Zohaib Malik | `docs/m2-static-analysis-and-scm.md` |
| **Implementation**| Formal Code Inspection | **Verification** | All SIL 3 | Fagan inspection with independent external peer | Arman Wali | `docs/m2-fagan-inspection-report.md` |
| **Implementation**| Unit Test Coverage | **Verification** | `QR-10` | Go testing framework + controlled clocks | Zohaib Malik | 100% passing backend unit test suites |
| **Integration** | Concurrency Stress Test | **Validation** | `QR-01`, `QR-04` | 50 simultaneous contenders integration fixture | Zohaib Malik | `TestCheckout_Concurrency_50Contenders_Integration` |
| **System** | End-to-End API Integration | **Validation** | `FR-01` to `FR-07` | Supertest / Fiber HTTP integration suites | Arman Wali | `http_integration_test.go` |
| **Acceptance** | First-Time User Usability | **Validation** | `QR-08` | Unassisted 3-minute booking user journey | Abdullah Zia | Padel booking wizard validation |
| **Acceptance** | Cross-Browser Audit | **Validation** | `QR-11` | Responsive rendering (390px mobile, 1366px desktop) | Abdullah Zia | Verified on Chrome, Firefox, WebKit |

---

## 3. Updated Requirements Traceability Matrix (RTM v2) (10% Weight)

At Milestone 1, all verification statuses were established as *Planned*. Below is the updated RTM reflecting the **actual implemented and verified Milestone 2 build**:

### 3.1 Functional Requirements Traceability (FR-01 to FR-09)

| Req ID | Requirement Summary | Primary Owner | Target Module | Concrete Implementation Artifacts | Automated Verification Suite | M2 Status |
| :---: | :--- | :---: | :--- | :--- | :--- | :---: |
| **FR-01** | User authentication, sessions & role-based access control | ZM | Auth / Users | `internal/auth/`, `internal/user/`, `internal/session/`, migration `00003` | `internal/auth/password_test.go`<br>`internal/session/model_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-02** | Facilities directory, timetables & Strategy eligibility | AW | Facilities | `internal/facility/`, `internal/seed/`, migrations `00002`, `00010`, `00011`, `00012` | `internal/facility/handler_test.go`<br>`internal/facility/service_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-03** | 5-minute Padel holds, checkout & ticket code verification | ZM | Padel Booking | `internal/padel/`, `unit_of_work.go`, `worker.go`, migration `00007` | `internal/padel/checkout_test.go`<br>`internal/padel/worker_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-04** | 30-day gym membership purchase, renewal & validity | AW | Memberships | `internal/membership/`, `validity.go`, migrations `00008`, `00013` | `internal/membership/validity_test.go`<br>`internal/membership/service_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-05** | Double-entry wallet ledger, cashier top-up & JazzCash | ZM | Digital Wallet | `internal/wallet/`, `internal/devwallet/`, migration `00006` | `internal/wallet/service_test.go`<br>`TestStableLockOrdering` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-06** | Admin booking cancellation with single refund | ZM | Padel / Wallet | `internal/padel/service.go` (`CancelBooking`) | `internal/padel/cancellation_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-07** | Announcements & achievements draft-to-published state machine | AZ | Content | `internal/content/`, migrations `00004`, `00005`, `00009`, `seed_content.sql` | `internal/content/handler_test.go`<br>`internal/content/model_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-08** | University event facility reservations & blockout | AZ | Events / Scheduling | Schedule audience expansion (`00010`) & admin override APIs | `internal/facility/handler_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **FR-09** | Structured administrative audit logs | AZ | Cross-Cutting | `internal/database/`, migration `00004_create_audit_logs.sql` | `internal/content/service_test.go`<br>`internal/facility/http_integration_test.go` | <span style="color:green;font-weight:bold;">PASSED</span> |

### 3.2 Quality Requirements Traceability (QR-01 to QR-15)

| Req ID | Quality Characteristic | System Quality Requirement | Target Threshold / Acceptance Criterion | Verification Evidence | M2 Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **QR-01** | Reliability | Double-booking prevention | In 100 trials with 50 simultaneous contenders, $\le 1$ booking succeeds | `TestCheckout_Concurrency_50Contenders_Integration` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-02** | Security | Role-based authorization | Unauthorized roles receive HTTP 403; private records isolated | `TestMiddleware_RequireAnyRole` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-03** | Functional Suitability| Ledger financial accuracy | $\text{Balance} = \sum \text{Credits} - \sum \text{Debits}$; zero partial charges | `TestWalletService_BalancedEntriesAndDerivedBalances` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-04** | Reliability | Idempotent transaction replay | 20 replayed checkout attempts produce exactly 1 charge and 1 booking | `TestCheckout_HappyPath_Integration` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-05** | Functional Suitability| Timetable & strategy rules | Mandatory closures override policy; student/faculty eligibility enforced | `TestFacilityRepository_ListAndAssociations` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-06** | Functional Suitability| 30-Day pass validity boundaries | Pass valid on $[T, T+30\text{d})$; renewal extends contiguous term | `TestPassValidity_HalfOpenInterval_QR06` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-07** | Performance Efficiency | API response latency | 95th-percentile response time $\le 2\text{s}$ reads, $\le 3\text{s}$ checkout | Go Fiber sub-millisecond local latency benchmark | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-08** | Usability | First-time booking completion | New campus user completes funded booking in $\le 3\text{ minutes}$ | React 19 interactive Padel booking wizard | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-09** | Usability | Keyboard accessibility | Zero keyboard traps; clear textual error feedback | Tab navigation verified across modals and timepicker | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-10** | Maintainability | Automated regression suite | Automated tests pass on all core business packages | `go test ./...` exits with code 0 across 10 packages | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-11** | Compatibility | Responsive web interface | Usable on viewport widths 390px (mobile) and 1366px (desktop) | Tailwind CSS v4 fluid layout; verified in Chrome & Firefox | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-12** | Compatibility | Payment gateway adapter | JazzCash callback verification and status mapping | `internal/wallet/` Adapter pattern implementation | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-13** | Security | Credential & session protection | Argon2id salted hashes; 30m idle / 8h absolute session invalidation | `TestPassword_Salting_DifferentHashesForIdenticalPasswords` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-14** | Maintainability | Static analysis & complexity gate | `go vet` and `tsc -b` report 0 errors; Cyclomatic Complexity $\le 10$ | `docs/m2-static-analysis-and-scm.md`<br>`docs/m2-white-box-test-design.md` | <span style="color:green;font-weight:bold;">PASSED</span> |
| **QR-15** | Reliability | Database migration integrity | Forward and reverse migrations execute cleanly without data loss | `TestMigrationIntegration_DisposableDatabaseCycle` | <span style="color:green;font-weight:bold;">PASSED</span> |

---

## 4. Milestone 2 Risk Register Review & Residual Risk Assessment

The 12 risks originally identified at Milestone 1 were re-evaluated based on architecture decisions, inspection findings (`DEF-01` to `DEF-05`), static analysis results, and test execution evidence.

**Scoring Scale:** Probability ($P \in [1..3]$) $\times$ Impact ($I \in [1..3]$) = Risk Score ($1..9$).

| Risk ID | Risk Description | Initial Rating | M2 Concrete Mitigation Implemented & Verified | Residual $P$ | Residual $I$ | Residual Score | M2 Status |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **R-01** | Simultaneous checkouts confirm same Padel slot | **9 (High)**<br>$(3 \times 3)$ | Row-level locking (`LockSlotForBooking`) with unique database constraints in `00007_create_padel_booking_tables.sql`. Verified by 50-contender test. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-02** | Partial checkout updates create ledger imbalance | **6 (High)**<br>$(2 \times 3)$ | Atomic PostgreSQL transaction (`UnitOfWork.Execute`) guarantees debit and booking commit together or roll back completely. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-03** | Missing role checks permit unauthorized actions | **6 (High)**<br>$(2 \times 3)$ | Fiber middleware (`RequireAnyRole`) validates role hierarchy and checks Origin header on all mutative routes. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-04** | Unclear facility eligibility rules cause access errors | **6 (High)**<br>$(3 \times 2)$ | Behavioral Strategy pattern (`EligibilityPolicy`) encapsulates student, faculty, and varsity rules; verified by unit decision tables. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-05** | Migration failure or schema corruption | **6 (High)**<br>$(2 \times 3)$ | Goose migrations runner hardened with PostgreSQL advisory session locks (`00001` to `00013`); reverse migrations restricted. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-06** | Payment provider sandbox delay | **6 (High)**<br>$(3 \times 2)$ | Structural Adapter pattern (`JazzCashAdapter`) decoupled internal ledger from provider wire formats using mock fixtures. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-07** | Integration overload across 7 modules | **9 (High)**<br>$(3 \times 3)$ | Modular monolith structure; vertical slice delivered early; continuous TDD commits across all 3 members. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-08** | Event blockout races with active user booking | **6 (High)**<br>$(2 \times 3)$ | Audience expansion migration (`00010`) and transactional schedule override checking. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-09** | Incorrect gym pass expiry calculations | **4 (Med)**<br>$(2 \times 2)$ | Pure mathematical utility `validity.go` using controlled clocks; half-open interval $[T, T+30\text{d})$ verified. | 1 | 1 | **1 (Low)** | **CONTROLLED** |
| **R-10** | Mobile viewport UI broken or overflowing | **4 (Med)**<br>$(2 \times 2)$ | Tailwind CSS v4 responsive grid; verified at 390px viewport width without horizontal scrollbars. | 1 | 1 | **1 (Low)** | **CONTROLLED** |
| **R-11** | Unverifiable AI-generated logic in codebase | **6 (High)**<br>$(2 \times 3)$ | Mandatory Fagan inspection with independent external peer review; every line defended and tested. | 1 | 2 | **2 (Low)** | **CONTROLLED** |
| **R-12** | CI and test-environment drift | **4 (Med)**<br>$(2 \times 2)$ | Pinned tool versions (Go 1.26.5, Node 23.8, PostgreSQL 17) and Docker Compose infrastructure configuration. | 1 | 1 | **1 (Low)** | **CONTROLLED** |

---

## 5. Milestone 2 Demo & Defense Guide

During the live Milestone 2 evaluation, the team is prepared to demonstrate:

1. **Working Core Build:**
   - Database startup: `docker compose up -d`
   - Migrations execution: `cd backend && go run ./cmd/migrate up` (applies all 13 migrations cleanly).
   - Backend launch: `cd backend && go run main.go` (listens on port 8081).
   - Frontend launch: `cd frontend && npm run dev` (listens on port 5173).
2. **Individual Rubric Defense:**
   - **Arman Wali:** Defends Facilities Strategy Pattern, Gym 30-day renewal calculations, and Moderator leadership of the Fagan inspection.
   - **Zohaib Malik:** Defends Argon2id timing protection, double-entry ledger lock ordering, Padel UnitOfWork, and HoldCleanerWorker Goroutine concurrency.
   - **Abdullah Zia:** Defends Content draft state machine, React 19 UI modals, WCAG keyboard accessibility, and IEEE 1012 V&V Plan.
