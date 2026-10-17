"""A clause that WAIVES the company's position, and the commercial pillars (AM-151/AM-152).

A customer's MOU said "No lock-in, early termination charges … shall apply" on a one-year,
₹90,84,000 contract. The engine said nothing: the early-exit standard's term "early
termination charge" missed the plural, and PRESENCE would in any case have read the
clause's mere presence as a MATCH. These pin the fixes on synthetic text (54.6).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from legalmind.analysis import semantic
from legalmind.analysis.service import opposed_span, waiver_signals
from legalmind.domain.enums import EvaluatorType, FindingClassification, MappingState
from legalmind.domain.enums import RuleOutcome as O
from legalmind.evaluation.contracts import (
    CompanyStandard,
    EvaluatorInput,
    LegalRule,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.registry import evaluate, version_for
from legalmind.extraction import commercial
from legalmind.mapping.engine import Clause, map_requirement
from legalmind.mapping.rules import MappingRules
from legalmind.mapping.scoring import contains_phrase

WAIVER = ("The Customer may terminate on 15 days prior written notice. No lock-in, early "
          "termination charges, penalties or charges for the unexpired Term shall apply.")
RESTRICTION = ("The Customer shall have no right to terminate this Agreement before the "
               "expiry of the Term.")
PATTERNS = ("no lock-in", "no early termination charge", "no minimum commitment")
RULES = MappingRules(aliases=("early termination charge",), confirm_threshold=5)


def _clause(text: str) -> Clause:
    return Clause(evidence_id=uuid4(), content=text, section_number="13",
                  section_title="Service Termination")


def _presence(state, opposed=False):
    return evaluate(EvaluatorInput(
        requirement=RequirementContext(requirement_version_id=uuid4(),
                                       code="EARLY-TERM-RESTRICTION-MSA-001",
                                       evaluator_type=EvaluatorType.PRESENCE),
        company_standard=CompanyStandard(version_id=uuid4(),
                                         configuration={"expected_presence": "PRESENT"}),
        evaluator_version=version_for(EvaluatorType.PRESENCE),
        mapping=MappingInput(mapping_state=state, opposed=opposed),
        legal_rule=LegalRule(version_id=uuid4(), configuration={
            "deviation_outcome": "UNACCEPTABLE", "unlimited_outcome": "UNACCEPTABLE"},
        ))).evaluations[0]


# ------------------------------------------------------------- inflection (AM-151)
def test_a_configured_term_reads_its_regular_inflections():
    assert contains_phrase("no early termination charges shall apply",
                           "early termination charge")
    assert contains_phrase("the agreement was terminated early", "agreement was terminate")
    assert contains_phrase("liabilities of either party", "liability")   # one word: plural
    assert contains_phrase("all fees are due", "fee")
    assert not contains_phrase("a client", "lien")              # still whole words
    assert not contains_phrase("capital", "cap")


def test_the_plural_alone_now_confirms_the_early_exit_term():
    clause = _clause("No early termination charges shall apply.")
    assert map_requirement(uuid4(), RULES, [clause]).state is not MappingState.NONE


# ---------------------------------------------------------------- polarity (AM-152)
def test_a_clause_that_waives_the_position_is_a_deviation_never_a_match():
    e = _presence(MappingState.CONFIRMED, opposed=True)
    assert e.classification is FindingClassification.DEVIATION
    assert e.rule_outcome is O.UNACCEPTABLE
    assert e.actual_value == {"presence": "WAIVED"}


def test_a_clause_that_states_the_position_is_still_a_match():
    e = _presence(MappingState.CONFIRMED)
    assert e.classification is FindingClassification.MATCH


def test_a_waiver_phrase_confirms_the_clause_and_names_its_sentence():
    waiver, restriction = _clause(WAIVER), _clause(RESTRICTION)
    signals = waiver_signals([waiver, restriction], PATTERNS, 5)
    assert set(signals) == {waiver.evidence_id}
    mapping = map_requirement(uuid4(), RULES, [waiver, restriction], extra_signals=signals)
    assert mapping.state is MappingState.CONFIRMED
    assert opposed_span(mapping).startswith("No lock-in, early termination charges")


def test_a_restriction_alone_carries_no_opposition():
    restriction = _clause(RESTRICTION)
    mapping = map_requirement(uuid4(), MappingRules(
        aliases=("no right to terminate",), confirm_threshold=3), [restriction])
    assert opposed_span(mapping) is None


# ------------------------------------------- the selected model decides (AM-152)
def _egress(position: str, span: str):
    def call(prompt, version):
        return SimpleNamespace(
            text=json.dumps({"verdicts": [{"clause": 1, "addresses": "YES",
                                           "position": position, "span": span}]}),
            model="any-selected-model", prompt_version=version, payload_sha256="0")
    return call


def test_the_selected_models_opposed_verdict_on_a_verbatim_span_decides(monkeypatch):
    clause = _clause(WAIVER)
    monkeypatch.setattr(semantic, "_nli", lambda pairs: [(0.01, 0.97)])
    signals, notes = semantic.adjudicate(
        "Early exit is charged", "", [(clause, 0.7)], 5,
        _egress("OPPOSED", "No lock-in, early termination charges, penalties"),
        position_statement="No early exit is permitted without a financial consequence.",
        opposable=True)
    assert signals[clause.evidence_id][0].kind == "semantic_opposed"
    assert any("OPPOSES" in n and "contradiction 0.97" in n for n in notes)


def test_the_local_nli_tripwire_sends_a_probable_misreading_to_a_person(monkeypatch):
    clause = _clause(RESTRICTION)
    monkeypatch.setattr(semantic, "_nli", lambda pairs: [(0.95, 0.0)])
    signals, notes = semantic.adjudicate(
        "Early exit is charged", "", [(clause, 0.7)], 5,
        _egress("OPPOSED", "shall have no right to terminate this Agreement"),
        position_statement="No early exit is permitted without a financial consequence.",
        opposable=True)
    assert signals[clause.evidence_id][0].kind == "semantic_candidate"   # weak, +1
    assert any("tripwire" in n for n in notes)


def test_an_unverifiable_span_is_never_an_opposition(monkeypatch):
    clause = _clause(WAIVER)
    monkeypatch.setattr(semantic, "_nli", lambda pairs: [(0.0, 0.99)])
    signals, _ = semantic.adjudicate("Early exit is charged", "", [(clause, 0.7)], 5,
                                     _egress("OPPOSED", "words the clause never says"),
                                     opposable=True)
    assert signals[clause.evidence_id][0].kind == "semantic_candidate"


# ------------------------------------------------------- commercial facts (AM-152)
def test_the_fee_and_the_committed_term_are_read_from_the_documents_own_words():
    facts = commercial.read([
        _clause("Service Costing: Rs. 7,57,000.00 + Rs. 1,36,260 (GST) Per Month"),
        _clause("Contract Agreement: 1 Year"),
    ])
    assert facts.fee_per_month == 757000.0 and facts.term_months == 12
    assert facts.committed_value == 9084000.0
    assert commercial.rupees(facts.committed_value) == "₹90,84,000"


def test_no_committed_term_means_no_fixed_term():
    assert not commercial.states_fixed_term([_clause("Services renew monthly; cancel at "
                                                     "any time.")])
    assert commercial.states_fixed_term([_clause("Contract Duration Annual")])
    assert commercial.read([_clause("an initial term of thirty-six (36) months")]
                           ).term_months == 36


def test_the_tripwire_also_catches_a_waiver_the_model_read_as_the_position(monkeypatch):
    """The owner's scenario, step 4: had the selected model marked the waiving clause
    SAME (acceptable), the local NLI's contradiction on its span sends it to a person."""
    clause = _clause(WAIVER)
    monkeypatch.setattr(semantic, "_nli", lambda pairs: [(0.0, 0.97)])
    signals, notes = semantic.adjudicate(
        "Early exit is charged", "", [(clause, 0.7)], 5,
        _egress("SAME", "No lock-in, early termination charges, penalties"),
        position_statement="No early exit is permitted without a financial consequence.",
        opposable=True)
    assert signals[clause.evidence_id][0].kind == "semantic_candidate"
    assert any("contradicting" in n and "tripwire" in n for n in notes)


