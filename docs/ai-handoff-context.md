# GIKI Sports Complex — AI Continuation Context

**Purpose:** This is a detailed handoff for another AI continuing this chat. It describes the product, repository, work already completed, user preferences, verified behaviour, known pitfalls, and the safest next steps. Treat the code and tests as the source of truth if this document ever conflicts with them.

## 1. User and collaboration style

The user is building the entire GIKI Sports Complex web app personally. They use **Antigravity** to make code changes, and use Codex as a reviewer, planner, debugger, and prompt writer.

The preferred workflow is deliberately incremental:

1. Inspect the current code and relevant requirements/docs.
2. Give **one small, independent, well-scoped prompt** for Antigravity.
3. The prompt must tell Antigravity to stop after that chunk, run relevant tests, and give a final teaching section named **Understand this chunk**.
4. The user pastes Antigravity's result back into this chat. Review it before choosing the next step.
5. Explain problems in plain language, including manual browser verification steps when useful.

Do not try to build the whole system in one prompt. The user learns as they go and explicitly wants explanations of *what changed and why* in each chunk. They own all modules; ignore any older plan that assigned module ownership to different teammates.

The repository includes a previous "giki-wallet" project. It is only a **reference**. It is acceptable to adapt carefully selected patterns, but do **not** modify "giki-wallet/", blindly copy its schema/security assumptions, or introduce its old bcrypt/default-password seed approach.

Never reveal or assume a password for the demo accounts. The user set them interactively.

## 2. Repository and local environment

Workspace root:

~~~
D:\giki sports complex
~~~

Main folders:

~~~
backend/       Go backend (Fiber + PostgreSQL)
frontend/      React + Vite + TypeScript app
giki-wallet/   reference project; must remain unchanged
docs/          requirements, API notes, baseline, design docs, and this handoff
backend/migrations/
~~~

Local development stack:

| Component | Expected local endpoint / command note |
| --- | --- |
| PostgreSQL Docker service | Compose service "db"; Sports database is local and mapped to port **5434** |
| Go Sports backend | http://127.0.0.1:8081 (**not 8080**) |
| Vite frontend | http://localhost:5173 |
| Vite API proxy | targets http://127.0.0.1:8081 |

After Go code changes, the backend process may be stale. Rebuild/restart it before interpreting a browser/API test failure as an implementation bug. Several earlier apparent frontend failures were actually caused by the stale Go process.

Useful baseline documents to inspect before proposing future work:

- docs/requirements-baseline.md
- docs/development-baseline.md
- docs/implementation-plan.md
- docs/facility-api.md
- docs/wallet-ledger-design.md

The database migrations currently include:

~~~
00001  base Sports schema
00002  facilities and schedules
00003  users, roles, and sessions
00004  audit logs
00005  content items
00006  wallet ledger tables
00007  padel booking and slot inventory tables
00008  gym memberships tables
~~~

## 3. Authentication and authorization — completed

Sports has its own secure authentication implementation, informed by the Wallet project but deliberately changed where necessary:

- Passwords use **Argon2id**, not the Wallet project's old bcrypt seed hashes.
- Sessions are server-side opaque tokens: 32 random bytes, base64url cookie value, SHA-256 hash stored server-side.
- Session policy: 30-minute idle expiry and 8-hour absolute expiry.
- Auth endpoints include login, current-user ("/api/auth/me"), and logout.
- Cookies, trusted Origin validation, CSRF-origin checks for mutations, basic rate limiting, and a concurrency cap are implemented.
- RequireAuth and role middleware protect mutation routes. The relevant high-authority roles are "sports_director" and "super_admin".

Development account provisioning is intentionally a separate local CLI, not a registration endpoint or boot-time seed:

~~~powershell
cd backend
go run ./cmd/provision-dev-user --dev --preset student
go run ./cmd/provision-dev-user --dev --preset director
~~~

It prompts for a password twice without echoing it. Presets map to "student@example.test" / role "student" and "director@example.test" / role "sports_director". It restricts itself to a loopback host and the "giki_sports_complex" database. Existing accounts are not silently modified or promoted.

## 4. Facilities and operating schedules — completed and manually verified

Facilities and weekly operating windows are stored in PostgreSQL and presented publicly in the frontend. The backend and UI support role-controlled schedule management:

