# Decision State Model — The Five Axes

**Status: LOCKED** (canonical cross-layer reference)

**This is the canonical reference for every controlled state vocabulary in LegalMind.** Any document, schema, or API that names a state must conform to the axis definitions here.

Canonical basis: `all_lock.md` Steps 28, 30, 31, 36, 44, 45A/45B.
Reconciliation authority: owner-approved cross-step reconciliation, 2026-08-16 (registry entries `REC-01`–`REC-05` in [../00-project/LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md)).

---

## The governing principle

This model is not new policy. It makes explicit a separation the specification already locked in **Step 30**:

> LegalMind V1 separates Review lifecycle, Finding status, Legal Decision, and comparison outcome. A single status field must not be used to represent all of these concepts.

Five distinct axes exist. **A single status field must never represent more than one of them.**

---

## The five axes

| # | Axis | Answers | Controlled values | Source |
|---|------|---------|-------------------|--------|
| **1** | **Mapping State** | Which Requirement does this clause relate to? | `CONFIRMED` · `AMBIGUOUS` · `UNRESOLVED` | Step 28 |
| **2** | **Finding Classification**<br>*(= Evaluation Outcome)* | What is the comparison result for this Requirement? | `MATCH` · `DEVIATION` · `MISSING` · `CONFLICT` · `AMBIGUOUS` · `UNRESOLVED` · `UNABLE_TO_EVALUATE` | Steps 36, 44, 45A/B |
| **3** | **Rule Outcome** | How does the organization tolerate this result? | `ACCEPTABLE` · `APPROVAL_REQUIRED` · `UNACCEPTABLE` · `NOT_APPLICABLE` | Steps 27, 31, 45B.14 |
| **4** | **Legal Decision** | What did an authorized human rule? | `ACCEPT_DEVIATION` · `REQUIRE_COMPANY_STANDARD` · `APPROVE_CUSTOMIZATION` · `REJECT` · `REQUEST_CLARIFICATION` | Step 31 |
| **5** | **Review Lifecycle** | Where is this Review in the workflow? | `DRAFT` → `UPLOADED` → `PROCESSING` → `ANALYSIS_COMPLETE` → `LEGAL_REVIEW` → `RESOLVED` → `CLOSED`<br>Exceptions: `ANALYSIS_FAILED`, `CANCELLED` | Step 30 |

### Axis 2 note — Finding Classification *is* Evaluation Outcome

These are the **same axis**, not two. The evaluation pipeline produces exactly one classification per evaluated Requirement, persisted as the `classification` field of the evaluator output (45B.12). "Evaluation outcome" is descriptive language for the same value.

The genuinely separate axis often confused with it is **axis 3, Rule Outcome**, which 45B.14 states explicitly:

> This is **not the same thing as Finding classification.**

```text
classification:
DEVIATION

rule_outcome:
ACCEPTABLE
```

---

## The document-level observation (not an axis)

`UNMATCHED_PROVISION` — a provision exists in the counterparty document with no corresponding configured Requirement.

**Status: LOCKED** (owner decision `REC-02`, 2026-08-16)

This is a **document-level observation, not a Finding Classification.** It is recorded separately from axis 2 and must never be written into a Finding's `classification` field.

Rationale: axis 2 is the outcome set of *evaluating a mapped Requirement*. An unmatched provision has no Requirement to evaluate, so it cannot carry an evaluation outcome. It supersedes `ADDITIONAL` (Step 18) and `EXTRA` (Step 27) — see [FINDING_CLASSIFICATION.md](FINDING_CLASSIFICATION.md).

The locked rules that governed `ADDITIONAL`/`EXTRA` carry over unchanged:

* An unmatched provision is **not** automatically negative or unacceptable.
* It retains traceable evidence like any other observation.
* It does not itself determine legal acceptability.

---

## Bridge rules between axes

These transitions are locked in the source and must be implemented exactly.

