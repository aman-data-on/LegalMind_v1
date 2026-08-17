# V1 Evaluator Scope Audit — N-27 / N-30 / N-11

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a conclusion was reached, and its status lines describe the state **at the time of writing**, which has since changed. A conclusion is authoritative only where it appears in [LOCKED_DECISIONS.md](../../00-project/LOCKED_DECISIONS.md) and `all_lock.md`. Do not implement from this file.

**Status: ⏳ ANALYSIS — NOTHING LOCKED.** `all_lock.md` unmodified (13,941 lines, md5 `66591e62`). No locked decision changed or reinterpreted. No evaluator type invented. **V1 not expanded.**

Prepared 2026-08-16. Related: [RECONCILIATION_PASS_4.md](RECONCILIATION_PASS_4.md) · [../EVALUATOR_EDGE_CASES.md](../EVALUATOR_EDGE_CASES.md) (45D) · [LIABILITY.md](LIABILITY.md) (45A 🔒) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

---

# 0. Framing correction

Steps **46 through 56 do not exist in `all_lock.md`.** They appear nowhere in the locked record — no definition, no scope, no lock. They are planning labels used in this working session, not locked steps. This audit therefore measures V1 against **locked decisions only**, not against a planned step sequence.

---

# 1. V1 evaluator coverage required by locked decisions

## 1.1 — What is explicitly locked

### L-1 · More than one evaluation algorithm is required

**Source: Step 36.11 (LOCKED).**

> Different legal requirements need different evaluation algorithms. … So we should **not create one universal comparison algorithm** for every legal clause. The Requirement configuration determines the appropriate deterministic evaluator.

**Legal comparison required:** at minimum two structurally different comparison algorithms must exist. A single-algorithm engine violates this locked rule directly.

**Specification exists:** partially — one algorithm (`NUMERIC_COMPARISON`, via `LIABILITY-001`) is fully specified.
**Illustrative?** The *rule* is locked; the three worked examples are illustrative.
**Must be fully specified before implementation:** **Yes** — at least one non-numeric algorithm.

### L-2 · Comparison must be a multi-clause alignment report

**Source: Step 8 / LEGAL-05 (LOCKED).**

> Comparison = complete alignment report. … What matches · What differs · What is missing · What conflicts · **Which clauses were reviewed** · Evidence supporting the result

**Legal comparison required:** a Review must report across a *set* of Requirements, showing matches alongside differences.
**Specification exists:** no — one Requirement is specified.
**Illustrative?** The locked decision is binding; the five-row example is illustrative.
**Must be fully specified before implementation:** **Yes** — but see §3, the obligation is thinner than it looks.

### L-3 · A Clause Library with a population

**Source: Step 20 (LOCKED).** Rule 4 ("not every Clause requires a Pre-approved Legal Rule"), rule 11 (entries "may be deprecated"), rule 9 (Clause, Requirement, Company Standard, Legal Rule are separate and versioned).

**Must be fully specified before implementation:** the *library mechanism* yes; its *contents* are configuration (see §1.3).

### L-4 · `LIABILITY-001`

**Source: Step 45A (LOCKED).** The only Requirement whose identity, facts, standard, rules and outcomes are specified.
**Illustrative?** No — fully locked.
**Must be fully specified before implementation:** already is, subject to the 45B amendment set.

## 1.2 — What is NOT locked

**No Requirement other than `LIABILITY-001` is locked as required for V1.**

Every other named clause type appears only as an example:

| Named | Where | Status |
|---|---|---|
| Payment Terms, Termination, Confidentiality, Indemnification, Governing Law | Step 7 tree | Illustrative — introduces clause-level comparison |
| Payment Terms, Confidentiality, Data Protection, Termination | Step 8 alignment example | Illustrative |
| Liability, Termination, Governing Law | Step 35.10 mapping keywords | Illustrative ("Example:") |
| Liability, Governing Law, Notice Period | Step 36.11 evaluation algorithms | Illustrative ("For example:") |
| Governing Law Evaluator | Step 44.26 evaluator architecture | Illustrative |
| Liability, Termination, Indemnification, Governing Law | Step 44 closing recommendation | **"should"** — a recommendation for Step 45's scope, never locked |