- Public facility list/detail and schedule reads.
- Sports Director / Super Admin may create, edit, and delete weekly schedule windows.
- Students and logged-out visitors can view schedules but cannot see management controls.
- Each schedule mutation is protected and produces an audit record atomically.
- UI supports error states and a delete-confirmation flow.

The user manually verified these flows in a normal and private window:

- As **student**, no edit/delete actions were available.
- As **director**, editing a time worked and was visible publicly.
- Adding/editing/deleting a window worked for a director.
- After an initially failed deletion, the user confirmed deletion ultimately worked successfully.

There are local demo facilities such as "demo-badminton-court" and "demo-table-tennis". A temporary "delete-check-..." test facility may remain in the developer database; it is test data, not product content.

### Important PowerShell pitfall already encountered

The user once pasted/executed only the SQL here-string while "$slug" was never assigned in that shell. PostgreSQL therefore literally inserted the slug "$slug", and the browser opened "/facilities/$slug", producing "Facility Not Found."

If future manual fixture instructions use "$slug", give the assignment and the SQL in the **same PowerShell block/session** and ensure the output URL contains the resolved random slug, not the literal characters "$slug".

## 5. Achievements and announcements (content lifecycle) — completed

The content system was implemented incrementally as a draft/publish lifecycle in shared "content_items" storage:

- Migration "00005_create_content_items".
- Draft creation, updates, author-scoped draft listing, and publishing.
- Public read APIs for announcements and achievements.
- Director/super-admin protected authoring APIs.
- Publish action creates an audit record.
- Frontend draft list/editor and publish UI, including modal keyboard handling.
- The homepage now reads the public content APIs through "AnnouncementsSection" and "AchievementsSection".
- Legacy unauthenticated write routes were retired:
  - POST /api/achievements
  - POST /api/announcements
  - DELETE /api/achievements/:id

The older legacy GET routes may still exist for compatibility, but the homepage should no longer use them.

The user initially reported that a published announcement was not visible. It was subsequently checked: a published test announcement existed in the database, appeared in the public announcements API, and had one "content.publish" audit record. If that symptom recurs, first inspect the actual frontend query, backend process freshness, and browser cache rather than immediately changing the data model.

The editor was deliberately designed as a social-style composer at one point. The user correctly noticed it showed a single input and only "Post," rather than distinct title/body and save-as-draft controls. This needs product/UI attention if the requirements require separate title and body fields. Do not claim that one composer input distinguishes title from body. Inspect current code and requirements before deciding whether the UI has since been corrected.

## 6. Wallet ledger — completed through Step 11G

### 6.1 Design decision

"docs/wallet-ledger-design.md" recommends a **Sports-owned local double-entry ledger** for local development and in-app checkout. A future production decision between a unified GIKI Wallet integration and a separate Sports balance remains open. Do not imply that the current Sports wallet transfers real money or calls a production Wallet system.

### 6.2 Storage and invariants

Migration "00006_create_wallet_ledger.sql" creates:

- "wallets"
- "wallet_transactions"
- "wallet_ledger_entries"

Key design points:

- Amounts are BIGINT **paisa**, never floating point.
- Transactions are append-only; triggers reject update/delete/truncate of ledger records.
- Balance is derived from ledger entry sums; there is no mutable balance column.
- A valid posted transfer has a header and balanced legs whose sum is zero.
- Personal senders cannot overdraw.
- An idempotency key is "(type, reference_id)".
- Deterministic wallet locking is used to prevent AB/BA wallet-lock cycles. It does **not** magically prevent every possible database deadlock.

### 6.3 Completed service/API/frontend work

Implemented in "backend/internal/wallet/":

- Atomic double-entry PostTransaction behavior.
- Idempotency: replay with exactly matching data returns the original transaction; incompatible reuse conflicts.
- A later race fix added PostTransactionWithResult, returning transaction ID plus AlreadyPosted, so a concurrent same-reference retry returns the original transaction instead of incorrectly reporting insufficient funds after the first caller spends the available amount.
- Owner-scoped read functions for a wallet's derived balance and latest 50 activity records.

Authenticated endpoint:

~~~
GET /api/wallet/me
~~~

It returns the signed-in user’s wallet only. For no wallet it returns {"wallet":null,"activity":[]}. It serializes paisa as strings to avoid JavaScript number precision loss. It does not expose counterparty/internal references.

Frontend:

- "/wallet" page is implemented.
- Signed-in navigation includes "My wallet."
- The page uses BigInt-safe formatting and has no-wallet, zero-balance, and funded states.
- A reported test run passed 148 Vitest tests across 8 suites, and the production frontend build passed.

