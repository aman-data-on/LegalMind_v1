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
            "finding": SimpleNamespace(id=uuid4(), status=None), "evidence_ids": [],
            "evidence": SimpleNamespace(content=evidence, section_number=None,
                                        section_title=None, page_number=None),
            "standard": {}, "document_type": "MSA"}


# ------------------------------------------------------------------- R1/R2/R6 money
def test_a_value_only_from_one_fee_and_one_term_and_the_refund_sentence():
    facts = commercial.read(_clauses(*MOU))
    assert facts.committed_value == 9084000 and facts.missing is None
    assert facts.refund_text and "pro-rata" in facts.refund_text


def test_no_value_and_a_reason_when_the_figures_are_not_unambiguous():
    two = commercial.read(_clauses("Rs. 50,000 per month", "Rs. 70,000 per month",
                                   "Contract Term: 12 months"))
    assert two.committed_value is None and "more than one monthly amount" in two.missing
    unit = commercial.read(_clauses("Rs. 50,000 per server per month",
                                    "Contract Term: 12 months"))
    assert unit.committed_value is None and "per unit" in unit.missing
    bracket = commercial.read(_clauses("Monthly fee: Rs. 50,000 per month",
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


def test_the_exit_point_states_the_whole_commitment_and_the_notice_in_days():
    """No deduction for the notice: days are never a fraction of a month (AM-62), so the
    figure is the whole committed value and the notice is said in its own days."""
    facts = commercial.read(_clauses(*MOU))
    point = angles._point(_row("EARLY-TERM-RESTRICTION-MSA-001", "DEVIATION",
                               {"presence": "WAIVED"}), facts, (15.0, "days"),
                          legal_position=True)
    assert "Up to ₹90,84,000 of committed fees is not secured" in point["money"]
    assert point["rupees"] == 9084000 and "15 days' notice" in point["body"]
    assert "Prepaid fees" in point["body"]


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
    # AM-156 R7 (corrected 2026-10-21): a one-way cap carries no rupees — only both ways
    assert point["money"] is None
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
    monkeypatch.setattr(angles, "_review_document_type", lambda db, review: "OTHER")
    monkeypatch.setattr(angles.reading, "read", lambda *a: None)
    monkeypatch.setattr(angles, "group_ids", lambda db, ids, **kw: {})  # AM-179 fold
    monkeypatch.setattr(angles, "_proposals", lambda db, sections: {
        "14": {"section": "14", "kind": "COMPANY_POSITION", "label": "§14", "text": "x"},
        "13": {"section": "13", "kind": "DRAFTING_LANGUAGE", "label": "§13", "text": "y"}})
    review = SimpleNamespace(id=None, document_version_id=uuid4())
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



# ------------------------------- /code-review of PR #213 (owner, 2026-10-17)
def _fee(*texts):
    return commercial.read(_clauses(*texts)).fee_per_month


def test_an_amount_is_read_whole_and_only_after_a_currency_word():
    term = " Contract Agreement: 1 Year"
    assert _fee("Fee: Rs. 15000 per month." + term) == 15000.0
    assert _fee("Charges INR 1500000/mo." + term) == 1500000.0
    assert _fee("Fee: Rs. 1,50,000.00 per month." + term) == 150000.0
    assert _fee("Dedicated servers 4 per month." + term) is None        # "rs" in a word
    assert _fee("Dedicated servers 4 per month.", "Fee: Rs. 15,000 per month." + term) \
        == 15000.0


def test_a_late_fee_or_credit_is_never_the_monthly_fee():
    term = " Contract Agreement: 1 Year"
    assert _fee("Late payment interest of Rs. 500 per month on overdue sums." + term) is None
    assert _fee("A service credit of Rs. 2,000 per month of downtime." + term) is None
    # a fee beside a late fee: two monthly amounts — withheld, never a guess (fail closed)
    assert _fee("Fee: Rs. 15,000 per month. Late fee Rs. 500 per month." + term) is None


def test_an_unnumbered_documents_tail_is_not_the_indemnitys_continuation():
    from legalmind.analysis.service import _with_continuations, breadth_hit
    from legalmind.mapping.engine import map_requirement
    from legalmind.mapping.rules import MappingRules
    cfg = json.loads((ROOT / "INDEMNITY-MSA-001.json").read_text())["configuration"]
    indemnity = Clause(evidence_id=uuid4(), content="The Customer shall defend, indemnify, "
                       "and hold harmless the Provider against third-party claims.")
    later = [Clause(evidence_id=uuid4(), content="Fees are payable within thirty days."),
             Clause(evidence_id=uuid4(), content="The Provider may recover lost profits "
                    "for late payment.")]
    mapping = map_requirement(uuid4(), MappingRules(
        exact_phrases=("defend, indemnify, and hold harmless",), confirm_threshold=5),
        [indemnity, *later])
    kept = _with_continuations([indemnity, *later], mapping)
    assert [c.evidence_id for c in kept] == [indemnity.evidence_id]   # trimmed, r19/r25
    assert breadth_hit(kept, cfg) is None         # the remainder's "lost profits" is not it


def test_a_heading_with_a_short_body_or_a_signature_block_ends_the_indemnity():
    """r29: a run is closed on a paragraph's FIRST line, so "Governing Law\nIndian law
    applies." or "IN WITNESS WHEREOF …" ends it and its continuation is still read."""
    for closer in ("Governing Law\nIndian law applies.",
                   "IN WITNESS WHEREOF the parties have executed this Agreement."):
        assert _breadth_of(
            "Fees\n\nThe fees are set out in the order form and are payable monthly in "
            "advance by the Customer to the Provider.\n\nYou agree to defend, indemnify, "
            "and hold harmless the Provider against third-party claims.\n\nThe Provider "
            "will notify you of any claim for which it seeks indemnification and give you "
            "sole control of the defense and settlement of the claim.\n\n" + closer
        ) == "control of the defense", closer


def test_the_business_point_reads_the_scope_that_gave_the_finding_its_class():
    from legalmind.domain.enums import FindingClassification as C
    match = SimpleNamespace(classification=C.MATCH, actual_value={"cap_value": 12.0})
    deviation = SimpleNamespace(classification=C.DEVIATION, actual_value={"cap_value": 3.0})
    assert angles._governing([match, deviation], C.DEVIATION) is deviation
    assert angles._governing([match], C.DEVIATION) is match       # never None while one exists


def test_uncapped_liability_is_said_and_never_ranked():
    point = angles._point(_row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"},
                               preferred=12), commercial.read(_clauses(*MOU)), None,
                          legal_position=True)
    assert point["headline"] == "Liability is not capped in this clause"
    assert point["risk"] is False and point["rupees"] is None and point["money"] is None


def test_a_position_keeps_every_paragraph_and_drafting_language_wins():
    rows = [("17", "Legal Constitution L1.13 · 17 · Company Position", "First para."),
            ("17", "Legal Constitution L1.13 · 17 · Company Position", "Second para."),
            ("13", "Legal Constitution L1.13 · 13 · Drafting Notes for Counsel", "Wording."),
            ("13", "Legal Constitution L1.13 · 13 · Company Position", "Position.")]
    db = SimpleNamespace(execute=lambda *a, **k: SimpleNamespace(all=lambda: rows))
    out = angles._proposals(db, {"13", "17"})
    assert out["17"]["text"] == "First para.\n\nSecond para."
    assert out["13"]["kind"] == "DRAFTING_LANGUAGE" and out["13"]["text"] == "Wording."


def test_a_labelled_unnumbered_clause_keeps_its_own_continuation():
    """An unnumbered partner agreement: the indemnity's "The Company will: … sole control
    of the defense" paragraph is its continuation; the next "Title:" label ends it."""
    from legalmind.analysis.service import _with_continuations, breadth_hit
    from legalmind.mapping.engine import map_requirement
    from legalmind.mapping.rules import MappingRules
    cfg = json.loads((ROOT / "INDEMNITY-MSA-001.json").read_text())["configuration"]
    head = Clause(evidence_id=uuid4(), content="Partner Indemnification of Company: The "
                  "Partner shall defend, indemnify, and hold harmless the Company.")
    tail = Clause(evidence_id=uuid4(), content="The Company will: (i) notify Partner of any "
                  "Claim for which it seeks indemnification, (ii) give Partner sole control "
                  "of the defense of the Claim.")
    nxt = Clause(evidence_id=uuid4(), content="Confidentiality")
    later = Clause(evidence_id=uuid4(), content="Liability for indirect damages is excluded "
                   "save for a party's indemnity obligations.")
    clauses = [head, tail, nxt, later]
    mapping = map_requirement(uuid4(), MappingRules(
        exact_phrases=("defend, indemnify, and hold harmless",), confirm_threshold=5), clauses)
    kept = _with_continuations(clauses, mapping)
    assert [c.evidence_id for c in kept] == [head.evidence_id, tail.evidence_id]
    assert breadth_hit(kept, cfg) == "control of the defense"



def test_only_a_real_indemnity_title_brings_its_clause_into_breadth():
    """A separate "Indemnification Procedure:" clause is the indemnity's own; a cap
    sentence the parser took as a title ("In no event, whether in contract, indemnity,
    …") is not, so its "indirect" is never read as the indemnity's breadth."""
    from legalmind.analysis.service import _titled_for
    cfg = json.loads((ROOT / "INDEMNITY-MSA-001.json").read_text())["configuration"]
    procedure = Clause(evidence_id=uuid4(), content="Indemnification Procedure: The Company "
                       "will give Partner sole control of the defense of any Claim.")
    cap = Clause(evidence_id=uuid4(), section_number="13.2", section_title="In no event, "
                 "whether in contract, indemnity, warranty, tort (including negligence), "
                 "strict liability or", content="otherwise, shall either party be liable for "
                 "any indirect or consequential loss.")
    combined = Clause(evidence_id=uuid4(), content="Limitation of Liability and Indemnity: "
                      "Neither Party will be liable for any indirect or consequential loss.")
    assert _titled_for([procedure, cap, combined], cfg) == [procedure]


def test_lost_profits_that_shall_not_be_recoverable_are_not_the_indemnitys_breadth():
    from legalmind.analysis.service import breadth_hit
    cfg = json.loads((ROOT / "INDEMNITY-MSA-001.json").read_text())["configuration"]
    clause = Clause(evidence_id=uuid4(), content="The Customer shall indemnify Leapswitch "
                    "against all third-party claims, provided that lost profits shall not "
                    "be recoverable under this indemnity.")
    assert breadth_hit([clause], cfg) is None


def test_word_auto_numbered_items_stay_with_their_numbered_clause():
    """Word's automatic (a)–(e) numbering is not rendered, so the items arrive
    unnumbered: they continue 14.1 until 14.2, whatever their count."""
    from legalmind.analysis.service import _with_continuations, breadth_hit
    from legalmind.mapping.engine import map_requirement
    from legalmind.mapping.rules import MappingRules
    cfg = json.loads((ROOT / "INDEMNITY-MSA-001.json").read_text())["configuration"]
    head = Clause(evidence_id=uuid4(), section_number="14.1", content="The Partner shall "
                  "defend, indemnify, and hold harmless the Company against claims arising "
                  "out of:")
    items = [Clause(evidence_id=uuid4(), content=f"({c}) any breach of clause {n};")
             for n, c in enumerate("abcde", start=1)]
    ceding = Clause(evidence_id=uuid4(), content="The Company will: (i) notify Partner of "
                    "any Claim for which it seeks indemnification, (ii) give Partner sole "
                    "control of the defense of the Claim.")
    nxt = Clause(evidence_id=uuid4(), section_number="14.2", content="Exclusions.")
    clauses = [head, *items, ceding, nxt]
    mapping = map_requirement(uuid4(), MappingRules(
        exact_phrases=("defend, indemnify, and hold harmless",), confirm_threshold=5), clauses)
    assert breadth_hit(_with_continuations(clauses, mapping), cfg) == "control of the defense"


def test_a_carve_out_made_unlimited_is_not_said_to_have_no_cap():
    row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"},
               "The aggregate liability of either Party shall not exceed the total fees "
               "paid in the twelve (12) months preceding the claim; provided that liability "
               "for fraud shall be unlimited.", preferred=12)
    point = angles._point(row, commercial.read(_clauses(*MOU)), None, legal_position=True)
    assert point["headline"] == "This clause makes liability unlimited for at least some claims"
    assert "no ceiling" not in point["body"]


