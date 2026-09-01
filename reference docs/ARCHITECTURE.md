# LegalMind — System Architecture

**Version:** 1.0  
**Last Updated:** 2026-09-01  
**Status:** Reference (reflects `ui-phase3-through-3.4` branch state; verify against current codebase if read later)  
**Framework:** FastAPI 0.115+ (Python 3.12+) + React 19 / Next.js 16 (TypeScript)

---

## Overview

LegalMind is a specification-first legal document analysis engine with a distributed backend architecture. The backend is a FastAPI/SQLAlchemy monolith handling API, legal analysis, and background jobs; the frontend is a Next.js 16 application with React 19, communicating via REST API only. No template rendering, no server-side page logic in the frontend — all content is dynamic via API.

---

## Technology Stack

### Backend
- **Framework:** FastAPI 0.115+
- **Python Version:** 3.12+
- **Database:** PostgreSQL (psycopg2-binary)
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic
- **Authentication:** OIDC (primary) + password fallback; server-side sessions; HS256 JWT (AM-36)
- **Authorization:** Code-defined permission constants (no database-driven RBAC library)
- **Background Jobs:** Celery + Redis (analysis jobs, assist-lane inference)
- **Document Parsing:** PyMuPDF, python-docx
- **Embeddings Runtime:** ONNX (onnxruntime + tokenizers; local inference, CPU-only, no training)

### Frontend
- **Framework:** Next.js 16 (App Router)
- **Language:** TypeScript 5.9
- **Runtime:** React 19
- **Styling:** Plain CSS (no component library by deliberate choice; see DESIGN.md)
- **API Client:** Fetch API (custom wrapper in `src/lib/api.ts`)
- **Testing:** Vitest (unit) + Playwright (E2E)

### Infrastructure
- **No separate admin / user microservices** — one image, one deployment
- **Session Storage:** PostgreSQL (sessions table)
- **Cache:** Optional Redis (for analysis result caching, quota tracking)

---

## Architecture Layers

```
┌──────────────────────────────────────────────────────────┐
│ Frontend (Next.js 16, React 19, TypeScript)              │
│ ├─ Pages (src/app/*/page.tsx)                            │
│ ├─ Components (src/components/)                          │
│ └─ API Client (src/lib/api.ts)                           │
└────────────────────┬─────────────────────────────────────┘
                     │ REST API (JSON)
                     │
┌────────────────────▼─────────────────────────────────────┐
│ FastAPI Router Layer (api/routers/)                       │
│ ├─ auth.py         — OIDC/password login, sessions       │
│ ├─ admin.py        — User/role CRUD, grants              │
│ ├─ contracts.py    — Contract list/create/fetch          │
│ ├─ documents.py    — Document version upload/download    │
│ ├─ reviews.py      — Review creation, list, retrieval    │
│ ├─ findings.py     — Finding detail, escalation          │
│ ├─ decisions.py    — Legal Decision recording            │
│ ├─ configuration.py— Legal Rules, Requirements           │
│ ├─ audit.py        — Audit trail read                    │
│ ├─ export.py       — PDF/DOCX export                     │
│ └─ assist.py       — Ask, type suggestion, Key Obligations
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│ Authorization Boundary (api/deps.py)                      │
│ ├─ get_principal()  — Session/JWT resolution             │
│ ├─ Guard class      — Object visibility, permission check │
│ └─ get_guard()      — Guard factory (FastAPI Depends)    │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│ Domain & Service Layer (legalmind/analysis/, /evaluation/)
│ ├─ Legal analysis engine                                 │
│ ├─ Contract parsing (PyMuPDF, python-docx)               │
│ ├─ Finding extraction & classification                   │
│ ├─ Assist lane (local embeddings + Gemini generation)    │
│ └─ OIDC/OAuth exchange                                   │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│ Data Layer (db/models.py via SQLAlchemy)                  │
│ ├─ User, UserIdentity, UserSession                       │
│ ├─ Role, Permission, RolePermission, UserRole            │
│ ├─ Contract, DocumentVersion, Review, Finding            │
│ ├─ Evaluation, LegalDecision, Escalation                 │
│ ├─ Configuration (RequirementVersion, LegalRule)         │
│ ├─ AuditEvent (append-only)                              │
│ └─ OidcProviderToken (encrypted refresh_token storage)   │
└────────────────────┬─────────────────────────────────────┘
                     │
                    ▼
        ┌──────────────────────────┐
        │  PostgreSQL Database     │
        └──────────────────────────┘
```

