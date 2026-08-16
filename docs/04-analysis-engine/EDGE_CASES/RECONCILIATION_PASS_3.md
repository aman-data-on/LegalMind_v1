# Reconciliation Pass 3 — N-1 / N-3 repair + full impact audit

**Status: ⏳ PROPOSAL — NOTHING LOCKED. `all_lock.md` not modified (13,941 lines, md5 `66591e62`). No historical locked text changed.**

Prepared 2026-08-16. Loop stage: **RECONCILE → REPAIR → CROSS-AUDIT → RECHECK → *(lock withheld)***.

Related: [RECONCILIATION_PASS_2.md](RECONCILIATION_PASS_2.md) · [OPEN_DECISIONS_ANALYSIS.md](OPEN_DECISIONS_ANALYSIS.md) · [LIABILITY_CONTRACT_AMENDMENTS.md](LIABILITY_CONTRACT_AMENDMENTS.md) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

---

# 1. N-1 decision — decision supersession

## The contradiction

Step 31 r14 requires decision history to be immutable, with later changes creating a new version. Step 31 r20 requires the current decision to always be distinguishable from historical ones. The locked `legal_decisions` table — in all three definitions (40.12, 41.21, 42.17) — provides no version, supersession pointer, or current flag. **A locked rule is unimplementable against the locked schema.**

## Alternatives evaluated

| Dimension | **A** `superseded_by_id` | **B** `is_current` + partial unique | **C** `version_number` | **D** hybrid (C + explicit `supersedes_id`) |
|---|---|---|---|---|
| Legal semantics | Explicit "replaced by" chain | Binary current/historical; no lineage | **Matches Step 31 r14's own words — "creates a new decision version"** | Same as C, plus redundant pointer |
| Historical reconstruction | Full chain via traversal | Ordering only by `created_at` | Natural total order per Evaluation | Full |
| Auditability | Good, but chain lives in mutable fields | Weakest — a flipped boolean carries no history | **Strong — nothing is ever rewritten** | Strong |
| Reproducibility | Good | Good | **Strongest — append-only** | Good |
| **Concurrent updates** | Two concurrent supersessions can leave two rows with `NULL` unless a partial unique index is added; lost-update risk on the pointer | Lost update can silently produce two currents unless the flip+insert is atomic | **Two concurrent supersessions both compute `N+1` → unique violation → one fails and retries. No lost update is possible.** | Same as C |
| Database integrity | Enforceable via partial unique index `(evaluation_id) WHERE superseded_by_id IS NULL` | Enforceable via partial unique index `(evaluation_id) WHERE is_current` | Enforceable via plain `UNIQUE(evaluation_id, version_number)` — no partial index needed | Same as C |
| **Mutation of historical rows** | **Required** — writes into a prior decision row | **Required** — flips a prior row's flag | **None** — prior rows are never touched | None |
| API behavior | Current = `superseded_by_id IS NULL` | Current = `is_current` | Current = `MAX(version_number)` per Evaluation | Same as C |
| Authorization | Equivalent across all options | Equivalent | Equivalent | Equivalent |
| Reviewer workflow | Chain display natural | Simple but lineage-poor | Version numbers are directly meaningful to reviewers ("decision v2") | Same |
| Rollback | New row pointing back | Flip flags — mutates history | New version restating the earlier position; the superseded version remains intact | Same |
| Deletion | Chain breaks if a row is removed | Flag orphaned | Consistent with 41.26's no-casual-hard-delete stance | Same |
| Re-review | New Review → new Findings/Evaluations → fresh version sequence | Same | Same | Same |
| Complexity | Medium — pointer maintenance | **Lowest** | Medium — current requires `MAX()`/window | Highest |
| Extensibility | Chain generalizes | Poor | Versioning generalizes to other versioned records | Redundant |

## Selected model: **Option C — `version_number`, append-only**

**Not selected for ease of implementation** — Option B is materially easier and was rejected.

### Rationale, from locked principles

1. **Step 31 r14 already names the model.** Its locked text says a later change "creates a new decision **version** rather than overwriting the previous decision." Options A and B both require writing into a previously-recorded decision row. Option C is the only one that never overwrites anything, which is what r14 literally requires.
2. **Append-only matches the locked audit posture** (AUD-01, Step 25, Step 32). A legal decision record is evidentiary; mutating it — even a flag — weakens the guarantee that history is what it says it is.
3. **Concurrency safety is strictly better.** Under A or B, two reviewers acting simultaneously can produce two current decisions through a lost update. Under C the database rejects the second write outright, because both attempts claim the same `version_number`. Correctness comes from the constraint, not from application discipline.
4. **`is_current` is a denormalized derived flag** — the same category of construct Step 30 r16 warns against when it cautions against manually editable final-result fields. `MAX(version_number)` cannot drift from reality; a boolean can.

