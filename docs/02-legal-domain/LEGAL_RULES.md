# Legal Rules

Source: all_lock.md Step 20 (Clause Library & Requirement Structure), with supporting cross-references from Steps 27, 28, 31. Canonical source: all_lock.md (Steps 20, 27-28, 31).

Related: [COMPANY_STANDARDS.md](./COMPANY_STANDARDS.md) · [FINDING_CLASSIFICATION.md](./FINDING_CLASSIFICATION.md) · [LEGAL_DECISIONS.md](./LEGAL_DECISIONS.md) · [../04-analysis-engine/REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md)

## Structured Legal Rules vs. Company Standards vs. Documents

**Status: LOCKED** (Step 20)

LegalMind V1 maintains a centralized Clause Library. A Clause represents a legal concept; a Requirement defines what must be satisfied for that concept. A structured Legal Rule (the "Pre-approved Legal Rule") is distinct from both the Company Standard and any source contract document.

```text
Clause
  ↓
Requirement
  ↓
Company Standard
  ↓
Pre-approved Legal Rule (if one exists)
  ↓
Legal Decision (if required)
```

### Pre-approved Legal Rule

A Pre-approved Legal Rule is an explicitly authorized Legal/Admin rule defining an acceptable variation from the Company Standard. LegalMind must never invent this rule, and not every Clause needs one.

```text
Company Standard: 6 months
Pre-approved: up to 12 months
Outside rule: Approval Required
```

### Locked Rules (Step 20)

1. Company Standard is the default organizational position.
2. A deviation is a comparison finding, not automatically a risk rating.
3. A Pre-approved Legal Rule may define an explicitly authorized acceptable variation.
4. Not every Clause requires a Pre-approved Legal Rule.
5. Outside an applicable Pre-approved Legal Rule, case-specific Legal approval is required.
6. If no rule exists, LegalMind must not invent an interpretation.
7. Legal Decisions remain separate from automated comparison and rule evaluation.
8. Normal users cannot approve deviations or customizations.
9. Clause, Requirement, Company Standard, and Pre-approved Legal Rule are separate and versioned.
10. Historical Reviews retain the exact configuration/rule versions used.
11. Used Clause Library entries are not physically deleted; they may be deprecated.
12. Document Type and Legal/Regulatory Reference remain separate concepts.

### Example — Limitation of Liability

```text
Company Standard: 6 months
Customer: 12 months
→ DEVIATION
→ Within pre-approved rule
→ No case-by-case approval

Customer: 18 months
→ DEVIATION
→ Outside pre-approved rule
→ APPROVAL REQUIRED
→ Authorized Legal decision
```

This example is illustrative only. Actual Legal Rules must be configured by authorized Legal/Admin users.

## Legal Rule's Role in the Requirement Model (Step 28)

**Status: LOCKED**

Each Requirement conceptually contains a Legal Rule alongside the Company Standard:

```text
Requirement ID
Document Type
Clause / Topic
Company Standard
Legal Rule
Required / Optional
Version
```

Example:

```text
LIABILITY-001

Document Type:
MSA

Clause:
Limitation of Liability

Company Standard:
6 months

Legal Rule:
≤12 months = Acceptable
>12 months = Approval Required
Unlimited = Unacceptable
```

Company Standard evaluation is separate from Legal Rule evaluation, and Legal Rule evaluation is separate from the Legal Decision (see [LEGAL_DECISIONS.md](./LEGAL_DECISIONS.md)). Full mapping-state rules (CONFIRMED / AMBIGUOUS / UNRESOLVED) live in [../04-analysis-engine/REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md).

## Legal Rule Evaluation in the Comparison Pipeline (Step 27)

**Status: LOCKED**

* Comparison operates through structured Requirements and mapped clauses.
* Finding classification is separate from Legal Rule evaluation.
* Legal Rule evaluation is separate from the Legal Decision.
* Legal Decisions are made only by authorized Legal users.
* Risk/severity is configuration-driven and is not hard-coded solely from Finding type.

### Example

```text
Customer:
Liability = 12 months

Company Standard:
Preferred = 6 months

Legal Rule:
≤12 months = Acceptable
>12 months = Approval Required
Unlimited = Unacceptable

Finding:
DEVIATION

Rule Evaluation:
Acceptable

Legal Decision:
Not automatically required
```

Full finding-type detail is in [FINDING_CLASSIFICATION.md](./FINDING_CLASSIFICATION.md).

## Core Separation (Step 31)

**Status: LOCKED**

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
