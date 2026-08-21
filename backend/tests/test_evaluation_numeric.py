"""NUMERIC_COMPARISON evaluator — locked Steps 45A, 45B, 45C.

All configuration here is synthetic and structural (see evaluation_fixtures);
these tests verify the ALGORITHM, not any company legal position.
"""

from __future__ import annotations

from uuid import uuid4

from legalmind.domain.enums import (
    EvaluationKind as K,
)
from legalmind.domain.enums import (
    ExtractionStatus,
)
from legalmind.domain.enums import (
    FindingClassification as C,
)
from legalmind.domain.enums import (
    RuleOutcome as O,
)
from legalmind.evaluation.registry import evaluate
from tests.evaluation_fixtures import (
    STRUCTURAL_BASIS,
    STRUCTURAL_SCOPE,
    cap,
    numeric_input,
    structural_rule,
    structural_standard,
)


def only(output):
    assert len(output.evaluations) == 1
    return output.evaluations[0]


# ============================================ the configured comparison matrix
def test_value_equal_to_standard_is_match():
    e = only(evaluate(numeric_input([cap(10)])))
    assert e.classification is C.MATCH
    assert e.rule_outcome is O.NOT_APPLICABLE      # 45A §17: MATCH has no outcome


def test_value_within_configured_tolerance_is_acceptable_deviation():
    e = only(evaluate(numeric_input([cap(20)])))
    assert (e.classification, e.rule_outcome) == (C.DEVIATION, O.ACCEPTABLE)


def test_value_above_configured_threshold_requires_approval():
    e = only(evaluate(numeric_input([cap(24)])))
    assert (e.classification, e.rule_outcome) == (C.DEVIATION, O.APPROVAL_REQUIRED)


def test_unlimited_uses_configured_outcome():
    e = only(evaluate(numeric_input([cap(None, status="UNLIMITED")])))
    assert (e.classification, e.rule_outcome) == (C.DEVIATION, O.UNACCEPTABLE)


def test_thresholds_come_from_configuration_not_code():
    """Locked Step 20 — actual Legal Rules are configured, never hardcoded."""
    lenient = structural_rule(acceptable_max=1000, approval_required_above=1000)
    e = only(evaluate(numeric_input([cap(24)], rule=lenient)))
    assert e.rule_outcome is O.ACCEPTABLE          # same value, different config


def test_no_legal_rule_yields_not_applicable():
    """Step 20 r4 — not every Clause requires a Pre-approved Legal Rule.

    The deviation stands and a human decides; the engine invents no tolerance.
    """
    e = only(evaluate(numeric_input([cap(24)], rule=None)))
    assert (e.classification, e.rule_outcome) == (C.DEVIATION, O.NOT_APPLICABLE)


# ================================================================ absence
def test_no_caps_is_missing_with_zero_evidence():
    """45C.15 / N-34 — absence never manufactures a position, and zero evidence
    is the correct representation."""
    e = only(evaluate(numeric_input([])))
    assert e.classification is C.MISSING
    assert e.evidence_refs == ()


def test_absent_cap_status_is_missing():
    e = only(evaluate(numeric_input([cap(None, status="ABSENT")])))
    assert e.classification is C.MISSING


# ============================================================== scoping
def test_different_scopes_are_evaluated_separately_not_as_conflict():
    """45C.1 — differing values across different scopes are NOT a conflict."""
    out = evaluate(numeric_input([
        cap(10),
        cap(30, scope="SCOPE_B", kind=K.EXCEPTION, label="carve-out"),
    ]))
    assert len(out.evaluations) == 2
    assert C.CONFLICT not in {e.classification for e in out.evaluations}


def test_exception_position_does_not_generalize():
    """45C.4 — an UNLIMITED carve-out applies ONLY to its own scope.

    The general scope must remain MATCH; the whole provision is never classified
    UNLIMITED.
    """
    out = evaluate(numeric_input([
        cap(10),
        cap(None, status="UNLIMITED", scope="SCOPE_B",
            kind=K.EXCEPTION, label="carve-out"),
    ]))
    by_kind = {e.evaluation_kind: e for e in out.evaluations}
    assert by_kind[K.PRIMARY].classification is C.MATCH
    assert by_kind[K.EXCEPTION].rule_outcome is O.UNACCEPTABLE
    assert out.finding_classification is C.DEVIATION      # roll-up, not UNLIMITED


def test_incomparable_scope_fails_closed():
    """45C.5 / 45C.20 — values in incomparable scopes are not compared."""
    e = only(evaluate(numeric_input([cap(10, scope="SCOPE_OTHER")])))
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert e.rule_outcome is O.NOT_APPLICABLE


def test_unknown_scope_when_required_fails_closed():
    """45C.20 — scope is never assumed."""
    e = only(evaluate(numeric_input([cap(10, scope="UNKNOWN")])))
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert any("not assumed" in x for x in e.explanation)


