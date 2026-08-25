# Step 54 — Testing Strategy

**Status: 🔒 LOCKED (2026-08-17).** No locked decision changed. Schema impact: none.

Prepared 2026-08-17. Builds on locked ENG-11 (determinism), ENG-12 (golden corpus mandatory), 44.34–44.35, Step 45E, Step 47 and Step 49.

Related: [GOLDEN_CORPUS_45E.md](GOLDEN_CORPUS_45E.md) · [GOLDEN_CORPUS.md](GOLDEN_CORPUS.md) · [REGRESSION_TESTING.md](REGRESSION_TESTING.md)

> The audited external reference contributes **nothing** here — none of its four documents describes a test strategy. That absence is itself informative: an admin application can survive without one; a deterministic legal evaluator cannot.

---

# 54.1 The centre of gravity

For most systems the test pyramid's base is unit tests. **For LegalMind it is the golden corpus.** ENG-12 makes it mandatory, and it is the only mechanism that makes locked determinism and explainability verifiable rather than asserted.

| Tier | Scope | Authority |
|---|---|---|
| **1 · Golden corpus** | Deterministic engine: mapping → extraction → evaluation → Finding | **Normative.** A diff is a specification change until proven otherwise |
| 2 · Unit | Pure functions: normalization, comparison algorithms, roll-up derivation | Supporting |
| 3 · Integration | Persistence, transactions, invariants (EV-MIN, uniqueness, deferred triggers) | Supporting |
| 4 · Authorization | Every endpoint × every role × ownership scope | **Blocking for release** |
| 5 · Workflow | Decisions, escalation, supersession, resolution derivation | Supporting |
| 6 · API contract | Envelope, error taxonomy, field omission | Supporting |

---

# 54.2 Tier 1 — Golden corpus

64 fixtures specified in [Step 45E](GOLDEN_CORPUS_45E.md). Governing rules:

1. **Every fixture asserts both** the exact scoped Evaluation set **and** the derived Finding summary. Never the roll-up alone — it is lossy by design.
2. Every fixture pins its configuration versions and `evaluator_version`.
3. **A changed expected output is a specification change**, reviewed as such — never edited to make a build green.
4. Fixtures are additive; an existing one changes only when the locked specification it encodes changes.
5. The corpus runs in full on any change to mapping, extraction, evaluation or configuration handling.

---

# 54.3 Determinism and reproducibility tests

Directly verify locked ENG-11:

* **Determinism:** identical inputs + identical configuration snapshot + identical evaluator version → **byte-identical** output, across repeated runs and across processes.
* **Reproducibility:** an historical Evaluation replays from persisted facts, evidence, `evaluator_version` and `legal_rule_version_id` (AM-19, AM-20) and yields the same result.
* **Snapshot isolation:** publishing new configuration mid-review does not alter a running or completed Review (Step 30).
* **No hidden inputs:** no clock, random source, locale or environment variable changes an evaluation result.

---

# 54.4 Tier 4 — Authorization tests (release-blocking)

Locked 41.24 and Step 47 make these non-negotiable:

| Test | Assertion |
|---|---|
| **IDOR matrix** | For every object type, a user outside the ownership/visibility scope receives **404** — never the object |
| **Anti-enumeration** | The out-of-scope `404` and the non-existent `404` are byte-identical, including headers and timing characteristics |
| **Permission matrix** | Every endpoint × every role, asserting the exact status |
| **Super-role boundary** | A super-role holder **without** `legal.decision` cannot create a decision through any route (SEC-02) |
| **Legal authority isolation** | `legal.review` alone does not permit deciding (SEC-05) |
| **Escalation guard** | A user cannot grant, edit or delete an authority they do not hold (S-8, S-9) |
| **Never-zero authorities** | A configuration change leaving no `legal.decision` holder is rejected |
| **Confidentiality** | Without `legal_position.view`, `rule_outcome`/thresholds/`rule_configuration` are **absent from the payload**, not null |
| **Session revocation** | A revoked session fails on the very next request |

---

