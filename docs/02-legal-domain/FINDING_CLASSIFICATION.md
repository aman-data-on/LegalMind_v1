# Finding Classification

Source: all_lock.md Steps 18, 22, 27, 30, 36. Canonical source: all_lock.md (Steps 18, 22, 27, 30, 36).

Related: [DECISION_STATE_MODEL.md](DECISION_STATE_MODEL.md) (**cross-layer canonical reference — read this first**) · [LEGAL_RULES.md](./LEGAL_RULES.md) · [LEGAL_DECISIONS.md](./LEGAL_DECISIONS.md) (Decision vocabulary is defined there, not repeated here) · [../04-analysis-engine/REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) · [../01-product/WORKFLOWS.md](../01-product/WORKFLOWS.md) (Review Lifecycle)

---

## ✅ CANONICAL — Finding Classification (axis 2)

**Status: LOCKED.** Canonicalized by owner-approved reconciliation `REC-01`, 2026-08-16.

The Finding Classification vocabulary for LegalMind V1 is the **Step 36 set**, carried forward unchanged by Steps 44, 45A and 45B:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

| Value | Meaning (Step 36) |
|-------|-------------------|
| `MATCH` | Customer provision conforms to the Company Standard. |
| `DEVIATION` | Customer provision differs from the Company Standard. **Does not automatically mean unacceptable** — the Legal Rule determines what happens next. |
| `MISSING` | The Requirement is expected, but no qualifying provision is found. |
| `CONFLICT` | Multiple provisions within the same contract produce incompatible positions. Both pieces of evidence remain attached. |
| `AMBIGUOUS` | Potentially relevant provisions were found, but the intended legal position cannot be deterministically established. Legal review is required. |
| `UNRESOLVED` | An issue is identified but evaluation cannot complete because required information or a required action is missing. Distinct from `AMBIGUOUS`. |
| `UNABLE_TO_EVALUATE` | Evaluation cannot be performed reliably because the underlying evidence is unavailable or unreliable. Prevents LegalMind from pretending that "not found" means "missing." |

Full verbatim definitions and worked examples: [../04-analysis-engine/ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) (§36.2–36.8).

Step 45A §17 ratifies this directly:

> The exact Finding classifications have some historical evolution in the document, including an earlier five-type model and the later expanded evaluation model. Since Step 44 and the later evaluator sections explicitly use the expanded classifications, **Step 45 should follow the later locked architecture rather than reintroducing the older five-type-only model.**

### Supersession chain

Steps 18 → 27 → 36 are a **supersession chain, not a contradiction**. The historical locked text of Steps 18 and 27 is preserved verbatim below and has **not** been modified; it is annotated as superseded.

| Term | Disposition |
|------|-------------|
| `MATCH` · `DEVIATION` · `MISSING` | Stable across all three steps; definitions consistent. |
| `CONFLICT` · `UNABLE_TO_EVALUATE` | Added by Step 27. Additive refinement. |
| `AMBIGUOUS` · `UNRESOLVED` | Added by Step 36. Additive refinement. |
| `ADDITIONAL` (Step 18) → `EXTRA` (Step 27) | Pure rename — the two definitions are near-verbatim. **Both are now superseded by `UNMATCHED_PROVISION`** (see below). |
| `UNMAPPED` (Step 18) | **Layer migration, not deletion.** Step 18 defines it as a provision "detected but could not be reliably mapped to the Clause Library" — that is a *mapping state*, formalized by Step 28 as `UNRESOLVED` on axis 1. See [DECISION_STATE_MODEL.md](DECISION_STATE_MODEL.md). |

---

## ✅ `UNMATCHED_PROVISION` — document-level observation, NOT a classification

**Status: LOCKED.** Owner decision `REC-02`, 2026-08-16, superseding `ADDITIONAL` (Step 18) and `EXTRA` (Step 27).

A provision that exists in the counterparty document with no corresponding configured Requirement is recorded as an **`UNMATCHED_PROVISION` document-level observation**.

**It is not a Finding Classification and must never be written into a Finding's `classification` field.**

Rationale: axis 2 is the outcome set of *evaluating a mapped Requirement*. An unmatched provision has no Requirement to evaluate, so it cannot carry an evaluation outcome. This is why Step 36 — the first step to define the evaluation pipeline's outcome set — contains no `EXTRA`.

