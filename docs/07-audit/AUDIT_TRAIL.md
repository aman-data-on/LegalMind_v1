# Audit Trail, Evidence & Explainability

Source: all_lock.md Steps 25, 32. Canonical source: all_lock.md (Steps 25, 32).

Related: [../02-legal-domain/LEGAL_DECISIONS.md](../02-legal-domain/LEGAL_DECISIONS.md) · [../02-legal-domain/FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) · [../02-legal-domain/COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md) · [../03-document-model/DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md) · [../06-security/OWNERSHIP.md](../06-security/OWNERSHIP.md)

## Step 25 — Audit Trail & Legal Activity History

**Status: LOCKED**

### Locked Decision

LegalMind V1 will maintain an authoritative, append-only Audit Trail separate from the user-facing Activity History.

The purpose is to establish exactly who performed an action, what resource it affected, what changed, when it happened, and what result followed.

### Locked Rules

1. The authoritative Audit Trail is separate from the user-facing Activity History.
2. Audit events are append-only and must not be silently modified or deleted.
3. Every important Legal/workflow action records the authenticated actor.
4. Every Legal Decision records who made it, when, what was decided, and the relevant Review/Finding.
5. Changes to Legal configuration create versioned records and corresponding audit events.
6. Historical Reviews retain the exact configuration versions used when they were performed.
7. Changing a Legal Decision creates a new decision/history event rather than overwriting the previous decision.
8. Clause, Requirement, Company Standard, and Pre-approved Legal Rule changes are auditable.
9. Ownership and Legal-assignment changes are auditable.
10. Permission and role changes are auditable.
11. Findings retain traceability to relevant contract evidence and Company Standard/configuration evidence.
12. Normal Users see an appropriate workflow timeline, not confidential internal Legal information.
13. Authorized Legal/Admin users can access deeper Legal audit information according to permission scope.
14. Super Admin does not automatically gain Legal Decision or confidential Legal content access.
15. Audit access itself is auditable.
16. Any future controlled retention/deletion process for audit records must itself generate an audit event.

### Core Audit Event

Conceptually:

```text
Audit Event

eventId
timestamp
actorId
actorRole
action
resourceType
resourceId
reviewId
findingId              optional
configurationVersion   optional
previousState          optional
newState               optional
reason                 optional
metadata               optional
```

The exact database schema will be determined during implementation.

### Example

```text
User A
  → uploaded contract

System
  → created Review

System
  → generated Finding

User A
  → escalated Finding

Legal Reviewer B
  → reviewed Finding

Legal Reviewer B
  → approved customization

System
  → created contract-specific exception

System
  → resolved Review
```

Each significant event remains in the authoritative Audit Trail.

### Historical Configuration Example

```text
Configuration v1
Liability Standard = 6 months

        ↓

Review REV-001 uses v1

        ↓

Later: Legal Admin changes standard

Configuration v2
Liability Standard = 12 months
```

REV-001 continues to reference v1 and therefore continues to show the original 6-month standard.

### Important Separation

```text
Audit Trail
    ≠
Activity History
    ≠
Legal Decision
```

The Audit Trail records what happened.

The Activity History provides an appropriate user-facing timeline.

The Legal Decision represents the authorized legal outcome.

---

## Step 32 — Evidence, Explainability & Audit Trail

**Status: LOCKED**

### Locked Decision

Every LegalMind V1 Finding must be traceable to the exact contract evidence, Requirement, Company Standard, Legal Rule, evaluation, and Legal Decision where applicable.

V1 explainability is deterministic and evidence-based. LLM/RAG is not required.

### Locked Rules

1. Every Finding must have traceable evidence or an explicit explainable basis for absence, such as `MISSING`.
2. Evidence references an immutable Document Version.
3. Evidence stores relevant source text whenever extraction permits.
4. Evidence stores document location using multiple references where available: section/clause, page, and stable text location.
5. Every Finding references the applicable Requirement version.
6. Every Finding references the Company Standard/configuration version used.
7. Every Finding references the applicable Legal Rule version.
8. A Finding must be reproducible from its document/configuration/mapping/evaluation chain.
9. Configuration changes never rewrite historical evidence or Findings.
10. `MISSING` Findings retain an explainable basis even though no customer clause exists.
11. `CONFLICT` Findings may contain multiple evidence references.
12. Legal Decisions reference the Finding they resolve.
13. Legal Decisions include decision-maker, timestamp, decision type, reason, and applicable configuration context.
14. Legal Audit Trail and technical application logs are separate concepts.
15. Legal Audit Trail is append-only; historical events cannot be overwritten.
16. Configuration, Finding, Review, and Legal Decision changes generate appropriate Audit events.
17. Historical Reviews remain explainable using the exact document/configuration versions used when the Review was analyzed.
18. The UI allows Legal to inspect the complete Evidence → Requirement → Standard → Rule → Finding → Decision chain.

### Locked Special Cases

#### MISSING

A MISSING Finding has no customer clause to quote, but it must still explain the Requirement, expected provision, search/mapping result, applicable configuration, and Finding.

#### CONFLICT

A CONFLICT Finding may contain multiple evidence references, with each conflicting provision preserved as evidence.

#### AMBIGUOUS / UNRESOLVED

If evidence cannot be mapped reliably, LegalMind must not invent a conclusion. It may produce `AMBIGUOUS`, `UNRESOLVED`, or where appropriate `UNABLE_TO_EVALUATE`. See mapping-state detail in [../04-analysis-engine/REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md).

### Locked Audit Principle

For every Finding, LegalMind must be able to answer:

1. What did the customer contract say?
2. Where exactly did it say it?
3. Which Requirement and Company Standard were used?
4. Which Legal Rule was used and what evaluation produced the Finding?
5. If Legal intervened, who decided what, when, and why?
