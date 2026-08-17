# Reconciliation Pass 6 — 45D blocker resolution

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a conclusion was reached, and its status lines describe the state **at the time of writing**, which has since changed. A conclusion is authoritative only where it appears in [LOCKED_DECISIONS.md](../../00-project/LOCKED_DECISIONS.md) and `all_lock.md`. Do not implement from this file.

**Status: ⏳ RESOLUTIONS — 45D NOT LOCKED.** `all_lock.md` unmodified (13,941 lines, md5 `66591e62`).

Prepared 2026-08-17. Working method: reuse established analysis; targeted regression checks only. Two locked-schema reads were performed (42.7, 42.8); everything else reuses Passes 2–5.

Related: [PRESENCE_EVALUATOR.md](PRESENCE_EVALUATOR.md) · [../EVALUATOR_EDGE_CASES.md](../EVALUATOR_EDGE_CASES.md) · [RECONCILIATION_PASS_5.md](RECONCILIATION_PASS_5.md) · [V1_SCOPE_AUDIT.md](V1_SCOPE_AUDIT.md)

---

# 1. N-36 — Composite Requirements · **RESOLVED (Option C)**

## Targeted check

```text
42.7  requirement_versions.evaluator_type  EVALUATOR_TYPE NOT NULL    ← singular
```

**A Requirement version has exactly one evaluator type.** This is locked. Option A (two evaluator types under one Requirement) is therefore not available without amending 42.7, and Option B (a composite evaluator) would require a new evaluator type — which the working principles rule out as convenience-driven.

## Resolution — Option C: separate Requirements over the same clause

Locked **Step 28 r1** already provides the mechanism: *"One clause may map to multiple Requirements."*

A presence condition and a value condition are **two Requirements**, each with its own evaluator type, Company Standard, Legal Rule and Finding, both mapping to the same clause.

```text
Clause 12.3  ──mapped──▶  Requirement X (PRESENCE)         → Finding X
             └─mapped──▶  Requirement Y (NUMERIC_COMPARISON) → Finding Y
```

## Why this is the right model

| Criterion | Outcome |
|---|---|
| Deterministic evaluation | ✅ Each evaluator does one thing |
| Explainability (44.33) | ✅ Two complete, independent `Evidence → Fact → Standard → Rule → Result` chains |
| Evidence traceability | ✅ Same evidence referenced by both, via `evaluation_evidence` |
| Evaluator separation | ✅ No composite semantics anywhere |
| Minimal duplication | ✅ No new type, no new table, no amendment |
| Extensibility | ✅ Any number of conditions over one clause |
| API / database | ✅ Two ordinary Findings; no special case |

## The observation that makes composites largely unnecessary

**A value-type Requirement already subsumes presence.** Locked 45C.15: absence yields `MISSING`. So a `NUMERIC_COMPARISON` Requirement whose provision is absent already reports `MISSING` — configuring a separate presence Requirement alongside it adds a second `MISSING` and no information.

Presence-type Requirements earn their place where the organization requires *only* that a provision exist, with no value criterion. Pairing both over one clause is possible but rarely useful.

**Known limitation, accepted:** if both are configured and the clause is absent, two `MISSING` Findings result. Inter-Requirement dependency is not in the locked model, and inventing one would be disproportionate. This is a configuration choice, not an engine defect.

**No amendment required.**

---

# 2. AM-18 — Company Standard kind · **REJECTED as redundant**

## Targeted check

```text
42.8  company_standard_versions
      configuration  JSONB NOT NULL
      "The JSONB contains evaluator-specific values."
      Example: { "unit": "months", "preferred": 6 }
```

**The distinction is already representable twice over:**

1. `requirement_versions.evaluator_type` (locked, `NOT NULL`) already determines how the Standard is interpreted. If the type is `PRESENCE`, the Standard is a presence standard. Adding `standard_kind` would duplicate it — the same two-sources-of-truth defect rejected in J-2 (`rule_outcome`) and N-1 (`is_current`).
2. `company_standard_versions.configuration` is a JSONB of **evaluator-specific values**, explicitly sanctioned by 42.1 r10 for "genuinely variable configuration." A presence standard is simply a different payload:

```text
VALUE standard      { "preferred": 6, "unit": "months", "scope": "AGGREGATE" }
PRESENCE standard   { "expected_presence": "PRESENT" }
```

**AM-18 is withdrawn. No amendment to 42.8.**

## Consequential simplification — A-2 is not a schema amendment either

A-2 proposed adding `scope` to the Company Standard. Under 42.8 it is a JSONB key, not a column. **A-2 reduces to a logical-contract change in 45B**, consistent with locked 45B.28 item 20 ("the logical contract is authoritative; the physical PostgreSQL representation can be finalized during schema implementation").

Earlier passes modelled `company_standard` as columns (`preferred_value`, `preferred_unit`); that was the *logical* 45B contract, not the locked physical schema. Corrected here.