Step 20 states the position explicitly for its own liability example: *"This example is illustrative only. Actual Legal Rules must be configured by authorized Legal/Admin users."*

## 1.3 — The decisive structural finding: Requirement *content* is configuration, not specification

Three locked decisions together determine what "specifying an evaluator" actually costs:

| Locked | Says | Consequence |
|---|---|---|
| **35.10** | "each Requirement can have its own deterministic mapping **configuration**" | Mapping keywords are **configuration** — no code, no specification step |
| **44.29** | Configuration controls `thresholds, allowed values, patterns, terminology, rule parameters`; Python controls `fact extraction algorithms, comparison semantics` | Thresholds and standards are **configuration**; extraction and comparison are **code** |
| **Steps 21, 29** | Authorized Legal admins create and version Requirements, Standards and Rules through a draft→review→publish workflow | Adding a Requirement is an **administrative act**, not a specification act |

**Therefore adding a Requirement to LegalMind requires new specification only when it requires new *code*** — that is, a fact-extraction algorithm or a comparison algorithm that does not already exist.

```text
New Requirement needs:
  mapping keywords          → configuration     (35.10)      no spec
  Company Standard          → configuration     (Step 21)    no spec
  Legal Rule thresholds     → configuration     (Step 21)    no spec
  evaluator type            → existing code?    (44.29)      spec only if new
  fact extraction           → existing code?    (44.11)      spec only if new
```

This is the finding that governs §3.

---

# 2. Explicit vs implied vs illustrative

### 2.1 Explicitly required V1 evaluator capabilities

| # | Capability | Locked source |
|---|---|---|
| E-1 | At least two structurally different comparison algorithms | 36.11 |
| E-2 | Requirement-specific fact extraction | 44.11, 44.29 |
| E-3 | Requirement-specific mapping configuration | 35.10 |
| E-4 | Multi-Requirement alignment reporting | Step 8 / LEGAL-05 |
| E-5 | `MISSING` for a required Requirement with no mapped provision | Step 28 r5 |
| E-6 | Conflict detection across provisions | 36.5, 44.18 |
| E-7 | Numeric comparison — `LIABILITY-001` | 45A, 45B |

### 2.2 Structurally implied capabilities

| # | Capability | Implied by | Note |
|---|---|---|---|
| I-1 | A presence/absence evaluation mode | Step 8's "Aligned" rows + Step 28 r5 | The cheapest way to satisfy E-4 — see §3 |
| I-2 | A permitted-value comparison mode | 36.11's Governing Law example + 36.12 | Implied by example only, not locked |
| I-3 | Per-Requirement scope vocabulary | 45C, AM-8′ | Already handled by `rule_configuration` |

### 2.3 Optional / future

Range comparison · exact-match as a distinct type · text-pattern evaluation (see §4) · every specific legal area named in the examples.

### 2.4 ⚠ Examples that must NOT be mistaken for requirements

**None of the following is a V1 requirement:**

* The clause list in Step 7 (Payment Terms, Termination, Confidentiality, Indemnification, Governing Law)
* The five rows and "82%" in Step 8's alignment example
* The mapping keyword sets in 35.10
* The Governing Law and Notice Period evaluators in 36.11
* Step 44's closing "should define … Liability, Termination, Indemnification, Governing Law, etc." — a recommendation, never locked
* The nine evaluator types in 36.12 — explicitly "I recommend … such as"

Treating any of these as a commitment would expand V1 without a locked decision.

---

# 3. N-27 impact — precisely what changes

## 3.1 The finding, restated correctly

Pass 4 stated N-27 as *"V1 is not currently specifiable end-to-end."* That is **true but overstated in cost.** The evidence in §1.3 narrows it sharply.

