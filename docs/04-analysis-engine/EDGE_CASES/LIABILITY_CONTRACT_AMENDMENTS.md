# A-1 – A-4 — Evaluator Contract Amendment Analysis

**Status: ⏳ PROPOSAL — NOT LOCKED. No locked decision has been modified.**

Prepared 2026-08-16 in response to the Step 45C review. Resolves A-4 first, then derives the minimum contract changes for A-1, A-2, A-3.

Related: [LIABILITY_EDGE_CASES.md](LIABILITY_EDGE_CASES.md) (45C, ⏳ REVIEW) · [LIABILITY_EVALUATOR_CONTRACT.md](LIABILITY_EVALUATOR_CONTRACT.md) (45B, 🔒 LOCKED) · [LIABILITY.md](LIABILITY.md) (45A, 🔒 LOCKED) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

---

# A. A-4 decision — evaluation result cardinality

## Proposal under evaluation

> One Requirement may produce multiple scoped Evaluation Results, but those Evaluation Results remain grouped under one Finding for that Requirement.

```text
Review
→ Finding
→ Requirement
→ multiple scoped Evaluation Results
→ Evidence
```

## Verdict: ✅ CORRECT — and already implied by locked Steps 40–42

This is not a new architectural choice. The locked database model **already** expresses exactly this shape.

| Locked decision | Text | Consequence |
|---|---|---|
| 41.19 / 42.15 | `evaluations` table carries `finding_id UUID FK → findings.id` | One Finding → **many** Evaluations is already locked |
| 41.19 | "Finding says *what did LegalMind conclude?* while Evaluation says *how did the deterministic evaluator reach that conclusion?*" | Finding is the conclusion; Evaluations are the working |
| 40.10 / 41.18 / 42.14 | `findings.classification` is a single `NOT NULL` column | **One classification per Finding** — locked, not a choice |
| 42.17 | `legal_decisions.finding_id` | Legal Decision attaches at **Finding** level — locked |
| 42.16 | `finding_evidence` supports Finding → multiple Evidence, incl. `CONFLICTING` | Multi-provision evidence already anticipated |
| Step 28 rule 2 | "One Requirement may be supported by multiple clauses" | Multiple provisions per Requirement is locked |
| 45C.16 / 45C.17 | "avoid generating duplicate Findings"; "No duplicate legal issue should be created merely because the provision appears twice" | Argues **against** Finding-per-scope |
| Step 36.14 | "Evaluation must preserve the calculation" | Each scope's calculation must survive → one Evaluation per scope |

**No locked decision is contradicted by the proposal.** Step 27 rule 16 ("Multiple independent findings may exist within one Review") is about independent Requirements and neither authorizes nor forbids multiple Findings per Requirement; the proposal resolves that silence in the direction the schema already points.

## Formal specification of A-4

**A-4.1** — For a given Review and a given Requirement Version, `LIABILITY-001` produces **exactly one Finding**.

**A-4.2** — That Finding carries **exactly one** `classification` (locked by 42.14).

**A-4.3** — The Finding groups **one or more Evaluation Results**, one per evaluated **scope**, where a scope is a general cap, a category cap, or a carve-out/exception.

**A-4.4** — Each Evaluation Result carries its own classification, rule outcome, expected/actual values, comparison, explanation and evidence references.

**A-4.5** — The Finding's single classification is a **deterministic roll-up** of its Evaluation Results' classifications (see A-4.7). The roll-up is a *summary*; the Evaluation Results remain the authoritative per-scope record.

**A-4.6** — Multiple provisions describing the **same** scope do not create multiple Evaluation Results; they create one Evaluation Result with multiple evidence references (45C.16, 45C.17), or `CONFLICT` where incompatible (45C.2).

**A-4.7** — ⚠ **REQUIRES APPROVAL — not derivable from locked text.** Proposed deterministic roll-up precedence, highest wins:

```text
1. UNABLE_TO_EVALUATE     ← fail-closed first: the result cannot be trusted
2. CONFLICT               ← established contradiction
3. AMBIGUOUS              ← interpretive uncertainty
4. UNRESOLVED             ← required information or action missing
5. MISSING                ← required provision absent
6. DEVIATION              ← present and differing
7. MATCH                  ← present and conforming
```

