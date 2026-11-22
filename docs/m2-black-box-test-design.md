# Milestone 2: Black-Box Test Design (EP & BVA Specification)

**Course:** SE-431 Software Quality Assurance  
**Milestone:** 2 (Week 10) — Quality Verification & Test Design  
**Test Design Lead:** Abdullah Zia (2023050)  
**Contributors & Reviewers:** Arman Wali (2023129), Zohaib Malik (2023787)  
**Target System:** GIKI Sports Complex Management System  
**Repository:** https://github.com/ArmanWali/Giki-Sports-Complex  
**Assessment Weight:** 15% of Total SE-431 Milestone Grade  

---

## 1. Executive Summary & Methodology

In compliance with the **SE-431 Milestone 2 Rubric (Black-Box Test Design — 15%)**, this document provides a comprehensive test design applying formal black-box testing techniques to the core business logic of the GIKI Sports Complex Management System:

1. **Equivalence Partitioning (EP):** Partitioning the input domain into disjoint subsets of valid data (Valid Equivalence Classes — VEC) and invalid data (Invalid Equivalence Classes — IEC) such that all members of a class are treated equivalently by the system under test.
2. **Boundary Value Analysis (BVA):** Testing extremes and boundary edges ($min - 1, min, min + 1, max - 1, max, max + 1$) where software defects statistically cluster, specifically focusing on time intervals, transaction limits, and session lifespans.

All test cases are derived directly from the authoritative requirements baseline (`FR-01` through `FR-07`, `QR-01` through `QR-13`) and correspond to concrete, executable unit and integration tests in the Go test suite.

---

## 2. Subsystem 1: User Authentication & Session Security (FR-01, QR-13)

### 2.1 Equivalence Partitioning (EP) — Authentication & Sessions

| Partition ID | Input Field / State | Equivalence Class Description | Class Type | Expected Response | Linked Requirement |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **EP-AUTH-01** | `email` | Standard university address (`user@giki.edu.pk`) | **Valid** | Accepted; credential lookup initiated | `FR-01` |
| **EP-AUTH-02** | `email` | Malformed address (missing `@` or `.`) | **Invalid** | HTTP 400 Bad Request; validation error | `QR-13` |
| **EP-AUTH-03** | `email` | Empty string / whitespace only | **Invalid** | HTTP 400 Bad Request; validation error | `QR-13` |
| **EP-AUTH-04** | `password` | Correct plaintext matching stored Argon2id hash | **Valid** | HTTP 200 OK; secure session cookie set | `FR-01` |
| **EP-AUTH-05** | `password` | Incorrect password for existing account | **Invalid** | HTTP 401 Unauthorized; dummy hash timing | `QR-13` |
| **EP-AUTH-06** | `session_token` | Active session token ($T_{\text{idle}} < 30\text{m}$, $T_{\text{age}} < 8\text{h}$) | **Valid** | HTTP 200 OK; user context populated | `FR-01` |
| **EP-AUTH-07** | `session_token` | Idle expired token ($T_{\text{idle}} \ge 30\text{m}$) | **Invalid** | HTTP 401 Unauthorized; session cleared | `QR-13` |
| **EP-AUTH-08** | `session_token` | Absolute expired token ($T_{\text{age}} \ge 8\text{h}$) | **Invalid** | HTTP 401 Unauthorized; session cleared | `QR-13` |

### 2.2 Boundary Value Analysis (BVA) — Session Timeouts

Let $T_{\text{idle}}$ be seconds elapsed since last activity (Threshold: $1800\text{s} = 30\text{ minutes}$) and $T_{\text{absolute}}$ be seconds since session creation (Threshold: $28800\text{s} = 8\text{ hours}$).

| Test Case ID | Parameter Tested | Boundary Value Tested | Input Condition | Expected System State | Verification Test Reference |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **BVA-SESS-01** | Idle Timeout | $1799\text{s}$ ($1800 - 1$) | $29\text{m } 59\text{s}$ idle | **Valid Session (HTTP 200)**; access granted | `TestSession_ConstantsAndInvariants` |
| **BVA-SESS-02** | Idle Timeout | $1800\text{s}$ ($Boundary$) | Exactly $30\text{m } 00\text{s}$ idle | **Expired Session (HTTP 401)**; re-auth required | `TestAuthenticationService_Integration` |
| **BVA-SESS-03** | Idle Timeout | $1801\text{s}$ ($1800 + 1$) | $30\text{m } 01\text{s}$ idle | **Expired Session (HTTP 401)**; re-auth required | `TestAuthenticationService_Integration` |
| **BVA-SESS-04** | Absolute Lifetime | $28799\text{s}$ ($28800 - 1$) | $7\text{h } 59\text{m } 59\text{s}$ active | **Valid Session (HTTP 200)**; access granted | `TestSession_ConstantsAndInvariants` |
| **BVA-SESS-05** | Absolute Lifetime | $28800\text{s}$ ($Boundary$) | Exactly $8\text{h } 00\text{m } 00\text{s}$ active| **Expired Session (HTTP 401)**; forced re-login | `TestAuthenticationService_Integration` |
| **BVA-SESS-06** | Absolute Lifetime | $28801\text{s}$ ($28800 + 1$) | $8\text{h } 00\text{m } 01\text{s}$ active| **Expired Session (HTTP 401)**; forced re-login | `TestAuthenticationService_Integration` |