# 54.5 Tier 3 — Invariant tests

* **EV-MIN** — a Finding cannot commit without ≥1 Evaluation (deferred constraint trigger).
* **Evidence cardinality** — non-empty for `MATCH`/`DEVIATION`/`CONFLICT`/`AMBIGUOUS`; empty permitted only for `MISSING`-by-absence; **no synthetic evidence** ever created.
* **Decision versioning** — concurrent supersession: two writers claiming the same `version_number`, one must fail; no lost update.
* **Append-only** — no code path updates or deletes an `audit_events` row or a superseded decision.
* **Uniqueness** — `findings(review_id, requirement_version_id)`, `legal_decisions(evaluation_id, version_number)`.
* **Idempotency** — retried analysis produces no duplicate Finding, Evaluation or Decision (43.28).

---

# 54.6 Test data

* Golden fixtures use **synthetic or cleared** contract text. Real counterparty contracts do not enter the repository.
* Fixtures carry their own configuration; they never depend on environment seed data.
* The representative contract set used for corpus authoring is the **same** set used to calibrate Step 35's provisional mapping thresholds — one data-gathering exercise, two consumers.

---

# 54.7 Release gate

A release requires: the full golden corpus passing with no unreviewed diff; all Tier-4 authorization tests passing; all Tier-3 invariants passing; and determinism/reproducibility tests passing.

**NOT YET SPECIFIED:** coverage targets, test framework selection, CI topology — implementation-phase choices, none determined by a locked decision.

---

## 📎 Implementation note — appended 2026-08-17, locked text unchanged

Nothing above is modified. This note records how the implementation sits against 54.1
and 54.7, because two things about it are easy to get wrong.

**The browser suite is not a tier and not a gate.** `frontend/e2e/` (Playwright, 22
tests) exists for the locked properties no other layer can prove — S-3's `HttpOnly`
session cookie, `LEGAL-02` omission surviving the proxy to the rendered page, 52.7's
no-optimistic-UI rule including the `409` path, and SEC-02's no-bypass claim over real
HTTP. **54.1's six tiers contain no browser tier and 54.7's release gate does not list
one**, so it is documented as supporting, and CI job 10 says so in its own comment. It
must not be cited as a release gate.

**The framework question is registered as `C-12`, not resolved.** Locked Step 39's stack
table names `Pytest + Playwright` and `Vitest`; 54.7 above lists "test framework
selection" as NOT YET SPECIFIED and adds that none of its items "is determined by a
locked decision". Both readings permit the frameworks in use — under the first they are
locked, and under the second they are an implementation choice that is still inside the
Step 39 stack — so the conflict blocks nothing and is recorded in
[CONFLICTS.md](../00-project/CONFLICTS.md) rather than decided.

**Coverage targets remain unset**, per 54.7. CI job 1 (`ruff`, `mypy`) is blocking at a
zero baseline, which is a defect gate rather than a coverage target.

Tier-by-tier state, and the corpus's real status, are in
[IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md); verification by
mechanisms independent of the tests is recorded in
[INDEPENDENT_VERIFICATION.md](INDEPENDENT_VERIFICATION.md).

---

## Tier 2 — the assistive tier (`AM-28`)

**Status: 🔒 LOCKED** — `AM-28`, Amendment Batch AB-3, 2026-08-24, with `AM-31` m1–m5 (AB-4,
2026-08-25). **Added to this document 2026-08-25**; the registry named this file as `AM-28`'s
canonical document and the section was never written. **Everything above this line is unchanged.**

### Tier 1 is untouched, and the assist lane is never admitted to it

> `AM-28`: *"Byte-identical output for identical inputs, configuration snapshot and engine
> version. The assist lane is **NEVER** admitted to this tier. No assist-lane component may be
> added to a determinism assertion, and no determinism assertion may be relaxed to accommodate
> one."*

`r1`: **the two tiers never merge, and a Tier 2 result never satisfies a Tier 1 gate.**

