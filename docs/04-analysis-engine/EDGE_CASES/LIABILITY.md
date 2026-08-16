Source: all_lock.md lines 11797-12481 (Step 45A). Canonical source: all_lock.md (Step 44 / Step 45A).

# Step 45A — LIABILITY-001

Cross-reference: see ../ANALYSIS_ENGINE.md for the Step 44 layered engine architecture this evaluator is built on. See ../FACT_EXTRACTION.md for Layer 5/6 fact extraction (the liability worked examples there are the same canonical examples formalized here). See ../CONFLICT_DETECTION.md for CONFLICT/AMBIGUOUS/MISSING/UNABLE_TO_EVALUATE definitions. See ../RULE_ENGINE.md for evaluator architecture and the rule engine.

I reviewed the existing specification specifically for the **Limitation of Liability evaluator**, and there is an important point before we lock anything:

The master specification already gives us several authoritative liability decisions—especially `6 months` as the Company Standard, `≤12 months` as acceptable, `>12 months` as approval-required, and `Unlimited` as unacceptable.

So we should **not invent a new liability model**. Step 45 should formalize what is already established.

---

## 1. Requirement identity

```text
Requirement ID:
LIABILITY-001

Name:
Limitation of Liability

Document Type:
MSA

Category:
Liability

Required:
YES

Evaluator:
Liability-specific deterministic evaluator
```

The Requirement is the evaluation unit. The evaluator is responsible for extracting and evaluating the structured liability facts. The existing specification explicitly says fact extraction should be Requirement-specific.

---

## 2. What the evaluator must determine

The evaluator should answer these questions **in order**:

```text
1. Is there a liability provision?
        ↓
2. Is there an identifiable liability cap?
        ↓
3. What is the cap?
        ↓
4. What unit is the cap expressed in?
        ↓
5. What is the scope of the cap?
        ↓
6. Are there exceptions / carve-outs?
        ↓
7. Are there multiple liability provisions?
        ↓
8. Do those provisions conflict?
        ↓
9. Can the provision be reliably evaluated?
        ↓
10. Compare against Company Standard
        ↓
11. Apply configured Legal Rule
```

This keeps **extraction → evaluation → Finding → Legal Decision** separate.

---

## 3. Structured liability fact

For the basic case:

> "The aggregate liability of either party shall not exceed six months of fees paid under this Agreement."

The evaluator extracts:

```text
{
  concept: "liability_cap",
  cap_exists: true,
  value: 6,
  unit: "months",
  scope: "aggregate"
}
```

This exact pattern is already established in the specification.

But I recommend we expand the internal representation slightly:

```text
LiabilityFact
├── cap_exists
├── cap_type
├── cap_value
├── cap_unit
├── cap_basis
├── scope
├── exceptions
├── evidence_refs
└── extraction_diagnostics
```

### Important

This does **not** mean every field must be populated.

If the contract does not specify a basis, we preserve:

```text
cap_basis = UNKNOWN
```

rather than guessing.

---

## 4. Cap type

We should distinguish at least:

```text
FINITE
UNLIMITED
ABSENT
UNKNOWN
```

Example:

### Finite

```text
6 months
```

→ `FINITE`

### Unlimited

> "Neither party's liability shall be subject to any limitation."

→ `UNLIMITED`

The specification explicitly uses Unlimited as a configured Legal Rule category.

### No identifiable provision

→ `ABSENT`

This can contribute to:

```text
MISSING
```

### Evidence exists but cannot be reliably interpreted

→ `UNKNOWN`

This can contribute to:

```text
UNABLE_TO_EVALUATE
```

---

## 5. Units

The evaluator must preserve the original unit.

Examples:

```text
6 months
12 months
₹10 crore
100% of fees
fees paid in previous 12 months
```

Do **not** automatically convert different bases into a common numerical value unless a deterministic conversion rule has explicitly been configured.

For example:

```text
6 months of fees
```

is not automatically equivalent to:

```text
₹X
```

without the necessary contractual data.

So:

```text
value = 6
unit = months
basis = fees_paid
```

is safer than attempting to calculate a monetary amount.

---

## 6. Scope

This is critical.

A liability provision might apply to:

```text
Aggregate liability
Per claim
Per event
Each party
One party only
Specific category of liability
```

Therefore:

```text
scope = aggregate
```

must not be silently generalized to:

```text
all liability
```

The specification already says scope and carve-outs need to remain represented rather than flattening the clause to a single number.

