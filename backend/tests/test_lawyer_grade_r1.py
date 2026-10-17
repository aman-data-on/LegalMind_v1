"""Release 1 of the lawyer-grade review (`AM-156`): money only when the document's own
figures are unambiguous, never a ₹ risk where the direction is the deal's, a blank never
read as a term, and every finding given an action in the Constitution's own words.
Synthetic text only (54.6)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from legalmind.api import angles
from legalmind.assist.service import topic_requirements
from legalmind.extraction import commercial
from legalmind.extraction.liability import (
    PLACEHOLDER,
    LiabilityExtractionConfig,
    extract_liability_facts,
)
from legalmind.mapping.engine import Clause

ROOT = Path(__file__).resolve().parents[1] / "config" / "company_standards"
MOU = ["Service Costing: Rs. 7,57,000.00 + Rs. 1,36,260 (GST) Per Month",
       "Contract Agreement: 1 Year",
       "Any prepaid fees for the unutilised period shall be refunded pro-rata within 15 "
       "days of termination."]


def _clauses(*texts: str) -> list[Clause]:
    return [Clause(evidence_id=uuid4(), content=t) for t in texts]


def _row(code: str, cls: str, actual: dict, evidence: str = "", preferred=None) -> dict:
    return {"code": code, "classification": cls, "actual": actual,
            "expected": {"preferred": preferred} if preferred is not None else {},
            "finding": SimpleNamespace(id=uuid4()), "evidence_ids": [],
            "evidence": SimpleNamespace(content=evidence, section_number=None,
                                        section_title=None, page_number=None),
            "standard": {}}


# ------------------------------------------------------------------- R1/R2/R6 money
def test_a_value_only_from_one_fee_and_one_term_and_what_a_notice_leaves():
    facts = commercial.read(_clauses(*MOU))
    assert facts.committed_value == 9084000 and facts.missing is None
    assert commercial.not_committed(facts, 15) == 8705500      # less 15 days' notice
    assert facts.refund_text and "pro-rata" in facts.refund_text


def test_no_value_and_a_reason_when_the_figures_are_not_unambiguous():
    two = commercial.read(_clauses("Rs. 50,000 per month", "Rs. 70,000 per month",
                                   "Contract Term: 12 months"))
    assert two.committed_value is None and "more than one monthly fee" in two.missing
    unit = commercial.read(_clauses("Rs. 50,000 per server per month",
                                    "Contract Term: 12 months"))
    assert unit.committed_value is None and "per unit" in unit.missing
    bracket = commercial.read(_clauses("Rs. 50,000 per month",
                                       "The initial term is \\[one (1) year\\]."))
    assert bracket.term_months is None and "blank or in brackets" in bracket.missing
    po = commercial.read(_clauses("Fees shall be as set out in the relevant purchase order."))
    assert "another document" in po.missing


# ----------------------------------------------------------------- A4 placeholders
def test_a_blank_or_bracketed_figure_is_not_agreed_and_never_compared():
    config = LiabilityExtractionConfig.from_config(
        json.loads((ROOT / "PAYMENT-PERIOD-MSA-001.json").read_text())["configuration"])
    for text in ("Partner shall pay all invoices in full within \\[30\\] days of the "
                 "invoice date.",
                 "Customer shall pay all invoices within [30] days of the invoice date."):
        cap = extract_liability_facts(_clauses(text), config).caps[0]
        assert (cap.cap_status, cap.reason) == ("UNKNOWN", PLACEHOLDER), text
    plain = extract_liability_facts(
        _clauses("Customer shall pay all invoices within 30 days of the invoice date."),
        config).caps[0]
    assert plain.cap_value == 30


# --------------------------------------------------------------- R7 business points
def test_a_liability_cap_is_never_a_ranked_rupee_risk_and_is_shown_both_ways():
    facts = commercial.read(_clauses(*MOU))
    point = angles._point(_row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 6.0},
                               "Either party's aggregate liability shall not exceed ..."),
                          facts, None, legal_position=True)
    assert point["rupees"] is None and point["risk"] is False
    assert "what LeapSwitch can owe" in point["body"] and "can recover" in point["body"]


def test_notice_is_planning_time_not_money():
    facts = commercial.read(_clauses(*MOU))
    point = angles._point(_row("CONVENIENCE-NOTICE-MSA-001", "DEVIATION",
                               {"cap_value": 15.0}, preferred=30),
                          facts, None, legal_position=True)
    assert point["money"] is None and point["rupees"] is None
    assert "plan for the end" in point["body"]


def test_the_exit_point_says_what_is_not_committed_and_the_refund():
    facts = commercial.read(_clauses(*MOU))
    point = angles._point(_row("EARLY-TERM-RESTRICTION-MSA-001", "DEVIATION",
                               {"presence": "WAIVED"}), facts, (15.0, "days"),
                          legal_position=True)
    assert "₹87,05,500" in point["money"] and "₹90,84,000" in point["money"]
    assert point["rupees"] == 8705500 and "Prepaid fees" in point["body"]


def test_a_missing_end_of_term_notice_is_raised_on_a_fixed_term_contract():
    facts = commercial.read(_clauses(*MOU))
    point = angles._point(_row("AUTORENEW-MSA-001", "MISSING", {"cap_status": "ABSENT"},
                               preferred=30), facts, None, legal_position=True)
    assert "how much notice ends it" in point["headline"] and "30 days" in point["body"]


# --------------------------------------------------------------------- A2 actions
def test_every_finding_gets_an_action_in_the_constitutions_words():
    match = _row("GOVLAW-MSA-001", "MATCH", {"presence": "PRESENT"})
    uncapped = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"})
    differs = _row("CURE-PERIOD-MSA-001", "DEVIATION", {"cap_value": 15.0})
    unread = _row("LIABILITY-MSA-001", "UNABLE_TO_EVALUATE", {"cap_status": "UNREADABLE"})
    assert angles.action(match, False) == angles.ACCEPT
    assert angles.action(uncapped, True) == angles.MUST_CHANGE
    assert angles.action(differs, True) == angles.SEND_WORDING
    assert angles.action(differs, False) == angles.NO_WORDING
    assert angles.action(unread, False) == angles.READ_IT
    assert not any("reject" in a.lower() for a in (angles.ACCEPT, angles.MUST_CHANGE,
                                                   angles.SEND_WORDING, angles.READ_IT))


# --------------------------------------------------------------- Ask topic filter
def test_the_asked_topic_names_its_standards():
    codes = topic_requirements("Can this customer walk away early without paying us anything?")
    assert "EARLY-TERM-RESTRICTION-MSA-001" in codes
    assert "PAYMENT-PERIOD-MSA-001" not in codes


def test_the_comparison_commentary_screen_is_the_strict_one_again():
    """It shared `_VERDICT`'s name with the narrower P13 screen, which replaced it at
    import: "we recommend accepting" beside a comparison had stopped being caught."""
    from legalmind.assist.verification import agent_verify
    for text in ("We recommend accepting this clause.", "This clause is acceptable.",
                 "You should sign this agreement."):
        assert agent_verify._COMMENTARY_VERDICT.search(text), text
    assert not agent_verify._COMMENTARY_VERDICT.search(
        "The agreement allows 15 days; the standard allows 30 days.")


# ------------------------------------- pre-commit review of release 1 (2026-10-17)
def _period(code: str, text: str):
    config = LiabilityExtractionConfig.from_config(
        json.loads((ROOT / f"{code}.json").read_text())["configuration"])
    cap = extract_liability_facts(_clauses(text), config).caps[0]
    return cap.cap_status, cap.cap_value, cap.reason


def test_two_agreed_terms_keep_the_commitment_in_scope_but_give_no_value():
    clauses = _clauses('"Initial Term" shall mean a period of 36 months.',
                       "The Customer agrees to a lock-in period of 12 months.",
                       "Rs. 50,000 per month")
    assert commercial.states_fixed_term(clauses)                       # §14 stays
    assert commercial.read(clauses).committed_value is None


def test_a_number_repeated_in_brackets_is_a_term_not_a_blank():
    facts = commercial.read(_clauses("Rs. 50,000 per month",
                                     "a service period of 01 \\[ONE\\] Year from the date"))
    assert facts.term_months == 12 and facts.term_stated


def test_only_a_single_monthly_figure_becomes_a_value():
    term = "Contract Term: 12 months"
    for text in ("Annual fee of Rs. 6,00,000 payable monthly in advance.",
                 "Setup: Rs. 25,000 (one time). Recurring: Rs. 50,000 per month",
                 "Rs. 6,00,000 per annum, payable as Rs. 50,000 per month",
                 "Rs. 50,000 per month per server for 10 servers.",
                 "Rs. 50,000 per month for each server"):
        assert commercial.read(_clauses(text, term)).committed_value is None, text
    lakh = commercial.read(_clauses("Monthly charges: Rs. 7.57 lakh per month",
                                    "Contract Agreement: 1 Year"))
    assert lakh.committed_value == 9084000
    gst = commercial.read(_clauses(*MOU[:2]))
    assert gst.fee_per_month == 757000                  # the GST beside it is not a fee


def test_nothing_is_left_uncommitted_when_notice_outlasts_the_term():
    facts = commercial.read(_clauses("Rs. 50,000 per month", "Contract Term: 1 month"))
    assert commercial.not_committed(facts, 90) is None


def test_the_refund_search_is_bounded_on_long_unpunctuated_text():
    import time
    started = time.monotonic()
    commercial.read(_clauses("refund " * 1500, "pro rata 50,000 " * 600))
    assert time.monotonic() - started < 1


def test_a_blank_or_bracketed_figure_is_never_replaced_by_another_sentences():
    L, P = "LIABILITY-MSA-001", "PAYMENT-PERIOD-MSA-001"
    for code, text in (
            (L, "The total aggregate liability shall not exceed the fees paid in the "
                "______ months preceding the claim. Claims must be brought within 12 months."),
            (P, "Customer shall pay all invoices within [30] days of the invoice date. "
                "Disputed amounts shall be notified within 15 days of receipt."),
            (L, "The aggregate liability shall not exceed the fees paid in the [up to 12 "
                "months] preceding the claim."),
            (P, "Customer shall pay all invoices within [up to 30 days] of the invoice date."),
            (P, "Customer shall pay all invoices within [not more than thirty (30)] days of "
                "the invoice date."),
            (L, "The aggregate liability shall not exceed Rs. ________ or the fees paid.")):
        assert _period(code, text)[2] == PLACEHOLDER, text


def test_a_cross_reference_footnote_or_link_is_not_a_blank():
    L = "LIABILITY-MSA-001"
    for text in ("The aggregate liability shall not exceed the fees paid under this "
                 "Agreement, subject to [Clause 17.4].",
                 'The aggregate liability shall not exceed the fees paid under this '
                 'Agreement (the "Cap") [1].',
                 "The aggregate liability shall not exceed the fees paid under "
                 "[Schedule 2](#schedule-2)."):
        assert _period(L, text)[2] != PLACEHOLDER, text


def test_a_cap_is_said_to_bind_whom_its_own_sentence_says():
    facts = commercial.read(_clauses(*MOU))
    one_sided = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 6.0},
                     "Neither party shall be liable for indirect damages. The Service "
                     "Provider's aggregate liability shall not exceed the fees paid in the "
                     "six (6) months preceding the claim.")
    point = angles._point(one_sided, facts, None, legal_position=True)
    assert point["headline"].startswith("LeapSwitch's liability")
    assert "either way" not in point["money"]
    mutual = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 6.0},
                  "Each party's aggregate liability shall not exceed the fees paid in the "
                  "six (6) months preceding the claim.")
    assert "either way" in angles._point(mutual, facts, None, legal_position=True)["money"]


def test_a_partner_agreement_notice_is_not_a_customer_redeploying_capacity():
    row = _row("CONVENIENCE-NOTICE-PARTNER_AGREEMENT-001", "DEVIATION", {"cap_value": 15.0})
    row["standard"] = {"document_type": "PARTNER_AGREEMENT"}
    point = angles._point(row, commercial.read(_clauses(*MOU)), None, legal_position=True)
    assert "customer" not in point["headline"] and "capacity" not in point["body"]


def test_a_document_type_alone_names_no_topic():
    assert topic_requirements("Can we sign this NDA?") == []


def test_a_company_position_is_not_wording_to_send_and_every_reader_gets_the_action(
        monkeypatch):
    """§14 has a Company Position and no Drafting Notes: the action must not say "send
    our wording". And a reader without the positions permission gets the same action —
    only the wording itself is withheld (SEC-07)."""
    exit_row = _row("EARLY-TERM-RESTRICTION-MSA-001", "DEVIATION", {"presence": "WAIVED"})
    exit_row.update(title="Early exit", standard={"constitution": {"section": "14"}})
    cure_row = _row("CURE-PERIOD-MSA-001", "DEVIATION", {"cap_value": 15.0})
    cure_row.update(title="Cure", standard={"constitution": {"section": "13"}})
    monkeypatch.setattr(angles, "_rows", lambda db, review: [exit_row, cure_row])
    monkeypatch.setattr(angles, "load_clauses", lambda db, version: _clauses(*MOU))
    monkeypatch.setattr(angles, "_proposals", lambda db, sections: {
        "14": {"section": "14", "kind": "COMPANY_POSITION", "label": "§14", "text": "x"},
        "13": {"section": "13", "kind": "DRAFTING_LANGUAGE", "label": "§13", "text": "y"}})
    review = SimpleNamespace(document_version_id=uuid4())
    for legal_position in (True, False):
        out = angles.review_angles(None, review, legal_position=legal_position)
        actions = {i["requirement_code"]: i["action"] for i in out["legal"]["items"]}
        assert actions["EARLY-TERM-RESTRICTION-MSA-001"] == angles.NO_WORDING
        assert actions["CURE-PERIOD-MSA-001"] == angles.SEND_WORDING
        assert bool(out["counter_proposals"]) is legal_position


def test_a_carve_out_naming_leapswitch_does_not_make_the_cap_leapswitchs():
    from legalmind.api.angles import _whose_cap
    row = {"evidence": SimpleNamespace(content=(
        "Liability capped at amount paid by customer in last 6 months, provided that such "
        "cap shall not apply to Leapswitch's liability arising from fraud."))}
    assert _whose_cap(row) is None          # the subject is "Liability": unsaid, not ours