Rationale: consistent with the locked fail-closed philosophy (ENG-09, 45C.18, 45C.25) — a Finding must never read `MATCH` while any scope is unevaluable, conflicting, or absent. **This ordering is a specification decision, not a derivation. It must be explicitly approved.**

---

# B. Revised 45B contract proposal

Changes marked `←`. Everything unmarked is the locked 45B contract, unchanged.

```text
LIABILITY_EVALUATOR_INPUT

{
    requirement: { id, code, version_id },

    evidence: [
        { evidence_id, document_version_id,
          page_number, section_number, section_title }
    ],

    facts: {
        caps: [                              ← A-1 + A-3 (unified)
            {
                cap_kind,                    ← GENERAL | EXCEPTION
                scope,
                scope_label,                 ← only when scope = CATEGORY/EXCEPTION
                cap_status,
                cap_value,
                cap_unit,
                cap_basis,
                evidence_refs[]
            }
        ],
        extraction_status,
        extraction_diagnostics
    },

    company_standard: {
        version_id,
        preferred_value,
        preferred_unit,
        scope                                ← A-2
    },

    legal_rule: {
        version_id, acceptable_max, acceptable_max_unit,
        approval_required_above, unlimited_outcome, rule_configuration
    },

    evaluator_version
}
```

```text
LIABILITY_EVALUATOR_OUTPUT

{
    evaluations: [                           ← A-4: was a single EvaluationResult
        {
            scope,                           ← A-4
            scope_label,                     ← A-4
            cap_kind,                        ← A-4
            classification,
            rule_outcome,
            expected_value,
            actual_value,
            comparison,
            evaluated_facts,
            evidence_refs[],
            explanation,
            diagnostics
        }
    ],
    finding_classification,                  ← A-4.5 roll-up
    evaluator_version
}
```

**Design note:** `caps[]` unifies A-1 (multiple caps) and A-3 (structured exceptions) into **one** repeating structure discriminated by `cap_kind`, rather than two parallel structures. 45C.4 establishes that an exception carries its own cap position — which makes an exception structurally a scoped cap. One concept, not two. No field is introduced that a 45C rule does not require.

---

# C. A-1 amendment — multiple caps

**Required by:** 45C.1, 45C.5, 45C.6, 45C.26 rules 1 & 4.

`facts.caps[]` replaces the singular `cap_status` / `cap_value` / `cap_unit` / `cap_basis` / `scope`. The field *names and value sets* are unchanged from locked 45B — only their cardinality changes.

| Field | Specification |
|---|---|
| **`caps[]`** | **Purpose:** hold every distinct liability position in the contract. **Type:** array of objects. **Required:** yes; may be empty when no cap is found (→ `MISSING`, 45C.15). **Relationship:** replaces the five singular cap fields. **Evidence:** each element carries its own `evidence_refs[]`. **Persisted:** yes, one row per element (see F). **Affects classification:** yes, per scope. **Affects rule outcome:** yes, per scope. |
| **`caps[].scope`** | **Purpose:** what the cap applies to — must be known before the number means anything (45C.24). **Type:** enum. **Required:** yes; `UNKNOWN` when undeterminable → `UNABLE_TO_EVALUATE` where scope is necessary (45C.20). **Allowed:** `AGGREGATE`, `PER_CLAIM`, `PER_EVENT`, `CATEGORY`, `UNKNOWN` — drawn from 45A §6's locked scope list. **Affects classification:** yes — determines comparability. **Affects rule outcome:** yes. |
| **`caps[].scope_label`** | **Purpose:** name the category or exception (`service credits`, `confidentiality breach`). **Type:** string. **Required:** only when `scope = CATEGORY` or `cap_kind = EXCEPTION`. **Affects classification:** no. **Affects rule outcome:** no. Carried for evidence, explanation and reviewer display. |
| `caps[].cap_status` / `cap_value` / `cap_unit` / `cap_basis` | Unchanged from locked 45B.4, now per cap. Same purposes, types, allowed values and nullability. |
| **`caps[].evidence_refs[]`** | **Purpose:** satisfy 45B.18 and 45C.25 per scope. **Type:** array of evidence ids. **Required:** yes, non-empty for any non-absent cap. **Persisted:** yes (see F — requires a new junction). |

