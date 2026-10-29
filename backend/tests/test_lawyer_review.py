"""`AM-236` (owner, 2026-10-29: "as a real lawyer"): ONE contract in Ask, reviewed as
LeapSwitch's lawyer would. The side we are on read from the parties clause and asked only
when it is not there; the points in the engine's order of importance; the bottom line in
fixed words, never "all fine" for a document our positions do not cover, never a review of
a file read in part. Synthetic text, no client named (54.6). No database, no model."""
from uuid import UUID

import pytest

from legalmind.api import angles as A
from legalmind.api import deal_review as D
from legalmind.api.temporary_review import TemporaryReview
from legalmind.assist import service
from legalmind.assist.agent import agent
from legalmind.assist.agent import deal_questions as Q

FILE = str(UUID(int=7))


@pytest.mark.parametrize("preamble, side", [
    ("This Agreement is made between Leapswitch Networks Private Limited "
     "(hereinafter “Service Provider”) and Acme Limited (hereinafter “Customer”).",
     Q.PROVIDER),
    ("Between Acme Hardware Limited (the \"Supplier\") and Leapswitch Networks Private "
     "Limited (the \"Customer\").", Q.BUYER),
    ("Between Acme Limited (\"Client\") and CloudPe (\"Provider\").", Q.PROVIDER),
    # our own MSA: we are defined by name, the other party by its role (real-file test)
    ("This Agreement is entered into between Leapswitch Networks Private Limited, "
     "hereinafter referred to as \"LeapSwitch\" or \"Company\", and Acme Limited, "
     "hereinafter referred to as \"Customer\".", Q.PROVIDER),
    ("This Agreement (\"Agreement\") is between Acme Hardware Limited (\"Supplier\") "
     "and Leapswitch Networks Private Limited.", Q.BUYER),
    ("These terms of service apply to every order.", None),
])
def test_the_side_we_are_on_is_read_from_the_parties_clause(preamble, side):
    assert Q.infer_side([{"content": preamble}]) == side


@pytest.mark.parametrize("asked", [
    "As Leapswitch lawyer, what should I focus on in this contract?",
    "what are the red flags here",
    "review this agreement please",
    "isme kya dekhna chahiye?",
    "kis point par dhyan dena chahiye",
    "Is this ok to sign?"])
def test_a_lawyers_question_on_one_file_is_read(asked):
    assert service.wants_lawyer_review(asked)


@pytest.mark.parametrize("asked", [
    "Summarise this agreement", "What are the risks in this?",
    "What is the termination notice period in this file?", "please prepare a email"])
def test_a_summary_a_risk_list_or_a_plain_question_keeps_its_own_path(asked):
    assert not service.wants_lawyer_review(asked)


def _finding(fid, code, cls, topic):
    return {"id": fid, "classification": cls,
            "requirement": {"code": code, "name": code, "description": topic,
                            "constitution": {"section": "9", "topic": topic,
                                             "basis": "COMPANY_APPROVED"}},
            "evaluations": [{"actual_value": {"v": fid}, "expected_value": {"x": 1}}],
            "evidence": [{"content": f"Clause text of {topic}, long enough to quote.",
                          "section_number": "1", "page_number": 1}]}


def _review(findings, order, **kw):
    return TemporaryReview("msa.docx", findings, attachment_id=UUID(FILE), angles={
        "legal": {"items": [{"finding_id": f["id"], "action": A.ACCEPT if
                             f["classification"] == "MATCH" else A.SEND_WORDING}
                            for f in sorted(findings, key=lambda f: order.index(f["id"]))]},
        "observations": {"structural": []}, "counter_proposals": {}}, **kw)


def test_points_follow_the_engines_order_of_importance_not_the_alphabet():
    rv = _review([_finding("a", "A", "DEVIATION", "Assignment"),
                  _finding("l", "L", "DEVIATION", "Liability")], order=["l", "a"])
    rows = D.build([rv], signed=set(), wins=FILE)["rows"]
    assert [r["topic"] for r in rows] == ["Liability", "Assignment"]
    assert "rank" not in rows[0]