def test_a_fee_beside_a_discount_rebate_or_credit_gives_no_value_but_a_discounted_price_does():
    term = " Contract Agreement: 1 Year"
    for text in ("List price Rs. 60,000 per month; discounted price Rs. 50,000 per month",
                 "Monthly fee Rs. 50,000 per month, less a discount of Rs. 5,000 per month"):
        assert _fee(text + "." + term) is None, text
    assert _fee("Discounted Price: ₹ 45,000/month." + term) == 45000.0
    assert _fee("Service Credits: as per SLA\nMRC: ₹ 50,000/month." + term) == 50000.0
    assert _fee("Rs. 500 per month as late fee." + term) is None


# --------------------------- final review before merge (2026-10-17)
def test_an_annual_or_deposit_word_on_the_line_above_still_withholds_the_figure():
    for text in ("4.1.\nFees: The Customer shall pay an annual subscription fee of \nRs. "
                 "6,00,000 (Rupees Six Lakh only) payable in equal monthly instalments \nin "
                 "advance. The Contract Term shall be 12 months.",
                 "Security Deposit\nRs. 1,50,000 adjusted against the monthly invoices. "
                 "Contract Term: 12 months.",
                 "Annual fee for P.O. No. 4471: Rs. 6,00,000 payable monthly. Contract "
                 "term: 1 year."):
        assert commercial.read(_clauses(text)).committed_value is None, text


