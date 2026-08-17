"""Golden corpus runner — locked ENG-12, Step 45E, Step 54.

The fixtures exercised here are **STRUCTURAL**: they verify the runner and the
algorithm. The NORMATIVE corpus specified in Step 45E (64 fixtures) requires real
representative contracts and the organization's real Company Standards, and is
not authored here — inventing expected legal outcomes would make a fabricated
legal conclusion normative under Step 54.1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from legalmind.domain.enums import FindingClassification as C
from legalmind.evaluation.corpus import (
    NORMATIVE,
    STRUCTURAL,
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
    assert {f.provenance for f in fixtures} == {STRUCTURAL}


def test_all_structural_fixtures_pass():
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
        f"normative fixtures present: {normative}. Verify each was authored "
        "from real representative contracts and real Company Standards.")
