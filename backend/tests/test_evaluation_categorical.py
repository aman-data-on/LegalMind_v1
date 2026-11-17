"""CATEGORICAL evaluator — AM-148.

A customer's markup moved the courts and the arbitration seat to Bengaluru, and the
review read "Acceptable": PRESENCE asks only whether a dispute clause exists. The
ratified DISPUTE-VENUE-MSA-001 states Constitution §22's position as values; these
tests pin how a clause's stated place is compared with them.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from legalmind.domain.enums import EvaluatorType
from legalmind.domain.enums import FindingClassification as C
from legalmind.domain.enums import MappingState as S
from legalmind.domain.enums import RuleOutcome as O
from legalmind.evaluation.categorical import CategoricalMisconfigured
from legalmind.evaluation.contracts import (
    CompanyStandard,
    EvaluatorInput,
    EvidenceRef,
    LegalRule,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.registry import evaluate, version_for
from legalmind.extraction.categorical import read_values
from legalmind.mapping.engine import Clause

STANDARD = json.loads((Path(__file__).resolve().parents[1] / "config" / "company_standards"
                       / "DISPUTE-VENUE-MSA-001.json").read_text())
CONFIG = STANDARD["configuration"]
ZERO_TOLERANCE = LegalRule(version_id=uuid4(),
                           configuration=STANDARD["legal_rule"]["configuration"])


def _clause(text: str) -> Clause:
    return Clause(evidence_id=uuid4(), content=text, section_number=None,
                  section_title="Dispute Resolution")


def _evaluate(text: str | None, state=S.CONFIRMED, *, required=True):
    clauses = [_clause(text)] if text is not None else []
    facts = read_values(clauses, CONFIG) if state is S.CONFIRMED else None
    refs = tuple(EvidenceRef(evidence_id=c.evidence_id) for c in clauses)
    out = evaluate(EvaluatorInput(
        requirement=RequirementContext(requirement_version_id=uuid4(),
                                       code="DISPUTE-VENUE-MSA-001",
                                       evaluator_type=EvaluatorType.CATEGORICAL,
                                       required=required),
        company_standard=CompanyStandard(version_id=uuid4(), configuration=CONFIG),
        evaluator_version=version_for(EvaluatorType.CATEGORICAL),
        evidence=refs, facts=facts,
        mapping=MappingInput(mapping_state=state, evidence_refs=refs),
        legal_rule=ZERO_TOLERANCE))
    assert len(out.evaluations) == 1
    return out.evaluations[0]


def test_our_msas_own_wording_matches():
    # AM-380 (owner 2026-11-16): the MSA venue is our MSA 19.3/19.4 — Mumbai.
    e = _evaluate("in the event of no consensus, then the High Court of Mumbai shall appoint "
                  "an Arbitrator. The arbitration shall take place in Mumbai, India unless "
                  "otherwise mutually agreed by the Parties and shall be conducted in the "
                  "English language.")
    assert e.classification is C.MATCH and e.rule_outcome is O.ACCEPTABLE
    assert e.actual_value == {"values": ["Mumbai"]}


def test_the_bombay_high_court_is_one_phrase_and_allowed():
    # 19.3's court by the name Constitution §22 prescribes; "Bombay" inside it is not
    # read as a separate place.
    e = _evaluate("Arbitration shall take place in Mumbai, India, and the Bombay High Court "
                  "shall appoint the arbitrator on no consensus.")
    assert e.classification is C.MATCH
    assert e.actual_value == {"values": ["Mumbai", "Bombay High Court"]}


def test_a_pune_seat_is_a_deviation_on_an_msa():
    # AM-380 r5: Pune (AM-150) is superseded for the MSA venue.
    e = _evaluate("The seat and venue of arbitration shall be Pune, India.")
    assert e.classification is C.DEVIATION and e.rule_outcome is O.UNACCEPTABLE
    assert "PUNE is not among the allowed" in e.explanation[0]


def test_a_customer_moving_the_seat_to_bengaluru_is_a_deviation_for_legal():
    e = _evaluate("In case of any dispute, the legal recourse is limited to the jurisdiction "
                  "of the court in Bangalore only. Any arbitration shall be seated in "
                  "Bengaluru, and the courts at Bengaluru shall have exclusive jurisdiction.")
    assert e.classification is C.DEVIATION and e.rule_outcome is O.UNACCEPTABLE
    assert e.actual_value == {"values": ["Bangalore", "Bengaluru"]}
    assert e.expected_value == {"allowed_values": ["MUMBAI", "BOMBAY_HIGH_COURT"]}
    assert "BENGALURU is not among the allowed" in e.explanation[0]


def test_pune_beside_another_city_is_still_a_deviation():
    e = _evaluate("Arbitration seated in Pune; the courts at Mumbai have exclusive jurisdiction.")
    assert e.classification is C.DEVIATION


@pytest.mark.parametrize("text", [
    "The parties submit to the exclusive jurisdiction of courts other than the courts at Pune.",
    "The courts at Pune shall have no jurisdiction; the courts at Mumbai shall.",
    "Pune courts shall not have jurisdiction over any dispute.",
])
def test_a_place_named_only_to_exclude_it_is_never_a_match(text):
    """QA-003 (2026-10-29): both of the tester's sentences read as "Pune" and were
    Acceptable. A place named to exclude it is not a stated venue; a person reads it."""
    e = _evaluate(text)
    assert e.classification is C.UNABLE_TO_EVALUATE and e.rule_outcome is O.NOT_APPLICABLE
    assert e.actual_value["reason"] == "VALUE_EXCLUDED"
    assert "only to exclude it" in e.explanation[0]


#: Our MSA 19.3/19.4 (AM-380): the High Court of Mumbai appoints the arbitrator "in the
#: event of no consensus" — a different noun's "no", never an exclusion.
_SECTION_22 = ("The Customer and LeapSwitch shall make every effort to resolve amicably by "
               "direct informal negotiations any dispute between them. Disputes shall be "
               "referred to arbitration by a single arbitrator to be mutually agreed upon "
               "and in the event of no consensus, then the High Court of Mumbai shall "
               "appoint an Arbitrator. The arbitration shall take place in {seat}, India "
               "and shall be conducted in the English language.")


def test_the_bombay_high_court_appointing_on_no_consensus_is_not_excluded():
    e = _evaluate(_SECTION_22.format(seat="Mumbai"))
    assert e.classification is C.MATCH and e.rule_outcome is O.ACCEPTABLE
    assert "reason" not in e.actual_value


def test_a_pune_seat_beside_the_same_wording_still_deviates():
    e = _evaluate(_SECTION_22.format(seat="Pune"))
    assert e.classification is C.DEVIATION and e.rule_outcome is O.UNACCEPTABLE
    assert "PUNE is not among the allowed" in e.explanation[0]


def test_an_exclusion_across_a_comma_free_phrase_still_excludes():
    e = _evaluate("Disputes go to courts other than the courts at Pune, Maharashtra.")
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert e.actual_value["reason"] == "VALUE_EXCLUDED"


def test_an_exclusive_mumbai_clause_with_no_other_court_still_matches():
    e = _evaluate("The courts at Mumbai shall have exclusive jurisdiction and no other "
                  "court shall have jurisdiction.")
    assert e.classification is C.MATCH


def test_a_clause_naming_no_place_is_never_a_match():
    e = _evaluate("Disputes shall be resolved by arbitration under the Arbitration Act.")
    assert e.classification is C.UNABLE_TO_EVALUATE
    assert e.rule_outcome is O.NOT_APPLICABLE
    assert e.actual_value == {"values": [], "reason": "NO_VALUE_STATED"}


def test_an_unresolved_mapping_compares_nothing():
    e = _evaluate("courts at Bengaluru", state=S.UNRESOLVED)
    assert e.classification is C.UNABLE_TO_EVALUATE


def test_no_dispute_clause_at_all_is_missing_with_no_evidence():
    e = _evaluate(None, state=S.NONE)
    assert e.classification is C.MISSING and e.evidence_refs == ()


def test_a_word_inside_another_word_is_not_a_place():
    assert read_values([_clause("The repune clause applies.")], CONFIG).values == ()


def test_a_standard_with_no_allowed_values_is_refused():
    with pytest.raises(CategoricalMisconfigured):
        read_values([_clause("courts at Pune")], {"recognised_values": {"PUNE": ["pune"]}})