def test_a_long_pricing_row_is_read_in_linear_time():
    import time
    started = time.monotonic()
    commercial.read(_clauses("Item i: line rental Rs. 500 per month for each server. " * 2000))
    assert time.monotonic() - started < 2


def _breadth_of(text: str):
    from legalmind.analysis.service import _with_continuations, breadth_hit
    from legalmind.ingestion import parsing
    from legalmind.mapping.engine import map_requirement
    from legalmind.mapping.rules import MappingRules
    payload = json.loads((ROOT / "INDEMNITY-MSA-001.json").read_text())
    clauses = [Clause(evidence_id=uuid4(), content=s.content, section_number=s.section_number,
                      section_title=s.section_title, is_heading=bool(s.metadata.get("heading")))
               for s in parsing.parse_text(text.encode()).segments]
    mapping = map_requirement(uuid4(), MappingRules.from_config(payload["mapping_rules"]),
                              clauses)
    return breadth_hit(_with_continuations(clauses, mapping), payload["configuration"])


def test_unprefixed_list_items_are_not_titles_and_an_exclusion_from_the_cap_is_breadth():
    assert _breadth_of(
        "14.1 The Customer shall defend, indemnify, and hold harmless Leapswitch against "
        "all losses arising from:\n\nCustomer-owned servers, devices, routers, or firewalls,"
        "\n\nData Protection Breaches\n\nThird-party software installed by the "
        "Customer,\n\nincluding, under this "
        "indemnity, indirect and consequential losses.\n\n14.2 Exclusions apply.") == "indirect"
    assert _breadth_of(
        "14.1 The Customer shall defend, indemnify, and hold harmless Leapswitch against all "
        "losses, including lost profits, which are excluded from the limitation of "
        "liability in clause 15.") == "lost profits"
    assert _breadth_of(
        "14.1 The Customer shall defend, indemnify, and hold harmless Leapswitch against all "
        "losses. The indemnity, including lost profits, is excluded from the limitation of "
        "liability.") == "lost profits"                  # reaches the FROM guard itself
    assert _breadth_of(
        "14.1 The Customer shall defend, indemnify, and hold harmless Leapswitch. Liability "
        "for indirect damages is excluded save for a party's indemnity obligations.") is None


def test_a_carve_out_in_another_sentence_does_not_stop_a_clause_stating_the_position():
    from legalmind.analysis.service import contested, waiver_signals
    from legalmind.ingestion import parsing
    from legalmind.mapping.engine import map_requirement
    from legalmind.mapping.rules import MappingRules
    payload = json.loads((ROOT / "EARLY-TERM-RESTRICTION-MSA-001.json").read_text())
    cfg, rules = payload["configuration"], MappingRules.from_config(payload["mapping_rules"])
    clauses = [Clause(evidence_id=uuid4(), content=s.content, section_number=s.section_number)
               for s in parsing.parse_text(
                   b"7.2 Restriction on Early Termination by Customer: The Customer shall "
                   b"have no right to terminate this Agreement before the expiry of the Term. "
                   b"The Customer may terminate only for Leapswitch's uncured material breach "
                   b"under clause 7.3.\n\n9.1 There is no lock-in for the Services under this "
                   b"order.").segments]
    signals = waiver_signals(clauses, cfg["waiver_patterns"], rules.confirm_threshold,
                             conditions=cfg["waiver_conditions"])
    mapping = map_requirement(uuid4(), rules, clauses, extra_signals=signals)
    assert contested(mapping, cfg["waiver_conditions"])          # a CONFLICT, not WAIVED



def test_a_stated_contract_value_is_never_a_wrong_figure():
    """The allow-list rule (final review, 2026-10-17): an amount is the fee only when its
    own words name it so and nothing marks it otherwise. A withheld figure is acceptable;
    a wrong one never is. None = no single monthly fee may be stated."""
    term = "Contract Term: 12 months"
    cases = [
        ("Service Costing: Rs. 7,57,000.00 + Rs. 1,36,260 (GST) Per Month", 757000),
        ("Monthly Charges: Rs. 50,000 per month", 50000),
        ("The Customer shall pay Rs. 50,000 per month.", 50000),
        ("Monthly charges: Rs. 50 thousand per month", 50000),
        ("Rs. 50k/month subscription fee", 50000),
        ("| Late Payment Charges | Rs. 500 per month |", None),
        ("| Service Credit | Rs. 5,000 per month |", None),
        ("| Dedicated Server | 4 | Rs. 25,000 / month |", None),
        ("Servers 4 x Rs 25000 monthly", None),
        ("Bandwidth: Rs. 450 per Mbps per month", None),
        ("A delayed payment charge of Rs. 500 per month shall apply.", None),
        ("Rs. 50,000 per month.", None),                      # not named as the fee
        ("Annual Maintenance Contract (AMC) for all equipment listed\nin Annexure A: "
         "Rs. 50,000 payable monthly", None),
        ("List price Rs. 60,000 per month; discounted price Rs. 50,000 per month", None),
    ]
    for text, want in cases:
        got = commercial.read(_clauses(text, term)).fee_per_month
        assert got is None or got == want, (text, got)
        if want is None:
            assert got is None, text


