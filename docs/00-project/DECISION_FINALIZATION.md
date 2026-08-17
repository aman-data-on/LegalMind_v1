# Decision Finalization — Path to Implementation Readiness

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a conclusion was reached, and its status lines describe the state **at the time of writing**, which has since changed. A conclusion is authoritative only where it appears in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) and `all_lock.md`. Do not implement from this file.

**Status: ⏳ FINALIZATION. `all_lock.md` unmodified (13,941 lines, md5 `66591e62`) — will not change until the amendment batch is approved.**

Prepared 2026-08-17. Mode: decision finalization, not audit. Every item below is classified **LOCK NOW · FIX BEFORE LOCK · NEEDS DECISION · IMPLEMENTATION TASK · DEFERRED V1+**. No item is left open merely because further discussion is imaginable.

Basis: [RECONCILIATION_PASS_6.md](../04-analysis-engine/EDGE_CASES/RECONCILIATION_PASS_6.md) · [PRESENCE_EVALUATOR.md](../04-analysis-engine/EDGE_CASES/PRESENCE_EVALUATOR.md) · [EVALUATOR_EDGE_CASES.md](../04-analysis-engine/EVALUATOR_EDGE_CASES.md) · Passes 2–5 · [EXTERNAL_REFERENCE_AUDIT.md](EXTERNAL_REFERENCE_AUDIT.md)

---

# 1. Resolved now by engineering judgment

Each resolved from locked decisions plus existing analysis. Rationale recorded; no further review needed.

### F-1 · N-35 — optional Requirement, no mapped provision → **no Finding**

Previously escalated. On review it is **determined by locked definitions**, not by policy:

* `MISSING` is excluded by **36.4** — "The Requirement is **expected**." An optional Requirement is not expected. Step 28 r5's "A **required** Requirement" qualifier confirms it.
* `MATCH` is excluded by **36.2** — "Customer **provision** conforms." There is no provision.
* A new enum value would amend REC-01, REC-06 and three schema definitions — disproportionate.

**Resolution:** no Finding, no Evaluation. Nothing was required, nothing found, nothing asserted. EV-MIN unaffected.
**Downstream:** Step 8's "which clauses were reviewed" is satisfied by **coverage reporting** (which Requirements the configuration snapshot evaluated) — an implementation task in the reporting step, alongside F-8/F-9.

### F-2 · B-9 — second-person approval (Step 31 r15) at **Evaluation** level

Decisions target Evaluations (J-3). A second approval of the *same decision* must target the same object, or the two could disagree about what was approved. No new state: a second `legal_decisions` row against the same `evaluation_id`, distinguished by `decision_type`/actor, with the configured requirement checked in the service layer.

### F-3 · B-10 — escalation recorded at **Finding** level

Locked Step 4 and Step 22 use Finding-level language ("escalate the contract/finding"). Escalation is a user request for review, not a disposition.

**Resolution:** escalation is recorded against the Finding and marks **every** Evaluation under it as requiring a decision (D-3.5 clause d). This preserves the locked user-facing vocabulary *and* the J-3 decision model with no new state and no ambiguity about what resolves the escalation.

### F-4 · N-8 — configuration may only **widen** decision requirements

Reconciles Step 27 r12 (severity is configuration-driven) with ENG-09 (fail-closed). Configuration may add decision requirements; it may never remove one the baseline imposes. **Adopted.**

### F-5 · N-9 — EV-MIN enforced by a **deferred constraint trigger**

`DEFERRABLE INITIALLY DEFERRED`, checked at COMMIT so insert order is irrelevant. Chosen over a service invariant because EV-MIN is load-bearing (`legal_decisions.evaluation_id NOT NULL` depends on it) and a migration or backfill can bypass service code. Service-layer validation retained as a fast-fail guard.

### F-6 · N-17 — 45C.22 narrowing recorded

45C.22's "an explicit deterministic contractual rule **or** configured precedence rule" is narrowed by the approved B-5 decision to **configured precedence only**. In-document precedence language is detected, evidenced and reported — never applied. Recorded as an interpretation; **no amendment to 45C.22**.

### F-7 · N-21 — golden corpus becomes its own step

