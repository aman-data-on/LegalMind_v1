"""`AM-229`–`AM-232` (2026-10-28): a client's documents reviewed side by side. The statuses
are the engine's actions and the reader's answers only; the forced questions are always
asked; the model's own questions are checked; plain words never add a figure. Synthetic
data — no client is named here (54.6). No database, no model."""
from uuid import UUID

from legalmind.api import angles as A
from legalmind.api import deal_review as D
from legalmind.api.temporary_review import TemporaryReview
from legalmind.assist.agent import deal_questions as Q
from legalmind.assist.agent import deal_words as W

MOU, MSA = str(UUID(int=1)), str(UUID(int=2))


def _finding(fid, code, cls, quote="", clause="1"):
    return {"id": fid, "classification": cls,
            "requirement": {"code": code, "name": code, "description": f"{code} standard",
                            "constitution": {"section": "9", "topic": code.title(),
                                             "basis": "COMPANY_APPROVED"}},
            "evaluations": [{"actual_value": {"v": quote}, "expected_value": {"months": 12}}],
            "evidence": [{"content": quote, "section_number": clause, "page_number": 1}]}


def _review(att, findings, actions, changed=()):
    return TemporaryReview(
        "file", findings, attachment_id=UUID(att),
        angles={"legal": {"items": [{"finding_id": f, "action": a} for f, a in actions.items()]},
                "client_changes": {"changes": len(changed), "sections": [{
                    "section": "1", "title": "T", "notes": [],
                    "changes": [{"clause": c, "kind": "Changed", "removed": "a",
                                 "added": "b", "measured_by": []} for c in changed]}]},
                "observations": {"structural": []}, "counter_proposals": {}})


def _rows(signed, wins):
    mou = _review(MOU, [_finding("m1", "CAP", "DEVIATION", "capped at 12 months", "13"),
                        _finding("m2", "NOTICE", "MATCH", "30 days notice", "5")],
                  {"m1": A.SEND_WORDING})
    msa = _review(MSA, [_finding("s1", "CAP", "DEVIATION", "uncapped for indemnity", "17"),
                        _finding("s2", "NOTICE", "MATCH", "30 days notice", "5"),
                        _finding("s3", "SUSPEND", "MISSING")],
                  {"s1": A.MUST_CHANGE, "s3": A.SEND_WORDING}, changed=("17",))
    return {r["code"]: r for r in D.build([mou, msa], signed=signed, wins=wins)["rows"]}


def test_the_signed_winner_is_agreed_and_a_worse_point_elsewhere_is_never_hidden():
    rows = _rows({MOU}, MOU)
    cap = rows["CAP"]
    assert cap["status"] == D.AGREED and cap["decided_by"] == MOU
    assert [a["status"] for a in cap["also"]] == [D.MUST_CHANGE]      # the MSA's extra
    assert cap["needs"] == D.MUST_CHANGE and cap["cells"][MSA]["changed"] is True
    assert rows["NOTICE"]["status"] == D.FINE and rows["NOTICE"]["also"] == []
    assert rows["SUSPEND"]["status"] == D.ASK_CHANGE          # only the MSA speaks to it


def test_with_no_winner_named_files_that_differ_go_to_a_person():
    rows = _rows(set(), None)
    assert rows["CAP"]["status"] == D.LEGAL_DECIDES and rows["CAP"]["note"] == "files_differ"
    assert rows["NOTICE"]["status"] == D.FINE


def test_an_unsigned_winner_is_never_agreed_and_an_unreadable_one_goes_to_a_person():
    assert _rows(set(), MOU)["CAP"]["status"] == D.ASK_CHANGE
    assert D.cell_status("UNABLE_TO_EVALUATE", None) == D.LEGAL_DECIDES
    assert D.cell_status("MATCH", A.FAVOURABLE) == D.FINE
    assert D.cell_status("DEVIATION", A.MUST_CHANGE) == D.MUST_CHANGE