This has a concrete consequence for `tools/verify_reproducibility.py`, which re-runs the whole
pipeline and compares a projection of the legal record. When chunking is dispatched after a
`DocumentProcessingRun` reaches `COMPLETED`, that run will have assist rows attached to it. The
correct fix is to **exclude assist rows from the projection** — never to loosen the comparison,
which `AM-28` r1 forbids outright.

### Tier 2 — what is measured

The assist lane is measured **statistically, not byte-identically**, against a LegalMind
evaluation set of real question-and-answer pairs **including unanswerable questions**:

| Measured | Why it is on the list |
|---|---|
| Retrieval recall | Did the right evidence come back at all |
| Citation precision | Does the cited span actually support the claim |
| Faithfulness | The share of claims with no valid supporting span |
| Refusal correctness, **in both directions** | Refused when the evidence was in fact present · answered when it should have refused |

**The gate:** *"a change to retrieval, chunking, prompt, or model that worsens faithfulness or the
wrongly-answered rate does not ship."*

### Two structural requirements that constrain build order

| Rule | Requirement |
|---|---|
| r2 | The **citation-enforcement component is tested independently of prompt and model code, and does not import them.** *"A guardrail that a prompt change can affect is not a guardrail."* |
| r3 | The golden corpus **remains a Tier 1 artifact governed by rule 21**. The evaluation set is a separate artifact and does not substitute for it. **AB-3 does not unblock the golden corpus**, authors no `NORMATIVE` fixture, and does not reduce the requirement for real supplied legal material |

⚠️ **r2 fixes build order, not just file layout.** Citation enforcement must be built **before**
generation exists. Built afterwards it will import prompt or model code, or need a retrofit — so
guardrails-first is the only order in which r2 is achievable without a rewrite. This is recorded as
`IMPL-02` r4, which makes it one of two properties in the assist build sequence that may **not** be
reordered.

### `AM-31` — measuring a hosted model while the egress gate is closed

`AM-26` r3 requires the quality bar measured on **real supplied documents**. `AM-31` g1 forbids real
counterparty text reaching a hosted provider until written no-training terms are recorded. Left
unresolved, someone measures on synthetic material and reports r3 as satisfied. `AM-31` closes it:

| Rule | Effect |
|---|---|
| m1 | A **provisional** selection may be made on an **explicitly-labelled synthetic** set. The label is part of the record; a synthetic result is never reported as an `AM-26` r3 result |
| m2 | A provisional selection is **not a passed quality bar**. r3 is satisfied only by a run on real supplied material, which requires the gate to be open first |
| m3 | **No assist-lane answer reaches a user over real counterparty material on a synthetic-only bar** |
| m4 | Tier 2's gate is unchanged, and a synthetic result never satisfies it — exactly as r1 already forbids a Tier 2 result satisfying a Tier 1 gate |
| m5 | The evaluation set is subject to locked 54.6 and rule 21 **without exception**: it carries no document text into the repository, and its real question-and-answer material is **supplied, never manufactured** |

**The evaluation set does not exist**, and per rule 21 it is requested, never authored. CI job 8
(`no-real-contracts`) additionally guards the repository against it becoming a route for contract
text to be committed.

### Boundary tests added ahead of the build (2026-08-25)

Two Tier-1 test files exist specifically to make AB-3/AB-4 guarantees structural rather than
aspirational, and both predate any assist code:

* `backend/tests/test_import_boundaries.py` (22 tests) — parses the import graph with `ast`.
  Asserts **no outbound network client anywhere** in `legalmind/` (`AM-30` t1), with an
  `EGRESS_ALLOWED` map that is empty and must be added to **by name** when the generation adapter
  lands; and fences the deterministic core with an **allow-list**, so importing a future
  `legalmind.assist` package fails before that package exists (`AM-25` r1/r2).
* `backend/tests/test_locked_schema_columns.py` (33 tests) — snapshots all 29 locked tables and 195
  columns against the live database, which is what `AM-27` r2 names as its evidence.

Both are gated by CI job 13, added in the same pass because roughly a dozen test files — these
included — were previously named in no job's explicit list.