# ==================================================== conflict (45C.2, 45C.27)
def test_same_scope_incompatible_caps_conflict():
    e = only(evaluate(numeric_input([cap(10), cap(20)])))
    assert e.classification is C.CONFLICT
    assert e.rule_outcome is O.NOT_APPLICABLE
    assert len(e.evidence_refs) == 2
    assert set(e.evidence_relationships.values()) == {"CONFLICTING"}


def test_conflict_is_not_resolved_by_any_heuristic():
    """45C.22 — no positional/ordinal heuristic may pick a winner.

    Order is reversed; the outcome must not change to a DEVIATION on either value.
    """
    a, b = cap(10), cap(20)
    forward = only(evaluate(numeric_input([a, b])))
    reverse = only(evaluate(numeric_input([b, a])))
    assert forward.classification is reverse.classification is C.CONFLICT


def test_identical_restatements_are_one_position_not_a_conflict():
    """45C.17 — the same position stated twice, with both evidence refs kept."""
    e1, e2 = uuid4(), uuid4()
    out = evaluate(numeric_input([
        cap(10, evidence=(e1,)), cap(10, evidence=(e2,))]))
    e = only(out)
    assert e.classification is C.MATCH
    assert set(e.evidence_refs) == {e1, e2}


# ================================================== fail-closed (ENG-09)
def test_failed_extraction_is_unable_to_evaluate():
    """45B.7 — a FAILED extraction never yields a guess."""
    e = only(evaluate(numeric_input(
        [cap(10)], extraction_status=ExtractionStatus.FAILED,
        diagnostics=("OCR produced no usable text",))))
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert "OCR produced no usable text" in e.diagnostics


def test_unknown_cap_status_is_unable_to_evaluate():
    e = only(evaluate(numeric_input([cap(None, status="UNKNOWN")])))
    assert e.classification is C.UNABLE_TO_EVALUATE


def test_missing_unit_is_unable_to_evaluate():
    """45C.19 — a bare quantity without its qualifier is insufficient."""
    bare = cap(10)
    bare = type(bare)(**{**vars(bare), "cap_unit": None})
    e = only(evaluate(numeric_input([bare])))
    assert e.classification is C.UNABLE_TO_EVALUATE


def test_incomparable_basis_fails_closed_without_conversion():
    """45C.7 / 45C.8 / 45C.23 — bases are never assumed equivalent."""
    e = only(evaluate(numeric_input([cap(10, basis="BASIS_OTHER")])))
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert any("not assumed equivalent" in x for x in e.explanation)


def test_conversion_rule_without_inputs_still_fails_closed():
    """45C.9 — declaring a conversion does not perform one; missing inputs still
    fail closed."""
    rule = structural_rule(rule_configuration={
        "scope_required": True,
        "comparable_scopes": [STRUCTURAL_SCOPE],
        "comparable_bases": [],
        "conversion_rules": [{"from_basis": "BASIS_OTHER",
                              "to_basis": STRUCTURAL_BASIS,
                              "required_inputs": ["contract_value"]}],
    })
    e = only(evaluate(numeric_input([cap(10, basis="BASIS_OTHER")], rule=rule)))
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert any("required inputs are" in x for x in e.explanation)


def test_unit_mismatch_is_not_silently_converted():
    e = only(evaluate(numeric_input([cap(10, unit="UNIT_OTHER")])))
    assert e.classification is C.UNABLE_TO_EVALUATE


def test_standard_without_preferred_value_fails_closed():
    e = only(evaluate(numeric_input(
        [cap(10)], standard=structural_standard(preferred=None))))
    assert e.classification is C.UNABLE_TO_EVALUATE


# ============================================================= determinism
def test_output_is_deterministic():
    """ENG-11 — same inputs, same evaluator version, identical output."""
    caps = [cap(10, evidence=(uuid4(),)),
            cap(30, scope="SCOPE_B", kind=K.EXCEPTION, label="c",
                evidence=(uuid4(),))]
    std, rule = structural_standard(), structural_rule()
    runs = [evaluate(numeric_input(caps, standard=std, rule=rule))
            for _ in range(10)]
    signatures = {
        (*((e.scope_key, e.classification, e.rule_outcome, e.explanation)
           for e in r.evaluations), r.finding_classification)
        for r in runs}
    assert len(signatures) == 1


def test_evaluator_version_is_carried_on_every_evaluation():
    """AM-19 / locked 45B.10 — reproducibility requires the exact version."""
    out = evaluate(numeric_input([cap(10), cap(30, scope="SCOPE_B")]))
    assert all(e.evaluator_version == "NUMERIC-COMPARISON-v1"
               for e in out.evaluations)
    assert out.evaluator_version == "NUMERIC-COMPARISON-v1"


def test_evaluator_emits_no_decision_or_status():
    """36.15 / 45B.14 — the engine produces no Legal Decision, and there is no
    field through which one could be expressed."""
    e = only(evaluate(numeric_input([cap(10)])))
    fields = set(vars(e))
    assert not (fields & {"decision", "decision_type", "legal_decision",
                          "status", "resolution", "risk"})