# ------------------------------------------------ owner rulings of 2026-10-16 (AM-154)
def test_working_days_are_never_calendar_days():
    """"Do NOT allow the system to treat working days as calendar days" — a period
    stated in working or business days deviates from a calendar-day standard."""
    import json as _json
    from pathlib import Path

    from legalmind.evaluation.contracts import LiabilityFacts
    from legalmind.extraction.liability import (
        LiabilityExtractionConfig,
        extract_liability_facts,
    )
    root = Path(__file__).resolve().parents[1] / "config" / "company_standards"
    payload = _json.loads((root / "PAYMENT-PERIOD-MSA-001.json").read_text())
    config = LiabilityExtractionConfig.from_config(payload["configuration"])
    for text in ("Invoices shall be paid within 21 business days of the invoice date.",
                 "Invoices shall be paid within 21 working days of the invoice date."):
        facts = extract_liability_facts([_clause(text)], config)
        e = evaluate(EvaluatorInput(
            requirement=RequirementContext(requirement_version_id=uuid4(),
                                           code="PAYMENT-PERIOD-MSA-001",
                                           evaluator_type=EvaluatorType.NUMERIC_COMPARISON),
            company_standard=CompanyStandard(version_id=uuid4(),
                                             configuration=payload["configuration"]),
            evaluator_version=version_for(EvaluatorType.NUMERIC_COMPARISON),
            facts=LiabilityFacts(caps=facts.caps),
            mapping=MappingInput(mapping_state=MappingState.CONFIRMED),
            legal_rule=LegalRule(version_id=uuid4(),
                                 configuration=payload["legal_rule"]["configuration"]),
        )).evaluations[0]
        assert e.classification is FindingClassification.DEVIATION, text
        assert e.actual_value["cap_unit"] == "WORKING_DAYS"
        assert e.rule_outcome is O.UNACCEPTABLE              # a person decides
    calendar = extract_liability_facts(
        [_clause("Invoices shall be paid within 21 days of the invoice date.")], config)
    assert calendar.caps[0].cap_status == "FINITE"            # calendar days unchanged


