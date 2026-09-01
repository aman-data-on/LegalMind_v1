# Reference Documentation Index

> **Scope.** LegalMind reference materials — architecture, authentication, authorization, and user management.
>
> **Status:** Last Updated 2026-09-01. References branch `ui-phase3-through-3.4` state; re-verify against current codebase if read much later (no automated sync).
>
> **Note:** This folder is a design reference, not part of the locked specification. See [docs/README.md](../docs/README.md) for the authoritative specification.

---

## Documents (4)

| File | What it is | Read when | Lines |
|------|-----------|-----------|-------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | FastAPI + SQLAlchemy backend, Next.js frontend, layering, file structure, core design decisions | First — overview of the system | 400 |
| [`AUTHENTICATION.md`](AUTHENTICATION.md) | OIDC (primary) + password (fallback) login, server-side sessions, AM-36 stateless JWT (advisory roles claim), rate limiting, logout/revocation | Understanding how users sign in | 624 |
| [`AUTHORIZATION.md`](AUTHORIZATION.md) | Permission catalogue (21 permissions), roles (5 canonical), no-bypass architecture, Guard class, object visibility model (ownership + scope), escalation guards (S-8, S-9, SEC-05), field redaction (LEGAL-02) | Understanding access control | 595 |
| [`USERS.md`](USERS.md) | User model, CRUD API (`POST /users`, grant/revoke roles), admin UI, status model (ACTIVE/SUSPENDED/DISABLED), zero default roles, no invitation flow | Managing users and roles | 526 |

---

**Total: 2,145 lines**

---

## How to Use This Folder

1. **New to LegalMind?** Start with [`ARCHITECTURE.md`](ARCHITECTURE.md) for the tech stack and overall structure.
2. **Implementing auth?** Read [`AUTHENTICATION.md`](AUTHENTICATION.md) for login flows, sessions, and the JWT model.
3. **Adding access control?** Read [`AUTHORIZATION.md`](AUTHORIZATION.md) for permissions, roles, and the authorization boundary.
4. **Creating/updating users?** Read [`USERS.md`](USERS.md) for the API and UI.
5. **Verifying a claim?** All files cite concrete file paths and line numbers; check them against `backend/` and `frontend/src/`.

---

## What's NOT Here

- ❌ **User invitations** — Intentionally not implemented; admin-only account creation.
- ❌ **Self-signup** — By design (locked 47.1.3 r3).
- ❌ **Bulk user import** — Not a V1 feature.
- ❌ **Email notifications on status change** — Not implemented.
- ❌ **Component library** — No Tailwind, no shadcn; by deliberate choice (rule 19).
- ❌ **Plugin/modular permissions** — Permissions are a single, code-defined catalogue.

---

## Scope Warnings

**This is a reference, not a specification.** Locked decisions live in:
- [`all_lock.md`](../../all_lock.md) (master record)
- [`docs/00-project/LOCKED_DECISIONS.md`](../../docs/00-project/LOCKED_DECISIONS.md) (indexed)
- [`docs/06-security/`](../../docs/06-security/) (specification detail)

**If a file here contradicts those, the locked docs win.** Report the discrepancy rather than silently following this reference.

---

**Last Updated:** 2026-09-01  
**Status:** Reference  
**Sync:** Manual (check against code after major changes)
