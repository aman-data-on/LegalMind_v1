# Reconciliation Pass 2 — J-series resolution & amendment set

**Status: ⏳ PROPOSAL — NOTHING LOCKED. `all_lock.md` not modified. No locked decision changed.**

Prepared 2026-08-16 following owner approval of J-1, J-2, J-3 (Option B), J-4, J-6 and the B-5 modification.

Related: [OPEN_DECISIONS_ANALYSIS.md](OPEN_DECISIONS_ANALYSIS.md) · [LIABILITY_CONTRACT_AMENDMENTS.md](LIABILITY_CONTRACT_AMENDMENTS.md) · [LIABILITY_EDGE_CASES.md](LIABILITY_EDGE_CASES.md) · [LIABILITY_EVALUATOR_CONTRACT.md](LIABILITY_EVALUATOR_CONTRACT.md) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

---

# 1. Final J-series decisions

## J-3 — Legal Decision targets a scoped Evaluation

**D-3.1** `legal_decisions.evaluation_id` is **REQUIRED** (`NOT NULL`, FK → `evaluations.id`).

**D-3.2** `legal_decisions.finding_id` is **retained** as the parent relationship. Integrity: the referenced Evaluation's `finding_id` must equal the decision's `finding_id`.

**D-3.3** A Legal Decision resolves **exactly one** Evaluation. It never implicitly disposes of any other Evaluation under the same Finding.

**D-3.4 — Invariant EV-MIN.** Every Finding has **at least one** Evaluation. This holds for every classification, including `MISSING`, `AMBIGUOUS` and `UNABLE_TO_EVALUATE`: the Evaluation records *how* the engine reached that conclusion, which 36.14 ("evaluation must preserve the calculation") and 45C.25 ("evidence survives every branch") already require. A Finding with zero Evaluations is a defect, not a valid state.

### D-3.5 — When an Evaluation requires a Legal Decision

An Evaluation **requires a Legal Decision** if **any** of:

```text
(a) rule_outcome ∈ { APPROVAL_REQUIRED, UNACCEPTABLE }
(b) classification ∈ { CONFLICT, AMBIGUOUS, UNRESOLVED, UNABLE_TO_EVALUATE }   (Tier 1)
(c) classification = MISSING  and the Requirement is required
(d) it has been escalated by a user (Step 4, Step 22)
```

An Evaluation requires **no** decision when `classification ∈ {MATCH, DEVIATION}` **and** `rule_outcome ∈ {ACCEPTABLE, NOT_APPLICABLE}` **and** it has not been escalated. No decision record is created; the state is derived, not stored.

**Configuration may only widen this set, never narrow it.** Step 27 r12 makes severity configuration-driven, but ENG-09 fail-closed forbids configuration that removes a decision requirement the baseline imposes. ⚠ *This widen-only rule is new specification and requires approval — see N-8.*

### D-3.6 — When a Finding is RESOLVED

```text
Finding is RESOLVED  ⟺
    for every Evaluation E under the Finding:
        E does not require a decision
        OR E has a current Legal Decision whose type ≠ REQUEST_CLARIFICATION
```

Evaluations that require no decision are satisfied trivially — they need no record and never block resolution. An outstanding `REQUEST_CLARIFICATION` blocks resolution (Step 31 r10). Review-level `RESOLVED` then follows unchanged from Step 30 r7 and Step 31 r18.

"Current" decision means the latest non-superseded decision for that Evaluation (Step 31 r14, r20) — **which the locked schema cannot currently express, see N-1.**

## J-1 — Finding classification is a derived summary

**D-1.1** `findings.classification` is a **derived, deterministic, stored summary**. The per-Evaluation classification is **authoritative**.

**D-1.2** Two-tier derivation:

```text
TIER 1 — result cannot be relied upon
    UNABLE_TO_EVALUATE  >  CONFLICT  >  AMBIGUOUS  >  UNRESOLVED

TIER 2 — evaluated positions
    MISSING  >  DEVIATION  >  MATCH
```

Any Tier-1 scope dominates every Tier-2 scope.

**D-1.3 — Required documentation statement.** The **tier split is legally derived** (ENG-09 fail-closed: a Finding must never read `MATCH` while a scope is unevaluable, contradictory or absent). The **ordering within Tier 1 is an engineering determinism convention only — it is NOT a legal hierarchy.** All four Tier-1 states route to human review and are legally equivalent in consequence; the order exists solely to satisfy ENG-11 determinism. Any total order would be equally correct. This statement must appear in the specification and in the code that implements the derivation.

