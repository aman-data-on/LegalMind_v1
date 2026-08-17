# `PRESENCE` — Presence-Mode Evaluator Specification

**Status: 🔒 LOCKED (2026-08-17, Step 45D).** Lock record in [`all_lock.md`](../../../all_lock.md) under "Step 45D — LOCK RECORD". No legal Requirement invented — this specifies a **generic evaluator**, not a legal area.

Prepared 2026-08-17 under approved **R-1** (a Company Standard may express presence) and **N-34** (evidence cardinality).

Related: [../EVALUATOR_EDGE_CASES.md](../EVALUATOR_EDGE_CASES.md) (45D) · [LIABILITY_EVALUATOR_CONTRACT.md](LIABILITY_EVALUATOR_CONTRACT.md) (45B 🔒) · [RECONCILIATION_PASS_5.md](RECONCILIATION_PASS_5.md) · [../REQUIREMENT_MAPPING.md](../REQUIREMENT_MAPPING.md) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

---

# P.1 Purpose and the one design constraint that matters

`PRESENCE` evaluates a Company Standard that requires a qualifying contractual provision to **exist**. It is generic — reusable by any configured Requirement — and carries no legal-domain content.

## The constraint: presence is established by Mapping, never by the evaluator

**The evaluator never reads clause text.** It consumes the **mapping state** produced by the locked mapping layer (Steps 28, 35) and nothing else.

```text
Document → Mapping layer (Steps 28, 35)  → mapping state → PRESENCE EVALUATOR
                  ↑                                              ↑
        patterns, keywords,                          consumes the mapping result
        negative terms live HERE                     reads no text, no patterns
```

This is the design decision that prevents the failure mode identified in **N-30**. An evaluator that scanned text for patterns would be a text-pattern evaluator by another name, would duplicate the locked mapping mechanism (35.4, 35.5, 35.10), and would collapse **ENG-03** (Mapping ≠ Evaluation).

**Presence is a mapping outcome. The evaluator's only job is to compare that outcome against the configured Standard.**

---

# P.2 Input contract

```text
PRESENCE_EVALUATOR_INPUT

{
    requirement: {
        id,
        code,
        version_id,
        applicability            ← REQUIRED | OPTIONAL  (45A §1 pattern)
    },

    mapping: {                   ← the ONLY source of presence
        mapping_state,           ← CONFIRMED | AMBIGUOUS | UNRESOLVED | NONE
        evidence_refs[]          ← evidence of the mapped provision, if any
    },

    company_standard: {
        version_id,
        configuration,           ← JSONB (42.8): { "expected_presence": "PRESENT" }
        scope_key
    },

    legal_rule: {                ← OPTIONAL — Step 20 r4
        version_id,
        rule_configuration
    },

    evaluator_version
}
```

## Field specification

| Field | Type | Card. | Req. | Allowed values | Evidence | Persisted | Failure behavior |
|---|---|---|---|---|---|---|---|
| `requirement.version_id` | id | 1 | Yes | — | — | `findings.requirement_version_id` | Cannot run |
| `requirement.applicability` | enum | 1 | Yes | `REQUIRED`, `OPTIONAL` | — | configuration | `OPTIONAL` + absent ⇒ no Finding (F-1) |
| `mapping.mapping_state` | enum | 1 | Yes | `CONFIRMED`, `AMBIGUOUS`, `UNRESOLVED`, `NONE` | — | see P.6 | Drives the outcome |
| `mapping.evidence_refs[]` | ids | 0..n | Yes (may be empty) | — | self | `evaluation_evidence` (AB-1.5) | Empty only when `NONE` |
| `company_standard.configuration` | JSONB | 1 | Yes | `{ "expected_presence": PRESENT \| ABSENT }` | — | `company_standard_versions.configuration` (42.8, locked) | Missing key ⇒ misconfiguration |
| `company_standard.scope_key` | string | 1 | Yes | member of the Requirement's declared scopes | — | `evaluations.scope_key` | See P.4 |
| `legal_rule` | object | 0..1 | **No** | — | — | versioned config | Absent ⇒ `rule_outcome = NOT_APPLICABLE` |
| `evaluator_version` | string | 1 | Yes | — | — | `evaluations.evaluator_version` (AM-19) | — |