### Specification

```text
legal_decisions
    version_number   INTEGER NOT NULL
    UNIQUE(evaluation_id, version_number)

Current decision for an Evaluation
    = the row with MAX(version_number) for that evaluation_id

First decision           version_number = 1
Each supersession        version_number = previous + 1
Prior rows               never updated, never deleted
```

`supersedes_id` is **deliberately excluded** — it is derivable from `(evaluation_id, version_number − 1)` and would be a second source of truth for the same relationship.

Read performance is addressed with an index on `(evaluation_id, version_number DESC)` and, if needed, a read-only view — neither changes semantics.

### Required amendments

| ID | Item | Change |
|----|------|--------|
| **AM-12** | 42.17 `legal_decisions` | Add `version_number INTEGER NOT NULL`; add `UNIQUE(evaluation_id, version_number)` |
| **AM-13** | 41.21 `legal_decisions` | Same field, keeping 41 and 42 aligned |
| **AM-14** | 40.12 `LegalDecision` | Add `versionNumber` |

Step 31 r14 and r20 need **no** amendment — Option C implements them as written. That is the strongest argument in its favour.

---

# 2. N-3 normalization — canonical Legal Decision model

## Historical definitions (unchanged, preserved)

| Field | 40.12 | 41.21 | 42.17 | Step 31 |
|---|---|---|---|---|
| id | `id` | `id` | `id UUID PK` | — |
| parent Finding | `findingId` | `finding_id` | `finding_id UUID FK` | Finding-level |
| decision type | `decisionType` | `decision_type` | `decision_type DECISION_TYPE NOT NULL` | Locked vocabulary |
| reason | **`justification`** | **`decision_text`** | **`decision_text TEXT`** | r11: "requires a reason/comment" |
| actor | `decidedBy` | `decided_by` | `decided_by UUID FK` | r12 |
| timestamp | `createdAt` | `created_at` | `created_at TIMESTAMPTZ NOT NULL` | r12 |
| extra | **`metadata`** | — | — | — |
| vocabulary | — | **`REQUIRE_STANDARD`** | — | **`REQUIRE_COMPANY_STANDARD`** |

## Canonical implementation schema

```text
legal_decisions
---------------
id                UUID PK
finding_id        UUID FK → findings.id            NOT NULL
evaluation_id     UUID FK → evaluations.id         NOT NULL    (AM-1)
decision_type     DECISION_TYPE                    NOT NULL
justification     TEXT                             NOT NULL    (N-3)
decided_by        UUID FK → users.id               NOT NULL
version_number    INTEGER                          NOT NULL    (AM-12)
created_at        TIMESTAMPTZ                      NOT NULL

UNIQUE(evaluation_id, version_number)
FOREIGN KEY (finding_id, evaluation_id)
    REFERENCES evaluations(finding_id, id)
INDEX(evaluation_id, version_number DESC)
INDEX(decided_by)
INDEX(created_at)
```

### Field resolutions

**`justification` over `decision_text`.** Recommended because Step 31 r11 requires a *reason*, and `justification` names that purpose while `decision_text` describes only a datatype. Either name is defensible; **the substantive point is `NOT NULL`** — see N-15, where the locked schema currently leaves it nullable and therefore fails to enforce r11.

**`metadata` — drop.** Present only in 40.12, absent from both schema steps. An unstructured bag on a legal record invites exactly the domain-data-hidden-in-JSON pattern 42.1 r10 prohibits. Any genuine future need should be an explicit column.

**`REQUIRE_COMPANY_STANDARD` is canonical.** 41.21's `REQUIRE_STANDARD` appears under "For example" and is followed by "The exact final enumeration should be locked when we define the Legal Decision workflow." Step 31 *is* that workflow and locks the vocabulary. **This is a supersession, not a conflict — no amendment to 41.21 is required**, only a recorded reconciliation note.

### Supersession / reconciliation relationship

```text
Step 40.12   conceptual domain model      superseded on field naming by 42.17 + canonical
Step 41.21   illustrative schema          superseded on vocabulary by Step 31
Step 42.17   exact schema                 canonical structure, amended by AM-1/AM-12
Step 31      workflow + vocabulary        canonical for decision types and rules
```

