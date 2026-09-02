# LegalMind — Authentication System

**Version:** 1.0  
**Last Updated:** 2026-09-01  
**Status:** Reference (reflects `ui-phase3-through-3.4` branch state; verify against current code if read later)  
**Specification:** Step 47 §47.1, OD-9, AM-36 (AB-8)

---

## Overview

LegalMind implements dual authentication: **corporate SSO via OIDC is primary** (locked 47.1.3);
**password login is a controlled fallback.** Both mechanisms produce a server-side session carrying
identity only. An additional stateless JWT (`AM-36`, 24-hour lifetime) is issued alongside the
session for the OIDC path, allowing session-independent operation in distributed scenarios. The
JWT's `roles` claim is **explicitly advisory and never trusted for authorization** — every
permission check is re-resolved from the database on every request.

**Account provisioning is admin-only:** there is **no self-signup, no user invitation flow, and no
email-based account creation.** Accounts are created via `POST /users` by an administrator with
`user.manage` permission.

---

## Key Features

- ✅ **OIDC SSO (Primary)** — Corporate identity provider (Google, Okta, Azure AD, …)
- ✅ **Password Login (Fallback)** — Credential-based authentication for offline/emergency scenarios
- ✅ **Server-Side Sessions** — Identity only (no roles/permissions), 12-hour lifetime, immediately revocable
- ✅ **AM-36 Stateless JWT** — Optional, 24-hour, HS256, roles claim advisory only (never trusted for authz)
- ✅ **Session-First Resolution** — Session cookie preferred over JWT when both present (maintains revocability)
- ✅ **Indistinguishable Failures** — Unknown account, wrong password, disabled account all produce identical response (S-7)
- ✅ **Rate Limiting** — Keyed on client IP, not submitted email (S-5), prevents account enumeration
- ✅ **Admin-Only Provisioning** — No self-registration; new accounts created by admins, start with no roles
- ✅ **Status Gating** — Only `ACTIVE` users can login; `SUSPENDED` and `DISABLED` accounts are refused
- ✅ **Immediate Revocation** — Disabling an account revokes all live sessions instantly
- ✅ **Token Refresh** — OIDC refresh_token exchange for new JWT without full re-authentication

---

## Authentication Flow

### 1. OIDC / Corporate SSO (Primary)

**Locked 47.1.3:** This is the **primary** mechanism. All features it supports (session creation,
account linking, token refresh) apply. The password form is secondary.

```
┌─────────────────────────────────────────────────────────────────┐
│ User at /login                                                  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ User clicks "Continue with [Corporate SSO]"                     │
│ → Navigates to GET /api/v1/auth/oidc/start                      │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ oidc_start() (auth.py:273)                                      │
│ ├─ Rate limit check (client IP, S-5)                            │
│ ├─ Call oidc.new_transaction()                                  │
│ ├─ Generate authorization_url() with state parameter            │
│ └─ Set transaction cookie (HttpOnly, 10min TTL)                 │
│    → Redirect 302 to identity provider                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ User authenticates at identity provider                         │
│ (enters credentials, MFA, etc.)                                 │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Identity provider redirects to GET /api/v1/auth/oidc/callback   │
│ → Carries: code, state, [error]                                 │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ oidc_callback() (auth.py:303)                                   │
│ ├─ Rate limit check (client IP)                                 │
│ ├─ Decode transaction cookie, verify state parameter (CSRF)     │
│ ├─ Exchange code for ID token (TLS POST to issuer)              │
│ ├─ Extract claims (sub, email, name)                            │
│ ├─ Call oidc.resolve_user(db, claims):                          │
│ │  ├─ Look up user by OIDC subject, or by email                 │
│ │  └─ Create user if new (status: ACTIVE)                       │
│ ├─ create_session(db, user) → UserSession (12h TTL)             │
│ ├─ Store OIDC provider tokens (refresh_token encrypted)         │
│ ├─ Audit: AUTH_LOGIN_SUCCEEDED                                  │
│ └─ Set session + JWT cookies, redirect to /documents            │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ User lands on /documents (authenticated)                        │
└─────────────────────────────────────────────────────────────────┘
```