The locked rules that governed `ADDITIONAL`/`EXTRA` carry over unchanged:

* An unmatched provision is **not** automatically negative or unacceptable (Step 18 rule 8, Step 27 rule 7).
* It retains traceable evidence (Step 18 rule 10, Step 27 rule 3).
* It does not itself determine legal acceptability (Step 18 rule 6).

**Status: NOT YET SPECIFIED** — the persistence model, surfacing, and review treatment of `UNMATCHED_PROVISION` observations. This decision establishes *what it is and is not*; it does not specify where it is stored or how it appears in a Review. Do not invent those.

---

## RESOLVED ≠ MATCH — Critical Locked Rule

**Status: LOCKED** (Step 22 Clarification)

> This is one of the most important separations in the entire spec: a Review reaching `RESOLVED` status is **not** the same thing as the underlying provision achieving a `MATCH` finding.

```text
Company Standard:
Liability cap = 6 months

Customer Contract:
Liability cap = 18 months

Comparison:
DEVIATION

Legal Decision:
Approved Customization for this specific contract

Review Status:
RESOLVED

Company Standard:
Still 6 months
```

`MATCH` means the customer provision aligns with the Company Standard.

`RESOLVED` means the deviation or workflow issue has received an authorized resolution. It does not mean the customer provision now matches the Company Standard.

Additional confirmation from Step 22:

```text
Finding:
DEVIATION

Legal Decision:
Approved Customization

Review:
RESOLVED
```

The contract still differs from the Company Standard; the deviation has simply received an authorized resolution.

## Step 18 — Finding Types (V1 initial set)

> **Status: LOCKED — SUPERSEDED for the classification vocabulary.**
> Historical locked text, preserved verbatim and unmodified. The five-type vocabulary below is superseded by the canonical Step 36 set above (`REC-01`): `ADDITIONAL` → `UNMATCHED_PROVISION` (`REC-02`), `UNMAPPED` → mapping-state `UNRESOLVED` on axis 1. **The locked *rules* in this step (6–11) remain in force** — they constrain how any classification behaves.

LegalMind V1 will use exactly these five core finding types:

* `MATCH`
* `DEVIATION`
* `MISSING`
* `ADDITIONAL`
* `UNMAPPED`

### Locked Rules

1. `MATCH` means the provision satisfies the configured comparison criteria.
2. `DEVIATION` means the provision exists but differs from the Company Standard.
3. `MISSING` means an expected configured provision was not found.
4. `ADDITIONAL` means an extra provision exists without a corresponding configured standard requirement.
5. `UNMAPPED` means a provision was detected but could not be reliably mapped to the Clause Library.
6. A finding type does not itself determine legal acceptability.
7. `DEVIATION` does not automatically mean unacceptable.
8. `ADDITIONAL` does not automatically mean unacceptable.
9. `UNMAPPED` must not be silently classified as a match.
10. Every finding must retain evidence showing where the relevant customer provision came from.
11. Legal decisions remain a separate authorized workflow (see [LEGAL_DECISIONS.md](./LEGAL_DECISIONS.md)).

### Example

```text
Customer Contract
       ↓
Clause Identification
       ↓
Clause Library
       ↓
Structured Extraction
       ↓
Requirement Evaluation
       ↓
Company Standard Comparison
       ↓
Finding Type
       │
       ├── MATCH
       ├── DEVIATION
       ├── MISSING
       ├── ADDITIONAL
       └── UNMAPPED
       ↓
Evidence
       ↓
User View / Escalation
       ↓
Authorized Legal Decision
```

### Example findings

```text
Confidentiality
→ MATCH

Limitation of Liability
→ DEVIATION

Data Protection
→ MISSING

Audit Rights
→ ADDITIONAL

Unrecognized legal provision
→ UNMAPPED
```

These finding types describe comparison results only. They do not expose or encode confidential internal Legal Position thresholds.

## Step 27 — Comparison & Finding Generation (Locked, Revised Finding Type Set)