**`mapping_state = NONE`** denotes established absence: the mapping layer completed and produced no mapping for this Requirement. It is distinct from `UNRESOLVED`, which means the mapping layer could not decide.

**No `extraction_status` / `extraction_diagnostics`.** Presence-mode performs **no fact extraction** — there is no value to extract. Carrying those fields would require inventing values for a stage that never ran, which locked **45B.26** (no arbitrary NULL semantics) forbids. This is a legitimate difference between evaluator contracts, permitted by locked **44.11** (fact extraction is Requirement-specific).

---

# P.3 Company Standard representation for presence Requirements

Under approved **R-1**, a Company Standard may express that a qualifying provision must exist. **This requires no schema amendment** — AM-18 was withdrawn as redundant, see [RECONCILIATION_PASS_6.md](RECONCILIATION_PASS_6.md) §2.

Locked **42.8** already provides the mechanism:

```text
company_standard_versions
    requirement_version_id  UUID FK
    configuration           JSONB NOT NULL   "contains evaluator-specific values"
```

The *kind* of Standard is already determined by locked `requirement_versions.evaluator_type` (42.7); its values live in the configuration JSONB:

```text
VALUE standard      { "preferred": 6, "unit": "months", "scope": "AGGREGATE" }
PRESENCE standard   { "expected_presence": "PRESENT" }
```

A separate `standard_kind` column would duplicate `evaluator_type` — the two-sources-of-truth defect already rejected in J-2 (`rule_outcome`) and N-1 (`is_current`).

**Worked example** (illustrative configuration, not a LegalMind legal Requirement):

```text
Company Standard:
"A Data Protection provision must be present."

evaluator_type = PRESENCE                       (requirement_versions, 42.7)
configuration  = { "expected_presence": "PRESENT" }   (company_standard_versions, 42.8)
scope_key      = <the Requirement's declared single scope>
```

⚠ **Scope limit, per the approval:** this permits a *presence-type Company Standard*. It creates no general legal-policy rule, mandates no specific Requirement, and does not make Data Protection a V1 Requirement — the example is configuration, exactly as Step 20 requires ("Actual Legal Rules must be configured by authorized Legal/Admin users").

---

# P.4 Single-scope `scope_key` rule

AM-8′ makes `evaluations.scope_key NOT NULL`. A presence Requirement typically has exactly one scope.

**Locked rule:**

1. Every Requirement's `rule_configuration.comparable_scopes` declares **at least one** scope key.
2. A single-scope Requirement declares exactly one; every Evaluation for it uses that value.
3. **No global default value is defined.** The specification does not mandate a name — the Requirement's configuration supplies it. Inventing a reserved sentinel would be inventing vocabulary.
4. `UNKNOWN` remains reserved for scope that could not be determined (45C.20) and is **not** a valid configured scope key.
5. A `scope_key` not present in the Requirement's declared scopes is a configuration error, not a runtime state — the evaluator does not silently accept it.

---

# P.5 Evaluation / output contract

```text
PRESENCE_EVALUATOR_OUTPUT

{
    evaluations: [
        {
            scope_key,
            scope_label,
            evaluation_kind      = PRIMARY,
            classification,
            rule_outcome,
            expected_value       = PRESENT,
            actual_value,                    ← PRESENT | ABSENT | INDETERMINATE
            comparison,
            evidence_refs[],
            explanation,
            diagnostics
        }
    ],
    finding_classification,                  ← derived per D-1.2
    evaluator_version
}
```

## P.5.1 Outcome matrix

