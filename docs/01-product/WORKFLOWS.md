# LegalMind V1 — Workflows (RBAC, Review, Escalation, Comparison Sources)

Source: all_lock.md, lines 1–1140 (Steps 3–5). Canonical source: all_lock.md (Steps 1-9).

---

## Step 3 — RBAC and Permissions

**Status: LOCKED** (concept) — permission matrix below is **Status: PROVISIONAL**

LegalMind should use **RBAC (Role-Based Access Control)**.

Conceptually:

```text
User
  ↓
Role
  ↓
Permissions
  ↓
Authorization Check
  ↓
Action
```

Job title and application role remain separate.

Example:

```text
Department = Sales
Role = User
```

or:

```text
Department = Legal
Role = Reviewer
```

### Proposed technical roles

* `Super Admin`
* `Admin`
* `Reviewer`
* `User`
* `Viewer`
* `Auditor`

### Working permission groups

**Status: PROVISIONAL** — the source text states these "are a draft and are NOT yet the final production matrix." This section is superseded/refined by the canonical permission matrix in [USER_ROLES.md](./USER_ROLES.md) (from Step 23), which should be treated as authoritative once available.

```text
Documents
- View
- Upload
- Edit
- Delete
- Download

Comparison
- Create
- View

Findings
- View
- Review
- Comment

Escalation
- Create

Legal Decision
- Approve
- Reject
- Request Changes

Customization
- Customize
- Finalize

Legal Positions
- View
- Create
- Edit
- Delete

Reports
- View
- Generate

Administration
- Manage Users
- Manage Roles
- Manage Settings

Audit
- View
```

### Critical rule

**Status: LOCKED**

A normal `User` does **not** have legal decision permissions.

Their workflow is:

```text
Upload
  ↓
Compare
  ↓
View
  ↓
Escalate
```

---

## Step 4 — Review, Escalation & Legal Authority

**Status: LOCKED**

### Confirmed principle

A normal User can only:

* Compare
* View
* Escalate

A normal User cannot make a legal decision.

### Workflow

```text
User
  ↓
Upload Contract
  ↓
Run Comparison
  ↓
View Findings
  ↓
Escalate if needed
  ↓
Reviewer / Authorized Legal Authority
  ↓
Legal Decision
```

### Escalation is not approval

An escalation means:

> "This requires authorized review."

It does not mean:

> "I approve this deviation."

Example:

```text
ESC-0001

Contract:
ABC Technologies MSA

Finding:
Unlimited Liability

Risk:
High

Raised by:
User A

Reason:
Please review this deviation.

Status:
Pending Review
```

### Review vs Legal Approval

**Review** means examining the contract, clause, company standard, comparison, evidence, risk, and comments.

**Legal approval** means the organization authorizes a specific deviation/exception.

These are separate authorities.

### Admin vs legal approval authority

`Admin` is a **system role**.

Being an Admin does **not** automatically grant legal approval authority.

Approval authority is a separate permission/capability that can be assigned to specific Admins.

Example:

```text
Admin A
- System administration: YES
- Legal approval: NO

Admin B
- System administration: YES
- Legal approval: YES
```

**Status: NOT YET SPECIFIED** — "Later we may introduce granular approval limits, but those are not finalized yet."

---

## Step 5 — Comparison Sources

**Status: LOCKED**

LegalMind V1 should compare a counterparty contract against:

1. The organization's standard documents
2. The organization's internal legal positions

Conceptually:

```text
                 Counterparty Contract
                         ↓
                Comparison Engine
                    /         \
                   /           \
                  ↓             ↓
       Standard Documents   Legal Positions
                                  ↓
                           Internal Rules
                                  ↓
                              Findings
```

### Why both?

A standard document provides the organization's standard wording/document.

A legal position provides the organization's internal tolerance and decision framework.

Example internal position:

```text
Topic:
Limitation of Liability

Preferred:
6 months

Acceptable:
Up to 12 months

Requires approval:
More than 12 months

Unacceptable:
Unlimited
```

This is useful to the comparison engine but contains internal legal strategy.

---

## Legal Position Visibility

**Status: LOCKED**

Internal Legal Positions are **permission-controlled information**.

A normal User must not automatically see:

* Preferred positions
* Acceptable thresholds
* Approval thresholds
* Unacceptable positions
* Internal negotiation strategy
* Internal legal comments

### Normal User view

```text
Customer MSA
      ↓
Comparison
      ↓
Finding

Liability clause:
12 months

Status:
Deviation detected

Risk:
Requires Legal Review

[Escalate to Legal]
```

### Authorized Admin view

An authorized Admin can see the internal context needed for the decision:

```text
Customer position:
12 months

Organization position:
6 months

Internal tolerance:
Up to 12 months

Approval requirement:
...

Risk:
...

[Approve]
[Reject]
[Request Changes]
```

