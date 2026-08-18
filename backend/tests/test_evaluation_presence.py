"""PRESENCE evaluator — locked Step 45D.

The two most important tests here are the ones asserting that ambiguity never
becomes absence, and that no clause text can reach the evaluator.
"""

from __future__ import annotations

import inspect
from uuid import uuid4

import pytest

from legalmind.domain.enums import (
    EvaluatorType,
)
from legalmind.domain.enums import (
    FindingClassification as C,
)
from legalmind.domain.enums import (
    MappingState as S,
)
from legalmind.domain.enums import (
    RuleOutcome as O,
)
from legalmind.evaluation.contracts import (
    CompanyStandard,
    EvidenceRef,
    LegalRule,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.presence import (
    OptionalRequirementAbsent,
    PresenceMisconfigured,
)
from legalmind.evaluation.registry import evaluate
from legalmind.evaluation.service import build_presence_input


def presence_input(state, *, expected="PRESENT", required=True,
                   evidence_count=1, legal_rule=None):
    evidence = tuple(EvidenceRef(evidence_id=uuid4()) for _ in range(evidence_count))
    return build_presence_input(
        requirement=RequirementContext(
            requirement_version_id=uuid4(), code="STRUCTURAL-PRESENCE-001",
            evaluator_type=EvaluatorType.PRESENCE, required=required),
        company_standard=CompanyStandard(
            version_id=uuid4(),
            configuration={"expected_presence": expected, "scope_key": "DEFAULT"}),
        mapping_state=state, evidence=evidence, legal_rule=legal_rule)


def only(output):
    assert len(output.evaluations) == 1
    return output.evaluations[0]


# ================================================= the locked outcome matrix
def test_confirmed_mapping_is_match():
    e = only(evaluate(presence_input(S.CONFIRMED)))
    assert e.classification is C.MATCH
    assert e.evidence_refs                        # evidence mandatory


def test_absent_required_is_missing_with_zero_evidence():
    """Step 28 r5 + 45C.15 — zero evidence is correct, nothing invented."""
    e = only(evaluate(presence_input(S.NONE, evidence_count=0)))
    assert e.classification is C.MISSING
    assert e.evidence_refs == ()


@pytest.mark.parametrize("state", [S.AMBIGUOUS, S.UNRESOLVED])
def test_ambiguous_or_unresolved_never_becomes_missing(state):
    """THE critical fail-closed rule (Step 28 r6, ENG-09).

    Recording ambiguity as absence would convert uncertainty into the legal
    conclusion "no such provision exists".
    """
    e = only(evaluate(presence_input(state, evidence_count=2)))
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert e.classification is not C.MISSING
    assert e.classification is not C.MATCH
    assert len(e.evidence_refs) == 2               # candidates retained
    assert any("NOT recorded as absence" in x for x in e.explanation)


def test_expected_absent_and_absent_is_match():
    """A Standard may require that a provision NOT exist."""
    e = only(evaluate(presence_input(S.NONE, expected="ABSENT", evidence_count=0)))
    assert e.classification is C.MATCH


def test_expected_absent_but_present_is_deviation():
    e = only(evaluate(presence_input(S.CONFIRMED, expected="ABSENT")))
    assert e.classification is C.DEVIATION


def test_optional_and_absent_produces_no_finding():
    """F-1 — MISSING is excluded by 36.4 ("the Requirement is expected") and
    MATCH by 36.2 ("customer provision conforms"). No Finding is produced."""
    with pytest.raises(OptionalRequirementAbsent):
        evaluate(presence_input(S.NONE, required=False, evidence_count=0))


def test_rule_outcome_reflects_whether_a_legal_rule_exists():
    """Step 20 r4 — no rule means NOT_APPLICABLE, not an invented tolerance."""
    without = only(evaluate(presence_input(S.CONFIRMED)))
    assert without.rule_outcome is O.NOT_APPLICABLE
    with_rule = only(evaluate(presence_input(
        S.CONFIRMED, legal_rule=LegalRule(version_id=uuid4()))))
    assert with_rule.rule_outcome is O.ACCEPTABLE


def test_presence_never_produces_deviation_from_a_value():
    """45D — DEVIATION from a compared VALUE is not producible here; presence
    has no magnitude. Value criteria are a separate Requirement (N-36)."""
    for state in (S.CONFIRMED, S.NONE, S.AMBIGUOUS, S.UNRESOLVED):
        out = evaluate(presence_input(
            state, evidence_count=0 if state is S.NONE else 1))
        e = only(out)
        assert e.actual_value["presence"] in {"PRESENT", "ABSENT", "INDETERMINATE"}
        assert "cap_value" not in (e.actual_value or {})


# =========================== NO RAW CLAUSE TEXT MAY ENTER THE EVALUATOR
def test_mapping_input_carries_no_clause_text():
    """N-30 / ENG-03 — structural, not conventional.

    If the input type had a text field, a future change could quietly start
    matching patterns here and duplicate the mapping layer.
    """
    fields = set(MappingInput.__dataclass_fields__)
    assert fields == {"mapping_state", "evidence_refs"}
    for banned in ("content", "text", "clause_text", "raw", "body", "patterns"):
        assert banned not in fields


def test_evidence_ref_carries_locations_not_content():
    fields = set(EvidenceRef.__dataclass_fields__)
    assert "content" not in fields and "text" not in fields
    assert "evidence_id" in fields


def test_builder_accepts_no_text_parameter():
    params = set(inspect.signature(build_presence_input).parameters)
    for banned in ("content", "text", "clause_text", "clauses", "document"):
        assert banned not in params


def test_outcome_depends_only_on_mapping_state():
    """P-06 — changing wording without changing mapping_state cannot change the
    outcome, because wording is not an input at all."""
    a = only(evaluate(presence_input(S.CONFIRMED)))
    b = only(evaluate(presence_input(S.CONFIRMED)))
    assert (a.classification, a.rule_outcome) == (b.classification, b.rule_outcome)


# ============================================================ misconfiguration
def test_standard_without_expected_presence_is_a_configuration_error():
    """45B.26 — guessing the expectation would invent the organization's
    position, so this refuses rather than defaulting."""
    bad = build_presence_input(
        requirement=RequirementContext(uuid4(), "X", EvaluatorType.PRESENCE),
        company_standard=CompanyStandard(uuid4(), {}),
        mapping_state=S.CONFIRMED)
    with pytest.raises(PresenceMisconfigured):
        evaluate(bad)


def test_evaluator_version_is_recorded():
    e = only(evaluate(presence_input(S.CONFIRMED)))
    assert e.evaluator_version == "PRESENCE-v1"