# --------------------------- second review before merge (2026-10-17, r29)
def test_no_other_charge_exit_charge_or_changing_price_is_ever_stated_as_the_fee():
    """r29: the fee is stated only when the document names ONE base monthly fee, with no
    other charge beside it in any wording, no exit or optional charge, no part-term or
    changing price, no multiplier or slash-unit, and one whole-number term."""
    t = "Contract Term: 12 months."
    for texts in (
        ("Server rental: Rs. 10,000 per month\nBackup charges: Rs. 10,000 per month", t),
        ("Fees: Rs. 50,000 per month (Phase 1)", "Fees: Rs. 50,000 per month (Phase 2)", t),
        ("Additional IP charges: Rs. 500 per month", t),
        ("Early termination fee: Rs. 50,000 per month of the remaining term", t),
        ("Optional managed support fee: Rs. 10,000 per month", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth charges: Rs. 10,000 p.m.", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth charges: Rs. 10,000 a month", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth: USD 200 per month", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth: Rs. 1,20,000 per quarter", t),
        ("Fees: Rs. 12,500 x 4 per month", t),
        ("Fees: Rs. 12,500 /server/month", t),
        ("Fee: Rs. 50,000 per month", "Lock-in period of 6 months; contract term of 36 months"),
        ("Fee: Rs. 50,000 per month", "Contract Period: 2 years 6 months"),
        ("Fee: Rs. 50,000 per month for Year 1", "Contract term: 36 months"),
        ("Fees: Rs. 50,000/month for the first 3 months", t),
        ("Fee: Rs. 50,000 per month.", "The fees shall increase by 10% every year.", t),
        ("All fees under this Agreement are payable in advance\nSupport add-on: Rs. 5,000 "
         "per month", t),
        ("Monthly fee: Rs. 50,000 per month", "Annual maintenance charges: Rs. 1,00,000", t),
    ):
        facts = commercial.read(_clauses(*texts))
        assert facts.committed_value is None and facts.missing, texts
    # a sentence ending above the fee says nothing about it
    assert _fee("4.1 Fees. The Customer shall pay a monthly fee of Rs. 50,000 per month.",
                t) == 50000.0
    # a cap figure or a tax line is not a second fee
    assert _fee("Monthly Charges: Rs. 50,000 per month", "Liability shall not exceed the "
                "fees paid, subject to Rs. 10,00,000.", t) == 50000.0


def _contested(text: str) -> bool:
    from legalmind.analysis.service import contested, waiver_signals
    from legalmind.ingestion import parsing
    from legalmind.mapping.engine import map_requirement
    from legalmind.mapping.rules import MappingRules
    payload = json.loads((ROOT / "EARLY-TERM-RESTRICTION-MSA-001.json").read_text())
    cfg, rules = payload["configuration"], MappingRules.from_config(payload["mapping_rules"])
    clauses = [Clause(evidence_id=uuid4(), content=s.content, section_number=s.section_number)
               for s in parsing.parse_text(text.encode()).segments]
    signals = waiver_signals(clauses, cfg["waiver_patterns"], rules.confirm_threshold,
                             conditions=cfg["waiver_conditions"])
    mapping = map_requirement(uuid4(), rules, clauses, extra_signals=signals)
    return contested(mapping, cfg["waiver_conditions"])


def test_an_abbreviation_never_splits_the_sentence_that_states_or_carves_out():
    """r29: "Rs." and "Sec." are not sentence ends — the stated charge stays one sentence
    (a CONFLICT with the stray waiver), the carve-out keeps its cue (still WAIVED)."""
    stray = "\n\n15.1 Add-on backups carry no minimum commitment."
    for currency in ("Rs.", "INR"):
        assert _contested(f"14.2 An early termination fee of {currency} 5,00,000 for the "
                          "remainder of the Term is payable on any early exit." + stray)
    for ref in ("Sec. 7", "Clause No. 7", "Section 7"):
        assert not _contested(
            f"14.3 Where the Customer terminates for Leapswitch's material breach under "
            f"{ref}, the early termination fee for the remainder of the Term is waived."
            "\n\n15.1 There is no lock-in for the Services.")


def test_a_stated_charge_with_its_own_for_cause_exception_still_states_the_position():
    """r29: a for-cause cue disqualifies a stating sentence only when that sentence also
    lifts the charge; "Save where … material breach, … shall pay an early termination
    fee …" states it."""
    assert _contested(
        "14.2 Save where the Customer terminates for Leapswitch's material breach, if the "
        "Customer terminates this Agreement before the expiry of the Term, the Customer "
        "shall pay an early termination fee equal to the fees for the remainder of the "
        "Term.\n\n15.1 Add-on backups carry no minimum commitment.")
    # a carve-out with an unrelated second sentence never states it either
    assert not _contested(
        "7.2 If the Customer is in material breach, the early termination fee for the "
        "remainder of the Term shall not apply. Notices go to the registered office."
        "\n\n9.1 There is no lock-in for the Services.")


def test_the_cap_point_reads_only_the_sentence_that_states_the_measured_cap():
    from legalmind.api.angles import _whose_cap
    two = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 6.0},
               "The Customer's liability for unpaid Fees shall be limited to the Fees then "
               "outstanding. The Provider's aggregate liability shall not exceed the total "
               "fees paid in the six (6) months preceding the claim.")
    assert _whose_cap(two) == "ours"
    negated = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 6.0},
                   "The Customer's liability for breach of Clause 8 is not limited to the "
                   "amounts below. The Provider's aggregate liability shall not exceed the "
                   "fees paid in the 6 months preceding the claim.")
    assert _whose_cap(negated) == "ours"
    for verb in ("will not exceed", "is not to exceed"):
        row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"},
                   f"The aggregate liability of either Party {verb} the total fees paid in "
                   "the twelve (12) months preceding the claim; provided that liability for "
                   "fraud shall be unlimited.", preferred=12)
        point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
        assert point["headline"].endswith("for at least some claims"), verb
    for text in ("The Customer's liability under this Agreement is not capped.",
                 "Each party shall have unlimited liability for all claims, including but "
                 "not limited to claims for breach of confidentiality."):
        row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"}, text)
        point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
        assert point["headline"] == "Liability is not capped in this clause", text


def test_a_one_way_obligation_is_not_mutual_for_an_either_party_elsewhere():
    from legalmind.api.angles import _mutual
    two = {"cap_value": 2.0, "cap_unit": "YEARS"}
    assert not _mutual(_row("CONF-SURVIVAL-NDA-001", "DEVIATION", two, (
        "The Receiving Party shall hold the Disclosing Party's Confidential Information in "
        "confidence, and this obligation shall survive for two (2) years after termination "
        "of this Agreement by either party.")))
    assert _mutual(_row("CONF-SURVIVAL-NDA-001", "DEVIATION", two, (
        "Each party shall keep the other's Confidential Information secret for two (2) "
        "years after termination.")))


def test_a_fee_word_on_the_line_above_does_not_name_an_amount_on_its_own_line():
    """The allow-list reads the amount's OWN line, sentence or cell (r27)."""
    facts = commercial.read(_clauses("All fees under this Agreement are payable in advance"
                                     "\nRs. 5,000 per month", "Contract Term: 12 months."))
    assert facts.committed_value is None and facts.missing


