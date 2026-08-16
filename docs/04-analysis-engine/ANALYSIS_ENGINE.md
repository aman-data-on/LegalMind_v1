Source: all_lock.md — Step 36 (lines 4667-5125), Steps 38.9-38.13 (lines 5446-5573), Step 44 (lines 10110-11796). This file covers Steps 36, 38.9-38.13, and 44. Canonical source: all_lock.md (Step 36 / Step 38 / Step 44 / Step 45A).

# Step 36 — Finding & Evaluation Engine

Status: LOCKED

This is the **most important algorithmic step so far**.

Step 35 answers:

> **Which Requirement does this clause belong to?**

Step 36 answers:

> **What does that clause mean according to our Company Standard and Legal Rule?**

## 36.1 The evaluation pipeline

```text
Mapped Clause
      ↓
Requirement
      ↓
Company Standard
      ↓
Legal Rule
      ↓
Deterministic Evaluation
      ↓
Finding
```

Possible V1 outcomes:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

---

## 36.2 MATCH

Customer provision conforms to the Company Standard.

Example:

```text
Company Standard:
Liability = 6 months

Customer:
Liability = 6 months

Result:
MATCH
```

---

## 36.3 DEVIATION

Customer provision differs from the Company Standard.

Example:

```text
Company Standard:
6 months

Customer:
12 months

Result:
DEVIATION
```

Important:

**DEVIATION does not automatically mean unacceptable.**

The Legal Rule determines what happens next.

---

## 36.4 MISSING

The Requirement is expected, but no qualifying provision is found.

```text
Requirement:
Limitation of Liability

Customer:
No qualifying liability limitation found

Result:
MISSING
```

---

## 36.5 CONFLICT

Multiple provisions within the same contract produce incompatible positions.

Example:

```text
Section 8.2:
Liability capped at 6 months

Section 14.4:
Liability is unlimited

Result:
CONFLICT
```

Both pieces of evidence remain attached.

---

## 36.6 AMBIGUOUS

The system found potentially relevant provisions but cannot deterministically establish the intended legal position.

```text
Clause:
"Liability may be limited as mutually agreed."

Result:
AMBIGUOUS
```

Legal review is required.

---

## 36.7 UNRESOLVED

The system has identified an issue but cannot complete the evaluation because required information or a required action is missing.

This is different from `AMBIGUOUS`.

---

## 36.8 UNABLE_TO_EVALUATE

The system cannot reliably perform the evaluation because the underlying evidence is unavailable or unreliable.

Example:

```text
Scanned page
   ↓
OCR failed
   ↓
Liability clause cannot be reliably extracted
   ↓
UNABLE_TO_EVALUATE
```

This prevents LegalMind from pretending that "not found" means "missing."

---

## 36.9 The most important rule

The engine must separate:

```text
Deviation
```

from:

```text
Legal acceptability
```

Example:

```text
Company Standard:
6 months

Customer:
12 months

Finding:
DEVIATION
```

Then the Legal Rule says:

```text
Preferred:
6 months

Acceptable:
≤12 months

Approval Required:
>12 months
```

So **DEVIATION is the factual comparison result**.

The Legal Rule determines the required workflow.

---

## 36.10 No generic risk score

I recommend we **do not introduce**:

```text
Risk = 83%
```

or:

```text
Low / Medium / High
```

as the primary V1 legal output.

Instead, LegalMind should produce a deterministic classification based on the configured Legal Rule.

That is much more defensible.

---

## 36.11 Requirement-specific evaluation

Different legal requirements need different evaluation algorithms.

For example:

### Liability

Numeric/range evaluation:

```text
Customer:
12 months

Standard:
6 months

Rule:
≤12 months acceptable

Finding:
DEVIATION
Workflow:
Legal decision may be required according to configuration
```

### Governing Law

Exact/allowed-value evaluation:

```text
Company Standard:
India

Customer:
Singapore

Finding:
DEVIATION
```

### Notice Period

Numeric comparison:

```text
Company Standard:
30 days

Customer:
60 days

Finding:
DEVIATION
```

So we should **not create one universal comparison algorithm** for every legal clause.

The Requirement configuration determines the appropriate deterministic evaluator.

---

## 36.12 Evaluation types

I recommend supporting a controlled set of evaluator types, such as:

```text
EXACT_MATCH
ALLOWED_VALUES
NUMERIC_COMPARISON
RANGE_COMPARISON
BOOLEAN_PRESENT
BOOLEAN_ABSENT
TEXT_PATTERN
MULTI_CLAUSE
CONFLICT_DETECTION
```

This gives us a reusable deterministic engine without introducing AI.

---

## 36.13 Example

```text
Requirement:
LIABILITY-001

Evaluator:
NUMERIC_COMPARISON

Company Standard:
6 months

Customer:
12 months

Legal Rule:
≤12 months = Acceptable
>12 months = Approval Required

Evaluation:
Customer value ≠ Company Standard
Customer value ≤ Acceptable threshold

Finding:
DEVIATION
```

Then Legal decides whether to:

```text
ACCEPT_DEVIATION
APPROVE_CUSTOMIZATION
REQUIRE_COMPANY_STANDARD
REJECT
REQUEST_CLARIFICATION
```

according to Step 31.

---

## 36.14 Evaluation must preserve the calculation

For numeric rules, don't only save:

```text
DEVIATION
```

Save the actual evaluation inputs:

```text
Expected:
6 months

Actual:
12 months

Operator:
>

Acceptable threshold:
12 months

Evaluation:
Actual > Expected
AND
Actual <= Acceptable threshold
```

This makes the result reproducible.

---

## 36.15 No automatic Legal Decision

The Evaluation Engine produces:

```text
FINDING
```

It does **not** produce:

```text
APPROVE_CUSTOMIZATION
```

That remains the Legal Decision layer from Step 31.

---

## 36.16 Historical reproducibility

Every evaluation must preserve:

```text
Document Version
Requirement Version
Company Standard Version
Legal Rule Version
Evaluator Version
Evaluation Inputs
Evaluation Output
```

Therefore:

```text
Same inputs
+
Same versions
=
Same Finding
```

This is exactly what we want from V1.

---

## 36.17 Step 36 recommendation

I recommend locking these principles:

1. Finding generation is deterministic.
2. Mapping and Evaluation are separate engines.
3. `DEVIATION` means deviation from Company Standard; it does not itself mean unacceptable.
4. Legal Rules determine the required workflow for a deviation.
5. V1 supports controlled Finding classifications: `MATCH`, `DEVIATION`, `MISSING`, `CONFLICT`, `AMBIGUOUS`, `UNRESOLVED`, and `UNABLE_TO_EVALUATE`.
6. Different Requirements may use different deterministic evaluator types.
7. No generic opaque risk percentage is used as the primary V1 legal classification.
8. Numeric evaluations preserve their inputs, operators, thresholds, and resulting comparison.
9. Multiple clauses may be evaluated collectively.
10. Conflicting provisions remain separately evidenced.
11. Insufficient evidence must not be converted into a false `MISSING` or `MATCH`.
12. The Evaluation Engine never makes a Legal Decision.
13. Every evaluation is reproducible from versioned inputs and rules.
14. Evaluator logic/configuration is versioned.
15. Historical Findings are never silently recalculated using newer rules.
16. Every Finding retains the Evidence/Requirement/Standard/Rule chain from Step 32.

### 🔒 Step 36 — LOCKED

---

# Step 38.9-38.13 — Analysis Engine Domain Boundaries

## 38.9 Analysis Engine

This should be isolated from the UI.

Its responsibility:

```text
Normalized Contract
        ↓
Clause Mapping
        ↓
Requirement Mapping
        ↓
Deterministic Evaluation
        ↓
Findings
```

This is the core LegalMind engine.

---

## 38.10 Mapping Engine

Responsible only for:

> **Which Requirement does this clause relate to?**

Example:

```text
Section 8.2
"Aggregate liability shall not exceed..."

        ↓

LIABILITY-001
```

It should not decide whether the customer term is acceptable.

---

## 38.11 Evaluation Engine

Responsible only for:

> **How does the mapped provision compare with the configured Company Standard and Legal Rule?**

Example:

```text
Customer:
12 months

Company Standard:
6 months

Legal Rule:
≤12 months acceptable

        ↓

Finding:
DEVIATION
```

Again:

**Evaluation ≠ Legal Decision.**

---

## 38.12 Findings Domain

Stores the result of deterministic analysis.

Example:

```text
Finding
 ├── Requirement
 ├── Evidence
 ├── Company Standard Version
 ├── Legal Rule Version
 ├── Evaluation
 └── Classification
```

Possible classifications:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

---

## 38.13 Review Workflow

