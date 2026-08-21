# Step 45E — Golden Corpus

**Status: ⏳ IN PROGRESS — specification of required fixtures. Not locked.**

> ⚠️ **Fixture source material must be supplied, not invented.** This document specifies *which* fixtures are required and what each must assert. Authoring them requires real representative contracts and the organization's real Company Standards. **Ask the owner for that material explicitly; do not draft contract text, cap values, carve-outs or standards to fill a fixture, and do not promote an illustrative example into a production expectation.** A fixture built on invented legal content asserts a legal conclusion the organization never made — and, being Tier 1 and normative under [STEP_54_TESTING_STRATEGY.md](STEP_54_TESTING_STRATEGY.md), it would then bind every later change. See [CLAUDE.md](../../CLAUDE.md) rule 21.

Opened 2026-08-17, following the locking of Steps 45B (revised), 45C and 45D. Basis: locked **ENG-12** (a golden test corpus is mandatory), locked 44.34–44.35, and 45C.26 rule 17 ("Edge cases must be represented in the golden test corpus before implementation is considered complete").

Related: [GOLDEN_CORPUS.md](GOLDEN_CORPUS.md) · [REGRESSION_TESTING.md](REGRESSION_TESTING.md) · [../04-analysis-engine/EDGE_CASES/LIABILITY_EDGE_CASES.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EDGE_CASES.md) · [../04-analysis-engine/EDGE_CASES/PRESENCE_EVALUATOR.md](../04-analysis-engine/EDGE_CASES/PRESENCE_EVALUATOR.md) · [../04-analysis-engine/EVALUATOR_EDGE_CASES.md](../04-analysis-engine/EVALUATOR_EDGE_CASES.md)

---

# 45E.1 Purpose and the universal assertion rule

The golden corpus is the executable form of the locked evaluator specification. It is the mechanism by which locked determinism (**ENG-11**) and locked reproducibility become verifiable rather than aspirational.

**Universal rule for every fixture:**

> Every case asserts **both** the exact set of scoped Evaluation outputs **and** the derived Finding summary. **Never the roll-up alone.**

The Finding classification is a lossy derived summary (locked 45D / D-1.2). A fixture asserting only the summary would let per-scope regressions pass undetected — which is the precise failure the two-level assertion exists to prevent.

## Fixture shape

```text
fixture:
  id
  description
  input:
    document excerpt (or synthetic clause set)
    requirement_version_id
    company_standard_version_id
    legal_rule_version_id            (may be absent — Step 20 r4)
    evaluator_version
  expect_finding:
    classification                   ← derived roll-up
    status                           ← where workflow is exercised
  expect_evaluations:                ← exact set, order-independent
    - scope_key, evaluation_kind, classification, rule_outcome,
      expected_value, actual_value, evidence_ref_count
  expect_invariants:
    EV-MIN, evidence cardinality, no synthetic evidence,
    no Legal Decision produced
```

---

# 45E.2 Engine fixtures — `LIABILITY-001`

Derived from locked 45C. One fixture per numbered rule.

| # | Case | Source | Expected |
|---|------|--------|----------|
| L-01 | 6-month aggregate cap | 45C.21 | `MATCH` / `NOT_APPLICABLE` |
| L-02 | 12-month aggregate cap | 45C.21 | `DEVIATION` / `ACCEPTABLE` |
| L-03 | 24-month aggregate cap | 45C.21 | `DEVIATION` / `APPROVAL_REQUIRED` |
| L-04 | Unlimited general liability | 45C.21 | `DEVIATION` / `UNACCEPTABLE` |
| L-05 | Multiple caps, different scopes | 45C.1 | Two Evaluations; **not** `CONFLICT` |
| L-06 | Same scope, contradictory caps | 45C.2 | `CONFLICT`; both evidence refs retained |
| L-07 | General cap + carve-outs | 45C.3 | `PRIMARY` + `EXCEPTION` Evaluations, evaluated separately |
| L-08 | Unlimited carve-out | 45C.4 | General `MATCH`; exception `DEVIATION`/`UNACCEPTABLE`; roll-up `DEVIATION`. **Whole provision never classified `UNLIMITED`** |
| L-09 | Per-claim vs aggregate | 45C.5 | Distinct `scope_key`s; no cross-scope comparison |
| L-10 | Per-event vs aggregate | 45C.6 | Distinct scopes; not conflicting |
| L-11 | Different monetary bases | 45C.7 | `UNABLE_TO_EVALUATE` absent a configured conversion |
| L-12 | Fixed amount vs fee-based | 45C.8 | `UNABLE_TO_EVALUATE`, **not** `DEVIATION` |
| L-13 | Percentage-based cap | 45C.9 | Preserved as `PERCENTAGE` / `CONTRACT_VALUE`; no conversion |
| L-14 | Cross-reference resolved | 45C.10 | Referenced provision evaluated normally |
| L-15 | Cross-reference unresolvable | 45C.10 | `UNABLE_TO_EVALUATE`; referent never invented |
| L-16 | Conflicting cross-reference chains | 45C.11 | `CONFLICT`; both chains traceable |
| L-17 | Negative wording — general | 45C.12 | `cap_status = UNLIMITED` |
| L-18 | Ambiguous wording | 45C.13 | `AMBIGUOUS`; never resolved into a position |
| L-19 | Liability clause, no cap | 45C.14 | `MISSING` **with** evidence retained |
| L-20 | Liability wholly absent | 45C.15 | `MISSING` with **zero** evidence |
| L-21 | Referencing clause | 45C.16 | One Evaluation, not two |
| L-22 | Same cap repeated | 45C.17 | One Evaluation, two evidence refs |
| L-23 | OCR corruption, resolvable | 45C.18 | Normalized; evaluated |
| L-24 | OCR corruption, ambiguous | 45C.18 | `UNABLE_TO_EVALUATE` |
| L-25 | Missing unit | 45C.19 | `UNABLE_TO_EVALUATE` |
| L-26 | Missing necessary scope | 45C.20 | `UNABLE_TO_EVALUATE`; `AGGREGATE` never assumed |
| L-27 | Precedence language, no configured rule | 45C.27 | `CONFLICT`; precedence clause attached as `SUPPORTING` evidence |
| L-28 | Configured deterministic precedence | 45C.2 | Resolved per configuration |