**D-1.4** The summary may never be returned by an API or displayed without its Evaluations, and may never be the basis of a Legal Decision — structurally guaranteed by D-3.1.

## J-2 — Rule Outcome at Evaluation level only

**D-2.1** `evaluations.rule_outcome RULE_OUTCOME NOT NULL` — `ACCEPTABLE | APPROVAL_REQUIRED | UNACCEPTABLE | NOT_APPLICABLE`. Not nullable (45B.26).

**D-2.2** No Finding-level rule outcome is persisted, ever. Any Finding-level notion is derived at read time (Step 30 r16).

**D-2.3** Derived Finding-level indicator: `requires_decision = ∃ Evaluation requiring a decision per D-3.5`.

## J-4 — Finding status: values and transitions

```text
OPEN                    No Legal Decision is currently required.
DECISION_REQUIRED       ≥1 Evaluation requires a decision (D-3.5).
AWAITING_CLARIFICATION  A REQUEST_CLARIFICATION is outstanding.
RESOLVED                D-3.6 satisfied.
```

### D-4.1 — Allowed transitions

| From | To | Trigger | Automatic / Human |
|------|----|---------|-------------------|
| *(none)* | `OPEN` | Analysis completes; no Evaluation requires a decision | **Automatic** (engine) |
| *(none)* | `DECISION_REQUIRED` | Analysis completes; ≥1 Evaluation requires a decision | **Automatic** (engine) |
| `OPEN` | `DECISION_REQUIRED` | User escalation (Step 4, Step 22) | **Human** |
| `DECISION_REQUIRED` | `AWAITING_CLARIFICATION` | `REQUEST_CLARIFICATION` recorded | **Human** (decision), status change automatic |
| `AWAITING_CLARIFICATION` | `DECISION_REQUIRED` | Clarification supplied / request withdrawn | **Human** |
| `DECISION_REQUIRED` | `RESOLVED` | Last outstanding decision recorded | **Automatic** (derived per D-3.6) |
| `RESOLVED` | `DECISION_REQUIRED` | Decision superseded (Step 31 r14) or new escalation | **Human** |
| `RESOLVED` | `AWAITING_CLARIFICATION` | Superseding decision is `REQUEST_CLARIFICATION` | **Human** |

**Forbidden:** `OPEN → RESOLVED` (nothing required a decision, so nothing was resolved); any user setting status directly (Step 30 r3 by analogy); any transition without an audit event (Step 25, Step 30 r17).

**Every transition emits an audit event.**

### D-4.2 — Boundaries

Finding status is **not** an axis of the [Decision State Model](../../02-legal-domain/DECISION_STATE_MODEL.md); it is per-Finding workflow position. It must never encode Review lifecycle (axis 5), classification (axis 2), rule outcome (axis 3) or the decision itself (axis 4). `Finding.RESOLVED` and `Review.RESOLVED` are different values on different objects — namespace, never share an enum type.

## J-6 — AMBIGUOUS / UNRESOLVED

**D-6.1 — Canonical definitions, applied consistently at every layer:**

```text
AMBIGUOUS   = multiple plausible candidates exist,
              but none can be selected confidently.

UNRESOLVED  = no usable answer can currently be established.
```

**D-6.2 — Step 36.7 correction (AMENDMENT).** `Classification.UNRESOLVED` must no longer include "or a required action is missing." Proposed replacement text:

> **36.7 UNRESOLVED** — The system has identified relevant material but no usable answer can currently be established from the available information. This is different from `AMBIGUOUS`, where multiple plausible candidates exist but none can be confidently selected.
>
> Requirements for human action or clarification are **workflow** states — Finding status or Legal Decision — and are never expressed as a Classification.

**D-6.3** Namespace, do not rename: three distinct enum types (`MAPPING_STATE`, `FINDING_CLASSIFICATION`, `EXTRACTION_STATUS`), layer-qualified API type names, UI labels that always name the layer.

## B-5 — Precedence is configuration-only, never interpretation

**D-5.1** `precedence_rules` expresses **only** explicitly configured, deterministic precedence relationships between named sources.

**D-5.2 — Prohibited without exception.** The evaluator must not support: arbitrary precedence expressions; executable rule definitions; DSLs; Python or any code supplied through configuration; free-form legal interpretation; administrator-defined evaluation algorithms. This is the direct application of 44.29 — comparison semantics and conflict-detection mechanics live in tested code, never in configuration.

