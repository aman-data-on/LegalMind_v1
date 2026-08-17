# Security Model

> **See [STEP_47_SECURITY_SPECIFICATION.md](STEP_47_SECURITY_SPECIFICATION.md)** for session/security invariants S-1 – S-10 and audit/security events (§47.8–47.9).


Canonical source: `all_lock.md` (Steps 5, 24, 38.21–38.24, 39 "Security", 41.24, 43.23)

**Status: LOCKED** for the architectural boundary rules (Steps 38, 41, 43).
**Status: RECOMMENDED (not yet locked)** for the Step 39 security control checklist, which the source frames as a recommendation.

This document is the canonical statement of LegalMind's security *principles and boundaries*. It deliberately does not restate the role matrix or the ownership rules:

* Role/permission matrix → [USER_ROLES.md](../01-product/USER_ROLES.md) (canonical)
* Ownership and review visibility → [OWNERSHIP.md](OWNERSHIP.md) (canonical)
* Authorization mechanics → [AUTHORIZATION.md](AUTHORIZATION.md) (canonical)
* Authentication responsibilities → [AUTHENTICATION.md](AUTHENTICATION.md) (canonical)

---

## 1. The security boundary (Step 38.21)

**Status: LOCKED**

The architecture should enforce:

```text
Authentication → Authorization → Business Operation → Database
```

Never:

```text
UI permission → Trust user
```

Ownership and role checks happen on the server.

---

## 2. No direct UI → database access (Step 38.22)

**Status: LOCKED**

The frontend should not directly manipulate the database.

Correct:

```text
UI → API/Application Layer → Domain Logic → Database
```

This allows permissions, validation, audit, and business rules to be enforced centrally.

---

## 3. No UI → analysis-engine shortcuts (Step 38.23)

**Status: LOCKED**

The UI should never implement its own version of legal evaluation.

For example, don't do:

```text
Frontend: if liability > 6: deviation
```

Instead:

```text
UI → Analysis API → Evaluation Engine → Finding
```

There must be one source of truth for legal evaluation.

---

## 4. API/domain boundary (Step 38.24)

**Status: LOCKED**

The API layer should orchestrate operations. For example:

```text
POST /reviews → Review Service → Document Version → Configuration Snapshot → Analysis Job
```

The exact endpoint naming is **not** locked here. API design is determined during implementation architecture. See [API_ARCHITECTURE.md](../05-architecture/API_ARCHITECTURE.md).

---

## 5. Critical authorization rule — object-level authorization (Step 41.24)

**Status: LOCKED**

Never rely on:

```text
GET /reviews/123
```

and assume that knowing `123` means access is allowed.

The backend must evaluate:

```text
Authenticated User
       ↓
Review
       ↓
Contract
       ↓
Owner / Role
       ↓
Permission
```

This protects against IDOR/object-level authorization failures.

---

## 6. Authorization model (Step 43.23)

**Status: LOCKED**

Authorization should happen at the API/service boundary.

Example:

```text
Request
 ↓
Authentication
 ↓
Role check
 ↓
Object ownership check
 ↓
Operation permission
 ↓
Domain operation
```

Never:

```text
Request
 ↓
Fetch object by ID
 ↓
Return object
```

without checking authorization.

---

## 7. Confidentiality of internal legal strategy (Step 5, Step 9, Step 24)

**Status: LOCKED**

The system must separate:

> **What the comparison engine knows**

from:

> **What each user is authorized to see.**

Internal legal strategy must not leak to ordinary users or counterparties. A normal User must not automatically see preferred positions, acceptable thresholds, approval thresholds, unacceptable positions, internal negotiation strategy, or internal legal comments.

The same Review may therefore produce different views depending on authorization:

```text
                    REVIEW
                      │
             ┌────────┴────────┐
             ↓                 ↓
        NORMAL USER       AUTHORIZED LEGAL/ADMIN
             │                 │
      Comparison result   Internal legal context
      Findings            Approval information
      Evidence            Internal comments
      High-level risk     Decisions
      Escalation
```

Full detail: [WORKFLOWS.md](../01-product/WORKFLOWS.md) (Step 5 — Legal Position Visibility) and [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) (Step 9 — Security and Visibility).

---

## 8. Recommended V1 security controls (Step 39)

**Status: RECOMMENDED (not yet locked)** — the source presents this as a recommendation, not an explicit lock.

Because these are legal documents, security isn't an optional add-on. V1 should include:

```text
TLS
Authentication
Server-side RBAC
Object-level authorization
Encrypted storage where supported
Secrets outside source code
Upload validation
Safe document parsing
Malware scanning where available
Audit trail
Rate limiting
Session security
Database backups
```

And importantly:

> A user must never be able to access another user's Contract, Document Version, Review, Finding, or Legal Decision merely by changing an ID in an API request.

---

## 9. Document ingestion is untrusted input

**Status: LOCKED** (Step 34)

Uploaded documents are untrusted input and must be parsed safely. See [PROCESSING_PIPELINE.md](../03-document-model/PROCESSING_PIPELINE.md) for the locked ingestion-security rules.