**Locked rules preserved:** different scopes are not conflicts merely for differing (45C.1); same-scope contradictions produce `CONFLICT` with all evidence attached (45C.2, 45A §14); no cap is silently discarded (45A rule 16).

---

# D. A-2 amendment — company-standard scope

**Required by:** 45C.5, 45C.20, 45C.24.

| Field | Specification |
|---|---|
| **`company_standard.scope`** | **Purpose:** state what the Company Standard's 6 months applies to, so a customer cap can be matched scope-to-scope. Without it, 45C.5's prohibition on comparing a per-claim cap against an aggregate standard cannot be enforced. **Type:** enum, same value set as `caps[].scope`. **Required:** yes for any Requirement whose evaluation is scope-sensitive; `LIABILITY-001` is. **Allowed:** `AGGREGATE`, `PER_CLAIM`, `PER_EVENT`, `CATEGORY`. **Not** `UNKNOWN` — an unscoped standard is a configuration defect, not a runtime state. **Relationship:** compared against `caps[].scope`; mismatch means not comparable. **Evidence:** none — this is configuration, not extracted fact. **Persisted:** yes, on `company_standard_versions` (versioned configuration; a scope change creates a new version per Step 29). **Affects classification:** yes — scope mismatch drives `UNABLE_TO_EVALUATE`. **Affects rule outcome:** indirectly, by gating comparability. |

This is a single new field. No other change to the `company_standard` block.

---

# E. A-3 amendment — structured exceptions

**Required by:** 45C.4, 45C.26 rule 6.

**`exceptions[]` is removed** and absorbed into `caps[]` via `cap_kind`. Retaining a separate flat `exceptions[]` alongside a structured `caps[]` would create two sources of truth for the same concept.

| Field | Specification |
|---|---|
| **`caps[].cap_kind`** | **Purpose:** distinguish the general position from a carve-out, so an unlimited carve-out never generalizes to the whole provision (45C.4). **Type:** enum. **Required:** yes. **Allowed:** `GENERAL`, `EXCEPTION`. **Relationship:** an `EXCEPTION` element scopes to `scope_label`; a `GENERAL` element carries the headline position. **Evidence:** via `caps[].evidence_refs[]`. **Persisted:** yes. **Affects classification:** yes — evaluated separately per 45C.21. **Affects rule outcome:** yes, per exception. |

**Worked check against 45C.4** — *"capped at 6 months, except confidentiality breaches unlimited"*:

```text
caps: [
  { cap_kind: GENERAL,   scope: AGGREGATE, cap_status: FINITE,
    cap_value: 6, cap_unit: MONTHS, cap_basis: FEES_PAID, evidence_refs: [E1] },

  { cap_kind: EXCEPTION, scope: CATEGORY, scope_label: "confidentiality breach",
    cap_status: UNLIMITED, cap_value: null, evidence_refs: [E1] }
]
```

Produces two Evaluation Results — `MATCH` on the general aggregate cap, `DEVIATION` + `UNACCEPTABLE` on the carve-out — rolling up to a Finding classification of `DEVIATION`. The whole provision is never classified `UNLIMITED`, satisfying 45C.4.

**Backward-compatibility note:** 45A §7's illustrative `exceptions: [fraud, wilful misconduct]` remains expressible — each becomes an `EXCEPTION` cap with `cap_status = UNKNOWN` where the contract states no distinct position for it. No 45A example is invalidated.

---

# F. Database implications

**A-4 requires no schema change.** `evaluations.finding_id` (42.15) already provides Finding → many Evaluations.

### Change F-1 — `evaluations` gains scope columns *(amends locked 42.15)*

```text
evaluations
-----------
id, finding_id, evaluator_type, expected_value, actual_value,
operator, result, rule_version_id, created_at,
scope           SCOPE NOT NULL          ← new
scope_label     VARCHAR NULL            ← new
cap_kind        CAP_KIND NOT NULL       ← new
```

Relational columns, not JSONB — 42.1 rule 10 permits JSONB only for "genuinely variable configuration, not to hide core relationships," and scope is the discriminator the whole model turns on. `expected_value` / `actual_value` / `result` remain JSONB as locked.

