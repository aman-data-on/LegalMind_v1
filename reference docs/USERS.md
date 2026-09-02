# LegalMind — User Management

**Version:** 1.0  
**Last Updated:** 2026-09-01  
**Status:** Reference (reflects `ui-phase3-through-3.4` branch state; verify against current code if read later)  
**Specification:** Step 47 §47.5 (S-8, S-9, SEC-05), 42.2 (User model), admin.py (API)

---

## Overview

User management in LegalMind is **admin-only:** there is no self-signup, no invitation flow, and no
email-driven account creation. Administrators create accounts via the admin API/UI, starting users
with **no roles** (locked 47.1.3 r3). Authority (roles, permissions, legal decision power) is
assigned separately and explicitly.

**No invitation system exists.** This is a deliberate design choice, not an omission.

---

## Key Features

- ✅ **Admin-Only Account Creation** — No self-signup; via `POST /api/v1/users` only
- ✅ **Zero Default Roles** — New users have no roles; authority is a later deliberate grant
- ✅ **Three User Statuses** — ACTIVE (can login), SUSPENDED (blocked), DISABLED (closed)
- ✅ **Immediate Session Revocation** — Disabling a user revokes all their live sessions instantly
- ✅ **Multi-Role Support** — Users can hold multiple roles (union of permissions)
- ✅ **Escalation Guards** — S-8 (can't grant what you don't hold), S-9 (can't edit more-privileged users)
- ✅ **Legal Authority Preservation** — Never remove the last user holding `legal.decision` (SEC-05)
- ✅ **Audit Trail** — Every role grant/revocation and user status change is logged
- ✅ **Full CRUD API** — List, create, read, update users; list, create, update roles

**What does NOT exist:**
- ❌ Self-registration / signup endpoint
- ❌ Email-based invitation flow
- ❌ Bulk user import
- ❌ User invitation tokens
- ❌ Pending/inactive user approval workflow (users are ACTIVE on creation, admin sets status)

---

## User Model

**Database table:** `users`

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `email` | String | Unique, normalized to lowercase |
| `name` | String | Display name (populated from OIDC profile or set by admin) |
| `status` | Enum | `ACTIVE` / `SUSPENDED` / `DISABLED` |
| `created_at` | Timestamp | Insertion time |
| `updated_at` | Timestamp | Last modification time |

**No credential or provider columns on User itself.** These live in separate tables:

### UserIdentity Table

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to User |
| `provider` | Enum | `OIDC` or `PASSWORD` |
| `provider_subject` | String | Subject ID from OIDC provider (if OIDC) |
| `credential_hash` | String | Scrypt hash of password (if PASSWORD); selected by exactly one query (S-4) |
| `last_used_at` | Timestamp | When this identity was last used to login |

**A user can have multiple identities** (e.g., both an OIDC and a password credential), but in V1
this is not used; typically one per user.

### UserSession Table

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key (the session ID) |
| `user_id` | UUID | Foreign key to User |
| `expires_at` | Timestamp | When the session expires (12h from creation) |
| `revoked_at` | Timestamp | When the session was revoked (NULL if active) |
| `revoked_reason` | String | Why it was revoked (e.g., "logout", "account disabled") |
| `last_seen_at` | Timestamp | When the user last used this session |

---

## Roles & Permissions

See [AUTHORIZATION.md](./AUTHORIZATION.md) for the complete permission catalogue and role
definitions.

**Quick reference:**

| Role | Primary Use | Legal Authority | Perms Count |
|------|-------------|-----------------|-------------|
| `USER` | Regular employee | None | 12 |
| `LEGAL_REVIEWER` | Attorney reviewing findings | `legal.review` only (no decision) | 14 |
| `LEGAL_ADMIN` | Senior counsel managing standards | `legal.review` + config edit | 17 |
| `SUPER_ADMIN` | System administrator | None (no content access) | 4 |
| `LEGAL_DECISION_AUTHORITY` | Additional role: grants decision power | `legal.decision`, `legal.approve_customization` | 2 |

**Key fact:** A new user starts with **no roles**. Authority is always assigned later.

---

## User Status Model

Three statuses; only `ACTIVE` users can login:

| Status | Can Login? | Meaning | Use Case |
|--------|-----------|---------|----------|
| **ACTIVE** | ✅ Yes | Account is operational | Normal working users |
| **SUSPENDED** | ❌ No | Temporarily blocked | Policy violation, investigation, leave of absence |
| **DISABLED** | ❌ No | Permanently closed | Termination, account migration, cleanup |

**Status gating is enforced everywhere:**
- Login (password): `if user.status != ACTIVE: raise Unauthenticated`
- Login (OIDC): Same check
- JWT path: `if user.status != ACTIVE: raise Unauthenticated` (re-checked on every token-authenticated request)

**Effect of status change to SUSPENDED/DISABLED:**
- User is immediately logged out (all sessions revoked)
- Next login attempt is refused
- Live sessions are invalidated; requests with that session cookie get 401

---

## User/Role CRUD API

**File:** `api/routers/admin.py`

All endpoints require `user.manage` or `role.manage` permission.

### List Users

`GET /api/v1/users`

**Requires:** `user.manage` permission

**Query params:**
- `page` (default 1)
- `page_size` (default 25)
- `status` (optional: `ACTIVE`, `SUSPENDED`, `DISABLED`)

**Response (200):**
```json
{
  "data": [
    {
      "user_id": "<uuid>",
      "email": "alice@example.com",
      "name": "Alice",
      "status": "ACTIVE",
      "roles": ["USER", "LEGAL_REVIEWER"],
      "permissions": ["contract.view", "review.create", ...],
      "created_at": "2026-08-20T10:00:00Z",
      "updated_at": "2026-09-01T12:00:00Z"
    }
  ],
  "pagination": { "page": 1, "page_size": 25, "total": 100 }
}
```

---

### Create User

`POST /api/v1/users`

**Requires:** `user.manage` permission

**Locked 47.1.3 r3:** A new account is created with **no roles**.

**Request:**
```json
{
  "email": "bob@example.com",
  "name": "Bob"
}
```

**Validation:**
- Email must be unique (case-insensitive)
- Email can be any format (no domain restriction)

**Response (201):**
```json
{
  "data": {
    "user_id": "<uuid>",
    "email": "bob@example.com",
    "name": "Bob",
    "status": "ACTIVE",
    "roles": [],
    "permissions": [],
    "created_at": "2026-09-01T12:30:00Z",
    "updated_at": "2026-09-01T12:30:00Z"
  }
}
```

**Audit:** `admin.user_created`

---

### Get User

`GET /api/v1/users/{user_id}`

**Requires:** `user.manage` permission

**Response (200):** Same as list (single user).

**Error (404):** User not found.

---

### Update User

`PATCH /api/v1/users/{user_id}`

**Requires:** `user.manage` permission + S-9 escalation guard

**Request:**
```json
{
  "name": "Bob Smith",
  "status": "SUSPENDED"
}
```

**Allowed fields:**
- `name` (string)
- `status` (enum: `ACTIVE`, `SUSPENDED`, `DISABLED`)

**Validation & Checks:**
- S-9: Cannot edit a user who holds more-privileged permissions than you
- SEC-05: If changing status to SUSPENDED/DISABLED, cannot leave zero `legal.decision` holders

**Effect of status change to SUSPENDED/DISABLED:**
- All sessions for this user are immediately revoked
- Audit: `admin.user_updated` + `AUTH_SESSION_REVOKED`
- Any live requests from this user get 401

**Response (200):** Updated user object.

**Error (403):** Escalation guard (target user is more-privileged) or SEC-05 (would leave zero legal authorities).

**Audit:** `admin.user_updated`

---

### Grant Role

`POST /api/v1/users/{user_id}/roles`

**Requires:** `user.manage` permission + S-8 escalation guard

**Request:**
```json
{
  "role_code": "USER"
}
```

**Validation & Checks:**
- S-8: Cannot grant a role with permissions you don't hold
- S-9: Cannot grant roles to a more-privileged user
- Idempotent: If user already has this role, no-op (no duplicate entry)

**Response (201):** Updated user object (now includes the new role).

**Error (403):** Escalation guard.

**Audit:** `admin.role_granted` (or `admin.legal_authority_granted` if role carries `legal.*`)

---

### Revoke Role

`DELETE /api/v1/users/{user_id}/roles/{role_code}`

**Requires:** `user.manage` permission + S-9 escalation guard

**Validation & Checks:**
- S-9: Cannot revoke from a more-privileged user
- SEC-05: Cannot revoke `legal.decision` from the last holder
- Idempotent: If user doesn't have this role, no-op

**Response (200):** Updated user object (role now removed).

**Error (403):** Escalation guard or SEC-05.

**Audit:** `admin.role_revoked` (or `admin.legal_authority_revoked` if role carries `legal.*`)

---

### List Roles

`GET /api/v1/roles`

**Requires:** `role.manage` permission

**Query params:**
- `page`, `page_size`

**Response (200):**
```json
{
  "data": [
    {
      "role_id": "<uuid>",
      "code": "USER",
      "name": "User",
      "permissions": ["contract.view", "contract.create", ...],
      "user_count": 45,
      "created_at": "2026-08-20T10:00:00Z",
      "updated_at": "2026-08-20T10:00:00Z"
    }
  ],
  "pagination": { ... }
}
```

---

### Create Role

`POST /api/v1/roles`

**Requires:** `role.manage` permission

**Request:**
```json
{
  "code": "CUSTOM_ROLE",
  "name": "Custom Role"
}
```

**Validation:**
- Code must be unique (case-insensitive)
- Code is uppercase string

**Effect:** New role is created with **no permissions** (permissions are assigned separately via PATCH).

**Response (201):** Role object.

**Audit:** `admin.permission_changed`

---

### Update Role

`PATCH /api/v1/roles/{role_id}`

**Requires:** `role.manage` permission + S-8 escalation guard

**Request:**
```json
{
  "name": "Updated Name",
  "permissions": ["contract.view", "contract.create", "legal.decision"]
}
```

**Allowed fields:**
- `name` (string)
- `permissions` (array of permission strings)

**Validation & Checks:**
- S-8: Cannot add a permission to the role that you don't hold yourself
- SEC-05: Cannot remove `legal.decision` from all roles if any users currently hold it
- Transactional: Either all permissions are replaced or none (S-10, locked 43.26)

**Response (200):** Updated role object.

**Error (403):** Escalation guard or SEC-05.

**Audit:** `admin.permission_changed`

---

## Admin UI (Current)

**Location:** `frontend/src/app/documents/admin/page.tsx` (327 lines)

**Tabs:**

### 1. Users Tab

- **List users** (paginated table)
  - Columns: Email, Name, Status, Roles, Actions
  - Filter by status (dropdown)
  - Search by email or name (text input)
  - Sort by email, created_at

- **Create user** (modal form)
  - Email (required, text input)
  - Name (required, text input)
  - Button: "Create"

- **Edit user** (inline or modal)
  - Name (editable)
  - Status (dropdown: ACTIVE / SUSPENDED / DISABLED)
  - Roles (list with checkboxes or grant/revoke UI)

- **Delete user** (modal confirm)
  - "Are you sure?" prompt

### 2. Roles Tab

- **List roles** (paginated table)
  - Columns: Code, Name, Permissions (count), Users, Actions
  - Filter by built-in vs. custom (future)

- **Create role** (modal form)
  - Code (required, text input, uppercase)
  - Name (required, text input)

- **Edit role** (modal)
  - Name (editable)
  - Permissions (multi-select checklist of all 21 permissions, grouped by domain)
  - Button: "Save"

- **Delete role** (modal confirm, if no users assigned)

---

## Frontend Admin UI Features

**Permission gating:** All admin buttons/forms are gated by `can(P.USER_MANAGE)` or `can(P.ROLE_MANAGE)` via the `PermissionGate` component.

**Error handling:** Server-side validation errors (S-8 escalation, SEC-05) are displayed inline next to the affected row with the exact server message.

**Indeterminate states:** When a permission is checked, the UI does not pre-validate S-8/S-9; it lets the server refuse and displays the error.

---

## Testing User Management

### Manual Test Checklist

1. **Create user with no roles**
   - ✅ `POST /users` with email + name → 201, empty roles
   - ✅ New user cannot login (no roles)
   - ✅ Audit log shows `admin.user_created`

2. **Grant USER role**
   - ✅ `POST /users/{id}/roles` with `role_code=USER` → 201
   - ✅ User now appears in roles list
   - ✅ Audit log shows `admin.role_granted`

3. **Escalation guard (S-8)**
   - ✅ Login as USER (no `legal.decision`)
   - ✅ Try to grant `LEGAL_DECISION_AUTHORITY` to another user
   - ✅ Server returns 403: "escalation refused: cannot grant permissions..."

4. **Escalation guard (S-9)**
   - ✅ Login as USER (no legal permissions)
   - ✅ Try to edit a LEGAL_ADMIN's name or status
   - ✅ Server returns 403: "escalation refused: target holds permissions..."

5. **Legal authority preservation (SEC-05)**
   - ✅ Ensure at least one user holds `legal.decision`
   - ✅ Try to revoke `LEGAL_DECISION_AUTHORITY` from last holder
   - ✅ Server returns 403: "refused: this change would leave no user able to make a Legal Decision"

6. **Session revocation on disable**
   - ✅ Create two windows, login as user A in both
   - ✅ In admin panel, set user A to SUSPENDED
   - ✅ User A's other window gets 401 on next request
   - ✅ Audit log shows `AUTH_SESSION_REVOKED`

7. **Role permissions are unions**
   - ✅ Assign USER (has `contract.create`) and LEGAL_REVIEWER (has `legal.review`)
   - ✅ User can now create contracts AND review legal content

---

## Common Issues

### Issue 1: User Cannot Login

**Cause:** User has no roles (new account, not yet granted).

**Solution:** Assign at least the `USER` role via `POST /users/{id}/roles?role_code=USER`.

### Issue 2: "Escalation Refused" When Granting Role

**Error:** `{"detail": "escalation refused: cannot grant permissions the actor does not hold: ['legal.decision']"}`

**Cause:** S-8 guard. You don't hold `legal.decision` yourself, so you can't grant it.

**Solution:** Only a user who holds `legal.decision` (or a Super Admin who holds LEGAL_DECISION_AUTHORITY) can create roles or grant them to users.

### Issue 3: Cannot Disable Last Legal Authority

**Error:** `{"detail": "refused: this change would leave no user able to make a Legal Decision"}`

**Cause:** SEC-05 guard prevents the last `legal.decision` holder from being disabled.

**Solution:** Grant `legal.decision` to another user first, then disable the original holder.

### Issue 4: Cannot Revoke Another User's Roles

**Error:** `{"detail": "escalation refused: target holds permissions the actor does not: ['...']"}`

**Cause:** S-9 guard. You're trying to revoke from a user who holds permissions you don't.

**Solution:** Escalate to a user who holds those permissions, or a Super Admin + LEGAL_DECISION_AUTHORITY.

---

## Related Documentation

- [Authorization System](./AUTHORIZATION.md) — Permission catalogue, roles, escalation guards
- [Authentication](./AUTHENTICATION.md) — Login, sessions, status gating
- [Architecture](./ARCHITECTURE.md) — API layer, Guard class, database schema
- [Step 47 Security Spec](../06-security/STEP_47_SECURITY_SPECIFICATION.md) — Locked auth/authz rules
- [Locked Decisions](../00-project/LOCKED_DECISIONS.md) — ROLE-01–ROLE-07, SEC-01–SEC-05

---

**Last Updated:** 2026-09-01  
**Status:** Reference Documentation  
**Completeness:** 100%