### 6.4 Step 11G — local test-wallet funding CLI (just completed by Antigravity)

Antigravity's latest reported implementation added:

~~~
backend/cmd/fund-dev-wallet/main.go
backend/internal/devwallet/fund.go
backend/internal/devwallet/fund_integration_test.go
~~~

It reports the following behaviour:

- Requires "--dev"/"--local-dev" and "--preset student|director".
- Reuses loopback and Sports-database target safeguards.
- Looks up the already-provisioned preset account and fails if it is missing/inactive; it never creates a user.
- Finds or safely creates the user's PERSONAL PKR wallet and one SYS_LIABILITY clearing wallet named "Dev Test Credit Clearing".
- Funds a fixed synthetic **50,000 paisa / PKR 500.00** by calling the wallet service, never by direct ledger insertion.
- Uses transfer type "DEV_TEST_CREDIT" and a stable user-specific reference "DEV_CREDIT_<user ID>".
- A rerun returns the original transaction rather than adding funds again, even after the user has spent part of the credit.
- Wallet creation and transaction posting are intentionally separate transactions. If the second step fails, an empty wallet can remain, but no ledger entries are written and retry is safe.

Reported integration coverage includes: first run, rerun, partial-spend rerun, concurrent calls, missing/inactive account, posting failure with zero ledger entries, and owner balance/history. Reported checks: wallet integration/unit tests, "go vet ./...", "go build ./...", backend tests, frontend tests, and frontend build all passed. Antigravity also reported the developer database was untouched at the time of its verification.

**This reported Step 11G work should be code-reviewed before a sensitive follow-on change.** It was not independently rerun in this chat after Antigravity’s final report.

The user may manually fund a local preset account only when they choose to do so:

~~~powershell
cd backend
go run ./cmd/fund-dev-wallet --dev --preset student
~~~

Then, after signing in as that same user, "/wallet" should show "PKR 500.00", an active PKR wallet, and a "+PKR 500.00" DEV_TEST_CREDIT/"Wallet Top-Up" activity. Do **not** run this command against the user’s development database on their behalf unless they explicitly ask. It mutates their local DB, even though it is designed to be safe and local-only.

## 7. Audit, testing, and safety conventions

### Audit conventions

Audit logging exists in migration 00004. Use the actual schema fields:

- "actor_id"
- "target_type"
- "target_id"
- "details"
- status and "created_at"

Do not invent outdated fields such as "changes", "entity_id", or "previous_state".

For state-changing domain actions, preserve the existing pattern: validate -> execute domain mutation -> write audit record in the **same transaction**, where the action needs atomic auditability.

### Verification expectations

For each Antigravity prompt, require targeted tests first, then proportional broader checks. Examples:

~~~powershell
cd backend
go test ./...
go test -tags=integration ./...
go vet ./...
go build ./...

cd ..\frontend
npm test -- --run
npm run build
~~~

Do not blindly require every long integration suite for a purely visual frontend change, but require enough evidence for the scope. Test databases should be disposable. Never use destructive database reset commands against the development DB merely to make tests pass.

### Security rules to preserve

- Mutating HTTP actions must keep Origin/CSRF/auth/role checks.
- Server authorization is authoritative; hiding a frontend button is not authorization.
- Keep monetary amounts in integer paisa from database through API and UI formatting.
- Never use floats for balances/prices.
- Do not create public registration or public wallet funding endpoints as a shortcut.
- Do not expose sessions, token hashes, password hashes, internal wallet/clearing references, or other users’ balances.
- Never add a real payment integration or live Wallet dependency without a confirmed product decision.

## 8. Prior inaccurate statements/pitfalls to correct if they reappear

1. **Backend port:** the Sports backend is **8081**, not 8080.
2. **Provisioning CLI:** exact form is "go run ./cmd/provision-dev-user --dev --preset student" (or director).
3. **Passwords:** there is no known static demo password. The user chose their own password at provisioning time.
4. **Wallet scope:** current funding is synthetic developer credit, not a payment/top-up system.
5. **Legacy Wallet:** reuse patterns only; leave "giki-wallet/" untouched.
6. **PowerShell variables:** ensure "$slug" or similar variables are assigned in the same session before using them in SQL/URLs.
7. **Stale processes:** restart/rebuild the Go server after backend edits before debugging client symptoms.
8. **Test reporting:** Antigravity sometimes gives inconsistent counts or overly broad claims. Read actual output when high confidence matters.