def test_the_bottom_line_states_the_assumptions_and_who_decided():
    review = D.build([_review([_finding("l", "L", "DEVIATION", "Liability")], ["l"])],
                     signed=set(), wins=FILE)
    text = D.one_file_summary(review, buyer=False, signed=False)
    assert text.startswith("msa.docx, reviewed against our positions: 1 point needs")
    assert "we provide the service, still being negotiated" in text
    assert "not from me" in text
    signed = D.build([_review([_finding("l", "L", "DEVIATION", "Liability")], ["l"])],
                     signed={FILE}, wins=FILE)
    assert signed["rows"][0]["status"] == D.AGREED
    assert "already signed" in D.one_file_summary(signed, buyer=True, signed=True)


def test_nothing_covered_is_never_called_fine_and_a_part_read_file_is_never_reviewed():
    empty = D.build([_review([], [])], signed=set(), wins=FILE)
    assert "do not cover this kind of document" in D.one_file_summary(
        empty, buyer=False, signed=False)
    part = D.build([TemporaryReview("scan.pdf", [], refused="PARTIAL_READ",
                                    attachment_id=UUID(FILE), unread=[9, 10])],
                   signed=set(), wins=FILE)
    text = D.one_file_summary(part, buyer=False, signed=False)
    assert "page(s) 9, 10 of scan.pdf" in text and "have not reviewed it" in text


def test_only_the_top_points_are_shown_first():
    rv = _review([_finding(str(n), f"R{n}", "DEVIATION", f"Topic {n:02d}")
                  for n in range(10)], order=[str(n) for n in range(10)])
    review = D.build([rv], signed=set(), wins=FILE)
    assert D.shown_codes(review) == {f"R{n}" for n in range(D.SHOWN)}


def test_a_stored_review_is_carried_into_the_thread_for_follow_ups():
    review = D.build([_review([_finding("l", "L", "DEVIATION", "Liability"),
                               _finding("m", "M", "MATCH", "Notice")], ["l", "m"])],
                     signed=set(), wins=FILE)
    note = agent.review_note({"kind": "deal_review", **review})
    assert "1. Liability — clause 1 — ask for a change — our position: Constitution §9" \
        in note
    assert "Notice" not in note                   # what matches is not a point to raise
    assert agent.review_note({"kind": "questions"}) == ""
    assert agent.review_note(None) == ""


def _ten():
    rv = _review([_finding(str(n), f"R{n}", "DEVIATION", f"Topic {n:02d}")
                  for n in range(10)], order=[str(n) for n in range(10)])
    return D.build([rv], signed=set(), wins=FILE)


def test_the_answer_takes_the_shape_the_reader_asked_for():
    review = _ten()
    three = D.shaped(review, count=3, bullets=True, table=False, short=False)
    assert three.count("\n- ") == 2 and three.startswith("- **Topic 00** (clause 1)")
    assert "ask for a change — our rule: Constitution §9" in three
    table = D.shaped(review, count=None, bullets=False, table=True, short=False)
    assert table.splitlines()[0] == "| Point | Where | What to do | Our rule |"
    assert len(table.splitlines()) == 2 + D.SHOWN
    assert D.shaped(review, count=None, bullets=False, table=False, short=True) \
        .count("\n") == 2                                  # short: the top three
    # no shape asked for: the memo is the answer
    assert D.shaped(review, count=None, bullets=False, table=False, short=False) is None


def test_a_difference_with_no_approved_wording_is_still_ask_for_a_change():
    # its action says Legal supplies the wording; "Legal decides" for it buried the signal
    assert D.cell_status("DEVIATION", A.NO_WORDING) == D.ASK_CHANGE
    assert D.cell_status("DEVIATION", A.SEND_WORDING) == D.ASK_CHANGE


def test_a_point_the_contract_does_not_state_names_no_clause():
    review = D.build([_review([_finding("m", "M", "MISSING", "Suspension")], ["m"])],
                     signed=set(), wins=FILE)
    assert "(not stated)" in D.shaped(review, count=1, bullets=True, table=False,
                                      short=False)
    assert "already match" not in D.one_file_summary(review, buyer=False, signed=False)