**What is genuinely true:** locked L-1 and L-2 cannot be satisfied by `LIABILITY-001` alone. LegalMind cannot produce a multi-clause alignment report from one Requirement, and 36.11 forbids a single universal algorithm.

**What is NOT true:** that V1 requires four new fully-specified legal Requirements. The examples naming Termination, Indemnification and Governing Law are illustrative (§2.4), and Requirement *content* is configuration (§1.3).

## 3.2 The minimum locked-satisfying coverage

Examine Step 8's own locked example by outcome type:

```text
✓ Payment Terms            Aligned      ← presence-satisfiable
✓ Confidentiality          Aligned      ← presence-satisfiable
⚠ Limitation of Liability  Deviation    ← value comparison (LIABILITY-001 ✅)
❌ Data Protection          Missing      ← falls out of mapping (Step 28 r5) — no evaluator needed
✓ Termination              Aligned      ← presence-satisfiable
```

**Four of five rows need no value comparison.** `MISSING` requires no evaluator at all — Step 28 r5 produces it from the absence of a mapping. The remaining "Aligned" rows are satisfiable by a presence-mode evaluation.

**Minimum coverage that satisfies every locked decision:**

| # | Item | Cost |
|---|---|---|
| 1 | `LIABILITY-001` — numeric comparison | ✅ Already specified |
| 2 | **One presence-mode evaluator type** (`BOOLEAN_PRESENT`) | **Requires no Requirement-specific fact extraction** — presence is established by the locked mapping layer. One generic specification, reusable by every Requirement |
| 3 | A configured set of Requirements using it | **Configuration** (Steps 21, 29) — not a specification act |

**N-27 therefore costs one generic evaluator-type specification, not four legal-domain specifications.** That is the material result of this audit.

## 3.3 ⚠ The one ambiguity this turns on

**Does "Aligned" in Step 8's example mean `MATCH` on a compared value, or merely that a qualifying provision is present?**

Not locked. Reading it as *value-match* would require a specified Company Standard for each of Payment Terms, Confidentiality and Termination — restoring the expensive interpretation. Reading it as *presence* makes §3.2's minimum sufficient.

Because it is an example, Step 20's rule applies — examples are illustrative and actual rules are configured. **But this must be ruled on explicitly, not assumed.** Recorded as **N-31**.

## 3.4 Impact by area

| Area | Impact |
|---|---|
| **Specification scope** | +1 generic evaluator-type specification. **No new legal-domain Requirement specification is compelled by any locked decision.** |
| **45D** | Unblocked in substance. 45D.4.1–45D.4.11 stand; the Requirement Template gains a second worked instance |
| **"Step 46"** | Does not exist in the locked record. If a Requirement-specification step is planned, its *content* is a product decision (N-24b), not a locked obligation |
| **Implementation readiness** | Improves. The blocker was mis-scoped; the real blockers remain N-12, N-13, B-6, B-8, B-15 |
| **Golden corpus** | Gains presence-mode fixtures: present→`MATCH`, absent→`MISSING`, present-but-non-qualifying→`MISSING` with evidence retained (45C.14) |
| **Database** | **None.** `evaluations` under AM-8′ already accommodates a presence evaluator: `scope_key` = the Requirement's single scope, `evaluation_kind = PRIMARY`, `expected_value`/`actual_value` nullable per locked 42.15 |
| **API** | **None.** The Finding → `evaluations[]` shape is evaluator-agnostic |

**V1 is not expanded by this audit.** It is measured, and found to require one generic capability rather than four legal specifications.

---

# 4. N-30 — `TEXT_PATTERN` against the Mapping ≠ Evaluation boundary

## 4.1 Where pattern matching is already locked

| Layer | Locked mechanism | Source |
|---|---|---|
| **Mapping** | Keyword groups, negative terms, requirement-specific mapping configuration | 35.4, 35.5, 35.10 |
| **Extraction** | Negative patterns, exception patterns, scope patterns | 44.16, 45A §15 |
| **Evaluation** | *(none)* | — |

