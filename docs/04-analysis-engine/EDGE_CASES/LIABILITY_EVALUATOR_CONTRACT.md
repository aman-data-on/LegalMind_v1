Source: all_lock.md lines 12482-13510 (Step 45B). Canonical source: all_lock.md (Step 45B).

Status: **🔒 LOCKED (revised 2026-08-17)** — comprising 45B.1–45B.28 as written, plus `REC-05` (R1), `REC-07`, and Amendment Batch **AB-1**. Re-lock record in [`all_lock.md`](../../../all_lock.md) under "Step 45B — RE-LOCK RECORD".

# Step 45B — Evaluator Data Contract

Cross-reference: see [LIABILITY.md](LIABILITY.md) for Step 45A — the `LIABILITY-001` policy/requirement definition this contract implements. See [../ANALYSIS_ENGINE.md](../ANALYSIS_ENGINE.md) for the Step 44 layered engine architecture, [../FACT_EXTRACTION.md](../FACT_EXTRACTION.md) for Layer 5/6 fact extraction, [../CONFLICT_DETECTION.md](../CONFLICT_DETECTION.md) for `CONFLICT` / `AMBIGUOUS` / `MISSING` / `UNABLE_TO_EVALUATE` definitions, [../RULE_ENGINE.md](../RULE_ENGINE.md) for evaluator architecture, and [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md) for the five-axis state model this contract must conform to.

---

# ⚠ REVISION R1 — corrections pending final review

**Status: 🔒 LOCKED — incorporated into the 45B re-lock and recorded in `all_lock.md`.**

Applied 2026-08-16 under owner-approved reconciliation item 5 (`REC-05`). The verbatim Step 45B transcription follows below and is **unmodified**; these corrections are recorded as a revision layer over it. They must be folded into `all_lock.md` when 45B is locked.

### R1.1 — `rule_configuration` restored to the complete input *(defect fix)*

45B.9 lists `rule_configuration` on the `LegalRule` tree, but 45B.11's complete evaluator input omits it. This is an internal inconsistency in 45B, not a decision. **Correction: `rule_configuration` is part of the contract and appears in the complete input.**

### R1.2 — extraction diagnostics restored on the evaluator input *(gap fix)*

Step 45A carried `extraction_diagnostics` on the fact model. 45B replaced it with the controlled enum `extraction_status` and placed free-form `diagnostics` only on the evaluator **output** (45B.17). The evaluator can therefore see *that* extraction was `PARTIAL` but not *why*, which weakens the Step 44 explainability contract at the input boundary.

**Correction: facts carry both** — `extraction_status` (controlled, drives control flow) **and** `extraction_diagnostics` (free-form, explains the status). This preserves 45A's field without weakening 45B's enum.

**Persistence — `REC-07`, LOCKED:** `extraction_diagnostics` is **persisted** as part of the evaluation/evidence record, for auditability and reproducibility. It is **diagnostic metadata only** and **cannot independently produce or alter a legal finding**. This is consistent with the existing locked constraint in 45B.17 — diagnostics are for system/debugging purposes and must never become legal conclusions — and resolves the persistence question left open by 45B.27.

### R1.3 — `cap_status` and `NOT_APPLICABLE` ratified *(refinements confirmed)*

Both 45B departures from 45A are **ratified as improvements**, not regressions:

| 45A | 45B | Why 45B is correct |
|-----|-----|--------------------|
| `cap_exists` (boolean) + `cap_type` | `cap_status` only | Two fields encoding one fact is two sources of truth, and a boolean cannot represent `UNKNOWN` without ambiguity. The enum `FINITE`/`UNLIMITED`/`ABSENT`/`UNKNOWN` is unchanged from 45A §4. |
| `extraction_diagnostics` | `extraction_status` | A controlled enum is required for deterministic control flow. Retained **in addition** per R1.2, not instead. |
| Rule outcome `—` (45A §17 matrix) | `NOT_APPLICABLE` | Required by 45B.26 "no arbitrary NULL semantics". |

### R1.4 — axis conformance

45B.13's classification set is identical to the canonical axis-2 vocabulary — no change required. Two conformance requirements apply:

* `extraction_status` is **not** an axis. It is a fact-quality signal on the input that feeds axis 2; a `FAILED` extraction must produce `UNABLE_TO_EVALUATE` rather than a guess.
* `ExtractionStatus.AMBIGUOUS`, `MappingState.AMBIGUOUS` and `Classification.AMBIGUOUS` are **three different values** and must not share an enum. See the collision table in [DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md).

