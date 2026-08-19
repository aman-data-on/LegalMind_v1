"""Golden corpus runner — locked ENG-12, Step 45E, Step 54.

Two kinds of fixture run here.

**STRUCTURAL** fixtures verify the runner and the algorithm with placeholder
values that carry no legal meaning.

**DOCUMENT_SUPPORTED** fixtures are built from the contracts supplied on
2026-08-18, and assert only outcomes that follow from real clause text plus the
locked specification — the fail-closed, conflict and absence paths, where the
engine's answer does not depend on what the organization will accept. They carry
no acceptance position, and `load_fixture` refuses one that tries to.

The **NORMATIVE** corpus of Step 45E still requires the organization's real
Company Standard and Legal Rule. Inventing an expected legal outcome would make a
fabricated legal conclusion normative under Step 54.1, so none is authored.
Per-fixture coverage of all 64 specified cases is tracked in
`tests/corpus_coverage.json` and enforced by `test_corpus_coverage.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from legalmind.domain.enums import RuleOutcome
from legalmind.evaluation.corpus import (
    DOCUMENT_SUPPORTED,
    NORMATIVE,
    STANDARD_DERIVED,
    STRUCTURAL,
    TRACEABLE_PROVENANCE,
    FixtureError,
    load_fixture,
    load_fixtures,
    run_corpus,
    run_fixture,
)

CORPUS_DIR = Path(__file__).parent / "corpus"


def test_corpus_directory_loads():
    fixtures = load_fixtures(CORPUS_DIR)
    assert fixtures
    # Three tiers as of 2026-08-18: STRUCTURAL placeholders, DOCUMENT_SUPPORTED
    # cases from the supplied contracts, and STANDARD_DERIVED cases measured
    # against a position those contracts explicitly state. NORMATIVE requires an
    # approved Legal Rule and must not appear — see the two guards below and
    # tests/corpus_coverage.json.
    assert {f.provenance for f in fixtures} == {
        STRUCTURAL, DOCUMENT_SUPPORTED, STANDARD_DERIVED}


def test_every_fixture_in_the_corpus_passes():
    outcomes = run_corpus(load_fixtures(CORPUS_DIR))
    failures = {o.fixture_id: o.failures for o in outcomes if not o.passed}
    assert not failures, failures


@pytest.mark.parametrize("fixture", load_fixtures(CORPUS_DIR),
                         ids=lambda f: f.id)
def test_fixture(fixture):
    """One test per fixture so a corpus regression names the exact case."""
    outcome = run_fixture(fixture)
    assert outcome.passed, outcome.failures


# ==================================================== runner guarantees
def test_runner_rejects_a_fixture_without_scoped_expectations():
    """Step 45E.1 — asserting only the roll-up would hide per-scope regressions.

    The roll-up is lossy by design, so the runner must refuse the weaker form
    rather than silently accept it.
    """
    payload = json.loads((CORPUS_DIR / "structural_numeric.json").read_text())[0]
    payload["expect_evaluations"] = []
    with pytest.raises(FixtureError, match="expect_evaluations is required"):
        run_fixture(load_fixture(payload))


def test_runner_rejects_unknown_provenance():
    """A fixture must declare whether its expectations are structural or
    normative; defaulting would let invented legal content pass as normative."""
    payload = json.loads((CORPUS_DIR / "structural_numeric.json").read_text())[0]
    payload["provenance"] = "SOMETHING_ELSE"
    with pytest.raises(FixtureError, match="provenance must be"):
        load_fixture(payload)


def test_runner_detects_a_wrong_classification():
    """The runner must actually fail on a mismatch — otherwise the corpus would
    be decorative."""
    payload = json.loads((CORPUS_DIR / "structural_numeric.json").read_text())[0]
    payload["expect_finding_classification"] = "CONFLICT"
    outcome = run_fixture(load_fixture(payload))
    assert not outcome.passed
    assert any("finding classification" in f for f in outcome.failures)


def test_runner_detects_a_wrong_scoped_rule_outcome():
    payload = json.loads((CORPUS_DIR / "structural_numeric.json").read_text())[0]
    payload["expect_evaluations"][0]["rule_outcome"] = "UNACCEPTABLE"
    outcome = run_fixture(load_fixture(payload))
    assert not outcome.passed
    assert any("rule_outcome" in f for f in outcome.failures)


def test_runner_detects_a_missing_scope():
    payload = json.loads((CORPUS_DIR / "structural_numeric.json").read_text())[0]
    payload["expect_evaluations"].append({
        "scope_key": "SCOPE_NOT_PRODUCED", "classification": "MATCH",
        "rule_outcome": "NOT_APPLICABLE"})
    outcome = run_fixture(load_fixture(payload))
    assert not outcome.passed
    assert any("missing evaluation" in f for f in outcome.failures)


def test_runner_enforces_evidence_cardinality():
    """N-34 asserted for every fixture, not only where a case remembers to."""
    payload = json.loads((CORPUS_DIR / "structural_numeric.json").read_text())[0]
    payload["caps"][0]["evidence_count"] = 0
    outcome = run_fixture(load_fixture(payload))
    assert not outcome.passed
    assert any("has no evidence" in f for f in outcome.failures)


def test_runner_is_deterministic():
    """ENG-11 — repeated corpus runs are identical."""
    fixtures = load_fixtures(CORPUS_DIR)
    signatures = {
        tuple((o.fixture_id, o.passed, tuple(o.failures))
              for o in run_corpus(fixtures))
        for _ in range(5)
    }
    assert len(signatures) == 1


def test_no_normative_fixtures_are_present_yet():
    """Guard: a NORMATIVE fixture must not appear until it is authored from real
    representative contracts and real Company Standards (Step 45E, Step 54.1).

    If this test starts failing because someone added one, that is the intended
    signal to check its provenance.
    """
    fixtures = load_fixtures(CORPUS_DIR)
    normative = [f.id for f in fixtures if f.provenance == NORMATIVE]
    assert not normative, (
        f"normative fixtures present: {normative}. A NORMATIVE fixture needs an "
        "approved Legal Rule as well as real contracts and a real Company "
        "Standard; verify each and update tests/corpus_coverage.json.")


def test_no_fixture_asserts_an_acceptance_policy():
    """The owner's V1 policy, checked across the whole corpus at once.

    No formally approved Company Acceptance Policy or Legal Rule exists
    (2026-08-18), so nothing in the corpus may assert what Legal should do about a
    deviation. Every Rule Outcome must be NOT_APPLICABLE, which locked Step 20 r4
    defines as "no Pre-approved Legal Rule; the deviation stands and a human
    decides".

    This is the repository-wide form of the per-fixture guard in `load_fixture`:
    that one refuses a bad fixture at load time, this one catches a tolerance
    reaching the corpus by any other route, including a future NORMATIVE tier
    added before the policy exists.

    STRUCTURAL fixtures are deliberately exempt, and the exemption is the whole
    point of the tier: `STRUCT-FC-*` configure `acceptable_max` over `UNIT_X` and
    `SCOPE_A` to verify that the threshold machinery works at all. Those numbers
    are declared to carry no legal meaning, so they assert nothing about what this
    organization will accept. Only a fixture claiming to describe real material
    can misrepresent a policy.
    """
    offenders = []
    for fixture in load_fixtures(CORPUS_DIR):
        if fixture.provenance not in TRACEABLE_PROVENANCE:
            continue
        if fixture.evaluator_input.legal_rule is not None:
            offenders.append(f"{fixture.id}: carries a Legal Rule")
        for x in fixture.expect_evaluations:
            if x.rule_outcome is not RuleOutcome.NOT_APPLICABLE:
                offenders.append(
                    f"{fixture.id}/{x.scope_key}: expects "
                    f"{x.rule_outcome.value}")
    assert not offenders, (
        "the corpus asserts an acceptance policy that has not been approved:\n  "
        + "\n  ".join(offenders))