**File locations:** `api/routers/auth.py` lines 273-377 · `security/oidc.py`

---

### 2. Password Login (Fallback)

**Locked 47.1.3:** A secondary authentication method. Does NOT support token refresh or multi-device
scenarios — the session-only model applies.

```
┌─────────────────────────────────────────────────────────────────┐
│ User at /login, clicks "Use credentials"                        │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ User enters email + password                                    │
│ POST /api/v1/auth/login (LoginRequest)                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ login() (auth.py:103)                                           │
│ ├─ Rate limit check (client IP, not email — S-5)                │
│ ├─ Query User by email.lower() [normalization]                  │
│ ├─ Query UserIdentity (provider=PASSWORD) [S-4: credential_hash │
│ │  is selected by this query and no other]                      │
│ ├─ verify_password(submitted_password, credential_hash)         │
│ │  [Scrypt; timing-safe even with wrong hash]                   │
│ ├─ Check user.status == ACTIVE (S-7: indistinguishable if not)  │
│ └─ If any step fails:                                           │
│    ├─ Audit: AUTH_LOGIN_FAILED (no submitted email, no actor)   │
│    ├─ Signal: auth.login_failed                                 │
│    └─ Response: Unauthenticated("authentication failed")        │
│    [Same response for unknown account / wrong password / disabled]
│                                                                 │
│ If all pass:                                                     │
│ ├─ create_session(db, user) → UserSession (12h TTL)             │
│ ├─ Audit: AUTH_LOGIN_SUCCEEDED                                  │
│ ├─ Set session cookie (no JWT for password path — AM-36 t1)     │
│ └─ Response: session + identity                                 │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ User lands on /documents (authenticated)                        │
└─────────────────────────────────────────────────────────────────┘
```

**File locations:** `api/routers/auth.py` lines 103-164 · `security/passwords.py`

---

## Session Management

### Server-Side Sessions (Locked SEC-01, S-1)

**Model:** `UserSession` (db/models.py lines 121-141)
- `id` (UUID, primary key)
- `user_id` (foreign key to User)
- `expires_at` (12 hours from creation)
- `revoked_at` (when admin/logout invalidated it)
- `revoked_reason` (string; e.g., "logout", "account disabled")
- `last_seen_at` (timestamp of last request using this session)

**Lifetime:** 12 hours from creation. Can be revoked immediately by an administrator or the user
themselves (logout).

**What it carries:** Identity only (user_id). **No roles, no permissions.** These are resolved
fresh from the database on every request (locked S-1, preventing mid-session permission changes
from being delayed).

**Cookie:** Session ID as UUID, stored in HttpOnly cookie (`SESSION_COOKIE`).
- `secure=True` (HTTPS only in production)
- `samesite="Lax"` (sent on cross-site top-level navigations, required for OIDC callback)
- `httponly=True` (not readable by JavaScript, protects against XSS)
- `path=/` (site-wide)

---

### AM-36: Optional Stateless JWT (2026-09-01)

**Locked `AM-36` (AB-8):** The OIDC path issues a **second** credential alongside the session.

**What it is:** A signed JWT, **HS256 only**, issued by `tokens.issue()` (security/tokens.py lines
1-200).

```
Header:  {"alg": "HS256", "typ": "JWT"}
Payload: {
  "iss": "legalmind",
  "aud": "legalmind",
  "sub": "<user_id>",           ← USED for authorization
  "email": "<user_email>",       ← ADVISORY ONLY (never trusted)
  "roles": ["USER", "..."],      ← ADVISORY ONLY (never trusted)
  "iat": <issued_at>,
  "exp": <expiry>,
  "jti": <unique_id>
}
Signature: HMAC-SHA256(secret)
```

**Lifetime:** 24 hours.

**When issued:** Alongside the session cookie, but **only** for the OIDC path (auth.py line 373,
`_set_token_cookie`). The password login does NOT issue a JWT (AM-36 t1).

**Why it exists:** A stateless token survives if the session cookie is dropped (e.g., domain
changes, browser isolation). It enables single-device or edge-cache scenarios without a central
session store.

