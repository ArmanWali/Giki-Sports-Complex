# Sports Complex Wallet Ledger Design

**Document ID:** `SPORTS-DESIGN-11A`  
**Status:** DRAFT (Step 11A Design Specification)  
**Related Requirements:** `FR-05`, `QR-03`, `QR-04`, `CR-07`  
**Related Implementation Plan:** Phase 5 (`Chunk 5.1`, `Chunk 5.2`, `Chunk 5.3`), Phase 6 (`Chunk 6.3`, `Chunk 6.5`), Phase 7 (`Chunk 7.2`)  
**Target Schema:** `giki_sports`  

---

## 1. Executive Summary & Scope

This design document establishes the architectural foundation for the financial ledger subsystem within the GIKI Sports Complex application (`giki_sports_complex`).

As defined in the project baseline:
* **`FR-05` (Digital Wallet Operations):** The system must record cashier cash credits, verified payment gateway credits, and service debits (e.g., Padel court bookings, memberships) within an immutable, append-only double-entry financial ledger. Account balances must be derived dynamically from ledger records ($\sum \text{Credits} - \sum \text{Debits}$) rather than maintained as mutable columns.
* **`QR-03` (Pricing & Atomic Debit):** Confirmed charges must match approved pricing rules. If a failure occurs during checkout or slot confirmation, both the booking and the ledger debit must roll back completely and atomically.
* **`QR-04` (Idempotency):** Replaying an identical user-scoped idempotency key 20 times must produce exactly 1 booking and 1 ledger debit; replaying a payment gateway callback reference 20 times must produce exactly 1 ledger credit.

This document reviews the existing GIKI Wallet codebase, compares architectural deployment options (local Sports ledger vs. external service integration), establishes the minimum double-entry data model, and outlines concurrency and idempotency defenses.

> **Scope Note for Step 11A:** This is a pure design milestone. No application code, database migrations, payment provider integrations, booking mutations, or GIKI Wallet modifications are performed during this step.

---

## 2. Review of GIKI Wallet Architecture

GIKI Wallet (`giki-wallet/backend`) contains a mature, production-grade double-entry ledger implementation. A thorough inspection of its database migrations, queries, and Go domain services reveals key architectural patterns and hardening measures that inform our Sports ledger design.

### 2.1 Schema & Migrations Reviewed

1. **`giki-wallet/backend/sql/schema/005_wallets.sql`:**
   * Defines schema `giki_wallet`.
   * **`wallets` table:** Supports personal user wallets (`user_id uuid UNIQUE REFERENCES users(id)`) and system wallets (`type VARCHAR(20) DEFAULT 'PERSONAL'`). Status enumeration: `ACTIVE`, `FROZEN`, `SUSPENDED`, `CLOSED`. Currency defaults to `G-Bux`.
   * **`transactions` table:** Acts as the logical transaction header (`id`, `type`, `reference_id`, `description`, `created_at`). Imposes `UNIQUE(type, reference_id)` to enforce business-level idempotency per transaction type.
   * **`ledger` table:** Stores individual legs of the double entry (`id`, `wallet_id`, `amount BIGINT CHECK (amount <> 0)`, `balance_after BIGINT`, `transaction_id`, `row_hash VARCHAR(255)`, `created_at TIMESTAMPTZ`).
   * **Indexes:** `idx_ledger_wallet_history (wallet_id, created_at DESC)` for efficient statement retrieval; `idx_ledger_txn_fk (transaction_id)` for join performance.

2. **`giki-wallet/backend/sql/schema/019_fix_wallet_race_condition.sql`:**
   * Resolves concurrent initialization of system wallets by adding a partial unique index:
     ```sql
     CREATE UNIQUE INDEX idx_system_wallet_unique 
     ON giki_wallet.wallets (name, type) 
     WHERE type IN ('SYS_REVENUE', 'SYS_LIABILITY');
     ```

3. **`giki-wallet/backend/sql/schema/020_prevent_ledger_corruption.sql`:**
   * Hardens referential integrity by altering the foreign key on `giki_wallet.ledger.transaction_id` to use `ON DELETE RESTRICT`, preventing cascading deletes from wiping historical audit rows.

4. **`giki-wallet/backend/sql/schema/021_fix_ledger_balance_ordering.sql`:**
   * Replaces transaction start time `NOW()` with monotonic system clock time:
     ```sql
     ALTER TABLE giki_wallet.ledger
         ALTER COLUMN created_at SET DEFAULT clock_timestamp();
     ```
   * *Critical Insight:* In PostgreSQL, `NOW()` remains fixed to the transaction start time across all statements in a transaction. When paired debit and credit entries are inserted in the same transaction, identical timestamps can introduce tie-breaking ambiguity during historical reconstructions. `clock_timestamp()` guarantees distinct, strictly increasing timestamps.