**D-5.3 — Detected-but-unresolvable precedence.** When the document contains precedence language (e.g. *"in the event of conflict the Schedule shall prevail"*) and the precedence relationship **cannot** be established from configured rules, the evaluator fails closed:

```text
classification  = CONFLICT
rule_outcome    = NOT_APPLICABLE
```

**Evidencing requirements:**

1. Every conflicting provision is attached to the Evaluation as evidence, `relationship_type = CONFLICTING`.
2. The precedence clause **itself** is attached as evidence, `relationship_type = SUPPORTING` — it is material to the conclusion and 45C.25 requires evidence to survive every branch.
3. `diagnostics` records that precedence language was detected and could not be deterministically resolved. Per REC-07 this is diagnostic metadata and cannot alter the finding.
4. `explanation` states that the conflict was not resolved because no configured precedence rule applied.

The evaluator **never** applies the document's precedence language. Detecting it and declining to act on it is the required behavior — this preserves 45C.22 while keeping contract interpretation outside V1.

## B-3 — Heterogeneous Evaluation states within one Finding

**Verdict: YES — different Evaluations under one Finding may have different states, and the worked example is fully compatible with every locked decision, given amendments AM-1 – AM-6.**

⚠ **Axis correction to the example.** `UNACCEPTABLE` is a **rule outcome** (axis 3), not a classification (axis 2). Restated correctly:

| | Scope | Classification | Rule outcome | Requires decision |
|---|---|---|---|---|
| Eval 1 | `AGGREGATE` (general cap) | `MATCH` | `NOT_APPLICABLE` | No |
| Eval 2 | `CATEGORY` — confidentiality carve-out | `DEVIATION` | `UNACCEPTABLE` | **Yes** (D-3.5a) |
| Eval 3 | `CATEGORY` — IP carve-out | `DEVIATION` | `ACCEPTABLE` | No |

**Finding classification** = `DEVIATION` (Tier 2: `MISSING` > `DEVIATION` > `MATCH`).
**Finding status** = `DECISION_REQUIRED` until Eval 2 receives a decision, then `RESOLVED`.

### Compatibility check against each locked step

| Locked | Result |
|---|---|
| Step 27 r9 (classification separate from rule evaluation) | ✅ Eval 2 is `DEVIATION` + `UNACCEPTABLE` — the separation is exactly what makes this expressible |
| Step 27 r12 (severity configuration-driven, not hard-coded from type) | ✅ D-3.5 is a baseline configuration may widen |
| Step 27 r16 (multiple findings per Review) | ✅ Unaffected — this is multiple *Evaluations* per Finding |
| Step 30 r1 (lifecycle vs Finding status separate) | ✅ Finding status is per-Finding; Review status unchanged |
| Step 30 r7, r16 (RESOLVED; summaries derived) | ✅ D-3.6 derives resolution; nothing manually editable |
| Step 31 r4, r9 (decision applies to the specific position) | ✅ Now literally true — r9's "contractual position" language is honoured |
| Step 31 r10 (`REQUEST_CLARIFICATION` leaves workflow unresolved) | ✅ Blocks D-3.6 |
| Step 31 r17 (decision resolves the Finding) | ⚠ **Requires amendment AM-2** |
| Step 31 r18 (Review RESOLVED when all decisions complete) | ✅ Follows from D-3.6 |
| Steps 40.12 / 41.21 / 42.17 (decision record) | ⚠ **Require amendments AM-1, AM-3, AM-4** |
| Step 36 (classification vocabulary) | ✅ Values used correctly per axis |
| Step 44 (analysis architecture) | ✅ Engine unaffected — decisions are downstream (36.15, 45A r18) |
| 45A §17 matrix | ✅ `MATCH` → rule outcome "—" = `NOT_APPLICABLE` |
| 45B.14 (classification ≠ rule outcome) | ✅ Demonstrated by Eval 2 |
| 45C.3, 45C.4 (carve-outs evaluated separately, unlimited carve-out does not generalize) | ✅ This is precisely the intended shape |

---

# 2. Required amendments to locked decisions