---

# 3. N-37 — Zero evidence rows · **RESOLVED**

A junction table imposes no minimum cardinality. The resolution is to **add no constraint**:

```text
evaluation_evidence
    evaluation_id      UUID FK → evaluations.id
    evidence_id        UUID FK → document_evidence.id
    relationship_type  EVIDENCE_RELATIONSHIP_TYPE NOT NULL
    PRIMARY KEY(evaluation_id, evidence_id)

No minimum-row constraint. Zero rows is a valid state.
```

**API:** `evidence_refs` is always present as an array and may be empty. **Never null** — an empty array states "no evidence exists"; null would be arbitrary NULL semantics (45B.26).

**Invariant** (service-enforced; spans `evaluations.classification` and a junction row count, so not expressible as a simple constraint — 42.21's sanctioned pattern):

> Non-empty evidence is required for `MATCH`, `DEVIATION`, `CONFLICT` and `AMBIGUOUS`. Empty is permitted **only** for `MISSING` arising from established absence. No synthetic evidence is ever created.

Enforced by service validation plus golden case **PE-2**.

---

# 4. N-18 / N-28 / N-29 — Final evaluator vocabulary · **RESOLVED**

## Distinct-responsibility test

| Candidate | Comparison semantics | Distinct? |
|---|---|---|
| `NUMERIC_COMPARISON` | Ordinal comparison of a magnitude against thresholds | ✅ |
| `RANGE_COMPARISON` | Magnitude against two thresholds | ❌ — `LIABILITY-001` already uses `acceptable_max` **and** `approval_required_above`; `NUMERIC_COMPARISON` is already multi-threshold |
| `ALLOWED_VALUES` | Set membership | ✅ (no V1 occupant) |
| `EXACT_MATCH` | Set membership where \|set\| = 1 | ❌ — a configuration of `ALLOWED_VALUES` |
| `BOOLEAN_PRESENT` | Existence against an expectation | ✅ |
| `BOOLEAN_ABSENT` | Existence, inverted | ❌ — a configuration parameter, not a distinct algorithm |

**N-28 resolved:** `EXACT_MATCH` merged into `ALLOWED_VALUES`.
**N-29 resolved:** `RANGE_COMPARISON` merged into `NUMERIC_COMPARISON`.
`BOOLEAN_ABSENT` merged into a parameterized presence type. Three algorithms remain: **ordinal, set-membership, existence.**

## The inert-vocabulary problem

`ALLOWED_VALUES` has **no V1 occupant** — Governing Law is illustrative only (N-24b). Including it would repeat the anti-pattern already rejected as X-8 and C-EXT-11 (a value declared in an enum that gates nothing).

Enum values are additive and cheap to add later under Step 29's configuration versioning. Declaring an unused one now is not.

## Final proposed vocabulary — **2 values**

```text
EVALUATOR_TYPE

NUMERIC_COMPARISON   Ordinal comparison of an extracted magnitude
                     against one or more configured thresholds.
                     Occupant: LIABILITY-001.

PRESENCE             Comparison of provision existence against the
                     configured expectation.
                     Parameter: expected_presence = PRESENT | ABSENT
                     Occupant: presence-mode Requirements.
```

**Documented extension points (not enum members):** set-membership comparison; any further algorithm a future Requirement needs. Each is an additive enum value plus a tested comparison implementation.

**Renamed** `BOOLEAN_PRESENT` → `PRESENCE`, because the type now covers both expected-present and expected-absent through a configuration parameter. The vocabulary was never locked, so this is a naming choice, not an amendment.

---

# 5. N-12 / N-13 / N-14 / N-16 — Reproducibility · **RESOLVED, two amendments needed**

Reusing Pass 3 §8 rather than re-deriving.

| ID | Resolution | Amendment? |
|----|-----------|------------|
| **N-13** `evaluator_version` | Add `evaluations.evaluator_version VARCHAR NOT NULL`. Locked 45B.10 requires it; no column exists. Must be relational — it is the reproducibility key, queried when an evaluator changes | **AM-19 — amends 42.15** |
| **N-12** Legal Rule version | Add `evaluations.legal_rule_version_id UUID FK → legal_rule_versions.id NULL`. The existing `rule_version_id` targets `evaluation_rule_versions`, a **different** locked table. Nullable because Step 20 r4 permits a Requirement with no Legal Rule | **AM-20 — amends 42.15** |
| **N-14** `extraction_diagnostics` | **No amendment.** Diagnostics are variable free-form text, not a core relationship, so 42.1 r10 sanctions carrying them inside the existing `evaluations.result JSONB` alongside evaluator `diagnostics`. REC-07's persistence requirement is satisfied | None |
| **N-16** Company Standard version | **No amendment.** Uniquely derivable: `findings.requirement_version_id` + `reviews.configuration_snapshot_id` → `configuration_snapshot_items` pins the exact standard version used. 42.20's traceability path is satisfiable without a redundant column | None |

**Step 32's audit question 4 — "Which Legal Rule was used?" — becomes answerable under AM-20.**

## 45D.4.12 resolution

> **45D.4.12 — Reproducibility.** Every Evaluation retains its evaluator version, the applicable configuration versions, its extracted facts and its evidence. Evaluator version and Legal Rule version are persisted relationally; the Company Standard version is derived through the Review's configuration snapshot; extraction diagnostics are persisted with the evaluation result.

**Specified. Implementable on approval of AM-19 and AM-20.**

---

# 6. N-35 — Optional Requirement, no mapped provision · **RECOMMENDATION — escalated**

This one changes user-visible behavior, so it is escalated rather than decided. The analysis narrows it to a single defensible answer.

## Elimination from locked definitions

| Candidate | Locked text | Verdict |
|---|---|---|
| `MISSING` | **36.4**: "The Requirement is **expected**, but no qualifying provision is found." | ❌ An optional Requirement is by definition *not expected*. `MISSING` would misstate the organization's own position. Step 28 r5 also scopes `MISSING` to "A **required** Requirement" — the qualifier appears deliberate |
| `MATCH` | **36.2**: "Customer **provision** conforms to the Company Standard." | ❌ There is no provision. Recording `MATCH` would assert conformance that was never evaluated — the same error class as `RESOLVED ≠ MATCH` |
| A new classification | REC-01, REC-06, 42.14 | ❌ Amends the locked 7-value enum across three schema definitions and two reconciliation decisions. Disproportionate |
| **No Finding** | Step 28 r5 says a required Requirement "**may** produce" `MISSING` — permissive, and silent on optional | ✅ The only option that contradicts no locked definition |

## Recommendation — produce no Finding

An optional Requirement with no mapped provision produces **no Finding and no Evaluation**. Nothing was required, nothing was found, and nothing is asserted.

**Consequence to ratify:** Step 8's alignment report will not show a row for it. Locked Step 8 requires "which clauses were reviewed" — satisfied by **coverage reporting** (which Requirements were in the configuration snapshot and evaluated), which is a reporting concern alongside N-33's alignment calculation, not a Finding concern.

**EV-MIN is unaffected** — no Finding means no Evaluation to require.

---

# 7. Revised amendment set

Three amendments **withdrawn** this pass, two **added**.

| ID | Amendment | Status |
|----|-----------|--------|
| AM-1 | `legal_decisions.evaluation_id NOT NULL` + composite FK | Pending approval |
| AM-2 / AM-5 / AM-6 | Step 31 r17 / r4 / r16 restatements | Pending approval |
| AM-7 | Step 36.7 wording | Pending approval |
| AM-8′ | `evaluations` + `scope_key`, `scope_label`, `evaluation_kind`, `rule_outcome` | Pending approval |
| AM-12 – AM-14 | `legal_decisions.version_number` + `UNIQUE(evaluation_id, version_number)` | Pending approval |
| AM-15 | `justification NOT NULL` | Pending approval |
| AM-16 | Define `EVALUATOR_TYPE` (2 values) | Pending approval |
| **AM-19** | `evaluations.evaluator_version VARCHAR NOT NULL` | **NEW** |
| **AM-20** | `evaluations.legal_rule_version_id UUID FK NULL` | **NEW** |
| ~~AM-18~~ | Company Standard `standard_kind` | **WITHDRAWN — redundant** |
| ~~AM-21~~ | Company Standard version on `evaluations` | **WITHDRAWN — derivable** |
| ~~A-2 as schema change~~ | Company Standard `scope` | **WITHDRAWN — JSONB configuration** |

---

# 8. Targeted regression check

Only rules materially affected by this pass were re-checked.

| Change | Rules checked | Result |
|---|---|---|
| N-36 → separate Requirements | Step 28 r1, r2; 42.7 singular type; Step 27 r16 (multiple Findings per Review); 44.33 | ✅ No contradiction |
| AM-18 rejected | 42.7, 42.8, 42.1 r10, 45B.28 item 20 | ✅ Standard kind fully determined by `evaluator_type` + configuration JSONB |
| Vocabulary → 2 values | 36.11 ("not one universal comparison algorithm"), 36.12 (recommendation only), 42.7 | ✅ Two distinct algorithms satisfy 36.11 |
| N-37 zero evidence | 45B.18, 45C.14, 45C.15, EV-MIN, 45B.26 | ✅ Consistent |
| AM-19 / AM-20 | 45B.10, Step 32 q4, 42.9 vs 42.11, Step 20 r4, ENG-11 | ✅ Both gaps closed |
| N-35 no Finding | 36.2, 36.4, Step 28 r5, Step 8, EV-MIN, REC-01 | ✅ No contradiction; one reporting consequence |

**No new contradictions found.**