### Request Lifecycle

```
1. Client → HTTP request
2. FastAPI middleware: extract request ID, CORS, etc.
3. Router handler receives request, calls get_guard() dependency
4. get_guard() calls:
   ├─ get_db() → create transaction
   ├─ get_principal() → resolve session/JWT, check status
   └─ Guard() → compose authentication + authorization
5. Guard.permission() or Guard.{contract,review,etc}() → Check auth, fetch object
   ├─ Object visibility check first (return 404 if not visible)
   └─ Permission check second (return 403 if permission denied)
6. Domain operation (if authorization passed)
7. db.commit() (or rollback on exception)
8. Response serialization
9. Response to client
```

**Key constraint (locked 43.23):** Authorization happens BEFORE any domain operation. A failed
permission check is logged and committed before the handler even sees the exception.

---

## Core Decisions & Tradeoffs

### 1. No Authorization Bypass Mechanism

**Decision:** LegalMind implements zero bypass for administrative accounts.

**Tradeoff:** A Super Admin cannot view a regular User's Contracts or Legal content by override.
They have administrative capabilities (user creation, role management, audit access) but NOT
content access.

**Why:** Every legal authority (`legal.decision`, `legal.approve_customization`) must be an
explicit grant, never inherited or bypassable (locked Step 23 / SEC-02). This prevents accidental
or malicious disclosure of confidential legal positions through an unguarded admin account.

### 2. Sessions First, Then Stateless Token

**Decision:** Server-side sessions (12h lifetime) are preferred; an optional JWT (`AM-36`) is
issued alongside for the OIDC path only.

**Tradeoff:** The JWT cannot be revoked server-side — a token stolen mid-session persists until
expiry. Session cookies can be revoked immediately.

**Why:** Sessions are the **only** mechanism the password fallback ever uses (locked `AM-36` t1).
The stateless token is a convenience for distributed/edge scenarios without a central session
store. Both mechanisms exist, and the session always takes precedence when both cookies are
present — so a normal sign-in is fully revocable.

### 3. Object Visibility BEFORE Permission

**Decision:** A 404 response is returned for any object a user cannot see, regardless of whether
they hold the permission to operate on it.

**Tradeoff:** The endpoint reveals nothing about whether an object exists (SEC-07). An attacker
enumerating IDs cannot distinguish "permission denied" from "not found."

**Why:** Disclosure of existence is itself a security boundary (locked 47.6 / SEC-06). A blind
enumeration attack learns nothing if every unauthorized ID returns the same 404.

### 4. Local Embedding Runtime, No Training

**Decision:** The assist lane runs embeddings locally via ONNX, CPU-only, inference only.
No torch, no fine-tuning, no network egress except to Gemini for generation (one gate, one key).

**Tradeoff:** Embedding quality is fixed at model release; there is no domain-specific tuning.

**Why:** Locked `AM-26`/`AM-30` exclude training and fine-tuning from V1 scope. The onnxruntime
import proves this: torch is 2.5GB; onnxruntime is 118MB. Inference-only is structural, not
merely stated.

### 5. No Plugin / Modular Permission System

**Decision:** Permissions are a single flat catalogue (21 permissions, code-defined, one canonical
set).

**Tradeoff:** Adding a new permission requires code changes and a seeding pass, not UI
configuration.

**Why:** Locked Step 47 / SEC-04 makes the permission catalogue normative. The seeding script
(`security/seed.py`) is idempotent and never auto-grants a permission an admin has since removed
— the guarantee is simpler than a dynamic system because permissions never silently drift.

---

## File Structure