> **Status: LOCKED — SUPERSEDED for the classification vocabulary.**
> Historical locked text, preserved verbatim and unmodified. The six-type vocabulary below is superseded by the canonical Step 36 set above (`REC-01`): `EXTRA` → `UNMATCHED_PROVISION` (`REC-02`); `AMBIGUOUS` and `UNRESOLVED` were added later by Step 36. **The locked *rules* in this step (1–18) remain in force in full** — they are the deterministic-comparison and separation-of-concerns rules, and nothing in this reconciliation touches them.

LegalMind V1 comparison is deterministic and explainable. V1 will not use an LLM, RAG, vector database, or semantic AI as the Legal decision-maker.

This does not mean simplistic string matching. During the later technical-design phase, LegalMind will select the best appropriate deterministic/NLP algorithms for document parsing, clause segmentation, candidate retrieval, extraction, normalization, matching, and rule evaluation.

### Locked Finding Types

```text
MATCH
DEVIATION
MISSING
CONFLICT
EXTRA
UNABLE_TO_EVALUATE
```

Note: Step 27 extends the Step 18 set — `CONFLICT` and `UNABLE_TO_EVALUATE` are added, `ADDITIONAL` is renamed `EXTRA`, and `UNMAPPED` moves to the mapping layer. Step 27 is in turn superseded for the classification vocabulary by Step 36 (`REC-01`). See the canonical section at the top of this document and [DECISION_STATE_MODEL.md](DECISION_STATE_MODEL.md).

### Locked Rules

1. Comparison operates through structured Requirements and mapped clauses.
2. Every Finding belongs to a specific Review.
3. Every Finding retains traceable evidence.
4. `DEVIATION` means the customer provision differs from the Company Standard; it does not automatically mean Legal approval is required.
5. `CONFLICT` means the customer provision directly contradicts a configured required position.
6. `MISSING` means a required/mapped provision could not be found.
7. `EXTRA` means an additional provision exists without a corresponding mapped Company Standard requirement; it is not automatically negative.
8. `UNABLE_TO_EVALUATE` is used when deterministic evaluation cannot establish a reliable result.
9. Finding classification is separate from Legal Rule evaluation.
10. Legal Rule evaluation is separate from the Legal Decision.
11. Legal Decisions are made only by authorized Legal users.
12. Risk/severity is configuration-driven and is not hard-coded solely from Finding type.
13. LegalMind must not invent unsupported contractual values or legal conclusions.
14. The same Contract Version + applicable Company Configuration versions + Legal Rule versions must produce the same deterministic result.
15. Historical Findings retain the exact evidence and configuration versions used to generate them.
16. Multiple independent findings may exist within one Review.
17. The technical implementation must be selected later based on the locked functional requirements; APIs, libraries, algorithms, OCR, database architecture, and application stack are not locked by this step.
18. Candidate retrieval may use appropriate deterministic/NLP techniques, but the final V1 Legal classification and Rule evaluation must remain reproducible and explainable.

### Conceptual Pipeline

```text
Customer Contract
      ↓
Document Parsing
      ↓
Clause Identification
      ↓
Structured Representation
      ↓
Requirement Mapping
      ↓
Company Standard + Legal Rule Evaluation
      ↓
Finding
      ↓
Legal Decision when required
```

### Important Separation

```text
Customer Contract
       ↓
Finding
       ↓
Legal Rule Evaluation
       ↓
Legal Decision
```

A Finding is not itself a Legal Decision.

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

## Step 30 — Review Lifecycle and Finding Status Are Separate Concepts

**Status: LOCKED**

LegalMind V1 separates Review lifecycle, Finding status, Legal Decision, and comparison outcome. A single status field must not be used to represent all of these concepts.

The full Review Lifecycle state machine (`DRAFT → UPLOADED → PROCESSING → ANALYSIS_COMPLETE → LEGAL_REVIEW → RESOLVED → CLOSED`, plus exception states `ANALYSIS_FAILED` and `CANCELLED`) is documented in [../01-product/USER_ROLES.md](../01-product/USER_ROLES.md#review-lifecycle--status-management-step-30) to keep review/workflow status alongside the roles that act on it.

### Conceptual Separation (relevant to Finding classification)

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

Key rule reiterated here because it governs Finding interpretation: `ANALYSIS_FAILED` (a Review-level exception state — automated analysis could not complete) is distinct from a Finding of `UNABLE_TO_EVALUATE` (a Finding-level classification where deterministic evaluation could not establish a reliable result).
