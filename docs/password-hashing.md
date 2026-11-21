# Password Hashing and Verification Specification (Step 6B)

**Document Reference:** `docs/password-hashing.md`  
**Milestone:** Step 6B (Argon2id Password Hashing and Verification)  
**Applicable Standards:** `requirements-baseline.md` (FR-01, QR-13, CR-05)  
**Package:** `backend/internal/auth`

---

## 1. Executive Summary & Purpose

Step 6B implements salted Argon2id password hashing and constant-time verification in Go, fulfilling requirements FR-01 and QR-13.

In this chunk:
- Passwords are encrypted neither at rest nor in transit through reversible ciphers; they are hashed using **Argon2id**, a one-way memory-hard key derivation function.
- The implementation strictly avoids storing plaintext passwords, salts in isolation, or unauthenticated parameters.
- It parses incoming stored hashes defensively **before** initiating expensive cryptographic key derivation, preventing algorithmic denial-of-service (DoS) attacks.
- Scope is strictly limited to cryptographic hashing and verification: it introduces no database connections, HTTP routes, repositories, or frontend changes.

---

## 2. GIKI Wallet Codebase Inspection & Adaptation

Before writing the implementation, password handling in `giki-wallet/backend/internal/auth/` was inspected:
- **Wallet Implementation (`service.go:489-495`):**
  ```go
  func HashPassword(password string) (string, error) {
      hashPassword, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
      if err != nil {
          return "", err
      }
      return string(hashPassword), nil
  }
  ```
- **What Was Reused / Adapted:**
  - The clean, high-level functional boundaries: `Hash(password string) (string, error)` and `Verify(password, encodedHash string) (bool, error)`.
  - The pattern of returning controlled errors rather than panicking on unexpected inputs.
- **What Was Replaced and Why:**
  - **Bcrypt was replaced with Argon2id (`golang.org/x/crypto/argon2`):** As mandated by QR-13 and CR-05, Argon2id provides superior resistance against offline brute-force cracking using specialized GPU and ASIC hardware due to its configurable memory hardness.
  - **Dependencies Excluded:** The Sports password package imports only Go standard libraries (`crypto/rand`, `crypto/subtle`, `encoding/base64`, `errors`, `fmt`, `io`, `strconv`, `strings`) and `golang.org/x/crypto/argon2`. Wallet's JWT token, worker, transport, and payment dependencies were completely excluded.

---

## 3. Encoded Hash Format & Parameter Choices

### 3.1 Standard Encoded String Format
Derived hashes are formatted as self-contained strings adhering to RFC 9106 conventions:

```
$argon2id$v=19$m=65536,t=3,p=4$<base64-salt>$<base64-hash>
```

- **`$argon2id$`:** Algorithm identifier.
- **`v=19`:** Algorithm version (Argon2 v1.3 / version 0x13).
- **`m=65536`:** Memory cost in kibibytes (KiB).
- **`t=3`:** Time cost / number of iterations over memory.
- **`p=4`:** Parallelism / number of independent computing lanes/threads.
- **`<base64-salt>`:** Raw standard base64 encoding (without `=` padding) of the random salt.
- **`<base64-hash>`:** Raw standard base64 encoding of the derived key.

### 3.2 Parameter Configuration

| Parameter | Unit | Production Value (`DefaultParams`) | Test Value (`TestParams`) | Resource Cost & Rationale |
|---|:---:|:---:|:---:|---|
| **Memory (`m`)** | KiB | `65536` (64 MiB) | `8192` (8 MiB) | Memory hardness forces attackers to allocate 64 MiB of RAM per concurrent guessing trial, making parallel ASIC/GPU attacks prohibitively expensive. |
| **Iterations (`t`)** | Passes | `3` | `1` | Number of sequential passes across the allocated memory buffer, increasing computational cost linearly. |
| **Parallelism (`p`)** | Threads | `4` | `2` | Number of concurrent execution lanes. Allows multi-threaded execution while bounding OS thread contention. |
| **Salt Length** | Bytes | `16` (128 bits) | `16` (128 bits) | High-entropy cryptographic randomness drawn from `crypto/rand`, ensuring identical passwords generate globally unique hashes. |
| **Key Length** | Bytes | `32` (256 bits) | `32` (256 bits) | Length of the output derived authentication digest. |

> [!NOTE]
> Parameter choices reflect deliberate implementation baselines balancing hardware brute-force defense with server concurrency, not measured benchmark performance claims. Production parameters remain unchanged.

> [!IMPORTANT]
> Cryptographic salts eliminate precomputed dictionary and rainbow-table attacks across multiple accounts, but **salts do not prevent offline password guessing**. An adversary possessing an exported salt and hash can still execute targeted dictionary or brute-force candidate searches against that specific hash. Argon2id's memory hardness raises the computational and hardware costs of each guess, but does not render guessing impossible.

---

## 4. Defensive Parsing & Resource Bounds

To prevent untrusted or corrupted database hashes from exhausting server CPU or memory, `ParseHash` inspects and validates the hash **before** executing Argon2 computations:

1. **Length Bounds:**
   - Encoded hash input length capped at `512` characters.
   - Plaintext password input technical bound capped at `1024` bytes (`ErrPasswordTooLong`) to prevent algorithmic DoS via massive strings.