| ID | Locked item | Amendment | Driver |
|----|-------------|-----------|--------|
| **AM-1** | 42.17 `legal_decisions` | Add `evaluation_id UUID FK → evaluations.id NOT NULL` | J-3 |
| **AM-2** | Step 31 r17 | "A Legal Decision resolves the relevant **Evaluation**; a Finding is resolved when every Evaluation requiring a decision has a current decision" | J-3 |
| **AM-3** | 41.21 `legal_decisions` | Same column added, keeping Steps 41 and 42 aligned | J-3 |
| **AM-4** | 40.12 `LegalDecision` domain model | Add `evaluationId` | J-3 |
| **AM-5** | Step 31 r4 | `ACCEPT_DEVIATION` applies to the specific Review/Finding/**Evaluation** | J-3 |
| **AM-6** | Step 31 r16 | Legal must be shown **every scoped Evaluation** with its own applicable Legal Rule before deciding | J-3 |
| **AM-7** | Step 36.7 | Remove "or a required action is missing"; adopt D-6.2 wording | J-6 |
| **AM-8** | 42.15 `evaluations` | Add `scope`, `scope_label`, `cap_kind`, `rule_outcome` | A-1, J-2 |
| **AM-9** | 45B.4 / 45B.11 | `facts.caps[]` replaces singular cap fields; `exceptions[]` absorbed | A-1, A-3 |
| **AM-10** | 45B.8 | `company_standard.scope` added | A-2 |
| **AM-11** | 45B.12 | Output becomes `evaluations[]` + derived `finding_classification` | A-4 |

Step 31's decision **vocabulary**, definitions, and rules 1–3, 5–15, 18–20 are untouched. Step 36's other classifications are untouched. No legal policy changes anywhere in this set.

---

# 3. Revised 45B contract

As proposed in [LIABILITY_CONTRACT_AMENDMENTS.md](LIABILITY_CONTRACT_AMENDMENTS.md) §B, unchanged by this pass, plus:

```text
LIABILITY_EVALUATOR_OUTPUT
{
    evaluations: [
        { scope, scope_label, cap_kind,
          classification, rule_outcome,
          expected_value, actual_value, comparison,
          evaluated_facts, evidence_refs[],
          explanation, diagnostics }
    ],
    finding_classification,      ← derived per D-1.2, non-authoritative
    evaluator_version
}
```

The evaluator emits **no** decision, status, or resolution field — those are workflow, downstream of the engine (36.15, 45A r18, 45B.14).

---

# 4. Revised 45C contract

45C.1–45C.25 stand as authored. Three additions arising from this pass:

**45C.27 — Detected-but-unresolvable precedence.** D-5.1 – D-5.3 above.

**45C.28 — Heterogeneous scoped outcomes.** One Finding may carry Evaluations with different classifications and rule outcomes. Each is decided independently; the Finding resolves only when all Evaluations requiring decisions are decided. No Evaluation is ever implicitly disposed of by a decision on another.

**45C.29 — Configuration may only widen decision requirements**, never narrow them (D-3.5).

45C.26's proposed lock list gains: *18. A Legal Decision resolves exactly one scoped Evaluation and never implicitly disposes of another. 19. Detected precedence language that cannot be deterministically resolved produces `CONFLICT`, with the precedence clause retained as evidence.*

---

# 5. Database changes

| # | Change | Type |
|---|--------|------|
| DB-1 | `legal_decisions.evaluation_id UUID NOT NULL FK → evaluations.id` | Amendment (AM-1) |
| DB-2 | `INDEX(evaluation_id)` on `legal_decisions` | New |
| DB-3 | `evaluations.scope SCOPE NOT NULL`, `scope_label VARCHAR NULL`, `cap_kind CAP_KIND NOT NULL` | Amendment (AM-8) |
| DB-4 | `evaluations.rule_outcome RULE_OUTCOME NOT NULL` + new enum type | Amendment (AM-8) |
| DB-5 | `evaluation_evidence(evaluation_id, evidence_id, relationship_type)` PK`(evaluation_id, evidence_id)` | New table (B-8) |
| DB-6 | `UNIQUE(review_id, requirement_version_id)` on `findings` | New constraint |
| DB-7 | `FINDING_STATUS` enum defined: `OPEN`, `DECISION_REQUIRED`, `AWAITING_CLARIFICATION`, `RESOLVED` | Fills gap (J-4) |
| DB-8 | Current-decision marker on `legal_decisions` | **⚠ UNRESOLVED — see N-1** |

### Constraints enforcing the new invariants

| Invariant | Enforcement |
|-----------|-------------|
| Decision's Evaluation belongs to the same Finding | Cross-table — domain-service validation, or a composite FK `(finding_id, evaluation_id)` against a `UNIQUE(id, finding_id)` on `evaluations`. **The composite-FK form is enforceable purely in the database and is preferred.** |
| **EV-MIN** — every Finding has ≥1 Evaluation | Not expressible as a simple FK (insert-order circularity). Requires a `DEFERRABLE INITIALLY DEFERRED` constraint trigger, or transactional enforcement in the domain service per 42.21's "domain-service validation where cross-table constraints become too complex". **Choice unresolved — N-9.** |
| Evidence belongs to the Review's Document Version | Extends 42.21's Evidence-consistency rule to `evaluation_evidence` |
| One current decision per Evaluation | Depends on N-1 |
| Status never user-set | Service-layer only; every transition audited |

`findings`, `finding_evidence` and `document_evidence` are otherwise unchanged. `finding_evidence` is **retained** as the Finding-level roll-up.

---

# 6. API changes

* Decisions are created against an **Evaluation**: the request must identify `evaluation_id`; a Finding-level decision endpoint must not exist.
* Finding responses embed `evaluations[]`, each with `classification`, `rule_outcome`, `evidence_refs[]`, `explanation`, and its own decision state.
* Finding carries the derived `classification` summary, `status`, and derived `requires_decision`. **The summary is never returned without the evaluations** (D-1.4).
* No endpoint returns a Finding-level rule outcome — none exists (D-2.2).
* Attempting to resolve a Finding directly must be rejected; resolution is derived, never asserted.
* Endpoint naming remains unlocked (38.24).

---

# 7. Authorization implications

* Decision creation authority is checked at the **Evaluation** level, traversing Evaluation → Finding → Review → Contract → Owner/Role per the locked object-level rule (41.24, 43.23). Knowing an `evaluation_id` grants nothing.
* `rule_outcome`, thresholds and `rule_configuration` expose internal legal position and remain permission-gated server-side (LEGAL-02, 38.21).
* Only users with legal-decision authority may create decisions (Step 4, ROLE-03, ROLE-05); escalation remains available to normal Users.
* **Step 31 r15 second-person approval is now ambiguous** — per Evaluation or per Finding? See B-9, still open.

---

# 8. Audit / reproducibility implications

* Every decision names the exact Evaluation it resolved — "did Legal consider the confidentiality carve-out?" becomes answerable from data rather than inferred from UI history.
* Every Finding-status transition emits an audit event (Step 25, Step 30 r17).
* The Finding classification summary is a pure function of persisted Evaluations, so it is reproducible and needs no separate audit record.
* Decision supersession (Step 31 r14) must remain immutable and reconstructable — **blocked by N-1**.
* `evaluation_evidence` makes per-scope evidence reconstructable, satisfying 45B.18 and 45C.25 at scope granularity for the first time.

---

# 9. Golden-test requirements

Engine-level (golden corpus, ENG-12):

1. Every 45C case asserts **both** the rolled-up Finding classification and the exact per-scope Evaluation set.
2. Tier-1 dominance: a Finding with one `UNABLE_TO_EVALUATE` scope and several `MATCH` scopes must summarize as `UNABLE_TO_EVALUATE`.
3. Tier-1 internal ordering fixtures — pinning the **convention**, labelled as such so no one later mistakes them for legal assertions.
4. The negative-pattern matched pair: *"Liability shall not be limited in respect of fraud"* (carve-out) vs *"Liability shall not be limited"* (general `UNLIMITED`).
5. B-5: precedence language present + no configured rule ⇒ `CONFLICT`, with the precedence clause attached as `SUPPORTING` evidence.
6. Fail-closed matrix: absent precedence ⇒ `CONFLICT`; absent conversion ⇒ `UNABLE_TO_EVALUATE`; unknown scope + `scope_required` ⇒ `UNABLE_TO_EVALUATE`; basis not in `comparable_bases` ⇒ `UNABLE_TO_EVALUATE`. Each asserts no default was silently applied.
7. `EV-MIN`: every fixture produces ≥1 Evaluation, including `MISSING` and `UNABLE_TO_EVALUATE` cases.
8. 45C.16/45C.17 duplicates ⇒ **one** Evaluation with two evidence refs.

Workflow-level (not golden corpus — these test human process, not the deterministic engine):

9. The B-3 three-evaluation scenario: Finding stays `DECISION_REQUIRED` until Eval 2 is decided.
10. A decision on Eval 2 must not alter Eval 1 or Eval 3.
11. `REQUEST_CLARIFICATION` on any Evaluation blocks Finding resolution.
12. Escalation moves `OPEN → DECISION_REQUIRED`.

---

# 10. Remaining implementation blockers

### New — discovered in this pass, not resolved

| ID | Issue | Severity |
|----|-------|----------|
| **N-1** | **Step 31 r20 has no schema support.** r20 requires the current decision always be distinguishable from historical ones, and r14 makes changes create new versions — but `legal_decisions` (40.12 / 41.21 / 42.17) has no supersession marker, version number or `is_current` flag. Options: `superseded_by_id`; `is_current` + partial unique index on `(evaluation_id) WHERE is_current`; or `version_number` + derivation by `created_at`. **A locked rule is currently unimplementable.** | **Critical** |
| **N-2** | 41.21 lists `REQUIRE_STANDARD`; Step 31 locks `REQUIRE_COMPANY_STANDARD`. 41.21 is explicitly illustrative and defers to the Legal Decision workflow, so Step 31 governs — but the discrepancy sits in locked text and should be recorded, not silently normalized. | Low |
| **N-3** | Field-name drift across the three locked definitions of the decision record: 40.12 has `justification` and `metadata`; 41.21 and 42.17 have `decision_text` and no metadata. Step 31 r11 requires a reason. Canonical naming undecided. | Medium |
| **N-4** | After AM-7, `Classification.UNRESOLVED` may have **no occupant** in `LIABILITY-001`: 45C.10 sends unresolvable cross-references and 45C.20 sends unknown scope to `UNABLE_TO_EVALUATE`, and 45C.23 sends missing conversion data there too. An enum value with no reachable case is a design smell — either a case belongs to it, or its role needs restating. | Medium |
| **N-8** | The **widen-only** configuration rule (D-3.5) is new specification, not derived from a single locked rule — it reconciles Step 27 r12 with ENG-09. Needs explicit approval. | Medium |
| **N-9** | `EV-MIN` enforcement mechanism undecided: deferred constraint trigger vs domain-service transaction. | Medium |
| **N-10** | `OPEN` and `RESOLVED` both mean "nothing pending", differing only in whether a decision was ever required. Semantically defensible but may confuse reviewers; worth confirming the pair earns its keep. | Low |

### Carried forward

| ID | Status after this pass |
|----|------------------------|
| **B-1** | ✅ **Resolved** — J-3 Option B approved |
| **B-2** | ✅ **Resolved** — D-1.3 records the convention explicitly |
| **B-3** | ✅ **Resolved** — D-4.1 transitions + D-3.6; no fifth status value needed, "partially decided" is derived, not stored |
| **B-4** | ✅ **Resolved** — AM-7 (pending approval of the amendment) |
| **B-5** | ✅ **Resolved** — D-5.1 – D-5.3 |
| **B-6** | ⏳ **Open** — AM-8 – AM-11 unapproved; 45B cannot be re-locked. **Critical** |
| **B-7** | ✅ **Resolved as specification** (EV-MIN, D-3.4); enforcement open as N-9 |
| **B-8** | ⏳ **Open** — `evaluation_evidence` unapproved. **Critical** |
| **B-9** | ⏳ **Open** — second-person approval at Evaluation or Finding level (Step 31 r15) |
| **B-10** | ⏳ **Open** — escalation now needs a target level: does a user escalate a Finding or an Evaluation? J-3 makes this sharper, not resolved |
| **B-11** | ⏳ **Open** — Step 35 band → mapping-state mapping, deliberately deferred |
| **B-12** | ⏳ **Open** — `UNMATCHED_PROVISION` persistence |
| **B-13** | ✅ Proposed as DB-6, unapproved |
| **B-14** | ⏳ **Open** — Step 33 provisional |
| **B-15** | ⏳ **Open** — authentication implementation. **Critical, independent** |

---

# 11. Recommended next step

**Resolve N-1 first.** It is the only item where a **locked rule is currently unimplementable**: Step 31 r20 mandates that the current decision be distinguishable from historical ones, and the decision table cannot express that. Every other open item is a design choice; this one is a contradiction between a locked rule and a locked schema, and it sits directly on the J-3 path since "current decision" is load-bearing in D-3.6.

Suggested order:

```text
N-1  (locked rule unimplementable)
  ↓
N-3  (canonical decision-record field names — resolve alongside N-1, same table)
  ↓
B-6 / B-8  (approve AM-8 – AM-11 and evaluation_evidence)
  ↓
N-8, N-9, B-9, B-10  (widen-only rule; EV-MIN enforcement; approval and escalation levels)
  ↓
N-4  (UNRESOLVED occupancy)
  ↓
re-lock 45B  →  lock 45C  →  45D golden tests
```

B-15 (authentication) remains independent and blocks any deployable system regardless of the liability track.