# --------------------------- r30: the census inverted, splitter, cap party, mutual
def test_every_amount_counts_against_the_fee_unless_it_is_positively_something_else():
    """r30: a wording nobody listed can only withhold. One-off sums "within a month" or
    "by 5 p.m." are never monthly; a second item at the same price under another name, a
    GST remark beside a second charge, shorthand periods ("PM", "p/m", "p.q.", per
    week/day), a dropped currency word and bi-/semi-monthly all withhold."""
    t = "Contract Term: 12 months."
    for texts in (
        ("Licence fee: Rs. 6,00,000, payable within a month of the invoice date.", t),
        ("Payment of Rs. 6,00,000 must reach Leapswitch by 5 p.m. IST on the due date.", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth: Rs. 40,000 per month", t),
        ("Monthly charges for the Primary Site: Rs. 40,000 per month.",
         "DR Site: Rs. 40,000 per month.", t),
        ("Server rental: Rs. 40,000 per month\nRs. 40,000 per month towards bandwidth", t),
        ("Server rental: Rs. 40,000 per month + GST",
         "Bandwidth charges: Rs. 1,20,000 per quarter + GST", t),
        ("Server rental: Rs. 40,000 per month", "Insurance charges: Rs. 6,000 per month", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth: Rs. 10,000 PM", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth: Rs. 1,20,000 p.q.", t),
        ("Server rental: Rs. 40,000 per month", "Colocation power: Rs. 300 per day", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth charges: 10,000 per month", t),
        ("Fees: Rs. 1,00,000 bi-monthly in advance.", t),
        ("Service charges: Rs. 25,000 semi-monthly.", t),
        ("Monthly fee: Rs. 50,000 per month", "Annual fee: Rs. 1,00,000", t),
        # r31: a restatement and two items at one price read alike; only a total parts them
        ("Schedule A - Charges\nMonthly charges: Rs. 50,000 per month", "5.1 The Customer "
         "shall pay the monthly charges of Rs. 50,000 per month in advance.", t),
    ):
        facts = commercial.read(_clauses(*texts))
        assert facts.committed_value is None and facts.missing, texts
    for texts, want in (
        (("Monthly fee: Rs. 50,000 per month.", "The fees shall not be increased during "
          "the Term.", t), 50000.0),                         # a price lock is not a change
        (("Monthly fee: Rs. 50,000 per month for the Initial Term.", t), 50000.0),
        (("Server rental: Rs. 40,000 per month + GST", t), 40000.0),
    ):
        assert commercial.read(_clauses(*texts)).fee_per_month == want, texts
    # the MOU's table restates the fee under the item's name; its own subtotal confirms it
    table = ("Service Costing: Rs. 7,57,000.00 + Rs. 1,36,260 (GST) Per Month",
             "| 1 | Bare Metal As A Service ( GPU - 1 ) | 1 | ₹ 7,57,000.00 /mo |\n"
             "| Subtotal (excl. GST) | | ₹ 7,57,000.00 |\n| Tax (18%) | | ₹1,36,260 |",
             "Contract Agreement: 1 Year")
    assert commercial.read(_clauses(*table)).committed_value == 9084000
    assert commercial.read(_clauses(*table[:1], table[1].split("\n")[0], table[2])
                           ).committed_value is None          # no subtotal: not confirmed


def test_a_real_sentence_end_before_a_figure_still_splits_the_waiver_from_the_next():
    from legalmind.analysis.service import _sentences
    assert len(_sentences("14.1 There is no lock-in period and no early termination fee "
                          "for the remainder of the term. 30 (thirty) days' notice is "
                          "required except on termination for cause.")) == 2
    assert len(_sentences("A fee of Rs. 5,00,000 under Sec. 7, i.e. the exit charge.")) == 1
    assert len(_sentences("All charges are billed monthly in INR. Either party may "
                          "terminate for material breach.")) == 2
    import time
    started = time.monotonic()
    _sentences("Sec. 1, " * 4000 + "Item No. 7 Server 12000 per month. " * 1000)
    assert time.monotonic() - started < 1                  # linear on a run of merges


def test_the_cap_party_is_the_liability_named_nearest_the_cap_and_the_figure_a_period():
    from legalmind.api.angles import _whose_cap
    carve = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 12.0, "cap_unit": "MONTHS"},
                 "Except for either party's obligations under Clause 9 (Confidentiality), "
                 "Leapswitch's total liability shall not exceed the fees paid in the twelve "
                 "(12) months preceding the claim.")
    assert _whose_cap(carve) == "ours"
    xref = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 24.0, "cap_unit": "MONTHS"},
                "Leapswitch's aggregate liability shall not exceed the fees paid in the two "
                "(2) years preceding the claim. The Customer's liability for breach of Clause "
                "24 (Export Control) shall be limited to direct damages.")
    assert _whose_cap(xref) == "ours"
    save = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 12.0, "cap_unit": "MONTHS"},
                "Save for the Customer's liability for unpaid fees, Leapswitch's total "
                "liability shall not exceed the fees paid in the twelve (12) months preceding "
                "the claim.")
    assert _whose_cap(save) is None          # two parties' liability named: unsaid (r31)
    neither = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 12.0, "cap_unit": "MONTHS"},
                   "The Customer's liability shall be limited to direct damages. Leapswitch's "
                   "liability shall not exceed the fees paid.")
    assert _whose_cap(neither) is None                      # no sentence holds the figure
    for text in ("In no event shall Leapswitch's aggregate liability exceed the fees paid in "
                 "the twelve (12) months preceding the claim, provided that liability for "
                 "fraud shall be unlimited.",
                 "Leapswitch's aggregate liability shall be restricted to the fees paid in the "
                 "twelve (12) months preceding the claim; provided that liability for fraud "
                 "shall be unlimited."):
        row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"}, text)
        point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
        assert point["headline"].endswith("for at least some claims"), text
    row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"},
               "Each party's liability for breach of confidentiality shall not be capped and "
               "shall be unlimited.")
    point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
    assert point["headline"] == "Liability is not capped in this clause"


def test_mutual_is_read_from_the_obligations_own_subject_in_the_measured_sentence():
    from legalmind.api.angles import _mutual
    two = {"cap_value": 2.0, "cap_unit": "YEARS"}
    for text in ("Following termination of this Agreement by either party for any reason, "
                 "the Receiving Party shall keep the Disclosing Party's Confidential "
                 "Information confidential for two (2) years.",
                 "The Customer shall keep Leapswitch's Confidential Information confidential "
                 "for two (2) years after termination. Each party shall bear its own costs."):
        assert not _mutual(_row("CONF-SURVIVAL-NDA-001", "DEVIATION", two, text)), text
    for text in ("The parties shall each keep the other's Confidential Information "
                 "confidential for two (2) years after termination.",
                 "The Parties agree to keep each other's Confidential Information "
                 "confidential for a period of two (2) years."):
        assert _mutual(_row("CONF-SURVIVAL-NDA-001", "DEVIATION", two, text)), text