---

## 7. Carve-outs

Consider:

> "Aggregate liability shall not exceed six months of fees, except for fraud, wilful misconduct and confidentiality breaches."

The structured representation should preserve:

```text
general_cap:
    value: 6
    unit: months

exceptions:
    - fraud
    - wilful misconduct
    - confidentiality breach
```

The master specification explicitly requires this kind of scope/carve-out preservation.

### Critical rule

The evaluator must **not** automatically conclude:

```text
6 months = fully compliant
```

without considering whether the Requirement's configured comparison criteria address those exceptions.

---

## 8. Company Standard

The authoritative existing standard is:

```text
Preferred:
6 months
```

This is already established in the specification.

Therefore:

```text
Customer = 6 months
Company Standard = 6 months
```

produces:

```text
Finding:
MATCH
```

---

## 9. Customer = 12 months

```text
Customer:
12 months

Company Standard:
6 months
```

Comparison:

```text
12 != 6
```

Therefore:

```text
Finding:
DEVIATION
```

Then the Legal Rule is evaluated:

```text
12 <= 12
```

Therefore:

```text
Rule Outcome:
ACCEPTABLE
```

This is explicitly established in the master specification.

And importantly:

```text
DEVIATION
+
ACCEPTABLE
```

does **not** automatically create a Legal Decision.

---

## 10. Customer = 24 months

```text
Customer:
24 months

Company Standard:
6 months
```

Therefore:

```text
Finding:
DEVIATION
```

Then:

```text
24 > 12
```

Therefore:

```text
Rule Outcome:
APPROVAL_REQUIRED
```

The engine stops there.

It does **not** automatically approve or reject the contract.

Legal Decision remains a separate authorized workflow.

---

## 11. Customer = Unlimited

```text
Customer:
UNLIMITED

Company Standard:
6 months

Legal Rule:
UNLIMITED = UNACCEPTABLE
```

Result:

```text
Finding:
DEVIATION

Rule Outcome:
UNACCEPTABLE
```

Again, the Legal Decision remains separate.

---

## 12. Missing liability cap

Suppose the Requirement is:

```text
LIABILITY-001
Required = YES
```

but no qualifying limitation provision can be identified.

Then:

```text
Finding:
MISSING
```

provided the system has sufficient evidence to establish that the provision is genuinely absent.

We must distinguish:

```text
No provision found
```

from:

```text
Provision exists but extraction failed
```

The second case should not be incorrectly classified as `MISSING`; it may be:

```text
UNABLE_TO_EVALUATE
```

The specification explicitly requires this fail-closed behavior.

---

## 13. Ambiguous liability provision

Example:

```text
Section 8:
6 months

Schedule B:
12 months
```

If deterministic rules cannot establish which provision governs:

```text
Finding:
AMBIGUOUS
```

or, depending on the exact stage where the uncertainty arises:

```text
UNRESOLVED
/
UNABLE_TO_EVALUATE
```

The engine must **not** simply select 6 because it appears first, or 12 because it has a stronger keyword score.

The specification explicitly says multiple contradictory provisions must trigger conflict handling rather than silent selection.

---

## 14. Conflict case

Example:

```text
Section 8.2
Aggregate liability = 6 months

Schedule B
Liability = unlimited
```

The result should preserve:

```text
Evidence A
    ↓
6 months

Evidence B
    ↓
Unlimited
```

and produce:

```text
Finding:
CONFLICT
```

rather than:

```text
Finding:
DEVIATION
Actual:
6 months
```

because that would discard material evidence.

---

## 15. Negative patterns

This is particularly important for liability.

Example:

> "Liability shall not be limited in respect of fraud."

This contains words associated with limitation of liability but is actually describing an **exception to the limitation**.

Therefore the extractor/mapping configuration needs:

```text
Positive patterns
Negative patterns
Exception patterns
Scope patterns
```

The master specification explicitly requires negative patterns and carve-outs.

---

## 16. Cross-reference

Example:

> "The limitation set forth in Section 8 shall not apply to the obligations described in Section 14."

The evaluator should preserve:

```text
8
 ↓
references
 ↓
14
```

Then downstream evaluation can inspect Section 14.

We should **not attempt to build general legal reasoning here**. The requirement is simply:

> preserve deterministic cross-reference relationships where they can be safely resolved.

That is already part of the locked architecture.

---

## 17. Final liability evaluation matrix