```
backend/legalmind/
├── api/
│   ├── routers/
│   │   ├── auth.py           — Login, OIDC, session mgmt
│   │   ├── admin.py          — Users, roles, grants
│   │   ├── contracts.py      — Contract CRUD
│   │   ├── documents.py      — Document upload/download
│   │   ├── reviews.py        — Review creation/list
│   │   ├── findings.py       — Finding detail/escalation
│   │   ├── decisions.py      — Legal Decision recording
│   │   ├── configuration.py  — Requirements, Legal Rules
│   │   ├── audit.py          — Audit event read
│   │   ├── export.py         — Export PDF/DOCX
│   │   └── assist.py         — Ask, suggestions, obligations
│   ├── deps.py               — get_principal, Guard, get_guard
│   ├── permission_map.py     — Endpoint → Permission mapping (normative)
│   ├── schemas.py            — Request/response Pydantic models
│   ├── serializers.py        — Domain → API serialization
│   ├── errors.py             — Exception classes
│   └── app.py                — FastAPI app instance
├── db/
│   ├── models.py             — SQLAlchemy models (30 tables)
│   └── session.py            — DB engine, session factory
├── domain/
│   ├── enums.py              — UserStatus, ReviewStatus, etc.
│   ├── document_types.py     — Contract type catalogue
│   └── (various domain modules)
├── analysis/
│   ├── service.py            — Legal analysis orchestration
│   └── engine.py             — Finding extraction, classification
├── evaluation/
│   ├── workflow.py           — Review lifecycle state machine
│   ├── evaluators/           — Evaluator implementations (NUMERIC_COMPARISON, PRESENCE)
│   └── Legal Rule application
├── security/
│   ├── permissions.py        — Permission catalogue, role definitions (canonical)
│   ├── resolver.py           — effective_permissions() per-request
│   ├── authorization.py      — Object visibility (require_*_visible)
│   ├── guards.py             — Escalation guards (S-8, S-9, SEC-05)
│   ├── sessions.py           — Server-side session management
│   ├── tokens.py             — JWT issuance/verification (HS256)
│   ├── oidc.py               — OIDC flow, state management
│   ├── passwords.py          — Password hashing/verify (scrypt)
│   ├── audit.py              — Audit event recording (append-only)
│   └── seed.py               — Idempotent permission/role seeding
├── assist/
│   ├── gateway.py            — Gemini API interface
│   ├── onnx_backend.py       — Local embedding inference
│   └── retrieval.py          — Vector search over documents
├── config.py                 — Environment configuration
└── observability/
    ├── logs.py               — Structured logging (log_event)
    └── metrics.py            — Observability signals
```

```
frontend/src/
├── app/
│   ├── login/page.tsx        — OIDC/password login (auth entry)
│   ├── documents/
│   │   ├── page.tsx          — Contract list (Documents)
│   │   ├── [id]/
│   │   │   └── page.tsx      — Contract detail (Workspace)
│   │   ├── admin/
│   │   │   └── page.tsx      — User/role management (current admin UI)
│   │   ├── admin/audit/
│   │   │   └── page.tsx      — Audit trail viewer
│   │   ├── legal/
│   │   │   └── page.tsx      — Legal queue
│   │   ├── ask/
│   │   │   └── page.tsx      — Assist chat
│   │   └── research/
│   │       └── page.tsx      — Legal research UI (placeholder)
│   ├── configuration/
│   │   └── page.tsx          — Legal Rules, Requirements
│   └── layout.tsx            — Root layout, nav, sidebar
├── components/
│   ├── Primitives.tsx        — Reusable UI primitives
│   ├── Feedback.tsx          — Loading, error, empty states
│   ├── AccessRestricted.tsx  — Permission-gated UI
│   ├── Findings*.tsx         — Finding display components
│   └── (specialized components by domain)
├── lib/
│   ├── api.ts                — Fetch wrapper, error handling
│   ├── permissions.ts        — Permission constant strings
│   ├── session.ts            — useSession hook
│   ├── types.ts              — TypeScript interfaces
│   └── (utilities)
└── __tests__/                — Unit tests (Vitest)
```

---

## Key Design Principles

1. **Specification-First:** Architecture implements locked specifications from `all_lock.md` exactly.
   Every table, endpoint, and permission traces to a decision record.

2. **Deterministic Analysis Lane:** The authoritative legal analysis engine produces deterministic
   results (same inputs + same config → same output) with full evidence traceability.

3. **Assist Lane Isolation:** AI-assisted features (Ask, type suggestion, Key Obligations) are
   never admitted to any determinism guarantee and produce no legal Findings, Evaluations, or
   Decisions — only human-reviewed working notes.