def test_an_indemnity_broader_than_the_position_goes_to_a_person():
    e = evaluate(EvaluatorInput(
        requirement=RequirementContext(requirement_version_id=uuid4(),
                                       code="INDEMNITY-MSA-001",
                                       evaluator_type=EvaluatorType.PRESENCE),
        company_standard=CompanyStandard(version_id=uuid4(),
                                         configuration={"expected_presence": "PRESENT"}),
        evaluator_version=version_for(EvaluatorType.PRESENCE),
        mapping=MappingInput(mapping_state=MappingState.CONFIRMED, too_broad=True),
        legal_rule=LegalRule(version_id=uuid4(), configuration={
            "deviation_outcome": "UNACCEPTABLE", "unlimited_outcome": "UNACCEPTABLE"}),
    )).evaluations[0]
    assert e.classification is FindingClassification.DEVIATION
    assert e.actual_value == {"presence": "TOO_BROAD"}
    assert e.rule_outcome is O.UNACCEPTABLE


# --------------------------------------------- pre-commit review fixes (AM-155)
def _standard(code: str) -> dict:
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "config" / "company_standards"
    return json.loads((root / f"{code}.json").read_text())


def _period(code: str, text: str):
    from legalmind.extraction.liability import (
        LiabilityExtractionConfig,
        extract_liability_facts,
    )
    config = LiabilityExtractionConfig.from_config(_standard(code)["configuration"])
    cap = extract_liability_facts([_clause(text)], config).caps[0]
    return cap.cap_status, cap.cap_value


def test_a_one_word_term_reads_its_plural_only():
    assert not contains_phrase("abc private limited", "limit")          # not "limited"
    assert not contains_phrase("payment and invoicing", "invoice")
    assert contains_phrase("all invoices", "invoice")


def test_a_heading_term_is_matched_exactly_and_scored_once():
    from legalmind.mapping.scoring import score_clause
    rules = MappingRules(section_heading_terms=("payment", "invoice", "invoicing"),
                         confirm_threshold=5)
    score = score_clause(rules, content="Text.", section_title="8. PAYMENT AND INVOICING")
    assert score.score == 4                       # payment + invoicing, never 6


def test_working_days_are_read_only_for_a_period_standard_and_its_own_sentence():
    assert _period("LIABILITY-MSA-001", "Aggregate liability shall not exceed the fees paid "
                   "in the preceding quarter. Claims must be notified within 10 business "
                   "days.")[0] != "WORKING_DAYS"
    assert _period("CURE-PERIOD-MSA-001", "Either party may terminate if a material breach "
                   "is not cured within one (1) month of written notice; the breaching party "
                   "shall acknowledge the notice within 5 business days.")[0] == "UNKNOWN"
    assert _period("DISPUTE-WINDOW-MSA-001", "Any invoice dispute must be raised in writing "
                   "within seven (7) working days of receipt of the invoice.") == \
        ("WORKING_DAYS", 7.0)