### Does any locked decision need amendment?

| Item | Verdict |
|---|---|
| 41.21 `REQUIRE_STANDARD` | **No** — explicitly illustrative and self-deferring to Step 31 |
| 40.12 `justification` vs 42.17 `decision_text` | **No amendment strictly required** — a canonical-naming note suffices; but see N-15 |
| 40.12 `metadata` | **No** — dropping it from the canonical schema needs a note, not a text change |
| `justification NOT NULL` | **Yes — AM-15**, because Step 31 r11 is otherwise unenforced (N-15) |

---

# 3. Cross-document audit

| Step | Subject | Status | Note |
|------|---------|--------|------|
| 27 | Finding generation & lifecycle | **CONSISTENT** | r9/r12/r16 all hold under the Evaluation model |
| 30 | Lifecycle separation | **CONSISTENT** | r1, r7, r16, r17 support derived Finding status |
| 31 | Legal Decision model | **REQUIRES AMENDMENT** | AM-2, AM-5, AM-6, AM-15. r14/r20 need **no** change under Option C |
| 32 | Evidence / explainability | **CONSISTENT** | Explicitly contemplates `AMBIGUOUS`/`UNRESOLVED`/`UNABLE_TO_EVALUATE` as produced states |
| 36 | Finding Classification | **OPEN** | AM-7 is now **contested** by Step 44.22 — see N-11 |
| 40 | Domain model | **REQUIRES AMENDMENT** | AM-4, AM-14 |
| 41 | Schema design | **REQUIRES AMENDMENT** | AM-3, AM-13; vocabulary superseded (N-2) |
| 42 | Exact schema & ERD | **REQUIRES AMENDMENT** | AM-1, AM-8, AM-12, AM-15; plus N-12/N-13/N-14/N-16 gaps |
| 44 | Analysis architecture | **OPEN** | **Internally contradictory** on `UNRESOLVED` — N-11 |
| 45A | Liability policy | **CONSISTENT** | §17 matrix assigns `UNRESOLVED` an occupant |
| 45B | Evaluator contract | **REQUIRES AMENDMENT** | AM-9, AM-10, AM-11; plus N-12/N-13 persistence gaps |
| 45C | Liability edge cases | **PROVISIONAL** | Additions 45C.27–45C.29; not lockable while N-11 is open |
| 33 | Contract versioning | **PROVISIONAL** | Unchanged from REC-04 |
| 35 | Mapping engine | **PROVISIONAL** | Band→state mapping deferred (B-11) |

### Canonical relationship table — the seven concepts remain separate

| Concept | Lives on | Cardinality | Set by | Locked source |
|---|---|---|---|---|
| **Review lifecycle** | `reviews.status` | 1 per Review | System + workflow | Step 30 |
| **Finding** | `findings` | 1 per (Review, Requirement Version) | Engine | 42.14 + DB-6 |
| **Evaluation** | `evaluations` | **≥1 per Finding** (EV-MIN) | Engine | 42.15 + D-3.4 |
| **Classification** | `evaluations.classification` (authoritative); `findings.classification` (derived summary) | 1 per Evaluation; 1 derived per Finding | Engine | Step 36, REC-01, D-1.1 |
| **Rule Outcome** | `evaluations.rule_outcome` **only** | 1 per Evaluation | Engine | 45B.14, D-2.1 |
| **Finding Status** | `findings.status` | 1 per Finding | Workflow (derived/human) | Step 30 r1, D-4.1 |
| **Legal Decision** | `legal_decisions` | 0..n per Evaluation, versioned | Authorized human only | Step 31, D-3.1 |

```text
Review ──1:n── Finding ──1:n── Evaluation ──0:n── LegalDecision (versioned)
                  │                 │
                  │                 └──n:m── Evidence   (evaluation_evidence)
                  └──────────────────n:m── Evidence     (finding_evidence, roll-up)
```

---

# 4. Database audit

