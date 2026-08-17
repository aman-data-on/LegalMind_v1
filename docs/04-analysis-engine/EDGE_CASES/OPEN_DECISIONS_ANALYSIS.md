# J-1 – J-6 — Open Decision Analysis

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a conclusion was reached, and its status lines describe the state **at the time of writing**, which has since changed. A conclusion is authoritative only where it appears in [LOCKED_DECISIONS.md](../../00-project/LOCKED_DECISIONS.md) and `all_lock.md`. Do not implement from this file.

**Status: ⏳ PROPOSAL — NOTHING LOCKED. No locked decision modified. `all_lock.md` not touched.**

Prepared 2026-08-16. Each decision independently re-tested against the locked corpus; the prior recommendation was **not** assumed.

Related: [LIABILITY_CONTRACT_AMENDMENTS.md](LIABILITY_CONTRACT_AMENDMENTS.md) · [LIABILITY_EDGE_CASES.md](LIABILITY_EDGE_CASES.md) · [LIABILITY_EVALUATOR_CONTRACT.md](LIABILITY_EVALUATOR_CONTRACT.md) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

---

# J-3 — Legal Decision scope

## 1. Current problem

Under A-4, one Finding may group several scoped Evaluation Results carrying **different** rule outcomes — `NOT_APPLICABLE` on a general aggregate cap, `UNACCEPTABLE` on a confidentiality carve-out. The locked `legal_decisions` table attaches a decision to a Finding, not to an Evaluation. It is therefore impossible to record that Legal accepted one scope and required the standard for another.

## 2. Relevant locked decisions

| Source | Text | Bearing |
|---|---|---|
| 42.17 | `legal_decisions.finding_id UUID FK → findings.id` | Decision is Finding-level today |
| Step 31 r2 | "decisions on Findings requiring Legal review" | Finding-level language |
| Step 31 r4 | "`ACCEPT_DEVIATION` applies only to the specific Review/Finding" | Scope of effect |
| Step 31 r9 | "`REJECT` applies to the specific contractual position/Finding" | **"contractual position"** — narrower than Finding |
| Step 31 r16 | Legal must be shown evidence, Requirement, Company Standard, **applicable Legal Rule**, Finding | Singular rule assumed |
| Step 31 r17 | "A Legal Decision resolves the relevant Finding" | Resolution unit |
| Step 31 r18 | Review `RESOLVED` only when all required decisions complete | Completeness |
| Step 31 r14 | Decision history immutable; changes create new versions | Versioning |
| 45C.22 | No silent precedence — never let one provision silently override another | **Decisive** |
| 45C.4 | An unlimited carve-out must not generalize to the whole provision | Decisive |
| 45A r16 | Carve-outs must not be discarded | Decisive |

## 3. Alternatives considered

**Option A** — Finding-level only; one decision disposes of all scoped Evaluations.
**Option B** — retain `finding_id`, add `evaluation_id` targeting a scoped Evaluation.
**Option C** *(constructed and rejected)* — Finding-level decision plus a `legal_decision_evaluations` junction recording which scopes it disposed of.

## 4. Advantages / disadvantages

| | Advantages | Disadvantages |
|---|---|---|
| **A** | No amendment to 42.17. Matches Step 31's Finding-level language. One decision per Finding — simple resolution, simple UI, no partial states. | **Cannot express differing dispositions per scope.** A blanket `ACCEPT_DEVIATION` silently disposes of an `UNACCEPTABLE` carve-out. Legal exposure. Adding per-scope decisions later = DB + API + UI redesign. |
| **B** | Expresses per-scope disposition. Consistent with 45C's "evaluate separately". Superior audit granularity. Aligns with Step 31 r9's "contractual position". | Amends locked 42.17 and restates Step 31 r17. Introduces Finding-resolution derivation. If `evaluation_id` is nullable, creates dual-mode semantics. |
| **C** | Explicit disposition without changing decision authority. | **Redundant.** Evaluations are fixed for a Finding (a re-review creates a new Review per Steps 26/33), so the junction is always derivable — a duplicate source of truth, contrary to 42.1 r10's spirit. Rejected. |

## 5. Recommendation

**Option B, with `evaluation_id` REQUIRED (`NOT NULL`).**

Not nullable, not conditional. A nullable column creates two decision semantics — "this decision covers the whole Finding" versus "this decision covers one scope" — which must then be reconciled at every read, in every authorization check, and in every audit reconstruction. One rule is safer than two.