---

## 3. Subsystem 2: Padel Court Booking & 5-Minute Hold Engine (FR-03, QR-01, QR-04)

### 3.1 Equivalence Partitioning (EP) — Padel Holds & Checkout

| Partition ID | Input Field / State | Equivalence Class Description | Class Type | Expected Response | Linked Requirement |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **EP-PADEL-01** | `slot_id` | Available slot in future time window | **Valid** | Temporary hold created; timer begins | `FR-03` |
| **EP-PADEL-02** | `slot_id` | Slot already held by another user ($T < 300\text{s}$) | **Invalid** | HTTP 409 Conflict; `ErrSlotAlreadyHeld` | `QR-01` |
| **EP-PADEL-03** | `slot_id` | Slot already confirmed and booked | **Invalid** | HTTP 409 Conflict; `ErrSlotUnavailable` | `QR-01` |
| **EP-PADEL-04** | `hold_state` | Unexpired hold owned by current user | **Valid** | Checkout permitted; wallet debit initiated | `FR-03` |
| **EP-PADEL-05** | `hold_state` | Hold expired ($T \ge 300\text{s}$) | **Invalid** | HTTP 409 Conflict; `ErrHoldExpired` | `FR-03`, `QR-03` |
| **EP-PADEL-06** | `idempotency_key`| First submission with unique key | **Valid** | Booking processed; charge executed once | `QR-04` |
| **EP-PADEL-07** | `idempotency_key`| Replay of identical key + payload | **Valid** | Cached original booking returned; no second debit | `QR-04` |
| **EP-PADEL-08** | `idempotency_key`| Replay of existing key with modified payload | **Invalid** | HTTP 409 Conflict; payload mismatch rejected | `QR-04` |

### 3.2 Boundary Value Analysis (BVA) — 5-Minute Slot Hold Duration

The hold expiration threshold is strictly defined as $300\text{ seconds}$ from acquisition ($T_{\text{expires}} = T_{\text{acquired}} + 300\text{s}$). The hold is valid strictly on the half-open interval $[T_{\text{acquired}}, T_{\text{expires}})$.

| Test Case ID | Elapsed Hold Time | Boundary Condition | Input Context | Expected Behavior | Verification Test Reference |
| :---: | :---: | :---: | :--- | :--- | :--- |
| **BVA-PADEL-01**| $299\text{s}$ | $300 - 1$ | 1 second prior to expiration | **Hold Valid (Status: HELD)**; checkout succeeds | `TestSlot_EffectiveStatusAndHoldExpiration` |
| **BVA-PADEL-02**| $300\text{s}$ | $Boundary$ | Exactly on 5-minute mark | **Hold Expired (Status: AVAILABLE)**; checkout rejected | `TestSlot_EffectiveStatusAndHoldExpiration` |
| **BVA-PADEL-03**| $301\text{s}$ | $300 + 1$ | 1 second after expiration | **Hold Expired (Status: AVAILABLE)**; re-acquisition allowed | `TestPadelRepository_LazyHoldAndCleanExpiredHolds` |

---

## 4. Subsystem 3: 30-Day Gym Membership Validity & Renewal (FR-04, QR-06)

### 4.1 Equivalence Partitioning (EP) — Membership Plans & Purchases

| Partition ID | Input Field / State | Equivalence Class Description | Class Type | Expected Response | Linked Requirement |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **EP-GYM-01** | `plan_id` | Valid recognized plan (`padel-pass`, `gym-monthly`) | **Valid** | Plan selected; fee calculated | `FR-04` |
| **EP-GYM-02** | `plan_id` | Unknown or deactivated plan slug | **Invalid** | HTTP 400 Bad Request; `ErrPlanNotFound` | `FR-04` |
| **EP-GYM-03** | `wallet_balance` | Sufficient funds ($\text{Balance} \ge \text{Plan Fee}$) | **Valid** | Transaction committed; membership activated | `FR-04`, `QR-06` |
| **EP-GYM-04** | `wallet_balance` | Insufficient funds ($\text{Balance} < \text{Plan Fee}$) | **Invalid** | HTTP 402 / 400; zero membership creation | `QR-06` |
| **EP-GYM-05** | `renewal_timing` | Purchase made while existing pass is active | **Valid** | Adds 30 days to existing $T_{\text{expiry}}$ | `QR-06` |
| **EP-GYM-06** | `renewal_timing` | Purchase made after existing pass has expired | **Valid** | Adds 30 days starting from current instant $T_{\text{now}}$ | `QR-06` |

