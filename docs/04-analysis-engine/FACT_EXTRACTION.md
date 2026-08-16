Source: all_lock.md lines 10412-10701 (Step 44, sections 44.10-44.17). Canonical source: all_lock.md (Step 44 / Step 45A).

# Layer 5 — Structured Fact Extraction and Layer 6 — Negative Patterns / Scope Extraction

**Status: LOCKED** — Step 44 is locked in the master specification. See [../00-project/LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md).

Cross-reference: see ANALYSIS_ENGINE.md for the overall layered pipeline (Layers 1-4, versioning, end-to-end example, final architecture, and the Step 44 lock). See CONFLICT_DETECTION.md for Layer 7. See EDGE_CASES/LIABILITY.md for the full LIABILITY-001 evaluator built on top of this layer.

---

## 44.10 Layer 5 — Structured fact extraction

This is where LegalMind becomes substantially more powerful than keyword matching.

The engine converts relevant language into structured facts.

Example:

```text
Contract text:

"Aggregate liability shall not exceed an amount
equal to twelve months of fees paid under this Agreement."
```

Fact:

```text
{
  "concept": "liability_cap",
  "value": 12,
  "unit": "months",
  "scope": "aggregate"
}
```

This fact is what the evaluator uses.

---

## 44.11 Fact extraction should be requirement-specific

There should not be one universal parser trying to understand every legal concept.

Instead:

```text
Liability Evaluator
    ↓
liability fact extractor

Termination Evaluator
    ↓
termination fact extractor

Governing Law Evaluator
    ↓
governing-law fact extractor
```

This makes the system much more deterministic and testable.

---

## 44.12 Example — Liability

Input:

> "The aggregate liability of either party shall not exceed six months of fees paid under this Agreement."

Extract:

```text
concept: liability_cap
value: 6
unit: months
scope: aggregate
```

Company Standard:

```text
preferred = 6 months
```

Legal Rule:

```text
preferred = 6
acceptable_max = 12
approval_required_above = 12
```

Evaluation:

```text
6 == 6
```

Result:

```text
MATCH
```

---

## 44.13 Example — Deviation

Contract:

> "Aggregate liability shall not exceed twelve months of fees."

Extract:

```text
liability_cap = 12 months
```

Standard:

```text
preferred = 6 months
```

Rule:

```text
≤12 months = acceptable
```

Result:

```text
DEVIATION
```

It is **not automatically a legal failure**.

That distinction is fundamental.

---

## 44.14 Example — Approval Required

Contract:

> "Aggregate liability shall not exceed twenty-four months of fees."

Extract:

```text
liability_cap = 24 months
```

Rule:

```text
>12 months = APPROVAL_REQUIRED
```

Finding:

```text
DEVIATION
```

with the evaluation state:

```text
APPROVAL_REQUIRED
```

The exact Finding/decision terminology should remain consistent with the previously locked Legal Decision model.

---

## 44.15 Example — Unlimited liability

Contract:

> "Neither party's liability shall be subject to any limitation."

Extract:

```text
liability_cap = UNLIMITED
```

If Company Standard says:

```text
6 months
```

and Legal Rule says:

```text
UNLIMITED = UNACCEPTABLE
```

then:

```text
Finding:
DEVIATION

Rule outcome:
UNACCEPTABLE
```

This is where the Legal Rule—not an arbitrary AI score—determines the outcome.

---

## 44.16 Layer 6 — Negative patterns

Negative patterns are essential.

Suppose we search for:

```text
"liability shall not exceed"
```

But the contract says:

> "Except for liability arising from fraud, the liability cap shall not exceed six months."

The engine must understand that:

```text
fraud
```

is a carve-out.

Therefore, a Requirement may define:

```text
positive patterns
negative patterns
carve-out patterns
scope patterns
```

---

## 44.17 Scope extraction

This is a major legal-analysis requirement.

A clause may contain:

```text
General cap:
6 months

Exceptions:
fraud
wilful misconduct
confidentiality breach
IP infringement
```

LegalMind should not flatten this into:

```text
liability_cap = 6 months
```

only.

It should preserve:

```text
General Rule
+
Exceptions / Carve-outs
```

Example:

```text
{
  "general_cap": {
    "value": 6,
    "unit": "months"
  },
  "exceptions": [
    "fraud",
    "wilful misconduct",
    "confidentiality"
  ]
}
```

This is much more useful for legal evaluation.