The 45D scope change displaced the liability golden test cases. They become **Step 45E — Golden Corpus**, covering liability and presence together. Resolves the discrepancy without reinterpreting anything.

### F-8 · N-32 — risk is a **configured display mapping**, not engine output

Locked 36.10 forbids a risk score "as the primary V1 legal output"; locked Step 27 r12 requires risk be configuration-driven; locked Step 9 lists "High-level risk" as a report element.

**Resolution:** risk is a configured mapping from `(classification, rule_outcome)` to a display label, owned by the **reporting layer**, versioned as configuration under Step 29. The evaluator emits no risk field. The label values are configured by authorized Legal admins — **no legal policy is invented here**.

### F-9 · N-33 — overall alignment is a reporting aggregation

A ratio over evaluated Requirements by classification, computed in the reporting layer. Not an evaluator output, carries no legal meaning, and cannot alter a Finding.

### F-10 · B-12 — `UNMATCHED_PROVISION` persistence

REC-02 makes it a document-level observation, not a Finding classification. Simplest representation that keeps it out of `findings`:

```text
unmatched_provisions
    id            UUID PK
    review_id     UUID FK → reviews.id
    evidence_id   UUID FK → document_evidence.id
    created_at    TIMESTAMPTZ NOT NULL
    PRIMARY KEY(id)
    UNIQUE(review_id, evidence_id)
```

New table, no amendment to any locked table. Surfacing is a reporting concern.

### F-11 · N-23 — closed

Superseded. The vocabulary is now two values, both exercised in V1. There are no unexercised evaluator types.

### F-12 · N-16, N-14, N-37, N-36, AM-18, A-2 — closed in Pass 6

Accepted as resolved; not reopened.

---

# 2. Amendment batch — **requires your approval**

Thirteen amendments, presented as one batch because they touch two tables and must land together. None changes legal meaning; all repair representational gaps in locked decisions.

