# User Roles, Permissions & Review Lifecycle

Source: all_lock.md Steps 23, 24, 30. Canonical source: all_lock.md (Steps 23-24, 30).

Related: [../06-security/AUTHORIZATION.md](../06-security/AUTHORIZATION.md) · [../06-security/OWNERSHIP.md](../06-security/OWNERSHIP.md) · [../02-legal-domain/FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) · [../02-legal-domain/LEGAL_DECISIONS.md](../02-legal-domain/LEGAL_DECISIONS.md)

> This file is the **canonical** role/permission model for LegalMind V1. It supersedes any earlier draft permission matrix appearing elsewhere in the spec (e.g. an earlier Step 3 draft) — Step 23 is explicitly locked and later in the document.

## Step 23 — Roles & Permission Matrix

**Status: LOCKED**

### Locked Decision

LegalMind V1 will use four base roles:

* User
* Legal Reviewer
* Legal Admin
* Super Admin

Roles provide the baseline permission set, while explicit permissions and resource scope provide finer control.

### Locked Rules

1. User cannot make Legal Decisions.
2. User cannot approve contract-specific customizations.
3. User can upload contracts, create Reviews, view permitted comparison results/evidence, and escalate findings.
4. Legal Reviewer handles contract/legal review.
5. Legal Admin manages controlled Legal configuration.
6. Super Admin manages platform, users, roles, and permissions.
7. Super Admin does not automatically have Legal authority.
8. Legal Decision authority is an explicit permission.
9. Approval of contract-specific customization is an explicit permission.
10. Legal configuration permissions are separate from Legal review permissions.
11. Role names alone do not determine resource scope.
12. Permissions support resource scope such as own, assigned, Legal scope, or system scope.
13. Internal Legal Rules are inaccessible to normal Users.
14. User/role administration is separate from Legal configuration.
15. Review visibility/scope is deliberately left for a separate decision before implementation (resolved at Step 24, see [../06-security/OWNERSHIP.md](../06-security/OWNERSHIP.md)).

### Recommended Permission Model

**Status: PROVISIONAL**

```text
ROLE
  ↓
PERMISSIONS
  ↓
RESOURCE SCOPE
```

Example:

```text
Legal Reviewer
  + legal.review
  + review.scope = assigned
```

A selected Legal user may additionally have:

```text
legal.decision
legal.approve_customization
```

without automatically receiving Legal configuration permissions.

### Role Summary

**Status: LOCKED** (summarizes the locked rules above)

```text
USER
- Upload/create Review
- View permitted own Reviews
- View findings/evidence
- Escalate
- No Legal approval
- No Legal configuration

LEGAL REVIEWER
- Legal review
- View assigned/permitted Reviews
- View findings/evidence
- View applicable internal Legal Rules
- Make Legal Decisions when explicitly permitted
- Approve customization when explicitly permitted
- No user/role administration

LEGAL ADMIN
- Legal Reviewer capabilities
- Manage Clause Library
- Manage Requirements
- Configure Company Standards
- Configure Pre-approved Legal Rules
- Version/deprecate Legal configuration
- No automatic platform/user administration

SUPER ADMIN
- Manage users
- Manage roles
- Manage permissions
- Platform/system administration
- Audit/system administration
- No automatic Legal Decision authority
```

### Example

```text
User finds:
Customer Liability = 18 months
Company Standard = 6 months

Finding:
DEVIATION

User:
[View Evidence]
[Escalate to Legal]

User cannot:
[Approve Customization]
```

An authorized Legal user with the explicit approval permission can make the Legal Decision.

A Super Admin without that Legal permission cannot approve the customization merely because they are a Super Admin.

### Important Separation

```text
Legal Review
      ≠
Legal Configuration
      ≠
Platform Administration
```

These responsibilities must remain separately permissioned.

The exact Review visibility model (who can see whose contracts/Reviews) is defined in Step 24, below.

---

## Step 24 — Review Visibility & Ownership

**Status: LOCKED**

### Locked Decision

LegalMind V1 will use an ownership + authorized-scope access model.

Every Review has an owner. The creator is the initial owner unless the Review is explicitly transferred or assigned.

### Locked Rules

1. Every Review has an owner.
2. The Review creator is the initial owner unless explicitly transferred/assigned.
3. A normal User can access their own Reviews.
4. A normal User cannot access another User's Reviews by default.
5. Escalation makes the Review available to the authorized Legal workflow.
6. Legal Reviewer access is controlled by assignment and/or explicit Legal scope.
7. Legal Admin has authorized Legal-scope access but does not automatically have unrestricted platform access.
8. Super Admin does not automatically have access to confidential contract or Legal content.
9. Contract-content access and platform administration are separate permissions.
10. Internal Legal Rules and confidential Legal Decision details are protected from normal Users.
11. A User can see the user-facing outcome of their own Legal review without necessarily seeing confidential internal Legal reasoning or Legal thresholds.
12. Access is based on permission + resource scope, not simply role name.
13. Least-privilege access is the default.
14. Access restrictions must be enforced server-side, not only by hiding UI elements.
15. Access to confidential Legal information must be auditable.
16. A Review may be visible to an authorized Legal Reviewer without transferring ownership from the original User.
17. Legal assignment gives access for Legal work; it does not make the Legal Reviewer the business owner of the Review.
18. A resolved Review remains accessible to its owner according to the same ownership rules, while Legal access remains governed by Legal scope/assignment.