| # | Constraint | Enforceability |
|---|---|---|
| 1 | `legal_decisions.evaluation_id NOT NULL` | **Database-enforced** |
| 2 | Decision's Evaluation belongs to the same Finding | **Database-enforced** — composite FK `(finding_id, evaluation_id)` → `evaluations(finding_id, id)`, requires `UNIQUE(id, finding_id)` on `evaluations`. Fully declarative; no trigger, no service check |
| 3 | `UNIQUE(evaluation_id, version_number)` | **Database-enforced**; also delivers concurrency safety |
| 4 | `justification NOT NULL` | **Database-enforced** (AM-15) |
| 5 | `UNIQUE(review_id, requirement_version_id)` on `findings` | **Database-enforced** (DB-6) |
| 6 | `evaluations.rule_outcome / scope / cap_kind NOT NULL` | **Database-enforced** |
| 7 | `evaluation_evidence` PK`(evaluation_id, evidence_id)` | **Database-enforced** (B-8, unapproved) |
| 8 | **EV-MIN** — every Finding has ≥1 Evaluation | **Deferred-constraint-enforceable** — see below |
| 9 | Evidence belongs to the Review's Document Version | **Service-enforced** — spans four tables; 42.21 explicitly permits domain-service validation where cross-table constraints become too complex |
| 10 | Finding status never user-set | **Service-enforced** + audited |
| 11 | Historical decisions never updated/deleted | **Service-enforced** (revoke UPDATE/DELETE at the role level; Option C requires neither) |
| 12 | Ownership traversal Evaluation → … → Owner | **Service-enforced** per 41.24/43.23; FKs make it traversable |
| 13 | No hard delete of Findings/Evaluations/Decisions | **Service-enforced**, per 41.26 |

### EV-MIN — recommended mechanism

Three candidates:

| Mechanism | Assessment |
|---|---|
| `DEFERRABLE INITIALLY DEFERRED` constraint trigger | Checks at COMMIT, so insert order inside the transaction doesn't matter. **True database enforcement; cannot be bypassed by any code path**, including future migrations and manual repair scripts |
| Transactional service invariant | Adequate while all writes go through the service, but a migration or backfill can silently violate it |
| `findings.evaluation_count` counter column | Denormalized; drift risk; rejected on the same grounds as `is_current` |

**Recommendation: the deferred constraint trigger**, with the service invariant retained as a fast-fail guard. EV-MIN is load-bearing — `legal_decisions.evaluation_id NOT NULL` depends on it — so it deserves enforcement the database itself guarantees. ⚠ This is documented database behavior, not invented: the mechanism and its timing semantics are stated here explicitly.

### Nullability review

`scope_label` nullable (only for `CATEGORY`/`EXCEPTION`). `evaluations.expected_value`/`actual_value` nullable per locked 42.15. `reviews.started_at`/`completed_at` nullable per locked 42.13. `justification` **must not** be nullable. `rule_outcome` **must not** be nullable (45B.26).

---

# 5. Evaluator audit

## Inputs

| Field | Type | Card. | Req. | Allowed | Evidence | Persisted | On failure |
|---|---|---|---|---|---|---|---|
| `requirement.{id,code,version_id}` | ids | 1 | Yes | — | — | via `findings.requirement_version_id` | Cannot run |
| `evidence[]` | objects | 0..n | Yes | — | self | `document_evidence` | Empty ⇒ `MISSING`/`UNABLE_TO_EVALUATE` |
| `facts.caps[]` | objects | 0..n | Yes | — | per-cap `evidence_refs[]` | `evaluations` (1 row/scope) | Empty ⇒ `MISSING` |
| `caps[].cap_kind` | enum | 1 | Yes | `GENERAL`,`EXCEPTION` | — | Yes | — |
| `caps[].scope` | enum | 1 | Yes | `AGGREGATE`,`PER_CLAIM`,`PER_EVENT`,`CATEGORY`,`UNKNOWN` | — | Yes | `UNKNOWN`+`scope_required` ⇒ `UNABLE_TO_EVALUATE` |
| `caps[].scope_label` | string | 0..1 | Cond. | — | — | Yes | — |
| `caps[].cap_status` | enum | 1 | Yes | `FINITE`,`UNLIMITED`,`ABSENT`,`UNKNOWN` | — | Yes | `UNKNOWN` ⇒ `UNABLE_TO_EVALUATE` |
| `caps[].cap_value/unit/basis` | scalars | 0..1 | Cond. | 45B.4 sets | — | Yes | Missing unit ⇒ `UNABLE_TO_EVALUATE` (45C.19) |
| `extraction_status` | enum | 1 | Yes | `COMPLETE`,`PARTIAL`,`AMBIGUOUS`,`FAILED` | — | Yes | `FAILED` ⇒ `UNABLE_TO_EVALUATE` |
| `extraction_diagnostics` | text/list | 0..1 | Yes (may be empty) | — | — | **⚠ no column — N-14** | Never alters outcome (REC-07) |
| `company_standard.{version_id,preferred_value,preferred_unit,scope}` | — | 1 | Yes | — | — | **⚠ not on `evaluations` — N-16** | Missing ⇒ cannot evaluate |
| `legal_rule.{version_id,…,rule_configuration}` | — | 1 | Yes | J-5 shape | — | **⚠ wrong FK target — N-12** | Absent config ⇒ fail closed |
| `evaluator_version` | string | 1 | Yes | — | — | **⚠ no column — N-13** | — |