### Revised `facts` block (R1.2)

```text
facts: {
    cap_status,
    cap_value,
    cap_unit,
    cap_basis,
    scope,
    exceptions[],
    evidence_refs[],
    extraction_status,
    extraction_diagnostics
}
```

### Revised complete evaluator input (R1.1 + R1.2)

Changes from 45B.11 are marked `←`; everything else is unchanged.

```text
LIABILITY_EVALUATOR_INPUT

{
    requirement: {
        id,
        code,
        version_id
    },

    evidence: [
        {
            evidence_id,
            document_version_id,
            page_number,
            section_number,
            section_title
        }
    ],

    facts: {
        cap_status,
        cap_value,
        cap_unit,
        cap_basis,
        scope,
        exceptions[],
        evidence_refs[],
        extraction_status,
        extraction_diagnostics        ← R1.2
    },

    company_standard: {
        version_id,
        preferred_value,
        preferred_unit
    },

    legal_rule: {
        version_id,
        acceptable_max,
        acceptable_max_unit,
        approval_required_above,
        unlimited_outcome,
        rule_configuration            ← R1.1
    },

    evaluator_version
}
```

The evaluator **output** (45B.12) is unchanged by this revision.

### Still open

* **`rule_configuration` has no defined shape.** 45B.9 names it but never specifies its contents. Status: **NOT YET SPECIFIED** — do not invent it.

*(Resolved: `extraction_diagnostics` persistence — see `REC-07` above.)*

---

Yes. We are now doing **Step 45B — Evaluator Data Contract / Schema**.

I checked the master specification again. It already establishes the important foundation: evaluations are separate from Findings, numeric evaluations preserve expected/actual/operator/rule information, and every evaluation must preserve the exact versioned context used.

The purpose of 45B is to define the **exact contract between Fact Extraction and the Evaluator**, and between the Evaluator and Finding Generation.

The architecture is:

```text
Evidence
   ↓
Requirement-specific Fact Extraction
   ↓
Evaluator Input
   ↓
Deterministic Evaluator
   ↓
Evaluation Result
   ↓
Finding Generator
   ↓
Finding
```

The evaluator must **not go back and independently search the whole document**.

---

## 45B.1 Evaluator Input

For `LIABILITY-001`, the evaluator receives five groups of information:

```text
EvaluatorInput
│
├── Requirement Context
├── Evidence
├── Extracted Facts
├── Company Standard
├── Legal Rule
└── Evaluator Version
```

Conceptually:

```text
EvaluatorInput {
    requirement_version
    evidence[]
    facts
    company_standard
    legal_rule
    evaluator_version
}
```

This is consistent with the master specification's requirement that a Review preserve the Requirement, Standard, Rule, Evaluation Rules and Evidence context.

---

## 45B.2 Requirement Context

The evaluator must know exactly **which Requirement it is evaluating**.

```text
RequirementContext
├── requirement_id
├── requirement_code
├── requirement_version_id
└── document_type
```

For example:

```text
requirement_id:
...

requirement_code:
LIABILITY-001

requirement_version_id:
...

document_type:
MSA
```

The evaluator must never rely only on:

```text
"liability"
```

as its identity.

It must use the versioned Requirement.

---

## 45B.3 Evidence Reference

Every extracted fact must remain traceable to source evidence.

The evidence object should conceptually contain:

```text
EvidenceReference
├── evidence_id
├── document_version_id
├── page_number
├── section_number
├── section_title
├── source_type
└── content_reference
```

The existing schema already establishes `document_evidence` with document version, processing run, page, section, content, source type and offsets.

The evaluator should receive **references**, not duplicated uncontrolled copies of the document.

---

## 45B.4 Liability Facts