**Supporting invariant required:** every Finding has **at least one** Evaluation, including `MISSING` and `UNABLE_TO_EVALUATE` Findings. This follows from 36.14 ("evaluation must preserve the calculation") and 45C.25 ("evidence survives every branch"), but is **not explicitly stated anywhere** and must be adopted for `evaluation_id NOT NULL` to be satisfiable. See Blocker B-7.

**Finding resolution becomes derived:** a Finding is resolved when every Evaluation requiring a decision has a current decision. This satisfies Step 31 r18 and matches Step 30 r16 ("Final summaries should be derived from Findings + Legal Decisions rather than relying on a manually editable final-result field").

## 6. Why this is safest for V1

The decisive argument is not convenience — it is consistency with the architecture's own governing principle.

**45C.22 forbids silent precedence at the evaluation layer.** LegalMind may not let one provision silently override another; where two positions conflict it must surface `CONFLICT` rather than pick a winner. Option A reintroduces exactly that pattern **one layer up**: a single Finding-level decision silently disposes of every scoped position beneath it, including ones Legal never addressed. A blanket `ACCEPT_DEVIATION` over a `MATCH` general cap and an `UNACCEPTABLE` carve-out is "first/only decision wins over all scopes" — the very behavior 45C.22 prohibits.

Option A would also require the exact class of later redesign this review exists to prevent: discovering post-launch that Legal needs per-scope dispositions means changing the decisions table, the decision API, the reviewer workflow, and the audit reconstruction simultaneously.

Option A remains defensible **only** if V1 explicitly accepts that Legal cannot record differing dispositions across scopes of one Requirement. That is a legal-authority limitation, not a technical one, and must be accepted knowingly rather than inherited by default.

## 7–14. Impact