| Mapping state | Applicability | `actual_value` | Classification | Rule outcome | Evidence |
|---|---|---|---|---|---|
| `CONFIRMED` | any | `PRESENT` | **`MATCH`** | `ACCEPTABLE` or `NOT_APPLICABLE` | **≥1 required** |
| `NONE` | `REQUIRED` | `ABSENT` | **`MISSING`** | `NOT_APPLICABLE` | **0 permitted** |
| `NONE` | `OPTIONAL` | — | **No Finding, no Evaluation** (F-1) | — | — |
| `AMBIGUOUS` | any | `INDETERMINATE` | **`UNABLE_TO_EVALUATE`** | `NOT_APPLICABLE` | **≥1 required** |
| `UNRESOLVED` | any | `INDETERMINATE` | **`UNABLE_TO_EVALUATE`** | `NOT_APPLICABLE` | ≥1 if any candidate evidence exists |

Locked basis: `CONFIRMED`→`MATCH` from 36.2 + R-1; `NONE`+`REQUIRED`→`MISSING` from **Step 28 r5**; `AMBIGUOUS`/`UNRESOLVED`→`UNABLE_TO_EVALUATE` from **Step 28 r6**.

## P.5.2 Outcomes `BOOLEAN_PRESENT` cannot produce

**`DEVIATION` is not producible by this evaluator.** A deviation requires a compared value, which presence-mode has none of.

R-1's third bullet — "provision exists but fails additional configured requirements" — is resolved by **N-36 (Pass 6 §1)**: such criteria are a *separate Requirement* over the same clause, permitted by locked Step 28 r1, each with its own evaluator type and Finding. Locked 42.7 makes `requirement_versions.evaluator_type` singular, so a Requirement cannot carry two evaluator types. Note also that a value-type Requirement already subsumes presence — its absence yields `MISSING` under 45C.15.

**`CONFLICT`** has no presence-specific trigger. It remains reachable through the engine's universal conflict layer (44.18), which is not this evaluator's concern (45D.4.5).

**`AMBIGUOUS` / `UNRESOLVED` as classifications** are not emitted by this evaluator; mapping-layer ambiguity routes to `UNABLE_TO_EVALUATE` per locked Step 28 r6.

---

# P.6 Evidence behavior — present vs absent

Implements approved **N-34**.

| Situation | Evidence references | Locked basis |
|---|---|---|
| Provision present (`MATCH`) | **≥1, mandatory** | 45B.18, 45C.25, 44.33 |
| Provision mapped but ambiguous (`UNABLE_TO_EVALUATE`) | **≥1, mandatory** — candidate provisions retained | 45C.25, Step 32 |
| Provision established absent (`MISSING`) | **0 permitted and expected** | 45C.15 |
| Provision present but non-qualifying (`MISSING` via a value-type Requirement) | **≥1, mandatory** | **45C.14** |

**Governing rule (N-34, approved):**

> Evidence references are preserved whenever evidence exists. `MATCH`, `DEVIATION`, `CONFLICT` and `AMBIGUOUS` evaluations must not have empty evidence references where supporting evidence exists. `MISSING` caused by established absence may legitimately contain zero. **No synthetic evidence may be created solely to satisfy a cardinality rule.**

## Reconciliation with the locked rules

| Locked rule | Reconciliation |
|---|---|
| **45B.18** "Evidence must survive the evaluator" | Evidence *that exists* survives. Where none exists, nothing is lost |
| **45C.14** provision exists, no qualifying value → evidence retained | Distinct case from absence; evidence mandatory |
| **45C.15** wholly absent → `MISSING` | Zero evidence is the correct representation; fabricating any would violate rule 7 (never invent) |
| **EV-MIN** every Finding has ≥1 Evaluation | Satisfied — an absent Requirement still produces **one** Evaluation recording how absence was established |
| **44.33** explainability chain | Preserved for absence: Evidence = *(none — absence established by mapping)*; Fact = no qualifying provision mapped; Standard = presence required; Rule = presence comparison; Result = `MISSING` |
| **AUD-01 / ENG-11** | The absence conclusion is reproducible from the persisted mapping result plus configuration versions |

**Database consequence:** `evaluation_evidence` (B-8) must permit zero rows for an Evaluation. No `NOT NULL`/`≥1` constraint may be placed on the junction.

---

# P.7 Diagnostics behavior

Per locked **REC-07** and 45B.17 — diagnostic metadata only; **cannot independently produce or alter a legal finding**.