For the full ownership-specific detail and access matrix, see [../06-security/OWNERSHIP.md](../06-security/OWNERSHIP.md). For authorization mechanics, see [../06-security/AUTHORIZATION.md](../06-security/AUTHORIZATION.md).

### Example

```text
User A
   │
   │ uploads ABC MSA
   ▼
Review REV-001
Owner = User A
   │
   ▼
Comparison
   │
   ▼
DEVIATION
   │
   │ User A escalates
   ▼
Legal Queue
   │
   │ assigned to
   ▼
Legal Reviewer B
   │
   ▼
Legal Review
   │
   ▼
Approved Customization
   │
   ▼
RESOLVED
```

Access:

```text
User A
✓ Own contract
✓ Own findings/evidence
✓ User-facing resolution

User B
✗ No access by default

Legal Reviewer B
✓ Authorized contract content
✓ Evidence
✓ Findings
✓ Internal Legal evaluation
✓ Legal Decision

Legal Admin
✓ Authorized Legal-scope Reviews
✓ Legal configuration

Super Admin
✓ Platform administration
✗ Legal content unless explicitly granted
```

### Important Separation

```text
Ownership
   ≠
Legal Assignment
   ≠
Platform Administration
```

A Legal Reviewer can be assigned to a Review without becoming its owner.

A Super Admin can administer the platform without automatically gaining Legal content access.

A normal User can own a Review without gaining any Legal approval authority.

---

## Review Lifecycle (Step 22 — Core Workflow, Ownership & Escalation)

**Status: LOCKED**

### Locked Decision

A Review has its own workflow lifecycle, separate from Findings and Legal Decisions.

### Core Workflow

```text
USER
  │
  │ Upload
  ▼
REVIEW
  │
  ▼
COMPARISON
  │
  ▼
FINDINGS
  │
  ├─────────────── No Legal action needed
  │                       ↓
  │                   COMPLETED
  │
  └── Escalate
          ↓
     LEGAL REVIEW
          ↓
     LEGAL DECISION
          │
          ├── Require Standard
          │
          └── Approve Customization
                    ↓
              Contract Exception
                    ↓
                 RESOLVED
```

### Locked Rules

1. A Review has its own lifecycle/status separate from Legal Decisions.
2. Normal Users can upload contracts and create Reviews.
3. Normal Users can view comparison results and evidence.
4. Normal Users can escalate findings.
5. Normal Users cannot approve findings, deviations, customizations, or contracts.
6. Legal decisions are available only to authorized Legal users.
7. A Legal Decision is separate from a Finding.
8. An approved customization creates a contract-specific exception.
9. An exception does not modify the Company Standard.
10. An exception does not automatically modify the Legal Rule.
11. V1 records approved customizations but does not automatically rewrite DOCX/PDF.
12. Historical Reviews retain their original contract/configuration versions.
13. `RESOLVED` means the workflow issue has an authorized resolution; it does not necessarily mean the contract exactly matches the Company Standard.
14. A new contract version receives a new Review.
15. A Review can complete without Legal escalation when no finding requires Legal action.

### Recommended V1 Review Statuses (Step 22 draft list)

**Status: PROVISIONAL** — this Step 22 status list is superseded for canonical purposes by the Step 30 Locked Review Lifecycle below, which is the authoritative state machine.

```text
DRAFT
  ↓
PROCESSING
  ↓
READY_FOR_REVIEW
  ↓
IN_REVIEW
  ↓
ESCALATED
  ↓
LEGAL_REVIEW
  ↓
DECISION_REQUIRED
  ↓
RESOLVED
```

A review with no required Legal action may proceed from user review to `COMPLETED`.

### Example — Approved Customization

```text
Company Standard:
6 months

Customer Contract:
18 months

Finding:
DEVIATION

Legal Decision:
Approve Customization

Exception:
18 months
Scope: ABC MSA v1 only

Review:
RESOLVED
```

The Company Standard remains 6 months. The exception is contract-specific and does not become a new Company Standard.

For the `RESOLVED ≠ MATCH` clarification (also part of Step 22, locked), see [../02-legal-domain/FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md#resolved--match--critical-locked-rule).

---

## Review Lifecycle & Status Management (Step 30)

**Status: LOCKED** — full content relocated to [WORKFLOWS.md](./WORKFLOWS.md#review-lifecycle--status-management-step-30), which now exists in this docs tree (it did not exist at the time this section was first drafted). See that file for the complete locked Review Lifecycle state machine (`DRAFT → UPLOADED → PROCESSING → ANALYSIS_COMPLETE → LEGAL_REVIEW → RESOLVED → CLOSED`, plus exception states `ANALYSIS_FAILED`/`CANCELLED`), locked definitions, locked rules, conceptual separation, configuration snapshot rule, and example.

For the `RESOLVED ≠ MATCH` clarification, see [../02-legal-domain/FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md#resolved--match--critical-locked-rule).

## Note on an Earlier Step 22 Lifecycle Diagram

Step 22 ("Review Lifecycle") preceded Step 23/24/30 in the source and included its own core workflow diagram and a "Recommended V1 Review Statuses" list (`DRAFT → PROCESSING → READY_FOR_REVIEW → IN_REVIEW → ESCALATED → LEGAL_REVIEW → DECISION_REQUIRED → RESOLVED`) plus a locked rule set about ownership/escalation of Reviews. That status list differs from the Step 30 locked lifecycle transcribed above — see the Contradictions note in the transcription report for how these two relate.