def test_a_waiver_inside_a_for_cause_carve_out_is_not_a_waiver():
    cfg = _standard("EARLY-TERM-RESTRICTION-MSA-001")["configuration"]
    carve_out = _clause("Where the Customer terminates under Clause 13.2 for LeapSwitch's "
                        "uncured material breach, early termination charges shall not apply.")
    assert waiver_signals([carve_out], cfg["waiver_patterns"], 5,
                          conditions=cfg["waiver_conditions"]) == {}
    assert waiver_signals([_clause(WAIVER)], cfg["waiver_patterns"], 5,
                          conditions=cfg["waiver_conditions"])


def test_breadth_is_what_the_indemnity_covers_never_what_it_excludes_or_keeps():
    from legalmind.analysis.service import breadth_hit
    cfg = _standard("INDEMNITY-MSA-001")["configuration"]
    assert breadth_hit([_clause("The Customer shall indemnify Leapswitch against all losses, "
                                "including indirect and consequential damages.")], cfg)
    assert breadth_hit([_clause("The Company will, for any Claim for which it seeks "
                                "indemnification, give Partner sole control of the defense "
                                "and settlement of the Claim.")], cfg)
    for narrower in (
            "Each party shall indemnify the other; this indemnity shall not extend to "
            "indirect or consequential losses.",
            "In no event shall either party be liable for any indirect or consequential "
            "damages, except in respect of a party's obligation to indemnify the other.",
            "The Customer shall indemnify Leapswitch, and Leapswitch shall retain control "
            "of the defence and the choice of counsel.",
            "Neither party shall be liable for indirect loss."):        # no indemnity
        assert breadth_hit([_clause(narrower)], cfg) is None, narrower


def test_an_opposed_verdict_only_opposes_a_standard_that_can_be_waived(monkeypatch):
    clause = _clause(WAIVER)
    monkeypatch.setattr(semantic, "_nli", lambda pairs: None)
    signals, notes = semantic.adjudicate(
        "Liability is capped", "", [(clause, 0.7)], 5,
        _egress("OPPOSED", "No lock-in, early termination charges, penalties"))
    assert signals[clause.evidence_id][0].kind == "semantic_candidate"   # a person
    assert any("different position" in n for n in notes)


def test_the_waiving_sentence_survives_an_apostrophe(monkeypatch):
    text = "Fees are payable monthly. The Customer's lock-in shall not apply. Other terms."
    clause = _clause(text)
    monkeypatch.setattr(semantic, "_nli", lambda pairs: None)
    signals, _ = semantic.adjudicate("Early exit is charged", "", [(clause, 0.7)], 5,
                                     _egress("OPPOSED", "The Customer's lock-in shall not apply"),
                                     opposable=True)
    mapping = map_requirement(uuid4(), MappingRules(confirm_threshold=5), [clause],
                              extra_signals=signals)
    assert opposed_span(mapping) == "The Customer's lock-in shall not apply."


def test_an_unknown_or_unconfigured_review_model_never_aborts_the_review(monkeypatch):
    import pytest

    from legalmind.analysis.service import _review_model
    from legalmind.assist.agent import model_router
    monkeypatch.setenv("LEGALMIND_REVIEW_MODEL", "no-such-model")
    with pytest.raises(model_router.UnknownModel):      # caught by the egress: lexical
        _review_model()
    monkeypatch.setenv("LEGALMIND_REVIEW_MODEL", "gemini")
    assert _review_model() is None


def test_the_business_angle_never_turns_working_days_into_days_or_money():
    from legalmind.api import angles
    row = {"code": "CONVENIENCE-NOTICE-MSA-001", "classification": "DEVIATION",
           "actual": {"cap_value": 15.0, "cap_unit": "WORKING_DAYS"},
           "expected": {"preferred": 30}, "finding": SimpleNamespace(id=uuid4()),
           "evidence": None, "evidence_ids": [], "standard": {}}
    facts = commercial.CommercialFacts(fee_per_month=100000.0, fee_text="₹1,00,000 per month")
    point = angles._point(row, facts, None, legal_position=True)
    assert "15 working days' notice" in point["headline"]
    assert point["money"] is None and point["rupees"] is None
    calendar = {**row, "actual": {"cap_value": 15.0}}
    hidden = angles._point(calendar, facts, None, legal_position=False)
    assert hidden["rupees"] is None                     # the standard is never derivable


def test_the_venue_named_is_the_one_the_standard_does_not_allow():
    from legalmind.api import angles
    std = _standard("DISPUTE-VENUE-MSA-001")["configuration"]
    assert angles._outside({"values": ["Pune", "Mumbai"]}, std) == "Mumbai"


