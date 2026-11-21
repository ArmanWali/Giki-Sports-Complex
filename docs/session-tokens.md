# Opaque Session-Token Generation and Hashing Specification (Step 6C)

**Document Reference:** `docs/session-tokens.md`  
**Milestone:** Step 6C (Opaque Session-Token Generation and Hashing)  
**Applicable Standards:** `requirements-baseline.md` (FR-01, QR-13, CR-05), `docs/auth-data-model.md`  
**Package:** `backend/internal/auth`

---

## 1. Executive Summary & Purpose

Step 6C implements cryptographically secure, opaque session token generation, format validation, and SHA-256 digest derivation in Go, fulfilling the bearer token requirements of FR-01, QR-13, and `docs/auth-data-model.md`.

In this chunk:
- Session tokens are **opaque 256-bit cryptographic bearer identifiers**, not structured or client-decodable tokens (such as JWTs).
- The raw token is generated for future transmission to the browser client (via secure HTTP cookies in Step 6E).
- The token hash is derived for future persistence in `giki_sports.sessions.token_hash` (Step 6D).
- The package strictly validates canonical token syntax prior to hashing, rejecting malformed, padded, or non-canonical strings.
- Implementation scope is strictly bounded: it does not query PostgreSQL, track idle/absolute session expiry, manage HTTP requests, or alter frontend code.

---

## 2. GIKI Wallet Codebase Inspection & Adaptation

Before implementing, random token and SHA-256 utilities in the GIKI Wallet codebase were inspected:

### 2.1 Inspected Source Paths & Functions
1. **`giki-wallet/backend/internal/auth/service.go`**:
   - `generateBase64Token(n int) (string, error)` (lines 481–487):
     ```go
     func generateBase64Token(n int) (string, error) {
         b := make([]byte, n)
         if _, err := io.ReadFull(rand.Reader, b); err != nil {
             return "", err
         }
         return base64.URLEncoding.EncodeToString(b), nil
     }
     ```
   - `sha256Hex(s string) string` (lines 374–377):
     ```go
     func sha256Hex(s string) string {
         sum := sha256.Sum256([]byte(s))
         return hex.EncodeToString(sum[:])
     }
     ```
2. **`giki-wallet/backend/internal/user/service.go`**:
   - `generateBase64Token(n int) (string, error)` (lines 185–195): identical pattern using `base64.URLEncoding`.
   - `sha256Hex(s string) string` (lines 197–200): identical SHA-256 lowercase hex formatting.

### 2.2 What Was Reused / Adapted
- **Entropy Ingestion:** Used `io.ReadFull` to ensure full entropy buffers are read without silent partial reads.
- **SHA-256 Hex Formatting:** Adapted the clean `sha256.Sum256` digest calculation formatted with `hex.EncodeToString(sum[:])`.

### 2.3 What Changed and Why
- **Unpadded URL-Safe Base64 (`base64.RawURLEncoding`):** Wallet used standard `base64.URLEncoding`, which appends `=` padding characters (yielding 44 characters for 32 bytes). Sports adopts unpadded URL-safe Base64 (`base64.RawURLEncoding`), generating clean 43-character URL-safe strings without padding artifacts.
- **Strict Canonical Validation:** Wallet had no token syntax validation. Sports implements `ValidateSessionToken`, enforcing exact character length (43), URL-safe alphabet, no padding, and strict canonicity (re-encoding decoded bytes must match input exactly to prevent non-canonical bit malleability).
- **Injectable Entropy Source:** Added `GenerateSessionTokenWithReader(io.Reader)` allowing deterministic unit tests with known vectors while preserving `crypto/rand.Reader` as the strict production default.
- **Controlled Error Safety:** All error returns use static sentinel errors. Candidate tokens are never interpolated or logged in error messages.
- **Complete Isolation:** Wallet dependencies (JWT, email worker, database queries, payment gateway) were completely omitted. The `giki-wallet` directory was left completely untouched.

---

## 3. Token & Stored Hash Formats

### 3.1 Raw Session Token
- **Entropy:** 32 cryptographically secure random bytes (256 bits of entropy) drawn from `crypto/rand`.
- **Encoding:** Unpadded URL-safe Base64 (`base64.RawURLEncoding`), character set `[A-Za-z0-9_-]`.
- **Length:** Exactly 43 ASCII characters ($\lceil 32 \times 8 / 6 \rceil = 43$).
- **Client Delivery:** Intended for future client transmission as an `HttpOnly`, `SameSite=Lax`, `Secure` cookie.
- **Encoding Rationale:** Unpadded Base64url is selected as a convenient, uniform transport encoding across HTTP headers, URLs, and cookies because it eliminates characters (`+`, `/`, `=`) that risk delimiter confusion or require percent-encoding. Standard Base64 is not universally invalid in HTTP cookies (RFC 6265 permits base64 characters in cookie values), but unpadded Base64url provides a clean, delimiter-free representation.

