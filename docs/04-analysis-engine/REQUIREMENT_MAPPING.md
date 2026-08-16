# Clause & Requirement Mapping

This file covers **Step 28 (Clause & Requirement Mapping)** and **Step 35 (Requirement & Clause Mapping Engine)**.

Canonical source: all_lock.md (Steps 28, 35).

Related: [../02-legal-domain/DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) (**cross-layer canonical reference**) · [../02-legal-domain/LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md) · [../02-legal-domain/COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md) · [../02-legal-domain/FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md)

---

## ✅ CANONICAL — Mapping State (axis 1)

**Status: LOCKED.** Canonicalized by owner-approved reconciliation `REC-03`, 2026-08-16.

The persisted Mapping State vocabulary is the **Step 28 set**:

```text
CONFIRMED
AMBIGUOUS
UNRESOLVED
```

This is **axis 1** of the [Decision State Model](../02-legal-domain/DECISION_STATE_MODEL.md). It answers *which Requirement a clause relates to* — never what the clause means. Mapping ≠ Evaluation.

### Relationship to Step 35's vocabulary

Step 28 and Step 35 are **different stages of the same layer, not competing vocabularies**:

| | Step 28 | Step 35 |
|---|---------|---------|
| What it defines | The **persisted mapping state** stored against a clause↔Requirement pair | **Internal scoring-stage** labels used while ranking candidates |
| Vocabulary | `CONFIRMED` · `AMBIGUOUS` · `UNRESOLVED` | `CANDIDATE` vs `CONFIRMED`; threshold bands `CONFIRMED` / `CANDIDATE-REVIEW` / `NOT MAPPED`; `NO_CONFIDENT_MAPPING` |
| Status | **LOCKED — canonical** | Mechanism locked; **numerical weights and thresholds explicitly PROVISIONAL** (illustrative, pending a representative contract test set) |

Step 35's band names are internal to the scoring stage. Only the Step 28 states are persisted and exposed.

### ⛔ OPEN — scoring-band → mapping-state mapping

**Status: NOT YET SPECIFIED. Explicitly deferred by owner decision, 2026-08-16.**

The source never states how Step 35's threshold bands (`CANDIDATE-REVIEW`, `NOT MAPPED`, `NO_CONFIDENT_MAPPING`) map onto Step 28's three persisted states. **This mapping must not be inferred, assumed, or implemented until it is explicitly decided.**

In particular, it is **not** established whether `CANDIDATE-REVIEW` corresponds to `AMBIGUOUS`, to `UNRESOLVED`, or to neither. Do not guess.

### Locked bridge to axis 2

* A mapping state of `AMBIGUOUS` or `UNRESOLVED` **may produce** a Finding Classification of `UNABLE_TO_EVALUATE` — never a guessed classification (Step 28 rule 6).
* A required Requirement with no mapped provision may produce `MISSING` (Step 28 rule 5).

### ⚠ Token collision

`AMBIGUOUS` and `UNRESOLVED` also exist on axis 2 (Finding Classification) with **different meanings**, and `AMBIGUOUS` again as an extraction status. They must not share an enum. See the collision table in [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md).

---

## Locked Decision

**Status: LOCKED**

LegalMind V1 maps customer-contract clauses to structured Company Requirements before applying Company Standards and Legal Rules.

A clause is not mapped directly to a Legal conclusion.

## Locked Requirement Model

Each Requirement should conceptually contain:

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

## Locked Mapping States

```text
CONFIRMED
AMBIGUOUS
UNRESOLVED
```

### CONFIRMED

The system has sufficient deterministic evidence to map the clause to the Requirement.

### AMBIGUOUS

More than one plausible mapping exists and LegalMind must not silently choose one.

### UNRESOLVED

The system cannot establish the mapping reliably.

An unresolved mapping must not produce an invented Legal conclusion.

## Locked Rules

1. One clause may map to multiple Requirements.
2. One Requirement may be supported by multiple clauses.
3. Explicit document cross-references should be resolved where deterministically possible.
4. If a cross-reference cannot be safely resolved, LegalMind must not guess.
5. A required Requirement with no mapped provision may produce a MISSING Finding.
6. An ambiguous or unresolved mapping may produce UNABLE_TO_EVALUATE rather than a guessed classification.
7. Every mapping retains evidence showing the relevant customer clause and Requirement.
8. Requirement mapping is separate from Company Standard evaluation.
9. Company Standard evaluation is separate from Legal Rule evaluation.
10. Legal Decision remains separate from all automated mapping/evaluation.
11. Administrators can change individual Requirements/Standards/Rules without replacing the entire source contract document.
12. Changes to Requirements/Standards/Rules create new configuration versions.
13. Existing Reviews continue to reference the exact configuration versions used at review time.
14. New Reviews use the currently active applicable configuration versions.
15. A mapping must be reproducible from the relevant Document Version and configuration versions.
16. The technical algorithm used for candidate retrieval/mapping will be selected later during technical design; V1 behavior is locked now.

## Conceptual Pipeline