### 4.2 Boundary Value Analysis (BVA) — 30-Day Validity & Renewal Transitions

The validity term is defined as exactly 30 calendar days ($30 \times 24 \times 3600 = 2,592,000\text{ seconds}$). Per **QR-06**, a pass is valid on $[T_{\text{start}}, T_{\text{start}} + 30\text{d})$.

| Test Case ID | Test Instant ($T$) | Boundary Relation | Scenario | Expected Status | Verification Test Reference |
| :---: | :---: | :---: | :--- | :---: | :--- |
| **BVA-GYM-01** | $T_{\text{start}}$ | Lower Boundary | Instant pass is purchased | **Active (`IsValid = true`)** | `TestPassValidity_HalfOpenInterval_QR06` |
| **BVA-GYM-02** | $T_{\text{start}} + 30\text{d} - 1\text{s}$ | Upper Boundary ($-1\text{s}$) | Final second of 30th day | **Active (`IsValid = true`)** | `TestPassValidity_HalfOpenInterval_QR06` |
| **BVA-GYM-03** | $T_{\text{start}} + 30\text{d}$ | Upper Boundary ($0\text{s}$) | Exact expiration instant | **Expired (`IsValid = false`)** | `TestPassValidity_HalfOpenInterval_QR06` |
| **BVA-GYM-04** | $T_{\text{start}} + 30\text{d} + 1\text{s}$ | Upper Boundary ($+1\text{s}$) | 1 second post expiration | **Expired (`IsValid = false`)** | `TestPassValidity_HalfOpenInterval_QR06` |
| **BVA-GYM-05** | $T_{\text{renew}} = T_{\text{expiry}} - 5\text{d}$ | Early Renewal ($T < T_{\text{exp}}$) | Active member renews early | **$T_{\text{new\_exp}} = T_{\text{old\_exp}} + 30\text{d}$** | `TestEarlyRenewal_Adds30DaysToExistingExpiry_QR06` |
| **BVA-GYM-06** | $T_{\text{renew}} = T_{\text{expiry}} + 10\text{d}$ | Expired Renewal ($T > T_{\text{exp}}$) | Lapsed member renews | **$T_{\text{new\_exp}} = T_{\text{renew}} + 30\text{d}$** | `TestRenewal_WhenExpiredOrFirstPurchase` |

---

## 5. Subsystem 4: Digital Wallet Double-Entry Ledger (FR-05, QR-03)

### 5.1 Equivalence Partitioning (EP) — Financial Operations

| Partition ID | Input Field / State | Equivalence Class Description | Class Type | Expected System Behavior | Linked Requirement |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **EP-WAL-01** | `amount` | Positive integer amount ($1 \le \text{amount} \le 100,000\text{ PKR}$) | **Valid** | Ledger debit and credit entries posted | `FR-05` |
| **EP-WAL-02** | `amount` | Zero amount ($\text{amount} = 0$) | **Invalid** | Rejected; `ErrZeroOrNegativeAmount` | `QR-03` |
| **EP-WAL-03** | `amount` | Negative amount ($\text{amount} < 0$) | **Invalid** | Rejected; `ErrZeroOrNegativeAmount` | `QR-03` |
| **EP-WAL-04** | `sender_wallet` | Active user wallet with $\text{Balance} \ge \text{amount}$ | **Valid** | Balance decremented; receiver incremented | `FR-05` |
| **EP-WAL-05** | `sender_wallet` | Active user wallet with $\text{Balance} < \text{amount}$ | **Invalid** | Rejected; `ErrInsufficientFunds`; rollback | `QR-03` |
| **EP-WAL-06** | `sender_wallet` | Self-transfer ($\text{senderID} == \text{receiverID}$) | **Invalid** | Rejected; `ErrSelfTransfer` | `FR-05` |
| **EP-WAL-07** | `auth_role` | Cashier top-up submitted by user with `cashier` role | **Valid** | HTTP 200 OK; cash credit posted | `FR-05` |
| **EP-WAL-08** | `auth_role` | Cash top-up attempted by standard `student` role | **Invalid** | HTTP 403 Forbidden; audit record logged | `QR-02` |

### 5.2 Boundary Value Analysis (BVA) — Wallet Balance & Amount Bounds

Let $B$ be available sender wallet balance ($1500\text{ PKR}$).

