# Analysis Orchestrator — what is specified, what is not

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a
> conclusion was reached and decides nothing. A conclusion is authoritative only
> where it appears in [LOCKED_DECISIONS.md](../../00-project/LOCKED_DECISIONS.md)
> and `all_lock.md`. Do not implement from this file.

**Prepared 2026-08-17.** Scope: determine precisely what the missing analysis
orchestrator needs, which of those needs locked decisions already answer, and which
genuinely require an owner decision. No audit is reopened; no decision is proposed
as settled.

Basis: locked Steps 28, 34, 35, 36, 44, 45B, 45C, 45D · `REC-02`, `REC-03` ·
`ENG-09`, `ENG-11` · the implementation in `backend/legalmind/{mapping,evaluation}/`.

> **§2 and §3 describe the state at the time of the investigation.** `D-1` – `D-4`
> were subsequently decided and implemented — see **§8** for what was built and for
> two findings the live run produced.

---

## 1. The finding that matters most

**The deferred Step 35 band → mapping-state mapping does not block the
orchestrator, and does not need to be decided to build it.**

`REC-03` (🔒) already establishes the two halves that matter:

> Step 28's mapping states are the canonical **persisted** mapping vocabulary:
> `CONFIRMED` / `AMBIGUOUS` / `UNRESOLVED`.
>
> Step 35's vocabulary (`CANDIDATE`, `CANDIDATE-REVIEW`, `NOT MAPPED`,
> `NO_CONFIDENT_MAPPING`) consists of **internal scoring-stage labels**, not
> persisted states.

and then defers only the *correspondence* between them:

> **NOT YET SPECIFIED — explicitly deferred:** how Step 35's scoring bands map onto
> Step 28's three persisted states. It is **not** established whether
> `CANDIDATE-REVIEW` corresponds to `AMBIGUOUS`, to `UNRESOLVED`, or to neither.
> This must not be inferred or implemented until explicitly decided.

A correspondence is only needed by something that has to **convert** a band label
into a persisted state. Nothing does:

* Locked Step 28 defines its three states **semantically**, not numerically —
  `CONFIRMED` is "sufficient deterministic evidence", `AMBIGUOUS` is "more than one
  plausible mapping exists and LegalMind must not silently choose one",
  `UNRESOLVED` is "cannot establish the mapping reliably". These are conditions an
  engine can evaluate directly.
* Locked 35.17 rule 8 requires only that mapping "distinguishes candidate matches
  from confirmed mappings". A distinction drawn internally satisfies it; nothing
  locked requires a band **label** to be emitted or stored.
* The implementation already does exactly this. `mapping/engine.py` derives state
  from Step 28's own definitions and produces no band vocabulary at all.

**Consequence:** the deferral can remain deferred indefinitely without blocking
anything, *provided* the owner accepts that persisted Mapping State is derived from
Step 28's semantics rather than from a Step 35 band. That is a confirmation, not a
new decision — `REC-03` says bands are not persisted states.

**What is genuinely missing from that layer is different and smaller:** a *numeric
confirm threshold*, which locked 35.9/35.10 deliberately left unlocked and told us
how to obtain — "validated against a representative contract test set". That is a
data dependency, not a policy question. See §4 D-1.

---

## 2. What the orchestrator must do, layer by layer

Locked 44.2 / 44.40 fix the pipeline. Each row states what is locked and what
exists.

| Layer | Locked basis | State |
|---|---|---|
| 1 Text normalization | 44.3, 34.x | ✅ implemented (`ingestion/parsing.py`) |
| 2 Structural parsing | 44.4, 34.x | ✅ implemented |
| 3 Requirement mapping | 44.5, Steps 28, 35 | ⚠️ implemented, but the confirm threshold is an invented default — see §3 |
| 4 Evidence selection | 44.9, 35.18, Step 28 r7 | ✅ mapping returns `evidence_ids` |
| 5 Structured fact extraction | 44.10, 44.11, 44.17, 45B `facts.caps[]` | ❌ **not implemented** — the real code gap |
| 6 Negative patterns | 44.16, 35.5 | ✅ implemented in scoring |
| 7 Conflict detection | 44.18, 45C | ✅ implemented in the evaluator |
| 8 Evaluation | 44.25–44.28, 45B, 45C, 45D | ✅ implemented (both locked evaluators) |
| 9 Finding + Evaluation persistence | AB-1, 42.14–42.16 | ✅ implemented (`evaluation/service.py`) |
| 10 Review lifecycle advance | Step 30 r6, r16 | ✅ implemented (`workflow/review_lifecycle.py`) |