## Outputs

`evaluations[]` — one per scope, each with `classification` (7 locked values), `rule_outcome` (4 values, `NOT_APPLICABLE` never null), `expected_value`, `actual_value`, `comparison`, `evaluated_facts`, `evidence_refs[]` (≥1), `explanation`, `diagnostics`. Plus derived `finding_classification` (D-1.2) and `evaluator_version`.

✅ **Confirmed: the evaluator produces no Legal Decision, no Finding status, and no resolution state** — verified against 36.15, 45A r18, 45B.14 and the proposed output shape. No field in the contract can carry one.

---

# 6. Precedence audit (B-5 re-verified)

| Rule | Requirement | Verdict |
|---|---|---|
| 45C.2 | Same-scope contradictory caps ⇒ `CONFLICT` unless a deterministic cross-reference establishes control | ✅ Configured precedence only |
| 45C.10 | Cross-references resolved only when deterministic | ✅ |
| 45C.11 | Conflicting cross-reference chains ⇒ `CONFLICT`, both traceable | ✅ Both chains retained as evidence |
| 45C.21 | Matrix rows for conflict and unresolvable cross-reference | ✅ |
| 45C.22 | No `first/latest/main-body/schedule wins` unless an explicit deterministic contractual rule **or configured precedence rule** establishes it | ⚠ See below |
| 45C.23 | No conversion without evidence | ✅ Unrelated but consistent |
| 44.29 | Comparison semantics and conflict mechanics stay in code | ✅ `precedence_rules` is declarative data only |

**Permitted:** detect precedence language, extract it, preserve it as evidence, report it, and apply **only** explicitly configured deterministic precedence relationships.

**Prohibited:** arbitrary precedence expressions, executable rule definitions, DSLs, code supplied through configuration, free-form legal interpretation, administrator-defined evaluation algorithms.

**Fail-closed output** when precedence language is detected but no configured rule resolves it:

```text
classification = CONFLICT
rule_outcome   = NOT_APPLICABLE
evidence       = each conflicting provision   (CONFLICTING)
               + the precedence clause itself (SUPPORTING)
diagnostics    = "precedence language detected; no configured rule applied"
explanation    = states the conflict was not resolved and why
```

⚠ **One residual tension.** 45C.22's phrase "an explicit deterministic contractual rule **or** configured precedence rule" can be read as permitting the *contractual* rule to be honoured directly from the document. The B-5 modification forbids that. The locked 45C text is not being changed — but the narrowing interpretation should be recorded explicitly rather than left to inference. Tracked as **N-17**.

---

# 7. Authorization audit

```text
Legal Decision → Evaluation → Finding → Review → Contract → owner_id → User → Role
```

| Requirement | Verdict |
|---|---|
| Possessing an `evaluation_id` grants nothing | ✅ Every access traverses to Contract ownership per 41.24/43.23; ids are never capabilities |
| Decisions require legal authority | ✅ Step 4/ROLE-05 — Admin ≠ approval authority; checked server-side (38.21) |
| Historical decisions readable per authorization | ✅ Same traversal; version history inherits the Finding's authorization |
| Superseded decisions cannot accidentally become current | ✅ **Structural under Option C** — "current" is `MAX(version_number)`, which no update can alter because prior rows are never written |
| Ownership isolation intact | ✅ 41.23 traversal unchanged; `evaluations` and `evaluation_evidence` add depth, not new roots |
| Internal legal position gated | ✅ `rule_outcome`, thresholds, `rule_configuration` permission-filtered (LEGAL-02) |
| Second-person approval (Step 31 r15) | ⏳ **OPEN (B-9)** — Evaluation-level or Finding-level undecided |

---

# 8. Audit / reproducibility audit

> **Can LegalMind reconstruct exactly what happened when a Legal Decision was made?**

**Not yet — four items are unrepresentable.**