# --------------------------- r31: totals, bare money, price changes, carve-outs, parties
def test_a_second_amount_or_a_total_that_is_not_the_fee_withholds_the_figure():
    t = "Contract Term: 12 months."
    for texts in (
        ("Server rental charges: Rs. 40,000 per month", "Bandwidth charges: Rs. 40,000 per "
         "month", t),
        ("Monthly fee for Server A: Rs. 40,000 per month", "Monthly fee for Server B: Rs. "
         "40,000 per month", t),
        ("Server rental: Rs. 40,000 per month\nBandwidth: 10,000\nTotal: Rs. 50,000", t),
        ("Server rental: Rs. 40,000 per month\nSub-total (Compute): Rs. 40,000\nBandwidth: "
         "Rs. 40,000 per month\nSub-total (Network): Rs. 40,000\nGrand Total: Rs. 80,000", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth charges: 10000 per month", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth: Rs. 1,20,000 per quarter",
         "Sub-total (Compute): Rs. 40,000", t),          # a sub-total equal to one item
        ("Fees: Rs. 7.5 lakh per month for the servers and 1.5 lakh per month for "
         "bandwidth.", t),
        ("Monthly fee: Rs. 5 lakh 50 thousand per month.", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth charges: Rs. 1,20,000 (GST extra) "
         "per quarter", t),
        ("Server rental: Rs. 40,000 per month", "Bandwidth charges: Rs. 1,20,000 per "
         "quarter, subject to service credits under the SLA.", t),
        ("Monthly fee: Rs. 50,000 per month.", "The Fees are fixed for the first twelve (12) "
         "months and shall thereafter be increased by 8% per annum.",
         "Contract Term: 36 months."),
        ("Monthly fee: Rs. 50,000 per month.", "The charges shall be adjusted annually in "
         "line with the CPI.", t),
        ("Monthly fee: Rs. 50,000 per month.", "Contract Term: 1 year plus 6 months"),
        ("Monthly fee: Rs. 50,000 per month.", "Contract Term: 12 months (Phase 1); 24 "
         "months (Phase 2)"),
    ):
        facts = commercial.read(_clauses(*texts))
        assert facts.committed_value is None and facts.missing, texts
    assert commercial.read(_clauses("Monthly fee: Rs. 50,000 per month.",
                                    "Contract Term: 120 months")).committed_value == 6000000
    assert _fee("Monthly fee: Rs. 50,000 per month.", "Total contract value: Rs. 6,00,000.",
                t) == 50000.0                                      # fee x term confirms
    assert _fee("Dedicated servers 4 per month.", "Fee: Rs. 15,000 per month.", t) == 15000.0


def test_a_for_cause_rule_is_a_carve_out_unless_the_cue_is_an_exception_to_a_charge():
    """r31: whatever words lift the fee, a for-cause cue outside an exception phrase makes
    the sentence a carve-out (the waiver stands); "Save where … material breach, …
    shall pay" still states the charge."""
    stray = "\n\n4.1 There is no lock-in period under this Agreement."
    for carve in ("Where the Customer terminates this Agreement for material breach by the "
                  "Provider, the Customer shall not be required to pay any early termination "
                  "fee for the remainder of the term.",
                  "The Customer shall be released from the early termination fee for the "
                  "remainder of the term where it terminates for material breach."):
        assert not _contested("4.2 " + carve + stray), carve
    assert _contested("4.2 Save where the Customer terminates for material breach, an early "
                      "termination fee equal to the fees for the remainder of the term is "
                      "payable." + stray)


def test_an_exclusion_of_indirect_and_consequential_loss_is_not_breadth():
    assert _breadth_of("12.1 The Customer shall defend, indemnify, and hold harmless the "
                       "Provider against third-party claims, provided that consequential or "
                       "indirect losses shall not be recoverable.") is None


def test_parties_read_with_curly_apostrophes_and_never_from_a_lead_in_or_a_joint_subject():
    from legalmind.api.angles import _mutual, _whose_cap
    curly = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 12.0, "cap_unit": "MONTHS"},
                 "Subject to clause 13.3, each Party\u2019s aggregate liability to the other "
                 "shall not exceed the fees paid in the 12 months preceding the claim.")
    assert _whose_cap(curly) == "both"
    joint = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 6.0, "cap_unit": "MONTHS"},
                 "The total liability of Leapswitch and the Customer under this Agreement "
                 "shall not exceed the fees paid in the six (6) months preceding the claim.")
    assert _whose_cap(joint) is None
    in_no_event = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 12.0,
                                                          "cap_unit": "MONTHS"},
                       "In no event shall Leapswitch's aggregate liability exceed the fees "
                       "paid in the twelve (12) months preceding the claim.")
    assert _whose_cap(in_no_event) == "ours"
    three = {"cap_value": 3.0, "cap_unit": "YEARS"}
    assert not _mutual(_row("CONF-SURVIVAL-NDA-001", "DEVIATION", three, (
        "Both parties acknowledge that the Customer shall keep the Confidential Information "
        "of Leapswitch confidential for a period of three (3) years after termination.")))
    row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"},
               "Leapswitch's liability shall in no event be more than the fees paid in the six "
               "(6) months preceding the claim; provided that liability for fraud shall be "
               "unlimited.")
    point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
    assert point["headline"].endswith("for at least some claims")


# --------------------------- r32: instalments, an indemnity's own exclusions, roles
def test_a_sum_paid_in_monthly_instalments_is_never_the_monthly_fee():
    for texts in (
        ("The Fees of Rs. 6,00,000 shall be payable in 12 equal monthly instalments.",
         "The Initial Term shall be 12 months."),
        ("A total fee of Rs. 2,40,000 for the Term, payable monthly in arrears.",
         "Contract Term: 12 months."),
        ("Rs. 6,00,000 for a period of one year, payable monthly.", "Contract Term: 1 year"),
        ("Fees: Rs. 3,60,000 payable in monthly instalments.", "Contract Term: 36 months"),
    ):
        facts = commercial.read(_clauses(*texts))
        assert facts.committed_value is None and facts.missing, texts


def test_an_indemnitys_own_exclusion_of_indirect_loss_is_not_breadth():
    head = ("12.1 Each Party shall defend, indemnify and hold harmless the other Party "
            "against all third-party claims arising from its breach. ")
    for tail in ("In no event shall the Indemnifying Party be liable for any indirect or "
                 "consequential damages.",
                 "The Indemnifying Party shall not be liable to the Indemnified Party for any "
                 "indirect or consequential loss.",
                 "The Indemnifying Party shall have no liability for any indirect or "
                 "consequential damages.",
                 "Neither Party shall be liable to the other Party for any indirect or "
                 "consequential loss under this indemnity.",
                 "Indirect and consequential losses are excluded from this indemnity."):
        assert _breadth_of(head + tail) is None, tail
    assert _breadth_of(head + "The indemnity, including lost profits, is excluded from "
                       "the limitation of liability.") == "lost profits"   # from the CAP