**Both non-evaluation layers already have distinct, locked pattern mechanisms.** No third mechanism is missing.

## 4.2 The decisive test — explainability, not tidiness

Locked **44.33** requires every Finding to reconstruct as:

```text
Evidence → Fact → Standard → Rule → Result
```

A `TEXT_PATTERN` **evaluator** compares clause *text* against a pattern. It therefore produces a Result without producing a **Fact** — the chain becomes `Evidence → Result`. That breaks the locked explainability contract, which is a rule 12 obligation in [CLAUDE.md](../../../CLAUDE.md) and locked at 44.33.

It also collapses **ENG-03** (Mapping ≠ Evaluation): matching clause text against configured patterns is definitionally what the locked mapping layer does (35.4, 35.10).

## 4.3 Determination

**`TEXT_PATTERN` belongs to Mapping and Extraction. It is not an evaluator type.**

Answering the three-way question directly: **both layers require distinct pattern mechanisms — and both already exist and are locked.** Nothing new is needed; the proposed evaluator type was the error.

Where pattern recognition must influence an outcome, the locked path is: pattern → extracted **Fact** → compared against Standard → Rule → Result. The Fact is not optional.

**Proposed `EVALUATOR_TYPE` reduces from 7 values to 6:**

```text
NUMERIC_COMPARISON · RANGE_COMPARISON · ALLOWED_VALUES
EXACT_MATCH · BOOLEAN_PRESENT · BOOLEAN_ABSENT
```

N-28 (`EXACT_MATCH` vs `ALLOWED_VALUES`) and N-29 (`RANGE_` vs `NUMERIC_`) remain open.

---

# 5. N-11 — dependencies, and whether it can be resolved now

## 5.1 What N-11 depends on

**Nothing further.** All evidence was gathered in Pass 3 §12: 32 occurrences of `UNRESOLVED` across the locked record. N-11 requires a ruling, not more research.

## 5.2 Re-reading 44.22 closely — the contradiction may not exist

Pass 3 recorded 44.22 as contradicting Step 36. Re-read in full:

> `UNRESOLVED` should represent a workflow state rather than a guessed legal conclusion.
> `Conflict detected → Legal review required → UNRESOLVED`
> After an authorized decision: `UNRESOLVED → RESOLVED`
> **This is different from the analytical classification.**

The closing sentence **acknowledges that the analytical classification exists and is a different thing.** 44.22 is not redefining Step 36's classification — it is describing a *workflow* state and explicitly distinguishing it.

Its contrast is with "a guessed legal conclusion": the point is that unresolvedness must route to workflow rather than be resolved by guessing. That is entirely consistent with ENG-09 fail-closed and with 45C.13.

**Assessment: N-11 is a token collision across axes, not a contradiction — the same species as C-01, and exactly what REC-06 was established to handle.** Two distinct concepts collided on one word before a workflow vocabulary existed.

The workflow vocabulary 44.22 was reaching for **now exists**: J-4's Finding status (`OPEN` / `DECISION_REQUIRED` / `AWAITING_CLARIFICATION` / `RESOLVED`). 44.22's `UNRESOLVED → RESOLVED` transition is precisely `DECISION_REQUIRED → RESOLVED`.

## 5.3 Consequences if this reading is accepted

| Item | Outcome |
|---|---|
| **44.22** | **No amendment.** It correctly describes a workflow state and correctly distinguishes it |
| **AM-7** | **Proceeds as approved.** Removing "or a required action is missing" from 36.7 is exactly right — that clause is the workflow concept leaking into an analytical definition |
| **Classification.UNRESOLVED** | Remains a canonical axis-2 value with its occupant in 45A §17 |
| **45C** | Unblocked on this point |
| **REC-06** | Extended with a third collision row — recorded, not rewritten |

**Recommendation: adopt Pass 3's path 3 (both are right about different things).** It requires no amendment to either locked step, matches 44.22's own words, and is consistent with the reconciliation pattern already used for C-01. **Presented for ruling, not applied.**