### 2.2 Data Access Queries Reviewed

* **`giki-wallet/backend/internal/wallet/sql/queries.sql`:**
  * `GetWalletForUpdate`: Performs row-level locking via `SELECT * FROM giki_wallet.wallets WHERE id = $1 FOR NO KEY UPDATE;`.
  * `GetOrCreateWalletAtomic`: Upsert pattern using `ON CONFLICT (user_id) WHERE type = 'PERSONAL' DO UPDATE SET status = wallets.status`.
  * `GetOrCreateSystemWalletAtomic`: Upsert pattern for system wallets using `ON CONFLICT (name, type) WHERE type IN ('SYS_REVENUE', 'SYS_LIABILITY')`.
  * `CreateTransactionHeader`: Inserts `(type, reference_id, description)` returning `(id, created_at)`.
  * `CreateLedgerEntry`: Inserts `(wallet_id, amount, transaction_id, balance_after, row_hash)`.
  * `GetWalletBalanceSnapshot`: Retrieves latest `balance_after` via `ORDER BY created_at DESC, id DESC LIMIT 1`.

### 2.3 Domain Service Logic Reviewed

* **`giki-wallet/backend/internal/wallet/service.go`:**
  * **`executeDoubleEntryTransaction(...)` (Lines 37–155):**
    * Validates that `amount > 0`.
    * **Opposite-Order Lock Cycle Prevention (Lines 58–61):** Sorts wallet UUIDs lexically before acquiring locks to prevent AB/BA lock cycles on the wallets table:
      ```go
      firstID, secondID := senderWalletID, receiverWalletID
      if firstID.String() > secondID.String() {
          firstID, secondID = secondID, firstID
      }
      ```
    * **Pessimistic Locking (Lines 64–74):** Calls `GetWalletForUpdate` on both wallets in sorted order.
    * **Balance Sufficiency (Lines 95–99):** Verifies `senderBalance >= amount` for non-system wallets; returns `ErrInsufficientFunds` if inadequate.
    * **Atomic Entry Creation (Lines 119–150):** Inserts both the debit leg (`-amount`) and credit leg (`+amount`) linked to the common transaction header.
    * **Row Hashing (Lines 442–470):** `CalculateRowHash` computes HMAC-SHA256 over `walletID|amount|transactionID|balanceAfter|createdAt` using a centralized ledger secret to detect offline tampering.
  * **`VerifyBookingDebitExists` and `VerifyRefundExists` (Lines 198–227):** Queries transaction headers to ensure refunds are strictly preceded by a confirmed debit and cannot be duplicated.

### 2.4 Integration in Transport & Payment Modules Reviewed

* **`giki-wallet/backend/internal/transport/service.go` (`BookTickets`, Lines 492–505):**
  * Transport booking and wallet debit share the **same database transaction** (`tx pgx.Tx`).
  * If ticket creation, hold deletion, or seat allocation fails, `tx.Rollback()` aborts both the booking and the wallet debit simultaneously.
* **`giki-wallet/backend/internal/payment/service.go` (`JazzCashDeposit`, Lines 490–520):**
  * Debits `SYS_LIABILITY` and credits the user's personal wallet using the payment gateway reference (`pp_TxnRefNo`).
  * Catches `CheckUniqueConstraintViolation(err)` (SQLSTATE `23505`) on `UNIQUE(type, reference_id)` to guarantee idempotent webhook handling.

---

## 3. Architecture Comparison & Atomic Checkout Tradeoffs

To support Sports Complex operations (Padel bookings, equipment checkout, facility memberships, cashier top-ups), we evaluate two structural options:

```
+--------------------------------------------------------------------------------------------------+
| OPTION A: Sports-Owned Local PostgreSQL Ledger (Recommended for Local Dev & Sports Subsystem)   |
|                                                                                                  |
|   +------------------------------------------------------------------------------------------+   |
|   | Sports Backend Process                                                                   |   |
|   |                                                                                          |   |
|   |   +----------------------------------------------------------------------------------+   |   |
|   |   | Single Database Transaction: pgx.Tx (Unit of Work)                               |   |   |
|   |   |                                                                                  |   |   |
|   |   |   1. Verify Slot Hold        2. Create Booking        3. Debit User Ledger       |   |   |
|   |   |      (padel_slots)              (bookings)               (wallet_ledger_entries) |   |   |
|   |   +----------------------------------------------------------------------------------+   |   |
|   +---------------------------------------------+--------------------------------------------+   |
|                                                 | (Local Connection Pool)                        |
|                                                 v                                                |
|                   +----------------------------------------------------------+                   |
|                   | PostgreSQL (Database: giki_sports_complex)               |                   |
|                   | Schema: giki_sports                                      |                   |
|                   +----------------------------------------------------------+                   |
+--------------------------------------------------------------------------------------------------+

                                                VS

+--------------------------------------------------------------------------------------------------+
| OPTION B: External GIKI Wallet Service Integration                                               |
|                                                                                                  |
|   +-------------------------------+                 +----------------------------------------+   |
|   | Sports Backend Process        |                 | GIKI Wallet Service (External Port)    |   |
|   |                               |                 |                                        |   |
|   |   1. Padel Slot Hold (DB 1)   |                 |   3. Debit Wallet API / RPC            |   |
|   |   2. Remote Call to Wallet    |== HTTP / gRPC =>|      (Database 2: giki_wallet)         |   |
|   |   4. Confirm Booking (DB 1)   |                 |                                        |   |
|   |                               |                 +----------------------------------------+   |
|   |   * Distributed Failure Risk: |                                                              |
|   |     If Step 4 fails after 3,  |                                                              |
|   |     must invoke Compensating  |                                                              |
|   |     Refund API.               |                                                              |
|   +-------------------------------+                                                              |
+--------------------------------------------------------------------------------------------------+
```

### 3.1 Comparative Analysis Matrix

| Evaluation Dimension | Option A: Sports-Owned Local Ledger (Adapted from GIKI Wallet) | Option B: External GIKI Wallet Service Integration |
|---|---|---|
| **Padel Checkout Atomicity (`QR-03`)** | **Strong ACID Guarantee:** Slot hold conversion and ledger debit execute within a single PostgreSQL `pgx.Tx`. If either step fails or encounters a concurrent conflict, the entire transaction rolls back cleanly. Zero risk of orphaned charges or double-booked slots. | **Distributed Saga / Two-Phase:** Cannot use a single `pgx.Tx`. If the wallet debit succeeds but the subsequent booking confirmation fails (or network times out), the system must execute a compensating refund call. Introduces window of vulnerability and reconciliation lag. |
| **Local Development Ergonomics** | **Zero External Dependencies:** Runs entirely inside the local `giki_sports_complex` PostgreSQL instance. Backend tests use existing disposable test containers/databases without spinning up or mocking an auxiliary microservice. | **High Complexity:** Developers must run both the Sports backend and the Wallet service, coordinate ports, seed matching users in two databases, and handle network mock failures in CI tests. |
| **Identity & Account Mapping** | Uses existing Sports `giki_sports.users` table (`id` UUID). No cross-service foreign-key mismatch or user synchronization required. | Requires either a federated campus SSO token, shared UUIDs across databases, or an explicit mapping table between Sports users and Wallet users. |
| **System Resilience & Network Failures** | Immune to inter-service network latency, circuit breaker trips, or socket timeouts during checkout. | Vulnerable to network partitions. Requires exponential backoff, dead-letter queues, and automated background reconciliation workers for failed calls. |
| **Audit & Reporting Isolation** | Sports directors and super admins can query booking receipts and ledger journals in unified administrative reporting queries. | Financial transaction logs reside in a separate database; administrative dashboards must aggregate data across multiple service endpoints. |
| **Compliance with Project Baseline** | Directly fulfills `FR-05`, `QR-03`, `CR-07`, and Phase 5/6 architecture outlined in `docs/implementation-plan.md`. | Deviates from the planned checkout design (`Chunk 6.3`), which specifically mandates a shared `UnitOfWork` binding `BookingRepository` and `LedgerRepository`. |

### 3.2 Recommendation for Local Development and Phase 5/6

**We recommend Option A (Sports-Owned PostgreSQL Ledger adapted from GIKI Wallet code) for local development and for the Sports Complex architecture.**

#### The Tradeoff for Atomic Padel Checkout:
1. In Padel court checkout, sports users lock a hold on an in-demand court slot. The slot hold has a strict 10-minute expiry window (`FR-03`).
2. When the user confirms checkout, two state mutations must occur together:
   * The slot hold must be converted into a confirmed `booking` with a verified check-in code.
   * The user's wallet must be debited the exact booking fee, and `SPORTS_REVENUE` must be credited.
3. With **Option A**, both mutations happen inside one PostgreSQL transaction (`pgx.Tx`):
   ```go
   // Unit of Work pattern:
   err := uow.Execute(ctx, func(factory TransactionRepositoryFactory) error {
       if err := factory.Bookings().ConfirmSlot(ctx, slotID, bookingDetails); err != nil {
           return err // automatic rollback of debit and booking
       }
       if err := factory.Ledger().DebitUser(ctx, userID, revenueWalletID, amount, "PADEL_BOOKING", bookingID); err != nil {
           return err // automatic rollback of debit and booking
       }
       return nil
   })
   ```