def test_a_joint_cap_and_a_vendors_roles_never_name_one_side():
    from legalmind.api.angles import _whose_cap
    six = {"cap_value": 6.0, "cap_unit": "MONTHS"}
    joint = _row("LIABILITY-MSA-001", "DEVIATION", six,
                 "The total aggregate liability of the Customer and Leapswitch under this "
                 "Agreement shall not exceed the fees paid in the six (6) months preceding "
                 "the claim.")
    assert _whose_cap(joint) is None
    vendor = _row("LIABILITY-MSA-001", "DEVIATION", six,
                  "The Service Provider's total aggregate liability shall not exceed the fees "
                  "paid in the six (6) months preceding the claim.")
    assert _whose_cap(vendor) == "ours"                   # a customer-service document
    vendor["document_type"] = "VENDOR_AGREEMENT"          # LeapSwitch buys: not its cap
    assert _whose_cap(vendor) is None
    named = dict(vendor, evidence=SimpleNamespace(content=(
        "Leapswitch's total aggregate liability shall not exceed the fees paid in the six (6) "
        "months preceding the claim."), section_number=None, section_title=None,
        page_number=None))
    assert _whose_cap(named) == "ours"                    # by name, on any document


# --------------------------- r33: damages, "L" for lakh, exception scope, exclusions
def test_damages_are_never_the_fee_and_lakh_written_l_is_read_whole():
    t = "Contract Term: 12 months."
    for text in ("The Service Provider shall pay liquidated damages of Rs. 25,000 per month "
                 "for non-performance.",
                 "Indemnity: the Partner shall pay Rs. 50,000 per month towards indemnified "
                 "losses."):
        assert commercial.read(_clauses("The fees shall be as set out in the Order Form.",
                                        text, t)).committed_value is None, text
    assert _fee("Monthly charges: Rs. 2.5L per month", t) == 250000.0
    facts = commercial.read(_clauses("Fees: Rs. 50,000 per month.", "Uptime is measured "
                                     "over a service period of 1 month."))
    assert facts.term_months is None and not facts.term_stated   # an SLA window, no term


def test_an_exception_word_counts_only_when_it_governs_the_cue():
    stray = "\n\n4.1 There is no lock-in period under this Agreement."
    assert not _contested(
        "14.3 Unless otherwise agreed in writing, upon termination for the Customer's "
        "material breach, the Customer shall pay an early termination fee equal to the "
        "charges for the remainder of the Term." + stray)
    assert _contested("14.2 Save where the Customer terminates for material breach, an "
                      "early termination fee equal to the fees for the remainder of the "
                      "term is payable." + stray)


def test_an_indemnity_that_does_not_apply_to_indirect_loss_is_not_breadth():
    head = ("12.1 The Partner shall indemnify, defend and hold harmless the Company against "
            "all losses arising out of any breach of this Agreement")
    for tail in (", provided that this indemnity shall not apply to any indirect or "
                 "consequential loss.",
                 ", provided that indirect and consequential losses are expressly "
                 "excluded.",
                 ". Indirect or consequential losses are not covered."):
        assert _breadth_of(head + tail) is None, tail


def test_leapswitchs_cap_never_claims_the_clause_caps_no_one_else():
    row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_value": 6.0, "cap_unit": "MONTHS"},
               "Leapswitch's aggregate liability under this Agreement shall not exceed the "
               "total fees paid in the six (6) months preceding the claim. The Customer's "
               "aggregate liability shall not exceed the Fees payable for the Term.")
    point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
    assert point["headline"].startswith("LeapSwitch's") and "no one else" not in point["body"]


# --------------------------- r34: plain shapes, scope-only price changes, headings
def test_a_figure_is_stated_only_from_a_plain_fee_statement():
    """r34: the shape of the fee line is the last gate — anything beyond a label, the
    amount, GST and the period withholds."""
    t = "Contract Term: 12 months."
    for text in ("Subscription Fee: INR 12,00,000 p.a., payable monthly in advance.",
                 "Service Fee: Rs. 6,00,000 pa, payable monthly",
                 "The Customer shall pay a service fee of Rs. 6,00,000 a year, billed monthly.",
                 "The Customer shall pay charges of Rs. 1,50,000 quarterly, invoiced monthly.",
                 "Rental charges for 2 dedicated servers @ Rs. 25,000/- per month each",
                 "Fees: Rs. 50 thousands per month"):
        facts = commercial.read(_clauses(text, t))
        assert facts.committed_value is None and facts.missing, text
    for text, want in (("Fees: Rs. 50,000 (Rupees Fifty Thousand only) per month", 50000.0),
                       ("Monthly Recurring Charges: Rs. 7,57,000 + GST per month", 757000.0),
                       ("Fees: Rs. 50,000 per month, plus applicable GST.", 50000.0),
                       ("| MRC | Rs. 50,000 per month |", 50000.0)):
        assert _fee(text, t) == want, text


def test_a_price_that_may_change_withholds_unless_only_the_scope_or_after_the_term():
    f, t = "Fees: Rs. 50,000 per month.", "Contract Term: 12 months."
    for text in ("Leapswitch reserves the right to change the fees on 30 days' notice.",
                 "Leapswitch may modify the Fees at any time upon 30 days' notice.",
                 "The Fees shall not be revised during the lock-in period, but may be "
                 "increased by 5% thereafter.",
                 "The pricing is valid for a period of 6 months and may be subject to change "
                 "thereafter."):
        assert commercial.read(_clauses(f, text, t)).committed_value is None, text
    for text in ("If the resources are upgraded or downgraded, the Service price will change "
                 "accordingly.",
                 "The pricing is valid for a period of 1 year and may be subject to change "
                 "thereafter.",
                 "The Fees shall not be changed during the Term."):
        assert _fee(f, text, t) == 50000.0, text


def test_a_confirmed_heading_is_read_with_the_clauses_numbered_under_it():
    assert _breadth_of("MASTER SERVICES AGREEMENT\n10. INDEMNIFICATION\n10.1 The Supplier "
                       "shall indemnify and keep indemnified the Customer against all losses, "
                       "whether direct or indirect, including loss of profits, arising from "
                       "any breach of this Agreement.\n10.2 The Supplier shall have sole "
                       "control of the defence of any third party claim.\n11. GOVERNING "
                       "LAW\n11.1 This Agreement is governed by the laws of India.\n") \
        == "indirect"
    head = "10.1 The Vendor shall indemnify and hold harmless the Company against direct "
    for tail in ("losses, but not against any indirect or consequential loss.",
                 "losses. The Vendor shall not be required to indemnify the Company for any "
                 "indirect or consequential loss.",
                 "losses. Neither Party shall be required to indemnify the other for "
                 "indirect or consequential losses."):
        assert _breadth_of(head + tail) is None, tail