## 9. Recommended continuation point

### Immediate human verification (optional)

The logical next user action, if they want to see the wallet UI with funds, is:

1. Confirm the desired preset user already exists.
2. Run "go run ./cmd/fund-dev-wallet --dev --preset student" from "backend".
3. Sign in as that same account and browse to "/wallet".
4. Re-run the command once if they want to verify idempotency: it should say the credit already exists and must not increase the balance.

This is a local, intentional database mutation; only guide the user through it after reminding them of that fact.

### Next development milestone

**Padel Court Booking (Phase 6 / Steps 12A–12I)** is fully implemented and verified.

**Gym Membership Management (Module 4, Phase 7)** is fully implemented and verified.

**Unified Facility Architecture & Landing Page Polish** is fully implemented and verified:
- Replaced misleading duplicate CTAs ("Book a Slot" & "View Schedule" jumping to general facilities) with clean university branding, purpose statement, and explicit action buttons.
- Removed redundant middle stats/utility strip between the Hero and the Facilities catalog, allowing visitors to land directly on the facilities directory without duplicate cards.
- Redesigned `FacilityCard.tsx` with unified taxonomy distinguishing access modes:
  - Advance Online Booking (`glass-padel-arena`): `Online Booking` badge + direct "Book Court Slot" action button to `/padel`.
  - 30-Day Membership Pass (`central-fitness-gym`): `30-Day Pass` badge + direct "Get / Renew Pass" action button to `/membership`.
  - Timetable Governed (Badminton, Pool, Squash, Tennis, Futsal, Table Tennis): `View Schedule` action + `Women-Only Hours` badge when applicable.
- Redesigned `FacilitiesGrid.tsx` with interactive text search (by name, sport, or location), Category tabs (`All`, `Padel`, `Gym`, `Racket & Indoor`, `Aquatic & Outdoor`), and Audience timing filters (`Student`, `Faculty`, `Women-Only`).
- Added prominent access callout banners on `FacilityDetail.tsx` for Padel court booking and Gym membership passes.
- Idempotent database seeding (`cmd/seed --campus`) added in `backend/internal/seed/campus_facilities.go`, populating all 8 authentic GIKI campus facilities and 50 weekly schedule windows into PostgreSQL, covered by `campus_integration_test.go`.
- All 11 frontend test suites (166 tests) and backend integration tests are 100% passing.

The natural next product progression is **Event Management & Conflict Resolution (Module 7)** or **JazzCash Adapter (Module 5)**.

## 10. How the next AI should respond

- Lead with the current result or diagnosis, not a generic plan.
- Be compact but educational; the user appreciates plain-language explanations.
- When the user pastes an Antigravity report, identify both the claimed changes and anything that needs independent confirmation.
- If asked "what prompt next?", provide a single copy-ready prompt (or clearly labeled sequential prompts only when a deliberate split is necessary).
- Each coding prompt should include: scope, existing files to inspect, explicit non-goals, security/concurrency rules, required tests, no commits/pushes, and a final "Understand this chunk" section.
- Do not change the workspace yourself when the task is simply review/planning unless the user explicitly asks you to implement a fix. Diagnostic, read-only commands are okay.

## 11. Current status snapshot

| Area | Status |
| --- | --- |
| Database/migrations | Through 00008 (gym memberships tables) |
| Auth, roles, sessions | Complete and manually used |
| Facility/schedule viewing and director management | Complete and manually verified |
| Announcements/achievements draft-to-publish | Complete; public homepage cutover done |
| Audit logging | In use for key mutations |
| Wallet ledger and owner read API | Complete with tests reported passing |
| Wallet frontend | Complete with tests/build reported passing |
| Local one-time test credit CLI | Complete (`cmd/fund-dev-wallet`) |
| Padel booking backend & concurrency engine | Complete (Steps 12A–12H) with all unit & integration tests passing |
| Padel booking frontend client | Complete (Step 12I) with Vitest tests and production build passing |
| Gym membership management | Complete (Phase 7 / Chunks 7.1–7.3) with all unit & integration tests passing |
| Unified Facility Taxonomy & Landing Page | Complete with search, category tabs, utility cards & 8 authentic facilities seeded |
| Event management & conflict resolution | Planned (Module 7) |

