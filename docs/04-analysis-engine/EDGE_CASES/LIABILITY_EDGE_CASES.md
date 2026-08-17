# Step 45C — LIABILITY-001 Edge Cases

**Status: 🔒 LOCKED (2026-08-17).**

Authored by the project owner, 2026-08-16. Text preserved verbatim below. Locked 2026-08-17; lock record in [`all_lock.md`](../../../all_lock.md) under "Step 45C — LOCK RECORD", which adds 45C.27 (detected-but-unresolvable precedence), 45C.28 (heterogeneous scoped outcomes), 45C.29 (widen-only configuration) and lock rules 18–19.

Related: [LIABILITY.md](LIABILITY.md) (Step 45A — policy, 🔒 LOCKED) · [LIABILITY_EVALUATOR_CONTRACT.md](LIABILITY_EVALUATOR_CONTRACT.md) (Step 45B — data contract, 🔒 LOCKED) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

**Purpose:** prove that `LIABILITY-001` does not break when the contract contains more complicated provisions. The master spec already requires scope, carve-outs, multiple clauses, cross-references, conflicts, and fail-closed behavior.

---

# REVIEW FINDINGS — ✅ ALL RESOLVED (Amendment Batch AB-1, 2026-08-17)

45C is substantively consistent with locked Steps 44/45A and contradicts none of them. Its decision matrix (45C.21) matches the locked 45A §17 matrix exactly on every shared row.

**Four locked-decision amendments were required.** All four were resolved through Amendment Batch AB-1: A-1 and A-3 by the generalized `caps[]` structure and `evaluation_kind`; A-2 by the locked 42.8 configuration JSONB (no schema change needed); A-4 by the Evaluation-level decision model. The original findings are retained below as the record of why.

## A-1 — `facts` must represent multiple caps

**Required by:** 45C.1, 45C.5, 45C.6, 45C.26 rules 1 & 4.

45C.26 rule 1 states "Multiple liability provisions are supported," and 45C.5 requires preserving `per_claim` and `aggregate` simultaneously. The locked 45B `facts` block represents **exactly one** cap:

```text
facts: {
    cap_status, cap_value, cap_unit, cap_basis, scope, ...
}
```

A repeating cap structure is required. **This amends locked Step 45B.**

## A-2 — `company_standard` needs a `scope`

**Required by:** 45C.5, 45C.20, 45C.24.

45C.5 says the evaluator "must not compare ₹10 lakh directly against the Company Standard for an aggregate cap," and 45C.20 requires `UNABLE_TO_EVALUATE` when scope is undeterminable and "scope is necessary for the applicable comparison." Both presuppose the Company Standard carries a scope. The locked 45B block does not:

```text
company_standard: { version_id, preferred_value, preferred_unit }
```

**This amends locked Step 45B.**

## A-3 — `exceptions[]` must be structured, not a bare list

**Required by:** 45C.4, 45C.26 rule 6.

45C.4 requires an exception to carry its own cap position:

```text
exception:
confidentiality breach → UNLIMITED
```

45A §7 and 45B model `exceptions[]` as a flat list of labels (`fraud`, `wilful misconduct`, `confidentiality breach`). Carrying a per-exception cap position requires each exception to become a structured object with at minimum a scope and a cap status. **This amends locked Step 45B.**

## A-4 — Evaluation result cardinality is undefined

**Required by:** 45C.1 ("evaluate them according to scope"), 45C.21 ("Different scopes → Evaluate separately"; "General cap + carve-out → Evaluate scope/exception separately").

If different scopes and carve-outs are evaluated *separately*, one Requirement on one document can yield **more than one evaluation result**. The locked 45B `EvaluationResult` is a single object with one `classification` and one `rule_outcome`.

The locked corpus does not settle this: Step 27 rule 16 allows multiple Findings per *Review*, and Step 28 rule 2 allows multiple clauses per *Requirement*, but **nothing states whether one Requirement may produce multiple Findings in one Review.**

**RESOLVED:** one Finding per Requirement, grouping one or more scoped Evaluations. Confirmed by locked 41.19/42.15 (`evaluations.finding_id`) and 42.14's single `classification` column.

## Dependency note