```text
Customer Clause
      ↓
Candidate Requirement(s)
      ↓
Mapping Status
      ↓
CONFIRMED / AMBIGUOUS / UNRESOLVED
      ↓
Company Standard Evaluation
      ↓
Legal Rule Evaluation
      ↓
Finding
      ↓
Legal Decision when required
```

---

# Step 35 — Requirement & Clause Mapping Engine

Source: all_lock.md Step 35. Canonical source: all_lock.md (Steps 28, 35).

This is where things become technically interesting.

The goal is:

```text
Contract
   ↓
Clause
   ↓
Requirement
```

**without LLM, RAG, vector database, or semantic AI.**

---

## 35.1 Core principle

The mapping engine should be:

> **Deterministic first, explainable always.**

We shouldn't ask:

> "Does this paragraph sound like liability?"

Instead, we should have structured Requirements with deterministic matching logic.

---

## 35.2 Requirement definition

A Requirement should contain structured metadata.

Example:

```text
Requirement:
LIABILITY-001

Name:
Limitation of Liability

Category:
Liability

Expected:
Contract must contain a liability limitation.

Required:
YES
```

Then mapping logic can specify what should be looked for.

---

## 35.3 Requirement aliases

Legal language can vary.

For example:

```text
Limitation of Liability
Limitation on Liability
Liability Cap
Aggregate Liability
Maximum Liability
```

These can be configured as deterministic aliases.

This is **not semantic AI**.

It is controlled legal configuration.

---

## 35.4 Keyword groups

Instead of one keyword:

```text
liability
```

use groups.

Example:

```text
GROUP A:
liability
liable
aggregate liability

GROUP B:
cap
limited
shall not exceed
maximum

GROUP C:
fees
amount paid
contract value
```

The engine can evaluate combinations.

For example:

```text
Group A
+
Group B
```

is stronger evidence than:

```text
liability
```

alone.

---

## 35.5 Negative terms

We also need exclusion patterns.

Example:

```text
"liability shall not be limited"
```

contains:

```text
liability
limited
```

but means the opposite of a liability cap.

So rules need:

```text
Positive patterns
+
Negative patterns
```

This is critical.

---

## 35.6 Clause-level mapping

Don't map an entire document at once.

Use:

```text
Document
 ↓
Sections
 ↓
Candidate Clauses
 ↓
Requirement Mapping
```

Example:

```text
Section 8.2
"Aggregate liability shall not exceed..."
        ↓
LIABILITY-001
```

---

## 35.7 Candidate vs confirmed mapping

This is an important safeguard.

The engine should distinguish:

```text
CANDIDATE
```

from:

```text
CONFIRMED
```

For example:

```text
Keyword match:
liability
```

doesn't automatically mean:

```text
Confirmed Liability Requirement
```

A stronger rule must be satisfied.

---

## 35.8 Deterministic scoring

**Status: PROVISIONAL** — the numerical weights below are explicitly called *illustrative* by the source and are **not locked yet**. Only the principle (deterministic, explainable scoring) is locked; the numbers must be validated before locking.

We can use a deterministic scoring/ranking mechanism to rank candidate clauses.

For example:

```text
Exact phrase match       +5
Alias match              +3
Required keyword group   +3
Section heading match    +2
Negative pattern         -5
```

These numbers are **illustrative**, not locked yet.

The important principle is:

> The score is deterministic and explainable.

The engine can say:

```text
Matched:
"limitation of liability"

Matched:
"shall not exceed"

Section:
8.2 Limitation of Liability

Candidate score:
X
```

This is very different from an opaque AI confidence score.

---

## 35.9 Thresholds

**Status: PROVISIONAL** — the source explicitly recommends **not locking numerical thresholds yet**; they are to be determined experimentally during algorithm validation.

We can then have:

```text
High deterministic match
       ↓
CONFIRMED

Medium
       ↓
CANDIDATE / REVIEW

Low
       ↓
NOT MAPPED
```

But I recommend **not locking numerical thresholds yet**.

We should determine them experimentally using a representative contract test set.

That belongs in the algorithm-validation stage.

---

## 35.10 Requirement-specific mapping rules

Not every Requirement should use the same algorithm.

Example:

### Liability

Look for:

```text
liability
liable
aggregate
cap
maximum
fees
```

### Termination

Look for:

```text
terminate
termination
notice
convenience
breach
```

### Governing Law

Look for:

```text
governing law
laws of
jurisdiction
venue
```

So each Requirement can have its own deterministic mapping configuration.

---

## 35.11 Section heading importance

A clause under:

```text
LIMITATION OF LIABILITY
```

should be treated differently from a random sentence mentioning:

```text
liability
```

Therefore section headings can contribute to mapping.

Example:

```text
Heading:
Limitation of Liability

Body:
Aggregate liability shall not exceed...
```

This is extremely strong deterministic evidence.

---

## 35.12 Cross-reference handling

Contracts often say:

> "Subject to Section 12.4."

The engine should preserve cross-references.

For example:

```text
Clause 8.2
      ↓
references 12.4
      ↓
12.4 contains exception
```