```text
diagnostics (present):
[ "Mapping CONFIRMED for requirement <code>",
  "1 provision mapped",
  "Presence standard satisfied" ]

diagnostics (absent):
[ "Mapping layer completed",
  "No provision mapped to requirement <code>",
  "Absence established by mapping, not by evaluator inspection" ]

diagnostics (indeterminate):
[ "Mapping AMBIGUOUS — 2 candidate provisions",
  "Presence could not be established deterministically",
  "Failing closed per Step 28 rule 6" ]
```

Diagnostics never assert a legal conclusion and never contain contract text as a substitute for evidence.

---

# P.8 Fail-closed behavior

| Condition | Behavior | Locked basis |
|---|---|---|
| Mapping `AMBIGUOUS` or `UNRESOLVED` | `UNABLE_TO_EVALUATE` — **never** treated as absent | **Step 28 r6**, ENG-09 |
| `expected_presence` absent from the Standard configuration | Evaluator does not run; configuration error | 45B.26 |
| `scope_key` not in declared scopes | Configuration error, not a runtime state | P.4 |
| Mapping layer did not complete | No Evaluation; Review-level `ANALYSIS_FAILED` | Step 30 (distinct from `UNABLE_TO_EVALUATE`) |
| `applicability = OPTIONAL` and absent | No Finding produced (F-1) | Step 28 r5 covers `REQUIRED` only |

**The single most important fail-closed rule:** an ambiguous or unresolved mapping must **never** be recorded as absence. Doing so would convert uncertainty into the legal conclusion "no such provision exists" — the exact failure mode ENG-09 and 45C.15 exist to prevent.

---

# P.9 Golden examples

Each asserts the exact Evaluation output **and** the derived Finding summary (45D requirement; never the roll-up alone).

### PE-1 · Provision present → `MATCH`

```text
mapping_state = CONFIRMED, evidence_refs = [E1]
evaluator_type = PRESENCE, expected_presence = PRESENT, applicability = REQUIRED

evaluations: [ { scope_key: <declared>, evaluation_kind: PRIMARY,
                 classification: MATCH, rule_outcome: NOT_APPLICABLE,
                 expected_value: PRESENT, actual_value: PRESENT,
                 evidence_refs: [E1] } ]
finding_classification: MATCH
assert: evidence_refs non-empty
```

### PE-2 · Provision absent → `MISSING`, zero evidence

```text
mapping_state = NONE, evidence_refs = []
applicability = REQUIRED

evaluations: [ { classification: MISSING, rule_outcome: NOT_APPLICABLE,
                 expected_value: PRESENT, actual_value: ABSENT,
                 evidence_refs: [] } ]
finding_classification: MISSING
assert: exactly one Evaluation exists (EV-MIN)
assert: evidence_refs empty AND no synthetic evidence created
```

### PE-3 · Ambiguous mapping → `UNABLE_TO_EVALUATE` (never absent)

```text
mapping_state = AMBIGUOUS, evidence_refs = [E1, E2]

evaluations: [ { classification: UNABLE_TO_EVALUATE,
                 rule_outcome: NOT_APPLICABLE,
                 actual_value: INDETERMINATE,
                 evidence_refs: [E1, E2] } ]
finding_classification: UNABLE_TO_EVALUATE
assert: classification is NOT MISSING          ← the critical regression guard
assert: both candidate provisions retained
```

### PE-4 · Unresolved mapping → `UNABLE_TO_EVALUATE`

```text
mapping_state = UNRESOLVED
assert: classification is NOT MISSING and NOT MATCH
```

### PE-5 · Multi-Requirement Review — the Step 8 alignment shape

Demonstrates that locked Step 8 is producible with **two** evaluator types.

```text
Requirement A (BOOLEAN_PRESENT)   CONFIRMED  → MATCH
Requirement B (BOOLEAN_PRESENT)   CONFIRMED  → MATCH
LIABILITY-001 (NUMERIC_COMPARISON) 12 months → DEVIATION + ACCEPTABLE
Requirement C (BOOLEAN_PRESENT)   NONE       → MISSING
Requirement D (BOOLEAN_PRESENT)   CONFIRMED  → MATCH

assert: 5 Findings, each with ≥1 Evaluation
assert: matches, a deviation and a missing all present in one Review
assert: no evaluator produced a Legal Decision
```

