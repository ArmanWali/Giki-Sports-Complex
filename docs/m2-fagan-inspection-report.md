# Milestone 2: Formal Fagan-Style Code Inspection Report & CAPA Register

**Course:** SE-431 Software Quality Assurance  
**Milestone:** 2 (Week 10) — Formal Inspection & Defect Tracking Baseline  
**Inspection Moderator & Defect Lead:** Arman Wali (2023129)  
**Artifact Author:** Zohaib Malik (2023787)  
**Reader / SQA Lead:** Abdullah Zia (2023050)  
**External Independent Inspector:** Danish Ahmad (2023172 — Team "Campus Facility Booking System", Paired Independent Inspector)  
**Target System:** GIKI Sports Complex Management System  
**Repository:** https://github.com/ArmanWali/Giki-Sports-Complex  
**Assessment Weight:** 20% of Total SE-431 Milestone Grade  

---

## 1. Inspection Overview & Fagan Process Evidence

In compliance with the **SE-431 Milestone 2 Rubric (Formal Inspection Report — 20%)** and **Project Guidelines Section 3.2**, a formal Fagan-style software code inspection was conducted on the core transactional and financial checkout engine.

### 1.1 Mandatory Inspection Roles

To eliminate self-review bias and satisfy the cross-team inspection mandate, the inspection team comprised four formal roles:

| Formal Role | Team Member | Responsibility in Inspection Cycle |
| :--- | :--- | :--- |
| **Moderator** | **Arman Wali** (2023129) | Planned inspection, scheduled meeting, verified entry criteria, mediated discussion, tracked defect log, and verified retesting during follow-up. |
| **Author** | **Zohaib Malik** (2023787) | Provided design specifications, presented overview, answered structural queries, performed defect rework, and submitted fixes for verification. |
| **Reader** | **Abdullah Zia** (2023050) | Paraphrased and led the team through the source code line-by-line during the formal meeting. |
| **External Inspector** | **Danish Ahmad** (2023172)<br>*(Paired Team "Campus Facility Booking System")* | **Independent Inspector** from external paired team; evaluated the code objectively against external specifications without insider bias. |

### 1.2 Inspection Logistics & Metrics

- **Target Artifact 1:** `backend/internal/padel/service.go` (`Checkout` workflow, Lines 348–460)
- **Target Artifact 2:** `backend/internal/padel/unit_of_work.go` (`UnitOfWork.Execute` transaction factory, Lines 40–115)
- **Target Artifact 3:** `backend/internal/wallet/service.go` (`PostTransactionTx` row locking, Lines 150–225)
- **Size of Inspected Artifacts:** 318 executable Lines of Code (LOC)
- **Preparation Time:** 2.0 hours per inspector (individual offline inspection)
- **Meeting Duration:** 90 minutes (1.5 hours)
- **Inspection Rate:** $318\text{ LOC} / 1.5\text{ h} = 212\text{ LOC/hour}$ *(Complies with Fagan standard threshold of $\le 250\text{ LOC/hour}$ for deep semantic review)*

### 1.3 The 6 Fagan Inspection Phases

```
┌───────────┐    ┌───────────┐    ┌─────────────┐    ┌────────────┐    ┌──────────┐    ┌───────────┐
│ Planning  │───>│ Overview  │───>│ Preparation │───>│ Inspection │───>│  Rework  │───>│ Follow-up │
│  (Arman)  │    │ (Zohaib)  │    │  (All 4)    │    │  Meeting   │    │ (Zohaib) │    │  (Arman)  │
└───────────┘    └───────────┘    └─────────────┘    └────────────┘    └──────────┘    └───────────┘
```