45C.2 and 45C.22 permit precedence resolution via a configured precedence rule in `rule_configuration`, whose minimum shape is specified in J-5. Narrowed by F-6: **configured precedence only** — in-document precedence language is detected, evidenced and reported, never applied (45C.27).

## Triage mapping

How 45C resolves the edge cases identified in the opening triage:

| Triage ID | Resolved by | Status |
|-----------|-------------|--------|
| EC-1 Multiple caps | 45C.1, 45C.5, 45C.6 | ✅ Resolved (A-1 via AB-1) |
| EC-2 Carve-outs | 45C.3, 45C.4, 45C.21 | ✅ Resolved (A-3 via AB-1) |
| EC-3 Per-claim vs aggregate | 45C.5, 45C.6, 45C.20 | ✅ Resolved (A-2 — 42.8 JSONB, no schema change) |
| EC-4 Monetary bases | 45C.7, 45C.8, 45C.9, 45C.23 | ✅ Fully resolved |
| EC-5 Cross-references | 45C.10, 45C.11 | ✅ Fully resolved |
| EC-6 Conflicting schedules | 45C.2, 45C.22 | ✅ Resolved — depends on `rule_configuration` |
| EC-7 Malformed/ambiguous | 45C.13, 45C.18, 45C.19 | ✅ Resolved — boundary defined by AM-7 and the J-6 discriminator (`AMBIGUOUS` = too many candidates; `UNRESOLVED` = no usable answer) |

---

# Step 45C — LIABILITY-001 Edge Cases

## 45C.1 Multiple liability caps

Example:

```text
Section 8:
Aggregate liability = 6 months

Schedule B:
Liability for service credits = 3 months
```

These are **not automatically a conflict**.

The evaluator must preserve:

```text
Cap A
scope = aggregate

Cap B
scope = service credits
```

Then evaluate them according to scope.

**Rule:** Different scopes do not constitute a conflict merely because the numeric values differ.

---

## 45C.2 Same scope, different caps

Example:

```text
Section 8:
Aggregate liability = 6 months

Schedule B:
Aggregate liability = 12 months
```

Now both provisions appear to govern the same scope.

Result:

```text
CONFLICT
```

unless a deterministic cross-reference establishes which provision controls.

Both evidence references must remain attached.

---

## 45C.3 General cap + carve-out

Example:

> Aggregate liability shall not exceed 6 months, except for fraud and wilful misconduct.

Structured facts:

```text
general_cap = 6 months

exceptions:
- fraud
- wilful misconduct
```

This is **not a conflict**.

The evaluator preserves both the general rule and exceptions.

---

## 45C.4 Unlimited carve-out

Example:

> Liability is capped at 6 months, except liability arising from confidentiality breaches is unlimited.

Result:

```text
general_cap = 6 months

exception:
confidentiality breach → UNLIMITED
```

Do **not** classify the whole provision as simply:

```text
UNLIMITED
```

The unlimited position applies only to the specified exception.

---

## 45C.5 Per-claim vs aggregate

Example:

```text
Per claim:
₹10 lakh

Aggregate:
₹50 lakh
```

These are different dimensions.

The evaluator must preserve:

```text
per_claim = ₹10 lakh
aggregate = ₹50 lakh
```

It must not compare `₹10 lakh` directly against the Company Standard for an aggregate cap.

---

## 45C.6 Per-event vs aggregate

Same principle:

```text
Per event:
6 months

Aggregate:
12 months
```

Different scopes → not automatically conflicting.

The evaluator must identify the scope before comparison.

---

## 45C.7 Different monetary bases

Example:

```text
Customer:
Liability limited to fees paid in previous 12 months.

Company Standard:
6 months of fees.
```

Do not automatically assume they are equivalent.

The evaluator must preserve:

```text
value = 12
unit = months
basis = fees_paid_previous_12_months
```

If deterministic normalization cannot establish equivalence:

```text
UNABLE_TO_EVALUATE
```

rather than guessing.

---

## 45C.8 Fixed monetary amount vs fee-based cap

Example:

```text
Customer:
₹1 crore

Company Standard:
6 months of fees
```

Without the necessary contractual financial data, LegalMind cannot safely convert one into the other.

Result:

```text
UNABLE_TO_EVALUATE
```

not:

```text
DEVIATION
```

unless the applicable comparison rule explicitly supports that comparison.

---