4. With **Option B**, the booking engine would have to call an external API. If the HTTP call to the wallet succeeds but the database write to `bookings` fails (e.g., deadlock, connection blip, constraint violation), the user has lost funds without receiving a booking. Resolving this requires a distributed two-phase commit or a compensating saga with retry queues, significantly elevating failure modes without adding local development benefit.

#### Clear System Boundaries & Strict Constraints:
To maintain clean architecture and respect project boundaries:
* **No Assumption of Shared Accounts:** Sports Complex `users` and GIKI Wallet `users` are distinct tables in separate schemas/databases.
* **No Shared Balances or Cross-Database SQL:** The Sports backend will not issue cross-database joins or cross-schema queries into `giki_wallet.*`.
* **No Direct Live Service Calls:** The Sports backend will not attempt unauthenticated or undocumented HTTP calls to a live external GIKI Wallet daemon unless an official campus API contract is formally provisioned.

### 3.3 Stakeholder Decisions Requiring Confirmation Before Production

While Option A is strictly required for local development and self-contained integration tests, the following decisions must be formally confirmed prior to production deployment:
1. **Campus-Wide Unified Wallet vs. Dedicated Sports Balance:** Will campus students use a single universal GIKI Wallet balance for transport, cafeteria, and sports, or will the Sports Complex maintain a dedicated sub-ledger account funded via cashier/gateway?
2. **Refund Policy Rules:** When an administrator cancels a confirmed Padel booking (`FR-06`), is the refund 100% of the booked fee, or are there time-dependent cancellation penalty fees?
3. **Cashier Role Provisioning:** Which user role permissions (`sports_director`, `super_admin`, or a dedicated `cashier` role) will be authorized to credit cash at the sports complex front desk?

---

## 4. Minimum Double-Entry Ledger Data Model

The Sports wallet ledger will adapt the proven GIKI Wallet schema while tailoring tables, types, and constraints to the `giki_sports` schema.

```
                          +------------------------------------------------+
                          |              giki_sports.wallets               |
                          |------------------------------------------------|
                          | id (UUID, PK)                                  |
                          | user_id (UUID, NULL for system, UNIQUE)        |
                          | name (VARCHAR(100))                            |
                          | type (VARCHAR(30))                             |
                          | status (VARCHAR(20): ACTIVE, FROZEN, CLOSED)   |
                          | currency (VARCHAR(10): PKR)                    |
                          | created_at (TIMESTAMPTZ)                       |
                          +------------------------------------------------+
                                 ^                                  ^
                                 |                                  |
                 Debit Leg       |                                  | Credit Leg
              (wallet_id FK)     |                                  | (wallet_id FK)
                                 |                                  |
                     +--------------------------------------------------+
                     |        giki_sports.wallet_ledger_entries         |
                     |--------------------------------------------------|
                     | id (UUID, PK)                                    |
                     | wallet_id (UUID, FK -> wallets.id)               |
                     | transaction_id (UUID, FK -> wallet_transactions) |
                     | amount (BIGINT, CHECK <> 0)                      |
                     | balance_after (BIGINT)                           |
                     | row_hash (VARCHAR(64))                           |
                     | created_at (TIMESTAMPTZ, clock_timestamp())      |
                     +--------------------------------------------------+
                                                |
                                                | References (ON DELETE RESTRICT)
                                                v
                          +------------------------------------------------+
                          |        giki_sports.wallet_transactions         |
                          |------------------------------------------------|
                          | id (UUID, PK)                                  |
                          | type (VARCHAR(50))                             |
                          | reference_id (VARCHAR(100))                    |
                          | description (TEXT)                             |
                          | created_at (TIMESTAMPTZ)                       |
                          |                                                |
                          | CONSTRAINT: UNIQUE (type, reference_id)        |
                          +------------------------------------------------+
```

### 4.1 Currency & Unit Representation (Integer Paisa)
* **Zero Floating Point Arithmetic:** All monetary amounts are stored as 64-bit signed integers (`BIGINT`) representing **paisa** (1 PKR = 100 paisa).
  * Example: 500 PKR = `50000` paisa.
  * Example: 2,500 PKR = `250000` paisa.
* Eliminates IEEE 754 binary floating-point rounding errors and fractional cent discrepancies.
* Currency identifier is standardized to `PKR`.

### 4.2 Entities and Tables