| ID | Locked item | Amendment | Driver |
|----|-------------|-----------|--------|
| **AM-1** | 42.17 `legal_decisions` | `evaluation_id UUID FK → evaluations.id NOT NULL`; composite FK `(finding_id, evaluation_id)` → `evaluations(finding_id, id)` | J-3 |
| **AM-12** | 42.17 | `version_number INTEGER NOT NULL`; `UNIQUE(evaluation_id, version_number)` | N-1 |
| **AM-15** | 42.17 | `justification TEXT NOT NULL` (Step 31 r11 currently unenforced) | N-15 |
| **AM-13** | 41.21 | Same two fields, keeping 41 and 42 aligned | N-1, J-3 |
| **AM-14** | 40.12 | `evaluationId`, `versionNumber` | N-1, J-3 |
| **AM-8′** | 42.15 `evaluations` | `scope_key VARCHAR NOT NULL`, `scope_label VARCHAR NULL`, `evaluation_kind EVALUATION_KIND NOT NULL`, `rule_outcome RULE_OUTCOME NOT NULL` | A-1, A-3, J-2 |
| **AM-19** | 42.15 | `evaluator_version VARCHAR NOT NULL` (locked 45B.10 requires it) | N-13 |
| **AM-20** | 42.15 | `legal_rule_version_id UUID FK → legal_rule_versions.id NULL` (Step 32 audit q4 currently unanswerable) | N-12 |
| **AM-16** | 42.7 / 42.11 / 42.15 | Define `EVALUATOR_TYPE` = `NUMERIC_COMPARISON`, `PRESENCE` | N-18 |
| **AM-2** | Step 31 r17 | "A Legal Decision resolves the relevant **Evaluation**; a Finding is resolved when every Evaluation requiring a decision has a current decision" | J-3 |
| **AM-5** | Step 31 r4 | `ACCEPT_DEVIATION` applies to the specific Review/Finding/**Evaluation** | J-3 |
| **AM-6** | Step 31 r16 | Legal must be shown **every scoped Evaluation** with its applicable Legal Rule | J-3 |
| **AM-7** | Step 36.7 | Remove "or a required action is missing"; adopt the D-6.2 wording | J-6, N-11 |

**New tables (no amendment):** `evaluation_evidence` (B-8, zero rows permitted), `unmatched_provisions` (F-10).

**Withdrawn:** AM-18, AM-21, A-2-as-schema-change.

Step 31's decision vocabulary, definitions and rules 1–3, 5–15, 18–20 are untouched. Step 36's other classifications are untouched. **No legal policy changes.**

---

# 3. Requires your decision — product/legal only

| ID | Decision | Why it cannot be engineered | Blocks |
|----|----------|------------------------------|--------|
| **OD-9** | Authentication method — password, corporate SSO/OIDC, or integration with an existing identity system | Depends on the organization's identity estate, not on LegalMind's design | Any deployable system. **Does not block 45B/45C/45D** |
| **OD-2 / OD-3 / OD-4** | Super-role bypass and its relation to Legal Decision authority (ROLE-05); single vs multi-role; permission catalogue contents | Authority model is legal/organizational | Security track |
| **N-24b** | Which Requirements ship in V1 | Legal/product scope | Configuration, not code. Open by direction |

**Nothing in this list blocks the evaluator track.**

---

# 4. Classification of every remaining item

| Item | Class |
|---|---|
| Amendment batch (13) | **LOCK NOW** — on approval |
| F-1 – F-12 resolutions | **LOCK NOW** — engineering, documented |
| 45B re-lock, 45C lock, 45D lock | **LOCK NOW** — after the batch |
| Step 45E golden corpus | **IMPLEMENTATION TASK** — next step after locks |
| Coverage reporting, alignment ratio, risk display mapping | **IMPLEMENTATION TASK** — reporting layer |
| `UNMATCHED_PROVISION` surfacing | **IMPLEMENTATION TASK** |
| B-11 Step 35 scoring thresholds | **IMPLEMENTATION TASK** — calibrated against the golden corpus; fail-closed defaults; owner's deferral of the band→state mapping stands |
| OD-9, OD-2/3/4, N-24b | **NEEDS DECISION** |
| OD-1, OD-5 – OD-8, OD-10 – OD-15 | **NEEDS DECISION** — security track, sequenced after OD-9 |
| B-14 Step 33 provisional items | **DEFERRED V1+** — locked 42.4 already provides `UNIQUE(contract_id, version_number)`; the three unlocked deltas are not required for V1 |
| Machine tokens, webhooks, MFA, multi-tenancy | **DEFERRED V1+** |

---

# 5. Targeted regression check

Only rules affected by §1 were re-checked.

| Resolution | Rules checked | Result |
|---|---|---|
| F-1 no Finding | 36.2, 36.4, Step 28 r5, Step 8, EV-MIN, REC-01 | ✅ |
| F-2 approval at Evaluation | Step 31 r15, J-3, 42.17 | ✅ |
| F-3 escalation at Finding | Step 4, Step 22, D-3.5, D-4.1 | ✅ |
| F-4 widen-only | Step 27 r12, ENG-09 | ✅ |
| F-5 deferred trigger | 42.21, EV-MIN | ✅ |
| F-8 risk mapping | 36.10, Step 27 r12, Step 9 | ✅ |
| F-10 unmatched table | REC-02, 42.14 | ✅ |

**No new contradictions.**

---

# 6. Shortest path

```text
1. APPROVE the amendment batch (§2)          ← one decision
       ↓
2. Apply amendments to all_lock.md + docs    ← synchronize master record,
   Re-lock 45B · Lock 45C · Lock 45D            registry, specs together
       ↓
3. Step 45E — Golden Corpus                  ← liability + presence fixtures
       ↓
4. Implementation Readiness Review           ← evaluator track complete
```

**In parallel, independent of the evaluator track:**

```text
Security track:  OD-9 → OD-2/3/4 → remaining OD items → Step 47
Then:            API finalization → frontend → observability → testing → deployment
```

**Step 2 is a single synchronized operation** — `all_lock.md`, `LOCKED_DECISIONS.md`, `IMPLEMENTATION_STATUS.md`, `CONFLICTS.md` and the affected specifications updated together, so the master record and the docs tree never diverge.

The evaluator track needs **one approval** to reach the golden corpus. The security track needs **one decision (OD-9)** to start. Those two are the critical path; everything else is implementation work.