**Critical: The `roles` Claim Is Advisory & Never Trusted**

Locked `AM-36` t2–t3:

> "The token carries a `roles` claim (t2's requirement) ... advisory (t3) — read here purely to
> fill the claim, and never consulted when authorizing."

`get_principal()` (`deps.py` lines 100-111) reads **only** `sub` from the token:

```python
token = request.cookies.get(tokens.TOKEN_COOKIE)
if not token:
    raise Unauthenticated("no session cookie")
claims = tokens.verify(token)          # raises if invalid
user = db.get(M.User, claims.user_id)  # claims.user_id only
if user is None or user.status is not E.UserStatus.ACTIVE:
    raise Unauthenticated("no valid session")
return Principal(user_id=claims.user_id, ...)
```

The `email` and `roles` fields are **discarded.** A test (`test_jwt_roles_claim_never_consulted`)
deliberately fails if a future change ever reads `claims.roles` during authorization. This is a
loaded assertion in code, not a promise in prose.

**Status re-check on token path:** Locked `AM-36` t4(b) requires that a disabled account is
refused immediately even if the token is still live. Lines 104–108 check the database for
`user.status != ACTIVE` on every token-authenticated request.

---

## Request: Session vs. JWT Resolution Order

`get_principal()` (deps.py lines 67-111) implements a deliberate priority:

```python
# STEP 1: Try server-side session (revocable)
raw = request.cookies.get(SESSION_COOKIE)
if raw:
    session_id = UUID(raw)
    return resolve_session(db, session_id)  # Checks expires_at, revoked_at

# STEP 2: Fall back to JWT (token-based)
token = request.cookies.get(tokens.TOKEN_COOKIE)
if not token:
    raise Unauthenticated("no session cookie")
claims = tokens.verify(token)
user = db.get(M.User, claims.user_id)
if user is None or user.status is not E.UserStatus.ACTIVE:
    raise Unauthenticated("no valid session")  # Status re-check
return Principal(user_id=claims.user_id, ...)
```

**Why this order:** A revoked session always takes precedence. If both cookies exist, the session
is checked first. This ensures that an administrator's revocation (logout or account disable) is
effective immediately, without waiting for the 24-hour token to expire.

---

## Cookie Attributes

| Cookie | HttpOnly | Secure | SameSite | Path | Max-Age |
|--------|----------|--------|----------|------|---------|
| Session ID | ✅ Yes | ✅ Yes | Lax | / | ~12h |
| JWT (Token) | ✅ Yes | ✅ Yes | Lax | / | 24h |
| CSRF token | ❌ No (read by JS) | ✅ Yes | Lax | / | ~12h |

**HttpOnly:** Session and JWT cookies are HttpOnly to prevent JavaScript access (XSS protection).

**Secure:** All cookies require HTTPS in production (`config.py` sets based on `APP_ENV`).

**SameSite=Lax:** Allows cookies on cross-site top-level navigations (required for OIDC callback
to receive the session cookie when redirecting from the identity provider).

---

## Rate Limiting (S-5)

**Rate limiter:** In-process (default) or Redis-backed; keyed on **client IP address, never email**.

```python
limiter.check(f"login:{client_ip}", ratelimit.LOGIN)
```

**Why not email:** An attacker could lock out a real user by submitting their email repeatedly.

**Per-client limit:** Currently hardcoded; configurable via `ratelimit.LoginLimit`.

**Where applied:**
- `POST /auth/login` (password)
- `GET /auth/oidc/start` (OIDC redirect)
- `GET /auth/oidc/callback` (OIDC callback)

**Enforcement:** Raises `RateLimitExceeded` (429), not silently dropped.

---

## User Status Gating (Locked 47.1.3)

Only **`ACTIVE`** users can login. Other statuses are refused:

| Status | Can Login? | Meaning |
|--------|-----------|---------|
| **ACTIVE** | ✅ Yes | Account is operational |
| **SUSPENDED** | ❌ No | Temporarily blocked (e.g., policy violation) |
| **DISABLED** | ❌ No | Permanently or administratively closed |