def test_breadth_reads_a_confirmed_clauses_own_continuation_paragraph():
    from legalmind.analysis.service import _with_continuations, breadth_hit
    cfg = _standard("INDEMNITY-MSA-001")["configuration"]
    head = Clause(evidence_id=uuid4(), content="14.1 The Partner shall defend, indemnify, "
                  "and hold harmless the Company.", section_number="14.1")
    tail = Clause(evidence_id=uuid4(), content="The Company will, for any Claim for which "
                  "it seeks indemnification, give Partner sole control of the defense.")
    other = Clause(evidence_id=uuid4(), content="15. Notices.", section_number="15")
    mapping = map_requirement(uuid4(), MappingRules(
        exact_phrases=("defend, indemnify, and hold harmless",), confirm_threshold=5),
        [head, tail, other])
    assert [c.evidence_id for c in _with_continuations([head, tail, other], mapping)] == \
        [head.evidence_id, tail.evidence_id]
    assert breadth_hit(_with_continuations([head, tail, other], mapping), cfg)


def test_a_waiver_beside_a_clause_stating_the_position_is_a_conflict_not_a_waiver():
    """/code-review, 2026-10-17: one stray waiver phrase (a schedule's "no minimum
    commitment") never speaks for the whole document — a person decides."""
    from legalmind.analysis.service import contested
    stating = _clause("If the Customer terminates early, the early termination charge "
                      "is the charges for the unexpired Term.")
    waiving = _clause("Add-on backups carry no minimum commitment and no early "
                      "termination charge.")
    rules = MappingRules(exact_phrases=("charges for the unexpired term",),
                         aliases=("early termination charge",), confirm_threshold=5)
    signals = waiver_signals([stating, waiving], PATTERNS, 5)
    mapping = map_requirement(uuid4(), rules, [stating, waiving], extra_signals=signals)
    assert len(mapping.candidates) == 2 and contested(mapping)
    alone = map_requirement(uuid4(), rules, [waiving], extra_signals=signals)
    assert not contested(alone)                              # a waiver alone stays WAIVED
    e = evaluate(EvaluatorInput(
        requirement=RequirementContext(requirement_version_id=uuid4(),
                                       code="EARLY-TERM-RESTRICTION-MSA-001",
                                       evaluator_type=EvaluatorType.PRESENCE),
        company_standard=CompanyStandard(version_id=uuid4(),
                                         configuration={"expected_presence": "PRESENT"}),
        evaluator_version=version_for(EvaluatorType.PRESENCE),
        mapping=MappingInput(mapping_state=MappingState.CONFIRMED, opposed=True,
                             contested=True),
        legal_rule=LegalRule(version_id=uuid4(), configuration={
            "deviation_outcome": "UNACCEPTABLE", "unlimited_outcome": "UNACCEPTABLE"}),
    )).evaluations[0]
    assert e.classification is FindingClassification.CONFLICT        # never MATCH/WAIVED
    assert e.actual_value != {"presence": "WAIVED"}



def test_a_carve_out_or_a_mere_mention_never_contests_a_waiver():
    """Re-review, 2026-10-17: only positive evidence states the position — a for-cause
    carve-out ("…without any early termination charge" on our breach) does not."""
    from legalmind.analysis.service import contested
    waiver = _clause("There is no lock-in period and no early termination charge for "
                     "this Order.")
    carve_out = _clause("If LeapSwitch is in material breach, the Customer may terminate "
                        "and the charges for the unexpired term shall not apply.")
    rules = MappingRules(exact_phrases=("charges for the unexpired term",),
                         aliases=("early termination charge",), confirm_threshold=3)
    signals = waiver_signals([waiver, carve_out], PATTERNS, 5)
    mapping = map_requirement(uuid4(), rules, [waiver, carve_out], extra_signals=signals)
    assert not contested(mapping, ("material breach",))     # the waiver stands


def test_a_for_cause_span_the_model_calls_opposed_is_left_to_a_person(monkeypatch):
    """Review of AM-155 (2026-10-17): the model's OPPOSED verdict on a for-cause
    carve-out is read as `waiver_signals` reads the phrase — a carve-out, not a waiver."""
    text = ("The Customer may terminate for material breach without any early termination "
            "charge.")
    clause = _clause(text)
    monkeypatch.setattr(semantic, "_nli", lambda pairs: [(0.01, 0.97)])
    signals, notes = semantic.adjudicate(
        "Early exit is charged", "", [(clause, 0.7)], 5, _egress("OPPOSED", text),
        position_statement="No early exit is permitted without a financial consequence.",
        opposable=True, conditions=("material breach",))
    assert signals[clause.evidence_id][0].kind == "semantic_candidate"
    assert any("carve-out" in n for n in notes)
