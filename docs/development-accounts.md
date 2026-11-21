# Development Account Provisioning Guide

**Document Reference:** `docs/development-accounts.md`  
**Applies To:** Step 6I Development Account Provisioning CLI  
**Execution Context:** Local development and testing environment only.

---

## 1. Architectural Principles & Isolation

### 1.1 Why Provisioning is a Separate Administrative CLI
In the GIKI Sports Complex Management System, user provisioning is deliberately implemented as a dedicated command-line utility (`backend/cmd/provision-dev-user`) rather than an automated startup hook or a public HTTP endpoint:

1. **Elimination of Attack Surface:**
   - Exposing user registration or administrative provisioning via HTTP endpoints introduces an attack surface that requires complex registration workflows, rate limiting, email verification, and authorization checks.
   - Keeping provisioning out of the HTTP API prevents accidental exposure in staging or production deployments.
2. **Deterministic Startup Lifecycle:**
   - Automated startup hooks (e.g., seeding users on application boot) create severe operational hazards:
     - Race conditions when multiple backend instances start concurrently.
     - Unexpected schema or data mutations during automated deployments or integration tests.
     - The risk of overwriting or resetting accounts in non-development databases if environment variables are misconfigured.
3. **Interactive Credential Hygiene:**
   - Automatic seeds traditionally rely on hardcoded, shared default passwords (e.g., `Password123!`), which frequently leak into version control, documentation, and staging databases.
   - The `provision-dev-user` CLI strictly requires interactive, un-echoed password entry from a live terminal. Passwords are never accepted via command-line flags, environment variables, configuration files, or logs.
4. **Strict Isolation of the Primary Development Database:**
   - The primary development database (`giki_sports_complex`) remains completely untouched (0 users, 0 user roles, 0 sessions) during migrations, automated builds, and test runs.
   - Accounts are created only when the developer explicitly runs the CLI on their local machine and chooses a password.

---

## 2. Target Safeguards & Defensive Constraints

Before prompting for a password or connecting to PostgreSQL, the CLI strictly verifies database targets:

1. **Loopback Host Enforcement:**
   - The database host must resolve to a valid loopback address (`127.0.0.1`, `localhost`, `::1`, or any IP where `ip.IsLoopback()` is true).
   - Any remote IP, cloud hostname, or LAN address is rejected immediately before any network traffic is initiated.
2. **Database Name Enforcement:**
   - The database name must strictly match the designated Sports development database (`giki_sports_complex`).
   - Connecting to other databases (such as `giki_wallet_db`, `postgres`, or staging databases) is immediately rejected.
3. **Explicit Opt-in Flag:**
   - Execution requires an explicit development flag (`--dev` or `--local-dev`).
4. **Safeguard Clarification:**
   - *These target checks are defensive safeguards against accidental misconfiguration, not cryptographic proof of the database's identity.* Developers remain responsible for their local environment configuration.

---

## 3. Account Presets & Role Boundaries

The CLI permits only two predefined synthetic presets. Arbitrary roles, custom emails, and privileged `super_admin` access are strictly disallowed:

| Preset Name | Email Address | Display Name | Assigned Role | Permissions / Boundary |
|---|---|---|---|---|
| `director` | `director@example.test` | Sports Director (Dev) | `sports_director` | Administrative access to facility schedules and booking policies. No cashier authority. |
| `student` | `student@example.test` | Student (Dev) | `student` | Standard user access to view schedules and book available facilities. |

- **Synthetic Domain (`.test`):** RFC 2606 reserves `.test` for testing; synthetic addresses can never collide with real educational emails or deliver outbound mail.
- **Role Assignment:** Roles are verified against the enum `user.Role` and inserted directly into `giki_sports.user_roles`.
- **No Cashier Authority:** Cashier privileges belong strictly to GIKI Wallet and cannot be granted via Sports Complex roles.

---

## 4. Provisioning Execution Commands

To provision local development accounts, open a PowerShell terminal in the repository root and run the commands below.

### 4.1 Provision Sports Director Account
```powershell
cd backend
go run ./cmd/provision-dev-user --dev --preset director
```

**Expected Interaction & Output:**
```text
Database Target:
  Host:     127.0.0.1
  Port:     5434
  Database: giki_sports_complex
  User:     giki_sports_app
  SSLMode:  disable

Target safeguards verified: connection is directed to local loopback and the development database.
Note: These checks are defensive safeguards against accidental misconfiguration, not cryptographic proof of the database's identity.

Enter password for director@example.test: [hidden]
Confirm password: [hidden]

[SUCCESS] User account created successfully.
  User ID:      <uuid>
  Email:        director@example.test
  Display Name: Sports Director (Dev)
  Role:         sports_director
```