### L-29 · The negative-pattern matched pair *(required)*

Two fixtures differing by six words, with opposite legal positions:

```text
L-29a  "Liability shall not be limited in respect of fraud"   → EXCEPTION carve-out
L-29b  "Liability shall not be limited"                       → general UNLIMITED
```

The sharpest available test of the negative-pattern and scope machinery (45A §15 vs 45C.12).

---

# 45E.3 Engine fixtures — `PRESENCE`

From the locked presence evaluator (45D).

| # | Case | Expected |
|---|------|----------|
| P-01 | Provision present | `MATCH`; evidence non-empty |
| P-02 | Provision absent, Requirement `REQUIRED` | `MISSING`; **zero** evidence; exactly one Evaluation (EV-MIN) |
| P-03 | Mapping `AMBIGUOUS` | `UNABLE_TO_EVALUATE`. **Asserts classification is NOT `MISSING`** |
| P-04 | Mapping `UNRESOLVED` | `UNABLE_TO_EVALUATE`; not `MISSING`, not `MATCH` |
| P-05 | Provision absent, Requirement `OPTIONAL` | **No Finding, no Evaluation** (F-1) |
| P-06 | **Text-independence guard** | Changing clause wording without changing `mapping_state` does not change the outcome. The evaluator receives no clause text |

**P-03 and P-06 are the two most important fixtures in the presence set.** P-03 guards the fail-closed rule that ambiguity must never become absence. P-06 structurally prevents the presence evaluator from drifting into a text-pattern evaluator.

---

# 45E.4 Roll-up and structural fixtures

| # | Case | Expected |
|---|------|----------|
| R-01 | Tier-1 dominance | One `UNABLE_TO_EVALUATE` scope among several `MATCH` → Finding summarizes `UNABLE_TO_EVALUATE` |
| R-02 – R-07 | Tier-1 internal ordering | One fixture per ordered pair. **Labelled as a determinism convention, not a legal hierarchy** |
| R-08 | Tier-2 ordering | `MISSING` > `DEVIATION` > `MATCH` |
| R-09 | EV-MIN | Every fixture produces ≥1 Evaluation, including `MISSING` and `UNABLE_TO_EVALUATE` |
| R-10 | Evidence cardinality | Non-empty for `MATCH`/`DEVIATION`/`CONFLICT`/`AMBIGUOUS`; empty permitted only for `MISSING`-by-absence; **no synthetic evidence** |
| R-11 | No Legal Decision | No evaluator output contains a decision, status or resolution field |
| R-12 | Determinism | Same inputs + same configuration snapshot + same evaluator version → byte-identical output |
| R-13 | Reproducibility | Evaluation replayable from persisted facts, evidence, `evaluator_version` and `legal_rule_version_id` |

### R-14 · Multi-Requirement alignment shape *(required)*

Demonstrates that locked Step 8's alignment report is producible with two evaluator types:

```text
Requirement A (PRESENCE)            CONFIRMED  → MATCH
Requirement B (PRESENCE)            CONFIRMED  → MATCH
LIABILITY-001 (NUMERIC_COMPARISON)  12 months  → DEVIATION + ACCEPTABLE
Requirement C (PRESENCE)            NONE       → MISSING
Requirement D (PRESENCE)            CONFIRMED  → MATCH

assert: 5 Findings, each with ≥1 Evaluation
assert: matches, a deviation and a missing all present in one Review
```

---

# 45E.5 Fail-closed matrix *(required)*

Each asserts that **no default was silently applied**:

```text
F-01  no configured precedence          ⇒ CONFLICT
F-02  no configured conversion rule     ⇒ UNABLE_TO_EVALUATE
F-03  scope UNKNOWN + scope_required    ⇒ UNABLE_TO_EVALUATE
F-04  basis not in comparable_bases     ⇒ UNABLE_TO_EVALUATE
F-05  extraction_status = FAILED        ⇒ UNABLE_TO_EVALUATE
F-06  mapping AMBIGUOUS / UNRESOLVED    ⇒ UNABLE_TO_EVALUATE (never MISSING)
```