## 45C.9 Percentage-based cap

Example:

```text
Liability shall not exceed 100% of annual contract value.
```

Preserve:

```text
value = 100
unit = PERCENTAGE
basis = CONTRACT_VALUE
```

Do not convert it into a monetary value unless the required contract data and deterministic conversion rule exist.

---

## 45C.10 Cross-reference

Example:

> Liability shall be subject to the limitations set out in Section 14.

Section 14:

> Aggregate liability shall not exceed 6 months.

If deterministic resolution succeeds:

```text
Section 8
   ↓
Section 14
   ↓
6 months
```

Evaluate normally.

If the referenced section cannot be safely resolved:

```text
UNABLE_TO_EVALUATE
```

or the applicable unresolved state.

The engine must not invent what Section 14 contains. Cross-reference preservation is already required by the specification.

---

## 45C.11 Conflicting cross-references

Example:

```text
Section 8 → Section 14

Schedule B → Section 18
```

Section 14:

```text
6 months
```

Section 18:

```text
Unlimited
```

If both appear applicable to the same liability scope:

```text
CONFLICT
```

Both chains must remain traceable.

---

## 45C.12 Negative wording

Example:

> Liability shall **not** be limited.

The presence of:

```text
liability
limited
```

must not cause a false positive liability-cap extraction.

Result:

```text
cap_status = UNLIMITED
```

if the wording deterministically establishes unlimited liability.

The specification explicitly requires negative/exclusion patterns for this reason.

---

## 45C.13 Ambiguous wording

Example:

> The parties may agree to appropriate limitations on liability.

This does not establish an actual cap.

Do not extract:

```text
cap = UNKNOWN → assume 6
```

Instead:

```text
AMBIGUOUS
```

or:

```text
UNABLE_TO_EVALUATE
```

depending on where the uncertainty occurs.

---

## 45C.14 Missing cap but liability clause exists

Example:

> Each party shall be liable for losses arising from its breach.

A liability provision exists, but there is no identifiable cap.

If `LIABILITY-001` requires a cap:

```text
MISSING
```

This is different from:

```text
No liability-related clause exists.
```

The evidence showing the liability provision should still be retained.

---

## 45C.15 Liability completely absent

If no qualifying liability provision can be mapped after deterministic processing:

```text
MISSING
```

provided the Requirement is required.

Again, do not manufacture:

```text
UNLIMITED
```

from absence.

---

## 45C.16 Multiple equivalent clauses

Example:

```text
Section 8:
Liability = 6 months

Schedule B:
"Subject to Section 8."
```

This is not a conflict.

The schedule merely references the existing provision.

The evaluator should avoid generating duplicate Findings.

---

## 45C.17 Same cap repeated

Example:

```text
Section 8:
6 months

Section 20:
6 months
```

If both are materially identical and applicable:

```text
MATCH
```

with both evidence references retained.

No duplicate legal issue should be created merely because the provision appears twice.

---

## 45C.18 OCR / extraction corruption

Example source:

```text
"Liability shall not exceed 6 m0nths"
```

If deterministic normalization can safely resolve the OCR error:

```text
6 months
```

continue.

If the value could be:

```text
6 months
```

or:

```text
8 months
```

and the system cannot safely determine which:

```text
UNABLE_TO_EVALUATE
```

The engine must fail closed.

---

## 45C.19 Missing unit

Example:

> Liability shall not exceed 6.

The number alone is insufficient.

Do not assume:

```text
6 months
```

or:

```text
₹6
```

Result:

```text
UNABLE_TO_EVALUATE
```

unless surrounding deterministic evidence establishes the unit.

---

## 45C.20 Missing scope

Example:

> Liability shall not exceed 6 months.

If the evaluator cannot determine whether this is:

```text
aggregate
per claim
per event
```

and scope is necessary for the applicable comparison:

```text
UNABLE_TO_EVALUATE
```

Do not invent `aggregate`.

---

# 45C.21 Edge-case decision matrix