| Bridge | Rule | Source |
|--------|------|--------|
| Axis 1 → Axis 2 | A mapping state of `AMBIGUOUS` or `UNRESOLVED` **may produce** a Finding Classification of `UNABLE_TO_EVALUATE` — never a guessed classification. | Step 28 rule 6 |
| Axis 1 → Axis 2 | A required Requirement with **no** mapped provision may produce `MISSING`. | Step 28 rule 5 |
| Axis 2 → Axis 3 | Classification and Rule Outcome are evaluated separately. `DEVIATION` does **not** imply unacceptable. | Steps 18/27/36, 45B.14 |
| Axis 2 → Axis 3 | Where no rule outcome applies (`MATCH`, `MISSING`, `CONFLICT`, `AMBIGUOUS`, `UNRESOLVED`, `UNABLE_TO_EVALUATE`), the value is the explicit `NOT_APPLICABLE` — never null. | 45A §17, 45B.26 |
| Axis 3 → Axis 4 | The engine never produces a Legal Decision. Only an authorized human does. | Steps 27, 31, 36.15, 45A, 45B.14 |
| Axis 5 ⇄ Axis 2 | **`RESOLVED` ≠ `MATCH`.** A Review reaching `RESOLVED` never converts a Finding to `MATCH`. | Step 22 clarification, Step 30 |
| Axis 5 ⇄ Axis 2 | `ANALYSIS_FAILED` (Review-level: analysis could not complete) is **distinct** from `UNABLE_TO_EVALUATE` (Finding-level: evaluation could not establish a result). | Step 30 |

---

## ⚠ Token collisions across axes

Three axes reuse the same words for different concepts. **These are not the same value and must not share a database enum, an API type, or a display string.**

| Token | Axis 1 — Mapping State | Axis 2 — Classification | Extraction Status (45B.7) |
|-------|------------------------|-------------------------|---------------------------|
| `AMBIGUOUS` | More than one plausible mapping exists; must not silently choose one | Provisions found, but the intended legal position cannot be deterministically established | Facts were extracted but are not reliably interpretable |
| `UNRESOLVED` | The mapping cannot be established reliably | An issue is identified but evaluation cannot complete because required information or action is missing | — |

**Implementation requirement:** qualify these by axis wherever they appear — `MappingState.AMBIGUOUS`, `Classification.AMBIGUOUS`, `ExtractionStatus.AMBIGUOUS` — in the schema, the API contract, and the UI. A single shared `ambiguous` enum across layers is a defect.

Note that *extraction status* (45B.7: `COMPLETE` / `PARTIAL` / `AMBIGUOUS` / `FAILED`) is a fact-quality signal on the evaluator **input**, not one of the five axes. It feeds axis 2 — a `FAILED` extraction must produce `UNABLE_TO_EVALUATE` rather than a guess.

---

## The full chain

```text
Clause
   ↓
[AXIS 1] Mapping State          CONFIRMED / AMBIGUOUS / UNRESOLVED
   ↓
Fact Extraction                 (extraction_status: COMPLETE / PARTIAL / AMBIGUOUS / FAILED)
   ↓
Company Standard Comparison
   ↓
Legal Rule Evaluation
   ↓
[AXIS 2] Finding Classification MATCH / DEVIATION / MISSING / CONFLICT /
   ↓                            AMBIGUOUS / UNRESOLVED / UNABLE_TO_EVALUATE
[AXIS 3] Rule Outcome           ACCEPTABLE / APPROVAL_REQUIRED /
   ↓                            UNACCEPTABLE / NOT_APPLICABLE
[AXIS 5] Review Lifecycle       ... → LEGAL_REVIEW → RESOLVED → CLOSED
   ↓
[AXIS 4] Legal Decision         ACCEPT_DEVIATION / REQUIRE_COMPANY_STANDARD /
                                APPROVE_CUSTOMIZATION / REJECT / REQUEST_CLARIFICATION
```

Separately, outside the Requirement-evaluation path:

```text
Provision with no configured Requirement
   ↓
UNMATCHED_PROVISION (document-level observation)
```

---

## Canonical documents per axis

| Axis | Canonical document |
|------|--------------------|
| 1 — Mapping State | [../04-analysis-engine/REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) |
| 2 — Finding Classification | [FINDING_CLASSIFICATION.md](FINDING_CLASSIFICATION.md) |
| 3 — Rule Outcome | [LEGAL_RULES.md](LEGAL_RULES.md) |
| 4 — Legal Decision | [LEGAL_DECISIONS.md](LEGAL_DECISIONS.md) |
| 5 — Review Lifecycle | [../01-product/WORKFLOWS.md](../01-product/WORKFLOWS.md) |