**Layer 5 is authorized to build now.** Locked 44.29 places "fact extraction
algorithms" in Python code and configuration in "thresholds, allowed values,
patterns, terminology, rule parameters". Locked 44.30 names the techniques
explicitly: regex/pattern matching for structured values ("6 months", "12 months",
"USD 5,000") and finite-state/rule-based extraction for legal patterns ("shall not
exceed X"). Locked 44.11 requires it to be requirement-specific. Locked 45B fixes
the output shape and 44.17 requires the general-rule-plus-exceptions structure to be
preserved rather than flattened.

So layer 5 needs **no owner decision** — only the patterns and terminology it
matches, which are configuration, and which for `LIABILITY-001` means real Company
Standard material eventually. It can be built and unit-tested against structural
fixtures before that.

---

## 3. One defect found, not a decision

`mapping/rules.py` defines `DEFAULT_CONFIRM_THRESHOLD = 5` and
`DEFAULT_TIE_MARGIN = 0`, and `MappingRules.from_config` falls back to them when the
configuration omits the key.

That contradicts **`ENG-09`** (every absent configuration value fails closed, never
defaults) and sits awkwardly beside locked 35.10. The comments mark the values
PROVISIONAL, but a comment does not stop them executing: a mapping rule version that
omits `confirm_threshold` today silently gets 5, and would silently produce
`CONFIRMED` and `UNRESOLVED` states from a number nobody decided.

It is currently harmless only because nothing calls `run_mapping` on the
authoritative path. **An orchestrator would put it there.** Fixing it is an ENG-09
conformance repair, not a policy change: an absent threshold should refuse to map.

---

## 4. What genuinely requires an owner decision

Four items. Nothing else in the orchestrator is blocked.

### D-1 · The mapping confirm threshold — how to obtain it

Locked 35.9 declines to lock numerical thresholds; 35.10 says they "should be
validated against a representative contract test set before being locked".

The question is not *what number* — it is *what the engine does until there is one*.
Options in §5.

### D-2 · Is persisted Mapping State a column, or is JSONB sufficient?

`REC-03` calls `CONFIRMED`/`AMBIGUOUS`/`UNRESOLVED` the canonical **persisted**
mapping vocabulary. Locked Step 28's pipeline shows "Mapping Status" as a stage
output. **No locked table carries it:** 42.x has no `mapping_state` column and no
`MAPPING_STATE` enum type.

Today the `PRESENCE` evaluator writes it into `evaluations.result.evaluated_facts`
as `{"mapping_state": ...}`. The `NUMERIC_COMPARISON` evaluator does not write it at
all, so for a liability Requirement a replay cannot show what mapping concluded.

This is a schema question, so it needs a decision either way — including the
decision to leave it in JSONB.

### D-3 · Where does Requirement applicability (REQUIRED / OPTIONAL) come from?

This one is **load-bearing and currently unsourced.** Locked Step 28's Requirement
model lists "Required / Optional", and locked 45D's `PRESENCE` table makes
applicability a direct input:

```text
mapping_state  applicability   classification          evidence
-------------------------------------------------------------------
NONE           REQUIRED        MISSING                 0 permitted
NONE           OPTIONAL        no Finding produced     —
```

`requirement_versions` (42.7) has no such column, and no configuration key is
specified for it. The golden-corpus runner reads a fixture key defaulting to `True`;
production has nothing to read. Without a source, an optional Requirement with no
matching provision would produce a `MISSING` Finding where locked `F-1` says it must
produce **no Finding at all**.

### D-4 · Should the orchestrator record `UNMATCHED_PROVISION` observations?

`REC-02` (🔒) records the persistence model, surfacing and review treatment of
`UNMATCHED_PROVISION` as **NOT YET SPECIFIED**. The `unmatched_provisions` table
exists (AB-1 / `F-10`) and the report endpoint already counts rows in it, but nothing
writes any. Leaving it empty is a defensible reading of the deferral; deciding to
populate it is a decision.

---

## 5. Minimum options, with consequences

### D-1 — the confirm threshold

| Option | Behaviour | Consequence |
|---|---|---|
| **D-1a** Threshold is **required configuration**; mapping refuses to run when absent | A Requirement version without `confirm_threshold` fails closed: no mapping, no Finding, and the Review reports the configuration as incomplete | Strictly `ENG-09`-conformant. Nothing is ever mapped by an undecided number. Cost: no Requirement can be evaluated until the owner enters a threshold per Requirement — and entering one before calibration is exactly what 35.10 warns against, so this makes the corpus the gate |
| **D-1b** Threshold required, but an absent threshold yields `UNRESOLVED` rather than refusing | Analysis runs; every Requirement lacking a threshold produces `UNRESOLVED` → `UNABLE_TO_EVALUATE` per Step 28 r6 | Fail-closed in the legal sense (never a guess, never a MISSING) while still exercising the whole pipeline end to end. Cost: a Review full of `UNABLE_TO_EVALUATE` looks like a malfunction unless the report explains it |
| **D-1c** Keep a provisional default in code, marked PROVISIONAL | Current behaviour | Violates `ENG-09` and puts an undecided number on the authoritative path. **Not recommended** — recorded only because it is the status quo |

*Note: none of these sets a threshold value. Calibration still needs a
representative contract set (35.10), and that is a later, separate request.*

### D-2 — Mapping State persistence

| Option | Consequence |
|---|---|
| **D-2a** Leave it in `evaluations.result.evaluated_facts`, and require **both** evaluators to write it | No schema change, no amendment. Reproducibility is satisfied because the value is in the append-only Evaluation record. Cost: it is not queryable as a column, so "show me every AMBIGUOUS mapping" needs a JSONB query |
| **D-2b** Amend the schema: add `mapping_state` + a `MAPPING_STATE` enum type on `evaluations` | Matches `REC-03`'s word "persisted" most literally and makes the axis queryable and constrained by the database. Cost: **an amendment batch** — a new enum type on the five-axis model (`REC-06` requires its own type), plus a migration |
| **D-2c** A dedicated `requirement_mappings` table per (Review, Requirement version) | Records mapping as its own stage output, which is what Step 28's pipeline depicts, and holds candidates and scores for replay. Cost: a new table, the largest of the three, and it duplicates what the Evaluation already carries |

### D-3 — Requirement applicability

| Option | Consequence |
|---|---|
| **D-3a** A key in `company_standard_versions.configuration`, e.g. `{"applicability": "REQUIRED"}` | No schema change; applicability is versioned and snapshot-pinned with the rest of the Standard, which is right — whether a clause is required *is* a Company Standard statement. Cost: it is a JSONB key, so a typo degrades to fail-closed rather than being rejected at write time |
| **D-3b** Amend `requirement_versions` with a `required BOOLEAN NOT NULL` column | Matches Step 28's Requirement model most literally and cannot be mistyped. Cost: an amendment to a locked table (42.7) |
| **D-3c** Treat every Requirement as REQUIRED in V1 and defer optionality | Zero work, and `F-1`'s optional-absent branch simply never fires. Cost: locked 45D's `PRESENCE` table has an OPTIONAL row that becomes unreachable, so a locked behaviour would ship untested and unusable |

**Whichever is chosen, fail closed on absence** — treat an unstated applicability as
REQUIRED, because that direction produces a Finding for review rather than silently
producing nothing.

### D-4 — `UNMATCHED_PROVISION`

| Option | Consequence |
|---|---|
| **D-4a** Do not write any; leave the table empty | Honours `REC-02`'s deferral exactly. The report shows 0 and the number is truthful about what was recorded, not about the document |
| **D-4b** Write one row per clause that matched no Requirement above threshold | Step 8's "which clauses were reviewed" gains real content. Cost: decides part of what `REC-02` deferred, and the count is meaningless while D-1 is unresolved, since "matched no Requirement" depends on the threshold |

---

## 6. What is *not* being asked

To keep the decision surface minimal, these were checked and found already settled:

* **The band → state mapping** — stays deferred; see §1.
* **Fact extraction** — authorized by 44.29/44.30; needs no decision, only building.
* **Conflict detection, scope grouping, roll-up, decision requirement, lifecycle
  advance** — all locked and implemented.
* **Evaluator vocabulary** — exactly two types (`AM-16`); no third is needed.
* **Where facts are persisted** — `evaluations.result.evaluated_facts`, locked by
  45B's output contract.
* **Real legal documents** — not required to *build* the orchestrator. Required to
  *calibrate* D-1's threshold and to author `NORMATIVE` fixtures. Deliberately not
  requested yet.

---

## 7. If all four are decided

The remaining work is implementation only, in this order:

```text
1. Fix the ENG-09 threshold defect (§3)
2. Liability fact extractor  — 44.10/44.11/44.17 -> 45B facts.caps[]
3. Orchestrator              — mapping -> extraction -> evaluation -> persist
4. Analysis submission       — the 49.8 Idempotency-Key endpoint
5. Frontend analysis state   — Step 30 lifecycle as the single progress source
```

Steps 2 and 3 are the substance. Nothing in them needs a locked decision beyond the
four above.

---

# 8. Implementation record — 2026-08-17

`D-1` – `D-4` were decided by the owner and implemented. **`D-1`: refuse at publish
time**, with a second check at analysis time. No schema change; nothing appended to
`all_lock.md`.

§1's conclusion held in practice: the band → state deferral was never consulted, and
no band vocabulary is produced or persisted anywhere.

## Two things the live run revealed

**1. A flat weight scheme ties easily, and a tie is `AMBIGUOUS`.**

A real three-paragraph liability clause, mapped with three configured exact phrases
and no keyword group, scored **5 / 5 / 5** — one phrase matched per paragraph. All
three tied at the top, so the engine reported `AMBIGUOUS`, extracted no facts, and the
evaluator returned `UNABLE_TO_EVALUATE`. Adding one keyword group made the substantive
clause score 8 and the same document came out `CONFIRMED`.

The pipeline behaved correctly and failed closed. But it means **whether a real
document yields a Finding at all is highly sensitive to per-Requirement weights and
thresholds** — which is precisely the calibration locked 35.10 defers to "a
representative contract test set". This is empirical support for the owner's deferral,
not an argument against it.

**2. `_is_ambiguous` may be reading Step 28's `AMBIGUOUS` more broadly than the
locked text does. Reported, not changed.**

`mapping/engine.py` treats *several qualifying clauses tied within `tie_margin` for
one Requirement* as `AMBIGUOUS`, reasoning that choosing a single governing clause
would be arbitrary. Two locked rules sit against that reading:

* **Step 28 r2** — "One Requirement may be supported by multiple clauses."
* **35.12** — the same, restated.

If multiple supporting clauses are normal, then no single governing clause has to be
chosen — and `map_requirement` already retains *all* qualifying candidates rather than
picking one. The arbitrary choice the tie rule guards against is never actually made,
which undercuts the justification for treating a tie as ambiguity.

Step 28's own words are "More than one plausible **mapping** exists and LegalMind must
not silently choose one." That reads more naturally as *this clause plausibly maps to
two different Requirements*, or *the evidence is genuinely undecidable* — not as
*two clauses both support this Requirement*.

**Why this is not being changed here.** Loosening the tie rule would move mapping
states from `AMBIGUOUS` toward `CONFIRMED`, which moves outcomes from
`UNABLE_TO_EVALUATE` toward real classifications. That is the direction in which a
silent change is most dangerous: it manufactures legal conclusions where the current
code refuses to. It is a question about what locked Step 28 means, so it is an owner
decision (rule 5).

**If it is to be revisited, the minimum options are:**

| | Behaviour | Consequence |
|---|---|---|
| **M-1** | Leave as built — a tie within `tie_margin` is `AMBIGUOUS` | Most conservative. Real documents will frequently be `UNABLE_TO_EVALUATE` until weights are calibrated, and Tier 1 means each one requires a Legal Decision (`D-3.5(b)`) — so an uncalibrated deployment generates Legal workload |
| **M-2** | Ties are `CONFIRMED` with all tied clauses retained as supporting evidence (Step 28 r2 / 35.12); `AMBIGUOUS` is reserved for a clause plausibly mapping to **different Requirements** | Matches r2's plain wording and stops flat configurations from stalling. Requires cross-Requirement ambiguity detection, which does not exist yet — `map_requirement` scores each Requirement independently |
| **M-3** | Keep the tie rule but make `tie_margin` express intent per Requirement, calibrated with the thresholds | No semantic change; folds into the 35.10 calibration exercise. Leaves the r2 tension unresolved on paper |

Nothing here should be inferred. `mapping/engine.py` behaves as **M-1** today.


---

# 9. `M-2` decided and implemented — 2026-08-17

**Owner decision: `M-2`, with a safeguard.** Tied clauses supporting the same
Requirement are `CONFIRMED` at the mapping layer and all are retained as evidence
(Step 28 r2, 35.12). **Mapping `CONFIRMED` never means legal compliance.**
Contradictory facts continue downstream to the existing conflict evaluator and
produce `CONFLICT` / `DECISION_REQUIRED` as already locked. No new legal outcome; no
change to locked conflict semantics.

## Where the safeguard lives, and why that layer

Mapping does not assess contradiction, and must not: locked **Step 28 r8** keeps
Requirement mapping separate from Company Standard evaluation, and locked **44.18**
places conflict detection at layer 7, after fact extraction. Contradiction is a
property of *facts*, not of scores or text.

Verified end to end against a real document with two incompatible general caps:

```text
mapping                  CONFIRMED          (both provisions retained)
extraction               2 PRIMARY caps, scope GENERAL, 6.0 and 24.0 months
_resolve_same_scope      None               (materially different, no precedence)
Evaluation               CONFLICT / NOT_APPLICABLE
    explanation          "2 incompatible provisions govern scope GENERAL"
                         "no configured precedence rule resolves them"
                         "all conflicting provisions retained as evidence (45C.2)"
    evidence             2 rows, relationship_type = CONFLICTING
Finding                  CONFLICT -> DECISION_REQUIRED   (Tier 1, D-3.5(b))
Review                   LEGAL_REVIEW
```

**`M-2` makes conflict detection reachable rather than weaker.** Under the previous
rule the tie fired first: contradictory clauses produced `AMBIGUOUS`, no facts were
extracted, and the outcome was `UNABLE_TO_EVALUATE` — "we could not tell". 45C.2's
design of retaining every conflicting provision as `CONFLICTING` evidence was
unreachable.

## Consequence recorded, not worked around

**Nothing in V1 produces `MappingState.AMBIGUOUS`.** Cross-Requirement ambiguity —
one clause plausibly mapping to two different Requirements — is the case Step 28's
wording most naturally describes, and it is **not implemented**: `map_document`
scores each Requirement independently. The enum value remains because locked
Step 28 defines it and locked 45D's `PRESENCE` table has a row for it, and the
presence evaluator's unit tests still exercise it by constructing the state
directly. **No producer was invented.** Registered in
[IMPLEMENTATION_STATUS.md](../../00-project/IMPLEMENTATION_STATUS.md) § Pending
ratification.

## `tie_margin` — audited, retained pending the owner's review

`tie_margin` was the tolerance of the removed tie rule and is now **unread**. An
audit found it in:

| Surface | Result |
|---|---|
| `all_lock.md` | **zero references** — no locked decision names it |
| `docs/` | only this working document, describing `M-1`/`M-3` |
| Backend code | `rules.py` field / `from_config` / `to_config`; both `engine.py` uses were in the deleted rule |
| Tests | 2 references |
| Corpus fixtures · frontend · Alembic | none |
| API schema / OpenAPI | not named; `mapping_rules` is an opaque `dict[str, Any]` |
| Persisted configuration | 1 `mapping_rule_versions` row exists; **0 rows carry the key** |

**Migration impact: none.** No schema change (JSONB key), no data migration, no API
contract change. Reproducibility is unaffected — a historical Review replays from its
pinned mapping rule version, no pinned row carries the key, and under `M-2` it is not
read even if one did.

**One risk if removed:** `from_config` ignores unrecognised keys, so a `tie_margin`
written later would be silently ignored rather than rejected. That is a pre-existing
property of the loader; the honest fix is a separate change making mapping-rule
loading reject unknown keys.

**Retained for now** at the owner's instruction, accepted and round-tripped but not
read, and labelled as such in `rules.py`.