#### 1. `giki_sports.wallets`
Represents an individual or system financial account.
* `id` (`UUID PRIMARY KEY DEFAULT gen_random_uuid()`): Unique wallet identifier.
* `user_id` (`UUID UNIQUE REFERENCES giki_sports.users(id) ON DELETE RESTRICT`): Nullable for system wallets; unique for personal user wallets.
* `name` (`VARCHAR(100) NOT NULL`): Descriptive label (e.g., `"Personal Wallet"`, `"Sports Revenue"`, `"Cashier Clearing"`).
* `type` (`VARCHAR(30) NOT NULL`): Account classification:
  * `PERSONAL`: Individual student/faculty wallet.
  * `SYS_REVENUE`: System revenue account (credits from booking fees, memberships).
  * `SYS_LIABILITY`: System liability/clearing account (sources cashier top-ups and gateway deposits).
* `status` (`VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'`): Enforced by `CHECK (status IN ('ACTIVE', 'FROZEN', 'SUSPENDED', 'CLOSED'))`.
* `currency` (`VARCHAR(10) NOT NULL DEFAULT 'PKR'`): Account denomination.
* `created_at` (`TIMESTAMPTZ NOT NULL DEFAULT NOW()`).

#### 2. `giki_sports.wallet_transactions`
The immutable transaction header recording the business event.
* `id` (`UUID PRIMARY KEY DEFAULT gen_random_uuid()`): Transaction event ID.
* `type` (`VARCHAR(50) NOT NULL`): Transaction classification (e.g., `CASHIER_CASH_TOPUP`, `JAZZCASH_TOPUP`, `PADEL_BOOKING`, `BOOKING_REFUND`, `MEMBERSHIP_PURCHASE`).
* `reference_id` (`VARCHAR(100) NOT NULL`): External or domain reference (e.g., cashier receipt number, payment gateway transaction reference, booking UUID).
* `description` (`TEXT NOT NULL DEFAULT ''`): Human-readable memo.
* `created_at` (`TIMESTAMPTZ NOT NULL DEFAULT NOW()`).
* **Uniqueness Constraint:** `UNIQUE (type, reference_id)` guarantees replay protection.

#### 3. `giki_sports.wallet_ledger_entries`
The atomic double-entry line items.
* `id` (`UUID PRIMARY KEY DEFAULT gen_random_uuid()`): Entry ID.
* `wallet_id` (`UUID NOT NULL REFERENCES giki_sports.wallets(id) ON DELETE RESTRICT`).
* `transaction_id` (`UUID NOT NULL REFERENCES giki_sports.wallet_transactions(id) ON DELETE RESTRICT`).
* `amount` (`BIGINT NOT NULL CHECK (amount <> 0)`): Signed integer in paisa. Positive for credit (incoming funds), negative for debit (outgoing funds).
* `balance_after` (`BIGINT NOT NULL`): The wallet's running balance immediately following this entry.
* `row_hash` (`VARCHAR(64) NOT NULL`): HMAC-SHA256 signature sealing the entry against modification.
* `created_at` (`TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()`): Monotonically increasing entry timestamp.

### 4.3 Double-Entry Zero-Sum Invariant
Every transaction header `T` must be associated with two or more ledger entries whose signed amounts sum to exactly zero:
$$\sum_{e \in \text{Entries}(T)} e.\text{amount} = 0$$

* When Alice adds 500 PKR via cashier:
  * System Liability: `-50000` paisa (debit from liability)
  * Alice Personal Wallet: `+50000` paisa (credit to user)
  * Sum: `(-50000) + (+50000) = 0`
* When Alice books a Padel court for 200 PKR:
  * Alice Personal Wallet: `-20000` paisa (debit from user)
  * Sports Revenue: `+20000` paisa (credit to revenue)
  * Sum: `(-20000) + (+20000) = 0`

### 4.4 Balance Derivation & Reversal Corrections
1. **Dynamic Derived Balance:**
   The true financial balance of any wallet is the mathematical sum of all historical entries recorded for that wallet:
   $$\text{Balance}(W) = \sum_{e \in \text{Entries}(W)} e.\text{amount}$$
   While `balance_after` is stored on each row for fast point-in-time reads and audit reconciliation (`ORDER BY created_at DESC, id DESC LIMIT 1`), the system integrity test suite will continuously verify that:
   $$\text{Latest}(balance\_after) \equiv \sum e.\text{amount}$$
2. **Reversals Instead of Edits (Strict Append-Only):**
   * Historical entries are never updated (`UPDATE`) or deleted (`DELETE`).
   * If a booking is cancelled or an erroneous top-up occurs, an authorized administrator or system workflow creates a **new** transaction with compensating reversal entries:
     * Original Debit: Alice `-20000`, Revenue `+20000`.
     * Reversal (Refund): Revenue `-20000`, Alice `+20000`.
   * Both pairs remain permanently visible in the audit trail.