> **Revised by R1.2** — the fact model also carries `extraction_diagnostics`. `cap_status` (replacing 45A's `cap_exists` + `cap_type`) is ratified by R1.3. See [REVISION R1](#-revision-r1--corrections-pending-final-review).

For `LIABILITY-001`, the minimum structured fact model should be:

```text
LiabilityFacts
├── cap_status
├── cap_value
├── cap_unit
├── cap_basis
├── scope
├── exceptions[]
├── evidence_refs[]
└── extraction_status
```

### `cap_status`

Controlled values:

```text
FINITE
UNLIMITED
ABSENT
UNKNOWN
```

### `cap_value`

Example:

```text
6
12
24
```

Nullable when the cap is:

```text
UNLIMITED
ABSENT
UNKNOWN
```

### `cap_unit`

Example:

```text
MONTHS
DAYS
CURRENCY
PERCENTAGE
OTHER
```

### `cap_basis`

Example:

```text
FEES_PAID
FEES_PAYABLE
CONTRACT_VALUE
FIXED_AMOUNT
OTHER
UNKNOWN
```

We should **not assume equivalence between different bases**.

---

## 45B.5 Scope

Scope must remain explicit.

Example:

```text
scope:
AGGREGATE
```

Other possible controlled values can include:

```text
PER_CLAIM
PER_EVENT
PARTY_SPECIFIC
CATEGORY_SPECIFIC
OTHER
UNKNOWN
```

The important principle is that the evaluator must not turn:

```text
aggregate liability cap = 6 months
```

into:

```text
all liability = 6 months
```

without evidence.

The master specification specifically requires scope and carve-outs to be preserved.

---

## 45B.6 Exceptions / Carve-outs

Represent them separately:

```text
exceptions: [
    {
        concept: "fraud",
        evidence_ref: "..."
    },
    {
        concept: "wilful misconduct",
        evidence_ref: "..."
    },
    {
        concept: "confidentiality breach",
        evidence_ref: "..."
    }
]
```

This is important because:

```text
General Cap
+
Exceptions
```

is materially different from simply:

```text
Cap = 6 months
```

The specification explicitly gives this liability example.

---

## 45B.7 Extraction Status

> **Revised by R1.2** — facts also carry `extraction_diagnostics` alongside this enum. See [REVISION R1](#-revision-r1--corrections-pending-final-review).

The evaluator needs to know whether the facts are actually usable.

Controlled states:

```text
COMPLETE
PARTIAL
AMBIGUOUS
FAILED
```

Example:

```text
cap_status = UNKNOWN
extraction_status = FAILED
```

The evaluator must then be capable of returning:

```text
UNABLE_TO_EVALUATE
```

rather than guessing.

---

## 45B.8 Company Standard Input

For `LIABILITY-001`:

```text
CompanyStandard
├── version_id
├── preferred_value
└── preferred_unit
```

Current authoritative configuration:

```text
preferred_value:
6

preferred_unit:
MONTHS
```

The master specification establishes 6 months as the preferred Company Standard.

---

## 45B.9 Legal Rule Input

The Legal Rule must be separate from the Company Standard.

Conceptually:

```text
LegalRule
├── version_id
├── acceptable_max
├── acceptable_max_unit
├── approval_required_above
├── unlimited_outcome
└── rule_configuration
```

Current authoritative example:

```text
acceptable_max:
12 months

approval_required_above:
12 months

unlimited:
UNACCEPTABLE
```

This separation is critical:

```text
Company Standard:
6 months

Legal Rule:
≤12 months acceptable
>12 months approval required
Unlimited unacceptable
```

The master specification explicitly distinguishes these concepts.

---

## 45B.10 Evaluator Version

Every evaluation must identify the exact evaluator implementation/version.

```text
evaluator_version:
LIABILITY-EVALUATOR-v1
```

This is different from:

```text
Requirement Version
Company Standard Version
Legal Rule Version
```

All four matter.

```text
Requirement v3
+
Company Standard v5
+
Legal Rule v4
+
Evaluator v1
```

This gives us reproducibility.

The specification requires the evaluator version and exact configuration context to be retained for historical reproducibility.

---

## 45B.11 Complete Evaluator Input

> **Revised by R1.1 + R1.2** — the block below is the verbatim source text and omits `rule_configuration` and `extraction_diagnostics`. See [REVISION R1](#-revision-r1--corrections-pending-final-review) for the corrected contract.

So the conceptual contract becomes:

```text
LIABILITY_EVALUATOR_INPUT

{
    requirement: {
        id,
        code,
        version_id
    },

    evidence: [
        {
            evidence_id,
            document_version_id,
            page_number,
            section_number,
            section_title
        }
    ],

    facts: {
        cap_status,
        cap_value,
        cap_unit,
        cap_basis,
        scope,
        exceptions[],
        evidence_refs[],
        extraction_status
    },

    company_standard: {
        version_id,
        preferred_value,
        preferred_unit
    },

    legal_rule: {
        version_id,
        acceptable_max,
        acceptable_max_unit,
        approval_required_above,
        unlimited_outcome
    },

    evaluator_version
}
```

This is the **logical contract**. We do not need to commit to this exact JSON representation in the database yet.

---

## 45B.12 Evaluator Output

The evaluator returns:

```text
EvaluationResult
├── classification
├── rule_outcome
├── expected_value
├── actual_value
├── comparison
├── evaluated_facts
├── evidence_refs[]
├── explanation
├── diagnostics
└── evaluator_version
```

---

## 45B.13 Classification

> Conforms to canonical axis 2 — no change required (R1.4). See [DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md).

Controlled V1 classifications:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

The master specification supports this expanded classification model.

---

## 45B.14 Rule Outcome

This is **not the same thing as Finding classification**.

For example:

```text
classification:
DEVIATION

rule_outcome:
ACCEPTABLE
```

or:

```text
classification:
DEVIATION

rule_outcome:
APPROVAL_REQUIRED
```

or:

```text
classification:
DEVIATION

rule_outcome:
UNACCEPTABLE
```

This preserves:

```text
Finding
   ≠
Rule Outcome
   ≠
Legal Decision
```

The specification explicitly says the Evaluation Engine does not produce the Legal Decision.

---

## 45B.15 Comparison Object

For numeric evaluation, preserve the actual calculation.

Example:

```text
comparison: {
    expected_value: 6,
    expected_unit: "MONTHS",

    actual_value: 12,
    actual_unit: "MONTHS",

    operator: "GREATER_THAN",

    acceptable_max: 12,
    acceptable_max_unit: "MONTHS",

    result: "DEVIATION_WITHIN_ACCEPTABLE_RANGE"
}
```

This is much better than storing only:

```text
DEVIATION
```

The specification explicitly requires preservation of expected value, actual value, operator, threshold and evaluation.

---

## 45B.16 Explanation

The evaluator should produce a **deterministic explanation**, not AI-generated prose.

Example:

```text
Customer liability cap:
12 months

Company Standard:
6 months

Comparison:
12 months > 6 months

Configured acceptable maximum:
12 months

Rule:
12 months is within acceptable maximum

Evaluation:
DEVIATION / ACCEPTABLE
```

This explanation can then be presented in the UI.

---

## 45B.17 Diagnostics

Diagnostics are for system/debugging purposes and should not become legal conclusions.

Examples:

```text
diagnostics:
[
    "Cap value successfully extracted",
    "Unit normalized to MONTHS",
    "Scope identified as AGGREGATE",
    "No conflicting cap detected"
]
```

Or:

```text
[
    "Two candidate liability provisions detected",
    "Governing provision could not be determined"
]
```

This helps explain why an evaluation became:

```text
AMBIGUOUS
```

or:

```text
UNABLE_TO_EVALUATE
```

---

## 45B.18 Evidence must survive the evaluator

This is a hard requirement.

For:

```text
Finding F-001
```

we must be able to trace:

```text
F-001
 ↓
Evaluation E-001
 ↓
Evidence EVD-182
 ↓
Document Version DV-4
 ↓
Page 12
 ↓
Section 8.2
 ↓
Original source text
```

The master schema explicitly separates `evaluations` from `findings` and provides `finding_evidence` for this purpose.

---

## 45B.19 Example — MATCH

Input:

```text
Actual:
6 months

Expected:
6 months
```

Output:

```text
classification:
MATCH

rule_outcome:
NOT_APPLICABLE

comparison:
6 == 6
```

---

## 45B.20 Example — ACCEPTABLE DEVIATION

Input:

```text
Actual:
12 months

Expected:
6 months

Acceptable max:
12 months
```

Output:

```text
classification:
DEVIATION

rule_outcome:
ACCEPTABLE

comparison:
12 > 6
AND
12 <= 12
```

---

## 45B.21 Example — Approval Required

```text
Actual:
24 months

Expected:
6 months

Acceptable max:
12 months
```

Output:

```text
classification:
DEVIATION

rule_outcome:
APPROVAL_REQUIRED

comparison:
24 > 6
AND
24 > 12
```

The evaluator stops here.

It does **not** generate:

```text
APPROVE
REJECT
ACCEPT
```

Those belong to the Legal Decision workflow.

---

## 45B.22 Example — Unlimited

```text
cap_status:
UNLIMITED
```

Output:

```text
classification:
DEVIATION

rule_outcome:
UNACCEPTABLE
```

assuming the applicable Legal Rule says Unlimited is unacceptable.

---

## 45B.23 Example — Missing

If the Requirement is required and deterministic evidence establishes that there is no qualifying liability provision:

```text
classification:
MISSING

rule_outcome:
NOT_APPLICABLE
```

We should not put:

```text
actual_value = 0
```

because absence of a clause is not numerically equivalent to zero.

---

## 45B.24 Example — Unable to Evaluate

Suppose:

```text
Evidence exists
    ↓
OCR damaged
    ↓
Cannot reliably determine whether "6" or "8" was extracted
```

Output:

```text
classification:
UNABLE_TO_EVALUATE

rule_outcome:
NOT_APPLICABLE
```

with diagnostics explaining the extraction problem.

---

## 45B.25 Example — Conflict

```text
Evidence A:
6 months

Evidence B:
Unlimited
```

Output:

```text
classification:
CONFLICT

rule_outcome:
NOT_APPLICABLE
```

Both evidence references remain attached.

The evaluator does not silently choose:

```text
6
```

or:

```text
Unlimited
```

---

## 45B.26 Important rule: no arbitrary NULL semantics

We need to explicitly lock this.

These are **not equivalent**:

```text
NULL
0
ABSENT
UNKNOWN
UNLIMITED
```

For example:

```text
cap_value = NULL
cap_status = UNLIMITED
```

means something very different from:

```text
cap_value = NULL
cap_status = UNKNOWN
```

This prevents database-level ambiguity from becoming legal-analysis ambiguity.

---

## 45B.27 Persistence model

The logical evaluator result can be persisted through the existing `evaluations` model:

```text
evaluations
-----------
id
finding_id
evaluator_type
expected_value
actual_value
operator
result
rule_version_id
created_at
```

The master specification already proposes this separation.

However, for `LIABILITY-001`, I recommend that the implementation **not squeeze every structured fact into `expected_value` / `actual_value` strings**.

The complete structured evaluator payload should be retained in a controlled structured field or related tables, while important queryable relationships remain relational.

That is consistent with the broader database rule that structured domain data should not be hidden entirely inside arbitrary JSON.

---

## 45B.28 Final 45B contract

The authoritative flow is now:

```text
                 DOCUMENT EVIDENCE
                        ↓
              LIABILITY FACTS
                        ↓
              ┌─────────────────┐
              │ EVALUATOR INPUT │
              └────────┬────────┘
                       │
       ┌───────────────┼────────────────┐
       ↓               ↓                ↓
 Requirement      Company Standard   Legal Rule
 Version              Version          Version
       │               │                │
       └───────────────┼────────────────┘
                       ↓
               Evaluator Version
                       ↓
             DETERMINISTIC EVALUATOR
                       ↓
              EVALUATION RESULT
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
   Classification  Rule Outcome  Comparison
          │            │            │
          └────────────┼────────────┘
                       ↓
                Evidence + Explanation
                       ↓
                    FINDING
                       ↓
                LEGAL WORKFLOW
```

## 🔒 45B proposed lock

I recommend locking these **before moving to 45C**:

1. Evaluators receive structured, versioned inputs.
2. Evaluators do not independently search or reinterpret the whole document.
3. Requirement Version is explicit input.
4. Evidence references are explicit input.
5. Requirement-specific facts are explicit input.
6. Company Standard Version is explicit input.
7. Legal Rule Version is explicit input.
8. Evaluator Version is explicit input.
9. Liability facts preserve cap status, value, unit, basis, scope, exceptions and evidence references.
10. `NULL`, `ABSENT`, `UNKNOWN`, `UNLIMITED`, and numeric zero are distinct concepts.
11. Evaluator output contains both Finding classification and Rule Outcome.
12. Numeric comparisons preserve expected value, actual value, units, operator, threshold and result.
13. Evaluations are persisted separately from Findings.
14. Evidence references remain attached to the evaluation/finding chain.
15. Deterministic explanations are retained.
16. Diagnostics may explain processing/evaluation limitations but do not constitute legal conclusions.
17. `MISSING`, `CONFLICT`, `AMBIGUOUS`, and `UNABLE_TO_EVALUATE` do not manufacture numeric values.
18. Evaluators never produce Legal Decisions.
19. The complete version context is retained for reproducibility.
20. The evaluator contract is implementation-independent: the logical contract is authoritative; the physical PostgreSQL representation can be finalized during schema implementation.

### Current position

```text
Steps 1–44       🔒 LOCKED
Step 45A         🔒 LOCKED
Step 45B         ⏳ REVIEW
```

**I recommend locking 45B after one final check, then moving to 45C — Liability Edge Cases.** That is where we test whether this contract survives the difficult real-world cases: multiple caps, carve-outs, per-claim vs aggregate caps, different monetary bases, cross-references, conflicting schedules, and malformed/ambiguous clauses.