| Customer provision                            | Finding                    | Rule outcome        |
| --------------------------------------------- | --------------------------- | -------------------- |
| 6 months                                      | `MATCH`                    | —                    |
| 12 months                                     | `DEVIATION`                | `ACCEPTABLE`         |
| 24 months                                     | `DEVIATION`                | `APPROVAL_REQUIRED`  |
| Unlimited                                     | `DEVIATION`                | `UNACCEPTABLE`       |
| No required provision                         | `MISSING`                   | —                    |
| Contradictory provisions                      | `CONFLICT`                 | —                    |
| Cannot determine intended provision           | `AMBIGUOUS` / `UNRESOLVED`  | —                    |
| Evidence insufficient for reliable evaluation | `UNABLE_TO_EVALUATE`        | —                    |

The exact Finding classifications have some historical evolution in the document, including an earlier five-type model and the later expanded evaluation model. Since Step 44 and the later evaluator sections explicitly use the expanded classifications, **Step 45 should follow the later locked architecture rather than reintroducing the older five-type-only model.**

---

## 18. Most important separation

The final Liability pipeline should be:

```text
CUSTOMER CONTRACT
       ↓
Evidence
       ↓
LIABILITY-001 Mapping
       ↓
Liability Fact Extraction
       ↓
Structured Liability Facts
       ↓
Company Standard Comparison
       ↓
Legal Rule Evaluation
       ↓
Finding
       ↓
Evidence + Explanation
       ↓
Review Workflow
       ↓
Authorized Legal Decision
```

Not:

```text
Contract
 ↓
AI/heuristic
 ↓
"High Risk"
 ↓
Reject
```

That would violate the entire V1 architecture.

---

## 19. Proposed Step 45A lock

Status: LOCKED (proposed / ready to lock — see "Current Status / Next Step" below)

I would lock the following:

### 🔒 LIABILITY-001 — LOCKED

1. `LIABILITY-001` is the canonical Limitation of Liability Requirement.
2. It is a required MSA Requirement unless configuration explicitly changes its applicability.
3. Liability extraction is Requirement-specific and deterministic.
4. The evaluator identifies whether a finite cap, unlimited liability, absent provision, or indeterminate provision exists.
5. The evaluator preserves value, unit, basis, scope, and exceptions/carve-outs where deterministically extractable.
6. Original evidence remains attached to every extracted fact.
7. The Company Standard is **6 months**.
8. `6 months` → `MATCH`.
9. `12 months` → `DEVIATION` + configured `ACCEPTABLE` rule outcome.
10. `>12 months` → `DEVIATION` + configured `APPROVAL_REQUIRED` rule outcome.
11. `UNLIMITED` → `DEVIATION` + configured `UNACCEPTABLE` rule outcome.
12. Absence of a required qualifying provision may produce `MISSING`.
13. Insufficient extraction/evidence must produce `UNABLE_TO_EVALUATE`, not a guessed result.
14. Multiple contradictory liability provisions must be preserved and evaluated as `CONFLICT` where incompatibility is established.
15. Ambiguous provisions must not be silently resolved.
16. Carve-outs and exceptions must not be discarded.
17. Cross-references must be preserved and resolved only where deterministic and safe.
18. The evaluator does not make a Legal Decision.
19. Finding classification and Legal Rule outcome remain separate.
20. All evaluation inputs and applicable configuration versions must be retained for reproducibility.
21. No LLM, RAG, embeddings, vector search, or semantic AI is introduced into this evaluator.

### Status

```text
Steps 1–44
🔒 LOCKED

Step 45
⏳ IN PROGRESS

Step 45A — LIABILITY-001
🔒 READY TO LOCK
```

---

## Current Status / Next Step

Step 45A is now **locked**. Step 45B — the evaluator data contract/schema for `LIABILITY-001` — has been drafted and is **in review** (proposed lock, not yet locked). It is documented in [LIABILITY_EVALUATOR_CONTRACT.md](LIABILITY_EVALUATOR_CONTRACT.md).

Current position as recorded in all_lock.md:

```text
Steps 1–44       🔒 LOCKED
Step 45A         🔒 LOCKED
Step 45B         ⏳ REVIEW
```

**I recommend locking 45B after one final check, then moving to 45C — Liability Edge Cases.** That is where we test whether this contract survives the difficult real-world cases: multiple caps, carve-outs, per-claim vs aggregate caps, different monetary bases, cross-references, conflicting schedules, and malformed/ambiguous clauses.