1. **Planning:** Moderator verified entry criteria (code compiled with zero compiler warnings, unit tests drafted).
2. **Overview:** Author briefed inspectors on transaction boundaries, row-level lock sequences, and ledger debit invariants.
3. **Preparation:** Each participant independently reviewed the code using the *Transactional Concurrency Checklist*, recording preliminary findings.
4. **Inspection Meeting:** Reader stepped through code line-by-line. Inspectors raised anomalies. Moderator recorded defects without debate on general design philosophy.
5. **Rework:** Author resolved all logged defects, updating code and adding regression test fixtures.
6. **Follow-up:** Moderator verified fixes against test runs, confirmed resolution, and formally signed off on closure.

---

## 2. Pre-Meeting Inspection Checklist

Inspectors reviewed the artifacts against a formal 8-point verification checklist:

- [x] **CHK-01 (Lock Ordering):** Are all database locks acquired in a deterministic order across concurrent transactions?
- [x] **CHK-02 (Idempotency):** Does the method safely reject duplicate submissions with conflicting payloads while returning original responses for identical replays?
- [x] **CHK-03 (Time Boundaries):** Are timestamp comparisons normalized to UTC and truncated to appropriate precision?
- [x] **CHK-04 (Rollback Safety):** Does any failure path exit without rolling back database transactions?
- [x] **CHK-05 (Credential & Data Leakage):** Are internal database IDs or balance traces leaked in error responses?
- [x] **CHK-06 (Defensive Validation):** Are all pointer receivers, strings, and UUID parameters validated before dereferencing?
- [x] **CHK-07 (Unbounded Retries):** Are random generation loops (e.g. check-in codes) bounded to prevent infinite loops?
- [x] **CHK-08 (Resource Cleanup):** Are all context timeouts and database transactions released via `defer`?

---

## 3. Formal Defect Log

During the preparation and inspection meeting phases, **5 reproducible defects** were identified:

| Defect ID | Artifact & Location | Severity | Defect Type | Defect Description & Observed Risk | Identified By |
| :---: | :--- | :---: | :---: | :--- | :---: |
| **DEF-01** | `padel/service.go`<br>Line 372 | **Critical** | Concurrency / Race Condition | **Pre-Lock vs Post-Lock Idempotency Window:** Idempotency lookup was only performed before acquiring the row lock on `LockSlotForBooking`. If two requests with the same key execute concurrently, both pass the pre-check before the lock is acquired, risking duplicate processing. | D. Ahmad<br>*(External)* |
| **DEF-02** | `padel/service.go`<br>Line 435 | **Major** | Data Integrity / Timing | **Sub-Second Clock Skew on Hold Expiration:** `now.Before(slot.HoldExpiresAt)` compared un-truncated nanosecond timestamps against database `TIMESTAMPTZ` values, causing boundary hold rejections 2 milliseconds before true expiration. | A. Zia<br>*(Reader)* |
| **DEF-03** | `padel/checkout.go`<br>Line 88 | **Major** | Algorithmic / Availability | **Unbounded Check-In Code Collision Loop:** `generateCheckInCode()` retried infinitely if collision occurred on the 6-character alphanumeric code, risking thread starvation under high slot volumes. | A. Wali<br>*(Moderator)*|
| **DEF-04** | `wallet/service.go`<br>Line 124 | **Minor** | Defensive Programming | **Unchecked Deferred Rollback Error:** `defer tx.Rollback(ctx)` ignored error return without debug logging during database connection drop scenarios. | Z. Malik<br>*(Author)* |
| **DEF-05** | `padel/unit_of_work.go`<br>Line 45 | **Minor** | Documentation / Maintainability | **Missing Abstract Factory Contract Godoc:** Interface `TransactionRepositoryFactory` lacked godoc annotations specifying that repositories spawned within the factory share the exact same underlying `pgx.Tx`. | D. Ahmad<br>*(External)* |

---

## 4. Corrective and Preventive Action (CAPA) Register

All logged defects were remediated by the author and verified by the moderator:

```text
Defect Status Summary:
Total Logged: 5 | Critical: 1 | Major: 2 | Minor: 2 | Verified & Closed: 5 (100%)
```