2. **Algorithm & Version Enforcement:**
   - Must match `"argon2id"` exactly; rejects `"bcrypt"`, `"argon2i"`, and `"argon2d"` with `ErrUnsupportedAlgorithm`.
   - Must match version `19` (`ErrUnsupportedVersion`).
3. **Parameter Integrity:**
   - Requires exactly three distinct parameters (`m`, `t`, `p`). Duplicate keys (e.g. `m=65536,m=65536`) and missing keys are rejected with `ErrInvalidHashFormat`.
4. **Parameter Resource Bounds (`ErrExcessiveParameters`):**
   - Memory must be between `8192` KiB (8 MiB) and `262144` KiB (256 MiB). Hashes requesting excessive memory (e.g. 1 GiB) are rejected before memory allocation.
   - Iterations must be between `1` and `10`.
   - Parallelism must be between `1` and `16`.
   - Salt and key lengths must be between `16` and `64` bytes.

> [!NOTE]
> Parameter bounds prevent an individual malformed or hostile hash from demanding unbounded server memory or CPU time during verification. However, **parameter bounds do not eliminate aggregate resource-exhaustion risk**. A sustained flood of verification requests using valid, bounded parameters can still saturate server CPU and memory. Application-level rate limiting, concurrency bounding, and IP throttling are required in the HTTP layer to address aggregate exhaustion.

5. **Exact Input Preservation:**
   - Passwords are **never** trimmed, truncated, or lowercased. Whitespace and multibyte UTF-8 characters are preserved exactly.
6. **Constant-Time Comparison:**
   - Verification uses `crypto/subtle.ConstantTimeCompare`, preventing side-channel timing attacks that infer correct characters based on comparison latency.
7. **Zero Secret Logging:**
   - Passwords, cryptographic salts, and complete password hashes are never logged.

---

## 5. Error Behavior

| Error Variable | Cause / Condition |
|---|---|
| `ErrInvalidHashFormat` | Input is empty, exceeds 512 chars, missing fields, non-numeric values, duplicate keys, or invalid base64. |
| `ErrUnsupportedAlgorithm` | Algorithm identifier is not `argon2id` (e.g. `bcrypt` or `argon2i`). |
| `ErrUnsupportedVersion` | Version identifier is not `19`. |
| `ErrExcessiveParameters` | Memory, iteration, or parallelism parameters fall outside defined safety bounds. |
| `ErrPasswordTooLong` | Password exceeds technical ceiling of 1024 bytes. |
| `ErrSaltGenerationFailed` | System randomness source (`crypto/rand`) fails to deliver requested salt bytes. |
| `ErrInvalidParams` | Custom parameters fail validation constraints. |

---

## 6. Automated Unit Test Verification

The test suite in [`backend/internal/auth/password_test.go`](file:///d:/giki%20sports%20complex/backend/internal/auth/password_test.go) exercises both fast synthetic parsing checks and real cryptographic round trips:

| Test Name | Focus | Result |
|---|---|:---:|
| `TestPassword_HashAndVerify_CorrectPassword` | Round-trip validation: matching password verifies to `true`. | **Passed** |
| `TestPassword_HashAndVerify_IncorrectPassword` | Incorrect password returns `(false, nil)` without error. | **Passed** |
| `TestPassword_Salting_DifferentHashesForIdenticalPasswords` | Two hashes of identical passwords yield different encoded strings. | **Passed** |
| `TestPassword_PreservesWhitespaceAndUnicode` | Preserves leading/trailing spaces, internal tabs, RTL Urdu, and emojis. | **Passed** |
| `TestPassword_DefensiveParsing_MalformedAndUnsupportedHashes` | 16 malformed/unsupported format cases rejected without panics. | **Passed** |
| `TestPassword_DefensiveParsing_ExcessiveResourceParametersRejected` | 6 out-of-bounds parameter cases rejected before Argon2 allocation. | **Passed** |
| `TestPassword_SaltGenerationFailure` | Faulty entropy reader returns `ErrSaltGenerationFailed` cleanly. | **Passed** |
| `TestPassword_TechnicalLengthBound` | Passwords $> 1024$ bytes rejected with `ErrPasswordTooLong`. | **Passed** |
| `TestPassword_ProductionDefaultsRoundTrip` | Exercises full production parameters (64 MiB, 3 passes, 4 threads). | **Passed** |

### Execution Command & Results
```bash
go test -v -count=1 ./internal/auth/...
```
**Result:** All tests passed in **~1.6s** (production round-trip executed in ~0.34s; all parsing tests completed in $< 0.01$s).

> [!NOTE]
> Test execution timings (e.g. ~0.34s for production parameters) are local empirical observations on this specific development host, not contractual latency guarantees. Actual execution latency varies depending on host CPU architecture, concurrent workload, and available hardware threads.

---

## 7. Remaining Boundaries
- **No Database Interaction:** Step 6B does not query `giki_sports.users` or execute SQL.
- **No Session Tokens:** Token generation and session management remain separate (Step 6C).
- **No HTTP Handlers:** Login/register endpoints, cookies, and middleware will be added in subsequent milestones.
