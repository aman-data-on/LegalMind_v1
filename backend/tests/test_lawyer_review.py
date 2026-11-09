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
    "Is this ok to sign?",
    # lawyer batch 1 (B1.6, owner 2026-11-09): the everyday ways a contract is handed
    # to a lawyer — "what are the risks" in THIS contract now gets the review too
    "is this ok?", "what puts us in danger here?", "what are the risks in this contract?",
    "What are the risks in this?", "anything in our favour?", "review this",
    "theek hai kya", "isme risk kya hai", "is this contract safe?",
    "which clauses are in our favour?"])
def test_a_lawyers_question_on_one_file_is_read(asked):
    assert service.wants_lawyer_review(asked)


@pytest.mark.parametrize("asked, loose", [
    ("is this ok?", True), ("anything in our favour?", True),
    ("review this contract", False), ("Is this ok to sign?", False)])
def test_an_everyday_phrasing_alone_needs_the_turn_to_be_about_the_file(asked, loose):
    """B1.6: only "review this contract"-style asks route on their own; "is this ok?"
    routes when the file is what the turn is about (`material_reason`)."""
    assert service.loose_review_only(asked) is loose


@pytest.mark.parametrize("asked", [
    # recheck D2: a question about one clause, figure or action is the agent's
    "client wants 45 days payment terms in clause 8, is that ok?",
    "is it ok if we give them 60 days notice instead of 30?",
    "is this fine to send to the client?", "what are the risks here if we miss the SLA?",
    "is it safe to share our pricing with them?",
    "review the attached and tell me the notice period",
    "Summarise this agreement", "what are the risks of GDPR?",
    "is the DPDP Act in force?", "what is our liability cap?",
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


def test_a_no_position_file_is_named_as_not_measured_never_as_reviewed():
    """Q-7 review (3): an AUP is never "reviewed side by side against our positions",
    and is never "could not be read as an agreement" either."""
    aup = TemporaryReview("aup.pdf", [], refused=service.NO_POSITION,
                          attachment_id=UUID(int=8))
    alone = D.build([aup], signed=set(), wins=str(UUID(int=8)))
    assert D.one_file_summary(alone, buyer=False, signed=False) \
        == service.not_measured_text("aup.pdf")
    both = D.build([_review([_finding("l", "L", "DEVIATION", "Liability")], ["l"]), aup],
                   signed=set(), wins=None)
    text = D.summary(both)
    assert text.startswith("I reviewed msa.docx side by side against our positions")
    assert "aup.pdf" not in text.split(".")[0]
    assert text.endswith(service.not_measured_text("aup.pdf"))
    assert D.summary(D.build([aup], signed=set(), wins=None)) \
        == service.not_measured_text("aup.pdf")


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
    assert "match our position" not in D.one_file_summary(review, buyer=False, signed=False)


# ------------------------------------------- lawyer batch 1 (B1.5): the four groups
PROVIDER_FAVOUR = (f"{A.FAVOURABLE}. Counsel confirms it holds: a shorter period may be "
                   "read as a penalty")


def _favour_review(favour_action=A.FAVOURABLE, enforceability=None, away=False):
    findings = [_finding("m", "M", "DEVIATION", "Liability"),
                _finding("a", "N", "DEVIATION", "Notice"),
                _finding("p", "PAYMENT-PERIOD-MSA", "DEVIATION", "Payment period"),
                _finding("x", "X", "MATCH", "Governing law"),
                _finding("y", "Y", "MATCH", "Venue")]
    actions = {"m": A.MUST_CHANGE, "a": A.SEND_WORDING, "p": favour_action,
               "x": A.ACCEPT, "y": A.ACCEPT}
    items = [{"finding_id": f, "action": a,
              **({"enforceability": enforceability} if enforceability and f == "p"
                 else {})} for f, a in actions.items()]
    clauses = [{"clause": "9.2", "page": 3, "effect": "AWAY_FROM_LEAPSWITCH",
                "reading": {"quote": "the Customer shall pay within 7 days"}},
               {"clause": "9.3", "page": 3, "effect": None}] if away else []
    return TemporaryReview("msa.docx", findings, attachment_id=UUID(FILE), angles={
        "legal": {"items": items}, "observations": {"structural": []},
        "counter_proposals": {},
        **({"client_changes": {"changes": 2, "sections": [
            {"section": "9", "title": "Payment", "notes": [], "changes": [],
             "clauses": clauses}]}} if away else {})})


def test_a_point_in_our_favour_is_its_own_group_never_a_match():
    review = D.build([_favour_review()], signed=set(), wins=FILE)
    c = review["counts"]
    assert (c[D.MUST_CHANGE], c[D.ASK_CHANGE], c[D.FAVOUR], c[D.FINE]) == (1, 1, 1, 2)
    text = D.one_file_summary(review, buyer=False, signed=False)
    assert "1 must change before signing, 1 to negotiate" in text
    assert "1 in our favour — keep; usable as leverage in negotiation" in text
    assert "2 match our position" in text
    assert [r["needs"] for r in review["rows"]] == [
        D.MUST_CHANGE, D.ASK_CHANGE, D.FAVOUR, D.FINE, D.FINE]
    table = D.shaped(review, count=None, bullets=False, table=True, short=False)
    assert "| Payment period | clause 1 | in our favour |" in table


def test_the_engines_role_guard_decides_favour_customer_paper_is_not_favour():
    """On customer paper the engine (`angles._in_our_favour`) never words a point as
    favourable, so its plain "send our wording" stays a point to negotiate."""
    review = D.build([_favour_review(favour_action=A.SEND_WORDING)], signed=set(),
                     wins=FILE)
    assert review["counts"][D.FAVOUR] == 0 and review["counts"][D.ASK_CHANGE] == 2
    assert D.cell_status("DEVIATION", A.ACCEPT_FAVOURABLE) == D.FAVOUR
    assert D.cell_status("MATCH", A.FAVOURABLE) == D.FINE


def test_a_push_back_note_only_where_a_source_states_it():
    with_check = D.build([_favour_review(favour_action=PROVIDER_FAVOUR)], signed=set(),
                         wins=FILE)
    cell = next(r for r in with_check["rows"] if r["needs"] == D.FAVOUR)["cells"][FILE]
    assert cell["counsel"] == {"text": "a shorter period may be read as a penalty",
                               "source": "standard"}
    note = {"section": "28.6", "text": "Subject to usury/penalty case law",
            "law": {"source": "Indian Contract Act, 1872", "section": "74", "quote": "q"}}
    by_law = D.build([_favour_review(enforceability=note)], signed=set(), wins=FILE)
    cell = next(r for r in by_law["rows"] if r["needs"] == D.FAVOUR)["cells"][FILE]
    assert cell["counsel"]["section"] == "28.6" and cell["counsel"]["law"]["section"] == "74"
    bare = D.build([_favour_review()], signed=set(), wins=FILE)
    cell = next(r for r in bare["rows"] if r["needs"] == D.FAVOUR)["cells"][FILE]
    assert "counsel" not in cell
    assert "push-back" not in D.one_file_summary(bare, buyer=False, signed=False)


def test_a_client_change_both_readings_call_better_for_us_is_in_our_favour():
    review = D.build([_favour_review(away=True)], signed=set(), wins=FILE)
    assert review["files"][0]["favour_changes"] == [
        {"clause": "9.2", "page": 3, "quote": "the Customer shall pay within 7 days"}]
    assert review["counts"][D.FAVOUR] == 2 and review["counts"][D.FINE] == 2


def test_the_favour_group_is_always_said_and_a_clause_counted_once():
    """Recheck D6: a short list cut at seven still names what favours us; a clause that is
    a favour finding and a client change both is one point."""
    many = [_finding(f"m{i}", f"M{i}", "DEVIATION", f"Topic {i}") for i in range(8)]
    fav = _finding("p", "PAYMENT-PERIOD-MSA", "DEVIATION", "Payment period")
    rv = TemporaryReview("msa.docx", [*many, fav], attachment_id=UUID(FILE), angles={
        "legal": {"items": [*({"finding_id": f["id"], "action": A.MUST_CHANGE}
                              for f in many), {"finding_id": "p", "action": A.FAVOURABLE}]},
        "observations": {"structural": []}, "counter_proposals": {},
        "client_changes": {"changes": 1, "sections": [{"section": "1", "title": "T",
            "notes": [], "changes": [], "clauses": [{"clause": "1", "page": 1,
                                                     "effect": "AWAY_FROM_LEAPSWITCH"}]}]}})
    review = D.build([rv], signed=set(), wins=FILE)
    assert review["counts"][D.FAVOUR] == 1 and review["files"][0]["favour_changes"] == []
    short = D.shaped(review, count=None, bullets=True, table=False, short=False)
    assert short.count("\n- ") == D.SHOWN - 1
    assert short.endswith("In our favour — keep; usable as leverage in negotiation: "
                          "Payment period (clause 1)")


def test_a_file_that_may_be_part_of_a_document_never_reports_a_clause_missing():
    """Recheck N1/N4: a short file or a photo is still reviewed (a short amendment is a
    whole one), but what it does not state is never reported as missing (`AM-143` r5)."""
    rv = _review([_finding("l", "L", "DEVIATION", "Liability"),
                  _finding("m", "M", "MISSING", "Data loss")], ["l", "m"])
    whole = D.build([rv], signed=set(), wins=FILE)
    part = D.build([rv], signed=set(), wins=FILE, partial={FILE})
    assert [r["topic"] for r in whole["rows"]] == ["Liability", "Data loss"]
    assert [r["topic"] for r in part["rows"]] == ["Liability"]
    assert D.PART in D.one_file_summary(part, buyer=False, signed=False)
    assert D.PART not in D.one_file_summary(whole, buyer=False, signed=False)


@pytest.mark.parametrize("asked, part", [
    ("is this clause ok?", True), ("what does the screenshot say?", True),
    ("is this ok?", False), ("review this contract", False)])
def test_the_reader_calling_a_file_a_part_is_read(asked, part):
    from types import SimpleNamespace

    from legalmind.assist.agent import attachments
    pdf = SimpleNamespace(mime_type="application/pdf")
    assert attachments.names_a_part(pdf, asked) is part
    assert attachments.names_a_part(SimpleNamespace(mime_type="image/png"), asked)