---

## 5. Concurrency, Idempotency & Defense-in-Depth

Financial ledgers require strict guarantees against race conditions, duplicate execution, and unauthorized modifications.

### 5.1 Concurrency & Overdraft Defenses (Row-Level Locking)
* **The Overdraft Race Risk:** If a user with a 200 PKR balance initiates two concurrent checkout requests simultaneously, both threads could read `balance = 20000`, validate that `20000 >= 20000`, and proceed to insert two debits of `20000`, leaving the user at `-20000` paisa.
* **Deterministic Ordered Locking:**
  Before reading the sender's balance or inserting ledger entries, the transaction must acquire exclusive row locks on the participating wallets:
  ```sql
  SELECT * FROM giki_sports.wallets WHERE id = $1 FOR NO KEY UPDATE;
  ```
  To prevent **AB/BA opposite-order lock cycles** when two concurrent transactions touch the same pair of wallets in opposing directions (e.g., transfers between User A and User B), wallet IDs are locked in deterministic lexical order:
  $$\text{FirstLock} = \min(W_A, W_B), \quad \text{SecondLock} = \max(W_A, W_B)$$
  *Note:* Lexicographical row locking prevents opposite-order lock cycles on the `wallets` table; it does not eliminate cross-table or multi-resource deadlock scenarios if external transactions acquire locks out of sequence.
* **Atomicity of Balance Check:** The check `balance >= amount` is performed **inside** the locked transaction window. Concurrent checkout requests are serialized; the second request will read the updated balance (`0`) and immediately fail with `ErrInsufficientFunds`.

### 5.2 Idempotent Deduplication (`QR-04`)
* **Transaction Header Constraint:** The unique index `UNIQUE (type, reference_id)` on `giki_sports.wallet_transactions` acts as the primary gatekeeper against double-execution.
* **Cashier & Payment Webhooks:** If JazzCash retries a webhook notification 20 times for the same `pp_TxnRefNo`, the first attempt commits successfully; subsequent attempts trigger a PostgreSQL unique constraint violation (`SQLSTATE 23505`). The application catches this violation and returns an idempotent HTTP 200 success without executing duplicate ledger entries.
* **Client Idempotency Keys:** Client checkouts submit a unique idempotency key header (`Idempotency-Key: UUID`). The key is bound to the booking transaction header. Replaying the checkout request returns the existing confirmed booking without a second charge.

### 5.3 Append-Only Enforcement & Tamper Detection
1. **PostgreSQL Trigger Defense:**
   A database trigger installed on `giki_sports.wallet_ledger_entries` and `giki_sports.wallet_transactions` will abort any attempt to execute `UPDATE` or `DELETE`:
   ```sql
   CREATE OR REPLACE FUNCTION giki_sports.prevent_ledger_modification()
   RETURNS TRIGGER AS $$
   BEGIN
       RAISE EXCEPTION 'Ledger records are immutable and append-only. UPDATE or DELETE is strictly prohibited.';
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER trg_immutable_ledger_entries
   BEFORE UPDATE OR DELETE ON giki_sports.wallet_ledger_entries
   FOR EACH ROW EXECUTE FUNCTION giki_sports.prevent_ledger_modification();
   ```
2. **Cryptographic HMAC-SHA256 Sealing:**
   Each ledger row incorporates a `row_hash` calculated over:
   $$\text{Hash} = \text{HMAC-SHA256}(K, \text{wallet\_id} \parallel \text{amount} \parallel \text{transaction\_id} \parallel \text{balance\_after} \parallel \text{created\_at})$$
   Any out-of-band manipulation (such as a compromised database superuser altering an amount) invalidates the hash chain and is immediately flagged during audit scans.

### 5.4 Separation of Responsibilities: PostgreSQL vs. Application Controls