**Enforcement location:** Both authentication methods check status before creating a session:
- Password path (auth.py line 146): `if user.status is not E.UserStatus.ACTIVE: raise`
- OIDC path (oidc.py, called from auth.py line 337): `resolve_user()` checks and raises
- JWT path (deps.py line 105): `if user.status is not E.UserStatus.ACTIVE: raise`

**Audit:** Login failures are recorded without the attempted email (enumeration prevention), but
the actor_id is set if the account exists.

---

## Logout & Revocation

### User-Initiated Logout

`POST /auth/logout`

```python
def logout(request: Request, response: Response, ...):
    revoke_session(db, principal.session_id, reason="logout")
    Audit: AUTH_LOGOUT
    # Delete all three cookies
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    response.delete_cookie(tokens.TOKEN_COOKIE)  # Clears JWT too
    return data({"revoked": True})
```

**Effect:** The session is marked revoked, and the cookies are deleted from the browser. The JWT
cannot be "revoked" server-side (stateless), but it is deleted from the browser immediately.

### Admin-Initiated Revocation

`DELETE /auth/sessions/{session_id}`

Allows a Super Admin or User Manager to terminate a session for another user:

```python
def revoke(session_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.USER_MANAGE)
    session = guard.db.get(M.UserSession, session_id)
    if session is not None:
        require_can_administer_user(...)  # S-9 escalation guard
        revoke_session(guard.db, session_id, reason="revoked by administrator")
        Audit: AUTH_SESSION_REVOKED
    return data({"revoked": True})
```

**Effect:** The session is immediately marked revoked. The user's next request with that session
cookie is refused.

### Account Disable

When an admin disables or suspends a user (`PATCH /users/{user_id}`):

```python
if body.status is not E.UserStatus.ACTIVE:
    revoked = revoke_all_for_user(guard.db, user_id, reason="account disabled")
    Audit: Sessions revoked
```

**Effect:** ALL active sessions for that user are revoked immediately.

---

## Token Refresh (OIDC Only)

`POST /auth/token/refresh`

Allows an authenticated user (OIDC path only) to issue a new JWT before the current one expires:

```python
def refresh_token(request: Request, response: Response, ...):
    # Find the user's OIDC identity + stored refresh_token
    # Exchange refresh_token at the provider for new access_token
    # Issue a new JWT with fresh expiry
    # Store new tokens (token rotation)
    _set_token_cookie(response, db, user)
```

**Preconditions:**
- User must be authenticated (session or JWT must be valid)
- User must have an OIDC identity (not password-only)
- A stored, non-expired refresh_token must exist

**Failures (401):**
- Provider refused the refresh (token revoked/expired on provider side)
- No OIDC identity for this user
- No stored refresh_token

**Effect:** A new JWT is issued, extended the 24-hour lifetime from now.

---

## Security Measures

### 1. Domain Restriction (Future)

**Future work:** OIDC is intended to support Google Workspace domain restrictions (e.g.,
`example.com` only). Configuration: `config.oidc_domain()`.

Current implementation: No domain restriction; any OIDC identity at any issuer is accepted.

### 2. Indistinguishable Failures (S-7, Audit)

Unknown account, wrong password, and disabled account all return:

```json
{
  "detail": "authentication failed"
}
```

The submitted email is **never recorded in the audit log** (enumeration prevention). If the account
exists, the audit record has an `actor_id`; if not, it does not.

### 3. Session Regeneration

After successful authentication, `session.regenerate()` is called to invalidate any pre-login
session cookie (OWASP A04 / session fixation prevention).

### 4. Password Security

Passwords are hashed with **scrypt**, not bcrypt (security/passwords.py). Scrypt is resistant to
ASIC attacks. Configuration in `config.py`:

```python
SCRYPT_PARAMS = dict(N=2**14, r=8, p=1)  # Tuned for ~1 second hashing
```

Password never appears in logs or JSON serialization (excluded from User.__dict__ via `__fields__`
in Pydantic).

### 5. No Self-Provisioning

Accounts are created **only** by an administrator via `POST /users` (admin.py line 73). No signup
endpoint, no invitation flow, no email-driven account creation.