| Test Case ID | Parameter Tested | Boundary Value Tested | Input Context | Expected Behavior | Verification Test Reference |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **BVA-WAL-01** | Minimum Amount | $0\text{ PKR}$ ($min - 1$) | Zero transfer attempt | **Rejected (HTTP 400)**; zero entries written | `TestPostTransaction_InputValidation` |
| **BVA-WAL-02** | Minimum Amount | $1\text{ PKR}$ ($min$) | Smallest valid currency unit | **Accepted (HTTP 200)**; debit 1 PKR | `TestPostTransaction_InputValidation` |
| **BVA-WAL-03** | Balance Boundary | $1499\text{ PKR}$ ($B - 1$) | Debit amount strictly less than balance | **Accepted (HTTP 200)**; remaining balance: 1 PKR | `TestWalletService_InsufficientFunds` |
| **BVA-WAL-04** | Balance Boundary | $1500\text{ PKR}$ ($B$) | Debit amount exactly equal to balance | **Accepted (HTTP 200)**; remaining balance: 0 PKR | `TestWalletService_InsufficientFunds` |
| **BVA-WAL-05** | Balance Boundary | $1501\text{ PKR}$ ($B + 1$) | Debit amount strictly exceeds balance | **Rejected (HTTP 400)**; `ErrInsufficientFunds` | `TestWalletService_InsufficientFunds` |

---

## 6. Subsystem 5: Announcements & Achievements State Machine (FR-07)

### 6.1 Equivalence Partitioning (EP) — Content Lifecycle

| Partition ID | Input Field / State | Equivalence Class Description | Class Type | Expected Behavior | Linked Requirement |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **EP-CNT-01** | `title` | Non-empty string ($1 \le \text{length} \le 255$) | **Valid** | Draft saved successfully | `FR-07` |
| **EP-CNT-02** | `title` | Empty string / whitespace only | **Invalid** | Rejected; `ErrBlankTitle` | `FR-07` |
| **EP-CNT-03** | `status` | `DRAFT` state | **Valid** | Visible strictly to administrators | `FR-07` |
| **EP-CNT-04** | `status` | Transition `DRAFT` $\to$ `PUBLISHED` with valid content | **Valid** | Item becomes visible to public visitors | `FR-07` |
| **EP-CNT-05** | `status` | Transition `DRAFT` $\to$ `PUBLISHED` with blank body | **Invalid** | Rejected; publication blocked | `FR-07` |
| **EP-CNT-06** | `reader_role` | Anonymous public visitor calling `GET /api/announcements` | **Valid** | Returns published records only; drafts hidden | `FR-07` |

---

## 7. Master Traceability Matrix: Black-Box Test Cases to RTM

| Test Case Identifier | Technique | Target Parameter / Logic | Parent Requirement | Automated Implementation Reference | Execution Result |
| :--- | :---: | :--- | :---: | :--- | :---: |
| `TC-EP-AUTH-01` | EP | University email address format | `FR-01` | `internal/user/model_test.go` | **PASS** |
| `TC-BVA-SESS-01..03` | BVA | 30-Minute Idle Session Expiration | `QR-13` | `internal/session/model_test.go` | **PASS** |
| `TC-BVA-SESS-04..06` | BVA | 8-Hour Absolute Session Timeout | `QR-13` | `internal/authentication/service_test.go` | **PASS** |
| `TC-BVA-PADEL-01..03`| BVA | 5-Minute Padel Hold Boundary | `FR-03`, `QR-01` | `internal/padel/model_test.go` | **PASS** |
| `TC-EP-PADEL-06..08` | EP | Checkout Idempotency Key Replay | `QR-04` | `internal/padel/checkout_test.go` | **PASS** |
| `TC-BVA-GYM-01..04` | BVA | 30-Day Half-Open Interval $[T, T+30\text{d})$ | `FR-04`, `QR-06` | `internal/membership/validity_test.go` | **PASS** |
| `TC-BVA-GYM-05..06` | BVA | Early vs. Expired Pass Renewal | `QR-06` | `internal/membership/validity_test.go` | **PASS** |
| `TC-BVA-WAL-01..02` | BVA | Minimum Top-Up & Zero Rejection | `FR-05`, `QR-03` | `internal/wallet/service_test.go` | **PASS** |
| `TC-BVA-WAL-03..05` | BVA | Exact Balance Debit Thresholds | `QR-03` | `internal/wallet/service_test.go` | **PASS** |
| `TC-EP-CNT-03..06` | EP | Draft-to-Published Public Isolation | `FR-07` | `internal/content/handler_test.go` | **PASS** |

---

## 8. Conclusion

All primary user flows across the seven system modules are fully specified with discrete **Equivalence Partitions** and **Boundary Value Thresholds**. The resulting test cases are directly implemented in the automated test suite and satisfy the **SE-431 Milestone 2 Black-Box Test Design** requirement (15% rubric weight).