This becomes important for Conflict detection later.

We don't necessarily need full legal reasoning here, but the mapping layer must retain the relationship.

---

## 35.13 Multiple clauses can map to one Requirement

Example:

```text
Requirement:
LIABILITY-001
```

might map to:

```text
8.2
14.4
Schedule B
```

That doesn't necessarily mean there are three separate Findings.

The Evaluation Engine in Step 36 decides what those mapped clauses collectively mean.

This separation is important:

```text
Mapping
≠
Evaluation
```

---

## 35.14 One clause can map to multiple Requirements

Example:

```text
Clause 12.3
```

could contain:

```text
Termination
+
Liability
+
Indemnification
```

So:

```text
Clause
 ↓
Requirement A
Requirement B
Requirement C
```

The mapping engine must support many-to-many relationships.

---

## 35.15 No forced mapping

If the engine cannot reliably map a clause:

```text
NO_CONFIDENT_MAPPING
```

It should not force it into a Requirement just to produce a result.

This is important for legal accuracy.

---

## 35.16 Mapping evidence

Every mapping should retain its reason.

Example:

```text
Requirement:
LIABILITY-001

Mapped Clause:
8.2

Why:
- Section heading matched
- Alias matched
- Required keyword group matched
- No exclusion pattern detected
```

This becomes part of the Step 32 explainability chain.

---

## 35.17 Step 35 recommended locked rules

**Status: LOCKED** (confirmed by the Step 35 final review below). Exception: rule 10 defers numerical thresholds, which remain PROVISIONAL per 35.8 / 35.9.

I recommend locking these principles:

1. Clause-to-Requirement mapping is deterministic in V1.
2. V1 does not use LLM, RAG, vector database, or semantic AI for mapping.
3. Requirements contain structured mapping metadata.
4. Requirements may define aliases and controlled terminology.
5. Mapping supports positive and negative patterns.
6. Mapping operates at clause/section level rather than treating the entire document as one text block.
7. Section headings can contribute to deterministic mapping.
8. Mapping distinguishes candidate matches from confirmed mappings.
9. Mapping can use deterministic ranking/scoring where useful.
10. Numerical thresholds should be validated against a representative contract test set before being locked.
11. Different Requirements may use different mapping rules.
12. One Requirement may map to multiple clauses.
13. One clause may map to multiple Requirements.
14. Mapping does not itself determine the final Finding.
15. Mapping and Evaluation remain separate engines.
16. Cross-references should be preserved for downstream evaluation.
17. The engine must allow a clause to remain unmapped when evidence is insufficient.
18. Every confirmed mapping records its deterministic explanation/evidence.
19. No opaque AI confidence score is used as the basis for a V1 Legal conclusion.
20. Mapping rules are versioned as part of Legal Configuration.

---

## The architecture we are heading toward

These two steps establish an important separation:

```text
                 DOCUMENT
                    ↓
          ┌───────────────────┐
          │ Ingestion/Parsing │
          └─────────┬─────────┘
                    ↓
             Normalized Text
                    ↓
          ┌───────────────────┐
          │ Mapping Engine    │
          └─────────┬─────────┘
                    ↓
           Requirement Mapping
                    ↓
          ┌───────────────────┐
          │ Evaluation Engine │  ← Step 36
          └─────────┬─────────┘
                    ↓
                 Finding
                    ↓
             Legal Decision
```

**Step 34 = how we reliably understand the document structure.**

**Step 35 = how we deterministically connect contract clauses to LegalMind Requirements.**

**Step 36 = how we actually evaluate those mapped clauses and produce MATCH / DEVIATION / MISSING / CONFLICT, etc.**

I recommend **not locking either 34 or 35 yet** until you review them, especially the deterministic mapping/scoring approach.

*(Note: this recommendation predates the review below; the Step 35 final review supersedes it and records STEP 35 — LOCKED.)*

---

## Step 35 final review

I also rechecked the mapping engine for the biggest V1 risks:

### 1. Keyword matching cannot be enough

Correct. We already require:

```text
Positive patterns
+
Negative patterns
+
Section context
+
Clause context
```

### 2. Mapping ≠ legal evaluation

This is critical and remains locked:

```text
Mapping:
"What Requirement does this clause relate to?"

Evaluation:
"What does this clause mean under our configured rule?"
```

### 3. One-to-many and many-to-one

Both are supported:

```text
One Requirement
    ↓
Multiple clauses
```

and:

```text
One clause
    ↓
Multiple Requirements
```

### 4. No forced mapping

If evidence isn't strong enough:

```text
NO_CONFIDENT_MAPPING
```

rather than inventing a match.

### 5. Scoring

We should **not hard-code arbitrary thresholds now**.

We first need a representative contract test set, then benchmark the deterministic rules and tune thresholds.

That is the correct engineering approach.

### 6. Versioning

Mapping rules themselves must be versioned.

So a historical Review can say:

```text
Requirement Mapping Rules: v4
```

and we don't accidentally reinterpret an old Review using today's rules.

### Decision

🔒 **STEP 35 — LOCKED**
