# Legal Decisions

Source: all_lock.md Step 31, with the separation principle reiterated at Steps 17, 18, 20, 22, 27. Canonical source: all_lock.md (Step 31, principle cross-referenced from Steps 17-18, 20, 22, 27).

Related: [FINDING_CLASSIFICATION.md](./FINDING_CLASSIFICATION.md) · [LEGAL_RULES.md](./LEGAL_RULES.md) · [COMPANY_STANDARDS.md](./COMPANY_STANDARDS.md) · [../07-audit/AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md)

## A Legal Decision Is Separate From a Finding and From Company Standards

**Status: LOCKED** — this separation recurs throughout the locked-decision range and is treated as a running principle:

* Step 17: "A Finding is not a Legal Decision."
* Step 18: "Legal decisions remain a separate authorized workflow."
* Step 20: "Legal Decisions remain separate from automated comparison and rule evaluation."
* Step 22: "A Legal Decision is separate from a Finding."
* Step 27: "A Finding is not itself a Legal Decision." Also: "Legal Rule evaluation is separate from the Legal Decision."

## Step 31 — Legal Decision & Approval Workflow

**Status: LOCKED**

### Locked Decision

Automated LegalMind analysis never makes the final Legal Decision. Authorized Legal users make decisions on Findings that require Legal review.

### Locked Decision Vocabulary

```text
ACCEPT_DEVIATION
REQUIRE_COMPANY_STANDARD
APPROVE_CUSTOMIZATION
REJECT
REQUEST_CLARIFICATION
```

### Locked Definitions

#### ACCEPT_DEVIATION

The specific deviation is accepted for this Review. It does not change the Company Standard.

#### APPROVE_CUSTOMIZATION

A contract-specific customization is authorized for this Review. It does not change the Company Standard.

#### REQUIRE_COMPANY_STANDARD

The customer provision should conform to the applicable Company Standard.

#### REJECT

The specific contractual position/Finding is rejected. This does not automatically mean the entire contract is rejected.

#### REQUEST_CLARIFICATION

Required clarification/action is requested and the relevant workflow remains unresolved until completed.

### Locked Rules

1. Automated analysis does not make final Legal Decisions.
2. Authorized Legal users make decisions on Findings requiring Legal review.
3. Legal Decision types use a controlled vocabulary.
4. `ACCEPT_DEVIATION` applies only to the specific Review/Finding.
5. `APPROVE_CUSTOMIZATION` authorizes only a contract-specific customization.
6. Neither `ACCEPT_DEVIATION` nor `APPROVE_CUSTOMIZATION` changes the Company Standard.
7. Company Standard changes use the Step 29 Legal Configuration versioning workflow (see [COMPANY_STANDARDS.md](./COMPANY_STANDARDS.md)).
8. `REQUIRE_COMPANY_STANDARD` requires the customer position to conform to the applicable Company Standard.
9. `REJECT` applies to the specific contractual position/Finding and does not automatically reject the entire contract.
10. `REQUEST_CLARIFICATION` leaves the required workflow unresolved until the clarification/action is completed.
11. Every Legal Decision requires a reason/comment.
12. Every Legal Decision records the decision-maker and timestamp.
13. Contract-specific Legal Decisions are separate from Company Configuration changes.
14. Legal Decision history is immutable; a later change creates a new decision version rather than overwriting the previous decision.
15. Requirements may be configured to require independent second-person approval for consequential contract-specific decisions.
16. Before deciding, Legal must be shown the underlying evidence, Requirement, Company Standard, applicable Legal Rule, and Finding.
17. A Legal Decision resolves the relevant Finding; it does not automatically constitute approval of the entire contract.
18. A Review becomes `RESOLVED` only when all required decisions/actions are complete.
19. All Legal Decisions and changes are included in the Audit Trail.
20. The current decision must always be distinguishable from historical decisions.

### Core Separation

```text
COMPANY STANDARD
       ↓
What the company normally wants

LEGAL RULE
       ↓
How the position is evaluated

FINDING
       ↓
What the customer contract contains

LEGAL DECISION
       ↓
What Legal decides for THIS contract

CONFIGURATION CHANGE
       ↓
Changes what future Reviews compare against
```

### Example

```text
Company Standard:
6 months

Customer Contract:
12 months

Finding:
DEVIATION

Legal Decision:
APPROVE_CUSTOMIZATION

Result:
This contract may use 12 months.

Company Standard:
Remains 6 months.
```

### Decision Change Example

```text
Decision v1:
APPROVE_CUSTOMIZATION
        ↓
Superseded

Decision v2:
REQUIRE_COMPANY_STANDARD
```

Both decisions remain in history; v2 is the current decision.

### Decision Record

Each Legal Decision should retain, at minimum:

```text
Review ID
Finding ID
Decision ID
Decision Type
Decision Maker
Decision Timestamp
Reason
Previous Decision ID, when applicable
Applicable Configuration Version
```