| Situation                                             | Result                                         |
| ----------------------------------------------------- | ---------------------------------------------- |
| 6-month aggregate cap                                 | `MATCH`                                        |
| 12-month aggregate cap                                | `DEVIATION` + `ACCEPTABLE`                     |
| 24-month aggregate cap                                | `DEVIATION` + `APPROVAL_REQUIRED`              |
| Unlimited general liability                           | `DEVIATION` + `UNACCEPTABLE`                   |
| Required cap absent                                   | `MISSING`                                      |
| Same-scope contradictory caps                         | `CONFLICT`                                     |
| Different scopes                                      | Evaluate separately                            |
| General cap + carve-out                               | Evaluate scope/exception separately            |
| Cross-reference safely resolved                       | Evaluate referenced provision                  |
| Cross-reference cannot be resolved                    | `UNABLE_TO_EVALUATE`                           |
| Missing unit                                          | `UNABLE_TO_EVALUATE`                           |
| Missing necessary scope                               | `UNABLE_TO_EVALUATE`                           |
| Ambiguous wording                                     | `AMBIGUOUS` / appropriate unresolved state     |
| OCR makes value unreliable                            | `UNABLE_TO_EVALUATE`                           |
| Duplicate equivalent provision                        | Single logical result + multiple evidence refs |
| Fixed amount vs fee-based cap without conversion data | `UNABLE_TO_EVALUATE`                           |

---

# 45C.22 Hard rule — no silent precedence

This is one of the most important edge-case rules.

If two provisions conflict:

```text
6 months
vs
Unlimited
```

LegalMind must **not** use:

```text
first occurrence wins
highest score wins
latest occurrence wins
main body always wins
schedule always wins
```

unless an explicit deterministic contractual rule or configured precedence rule establishes that result.

Otherwise:

```text
CONFLICT
```

This follows the master specification's requirement that conflicting provisions be explicitly detected rather than silently choosing one.

---

# 45C.23 Hard rule — no conversion without evidence

LegalMind must never silently convert:

```text
₹1 crore
```

into:

```text
6 months
```

or:

```text
100% annual contract value
```

into:

```text
12 months
```

unless the required deterministic conversion inputs and rule exist.

Otherwise:

```text
UNABLE_TO_EVALUATE
```

---

# 45C.24 Hard rule — scope first

For every liability provision:

```text
CAP
 ↓
UNIT
 ↓
BASIS
 ↓
SCOPE
 ↓
EXCEPTIONS
 ↓
COMPARISON
```

The system must understand **what the number applies to** before treating the number as the legal position.

---

# 45C.25 Hard rule — evidence survives every branch

Whether the result is:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

the relevant evidence remains attached.

Therefore even a failed evaluation can be audited:

```text
Finding
 ↓
Evaluation
 ↓
Fact
 ↓
Evidence
 ↓
Document Version
```

This is consistent with the master specification's evidence-first architecture.

---

# 45C.26 Proposed lock

**Status: 🔒 LOCKED.** Amendments A-1 – A-4 were resolved through Amendment Batch AB-1.

I recommend locking Step 45C with these rules:

1. Multiple liability provisions are supported.
2. Different scopes are not automatically conflicts.
3. Same-scope contradictory provisions produce `CONFLICT` unless deterministic precedence resolves them.
4. Per-claim, per-event, aggregate and category-specific caps remain distinct.
5. General caps and carve-outs remain separately represented.
6. Unlimited carve-outs apply only to their defined scope.
7. Monetary, fee-based, percentage and other bases are not silently converted.
8. Cross-references are resolved only when deterministic.
9. Unresolved cross-references never produce guessed legal conclusions.
10. Negative wording is explicitly handled.
11. Absence of a cap is not automatically equivalent to unlimited liability.
12. Missing units or necessary scope can produce `UNABLE_TO_EVALUATE`.
13. Duplicate equivalent provisions do not create duplicate Findings.
14. OCR/extraction uncertainty must fail closed.
15. No arbitrary precedence rule such as "first clause wins" is permitted.
16. Every edge-case result retains its supporting evidence.
17. Edge cases must be represented in the golden test corpus before implementation is considered complete.

### Current status

```text
Steps 1–44       🔒 LOCKED
Step 45A         🔒 LOCKED
Step 45B         🔒 LOCKED
Step 45C         ⏳ REVIEW
```

**Next after 45C:** **Step 45D — Liability Golden Test Cases.**
That will turn these rules into concrete input → expected output tests, which is the final validation layer before we lock the complete `LIABILITY-001` evaluator and move to the next Requirement.