def test_counts_name_what_each_row_needs_and_the_summary_says_who_decided():
    review = D.build([_review(MOU, [_finding("m1", "CAP", "DEVIATION", "x")], {}),
                      _review(MSA, [_finding("s1", "CAP", "DEVIATION", "y")],
                              {"s1": A.MUST_CHANGE})], signed={MOU}, wins=MOU)
    assert review["counts"][D.MUST_CHANGE] == 1
    assert "not from me" in D.summary(review)


def test_the_two_questions_are_always_asked_until_answered_and_quote_the_documents():
    files = [Q.FileFacts(MOU, "MOU", precedence=["Clause 13: “this MOU shall prevail”"]),
             Q.FileFacts(MSA, "MSA")]
    asked = Q.forced(files, {})
    assert [q["id"] for q in asked] == ["signed", "wins"]
    assert "this MOU shall prevail" in asked[1]["why"]
    assert Q.OPEN in [o["value"] for o in asked[1]["options"]]
    assert Q.forced(files, {"signed": [MOU], "wins": MOU}) == []


def _q(qid, text, default="a"):
    return {"id": qid, "text": text, "why": "it changes the advice", "default": default,
            "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]}


def test_the_models_questions_never_ask_our_position_or_repeat_what_is_asked():
    proposed = [_q("started", "Has the service already started?", default="B"),
                _q("cap", "What liability cap do we accept for this client?"),
                _q("signed2", "Has the client already signed either document?"),
                _q("wins2", "Which document governs if they conflict?"),
                {"id": "bad", "text": "No options?", "why": "x", "options": [], "default": "a"}]
    kept = Q.valid_proposed(proposed, {}, Q.forced([Q.FileFacts(MOU, "MOU")], {}))
    assert [(q["id"], q["default"]) for q in kept] == [("started", "b")]  # label → value
    assert Q.valid_proposed([_q("started", "Has it started?")], {"started": "a"}, []) == []


def test_plain_words_never_add_a_figure_and_never_rewrite_a_heading():
    quote = "Either party may terminate on thirty (30) days written notice."
    assert W.kept("Either side can end it with 30 days' written notice.", quote)
    assert not W.kept("Either side can end it with 60 days' notice.", quote)
    assert not W.rewritable("INDEMNIFICATION")


def test_another_file_that_agrees_with_or_is_silent_on_the_agreed_point_is_no_issue():
    mou = _review(MOU, [_finding("m1", "VENUE", "DEVIATION", "New Delhi"),
                        _finding("m2", "PRICE", "MATCH", "fixed for a year")],
                  {"m1": A.SEND_WORDING})
    msa = _review(MSA, [_finding("s1", "VENUE", "DEVIATION", "New Delhi"),
                        _finding("s2", "PRICE", "MISSING")],
                  {"s1": A.SEND_WORDING, "s2": A.SEND_WORDING})
    rows = {r["code"]: r for r in D.build([mou, msa], signed={MOU}, wins=MOU)["rows"]}
    assert rows["VENUE"]["status"] == D.AGREED and rows["VENUE"]["also"] == []   # same words
    assert rows["PRICE"]["needs"] == D.FINE and rows["PRICE"]["also"] == []      # silence


def test_the_quote_is_the_clause_row_never_its_heading():
    f = _finding("s1", "INDEMNITY", "DEVIATION", "x")
    f["evidence"] = [{"content": "INDEMNIFICATION", "section_number": "16", "page_number": 1},
                     {"content": "The Provider shall indemnify the Customer against all "
                                 "third-party claims.", "section_number": "16.1", "page_number": 1}]
    cell = D.build([_review(MSA, [f], {})], signed=set(), wins=None)["rows"][0]["cells"][MSA]
    assert cell["clause"] == "16.1" and cell["quote"].startswith("The Provider")


def test_a_term_stated_by_one_file_of_the_deal_is_read_from_its_segments():
    from legalmind.api.temporary_review import states_fixed_term
    assert states_fixed_term([{"content": "Contract Term: 1 Year (fixed-term commitment)",
                               "section_number": "2"}])
    assert not states_fixed_term([{"content": "Services are provided month to month."}])