### 4.1 Detailed CAPA Action Sheets

#### CAPA-01 (for Defect DEF-01: Idempotency Concurrency Window)
- **Root Cause:** Optimization assumption that checking idempotency outside the row lock was sufficient for sequential replays.
- **Corrective Action:** Implemented **Double-Checked Idempotency Locking**. The pre-lock check provides an ultra-fast exit path for sequential replays, while a second check is executed immediately after acquiring the row lock:
  ```go
  // Post-lock idempotency check in case a concurrent request with identical key committed while waiting
  existing, err = factory.Bookings().FindBookingByIdempotency(ctx, userID, idempotencyKey)
  if existing != nil { return returnCachedBooking(existing) }
  ```
- **Preventive Action:** Created concurrent race integration test `TestCheckout_Concurrency_50Contenders_Integration` simulating 50 simultaneous contenders.
- **Verification Status:** **CLOSED.** Verified by Arman Wali on commit `7743075`.

#### CAPA-02 (for Defect DEF-02: Nanosecond Clock Drift on Hold Expiry)
- **Root Cause:** Standard Go `time.Now()` contains monotonic clock readings and nanoseconds not stored in standard PostgreSQL microsecond timestamp fields.
- **Corrective Action:** Normalized all time comparisons to UTC truncated to whole seconds (`time.Now().UTC().Truncate(time.Second)`).
- **Preventive Action:** Added boundary test `TestSlot_EffectiveStatusAndHoldExpiration` testing $T_{\text{exp}} - 1\text{s}$, $T_{\text{exp}}$, and $T_{\text{exp}} + 1\text{s}$.
- **Verification Status:** **CLOSED.** Verified by Arman Wali.

#### CAPA-03 (for Defect DEF-03: Unbounded Code Generator Retries)
- **Root Cause:** Naive `for` loop assuming collision probability on $36^6 \approx 2.17\times 10^9$ possibilities was too low to matter.
- **Corrective Action:** Bounded the retry loop to a maximum of 10 attempts; returns explicit typed error `ErrCodeGenerationFailed` if exhausted.
- **Preventive Action:** Unit test `TestCheckInCodeGenerator` verifying retry cap and format constraints.
- **Verification Status:** **CLOSED.** Verified by Arman Wali.

#### CAPA-04 (for Defect DEF-04: Error Swallowing on Deferred Rollback)
- **Root Cause:** Standard Go idiom `defer tx.Rollback(ctx)` produces compiler discard warning.
- **Corrective Action:** Added conditional check: if transaction is already committed, `ErrTxClosed` is safely ignored; otherwise, unexpected errors are logged to the audit facility.
- **Verification Status:** **CLOSED.** Verified by Arman Wali.

#### CAPA-05 (for Defect DEF-05: Missing Factory Godoc)
- **Root Cause:** Implementation was completed rapidly during Phase 6 without full package doc comments.
- **Corrective Action:** Added comprehensive architectural Godoc explaining the Abstract Factory pattern and transaction lifetime.
- **Verification Status:** **CLOSED.** Verified by Arman Wali.

---

## 5. Inspection Formal Sign-Off

The inspection team confirms that the inspected artifacts have undergone rigorous Fagan inspection, all identified defects have been remediated, and regression suites verify the integrity of the running system.

| Role | Name | Registration No. | Team | Formal Sign-Off |
| :--- | :--- | :---: | :---: | :---: |
| **Moderator** | Arman Wali | 2023129 | Team Banana | **APPROVED (Verified Closure)** |
| **Author** | Zohaib Malik | 2023787 | Team Banana | **APPROVED (Rework Complete)** |
| **Reader** | Abdullah Zia | 2023050 | Team Banana | **APPROVED (Checks Satisfied)** |
| **External Inspector** | Danish Ahmad | 2023172 | Team Campus Facility Booking System *(Paired)* | **APPROVED (Independent Sign-Off)** |