| Security / Integrity Rule | Enforced Directly by PostgreSQL Engine | Enforced by Application / Transaction Controls (`pgx.Tx`) |
|---|:---:|:---:|
| **Non-Zero Amounts (`amount <> 0`)** | ✅ `CHECK (amount <> 0)` | ✅ Validated at input gateway (`amount > 0`) |
| **Referential Integrity** | ✅ Foreign keys with `ON DELETE RESTRICT` | — |
| **Monotonic Timestamping** | ✅ `DEFAULT clock_timestamp()` | — |
| **Replay Protection** | ✅ `UNIQUE (type, reference_id)` | ✅ Idempotency key mapping & HTTP response caching |
| **Physical Immutability** | ✅ `BEFORE UPDATE OR DELETE` triggers | ✅ Repository exposes only `INSERT` and `SELECT` |
| **Opposite-Order Lock Cycle Avoidance** | — | ✅ Lexicographical wallet ID sorting before locking prevents AB/BA lock cycles on the wallets table |
| **Sufficient Balance Check** | Optional `CHECK (balance_after >= 0)` on personal wallets | ✅ Evaluated under `SELECT FOR UPDATE` lock |
| **Zero-Sum Ledger Balance ($\sum = 0$)** | Deferred constraint / audit view | ✅ Transaction creates paired entries in single atomic block |
| **Cross-Module Atomic Checkout** | Single DB transaction scope | ✅ `UnitOfWork` coordinating Booking and Ledger repositories |

---

## 6. Synthetic Concrete Example & Entry Trace

To illustrate the ledger model in operation, consider a concrete end-to-end scenario involving User Alice (`user_id: 11111111-...`):

### 6.1 Wallets Setup
* **Alice Personal Wallet:** `ID = A000...`, Type = `PERSONAL`, Currency = `PKR`
* **System Liability Wallet:** `ID = L000...`, Type = `SYS_LIABILITY`, Name = `"Cashier Clearing"`
* **Sports Revenue Wallet:** `ID = R000...`, Type = `SYS_REVENUE`, Name = `"Sports Revenue"`

---

### 6.2 Transaction 1: Cashier Cash Top-Up (500 PKR / 50,000 paisa)
Alice presents 500 PKR cash to the cashier at the Sports Complex reception desk. The cashier verifies the cash and enters receipt `REC-2026-001`.

1. **Transaction Header (`wallet_transactions`):**
   * `id`: `TX-TOPUP-01`
   * `type`: `"CASHIER_CASH_TOPUP"`
   * `reference_id`: `"REC-2026-001"`
   * `description`: `"Cashier cash top-up at front desk"`
2. **Paired Ledger Entries (`wallet_ledger_entries`):**
   * **Leg 1 (System Liability):**
     * `wallet_id`: `L000...` (System Liability)
     * `amount`: `-50000` (Negative: liability to customer increases)
     * `balance_after`: `-50000`
   * **Leg 2 (User Wallet):**
     * `wallet_id`: `A000...` (Alice)
     * `amount`: `+50000` (Positive: personal funds increase)
     * `balance_after`: `+50000`
3. **Zero-Sum Verification:**
   $$(-50000) + (+50000) = 0 \quad \text{[BALANCED]}$$
4. **Alice's Derived Balance:** `50,000` paisa (**500.00 PKR**).

---

### 6.3 Transaction 2: Padel Court Booking Checkout (200 PKR / 20,000 paisa)
Alice books Padel Court 1 for 18:00 tomorrow. The booking fee is 200 PKR.

1. **Transaction Header (`wallet_transactions`):**
   * `id`: `TX-BOOKING-01`
   * `type`: `"PADEL_BOOKING"`
   * `reference_id`: `"BK-PADEL-8899"`
   * `description`: `"Court 1 reservation (18:00 - 19:00)"`
2. **Paired Ledger Entries (`wallet_ledger_entries`):**
   * **Leg 1 (User Wallet):**
     * `wallet_id`: `A000...` (Alice)
     * `amount`: `-20000` (Negative: personal funds debited)
     * `balance_after`: `+30000`
   * **Leg 2 (Sports Revenue):**
     * `wallet_id`: `R000...` (Sports Revenue)
     * `amount`: `+20000` (Positive: facility revenue earned)
     * `balance_after`: `+20000`
3. **Zero-Sum Verification:**
   $$(-20000) + (+20000) = 0 \quad \text{[BALANCED]}$$
4. **Alice's Derived Balance:**
   $$\sum \text{Entries} = (+50000) + (-20000) = 30000 \text{ paisa} \quad (\mathbf{300.00\text{ \textbf{PKR}}})$$
5. **Sports Revenue Balance:** `+20,000` paisa (**200.00 PKR**).

---

### 6.4 Transaction 3: Admin Cancellation & Reversal Refund (200 PKR / 20,000 paisa)
Heavy rain causes court maintenance; Sports Director cancels booking `BK-PADEL-8899` and authorizes a full refund under `FR-06`.

1. **Transaction Header (`wallet_transactions`):**
   * `id`: `TX-REFUND-01`
   * `type`: `"PADEL_BOOKING_REFUND"`
   * `reference_id`: `"BK-PADEL-8899"`
   * `description`: `"Weather cancellation refund for BK-PADEL-8899"`