### 3.2 Stored Token Hash
- **Algorithm:** SHA-256 cryptographic hash function.
- **Encoding:** Lowercase hexadecimal string (`hex.EncodeToString`).
- **Length:** Exactly 64 hexadecimal characters ($32 \text{ bytes} \times 2 = 64$).
- **Database Contract:** Matches PostgreSQL column `giki_sports.sessions.token_hash VARCHAR(255) NOT NULL UNIQUE`.

> [!NOTE]
> Storing SHA-256 token hashes reduces exposure during a read-only database leak: an adversary obtaining snapshot read access to PostgreSQL cannot directly present stored SHA-256 hashes as bearer credentials. However, token hashing does not prevent session compromise in every database-compromise scenario (e.g., an attacker with read-write database privileges can overwrite `token_hash` with a digest of their own chosen token, or modify account roles directly), nor does it prevent session theft via client-side cookie interception or transport tampering.

### 3.3 Hashing Convention
> [!IMPORTANT]
> **Token Hashing Convention:**  
> In this implementation, SHA-256 hashing operates directly on the **canonical ASCII bytes of the unpadded URL-safe Base64-encoded token string** (`[]byte(rawToken)`), **not** on the decoded 32-byte entropy slice.  
> 
> **Rationale:**
> 1. Directly matches GIKI Wallet's `sha256Hex(token)` pattern.
> 2. Enables direct database lookups: incoming HTTP bearer tokens can be validated and hashed directly without performing an intermediate Base64 decode step.
> 3. Because `ValidateSessionToken` strictly enforces canonical encoding, there is an exact 1-to-1 bijection between the 43-character token string and the underlying 32 bytes of entropy.

---

## 4. Strict Validation & Error Guarantees

Before hashing any incoming token for database lookup, `HashSessionToken` invokes `ValidateSessionToken(token)` to enforce strict structural invariants:

1. **Non-Empty:** Rejects empty string (`ErrTokenEmpty`).
2. **Exact Length:** Rejects any input where `len(token) != 43` (`ErrInvalidTokenLength`).
3. **No Padding:** Rejects any input containing `=` (`ErrInvalidTokenFormat`).
4. **URL-Safe Base64 Alphabet:** Rejects non-base64 characters, whitespace, standard Base64 `+` and `/` (`ErrInvalidTokenFormat`).
5. **Decoded Byte Count:** Must decode to exactly 32 bytes (`ErrInvalidTokenLength`).
6. **Canonical Encoding:** The decoded 32 bytes are re-encoded with `base64.RawURLEncoding.EncodeToString`. If the output differs from the input token, the token contains non-zero unused bits and is rejected (`ErrNonCanonicalToken`).
7. **No Trimming or Normalization:** Tokens are never trimmed, altered, or normalized. Leading or trailing whitespace is preserved and causes immediate rejection.
8. **Zero Secret Leakage:** Error messages never format, reflect, or print candidate tokens.

> [!NOTE]
> `ValidateSessionToken` validates **format only**. It does not check whether a session exists in PostgreSQL, whether the session has expired (idle or absolute), whether it was revoked, or what user identity it belongs to. Database session evaluation occurs in Step 6D.

---

## 5. Automated Unit Test Verification

The test suite in [`backend/internal/auth/token_test.go`](file:///d:/giki%20sports%20complex/backend/internal/auth/token_test.go) exercises formatting, determinism, validation, and error safety:

| Test Name | Focus | Result |
|---|---|:---:|
| `TestToken_GenerateSessionToken_FormatAndLength` | Verifies 43-char token, 64-char hex hash, 32-byte decoded entropy, validation success, and recomputed hash match. | **Passed** |
| `TestToken_DeterministicEntropy_KnownVectors` | Tests 32 zero bytes (produces 43 'A's) and sequential bytes (0x00..0x1F) against independent SHA-256 calculations. | **Passed** |
| `TestToken_HashSessionToken_RepeatedCallsConsistent` | Verifies repeated hashing of a token produces idempotent digests across 5 iterations. | **Passed** |
| `TestToken_Validation_RejectsInvalidFormats` | 11 subtests verifying rejection of empty string, short (42), long (44), padded (`=`), `+`, `/`, internal/leading/trailing whitespace, punctuation, and non-canonical base64. | **Passed** |
| `TestToken_EntropySourceFailures` | Verifies nil reader, simulated hardware error reader, and short-read (16 bytes) reader return `ErrEntropyReadFailed`. | **Passed** |
| `TestToken_ErrorsDoNotLeakSubmittedToken` | Confirms sensitive candidate token strings are never present in returned error messages. | **Passed** |

> [!NOTE]
> Passing sample uniqueness or format tests demonstrates correct formatting and entropy handling in the test environment; it is not a formal mathematical proof of global cryptographic security.

---

## 6. Remaining Boundaries

- **No Database Persistence:** Step 6C does not execute SQL or interact with PostgreSQL `sessions`.
- **No Session Lifecycle Management:** Idle timeout (30 minutes), absolute timeout (8 hours), and revocation tracking belong in Step 6D (`SessionRepository`).
- **No HTTP Cookies or Middleware:** Cookie extraction, cookie setting, and Fiber middleware belong in Step 6E.
