Source: all_lock.md lines 10703-10856 (Step 44, sections 44.18-44.22). Canonical source: all_lock.md (Step 44 / Step 45A).

# Layer 7 — Conflict Detection, Cross-Clause Analysis, Missing Clause Detection, Ambiguity, and Unresolved State

**Status: LOCKED** — Step 44 is locked in the master specification. See [../00-project/LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md).

Cross-reference: see ANALYSIS_ENGINE.md for the overall layered pipeline. See FACT_EXTRACTION.md for Layers 5-6. See EDGE_CASES/LIABILITY.md for how CONFLICT, AMBIGUOUS, MISSING, and UNABLE_TO_EVALUATE apply concretely to LIABILITY-001.

---

## 44.18 Layer 7 — Conflict detection

Conflict detection should be a dedicated engine capability.

Example:

```text
Section 8:
Liability limited to 6 months.

Schedule B:
Liability shall be unlimited.
```

The engine should produce:

```text
CONFLICT
```

rather than selecting one clause and ignoring the other.

The Finding should reference:

```text
Evidence A
Evidence B
```

with:

```text
relationship_type = CONFLICTING
```

---

## 44.19 Cross-clause analysis

Some legal requirements cannot be evaluated from one paragraph.

Example:

```text
Section 8:
Liability capped at 6 months.

Section 8.3:
Cap does not apply to confidentiality breaches.
```

The evaluator may need both.

Therefore:

> Requirement evaluators must be able to consume **multiple Evidence items**.

This is already supported by the Step 42 schema.

---

## 44.20 Missing clause detection

Missing clauses are not the same as:

```text
Unable to extract
```

The engine must distinguish:

```text
MISSING
```

from:

```text
UNABLE_TO_EVALUATE
```

Example:

### Missing

No termination provision is found anywhere.

```text
MISSING
```

### Unable to evaluate

A termination clause exists, but extraction is too corrupted to reliably determine the notice period.

```text
UNABLE_TO_EVALUATE
```

These must never be treated as equivalent.

---

## 44.21 Ambiguity

Consider:

> "Liability shall be limited to an amount agreed between the parties."

There is a liability concept, but no determinable amount.

Result:

```text
AMBIGUOUS
```

Not:

```text
MATCH
```

and not automatically:

```text
MISSING
```

---

## 44.22 Unresolved state

`UNRESOLVED` should represent a workflow state rather than a guessed legal conclusion.

For example:

```text
Conflict detected
       ↓
Legal review required
       ↓
UNRESOLVED
```

After an authorized decision:

```text
UNRESOLVED
       ↓
RESOLVED
```

This is different from the analytical classification.