2. **Paired Ledger Entries (`wallet_ledger_entries`):**
   * **Leg 1 (Sports Revenue):**
     * `wallet_id`: `R000...` (Sports Revenue)
     * `amount`: `-20000` (Negative: revenue returned)
     * `balance_after`: `0`
   * **Leg 2 (User Wallet):**
     * `wallet_id`: `A000...` (Alice)
     * `amount`: `+20000` (Positive: personal funds credited back)
     * `balance_after`: `+50000`
3. **Zero-Sum Verification:**
   $$(-20000) + (+20000) = 0 \quad \text{[BALANCED]}$$
4. **Alice's Restored Derived Balance:**
   $$\sum \text{Entries} = (+50000) + (-20000) + (+20000) = 50000 \text{ paisa} \quad (\mathbf{500.00\text{ \textbf{PKR}}})$$

### 6.5 Synthetic Ledger Trace Table

| Entry ID | Tx ID | Tx Type | Reference ID | Wallet | Signed Amount (Paisa) | Balance After (Paisa) | Created At |
|---|---|---|---|---|:---:|:---:|---|
| `E-01` | `TX-TOPUP-01` | `CASHIER_CASH_TOPUP` | `REC-2026-001` | System Liability | `-50,000` | `-50,000` | `2026-11-09 10:00:00.001` |
| `E-02` | `TX-TOPUP-01` | `CASHIER_CASH_TOPUP` | `REC-2026-001` | Alice Personal | `+50,000` | `+50,000` | `2026-11-09 10:00:00.002` |
| `E-03` | `TX-BOOKING-01` | `PADEL_BOOKING` | `BK-PADEL-8899` | Alice Personal | `-20,000` | `+30,000` | `2026-11-09 10:05:00.001` |
| `E-04` | `TX-BOOKING-01` | `PADEL_BOOKING` | `BK-PADEL-8899` | Sports Revenue | `+20,000` | `+20,000` | `2026-11-09 10:05:00.002` |
| `E-05` | `TX-REFUND-01` | `PADEL_BOOKING_REFUND` | `BK-PADEL-8899` | Sports Revenue | `-20,000` | `0` | `2026-11-09 10:30:00.001` |
| `E-06` | `TX-REFUND-01` | `PADEL_BOOKING_REFUND` | `BK-PADEL-8899` | Alice Personal | `+20,000` | `+50,000` | `2026-11-09 10:30:00.002` |

---

## 7. Proposed Next Chunk: Migration & Tests (Chunk 11B)

*(Proposed design only; not implemented in this chunk.)*

### 7.1 Proposed Migration: `00006_create_wallet_ledger.sql`
The subsequent chunk will introduce migration `backend/migrations/00006_create_wallet_ledger.sql`:
1. Create table `giki_sports.wallets`:
   * Support `PERSONAL`, `SYS_REVENUE`, and `SYS_LIABILITY`.
   * Partial unique index for system wallets on `(name, type)`.
   * Unique index on `user_id` for personal wallets.
2. Create table `giki_sports.wallet_transactions`:
   * Unique index `UNIQUE (type, reference_id)`.
3. Create table `giki_sports.wallet_ledger_entries`:
   * Check constraint `amount <> 0`.
   * Check constraint on personal wallet `balance_after >= 0` to prevent overdrafts.
   * Foreign keys with `ON DELETE RESTRICT`.
   * Timestamp column with `DEFAULT clock_timestamp()`.
4. Install trigger `trg_immutable_ledger_entries` prohibiting `UPDATE` or `DELETE`.
5. Seed default system wallets (`Sports Revenue`, `Cashier Clearing`).

### 7.2 Proposed Automated Verification Tests
A dedicated Go test suite (`backend/internal/wallet/ledger_integration_test.go`) against a disposable PostgreSQL test container will verify:
1. **Zero-Sum Entry Creation:** Both legs insert successfully in a single transaction; unbalanced entry attempts fail.
2. **Derived Balance Equality:** Dynamic `SUM(amount)` exactly matches latest `balance_after`.
3. **Pessimistic Concurrency Test:** 50 concurrent goroutines attempting to debit 1,000 paisa from a wallet containing 10,000 paisa will result in exactly 10 successful debits and 40 `ErrInsufficientFunds` rejections, with final balance exactly `0`.
4. **Replay & Idempotency Test:** Submitting 20 identical `(type, reference_id)` transactions produces exactly 1 transaction header, 2 ledger entries, and 19 handled idempotent rejections (`QR-04`).
5. **Append-Only Trigger Enforcement:** Direct SQL `UPDATE` or `DELETE` statements executed against `wallet_ledger_entries` are rejected by PostgreSQL with exception errors.

