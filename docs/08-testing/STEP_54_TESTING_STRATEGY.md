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