| Dimension | Impact |
|---|---|
| **7. Database** | Amend locked 42.17: add `evaluation_id UUID FK → evaluations.id NOT NULL`. Integrity constraint: `evaluations.finding_id` must equal `legal_decisions.finding_id` (enforced per 42.21's "database constraints where practical, domain-service validation where cross-table constraints become too complex"). Index on `evaluation_id`. `finding_id` retained — denormalized but valuable for the dominant query pattern. |
| **8. API** | Decisions are created against an Evaluation, not a Finding. Finding responses expose per-Evaluation decision state plus a derived Finding resolution flag. Endpoint naming remains unlocked (38.24). |
| **9. Evaluator** | **None.** The evaluator never produces decisions (36.15, 45A r18, 45B.14). This decision is entirely downstream of the engine. |
| **10. Reviewer/UI** | Decision controls move to the scope row. Step 31 r16 is *better* satisfied: each scope shows its own applicable Legal Rule. The Finding cannot be resolved while any scope requiring a decision lacks one — the "hidden carve-out" failure becomes structurally impossible. |
| **11. Audit/reproducibility** | Strictly improved. The audit trail records which scope was decided, by whom, with which reason (Step 31 r11, r12, r19). Under Option A, reconstructing "did Legal consider the carve-out?" depends on inferring what the UI displayed. |
| **12. Testing/golden corpus** | Golden corpus covers the evaluator, which is unaffected. Adds workflow fixtures: heterogeneous-outcome Findings, partial-decision states, resolution derivation. |
| **13. New risks** | Partially-decided Findings become a real state needing UI treatment. More decision records per Review (audit volume). Second-person approval (Step 31 r15) must be defined at Evaluation level. |
| **14. Amendment required** | **Yes — two.** (i) 42.17 gains `evaluation_id`. (ii) Step 31 r17 restated: a Legal Decision resolves the relevant **Evaluation**; the Finding is resolved when all its Evaluations requiring decisions are resolved. Step 31's vocabulary, definitions and rules 1–16 and 18–20 are otherwise untouched. |

---

# J-1 — Finding classification roll-up

## 1. Current problem

`findings.classification` is a stored `NOT NULL` column (42.14). When a Finding groups several scoped Evaluations with different classifications, what does that single stored value mean?

## 2. Relevant locked decisions

42.14 / 41.18 / 40.10 (single stored `NOT NULL` classification, 7 locked values) · REC-01 (canonical vocabulary) · **Step 30 r16** ("Final summaries should be **derived** from Findings + Legal Decisions rather than relying on a manually editable final-result field") · 41.19 (Finding = *what did LegalMind conclude*; Evaluation = *how*) · ENG-09 fail-closed · 45C.22 no silent precedence · 36.14 preserve the calculation.

## 3. Alternatives considered

1. **Strict precedence** — a fixed ordering; the Finding takes the highest-ranked scoped classification.
2. **Derived summary** — same computation, but formally designated non-authoritative and never a decision basis.
3. **Explicit roll-up field** — a separate column distinct from evaluation classifications.
4. **`MIXED` / `MULTIPLE` sentinel value** — a new enum member for heterogeneous Findings.
5. **General-scope proxy** — the Finding takes the `GENERAL` cap's classification.

## 4. Advantages / disadvantages

| | Advantages | Disadvantages |
|---|---|---|
| 1 Strict precedence | Deterministic; single value; no schema change | Reads as an independent legal conclusion; risks the summary being treated as the truth |
| 2 Derived summary | Same mechanics, correct epistemic status; satisfies Step 30 r16 | Requires an explicit non-authoritative declaration and enforcement in API/UI |
| 3 Separate roll-up field | Explicit | `findings.classification` still needs a value — solves nothing, adds a field |
| 4 `MIXED` sentinel | Honest about heterogeneity | **Amends the locked 7-value enum** (42.14, REC-01, REC-06 axis 2); pollutes axis 2 with a non-legal value; `MIXED` is unfilterable and uninformative |
| 5 General-scope proxy | Trivial, no ordering invented | **Unsafe.** General cap `MATCH` + carve-out `UNACCEPTABLE` → Finding reads `MATCH`. Rejected outright |

## 5. Recommendation

**Option 2 — a derived, deterministic, stored summary, formally non-authoritative.**

Three components:

**(a) Status declaration.** `findings.classification` is a *summary index* for listing, filtering and reporting. **The scoped Evaluation Results are authoritative.** No Legal Decision may be taken on the summary alone — which J-3 Option B enforces structurally, since decisions target Evaluations.

**(b) Two-tier derivation**, justified from locked principles rather than convenience:

```text
TIER 1 — result cannot be relied upon (fail-closed, ENG-09)
    UNABLE_TO_EVALUATE  >  CONFLICT  >  AMBIGUOUS  >  UNRESOLVED

TIER 2 — evaluated positions
    MISSING  >  DEVIATION  >  MATCH
```

Any Tier-1 scope dominates every Tier-2 scope. **This is derived, not invented:** ENG-09 and 45C.18/45C.25 require that a Finding never read `MATCH` while any scope is unevaluable, contradictory or absent. Within Tier 2, `MISSING` (a required provision absent) outranks `DEVIATION` (present but differing) outranks `MATCH`, matching the escalation ordering already implicit in 45A §17.

**(c) Honest disclosure of the arbitrary part.** The ordering *within* Tier 1 is **not** legally derivable — all four states route to human review and are legally equivalent in consequence. A fixed order is chosen solely for determinism (locked requirement ENG-11), not legal judgment. Any total order would be equally correct; this must be stated in the specification rather than presented as reasoned.

**(d) Stored, not computed at read time**, because 42.14 declares it `NOT NULL` and it must be indexable for review listings. It is written once by the engine and never user-editable, satisfying Step 30 r16.

## 6. Why safest

It preserves the locked principle that Evaluations are authoritative while satisfying a locked `NOT NULL` column, invents no enum values, amends no locked decision, and is explicit about which part of the ordering is convention rather than law — the opposite of smuggling a legal precedence in as an implementation detail.

## 7–14. Impact

| Dimension | Impact |
|---|---|
| **7. Database** | None. `findings.classification` unchanged. Written by the engine; never user-editable. |
| **8. API** | Finding response carries both the summary and the full `evaluations[]`. The summary must never be returned without the evaluations, or clients will treat it as authoritative. |
| **9. Evaluator** | Emits `finding_classification` alongside `evaluations[]` (already in the B-proposal output). Pure function of the scoped classifications — deterministic and reproducible. |
| **10. Reviewer/UI** | Summary shown at Finding level; scopes always expandable. A Finding whose summary is `DEVIATION` but which hides an `UNACCEPTABLE` scope must be visually distinguishable. |
| **11. Audit/reproducibility** | The derivation is a pure function of persisted Evaluations, so it is reproducible from stored data and needs no separate audit record. |
| **12. Testing** | One fixture per ordered pair to pin the derivation; plus per-45C-case fixtures asserting summary **and** scoped set (asserting only the summary hides per-scope regressions). |
| **13. New risks** | The summary being mistaken for the legal conclusion — mitigated by (a) and by J-3 Option B. |
| **14. Amendment required** | **No.** New specification only. |

---

# J-2 — Rule Outcome level

## 1. Current problem

`rule_outcome` appears throughout 44.x and 45B but exists in **no** locked table. Its home is undefined, and with multiple scopes it is unclear whether a Finding has one.

## 2. Relevant locked decisions

45B.14 (rule outcome sits on the EvaluationResult and "is **not the same thing as** Finding classification") · 42.14 (`findings` has **no** rule-outcome column) · 42.15 (`evaluations` has `result JSONB NOT NULL`, no explicit column) · 42.1 r10 (JSONB for "genuinely variable configuration, **not to hide core relationships**") · REC-06 (axis 3 distinct from axis 2) · Step 27 r9 · Step 30 r6 (`LEGAL_REVIEW` entered only when the configured workflow requires it — so rule outcome drives routing) · Step 30 r16 (summaries derived).

## 3. Alternatives considered

1. Evaluation level only, as a **column**.
2. Evaluation level only, inside `result` JSONB.
3. Both Evaluation and Finding level, stored.
4. Evaluation level stored + Finding level **derived at query time**.

## 4. Advantages / disadvantages

| | Advantages | Disadvantages |
|---|---|---|
| 1 | Single source of truth; queryable; matches 45B.14 | Amends 42.15 (already being amended by F-1) |
| 2 | No schema change | Rule outcome drives review routing and authorization filtering — burying a controlled enum in JSONB contradicts 42.1 r10 and makes routing queries unindexable |
| 3 | Fast Finding-level queries | **Duplicate source of truth.** Two values that can diverge; a stored Finding-level outcome is exactly the "manually editable final-result field" Step 30 r16 warns against |
| 4 | Single source of truth **and** Finding-level answers | Derived value must be computed consistently everywhere |

## 5. Recommendation

**Option 1 + 4: `rule_outcome` exists only at Evaluation level, as a column. Any Finding-level notion is derived, never stored.**

```text
evaluations.rule_outcome  RULE_OUTCOME NOT NULL
    ACCEPTABLE | APPROVAL_REQUIRED | UNACCEPTABLE | NOT_APPLICABLE
```

`NOT_APPLICABLE` is required, not nullable — locked by 45B.26 (no arbitrary NULL semantics) and REC-05 R1.3.

The question "does this Finding need Legal approval?" is answered by derivation: **a Finding requires a decision if any of its Evaluations has `rule_outcome ∈ {APPROVAL_REQUIRED, UNACCEPTABLE}`.** This is the fail-closed reading and the only one consistent with 45C.4 — a single unacceptable carve-out must escalate the Finding.

## 6. Why safest

One canonical location, no divergence risk, satisfies Step 30 r16, and keeps a routing- and authorization-relevant enum queryable instead of hidden in JSON. It also keeps axis 3 cleanly separated from axis 2 per REC-06.

## 7–14. Impact

| Dimension | Impact |
|---|---|
| **7. Database** | Amend 42.15: add `rule_outcome RULE_OUTCOME NOT NULL`. New enum type. Index for review-routing queries. No change to `findings`. |
| **8. API** | `rule_outcome` on each evaluation; a derived `requires_decision` boolean on the Finding. **Permission-filtered** — rule outcomes expose internal legal position (LEGAL-02) and must be server-side gated. |
| **9. Evaluator** | Already emits `rule_outcome` per 45B; now persisted relationally rather than inside `result`. |
| **10. Reviewer/UI** | Per-scope outcome badges. The Finding-level "needs decision" indicator is derived, so it can never contradict the scopes beneath it. |
| **11. Audit/reproducibility** | Improved — the value that drove routing is explicitly persisted per scope with its `rule_version_id`. |
| **12. Testing** | Fixtures assert `rule_outcome` per scope; plus derivation tests (one `UNACCEPTABLE` scope among `ACCEPTABLE` ones must escalate the Finding). |
| **13. New risks** | The derivation must be implemented once in a shared service, not re-implemented per caller. |
| **14. Amendment required** | **Yes — one:** 42.15 gains a column. No conceptual locked decision changes; this *fills* a gap rather than altering a decision. |

---

# J-4 — Finding status

## 1. Current problem

`findings.status FINDING_STATUS NOT NULL` (42.14) references an enum whose values are **never defined anywhere in `all_lock.md`**. It cannot be implemented as locked.

## 2. Relevant locked decisions

Step 30 r1 ("Review lifecycle and Finding status are **separate concepts**") · Step 30 r6, r7, r16, r17 · Step 31 r10 (`REQUEST_CLARIFICATION` "leaves the required workflow unresolved until completed"), r17, r18 · Step 4 / Step 22 (escalation) · REC-06 (five axes — Finding status is *not* one of them and must not duplicate any).

## 3. Alternatives considered

1. **No status column** — derive everything from decisions.
2. **Minimal workflow enum** — only states not derivable from other axes.
3. **Rich enum** mirroring the Review lifecycle.
4. **Reuse Review lifecycle values.**

## 4. Advantages / disadvantages

| | Advantages | Disadvantages |
|---|---|---|
| 1 | No duplicate state | Contradicts locked 42.14 (`NOT NULL` column) and Step 30 r1's assertion that Finding status exists |
| 2 | Satisfies the locked column; no axis duplication | Requires justifying every value as non-derivable |
| 3 | Expressive | Duplicates Review lifecycle; contradicts Step 30 r1's separation |
| 4 | Consistent naming | **Directly violates** Step 30's core locked decision — a single status field must not represent multiple concepts |

## 5. Recommendation

**Option 2 — a minimal four-value enum**, each value justified as *not* derivable from classification, rule outcome, decision, or Review lifecycle:

```text
OPEN                     Generated; no decision required.
DECISION_REQUIRED        A decision is required — because a scoped rule outcome
                         demands it, OR because a user escalated it (Step 4).
AWAITING_CLARIFICATION   REQUEST_CLARIFICATION issued; workflow blocked
                         pending external action (Step 31 r10).
RESOLVED                 All required decisions complete (Step 31 r17, r18).
```

**Why a stored column rather than pure derivation:** escalation (Step 4, Step 22) lets a *user* raise a Finding for review even when the rule outcome is `ACCEPTABLE`. That state is not derivable from any evaluation value, which is precisely why Step 30 r1 declares Finding status a separate concept. `AWAITING_CLARIFICATION` likewise reflects an external action, not an evaluation.

**Boundaries** — this enum must never encode: Review position (axis 5), comparison result (axis 2), tolerance (axis 3), or the decision itself (axis 4). `RESOLVED` here means *this Finding's* required decisions are complete; `RESOLVED` on a Review means *all* Findings are (Step 30 r7). Same word, different axis — a collision to be namespaced per REC-06, not renamed.

⚠ **Interaction with J-3.** Under Option B, `RESOLVED` becomes derived from per-Evaluation decisions, and a new implicit state appears: *partially decided*. Whether that warrants a fifth value (`PARTIALLY_DECIDED`) or is derived for display only is **open** — see Blocker B-3.

## 6. Why safest

It is the smallest enum that satisfies the locked `NOT NULL` column without duplicating any of the five locked axes, and every value is defensible from locked text rather than invented for completeness.

## 7–14. Impact

| Dimension | Impact |
|---|---|
| **7. Database** | Defines the existing `FINDING_STATUS` type; no structural change. |
| **8. API** | Finding status exposed and filterable ("show findings needing decisions"). |
| **9. Evaluator** | None — the evaluator sets the initial value only; status is workflow, not analysis. |
| **10. Reviewer/UI** | Primary work-queue filter. Must be visually distinct from Review status to avoid the `RESOLVED`/`RESOLVED` collision. |
| **11. Audit** | Every transition is an audit event (Step 30 r17 by analogy; Step 25). |
| **12. Testing** | Workflow tests, not golden-corpus tests — the corpus covers the deterministic engine, and status is downstream of human action. |
| **13. New risks** | `RESOLVED` collision with Review lifecycle. Escalation semantics (Step 4/22) versus `DECISION_REQUIRED` need confirmation. |
| **14. Amendment required** | **No** — this fills a gap in a locked decision rather than changing one. New specification, requires approval. |

---

# J-6 — AMBIGUOUS / UNRESOLVED boundaries

## 1. Current problem

Five controlled values across three layers reuse two tokens. Without crisp boundaries they will collide in the schema, the API and the reviewer's mental model.

## 2. Relevant locked decisions

Step 28 (mapping states) · 36.6, 36.7, 36.8 (classifications) · 45B.7 (extraction status) · REC-03, REC-06 (axes must not share enums) · ENG-09 fail-closed.

## 3. Definitions and boundary test

Each layer answers a different question. The boundary is **the stage at which determinism failed**.

| Value | Layer | Question that failed | Locked definition |
|---|---|---|---|
| `MappingState.AMBIGUOUS` | Mapping | *Which Requirement?* | More than one plausible mapping exists; must not silently choose (Step 28) |
| `MappingState.UNRESOLVED` | Mapping | *Which Requirement?* | Mapping cannot be established reliably (Step 28) |
| `ExtractionStatus.AMBIGUOUS` | Extraction | *What are the facts?* | Facts extracted but not reliably interpretable (45B.7) |
| `Classification.AMBIGUOUS` | Evaluation | *What is the legal position?* | Provisions found; intended legal position not deterministically establishable (36.6) |
| `Classification.UNRESOLVED` | Evaluation | *What is the legal position?* | Issue identified; evaluation cannot complete because required information **or a required action** is missing (36.7) |

**Discriminator within a layer:** `AMBIGUOUS` = *too many* candidate answers; `UNRESOLVED` = *no* usable answer. This holds for both mapping and evaluation and is consistent with all locked definitions.

**Cross-layer routing** (locked): mapping `AMBIGUOUS`/`UNRESOLVED` may produce `UNABLE_TO_EVALUATE` (Step 28 r6); extraction `FAILED` must produce `UNABLE_TO_EVALUATE` (45B.7).

## 4. The one genuine semantic problem

**`Classification.UNRESOLVED` (36.7) says "or a required action is missing."** That is workflow language inside an analysis-layer value. It overlaps directly with J-4's `AWAITING_CLARIFICATION` and with Step 31 r10's `REQUEST_CLARIFICATION`.

If a clarification request is outstanding, is that `Classification.UNRESOLVED` (axis 2) or Finding status `AWAITING_CLARIFICATION` (workflow)? Under REC-06 it **must** be the latter — axis 2 is a comparison result, not a workflow position — but 36.7's wording invites the opposite reading. This is a **genuine locked-text ambiguity**, not merely a naming collision.

## 5. Recommendation

**(a) Do not rename. Namespace instead.** Every candidate rename amends a locked decision: mapping states are locked by Step 28 and REC-03; classifications by Step 36 and REC-01; extraction status by Step 45B. The renames considered and rejected:

| Rename considered | Would amend | Verdict |
|---|---|---|
| `MappingState.AMBIGUOUS` → `MULTIPLE_CANDIDATES` | Step 28, REC-03 | Clearer, but not worth amending two locked decisions |
| `MappingState.UNRESOLVED` → `NO_CONFIDENT_MAPPING` | Step 28, REC-03 | Tempting — aligns with Step 35's existing vocabulary — but Step 35's term is an unlocked scoring label, and adopting it would pre-empt the deliberately deferred band→state mapping |
| `ExtractionStatus.AMBIGUOUS` → `INDETERMINATE` | Step 45B | Marginal gain; 45B just locked |

**Enforcement instead of renaming:** three distinct PostgreSQL enum types (`MAPPING_STATE`, `FINDING_CLASSIFICATION`, `EXTRACTION_STATUS`), never a shared type; namespaced API type names; UI labels that name the layer ("Mapping: ambiguous"), never a bare "Ambiguous".

**(b) Clarify 36.7 — the real fix.** Propose an interpretive clarification (not a rewording of locked text): `Classification.UNRESOLVED` covers *information* required to complete the **evaluation**. A pending human **action** is Finding status, not classification. See Blocker B-4.

## 6. Why safest

Zero amendments to a corpus that just absorbed seven reconciliation decisions, while addressing the only defect that actually threatens correctness — the workflow/analysis overlap in 36.7. Renaming would buy readability at the cost of destabilising locked vocabulary; namespacing achieves the same isolation at schema and API level, which is where collisions actually cause harm.

## 7–14. Impact

| Dimension | Impact |
|---|---|
| **7. Database** | Three separate enum types; never reuse one across layers. |
| **8. API** | Namespaced type names; layer-qualified serialization. |
| **9. Evaluator** | Must apply the too-many / none discriminator consistently. |
| **10. Reviewer/UI** | Labels always name the layer. |
| **11. Audit** | Layer-qualified values make failure-stage reconstruction unambiguous. |
| **12. Testing** | Fixtures for each of the five values, plus the cross-layer routing rules (Step 28 r6, 45B.7). |
| **13. New risks** | If 36.7 is not clarified, `UNRESOLVED` and `AWAITING_CLARIFICATION` will be used interchangeably. |
| **14. Amendment required** | **No** for (a). (b) is an interpretive clarification requiring approval, not a text change. |

---

# J-5 — `rule_configuration` shape

## 1. Current problem

`rule_configuration` is locked as a field of the Legal Rule input (45B.9, REC-05) with no defined contents. 45C.2 and 45C.22 make conflict-precedence behavior depend on it.

## 2. Relevant locked decisions

**44.29 is the governing constraint:**

> Configuration controls: `thresholds`, `allowed values`, `patterns`, `terminology`, `rule parameters`.
> Python controls: `parsing algorithms`, `normalization`, `fact extraction algorithms`, `comparison semantics`, `evaluation execution`, `conflict detection mechanics`.

Also: 44.28 (rule engine executes structured rules) · 42.1 r10 (JSONB for genuinely variable configuration) · 45C.2/45C.22 (precedence) · 45C.7/45C.8 (basis comparability) · 45C.9/45C.23 (conversion) · 45C.20 (scope necessity) · 45A §7 (configured criteria must address exceptions) · ENG-10 (parameters configurable, core code tested).

## 3. Alternatives considered

1. **Rule DSL / expression language** — arbitrary configurable logic.
2. **Minimal parameter set** — declarative parameters only; all logic in tested code.
3. **Leave unspecified** — decide during implementation.

## 4. Advantages / disadvantages

| | Advantages | Disadvantages |
|---|---|---|
| 1 DSL | Maximum flexibility | **Directly violates 44.29** — comparison semantics and conflict-detection mechanics belong in Python. An admin-editable DSL makes legal evaluation logic user-modifiable, destroying the ENG-10 guarantee that core evaluation is tested code. Rejected outright |
| 2 Minimal parameters | Complies with 44.29 and ENG-10; every field traceable to a 45C requirement | Extension needs a specification step |
| 3 Defer | No premature design | 45C.2/45C.22 cannot be implemented; blocks 45C locking |

## 5. Recommendation

**Option 2 — declarative parameters only. No logic, no expressions, no DSL.**

```text
rule_configuration {

  REQUIRED
    scope_required              bool
        45C.20 — is scope necessary for this comparison?
    comparable_scopes           [SCOPE]
        45C.5/45C.6 — customer scopes comparable to the standard's scope.
        Empty ⇒ nothing is comparable.
    comparable_bases            [CAP_BASIS]
        45C.7/45C.8 — bases comparable without conversion.
        Empty ⇒ only an identical basis is comparable.
    exception_handling          ENUM
        45A §7, 45C.3/45C.4 — how carve-outs affect the outcome.
        EVALUATE_SEPARATELY | IGNORE_FOR_GENERAL_CAP
        No default. Must be configured.

  OPTIONAL
    precedence_rules            [ { winning_source, losing_source } ]
        45C.2/45C.22 — declarative precedence only.
        ABSENT OR EMPTY ⇒ CONFLICT. Never inferred.
    conversion_rules            [ { from_basis, to_basis, required_inputs[] } ]
        45C.9/45C.23 — declares that a conversion is permitted and what
        data it needs. ABSENT ⇒ no conversion permitted ⇒ UNABLE_TO_EVALUATE.
}
```

**Must NEVER be inferred by the evaluator** — each absence is a fail-closed instruction, per ENG-09, 45C.22 and 45C.23:

```text
no precedence_rules   ⇒ CONFLICT              (never pick a winner)
no conversion_rules   ⇒ UNABLE_TO_EVALUATE    (never convert)
scope unknown + scope_required ⇒ UNABLE_TO_EVALUATE  (never assume AGGREGATE)
basis not in comparable_bases  ⇒ UNABLE_TO_EVALUATE  (never assume equivalence)
```

**Deliberately excluded.** `acceptable_max`, `approval_required_above` and `unlimited_outcome` are already first-class locked fields of `legal_rule` (45B.9) and must **not** be duplicated here. Nothing is included that no 45C rule requires.

**Extension points** (structure supports, V1 does not specify): additional conversion bases, per-scope threshold overrides, requirement-specific pattern configuration. Each requires its own specification step.

**Note on `precedence_rules`:** 45C.22 permits precedence only where "an explicit deterministic contractual rule or configured precedence rule establishes that result." This field covers the *configured* half. Honouring an **in-document** precedence clause ("the Schedule shall prevail") is contract interpretation and is **not** specified — see Blocker B-5.

## 6. Why safest

Every field traces to a specific locked 45C requirement; nothing is speculative. The design stays firmly on the configuration side of 44.29's line, so no admin can alter comparison semantics. Every absent value fails closed, matching the architecture's governing instinct.

## 7–14. Impact

| Dimension | Impact |
|---|---|
| **7. Database** | Stored on `evaluation_rule_versions`, versioned per Step 29 and captured in the configuration snapshot. JSONB is appropriate here — this is "genuinely variable configuration" in 42.1 r10's sense — but `scope_required` and `exception_handling` may warrant columns if they drive queries. |
| **8. API** | Exposed only through configuration-administration endpoints, to Legal Admin roles (Step 23). Not returned to normal users — it encodes internal legal position (LEGAL-02). |
| **9. Evaluator** | Reads parameters; never interprets logic. Absent values trigger fail-closed paths rather than defaults. |
| **10. Reviewer/UI** | Not shown to reviewers. Legal Admin configuration screens only, under the Step 29 draft→review→publish workflow. |
| **11. Audit/reproducibility** | Versioned and snapshot-captured, so a historical evaluation is reproducible with the exact configuration used (AUD-04, ENG-11). |
| **12. Testing** | A fixture per fail-closed path — absent precedence ⇒ `CONFLICT`; absent conversion ⇒ `UNABLE_TO_EVALUATE`; and a test that no default is silently applied. |
| **13. New risks** | Misconfiguration (e.g. over-broad `comparable_bases`) could permit unsafe comparisons — mitigated by Step 29's dual-control publish workflow. |
| **14. Amendment required** | **No.** `rule_configuration` is already a locked field; this specifies its contents, which the lock explicitly left open as an extension point. |

---

# IMPLEMENTATION BLOCKERS

Unresolved decisions that could materially change implementation. **None is locked.**

| ID | Blocker | Blocks | Severity |
|----|---------|--------|----------|
| **B-1** | **J-3 decision scope.** Option B amends locked 42.17 and restates Step 31 r17. Until decided, the decisions table, decision API, reviewer workflow and audit model cannot be fixed. | DB, API, UI, audit | **Critical** |
| **B-2** | **J-1 Tier-1 internal ordering** is a determinism convention, not a legal derivation. Must be accepted as such. | Evaluator, golden corpus | High |
| **B-3** | **Partially-decided Findings.** Under J-3 Option B, does a fifth status value (`PARTIALLY_DECIDED`) exist, or is it derived for display? | DB enum, UI, API | High |
| **B-4** | **36.7 workflow/analysis overlap.** `Classification.UNRESOLVED` versus Finding status `AWAITING_CLARIFICATION`. Needs interpretive clarification. | Evaluator, UI, schema | High |
| **B-5** | **In-document precedence clauses.** 45C.22 allows "an explicit deterministic contractual rule" to establish precedence, but nothing specifies detecting or honouring one. Arguably contract interpretation the engine must not perform. | Evaluator, 45C lock | High |
| **B-6** | **A-1/A-2/A-3 amendments to locked 45B** remain unapproved; 45B cannot be re-locked without them. | Evaluator contract, DB | **Critical** |
| **B-7** | **"Every Finding has ≥1 Evaluation"** is required for `evaluation_id NOT NULL` but is stated nowhere in locked text. | DB integrity, J-3 | High |
| **B-8** | **`evaluation_evidence` junction (F-2)** unapproved; without it per-scope evidence attribution is impossible and 45C.25 cannot be satisfied. | DB, audit | **Critical** |
| **B-9** | **Second-person approval** (Step 31 r15) — at Finding or Evaluation level under J-3 Option B? | Authorization, DB | Medium |
| **B-10** | **Escalation semantics.** How Step 4/22 escalation maps onto `DECISION_REQUIRED`; whether escalation is distinguishable from rule-driven decision requirement. | Workflow, UI | Medium |
| **B-11** | **Step 35 scoring-band → mapping-state mapping** — deliberately deferred 2026-08-16; still open. | Mapping engine | Medium |
| **B-12** | **`UNMATCHED_PROVISION` persistence** (REC-02) — storage, surfacing and review treatment unspecified. | DB, API, UI | Medium |
| **B-13** | **`findings` uniqueness constraint** `(review_id, requirement_version_id)` (F-3) unapproved. | DB integrity | Medium |
| **B-14** | **Step 33** remains PROVISIONAL; three rules (version numbering, withdrawal semantics, predecessor chain) unlocked. | DB, versioning | Medium |
| **B-15** | **Authentication implementation** unspecified — mechanism, session/token strategy, existing-system integration. | Auth, API, security | **Critical for implementation** |

**Critical path to implementation readiness:** B-1 → B-6 → B-8 → B-7 → B-3 → B-2 → B-4/B-5 → re-lock 45B → lock 45C → 45D golden tests. B-15 is independent and blocks any deployable system regardless of the liability work.