---

# 45E.6 Workflow fixtures

Not golden-corpus cases — these exercise human process, not the deterministic engine. Tracked separately.

| # | Case | Expected |
|---|------|----------|
| W-01 | Heterogeneous Finding | `MATCH` + `UNACCEPTABLE` + `ACCEPTABLE` scopes → Finding `DECISION_REQUIRED` until the unacceptable scope is decided |
| W-02 | Scoped decision isolation | A decision on Evaluation 2 does not alter Evaluations 1 or 3 |
| W-03 | Decision supersession | Version 2 supersedes version 1; version 1 remains intact and readable |
| W-04 | Concurrent supersession | Two writers both claiming `version_number = N+1` → one fails; no lost update |
| W-05 | `REQUEST_CLARIFICATION` | Blocks Finding resolution |
| W-06 | Escalation | `OPEN → DECISION_REQUIRED`; all Evaluations under the Finding marked as requiring a decision |
| W-07 | Per-scope evidence | Evidence attributable to individual Evaluations via `evaluation_evidence` |
| W-08 | `RESOLVED ≠ MATCH` | A resolved Finding retains its original classification |

---

# 45E.7 Corpus governance

Per locked 44.34–44.35 and REGRESSION_TESTING:

1. Every fixture pins its **configuration versions** and **evaluator version**. A configuration change that alters an expected output is a specification change, not a test failure to be edited away.
2. Any evaluator change must re-run the full corpus; a diff in any expected output requires explicit review.
3. Fixtures are **additive**. An existing fixture is amended only when the locked specification it encodes changes.
4. Corpus coverage is a precondition for implementation completeness (45C.26 rule 17).

---

# 45E.8 Status

| Group | Count | State |
|---|---|---|
| Liability engine (L-01 – L-29b) | 30 | Specified |
| Presence engine (P-01 – P-06) | 6 | Specified |
| Roll-up / structural (R-01 – R-14) | 14 | Specified |
| Fail-closed (F-01 – F-06) | 6 | Specified |
| Workflow (W-01 – W-08) | 8 | Specified — separate track |

**64 fixtures specified.** Authoring the actual documents and expected outputs is implementation work, gated on the representative contract test set that Step 35's threshold calibration also requires.

**Dependency:** Step 35's mapping thresholds are explicitly provisional pending a representative contract set. The corpus and the threshold calibration should be built from the same document set — they are the same data-gathering exercise.

---

# 45E.9 Coverage record — added 2026-08-18

**This section records where authoring stands. It changes nothing above it.**

Per-fixture status for all 64 ids specified in this document lives in
`backend/tests/corpus_coverage.json`, enforced by `backend/tests/test_corpus_coverage.py`
— the ids are derived from this specification rather than copied, so a forgotten or
invented case fails a test rather than passing unnoticed.

As of 2026-08-18: **14 AUTHORED · 1 AUTHORED_RATIFIED · 3 PARTIAL · 25 BLOCKED ·
13 STRUCTURAL_ONLY · 8 SEPARATE_TRACK** (the last being 45E.6's workflow track).

⚠️ **45E.2's expected-outcome column for L-01 – L-04 was written against the illustrative
six-month standard, and the ratified Company Standard is twelve months of total fees**
(owner, 2026-08-18). Those rows are therefore no longer the expected outcomes: a twelve-month
cap `MATCH`es rather than deviating, and the only six-month cap in the supplied documents
measures on a different basis and fails closed. The manifest status `AUTHORED_RATIFIED`
marks a case where ratification supersedes this document's illustration. **No text above has
been altered** — CLAUDE.md is explicit that the six-month examples illustrate behaviour
rather than state a position, so this is the illustration behaving as labelled, not a
conflict.

Authored cases carry one of two provenances. `DOCUMENT_SUPPORTED` expectations follow from
real clause text plus this specification's fail-closed rules, with no Company Standard value
involved. `STANDARD_DERIVED` expectations are measured against a position the supplied
documents *explicitly state*, per the owner's V1 interim policy of 2026-08-18, and may
assert `MATCH` or `DEVIATION`.

**Neither tier may assert a Rule Outcome other than `NOT_APPLICABLE`.** No approved Company
Acceptance Policy or Legal Rule exists, and locked Step 20 r4 already gives
`NOT_APPLICABLE` the needed meaning — *no Pre-approved Legal Rule; the deviation stands and
a human decides*. This is why several rows here read PARTIAL rather than AUTHORED: 45E.2
expects outcomes such as `ACCEPTABLE` (L-02) and `UNACCEPTABLE` (L-08) that presuppose a
policy. **No `NORMATIVE` fixture exists**, and none may be authored until that policy is
approved — see
[../00-project/SOURCE_MATERIAL_INTAKE.md](../00-project/SOURCE_MATERIAL_INTAKE.md), which
records what the first tranche of material did and did not cover.