A Review is the container that connects everything.

Conceptually:

```text
Review
 │
 ├── Contract
 ├── Document Version
 ├── Configuration Snapshot
 ├── Analysis
 ├── Findings
 ├── Legal Decisions
 └── Audit Events
```

This is extremely important.

A Review should represent:

> **What LegalMind analyzed, using which versions, and what happened as a result.**

---

# Step 44 — Legal Analysis Engine Architecture

This is one of the **most important steps in the entire LegalMind design**.

The question we must answer is:

> **How does LegalMind take an actual contract, understand the relevant clause using deterministic methods, compare it against the Company Standard and Legal Rule, and produce a defensible Finding?**

We need something substantially better than simple keyword matching.

The V1 engine should therefore be a **layered deterministic legal analysis pipeline**.

Cross-reference: FACT_EXTRACTION.md (Layers 5-6), CONFLICT_DETECTION.md (Layer 7, cross-clause, missing clause, ambiguity, unresolved state), EXPLAINABILITY.md (confidence/explainability/failure philosophy), RULE_ENGINE.md (evaluator architecture, rule engine, algorithm selection), GOLDEN_CORPUS.md and REGRESSION_TESTING.md (docs/08-testing).

---

## 44.1 The fundamental principle

LegalMind must never jump directly from:

```text
Contract text
      ↓
Finding
```

Instead:

```text
Contract
   ↓
Document Evidence
   ↓
Normalization
   ↓
Requirement Candidate Detection
   ↓
Evidence Selection
   ↓
Structured Fact Extraction
   ↓
Requirement Evaluation
   ↓
Legal Rule Evaluation
   ↓
Finding
   ↓
Evidence + Explanation
```

Every stage should produce inspectable intermediate results.

---

## 44.2 The engine

The core engine should conceptually be:

```text
                Document Evidence
                       ↓
                  Normalization
                       ↓
                Requirement Mapping
                       ↓
                Evidence Selection
                       ↓
                 Fact Extraction
                       ↓
              Deterministic Evaluation
                       ↓
               Legal Rule Evaluation
                       ↓
               Finding Generation
```

---

## 44.3 Layer 1 — Text normalization

Raw extraction is not analysis-ready.

For example, a PDF may produce:

```text
Limitation of Liabil-
ity
```

while the actual clause is:

```text
Limitation of Liability
```

Normalization should handle things such as:

* whitespace
* line breaks
* hyphenation caused by PDF layout
* repeated headers/footers
* page artifacts
* Unicode normalization
* quotation normalization
* common OCR errors where safely detectable
* section numbering normalization

But:

> **Normalization must never silently alter the legal meaning of the original text.**

Original evidence remains preserved.

---

## 44.4 Layer 2 — Structural parsing

Before looking for legal concepts, extract document structure.

For example:

```text
Document
 ├── Page 1
 ├── Page 2
 ├── Section 1
 ├── Section 2
 ├── Section 8
 │     └── 8.2 Limitation of Liability
 └── Appendix A
```

The engine should identify:

* page boundaries
* headings
* numbered sections
* paragraphs
* tables
* bullet lists
* annexures/schedules where detectable

This gives later stages structural signals.

---

## 44.5 Layer 3 — Requirement Mapping

Now LegalMind asks:

> **Where in this contract is the evidence relevant to this Requirement?**

Example:

```text
Requirement:
LIABILITY-001
```

Potential evidence:

```text
Section 8 — Limitation of Liability
Section 8.2 — Aggregate Liability
Schedule B — Liability
```

The mapper should combine multiple deterministic signals.

### Do NOT use simple keyword matching alone

Weak implementation:

```text
if "liability" in text:
    return liability_clause
```

This will fail badly.

For example:

> "The parties shall have no limitation of liability for fraud."

That contains "limitation of liability" but may represent a specific carve-out rather than the general liability cap.

Instead, use **multi-signal candidate ranking**.

### Candidate ranking

For every Requirement, candidate evidence can receive a deterministic relevance score based on signals such as:

```text
Heading match
Section-title match
Known terminology
Positive patterns
Negative patterns
Required concepts
Proximity of related terms
Section position
Clause structure
```

Conceptually:

```text
Candidate Score =
    heading_score
  + terminology_score
  + pattern_score
  + concept_score
  + proximity_score
  + structural_score
```

The exact numerical weights should **not be hard-coded globally yet**.

They should be Requirement/evaluator configuration.

