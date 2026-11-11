"""UX Batch 1 slice A — the client's paper read truthfully (2026-11-09).

(a) A point on the client's paper shows a passage only where its mapping was CONFIRMED;
an unresolved mapping lists the clauses that may hold it, unranked, with no passage; a
NEGATIVE row says why (WORSE / ABSENT / NOT_MEASURED) with its route unchanged; one
wording is never written over two clauses. (b) A Word->Markdown export's marks are
read away (ingest-v11); a number the paper uses for two clauses names each by its own words.
Every text here is synthetic structure — no legal conclusion is asserted (rule 21).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from legalmind.analysis import negotiation as N
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting.reply_plan import Answer, reply_rows, sha256
from legalmind.ingestion.parsing import parse_text
from legalmind.mapping.engine import Clause
from tests.conftest import make_evaluation, make_finding
from tests.test_negotiation import _contract, _docx, _ingest, owner  # noqa: F401

PAPER = ("1. Alpha clause text.", "2. Beta clause text.", "3. Gamma clause text.")


def _paper(db, tmp_path, owner):
    c = _contract(db, owner)
    data = _docx(*PAPER)
    version = _ingest(db, tmp_path, c, data, "theirs.docx")
    evidence = db.scalars(select(M.DocumentEvidence.id)
                          .where(M.DocumentEvidence.document_version_id == version.id)
                          .order_by(M.DocumentEvidence.start_offset)).all()
    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex,
                                   created_by=version.uploaded_by)
    db.add(snap)
    db.flush()
    review = M.Review(contract_id=c.id, document_version_id=version.id,
                      configuration_snapshot_id=snap.id,
                      status=E.ReviewStatus.ANALYSIS_COMPLETE,
                      created_by=version.uploaded_by)
    db.add(review)
    db.flush()
    return c, version, data, evidence, review


def _point(db, review, cls, evaluations):
    """One Finding; ``evaluations``: (mapping state or None, evidence ids)."""
    req = M.Requirement(code=f"PT-{uuid.uuid4().hex[:6]}", status=E.ConfigStatus.ACTIVE)
    db.add(req)
    db.flush()
    rv = M.RequirementVersion(requirement_id=req.id, version_number=1, name="Point",
                              evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                              created_by=review.created_by)
    db.add(rv)
    db.flush()
    finding = make_finding(db, review, rv, classification=cls)
    for state, ids in evaluations:
        ev = make_evaluation(db, finding, classification=cls,
                             rule_outcome=E.RuleOutcome.UNACCEPTABLE,
                             scope_key=uuid.uuid4().hex[:8])
        if state is not None:
            ev.result = {"diagnostics": [], "evaluated_facts": {"mapping_state": state}}
        for e in ids:
            db.add(M.EvaluationEvidence(evaluation_id=ev.id, evidence_id=e,
                                        relationship_type=E.EvidenceRelationshipType.PRIMARY))
    db.flush()
    return req.code


def _row(db, c, version, code):
    rows = N.paper_first(db, c, version, legal_position=True)["changes"]
    return next(r for r in rows if r["review"]["after"][0]["requirement_code"] == code)


def test_an_unresolved_point_shows_no_passage_and_lists_its_candidates(
        db, owner, tmp_path):
    c, version, _, ev, review = _paper(db, tmp_path, owner)
    code = _point(db, review, E.FindingClassification.UNABLE_TO_EVALUATE,
                  [("UNRESOLVED", ev)])
    row = _row(db, c, version, code)
    assert row["after"] is None and row["clauses"] == []
    assert [x["number"] for x in row["candidates"]] == ["1", "2", "3"]
    assert row["measured"] == "NOT_MEASURED"
    assert (row["route"], row["effect_for_us"]) == ("holder", "NEGATIVE")   # unchanged
    # AM-253: the key is still the finding's first evidence row, as before
    (found,) = N._review_findings(db, review)
    assert row["row_key"] == f"N|THEIRS|{code}|{found['evidence_ids'][0]}"


def test_an_unstamped_evaluation_is_not_confirmed(db, owner, tmp_path):
    c, version, _, ev, review = _paper(db, tmp_path, owner)
    code = _point(db, review, E.FindingClassification.DEVIATION, [(None, ev[:1])])
    row = _row(db, c, version, code)
    assert row["after"] is None and [x["number"] for x in row["candidates"]] == ["1"]


def test_a_missing_point_is_not_in_their_paper(db, owner, tmp_path):
    c, version, _, _, review = _paper(db, tmp_path, owner)
    code = _point(db, review, E.FindingClassification.MISSING, [("NONE", [])])
    row = _row(db, c, version, code)
    assert row["measured"] == "ABSENT" and row["after"] is None


def test_a_deviation_reads_only_its_confirmed_clause(db, owner, tmp_path):
    c, version, _, ev, review = _paper(db, tmp_path, owner)
    code = _point(db, review, E.FindingClassification.DEVIATION,
                  [("CONFIRMED", [ev[1]]), ("UNRESOLVED", [ev[0], ev[2]])])
    row = _row(db, c, version, code)
    assert row["measured"] == "WORSE"
    assert row["after"] == {"evidence_ids": [str(ev[1])], "text": PAPER[1]}
    assert row["clause"]["number"] == "2" and len(row["clauses"]) == 1
    assert "candidates" not in row


def test_one_wording_is_never_written_over_two_clauses(db, owner, tmp_path):
    c, version, data, ev, review = _paper(db, tmp_path, owner)
    code = _point(db, review, E.FindingClassification.DEVIATION,
                  [("CONFIRMED", [ev[0], ev[1]])])
    row = _row(db, c, version, code)
    assert [x["number"] for x in row["clauses"]] == ["1", "2"]
    wording = "1. Our wording."
    (plan,) = reply_rows(db, None, version,
                         {row["row_key"]: Answer("write_wording", wording, sha256(wording))},
                         data, theirs_rows=[row])
    assert plan.edits == [] and plan.error is not None
    assert plan.error.code == "UNSUPPORTED" and "1 and 2" in str(plan.error)


def test_why_a_negative_row_goes_to_legal():
    dev = {"classification": "DEVIATION", "user_status": "NEEDS_DECISION"}
    favoured = {"classification": "DEVIATION", "user_status": "ACCEPTABLE"}
    unable = {"classification": "UNABLE_TO_EVALUATE", "user_status": "NEEDS_DECISION"}
    assert N._measured("NEUTRAL", "MODIFIED", [], [dev], None) == {}
    assert N._measured("NEGATIVE", "MODIFIED", [], [dev], None)["measured"] == "WORSE"
    assert N._measured("NEGATIVE", "MODIFIED", [], [favoured], None)["measured"] \
        == "REVIEW"
    match = {"classification": "MATCH", "user_status": "ACCEPTABLE"}
    assert N._measured("NEGATIVE", "MODIFIED", [match], [match], None)["measured"] \
        == "REVIEW"                          # AM-317 r1: words changed, still matches
    assert N._measured("NEGATIVE", "MODIFIED", [], [unable], None)["measured"] \
        == "NOT_MEASURED"
    assert N._measured("NEGATIVE", "MODIFIED", [], [unable],
                       {"reasons": [{"reason": "r", "quote": "q"}]})["measured"] == "WORSE"
    assert N._measured("NEGATIVE", "DELETED", [unable], [], None)["measured"] == "WORSE"
    assert N._measured("NEGATIVE", "MOVED", [], [], None)["measured"] == "NOT_MEASURED"


# ------------------------------------------------------------------ (b) reading
def test_a_markdown_export_reads_its_numbers_and_headings():
    data = b"12. ## **CONFIDENTIALITY**\n\n8. Suspension**:** text \\- here"
    segments = parse_text(data, markdown=True).segments
    assert (segments[0].section_number, segments[0].section_title) \
        == ("12", "CONFIDENTIALITY")
    assert segments[1].section_number == "8"
    assert not any(ch in s.content for s in segments for ch in "*#")
    assert "text - here" in segments[1].content
    plain = parse_text(data, markdown=False).segments
    assert plain[0].content == "12. ## **CONFIDENTIALITY**"
    assert "\\-" in plain[1].content


def test_a_markdown_blank_and_change_marks_are_kept():
    data = b"4. Name: ____ and ~~old~~ [new]{.insertion}."
    (seg,) = parse_text(data, markdown=True).segments
    assert "____" in seg.content and "~~old~~" in seg.content
    assert "[new]{.insertion}" in seg.content


def _clauses(rows):
    return [Clause(uuid.uuid4(), text, number, title, None, heading)
            for text, number, title, heading in rows]


def _names(rows):
    return [(u["number"], u["name"]) for u in N._units(_clauses(rows))]


# re-verify 2026-11-09: a repeated number is named by each clause's OWN words only
STORED_V1 = [  # ingest-v10 reading of a Word->Markdown export: marks left in
    ("**ARTICLE 7 \u2013 TERMINATION**", None, None, False),
    ("2. ## **Restriction on Early Termination**", "2", "Restriction on Early Termination",
     True),
    ("5. ## **Immediate Termination Rights**", "5", "Immediate Termination Rights", True),
    ("6. After notice the services stop.", "6", None, False),
    ("**ARTICLE 8 \u2013 INVOICING**", None, None, False),
    ("2. **Invoicing and Payment**", "2", None, False),
    ("**ARTICLE 21 \u2013 FORCE MAJEURE**", None, None, False),
    ("1. Neither party is liable for events beyond control.", "1", None, False)]


def test_two_clauses_with_one_number_are_named_by_their_own_words():
    got = _names(STORED_V1)
    assert [x for x in got if x[1]] == [("2", "Restriction on Early Termination"),
                                         ("2", "Invoicing and Payment")]
    # a number used once (5, 6, 1, the articles) is not named at all
    assert all(name is None for number, name in got if number != "2")


def test_continuation_rows_are_one_clause_not_a_repeat():
    rows = [("3. Fees.", "3", None, False), ("3. are due monthly.", "3", None, False),
            ("4. Term.", "4", None, False)]
    assert _names(rows) == [("3", None), ("4", None)]


def test_a_clause_with_no_heading_is_named_by_its_first_words():
    rows = [("1. \u200b", "1", "\u200b", False), ("9. Other.", "9", None, False),
            ("1. Each party keeps the other party's information secret at all times here.",
             "1", None, False)]
    got = _names(rows)
    assert got[0] == ("1", None)                    # nothing of its own to say: unnamed
    assert got[1] == ("9", None)
    assert got[2] == ("1", "Each party keeps the other party's information secret…")


def test_a_name_is_read_past_an_empty_first_line():
    rows = [("8.4.\u200b\nAll amounts payable are due in thirty days.", "8.4", None, False),
            ("9. Other.", "9", None, False),
            ("8.4 Data is kept for the term.", "8.4", None, False)]
    assert [n for _, n in _names(rows)] == [
        "All amounts payable are due in thirty days", None, "Data is kept for the term"]


def test_a_sub_clause_groups_under_its_own_parent_unit():
    rows = [("2. Fees are invoiced.", "2", None, False),
            ("2.1 Invoices monthly.", "2.1", None, False),
            ("3. Term.", "3", None, False),
            ("2. Early exit is restricted.", "2", None, False),
            ("2.1 Notice of ninety days.", "2.1", None, False),
            ("4. Unique.", "4", None, False), ("4.1 Unique sub.", "4.1", None, False)]
    units = N._units(_clauses(rows))
    groups = [(u["number"], u["group"] and u["group"]["name"]) for u in units]
    assert groups == [("2", "Fees are invoiced"), ("2.1", "Fees are invoiced"),
                      ("3", None), ("2", "Early exit is restricted"),
                      ("2.1", "Early exit is restricted"), ("4", None), ("4.1", None)]


def test_a_clause_is_said_once_with_its_own_words():
    assert N.clause_label({"number": "2", "heading": "Fees", "name": "Fees"}) == "2 — Fees"
    assert N.clause_label({"number": "7", "heading": "Fees", "name": None}) == "7 Fees"
    assert N.clause_label({"number": "7", "heading": "Fees"}, heading=False) == "7"
