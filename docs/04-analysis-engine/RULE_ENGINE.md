Source: all_lock.md lines 10955-11208 (Step 44, sections 44.26-44.32). Canonical source: all_lock.md (Step 44 / Step 45A).

# Evaluator Architecture, Common Engine + Specialized Evaluators, the Rule Engine, Algorithm Selection, Classical NLP Libraries, and Embeddings

**Status: LOCKED** — Step 44 is locked in the master specification. See [../00-project/LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md).

Cross-reference: see ANALYSIS_ENGINE.md for the overall layered pipeline and the Step 44 lock. See FACT_EXTRACTION.md and CONFLICT_DETECTION.md for the layers this architecture wraps. See EXPLAINABILITY.md for the explainability contract these evaluators must satisfy.

---

## 44.26 Evaluator architecture

Example:

```text
Analysis Engine
│
├── LiabilityEvaluator
│    ├── LiabilityMapper
│    ├── LiabilityFactExtractor
│    └── LiabilityRuleEvaluator
│
├── TerminationEvaluator
│    ├── TerminationMapper
│    ├── TerminationFactExtractor
│    └── TerminationRuleEvaluator
│
├── GoverningLawEvaluator
│    ├── GoverningLawMapper
│    ├── GoverningLawFactExtractor
│    └── GoverningLawRuleEvaluator
│
└── ...
```

This allows requirement-specific precision without creating a completely different architecture for every clause.

---

## 44.27 Common engine + specialized evaluators

We should avoid two extremes.

### Bad approach A

One enormous universal legal parser.

```text
UniversalLegalParser
```

Too difficult to test and reason about.

### Bad approach B

Every requirement becomes a completely independent application.

Too much duplication.

### Correct approach

```text
Shared deterministic infrastructure
+
Requirement-specific evaluators
```

Shared:

```text
Normalization
Structure parsing
Pattern engine
Candidate ranking
Evidence model
Fact model
Rule execution
Diagnostics
```

Specialized:

```text
Liability
Termination
Indemnification
Governing Law
```

---

## 44.28 Rule engine

The Rule Engine should execute structured rules.

For example:

```text
IF
    actual_value <= acceptable_max

THEN
    rule_outcome = ACCEPTABLE
```

Another:

```text
IF
    actual_value > approval_threshold

THEN
    rule_outcome = APPROVAL_REQUIRED
```

Rules should be data/configuration driven where practical.

The engine executes them.

It should not require modifying Python code every time an Admin changes a Company Standard.

---

## 44.29 But not everything should be configurable

We should **not** make the entire legal analysis engine arbitrary JSON.

Core evaluator algorithms belong in tested Python code.

Configuration controls things like:

```text
thresholds
allowed values
patterns
terminology
rule parameters
```

Python controls:

```text
parsing algorithms
normalization
fact extraction algorithms
comparison semantics
evaluation execution
conflict detection mechanics
```

This gives us both flexibility and safety.

---

## 44.30 Algorithm selection

For V1, the best approach is a **hybrid deterministic NLP/rule-based pipeline**, not one algorithm.

Use:

### 1. Structural heuristics

For:

```text
headings
sections
paragraphs
tables
```

### 2. Lexical matching

Use:

```text
exact match
case-normalized match
phrase matching
controlled synonyms
```

### 3. Regex/pattern matching

For structured values:

```text
6 months
12 months
30 days
₹10 million
USD 5,000
```

### 4. Finite-state / rule-based extraction

For legal patterns such as:

```text
shall not exceed X
may terminate upon X days' notice
governed by laws of X
```

### 5. Candidate ranking

Use deterministic weighted signals.

### 6. Requirement-specific evaluators

Convert evidence into structured facts.

### 7. Rule evaluation

Compare facts against Company Standards and Legal Rules.

This combination is substantially stronger than plain keyword matching while remaining explainable.

---

## 44.31 What about classical NLP libraries?

A controlled classical NLP layer can be used where it genuinely helps:

```text
spaCy
```

for things such as:

* sentence segmentation
* tokenization
* linguistic normalization
* selected entity extraction

But it should **not become the legal decision-maker**.

The authoritative result still comes from deterministic evaluators and rules.

---

## 44.32 What about embeddings?

For V1:

**No vector database and no semantic retrieval.**

However, a future architecture may evaluate semantic retrieval separately.

The important thing is:

```text
V1:
Deterministic retrieval
```

not:

```text
V1:
Embedding similarity decides legal relevance
```