### 4.2 Provision Student Account
```powershell
cd backend
go run ./cmd/provision-dev-user --dev --preset student
```

**Expected Interaction & Output:**
```text
Database Target:
  Host:     127.0.0.1
  Port:     5434
  Database: giki_sports_complex
  User:     giki_sports_app
  SSLMode:  disable

Target safeguards verified: connection is directed to local loopback and the development database.
Note: These checks are defensive safeguards against accidental misconfiguration, not cryptographic proof of the database's identity.

Enter password for student@example.test: [hidden]
Confirm password: [hidden]

[SUCCESS] User account created successfully.
  User ID:      <uuid>
  Email:        student@example.test
  Display Name: Student (Dev)
  Role:         student
```

### 4.3 Idempotency & Re-run Behavior
If an account with the specified email already exists:
- The CLI detects the existing record inside the transaction.
- It displays a notice showing the user ID, email, and roles.
- It **does not alter** the stored password hash, account status, or assigned roles.
- No silent promotion or password reset occurs.

---

## 5. Verification Commands (Login & Session Verification)

To verify the newly provisioned accounts against the running backend server (`http://127.0.0.1:8081`), use the following PowerShell commands. These commands test `/api/auth/login` and `/api/auth/me` while safely holding session cookies in memory without printing passwords or raw tokens to the terminal.

> [!NOTE]
> Ensure the backend server is running in another terminal before running verification:
> ```powershell
> cd backend
> go run main.go
> ```

### 5.1 Verify Sports Director Account
```powershell
# 1. Prompt for password securely in memory (not echoed or saved to disk)
$DirectorPass = Read-Host -Prompt "Enter password for director@example.test" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($DirectorPass)
$PlainPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# 2. Authenticate against POST /api/auth/login and capture session cookie in $DirectorSession
$Body = @{
    email    = "director@example.test"
    password = $PlainPass
} | ConvertTo-Json

$LoginRes = Invoke-RestMethod -Uri "http://127.0.0.1:8081/api/auth/login" `
    -Method Post `
    -Headers @{ "Origin" = "http://127.0.0.1:8081" } `
    -ContentType "application/json" `
    -Body $Body `
    -SessionVariable DirectorSession

# 3. Clean up plain password string immediately
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
$PlainPass = $null

# 4. Display safe public user DTO returned by login
Write-Host "Login successful for:" $LoginRes.user.email
Write-Host "Roles:" ($LoginRes.user.roles -join ", ")

# 5. Verify session via GET /api/auth/me using the stored cookie session
$MeRes = Invoke-RestMethod -Uri "http://127.0.0.1:8081/api/auth/me" `
    -Method Get `
    -WebSession $DirectorSession

Write-Host "Me endpoint confirmed identity:" $MeRes.user.email
Write-Host "Display Name:" $MeRes.user.displayName
```

### 5.2 Verify Student Account
```powershell
# 1. Prompt for password securely in memory
$StudentPass = Read-Host -Prompt "Enter password for student@example.test" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($StudentPass)
$PlainPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# 2. Authenticate against POST /api/auth/login and capture session cookie in $StudentSession
$Body = @{
    email    = "student@example.test"
    password = $PlainPass
} | ConvertTo-Json

$LoginRes = Invoke-RestMethod -Uri "http://127.0.0.1:8081/api/auth/login" `
    -Method Post `
    -Headers @{ "Origin" = "http://127.0.0.1:8081" } `
    -ContentType "application/json" `
    -Body $Body `
    -SessionVariable StudentSession

# 3. Clean up plain password string immediately
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
$PlainPass = $null

# 4. Display safe public user DTO returned by login
Write-Host "Login successful for:" $LoginRes.user.email
Write-Host "Roles:" ($LoginRes.user.roles -join ", ")

# 5. Verify session via GET /api/auth/me using the stored cookie session
$MeRes = Invoke-RestMethod -Uri "http://127.0.0.1:8081/api/auth/me" `
    -Method Get `
    -WebSession $StudentSession

Write-Host "Me endpoint confirmed identity:" $MeRes.user.email
Write-Host "Display Name:" $MeRes.user.displayName
```

---

## 6. Summary of Security & Verification Guarantees

- **No Credential Leakage:** Raw passwords and session cookies are never printed to the console or written to logs.
- **Production Argon2id Parameters:** Hashes use the RFC 9106 recommended parameters (64 MiB memory, 3 iterations, 4 parallelism threads) matching production runtime behavior.
- **Database Safety:** Automated test suites run exclusively against ephemeral disposable databases (`giki_sports_disposable_devuser_*`) and destroy them immediately after testing.
- **Unmutated Development Database:** Running `go test` does not populate `giki_sports.users` or `giki_sports.sessions`. The primary development database remains empty until the developer executes the CLI.