**Rationale:** Locked 47.1.3 r3 — "LegalMind never self-provisions an account." This is a
security boundary, not a convenience trade-off.

---

## API Reference

### POST /api/v1/auth/login

**Fallback password authentication.**

Request:
```json
{
  "email": "user@example.com",
  "password": "secret",
  "remember": false
}
```

Response (200):
```json
{
  "data": {
    "user_id": "<uuid>",
    "email": "user@example.com",
    "name": "Alice",
    "permissions": ["contract.view", "review.create", ...]
  }
}
```

Error (401): `{"detail": "authentication failed"}`

Error (429): Rate limit exceeded.

---

### GET /api/v1/auth/oidc/start

**Begin OIDC flow.**

Query params (optional): none

Response (302): Redirect to identity provider.

Sets: Transaction cookie (state, 10min TTL).

---

### GET /api/v1/auth/oidc/callback

**Complete OIDC flow.**

Query params: `code`, `state`, (optional) `error`

Response (302): Redirect to `/documents` on success.

Sets: Session cookie + JWT (if valid).

Error (302): Redirect to `/login?sso=<failed|domain>` on failure.

---

### GET /api/v1/auth/session

**Current session identity + permissions.**

Response (200):
```json
{
  "data": {
    "user_id": "<uuid>",
    "email": "user@example.com",
    "name": "Alice",
    "session_id": "<session_uuid>",
    "authenticated_at": "2026-09-01T12:00:00Z",
    "permissions": ["contract.view", "review.create", ...]
  }
}
```

---

### POST /api/v1/auth/logout

**Sign out the current user.**

Response (200): `{"data": {"revoked": true}}`

Effect: Session marked revoked, all cookies deleted from browser.

---

### DELETE /api/v1/auth/sessions/{session_id}

**Admin: Revoke another user's session.**

Requires: `user.manage` permission + S-9 escalation guard (cannot revoke a more-privileged user's session).

Response (200): `{"data": {"revoked": true}}`

Effect: Specified session is marked revoked; user's next request with that session is refused.

---

### POST /api/v1/auth/token/refresh

**Refresh the JWT token.**

Requires: Valid session or JWT + OIDC identity.

Response (200): `{"data": {"refreshed": true}}`

Sets: New JWT cookie (fresh 24h expiry).

Error (401): `{"detail": "token refresh failed; please sign in again"}`

---

## Common Issues

### Issue 1: "Authentication failed" — Unknown Account

**Cause:** The submitted email is not in the User table.

**Solution:** An admin must create the account via `POST /users` first. There is no self-signup.

### Issue 2: "Authentication failed" — Account Disabled

**Cause:** User has been suspended or disabled by an admin (`status != ACTIVE`).

**Solution:** The admin must re-enable the account, setting `status = ACTIVE`.

### Issue 3: Rate Limit Exceeded (429)

**Cause:** Too many login attempts from the same client IP within a short window.

**Solution:** Wait for the rate-limit window to reset (typically 15 min). Attacks on named accounts
are not possible (rate limiter is per-IP, not per-email).

### Issue 4: OIDC Redirect Loop / "Redirect URI Mismatch"

**Cause:** The OIDC provider's registered redirect URI does not match `config.oidc_redirect_uri()`.

**Solution:** Update the identity provider's client configuration to list the correct callback URL
(e.g., `https://legalmind.example.com/api/v1/auth/oidc/callback`).

### Issue 5: JWT Token Expired (401)

**Cause:** The JWT has reached 24-hour expiry.

**Solution:** Call `POST /auth/token/refresh` if an OIDC refresh_token is available, or re-authenticate.

---

## Related Documentation

- [Authorization System](./AUTHORIZATION.md) — Permission resolution, object scope
- [User Management](./USERS.md) — Account creation, role assignment
- [Step 47 Security Spec](../06-security/STEP_47_SECURITY_SPECIFICATION.md) — Locked decisions
- [Locked Decisions](../00-project/LOCKED_DECISIONS.md) — SEC-01, S-1–S-10, OD-9, AM-36

---

**Last Updated:** 2026-09-01  
**Status:** Reference Documentation  
**Completeness:** 100%