### PE-6 · Regression guard — the evaluator reads no text

```text
assert: the presence evaluator receives no clause text in its input
assert: changing clause wording without changing mapping_state
        does not change the evaluation outcome
```

PE-6 is the structural guard against N-30 recurring.

---

# P.10 Cross-check against locked decisions and current amendments

| Check | Result |
|---|---|
| **Presence ≠ text-pattern evaluator** | ✅ Input carries no text and no patterns; presence derives solely from `mapping_state`. PE-6 enforces it |
| **Mapping ≠ Evaluation (ENG-03)** | ✅ Mapping decides *which Requirement a clause relates to*; the evaluator compares that result against the Standard. Neither performs the other's job |
| **Finding ≠ Evaluation** | ✅ One Finding per Requirement, ≥1 Evaluation beneath it; classification derived per D-1.2, evaluations authoritative |
| **Rule outcome at Evaluation level only (J-2)** | ✅ `rule_outcome` on each Evaluation; no Finding-level value |
| **EV-MIN** | ✅ Every case, including PE-2 absence, produces exactly one Evaluation |
| **Evidence / audit reproducibility** | ✅ Complete — `evaluator_version` (AM-19) and `legal_rule_version_id` (AM-20) are persisted; Company Standard version derived via the configuration snapshot |
| **44.33 explainability** | ✅ Chain intact for present and absent alike (P.6) |
| **36.2 `MATCH` = conforms to Company Standard** | ✅ Valid under approved R-1; the Standard is a presence Standard per `evaluator_type` (42.7) + `configuration` JSONB (42.8) |
| **Step 28 r5 / r6** | ✅ Both implemented literally |
| **Step 20 r4** (not every Clause needs a Legal Rule) | ✅ `legal_rule` optional; absence ⇒ `NOT_APPLICABLE` |
| **45B (liability contract)** | ✅ Untouched — this is a separate contract, as 44.11 intends |
| **45C** | ✅ Untouched — liability edge cases do not apply |
| **AM-8′** | ✅ Compatible: `scope_key`, `scope_label`, `evaluation_kind = PRIMARY`, `rule_outcome` |
| **36.10 no generic risk score** | ✅ No risk output |
| **N-33 alignment** | ✅ Not an evaluator concern; excluded |
| **42.15 nullable `expected_value`/`actual_value`** | ✅ Populated here, but locked nullability is unaffected |
| **No new legal Requirement** | ✅ The Data Protection example is illustrative configuration only |

---

# P.11 New findings

| ID | Finding | Class |
|----|---------|-------|
| **N-35** | Optional Requirement, no mapped provision → **no Finding, no Evaluation** | **RESOLVED — pending ratification** (Pass 6 §6) |
| **N-36** | Composite Requirements → **separate Requirements over the same clause** (Step 28 r1); locked 42.7 makes `evaluator_type` singular | **RESOLVED** (Pass 6 §1) |
| **AM-18** | `standard_kind` column | **WITHDRAWN — redundant** with `evaluator_type` (42.7) + `configuration` JSONB (42.8) |
| **N-37** | `evaluation_evidence` permits zero rows; no minimum-cardinality constraint; invariant service-enforced | **RESOLVED** (Pass 6 §3) |

### Second-order dependency check

**AM-18 affects:** `company_standard_versions` (42.8), the configuration snapshot (42.12), the 45B input `company_standard` block (which A-2 already amends with `scope`), the Legal Admin configuration UI (Step 29), and golden fixtures. **Does not affect** findings, decisions, authorization, or the roll-up.

**N-35 affects:** the presence outcome matrix, Step 8 report completeness (an optional absent Requirement may or may not appear as a row), and golden case PE-2's variants. It is a *legal-domain* question about what an optional Requirement means, not an engineering one.