---

# 6. Revised roadmap to an Implementation Readiness Review

Minimum remaining specification sequence. Steps 46–56 are not locked; this is a proposed order, not a step definition.

### Phase 1 — Close the contradictions *(all decision-ready; no further research needed)*

| # | Item | Nature |
|---|---|---|
| 1 | **N-11** | Ruling — §5.3 recommends path 3 |
| 2 | **N-31** | Ruling — does Step 8 "Aligned" mean value-match or presence? Governs Phase 2's cost |
| 3 | **N-30** | Ruling — §4.3 recommends removing `TEXT_PATTERN` |
| 4 | **N-18** | Approve the 6-value vocabulary; rule on N-28, N-29 |
| 5 | **AM-8′** | Approve generalized discriminators |

### Phase 2 — Close the reproducibility gaps *(schema)*

| # | Item |
|---|---|
| 6 | **N-12** — persist the Legal Rule version (Step 32 audit question 4 currently unanswerable) |
| 7 | **N-13** — persist `evaluator_version` (locked 45B.10) |
| 8 | **N-14** — persist `extraction_diagnostics` (locked REC-07) |
| 9 | **N-15** — `justification NOT NULL` (locked Step 31 r11) |
| 10 | **B-8** — `evaluation_evidence` junction |
| 11 | **N-1 / N-3** — decision versioning and canonical decision schema |

### Phase 3 — Re-lock the evaluator layer

| # | Item |
|---|---|
| 12 | Re-lock **45B** with AM-1, AM-8′, AM-9′–AM-17 |
| 13 | Lock **45C** |
| 14 | Lock **45D** (45D.4.1–45D.4.12 + Requirement Template) |
| 15 | Specify **one presence-mode evaluator** — satisfies L-1 and L-2 (§3.2) |

### Phase 4 — Golden corpus

| # | Item |
|---|---|
| 16 | Liability golden test cases — the deliverable displaced by the 45D scope change (N-21) |
| 17 | Presence-mode golden cases |
| 18 | Workflow tests — partial decisions, supersession, per-scope evidence |

### Phase 5 — Outside the evaluator track *(independent, can run in parallel)*

| # | Item |
|---|---|
| 19 | **Security / Authorization** — OD-1 – OD-15, resolves B-15 |
| 20 | **API finalization** |
| 21 | **Frontend, observability, testing strategy, deployment** |
| 22 | Resolve or explicitly defer Steps 33 and 35's provisional items (B-11, B-14) |

### Then: Implementation Readiness Review

Entry criteria: every CRITICAL and HIGH blocker resolved or explicitly deferred with recorded rationale; the Step 32 audit questions all answerable; the golden corpus expressible; authentication and authorization specified.

**Phase 1 is entirely rulings — no research remains.** Phase 2 is the largest genuine specification effort, and it is schema work driven by locked requirements the current schema cannot represent.

---

# 7. Decisions presented for review

Nothing below has been applied.

| ID | Decision | Recommendation |
|----|----------|----------------|
| **N-11** | Analytical vs workflow `UNRESOLVED` | Path 3 — distinct concepts, one word. No amendment to 44.22 or Step 36 beyond AM-7 |
| **N-31** | Does Step 8's "Aligned" mean value-match or presence? | Presence — consistent with Step 20's "illustrative only" rule. **Governs whether N-27 costs one generic evaluator or several legal specifications** |
| **N-30** | `TEXT_PATTERN` placement | Mapping + Extraction; remove from evaluator vocabulary |
| **N-27** | Minimum V1 coverage | `LIABILITY-001` + one presence-mode evaluator + configured Requirements |
| **N-24b** | Which Requirements ship in V1 | **Not recommended by me** — legal/product decision, and no locked decision compels any specific one |

**N-31 is the highest-leverage ruling.** It alone determines whether N-27 is a one-item task or a multi-Requirement specification programme.