### Change F-2 — new `evaluation_evidence` junction *(new table)*

**This is a genuine gap in the locked model.** `finding_evidence` (42.16) is keyed `(finding_id, evidence_id)` — there is **no way to attribute evidence to a specific scoped evaluation**. 45B.18 and 45C.25 require evidence to survive every branch; with multiple scopes, Finding-level attachment cannot say *which* evidence supports *which* scope.

```text
evaluation_evidence
-------------------
evaluation_id      UUID FK → evaluations.id
evidence_id        UUID FK → document_evidence.id
relationship_type  EVIDENCE_RELATIONSHIP_TYPE NOT NULL
PRIMARY KEY(evaluation_id, evidence_id)
```

Reuses the locked `PRIMARY` / `SUPPORTING` / `CONFLICTING` vocabulary. `finding_evidence` is **retained unchanged** — it remains the Finding-level roll-up and nothing about it is invalidated.

### Change F-3 — uniqueness constraint *(fills a locked-schema gap)*

A-4.1 requires one Finding per Requirement per Review. The locked `findings` table declares no such constraint:

```text
UNIQUE(review_id, requirement_version_id)
```

### Change F-4 — `rule_outcome` has no home *(open — see J)*

`rule_outcome` appears throughout 44.x and 45B but exists in **no** locked table. It is currently implicit inside `evaluations.result` JSONB. Given 42.1 rule 10 and that rule outcome drives review routing, it likely warrants a column — but this was never decided and is not proposed here.

### Unchanged

`findings` (single classification), `legal_decisions` (Finding-level), `finding_evidence`, `document_evidence`.

---

# G. API implications

Per 43.21's locked envelope, a Finding is returned with its evaluations nested — never as flat sibling findings, which would contradict A-4.1.

```text
GET /findings/{id}

{
  "id": "...",
  "requirement": { "code": "LIABILITY-001", "version_id": "..." },
  "classification": "DEVIATION",            // roll-up (A-4.5)
  "status": "...",
  "evaluations": [
    { "scope": "AGGREGATE", "cap_kind": "GENERAL",
      "classification": "MATCH", "rule_outcome": "NOT_APPLICABLE",
      "expected_value": {...}, "actual_value": {...},
      "evidence_refs": ["E1"], "explanation": "..." },

    { "scope": "CATEGORY", "scope_label": "confidentiality breach",
      "cap_kind": "EXCEPTION",
      "classification": "DEVIATION", "rule_outcome": "UNACCEPTABLE",
      "evidence_refs": ["E1"], "explanation": "..." }
  ],
  "evidence": [ ... ]                        // Finding-level roll-up
}
```

Constraints: endpoint naming stays unlocked (38.24); `rule_outcome` and thresholds are internal legal position and must be permission-filtered server-side (LEGAL-02, 38.21); the response never implies a Legal Decision (36.15, 45B.14).

---

# H. UI / reviewer implications

Step 31 rule 16 is the governing constraint:

> Before deciding, Legal must be shown the underlying evidence, Requirement, Company Standard, applicable Legal Rule, and Finding.

With multiple scopes there are multiple applicable Legal Rules, so **every scoped evaluation must be visible before a decision is recorded** — a collapsed summary row alone would not satisfy rule 16.

* One Finding row per Requirement, showing the rolled-up classification.
* Expanded: one row per scope — scope, cap, classification, rule outcome, evidence, explanation.
* A scope whose rule outcome is `APPROVAL_REQUIRED` or `UNACCEPTABLE` must be visually distinct; it must not be possible to resolve the Finding without having seen it (see J-3).
* Rule outcomes and thresholds are permission-gated (LEGAL-02).
* `RESOLVED ≠ MATCH` must remain evident in the display (Step 22, Step 30).

---

# I. Golden-test implications

Per locked ENG-12 and 45C.26 rule 17, every 45C case becomes a corpus fixture. Each fixture asserts **both** levels:

```text
fixture: 45C.4-unlimited-carve-out
  input:    contract excerpt + config versions
  expect_finding:
      classification: DEVIATION            ← roll-up
  expect_evaluations:                       ← exact set, order-independent
    - scope: AGGREGATE, cap_kind: GENERAL,
      classification: MATCH, rule_outcome: NOT_APPLICABLE
    - scope: CATEGORY, scope_label: "confidentiality breach",
      cap_kind: EXCEPTION,
      classification: DEVIATION, rule_outcome: UNACCEPTABLE
  expect_evidence: every evaluation has ≥1 evidence ref
```