| Element | Representable? |
|---|---|
| Requirement version | ✅ `findings.requirement_version_id` |
| Evidence references | ✅ `finding_evidence` + `evaluation_evidence` (B-8, unapproved) |
| Extracted facts | ✅ `evaluations.evaluated_facts` / `actual_value` |
| Finding classification | ✅ Derived + stored |
| Rule Outcome | ✅ After AM-8 |
| Decision actor & timestamp | ✅ `decided_by`, `created_at` |
| Decision history | ✅ After AM-12 |
| **Supersession chain** | ✅ After AM-12 (append-only versions) |
| Configuration context | ✅ `reviews.configuration_snapshot_id` |
| **Evaluator version** | ❌ **No column** — 45B.10 locks that it must be retained. **N-13** |
| **Legal Rule version** | ❌ `evaluations.rule_version_id` targets `evaluation_rule_versions`, but 45B feeds `legal_rule.version_id`. **N-12** |
| **Extraction diagnostics** | ❌ No column, though REC-07 locks that it is persisted. **N-14** |
| **Company Standard version** | ⚠ Only via the Review snapshot, not per Evaluation; 42.20's traceability path names it explicitly. **N-16** |

Step 32's five audit questions are answerable for 1–3 and 5; **question 4 — "Which Legal Rule was used?" — is not**, because of N-12.

---

# 9. API audit

| Operation | Shape | Notes |
|---|---|---|
| Retrieve Finding | Finding + derived `classification`, `status`, `requires_decision` + `evaluations[]` | Summary never returned without evaluations (D-1.4) |
| List Findings | Same, `evaluations[]` optionally summarized by count | Filter by status / `requires_decision` |
| Create Decision | Targets `evaluation_id`; server assigns `version_number` | No Finding-level decision endpoint may exist |
| Update Decision | **Does not exist.** Supersession = create with `version_number + 1` | Enforces r14 at the API surface |
| Current vs historical | Current = highest version; `?include=history` returns the full chain | Unambiguous |
| Concurrency | Client submits the expected next version; a `UNIQUE` violation surfaces as `409 Conflict` | **Optimistic concurrency comes free from the constraint** — no separate ETag/version header needed |
| Audit history | Decision versions + audit events | |
| Authorization | Object-level on every call (43.23) | 404 vs 403 semantics per 43.22 |

Endpoint naming remains unlocked (38.24).

---

# 10. Reviewer / UI audit

| Reviewer must understand | Backend can supply? |
|---|---|
| What each scope represents | ✅ `scope` + `scope_label` |
| Which Evaluation requires a decision | ✅ Derived per D-3.5 |
| Which decision is current | ✅ `MAX(version_number)` |
| Which are historical | ✅ Version chain |
| Why a Finding is unresolved | ✅ Enumerable — which Evaluations lack decisions |
| Why a Finding is `DECISION_REQUIRED` | ✅ D-3.5 gives the specific trigger, including escalation |
| Evidence per Evaluation | ⚠ **Requires `evaluation_evidence` (B-8)** — impossible today |
| Which Legal Rule version applied | ❌ **Blocked by N-12** |

**Two UI requirements currently exceed backend capability**, both traceable to unapproved/unresolved items rather than to UI over-reach.

---

# 11. Golden-corpus audit

All twelve required cases, each asserting **exact Evaluation outputs and** the derived Finding summary — never the roll-up alone.

| # | Case | Engine / Workflow | Status |
|---|---|---|---|
| 1 | General cap only | Engine | Ready |
| 2 | Multiple caps | Engine | Needs A-1 |
| 3 | Exception with its own cap | Engine | Needs A-3 |
| 4 | `MATCH` + `UNACCEPTABLE` scoped Evaluation | Engine | Needs A-1/A-3 |
| 5 | Partially decided Finding | **Workflow** | Needs J-3 |
| 6 | Decision superseded by a new decision | **Workflow** | Needs AM-12 |
| 7 | Precedence detected, not applicable | Engine | Needs J-5 |
| 8 | Deterministic configured precedence | Engine | Needs J-5 |
| 9 | Missing required Requirement | Engine | Ready |
| 10 | Extraction ambiguity | Engine | Ready |
| 11 | Unable to evaluate | Engine | Ready |
| 12 | Evidence attributed to individual Evaluations | Engine | **Needs B-8** |

Additional required cases: Tier-1 dominance; Tier-1 ordering fixtures **labelled as convention**; the negative-pattern matched pair (*"…not be limited in respect of fraud"* vs *"…not be limited"*); the four fail-closed paths; EV-MIN on every fixture; 45C.16/45C.17 duplicates ⇒ one Evaluation, two evidence refs.