### Why ranking matters

Suppose a contract contains:

```text
Section 4:
Confidentiality

Section 9:
Limitation of Liability

Section 15:
General provisions referring to liability.
```

A simple search might return all three.

The mapper should rank:

```text
Section 9 → strongest candidate
Section 15 → secondary candidate
Section 4 → irrelevant
```

Then the engine can evaluate the strongest relevant evidence while preserving secondary evidence where necessary.

---

## 44.9 Layer 4 — Evidence selection

Mapping produces candidates.

Selection determines:

> **Which evidence is actually sufficient for evaluation?**

Possible outcomes:

```text
FOUND
MULTIPLE_CANDIDATES
MISSING
AMBIGUOUS
```

This distinction is important.

If two contradictory liability clauses exist:

```text
Section 8 → 6 months
Schedule B → unlimited
```

the engine should **not simply choose whichever scored highest**.

It should identify a potential conflict.

(Layer 5 — Structured fact extraction — and Layer 6 — Negative patterns and scope extraction — are documented in FACT_EXTRACTION.md. Layer 7 — Conflict detection, cross-clause analysis, missing clause detection, ambiguity, and unresolved state are documented in CONFLICT_DETECTION.md.)

---

## 44.36 Engine versioning

The analysis engine itself must have a version.

For example:

```text
engine_version = 1.0.0
```

A Review should retain:

```text
configuration_snapshot
+
analysis_engine_version
+
processing_version
```

Then six months later we can answer:

> Which exact engine produced this Finding?

This is an important addition to the historical reproducibility requirement.

### Deterministic reproducibility

Given identical:

```text
Document Evidence
+
Configuration Snapshot
+
Analysis Engine Version
```

the engine should produce the same result.

Formally:

```text
Same Input
+
Same Rules
+
Same Engine Version
=
Same Output
```

No hidden external model or changing API should alter the result.

---

## 44.39 End-to-end example

Let's take one realistic example.

Contract:

> "The aggregate liability of the Supplier shall not exceed twenty-four months of fees paid under this Agreement. This limitation shall not apply to fraud or wilful misconduct."

### Step 1 — Mapping

Relevant evidence:

```text
Section 10.2
Page 14
```

### Step 2 — Fact extraction

```text
general_cap = 24 months

exceptions:
- fraud
- wilful misconduct
```

### Step 3 — Company Standard

```text
preferred = 6 months
```

### Step 4 — Legal Rule

```text
≤ 12 months = acceptable
> 12 months = approval required
```

### Step 5 — Evaluation

```text
24 > 12
```

### Step 6 — Result

```text
Finding:
DEVIATION

Rule Outcome:
APPROVAL_REQUIRED
```

### Step 7 — Evidence

Attach:

```text
Section 10.2
Page 14
```

### Step 8 — Explanation

The UI can explain:

```text
Company Standard: 6 months
Contract provision: 24 months
Applicable rule: >12 months requires approval
```

### Step 9 — Legal Decision

Authorized reviewer decides:

```text
APPROVE_CUSTOMIZATION
```

The Company Standard remains:

```text
6 months
```

This preserves the already locked:

> **RESOLVED ≠ MATCH**

principle.

---

## 44.40 Final architecture

The complete V1 Analysis Engine becomes:

```text
                    DOCUMENT
                       │
                       ↓
                 RAW EVIDENCE
                       │
                       ↓
                 NORMALIZATION
                       │
                       ↓
               STRUCTURAL PARSER
                       │
                       ↓
              REQUIREMENT MAPPER
                       │
                       ↓
              CANDIDATE RANKING
                       │
                       ↓
               EVIDENCE SELECTOR
                       │
                       ↓
             FACT EXTRACTION
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
        FACTS VALID?          AMBIGUOUS
             │                   │
             ↓                   ↓
       RULE EVALUATION       UNRESOLVED /
             │               UNABLE_TO_EVALUATE
             ↓
       CONFLICT CHECK
             │
             ↓
        EVALUATION
             │
             ↓
          FINDING
             │
       ┌─────┴─────┐
       ↓           ↓
   EVIDENCE    EXPLANATION
       │
       ↓
 LEGAL DECISION
       │
       ↓
    AUDIT EVENT
```

---

## Step 44 — Proposed Lock

Status: LOCKED

I recommend locking these principles:

1. LegalMind V1 uses a **layered deterministic analysis engine**.
2. Raw contract text is never directly converted into a Finding.
3. Original evidence remains preserved.
4. Normalization never silently changes legal meaning.
5. Document structure is extracted before legal mapping.
6. Requirement Mapping is separate from Evaluation.
7. Candidate selection uses multiple deterministic signals rather than keywords alone.
8. Evidence selection explicitly handles multiple candidates.
9. Requirement-specific fact extraction converts relevant language into structured facts.
10. Evaluators are requirement-specific but use shared deterministic infrastructure.
11. Company Standards and Legal Rules are inputs to evaluation, not hard-coded legal conclusions.
12. Negative patterns and carve-outs are first-class concepts.
13. Cross-clause analysis is supported.
14. Conflicting provisions are explicitly detected rather than silently choosing one.
15. `MISSING`, `AMBIGUOUS`, `UNRESOLVED`, and `UNABLE_TO_EVALUATE` remain distinct states.
16. The system does not use generic AI confidence scores.
17. The system fails closed rather than guessing.
18. V1 uses deterministic NLP/rule-based techniques such as structural heuristics, lexical matching, regex/pattern extraction, finite-state/rule logic, candidate ranking, and requirement-specific evaluators.
19. Classical NLP libraries such as spaCy may assist extraction/segmentation but cannot determine the legal result.
20. V1 does not use LLM, RAG, embeddings, or vector search in the authoritative legal-analysis path.
21. The Rule Engine executes configurable rule parameters while core evaluation algorithms remain tested application code.
22. Every Finding must be explainable through Evidence → Fact → Standard → Rule → Result.
23. The Analysis Engine has its own explicit version.
24. A Review records the Analysis Engine Version alongside its Configuration Snapshot.
25. Identical evidence + identical configuration + identical engine version must produce the same result.
26. A golden contract corpus is mandatory for evaluator validation and regression testing.
27. Every material Finding must remain traceable to the exact evidence used to produce it.
28. LegalMind must never manufacture a legal conclusion when evidence is insufficient.

### 🔒 Step 44 — LOCKED

The final authoritative architecture is:

```text
Document Version
      ↓
Original Evidence
      ↓
Normalization
      ↓
Structural Parsing
      ↓
Requirement Mapping
      ↓
Candidate Selection
      ↓
Evidence Selection
      ↓
Fact Extraction
      ↓
┌──────────────────────────────┐
│ Requirement Evaluation       │
│ Conflict Detection           │
│ Cross-Clause Analysis        │
└──────────────┬───────────────┘
               ↓
        Evaluation Result
               ↓
            Finding
               ↓
      Evidence + Explanation
               ↓
        Review Workflow
               ↓
  Authorized Legal Decision
               ↓
          Audit Event
```

### Final locked clarifications

* **Analysis Engine ends at Finding + Evidence + Explanation.**
  Legal Decision is outside the engine and belongs to the authorized Legal workflow.

* **`AMBIGUOUS`, `UNRESOLVED`, and `UNABLE_TO_EVALUATE` are distinct.**
  The engine must never use uncertainty as an excuse to guess.

* **Conflict Detection is a first-class engine capability.**
  It is not merely a final step after a single clause evaluation.

* The V1 engine remains completely deterministic, versioned, reproducible, and explainable.

* Same:

  ```text
  Evidence
  + Configuration
  + Analysis Engine Version
  ```

  must produce the same analytical result.

* No LLM, RAG, embeddings, vector database, or AI-generated legal decision enters this authoritative V1 path.

This fits the existing locked requirements around deterministic evaluation, evidence traceability, reproducibility, and separation between Findings and Legal Decisions.

## Current position

```text
Steps 1–43  🔒 LOCKED
Step 44      🔒 LOCKED
```

### Next: Step 45 — Requirement / Evaluator Specification

Now we move from **architecture** to the actual legal evaluation design.

We'll define, requirement by requirement:

```text
Requirement
   ↓
Evidence required
   ↓
Fact extraction
   ↓
Positive / negative patterns
   ↓
Carve-outs / exceptions
   ↓
Company Standard
   ↓
Legal Rule
   ↓
Evaluation logic
   ↓
Finding
   ↓
Possible workflow consequence
```

And we should start with **Limitation of Liability** as the first concrete evaluator because it is already our canonical example throughout the specification.

**Step 44 is locked. We move to Step 45.**

See EDGE_CASES/LIABILITY.md for Step 45A (LIABILITY-001).