4. **Server-Side Authority:** All authorization is enforced server-side. The frontend holds a
   presentation-only copy of the user's permissions for UI gating; the API never trusts it.

5. **Audit Trail:** Every material change (user role grant, legal decision, contract status change)
   is recorded in an append-only audit log with actor ID, timestamp, before/after values, and
   request traceability.

6. **No Data Silence:** A user either sees an object or receives 404. Null fields are never used
   to signal "you lack permission to see this" — fields are omitted entirely (e.g.,
   `rule_outcome` when `legal_position.view` is denied), or the whole object is hidden.

---

## Request Path Example: Viewing a Review

```
1. Frontend calls GET /api/v1/reviews/review-id
2. FastAPI extracts session or JWT from cookies
3. get_principal() resolves user from session/token
   (status re-checked on JWT path)
4. get_guard() creates Guard with user_id
5. Router handler calls guard.review(review_id, "review.view")
6. Guard.review() runs:
   ├─ require_review_visible(db, user_id, review_id)
   │   ├─ Fetches review from DB
   │   └─ Calls can_see_review() — checks:
   │       ├─ Is user the creator?
   │       ├─ Does user have a legal assignment?
   │       └─ Does user have legal.review AND is review in Legal scope?
   │   └─ Raises NotVisible(404) if none match
   └─ Checks "review.view" in permissions
       └─ Raises Forbidden(403) if not present
7. Domain operation (serialize review, return JSON)
8. Response to frontend
```

---

## Database Schema

30 tables total. Key entities:

- **User** — authentication subject (id, email, name, status)
- **UserIdentity** — credentials (OIDC subject or password hash)
- **UserSession** — server-side session (id, user_id, expires_at, revoked_at)
- **Role, Permission, RolePermission, UserRole** — authorization (union semantics)
- **Contract, DocumentVersion, Review, Finding, Evaluation** — legal analysis workflow
- **LegalDecision, Escalation** — decision trail
- **RequirementVersion, LegalRuleVersion, LegalRuleConfiguration** — Legal Rules
- **AuditEvent** — append-only change log
- **OidcProviderToken** — encrypted refresh_token storage for OIDC refresh flow

See `db/models.py` for the full schema (1:1 with database structure via Alembic migrations).

---

## Testing Strategy

- **Unit Tests (Vitest):** React components, utility functions
- **Integration Tests (Pytest):** API handlers with in-memory session, real DB (transactional)
- **E2E Tests (Playwright):** Full user workflows (auth, upload, analysis, review, decision)
- **Visual Regression (Playwright):** Baseline screenshots in CI

CI runs: `pytest backend/tests/`, `npm test` (frontend unit), `npm run test:e2e` (Playwright).

---

## Common Questions

**Q: Why no component library?**  
A: DESIGN.md §2 / rule 19. No CSS framework or component library was added deliberately. The
design surface remains unspecified, so adopting Tailwind or shadcn would be a rule-19 dependency
decision requiring owner approval.

**Q: Why is Super Admin powerless over contracts?**  
A: Locked Step 23 / Step 24 r8. Admin is a system role for account/permission management.
Contract and Legal content access are separate permissions (contract.view, legal.review, etc.).
This prevents accidental disclosure through an unguarded admin account.

**Q: Can I cache permissions across requests?**  
A: No. Locked S-1: permissions are resolved fresh from the database on every request. Cached
permissions would delay the effect of a revocation mid-session.

**Q: Why no microservices?**  
A: Locked Step 39 specifies a monolith. Analysis is synchronous for small documents and
background (Celery) for large ones, both within the same deployment image.

---

## Related Documentation

- [Authentication System](../06-security/STEP_47_SECURITY_SPECIFICATION.md) — Locked auth decisions
- [Authorization System](../06-security/OWNERSHIP.md) — Object visibility & scope
- [User Roles](../01-product/USER_ROLES.md) — Role definitions and permissions
- [DESIGN.md](../../DESIGN.md) — Visual design constraints
- [all_lock.md](../../all_lock.md) — Complete specification record

---

**Last Updated:** 2026-09-01  
**Status:** Reference Documentation  
**Completeness:** 100%