Cases 5, 6 and 12 cannot be written today.

---

# 12. N-4 finding — `Classification.UNRESOLVED`

**Searched all 32 occurrences across `all_lock.md`. Conclusion: DO NOT change the enum. The premise of N-4 was wrong, and the search found a deeper problem.**

### It is not unused

**45A §17's own matrix assigns it an occupant inside `LIABILITY-001`:**

```text
| Cannot determine intended provision | `AMBIGUOUS` / `UNRESOLVED` | — |
```

Step 32 also names it as a producible state: "It may produce `AMBIGUOUS`, `UNRESOLVED`, or where appropriate `UNABLE_TO_EVALUATE`." Step 44's own end-to-end diagram (44.39) shows `UNRESOLVED / UNABLE_TO_EVALUATE` as outputs of rule evaluation, and Step 44 lock item 15 lists it among four distinct analytical states. Step 39's algorithm foundation lists it under "explicit uncertainty states."

### But the search surfaced a genuine locked contradiction — **N-11**

**Step 44.22 states:**

> `UNRESOLVED` should represent a **workflow state** rather than a guessed legal conclusion. … This is different from the analytical classification.

This directly contradicts Step 36.7, Step 32, Step 44's own lock item 15, Step 44's own 44.39 diagram, 45A §17, 45B.13, and the `FINDING_CLASSIFICATION` enum in 40.10 / 41.18 / 42.14 — all of which treat `UNRESOLVED` as an analytical classification. **Step 44 contradicts itself.**

### Consequence for AM-7 — the previously approved amendment is now contested

AM-7 removes "or a required action is missing" from 36.7, pushing `UNRESOLVED` firmly into the analytical camp. That is defensible against the weight of the corpus — but it moves *directly against* 44.22, which is also locked. Applying AM-7 without addressing 44.22 would replace one ambiguity with a sharper contradiction between two locked steps.

**Recommendation: hold AM-7. Resolve N-11 first.** Three paths, none selected:

1. **44.22 is the outlier** — treat `UNRESOLVED` as analytical (consistent with eight other locked references); record 44.22 as superseded. AM-7 then proceeds.
2. **44.22 is right** — `UNRESOLVED` is a workflow state, remove it from the classification enum. Amends the locked 7-value vocabulary, REC-01, REC-06, 45A §17, 45B.13 and three schema definitions. Expensive and destabilising.
3. **Both are right about different things** — the analytical `UNRESOLVED` and the workflow "unresolved" are distinct concepts that collided on one word. This matches the J-6 namespacing posture and may need a rename on one side.

Path 1 is cheapest and best supported; path 3 is most honest about the underlying cause. **This must be decided, not assumed.**

---

# 13. New conflicts discovered

**Mandatory section. Recorded, not resolved.**

| ID | Conflict | Severity |
|----|----------|----------|
| **N-11** | **Step 44 contradicts itself and Step 36 on `UNRESOLVED`.** 44.22 calls it a workflow state "different from the analytical classification"; 36.7, 32, 44 lock item 15, 44.39, 45A §17, 45B.13 and three schema definitions treat it as an analytical classification. **Blocks AM-7 and the locking of 45C.** | **CRITICAL** |
| **N-12** | **Legal Rule version is not persisted.** `evaluations.rule_version_id` targets `evaluation_rule_versions` (42.15), but 45B feeds `legal_rule.version_id`; these are separate locked tables (42.9 vs 42.11). Step 32's audit question 4 — "Which Legal Rule was used?" — is unanswerable. | **CRITICAL** |
| **N-13** | **`evaluator_version` has no column.** 45B.10 locks that every evaluation must identify the exact evaluator version; `evaluations` (42.15) has only `evaluator_type`. Breaks ENG-11 reproducibility. | **CRITICAL** |
| **N-14** | **`extraction_diagnostics` has no column**, though REC-07 locks that it is persisted as part of the evaluation/evidence record. | HIGH |
| **N-15** | **Step 31 r11 is unenforced.** r11 requires every decision to carry a reason; 42.17's `decision_text TEXT` is nullable. Proposed AM-15. | HIGH |
| **N-16** | **Company Standard version not recorded per Evaluation.** 42.20's traceability path names it explicitly; it is currently only reachable through the Review-level configuration snapshot. | MEDIUM |
| **N-17** | **45C.22 narrowing.** Its "explicit deterministic contractual rule **or** configured precedence rule" can be read as permitting in-document precedence to be honoured directly, which B-5 forbids. The narrowing interpretation needs recording. | MEDIUM |
| **N-2** | 41.21 `REQUIRE_STANDARD` vs Step 31 `REQUIRE_COMPANY_STANDARD` | **RESOLVED** — supersession, no amendment |
| **N-3** | Decision-record field-name drift | **RESOLVED** — canonical schema above |