### Security principle

The system must separate:

> **What the comparison engine knows**

from:

> **What each user is authorized to see.**

Internal legal strategy must not leak to ordinary users or counterparties.

---

## Cross-reference

Role/permission specifics in this document (Step 3 draft matrix) are provisional and are superseded/refined by the canonical permission matrix at [../01-product/USER_ROLES.md](../01-product/USER_ROLES.md) (Step 23), maintained by a separate agent. The RBAC concept, escalation-vs-approval distinction, and legal-position visibility rules above remain locked as described.

---

## Review Lifecycle & Status Management (Step 30)

Canonical source: all_lock.md (Step 30). Added by a subsequent transcription pass covering Steps 17–32.

**Status: LOCKED**

### Locked Decision

LegalMind V1 separates Review lifecycle, Finding status, Legal Decision, and comparison outcome. A single status field must not be used to represent all of these concepts.

### Locked Review Lifecycle

```text
DRAFT
  ↓
UPLOADED
  ↓
PROCESSING
  ↓
ANALYSIS_COMPLETE
  ↓
LEGAL_REVIEW (when required)
  ↓
RESOLVED
  ↓
CLOSED
```

### Exception States

```text
PROCESSING → ANALYSIS_FAILED

DRAFT / UPLOADED → CANCELLED
```

### Locked Definitions

#### DRAFT

Review exists but analysis has not started.

#### UPLOADED

The required Document Version has been attached to the Review.

#### PROCESSING

The system is actively parsing, segmenting, mapping, evaluating, and generating findings.

#### ANALYSIS_COMPLETE

Automated V1 analysis has completed and Findings/Evidence have been generated. This does not mean Legal approval.

#### LEGAL_REVIEW

One or more Findings require an authorized Legal decision.

#### RESOLVED

All required workflow/Legal decisions have been completed and no required action remains.

`RESOLVED ≠ MATCH`

`RESOLVED ≠ Legal approval of the entire contract`

`RESOLVED ≠ Contract matches the Company Standard`

See the fully worked-out clarification in [../02-legal-domain/FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md#resolved--match--critical-locked-rule).

#### CLOSED

The Review has been formally completed after resolution.

#### ANALYSIS_FAILED

The automated analysis could not complete. This is distinct from a Finding of `UNABLE_TO_EVALUATE`.

#### CANCELLED

A controlled terminal state for an eligible Review that is cancelled before completion.

### Locked Rules

1. Review lifecycle and Finding status are separate concepts.
2. Review status follows a controlled state machine.
3. Users cannot arbitrarily set Review status.
4. The applicable configuration versions are fixed when analysis begins.
5. `ANALYSIS_COMPLETE` means automated analysis finished; it does not mean Legal approval.
6. `LEGAL_REVIEW` is entered only when the configured workflow requires Legal intervention.
7. `RESOLVED` means all required workflow/Legal decisions are complete.
8. `RESOLVED` does not mean MATCH.
9. `RESOLVED` does not mean the contract matches the Company Standard.
10. `RESOLVED` does not mean the contract is universally legally approved.
11. `CLOSED` represents formal workflow completion after resolution.
12. A new contract version creates a new Review rather than silently reopening/replacing the old Review.
13. `ANALYSIS_FAILED` is distinct from a Finding of `UNABLE_TO_EVALUATE`.
14. `CANCELLED` is a controlled terminal state for eligible pre-completion Reviews.
15. Historical Reviews and their status transitions remain auditable.
16. Final summaries should be derived from Findings + Legal Decisions rather than relying on a manually editable final-result field.
17. Each status transition generates an Audit Trail event.

### Conceptual Separation

```text
MATCH / DEVIATION / CONFLICT / MISSING
        ↓
Comparison Finding

Legal Decision
        ↓
Authorized Legal action

RESOLVED
        ↓
Required workflow decisions completed

CLOSED
        ↓
Workflow formally finished
```

### Configuration Snapshot Rule

If a Review begins under configuration v1 and Legal publishes v2 while that Review is processing:

```text
Review starts
    ↓
Configuration v1 captured
    ↓
Legal publishes v2
    ↓
Review continues under v1
```

The Review must not change configuration midway.

### Example

```text
User uploads MSA
      ↓
UPLOADED
      ↓
PROCESSING
      ↓
ANALYSIS_COMPLETE
      ↓
Findings:
- Liability → DEVIATION
- Termination → MATCH
- DPA → MISSING
      ↓
Legal intervention required
      ↓
LEGAL_REVIEW
      ↓
Legal decisions completed
      ↓
RESOLVED
      ↓
CLOSED
```

The Step 22 "Review Lifecycle" core workflow/ownership/escalation rules and the Step 23/24 role and ownership matrix remain documented in [../01-product/USER_ROLES.md](../01-product/USER_ROLES.md); this section covers only the Step 30 status state machine.
