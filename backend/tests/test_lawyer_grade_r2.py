"""Release 2 of the lawyer-grade review: a bullet ends a sentence, so a price word in one
bullet never pairs with a change word in another (`AM-152` r5: committed value is
arithmetic on stated figures). Synthetic text only (54.6)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from legalmind.extraction import commercial
from legalmind.mapping.engine import Clause

FEE, TERM = "Fees: Rs. 50,000 per month.", "Contract Term: 12 months."


def _clauses(*texts: str) -> list[Clause]:
    return [Clause(evidence_id=uuid4(), content=t) for t in texts]


def test_a_bullet_ends_a_sentence():
    # "changes" in one bullet (not a price change), a price word in a later one under its
    # own heading line: a list a page renders with each heading on a line of its own
    for text in ("● Material changes require customer consent\nLimitation of Liability\n"
                 "● Liability capped at amount paid by customer",
                 "Terms • Material changes require customer consent ▪ Liability capped "
                 "at amount paid by customer",
                 "Terms\n- Material changes require customer consent\n* Liability capped "
                 "at amount paid by customer"):
        assert commercial.read(_clauses(FEE, text, TERM)).fee_per_month == 50000.0, text


def test_a_price_change_a_blank_a_heading_and_a_mid_line_dash_still_withhold():
    for text in ("Pricing ● Leapswitch may revise the fees on 30 days' notice",
                 "The fees of Rs [●] may be revised annually",
                 "The fees - as stated above - may be revised annually",
                 # the price word in the heading, the change in a bullet under it
                 "Pricing ● Revised annually as per CPI",
                 "Charges\n- Escalation: 5% every year",
                 "Charges • Discount of 10% for the first 3 months",
                 "Charges\n● As per the order form\n● Revised annually",
                 # a bare "●" as a template blank is no bullet
                 "Fees are fixed for ● months and thereafter revised",
                 "Customer pays ● for the fees ● and these may be revised",
                 # a change bullet that speaks of the fee bullet above it (review c11)
                 "Terms\n● Hosting fees are payable monthly\n● Subject to revision every "
                 "year",
                 "Terms ● Monthly charges are billed in advance ● LeapSwitch may increase "
                 "them annually",
                 # a change with no subject of its own, under a heading with no price
                 # word; and a list whose bullets end in ";" (review r5)
                 "Commercial Terms\n● Service charges are billed monthly in advance\n"
                 "● Revised annually as per CPI",
                 "Commercial Terms • Service charges are billed monthly in advance • "
                 "Revised annually as per CPI",
                 "Commercial Terms\n- Service charges are billed monthly\n- Escalation: "
                 "10% every year",
                 "Pricing\n● Billed monthly in advance;\n● Revised annually as per CPI;",
                 "Pricing ● Billed monthly in advance. ● Revised annually as per CPI."):
        facts = commercial.read(_clauses(FEE, text, TERM))
        assert facts.committed_value is None and facts.missing, text


# --------------------------- item 2: one projection, wider action words (AM-159)
def test_ask_and_the_review_give_a_prohibited_deviation_the_same_word():
    from legalmind.domain.constitution_boundaries import constitution_prohibition_for as d
    from legalmind.domain.enums import FindingClassification as C
    from legalmind.domain.user_status import NEEDS_DECISION, user_status
    from legalmind.evaluation.constitution_boundaries import (
        constitution_prohibition_for as e,
    )
    assert d is e                                     # one predicate, re-exported
    uncapped = {"cap_status": "UNLIMITED"}
    assert user_status(C.DEVIATION, prohibited=d("LIABILITY-MSA-001", uncapped) is not None) \
        == NEEDS_DECISION


def test_every_class_has_an_action_and_none_rejects_or_approves():
    from types import SimpleNamespace

    from legalmind.api import angles

    def row(cls, title=None, number=None, page=None):
        return {"code": "LIABILITY-MSA-001", "classification": cls, "actual": {},
                "evidence": SimpleNamespace(section_number=number, section_title=title,
                                            page_number=page)}
    assert angles.action(row("CONFLICT"), False) == angles.CONFLICT_DECIDE
    # the clause's number only; its title and page show apart (review r24)
    assert angles.action(row("UNABLE_TO_EVALUATE", "Limitation of Liability", "13.2", 3),
                         False) == "A person must read clause 13.2 before it can be relied on"
    assert angles.action(row("UNABLE_TO_EVALUATE"), False) == angles.READ_IT
    assert angles.action(row("UNABLE_TO_EVALUATE", page=3), False) == angles.READ_IT
    texts = (angles.ACCEPT, angles.SEND_WORDING, angles.NO_WORDING, angles.MUST_CHANGE,
             angles.READ_IT, angles.CONFLICT_DECIDE, angles.UNDEFINED)
    # "approved wording" is the Constitution's drafting language; no action is a verdict
    assert not any(w in t.lower() for t in texts
                   for w in ("reject", "is approved", "are approved", "approved by"))


# --------------------------- item 3: §13's export window is checkable (AM-159)
def test_an_export_window_under_30_days_is_the_section_13_unacceptable_position():
    from legalmind.domain.constitution_boundaries import constitution_prohibition_for as p
    assert p("DATA-PURGE-MSA-001", {"cap_value": 15, "cap_unit": "DAYS"}) == {
        "section": "13",
        "quote": "A post-termination data-export window shorter than 30 days […]"}
    for actual in ({"cap_value": 30, "cap_unit": "DAYS"},      # the position itself
                   {"cap_value": 1, "cap_unit": "MONTHS"},     # never converted
                   {"cap_status": "ABSENT"}):                  # MISSING never fires
        assert p("DATA-PURGE-MSA-001", actual) is None, actual
    # the published TOS governs itself (§13 Applicability): 7 days is not prohibited …
    assert p("DATA-RETRIEVAL-TOS-001", {"cap_value": 7, "cap_unit": "DAYS"}) is None
    # … and the MSA window is never measured on a TOS
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parents[1] / "config" / "company_standards"
                      / "DATA-PURGE-MSA-001.json").read_text())["configuration"]
    assert "TOS" in cfg["not_applicable_to"]
    # the quoted limb is the Constitution's own words
    constitution = (Path(__file__).resolve().parents[2] / "docs" / "02-legal-domain"
                    / "LEGAL_CONSTITUTION_L1.13.md").read_text()
    assert "A post-termination data-export window shorter than 30 days" in constitution


# --------------------------- item 4: an order "declined" is not a convenience exit
def test_an_order_declined_with_or_without_cause_is_not_termination_for_convenience():
    import json
    from pathlib import Path
    from uuid import uuid4

    from legalmind.mapping.engine import Clause, map_requirement
    from legalmind.mapping.rules import MappingRules
    payload = json.loads((Path(__file__).resolve().parents[1] / "config" / "company_standards"
                          / "CONVENIENCE-NOTICE-MSA-001.json").read_text())
    rules = MappingRules.from_config(payload["mapping_rules"])

    def state(text):
        return map_requirement(uuid4(), rules, [Clause(evidence_id=uuid4(), content=text)]
                               ).state.name
    assert state("A Purchase Order may be accepted or is declined at LeapSwitch's sole "
                 "discretion, with or without cause.") != "CONFIRMED"
    assert state("Either party may terminate this Agreement without cause on thirty (30) "
                 "days' written notice to the other party.") == "CONFIRMED"


# --------------------------- item 7 / AM-160: the issues in order, and one recommendation
def test_the_recommendation_follows_the_actions_and_is_never_a_score():
    from legalmind.api import angles as A
    none = {"structural": [], "additional": []}

    def items(*actions):
        return [{"action": a} for a in actions]
    assert A.recommendation(items(A.MUST_CHANGE, A.SEND_WORDING, A.READ_IT), none, 3) == (
        "Recommendation: do not sign as drafted — 1 point must change before signing, and "
        "1 other change proposed; a person must decide or read 1 point first. Only an "
        "authorised approver may grant an exception (§25.1).")
    assert A.recommendation(items(A.SEND_WORDING, A.SEND_WORDING), none, 2) == (
        "Recommendation: sign after 2 changes. An authorised person decides (§24.3).")
    # no approved wording is a Legal decision, not a change to send (review d8)
    assert A.recommendation(items(A.SEND_WORDING, A.NO_WORDING), none, 2) == (
        "Recommendation: sign after 1 change; a person must decide or read 1 point first. "
        "An authorised person decides (§24.3).")
    assert A.recommendation([], {"structural": [{"action": A.UNDEFINED}],
                                 "additional": []}, 2).startswith(
        "Recommendation: no point differs from our positions, but a person must decide")
    # observations alone never make a claim about our positions (review r23)
    assert A.recommendation([], {"structural": [{"action": None}], "additional": []},
                            0) is None
    assert A.recommendation([], none, 4) == ("No point differs from our positions — a "
                                             "person still reviews before final sign-off "
                                             "(§25.2).")
    # a deviation with no approved wording is never "no point differs" (review r27)
    assert A.recommendation([{"action": A.NO_WORDING, "classification": "DEVIATION"}],
                            none, 1) == (
        "Recommendation: a person must decide or read 1 point before signing; 1 point "
        "differs from our positions with no approved wording to send.")
    # nothing measured: nothing to recommend (review c10)
    assert A.recommendation([], none, 0) is None
    for text in (A.recommendation(items(A.MUST_CHANGE), none, 1),
                 A.recommendation([], none, 1)):
        assert text and "%" not in text and not any(
            w in text.lower() for w in ("risk", "score", "reject", "high", "low"))
    assert sorted([A.READ_IT, A.SEND_WORDING, A.MUST_CHANGE], key=A._action_rank) == [
        A.MUST_CHANGE, A.SEND_WORDING, A.READ_IT]


def test_the_angles_payload_carries_no_verdict_or_score_field(monkeypatch):
    from legalmind.api import angles as A
    monkeypatch.setattr(A, "_rows", lambda db, review: [])
    monkeypatch.setattr(A, "load_clauses", lambda db, version: [])
    monkeypatch.setattr(A, "_review_document_type", lambda db, review: None)
    monkeypatch.setattr(A, "_proposals", lambda db, sections: {})
    monkeypatch.setattr(A.reading, "read", lambda *a: None)
    monkeypatch.setattr(A, "group_ids", lambda db, ids, **kw: {})  # AM-179 fold
    from types import SimpleNamespace
    out = A.review_angles(None, SimpleNamespace(id=None, document_version_id=None),
                          legal_position=True)
    assert {"verdict", "overall", "score", "risk_level", "posture"}.isdisjoint(out)
    assert out["observations"] == {"structural": [], "additional": []}


def test_the_issues_are_listed_must_change_first(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    from legalmind.api import angles as A

    def row(code, actual):
        return {"finding": SimpleNamespace(id=uuid4(), status=None), "code": code, "title": code,
                "classification": "DEVIATION", "actual": actual, "expected": {},
                "evidence": None, "evidence_ids": [], "standard": {}}
    rows = [row("CURE-PERIOD-MSA-001", {"cap_value": 15, "cap_unit": "DAYS"}),
            row("LIABILITY-MSA-001", {"cap_status": "UNLIMITED"})]
    monkeypatch.setattr(A, "_rows", lambda db, review: rows)
    monkeypatch.setattr(A, "load_clauses", lambda db, version: [])
    monkeypatch.setattr(A, "_review_document_type", lambda db, review: "MSA")
    monkeypatch.setattr(A, "_proposals", lambda db, sections: {})
    monkeypatch.setattr(A.reading, "read", lambda *a: None)
    monkeypatch.setattr(A, "group_ids", lambda db, ids, **kw: {})  # AM-179 fold
    out = A.review_angles(None, SimpleNamespace(id=None, document_version_id=None),
                          legal_position=True)
    assert [i["requirement_code"] for i in out["legal"]["items"]] == [
        "LIABILITY-MSA-001", "CURE-PERIOD-MSA-001"]
    # equal actions read in one order however the rows arrive (review r25)
    rows[:] = [row("PAYMENT-TERMS-MSA-001", {"cap_value": 45, "cap_unit": "DAYS"}),
               row("CURE-PERIOD-MSA-001", {"cap_value": 15, "cap_unit": "DAYS"})]
    first = [i["requirement_code"] for i in A.review_angles(
        None, SimpleNamespace(id=None, document_version_id=None), legal_position=True)["legal"]["items"]]
    rows.reverse()
    assert first == [i["requirement_code"] for i in A.review_angles(
        None, SimpleNamespace(id=None, document_version_id=None), legal_position=True)["legal"]["items"]]


@pytest.mark.parametrize("legal_position", [True, False])
def test_the_constitutions_words_are_omitted_for_a_reader_without_positions(
        monkeypatch, legal_position):
    """SEC-07 / LEGAL-02 (review c8): an enforceability note and an observation's basis
    quote the Constitution — omitted, never nulled, without the positions permission."""
    from types import SimpleNamespace

    from legalmind.api import angles as A
    rows = [{"finding": SimpleNamespace(id=uuid4(), status=None), "code": "LATE-FEE-MSA-001",
             "title": "Late fee", "classification": "DEVIATION",
             "actual": {"cap_value": 3, "cap_unit": "PERCENT"}, "expected": {},
             "evidence": None, "evidence_ids": [], "standard": {}}]
    clauses = [Clause(evidence_id=uuid4(), section_number="29", section_title="Precedence",
                      content="29. In the event of any conflict between this Agreement and "
                              "a Purchase Order, this Agreement shall prevail.")]
    monkeypatch.setattr(A, "_rows", lambda db, review: rows)
    monkeypatch.setattr(A, "load_clauses", lambda db, version: clauses)
    monkeypatch.setattr(A, "_review_document_type", lambda db, review: "MSA")
    monkeypatch.setattr(A, "_proposals", lambda db, sections: {})
    monkeypatch.setattr(A.reading, "read", lambda *a: None)
    monkeypatch.setattr(A, "group_ids", lambda db, ids, **kw: {})  # AM-179 fold
    out = A.review_angles(None, SimpleNamespace(id=None, document_version_id=None),
                          legal_position=legal_position)
    [item] = out["legal"]["items"]
    [observed] = out["observations"]["structural"]
    assert ("enforceability" in item) is legal_position
    assert ("basis" in observed) is legal_position
    assert all(("enforceability" in p) is legal_position for p in out["business"])


def test_a_long_list_reads_in_linear_time():
    import time
    text = "Terms\n" + "\n".join(f"● Item {i} covers the fees for service line"
                                  for i in range(5000))
    start = time.perf_counter()
    commercial.read(_clauses(FEE, text, TERM))
    assert time.perf_counter() - start < 2.0          # quadratic took ~6 s