**Second-order check on the N-1 repair:** adding `version_number` affects the decision API (update becomes supersession), reviewer display (version history), authorization (unchanged — traversal identical), audit (improved), and golden cases 6 and 12. No existing document, test, or authorization rule depended on decisions being single-row-per-Finding, because no such document exists yet — the dependency surface is entirely within this unlocked proposal set.

---

# 14. Remaining implementation blockers

| ID | Blocker | Class |
|----|---------|-------|
| **N-11** | `UNRESOLVED` — Step 44 vs Step 36 contradiction | **CRITICAL** |
| **N-12** | Legal Rule version not persisted | **CRITICAL** |
| **N-13** | `evaluator_version` not persisted | **CRITICAL** |
| **B-6** | AM-8 – AM-11 unapproved; 45B not re-lockable | **CRITICAL** |
| **B-8** | `evaluation_evidence` unapproved | **CRITICAL** |
| **B-15** | Authentication implementation unspecified | **CRITICAL** (independent) |
| **N-14** | `extraction_diagnostics` not persisted | HIGH |
| **N-15** | `justification NOT NULL` (r11 unenforced) | HIGH |
| **N-8** | Widen-only configuration rule unapproved | HIGH |
| **N-9** | EV-MIN mechanism — deferred trigger recommended, unapproved | HIGH |
| **B-9** | Second-person approval level | HIGH |
| **B-10** | Escalation target level (Finding vs Evaluation) | HIGH |
| **N-16** | Company Standard version per Evaluation | MEDIUM |
| **N-17** | 45C.22 narrowing not recorded | MEDIUM |
| **B-11** | Step 35 band → mapping-state mapping (deferred) | MEDIUM |
| **B-12** | `UNMATCHED_PROVISION` persistence | MEDIUM |
| **B-14** | Step 33 provisional | MEDIUM |
| **N-2** | Vocabulary supersession | NON-BLOCKING |
| **N-3** | Field naming | NON-BLOCKING (given AM-15) |
| **N-10** | `OPEN`/`RESOLVED` semantic overlap | NON-BLOCKING |

---

# 15. Lock readiness

| Question | Answer |
|---|---|
| **Is N-1 ready to lock?** | **Yes, substantively** — Option C is fully specified, needs no change to Step 31 r14/r20, and is enforceable declaratively. It should lock **together with** N-3/AM-15, since both amend the same table. |
| **Is N-3 ready to lock?** | **Yes** — canonical schema settled; `REQUIRE_STANDARD` resolved as supersession without amendment. Requires approval of AM-15 (`justification NOT NULL`) and the decision to drop `metadata`. |
| **Is revised 45B ready to lock?** | **No.** Blocked by N-11 (its `classification` enum is contested), N-12 and N-13 (its own locked reproducibility requirements are unrepresentable), and B-6/B-8. |
| **Is 45C ready to lock?** | **No.** Blocked by N-11 — 45C.13 and 45C.21 both route to `UNRESOLVED`/"appropriate unresolved state", which is exactly the contested term. N-17 should be recorded first. |
| **What must be completed before 45D?** | N-11, N-12, N-13, B-6, B-8, plus N-8/N-9/B-9/B-10. Golden cases 5, 6 and 12 are unwritable until then — and 45D's entire purpose is expressing expected output, which requires a settled contract. |
| **What must be completed before implementation?** | Every CRITICAL and HIGH item above; B-15 independently; plus the MEDIUM set resolved or explicitly deferred with recorded rationale. Steps 33 and 35 must be locked or explicitly scoped out of V1. |

**Loop status:** RECONCILE ✅ · REPAIR ✅ (N-1, N-3) · CROSS-AUDIT ✅ · RECHECK ✅ (three new critical conflicts surfaced) · **LOCK — withheld.**

The audit repaired two contradictions and exposed three more, all of the same species: **locked requirements in Steps 31/32/45B that the locked schema in Step 42 cannot represent.** This is now a recognisable pattern rather than a set of isolated defects, and it suggests the Step 40–42 schema was fixed before the Step 44–45B evaluator contract existed.