def test_the_other_side_named_before_a_cap_says_neither_and_silence_is_never_claimed():
    from legalmind.api.angles import _mutual, _whose_cap
    six = {"cap_value": 6.0, "cap_unit": "MONTHS"}
    for subject in ("The aggregate liability of the Customer and/or LeapSwitch",
                    "The total liability of the Customer, or of LeapSwitch,"):
        row = _row("LIABILITY-MSA-001", "DEVIATION", six, subject + " under this "
                   "Agreement shall not exceed the fees paid in the six (6) months "
                   "preceding the claim.", preferred=12)
        assert _whose_cap(row) is None, subject
        point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
        assert "does not say" not in point["body"]
    months = {"cap_value": 2.0, "cap_unit": "YEARS"}
    assert _mutual(_row("CONF-SURVIVAL-MSA-001", "DEVIATION", months,
                        "Each Party shall keep the other's information confidential for "
                        "twenty-four (24) months after termination."))
    one_way = _row("CONF-SURVIVAL-NDA-001", "DEVIATION", months,
                   "The Receiving Party shall keep it confidential for two (2) years.",
                   preferred=3)
    point = angles._point(one_way, commercial.read(_clauses(*MOU)), None, True)
    assert point["body"] == "Our standard is 3 years."


# --------------------------- r35: escalation words, discounts, lists, exceptions, roles
def test_an_increment_a_discount_or_a_first_year_price_withholds_the_figure():
    f, t = "Monthly Fee: Rs. 60,000 per month", "Contract Term: 36 months."
    for text in ("The fees shall be subject to an annual increment of 5%.",
                 "The fees shall be subject to annual increments as per policy.",
                 "The rental shall be increased by 5% every year.",
                 "The MRC shall escalate by 5% annually.",
                 "A 5% year-on-year increase shall apply.",
                 "Fees are fixed only for the first year.",
                 "After the first year, the then-prevailing list prices shall apply.",
                 "Pricing is valid for 12 months only, after which the prevailing rates "
                 "shall apply.",
                 "A special discount of 10% shall apply on the monthly charges.",
                 "The charges for the first month shall be waived.",
                 "Special Discount: Rs. 6,000"):
        assert commercial.read(_clauses(f, text, t)).committed_value is None, text
    # an SLA's percentages and "may vary" are not a price change; a quote table's empty
    # discount column is not a discount
    assert _fee(f, "SLA uptime: 99.9% (response times may vary).", t) == 60000.0
    quote = ("Service Costing: Rs. 7,57,000.00 + Rs. 1,36,260 (GST) Per Month",
             "Quote Summary & Pricing\n| # | Service | Qty | Original | Discount | Amount |\n"
             "| 1 | Bare Metal As A Service | 1 | ₹ 7,57,000.00 /mo | - | ₹ 7,57,000.00 /mo |\n"
             "| Subtotal (excl. GST) | | | | | ₹ 7,57,000.00 |", "Contract Agreement: 1 Year")
    assert commercial.read(_clauses(*quote)).committed_value == 9084000


def test_a_semicolon_list_keeps_its_indemnity_and_but_not_excludes():
    assert _breadth_of("12.1 The Customer shall indemnify and hold harmless the Company from "
                       "and against: (a) any third party claim; (b) all losses, including "
                       "indirect and consequential losses and loss of profits; and (c) legal "
                       "costs.") == "indirect"
    for tail in ("against direct losses, but not indirect or consequential losses.",
                 "against all losses arising from its breach; indirect and consequential "
                 "losses are not included.",
                 "against direct losses, with the exception of indirect or consequential "
                 "losses."):
        assert _breadth_of("12.1 The Customer shall indemnify and hold harmless the Company "
                           + tail) is None, tail


def test_subject_to_or_notwithstanding_a_cause_clause_still_states_the_lock_in():
    stray = "\n\n6.1 There is no lock-in period and no early termination charges shall apply."
    for lead in ("Subject to Clause 5.3 (Termination for Cause), ",
                 "Notwithstanding Clause 5.3 (Termination for Cause), "):
        assert _contested("5.1 " + lead + "the Customer shall have no right to terminate this "
                          "Agreement before the expiry of the Term." + stray), lead


def test_more_than_is_a_cap_and_either_party_in_a_lead_in_is_not_mutual():
    from legalmind.api.angles import _mutual
    row = _row("LIABILITY-MSA-001", "DEVIATION", {"cap_status": "UNLIMITED"},
               "Leapswitch's aggregate liability shall not be more than the total fees paid "
               "by the Customer under this Agreement. The Customer's liability for "
               "non-payment of fees shall be unlimited.")
    point = angles._point(row, commercial.read(_clauses(*MOU)), None, True)
    assert point["headline"].endswith("for at least some claims")
    assert not _mutual(_row("CONF-SURVIVAL-MSA-001", "DEVIATION",
                            {"cap_value": 2.0, "cap_unit": "YEARS"},
                            "Upon termination of this Agreement by either Party the "
                            "obligations of the Customer under this Clause shall survive for "
                            "a period of two (2) years after termination."))


# --------------------------- review of AM-155 on main (2026-10-17, a peer session's list)
def test_a_term_in_force_for_a_period_or_in_words_is_read_and_a_zero_term_is_none():
    for text, months in (("This Agreement shall remain in force for a period of three (3) "
                          "years.", 36),
                         ("The initial term is ten (10) years.", 120),
                         ("This Agreement shall continue for a period of 12 months from the "
                          "Effective Date.", 12)):
        facts = commercial.read(_clauses(text))
        assert facts.term_months == months and facts.term_stated, text
    for text in ("Lock-in period: 0 months", "Contract Term: 0 months"):
        assert not commercial.states_fixed_term(_clauses(text)), text


def test_working_days_are_never_calendar_days_with_or_without_an_anchor(monkeypatch):
    from legalmind.extraction import liability
    pay = LiabilityExtractionConfig.from_config(
        json.loads((ROOT / "PAYMENT-PERIOD-MSA-001.json").read_text())["configuration"])
    monkeypatch.setattr(liability, "_phrase_span", lambda body, phrases: None)
    cap = extract_liability_facts(_clauses("Invoices are payable within 30 business days "
                                           "of the invoice date."), pay).caps[0]
    assert cap.cap_status == "WORKING_DAYS"          # never 30 calendar days
    monkeypatch.undo()
    cure = LiabilityExtractionConfig.from_config(
        json.loads((ROOT / "CURE-PERIOD-MSA-001.json").read_text())["configuration"])
    cap = extract_liability_facts(_clauses(
        "Notices are acknowledged within 2 business days. A breach not cured within the "
        "cure period of thirty (30) days entitles the other party to terminate."),
        cure).caps[0]
    assert (cap.cap_status, cap.cap_value) == ("FINITE", 30.0)   # not lost to the 2