Asserting only the rolled-up classification would let per-scope regressions pass undetected — the roll-up is lossy by design.

Required additions beyond the 45C list:

* **The negative-pattern matched pair** — *"Liability shall not be limited **in respect of fraud**"* (45A §15, a carve-out) versus *"Liability shall not be limited"* (45C.12, general `UNLIMITED`). Six words apart, opposite legal positions; the sharpest available test of the scope and negative-pattern machinery.
* A roll-up precedence fixture per ordered pair, once A-4.7 is approved.
* A fixture asserting that 45C.16/45C.17 duplicates produce **one** evaluation with two evidence refs, not two evaluations.

---

# J. Remaining contradictions and open decisions

**J-1 — Roll-up precedence is not derivable (A-4.7).** Requires explicit approval. Blocks the roll-up fixtures.

**J-2 — Finding-level rule outcome is undefined.** `rule_outcome` lives in no locked table (F-4). With multiple scopes, "does this Finding need Legal approval?" must be derived from the scoped outcomes — deterministically, per Step 36/44. The derivation rule is unspecified.

**J-3 — ⚠ Legal Decision granularity — the most consequential open item.** `legal_decisions.finding_id` (42.17) puts the decision at Finding level, and Step 31 rules 4, 9 and 17 speak of deciding "the Finding." But scopes can carry *different* rule outcomes — `NOT_APPLICABLE` on the general cap, `UNACCEPTABLE` on a carve-out. A single Finding-level `ACCEPT_DEVIATION` would then dispose of an unacceptable carve-out without ever naming it.

Two options, neither chosen here:

* **(a) Keep Finding-level decisions.** No schema change. Requires a compensating rule that a decision disposes of *all* scopes and that all scoped outcomes were displayed (H).
* **(b) Add `evaluation_id` to `legal_decisions`.** Permits per-scope decisions. **Amends locked 42.17** and expands Step 31's model.

This is a legal-authority question, not a technical one. It must be decided explicitly.

**J-4 — `FINDING_STATUS` is never defined.** Referenced at 42.14 as a NOT NULL enum; no locked text enumerates its values. Pre-existing gap, surfaced by this analysis.

**J-5 — `rule_configuration` shape still unspecified**, and 45C.2/45C.22 precedence resolution depends on it.

**J-6 — `AMBIGUOUS` vs `UNRESOLVED` boundary** remains soft (45C.13, 45C.21); EC-7 not fully closed.

**J-7 — Amendment count.** These proposals amend locked 42.15 (F-1), add a table (F-2), add a constraint (F-3), and amend locked 45B (B/C/D/E). All require approval under CLAUDE.md rule 6.

---

# K. Recommendation

## REVISE — do not lock

| Item | Recommendation |
|---|---|
| **A-4 core proposal** | **Approve.** Confirmed correct and already implied by locked 41.19/42.15/42.17. Formalize as A-4.1–A-4.6. |
| **A-4.7 roll-up precedence** | **Decide.** Not derivable; blocks 45D. |
| **A-1 / A-2 / A-3** | **Approve as drafted**, contingent on the 45B amendment being accepted. |
| **F-2 `evaluation_evidence`** | **Approve.** Without it, per-scope evidence attribution is impossible and 45C.25 cannot be satisfied. |
| **J-3 decision granularity** | **Decide before locking 45C.** Legal-authority question with real exposure. |
| **Step 45B** | **Do not re-lock** until amendments B–E are approved, then re-lock as a single revised contract. |
| **Step 45C** | **Do not lock** until J-1 and J-3 are resolved. |
| **Step 45D** | **Do not start.** Golden tests cannot state expected output while J-1 and J-2 are open. |

**Suggested order:** J-3 (legal authority) → A-4.7 (roll-up) → J-2 (derived outcome) → re-lock 45B with B–E → lock 45C → start 45D.

J-3 first because it is the only one carrying legal exposure rather than engineering cost, and because option (b) would change the shape of everything downstream.
