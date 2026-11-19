"""Redline truth (client case 2026-11-19, batch 1): every screen tells the truth about a
client's tracked changes. R2 "changed without marking it" only where the returned copy's
wording before its marks is not ours, read over the whole document (a block deleted
whole is kept on the row before it — `parsing.drop` — and two papers may cut a clause
into units differently); a clause rewritten under marks pairs with its own counterpart
(F3); the client's Word comments ride on the change they belong to; an answer is never
dropped when a reading pairs a clause differently (ground rule 1, `AM-253`).

Every document is built here as synthetic OOXML (CI runs it without any real file) and
names no client; the words are illustrations, never a position (rule 21).
"""

from __future__ import annotations

import io

import docx
import pytest
from docx.oxml import parse_xml
from docx.text.run import Run

from legalmind.analysis import negotiation
from legalmind.db import models as M
from tests.test_negotiation import OURS, _contract, _ingest, owner  # noqa: F401
from tests.test_negotiation_wording import published  # noqa: F401  (fixture)

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_AT = 'w:author="Client" w:date="2026-11-01T00:00:00Z"'


def r(t: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{t}</w:t></w:r>'


def br(*lines: str) -> str:
    """One run of ``lines`` with a line break (w:br) between them."""
    return "<w:r>" + "<w:br/>".join(f'<w:t xml:space="preserve">{t}</w:t>'
                                    for t in lines) + "</w:r>"


def d(t: str, n: int) -> str:
    return f'<w:del w:id="{n}" {_AT}><w:r><w:delText xml:space="preserve">{t}' \
           "</w:delText></w:r></w:del>"


def d_br(n: int, *lines: str) -> str:
    return f'<w:del w:id="{n}" {_AT}><w:r>' + "<w:br/>".join(
        f'<w:delText xml:space="preserve">{t}</w:delText>' for t in lines) + "</w:r></w:del>"


def i(t: str, n: int) -> str:
    return f'<w:ins w:id="{n}" {_AT}>{r(t)}</w:ins>'


def p(*runs: str, mark_deleted: int | None = None) -> str:
    """A paragraph; ``mark_deleted``: its paragraph mark is a tracked deletion too —
    how Word records a paragraph deleted whole."""
    ppr = f'<w:pPr><w:rPr><w:del w:id="{mark_deleted}" {_AT}/></w:rPr></w:pPr>' \
        if mark_deleted is not None else ""
    return f"<w:p {W}>{ppr}{''.join(runs)}</w:p>"


def gone(text: str, n: int) -> str:
    """A paragraph deleted whole: every run and its mark."""
    return p(d(text, n), mark_deleted=n + 1)


def table(rows: list[list[str]], deleted: frozenset[int] = frozenset(), n: int = 50) -> str:
    """A table; the rows in ``deleted`` are tracked deletions (row mark and text)."""
    out = []
    for k, cells in enumerate(rows):
        dead = k in deleted
        trpr = f'<w:trPr><w:del w:id="{n + k}" {_AT}/></w:trPr>' if dead else ""
        tcs = "".join(f"<w:tc><w:p>{d(c, n + 10 + k) if dead else r(c)}</w:p></w:tc>"
                      for c in cells)
        out.append(f"<w:tr>{trpr}{tcs}</w:tr>")
    return f"<w:tbl {W}><w:tblGrid/>{''.join(out)}</w:tbl>"


def build(*blocks: str, comment_on: int | None = None, comment: str = "") -> bytes:
    """A DOCX of raw body ``blocks`` (paragraph or table XML). ``comment_on``: the
    block index whose first plain run carries a Word comment by "Counsel"."""
    doc = docx.Document()
    body = doc.element.body
    for block in blocks:
        body.insert(len(body) - 1, parse_xml(block))
    if comment_on is not None:
        para = doc.paragraphs[comment_on]
        run = para._p.xpath("./w:r")[0]
        doc.add_comment(Run(run, para), text=comment, author="Counsel")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def plain(*texts: str) -> bytes:
    return build(*(p(r(t)) for t in texts))


def _listed(db, owner, tmp_path, ours: bytes, theirs: bytes, **kw):
    c = _contract(db, owner)
    v1 = _ingest(db, tmp_path, c, ours, "ours.docx")
    v2 = _ingest(db, tmp_path, c, theirs, "theirs.docx")
    return negotiation.changes(db, c, v1, v2, legal_position=kw.get("legal", True))


def _rows(listed) -> list[tuple]:
    return [(c["kind"], c["clause"]["number"], c["tracked"], c["untracked"])
            for c in listed["changes"]]


# clause 1 edited under marks (30 -> 60), the paragraph after it deleted whole
EDITED = p(r("1. Fees are payable within "), d("30", 1), i("60", 2), r(" days of invoice."))


def test_a_paragraph_deleted_whole_beside_a_tracked_edit_is_never_untracked(db, owner,
                                                                             tmp_path):
    listed = _listed(db, owner, tmp_path, plain(*OURS),
                     build(EDITED, gone(OURS[1], 3), p(r(OURS[2])), p(r(OURS[3]))))
    assert _rows(listed) == [("MODIFIED", "1", True, False), ("DELETED", "2", True, False)]
    assert listed["summary"]["untracked"] == 0


def test_a_deleted_paragraph_with_a_line_break_is_never_untracked(db, owner, tmp_path):
    lines = ("2. This Agreement is governed", "by the laws of India.")
    ours = build(p(r(OURS[0])), p(br(*lines)), p(r(OURS[2])), p(r(OURS[3])))
    theirs = build(EDITED, p(d_br(3, *lines), mark_deleted=4), p(r(OURS[2])),
                   p(r(OURS[3])))
    listed = _listed(db, owner, tmp_path, ours, theirs)
    assert listed["summary"]["untracked"] == 0
    assert [c["kind"] for c in listed["changes"]] == ["MODIFIED", "DELETED"]


def test_a_deleted_table_row_and_a_deleted_table_are_never_untracked(db, owner, tmp_path):
    grid = [["Service", "Monthly fee"], ["Hosting", "100"], ["Backup", "20"]]
    ours = build(*(p(r(t)) for t in OURS), table(grid))
    row_gone = _listed(db, owner, tmp_path, ours,
                       build(EDITED, *(p(r(t)) for t in OURS[1:]), table(grid, frozenset({2}))))
    assert row_gone["summary"]["untracked"] == 0 and row_gone["changes"]
    all_gone = _listed(db, owner, tmp_path, ours,
                       build(EDITED, *(p(r(t)) for t in OURS[1:]),
                             table(grid, frozenset({0, 1, 2}))))
    assert all_gone["summary"]["untracked"] == 0 and all_gone["changes"]


def test_a_tracked_move_is_never_untracked(db, owner, tmp_path):
    def move(tag: str, t: str, n: int) -> str:
        run = "delText" if tag == "moveFrom" else "t"
        return p(f'<w:{tag} w:id="{n}" {_AT}><w:r><w:{run} xml:space="preserve">{t}'
                 f"</w:{run}></w:r></w:{tag}>")
    listed = _listed(db, owner, tmp_path, plain(*OURS),
                     build(EDITED, p(r(OURS[1])), move("moveFrom", OURS[2], 5),
                           p(r(OURS[3])), move("moveTo", OURS[2], 6)))
    assert listed["summary"]["untracked"] == 0
    assert ("MOVED", "3", True, False) in _rows(listed)


def test_a_deleted_paragraph_mark_is_never_untracked(db, owner, tmp_path):
    """Two paragraphs joined by deleting the first one's mark, beside a tracked edit."""
    listed = _listed(db, owner, tmp_path, plain(*OURS),
                     build(EDITED, p(r(OURS[1]), mark_deleted=7), p(r(OURS[2])),
                           p(r(OURS[3]))))
    assert listed["summary"]["untracked"] == 0
    assert _rows(listed) == [("MODIFIED", "1", True, False)]


def test_negative_control_one_silent_edit_is_exactly_one_untracked(db, owner, tmp_path):
    """The first test's copy plus one edit made WITHOUT tracking: exactly that row."""
    silent = OURS[3].replace("one year", "two years")
    listed = _listed(db, owner, tmp_path, plain(*OURS),
                     build(EDITED, gone(OURS[1], 3), p(r(OURS[2])), p(r(silent))))
    assert listed["summary"]["untracked"] == 1
    assert [(c["clause"]["number"]) for c in listed["changes"] if c["untracked"]] == ["4"]


def test_a_clause_rewritten_under_marks_pairs_with_its_own_counterpart(db, owner, tmp_path):
    """F3: 5.1 rewritten under marks into words that resemble 5.3, and 5.3 deleted whole:
    5.1 pairs with our 5.1 (its wording before the marks), never with 5.3."""
    ours = ["5. Deliveries.", "5.1. the parcels are packed in blue boxes;",
            "5.2. the courier collects them on Monday;",
            "5.3. the green crates go to the north warehouse or to the east depot."]
    theirs = build(p(r(ours[0])),
                   p(r("5.1. "), d("the parcels are packed in blue boxes;", 1),
                     i("the green crates and the yellow crates go to the north warehouse "
                       "or to the west depot;", 2)),
                   p(r(ours[2])), gone(ours[3], 3))
    listed = _listed(db, owner, tmp_path, plain(*ours), theirs)
    by = {(c["kind"], c["clause"]["number"]): c for c in listed["changes"]}
    assert set(by) == {("MODIFIED", "5.1"), ("DELETED", "5.3")}
    assert by[("MODIFIED", "5.1")]["before"]["text"].startswith("5.1.")
    assert listed["summary"]["untracked"] == 0


def test_the_clients_comment_rides_on_its_change_and_ours_only_for_legal(db, owner,
                                                                         tmp_path):
    """The client's Word comment is on the row's after side as {author, text}; a comment
    in OUR version is our own note — only for a reader of positions, omitted otherwise
    (never null). A comment on an unchanged clause is listed apart."""
    ours = build(*(p(r(t)) for t in OURS), comment_on=1, comment="Our own note.")
    theirs = build(EDITED, p(r(OURS[1])), p(r(OURS[2])), p(r(OURS[3])),
                   comment_on=0, comment="Please confirm the new period.")
    c = _contract(db, owner)
    v1 = _ingest(db, tmp_path, c, ours, "ours.docx")
    v2 = _ingest(db, tmp_path, c, theirs, "theirs.docx")
    for legal in (True, False):
        row = negotiation.changes(db, c, v1, v2, legal_position=legal)["changes"][0]
        assert row["after"]["comments"] == [{"author": "Counsel",
                                             "text": "Please confirm the new period."}]
        assert "comments" not in row["before"]          # our 2's note: not this row
    # our note on clause 2 is on our side of no row; the client's other notes listed apart
    theirs2 = build(EDITED, p(r(OURS[1])), p(r(OURS[2])), p(r(OURS[3])),
                    comment_on=2, comment="A note on an unchanged clause.")
    v3 = _ingest(db, tmp_path, c, theirs2, "t.docx")
    listed = negotiation.changes(db, c, v1, v3, legal_position=False)
    assert "comments" not in listed["changes"][0]["after"]
    assert [(e["clause"]["number"], e["author"], e["text"])
            for e in listed["comments_elsewhere"]] == [
        ("3", "Counsel", "A note on an unchanged clause.")]


def test_our_own_comment_on_a_changed_clause_is_omitted_without_legal_position(
        db, owner, tmp_path):
    ours = build(*(p(r(t)) for t in OURS), comment_on=0, comment="Our own note.")
    c = _contract(db, owner)
    v1 = _ingest(db, tmp_path, c, ours, "ours.docx")
    v2 = _ingest(db, tmp_path, c, build(EDITED, *(p(r(t)) for t in OURS[1:])),
                 "theirs.docx")
    legal = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"][0]
    sales = negotiation.changes(db, c, v1, v2, legal_position=False)["changes"][0]
    assert legal["before"]["comments"] == [{"author": "Counsel", "text": "Our own note."}]
    assert "comments" not in sales["before"]


def _answer(db, contract, v1, v2, key: str, user) -> None:
    db.add(M.ComparisonChoice(
        left_version_id=v1.id, right_version_id=v2.id, row_key=key, choice="ours",
        version_number=1, decided_by=user.id, reason="kept"))
    db.flush()


def test_answered_keys_survive_and_an_old_reading_is_never_dropped(db, owner, tmp_path):
    """Ground rule 1: an answered row whose pairing is unchanged keeps its key and its
    answer; an answer stored under a key this reading no longer lists is shown on the
    row that holds its clause, "answered on an earlier reading" — never dropped."""
    c = _contract(db, owner)
    v1 = _ingest(db, tmp_path, c, plain(*OURS), "ours.docx")
    v2 = _ingest(db, tmp_path, c, build(EDITED, gone(OURS[1], 3), p(r(OURS[2])),
                                        p(r(OURS[3]))), "theirs.docx")
    first = negotiation.changes(db, c, v1, v2, legal_position=True)
    keys = [row["row_key"] for row in first["changes"]]
    _answer(db, c, v1, v2, keys[0], owner)
    # a key an earlier reading made: the same clauses, paired the other way
    modified = first["changes"][0]
    deleted = first["changes"][1]["before"]["evidence_ids"][0]
    stale = (f"{negotiation.KEY_PREFIX}MODIFIED|{deleted}"
             f"|{modified['after']['evidence_ids'][0]}")
    _answer(db, c, v1, v2, stale, owner)
    again = negotiation.changes(db, c, v1, v2, legal_position=True)
    assert [row["row_key"] for row in again["changes"]] == keys        # keys survive
    assert again["changes"][0]["answer"]["answer"] == "keep_ours"
    held = again["changes"][0]["earlier_answers"]
    assert [(e["row_key"], e["answer"]) for e in held] == [(stale, "keep_ours")]
    assert "answered_earlier" not in again                 # every one found its row


# ------------------------------------------------- one count (AM-291) and F5
def test_every_surface_says_the_same_two_numbers_and_never_sign_after(api, db, owner,
                                                                     tmp_path):
    """The header, the To-do (the Legal queue reads it), the Changes tab, the
    recommendation and the report lead with the same two numbers: change rows
    (`deal_counts`) and points (`review_progress.to_decide`). While a change waits for
    Legal the recommendation never says "Sign after"; the tracked edits are a detail
    line, never "N changes to M clauses"."""
    import re

    from legalmind.domain import enums as E
    from legalmind.workflow.review_progress import review_progress
    from tests.test_negotiation import _review
    from tests.test_todo import _holder
    from tests.test_version_comparison import V1

    c = _contract(db, owner)
    _ingest(db, tmp_path, c, plain(*OURS), "ours.docx")
    v2 = _ingest(db, tmp_path, c, build(EDITED, gone(OURS[1], 3), p(r(OURS[2])),
                                        p(r(OURS[3]))), "theirs.docx")
    review = _review(db, v2, [(0, E.FindingClassification.DEVIATION,
                               E.RuleOutcome.UNACCEPTABLE)])
    review.status = E.ReviewStatus.LEGAL_REVIEW
    lawyer = _holder(db, "COUNT")
    db.add(M.ReviewAssignment(review_id=review.id, user_id=lawyer.id,
                              assigned_by=owner.id))
    db.flush()
    from tests.conftest import sign_in
    sign_in(api, db, lawyer)

    def get(path):
        got = api.get(f"{V1}{path}")
        assert got.status_code == 200, got.text
        return got.json()["data"]

    counts = get(f"/contracts/{c.id}")["counts"]
    to_decide = review_progress(db, review)["to_decide"]
    changes = get(f"/contracts/{c.id}/changes")
    [task] = [i for i in get("/todo")["items"] if i["kind"] == "decide"]
    assert (counts["changes_total"], to_decide) == (2, 1)        # non-trivial numbers
    assert counts["changes_total"] == len(changes["changes"]) == changes["summary"]["total"]
    assert counts["changes_left_for_me"] == task["changes"] == counts["changes_left_legal"]
    assert counts["points_open"] == counts["points_for_me"] == task["count"] == to_decide
    # one lawyer queue: the To-do leads with the changes, as the header's one primary
    assert task["sentence"] == "2 changes to answer, then 1 point to decide."
    said = get(f"/reviews/{review.id}/angles")["recommendation"]
    assert said.startswith(f"Not ready to sign: {counts['changes_left_legal']} of the "
                           "client's changes wait for Legal")
    assert f"{to_decide} point" in said and "Sign after" not in said
    report = " ".join(b["text"] for b in get(f"/reviews/{review.id}/report/document"))
    assert f"The client made {counts['changes_total']} changes" in report
    # the next step names both nouns: the changes waiting for Legal and the points
    assert "answers the 2 changes from the client and decides the 1 open point." in report
    assert not re.search(r"changes to \d+ clauses", report + said)


def test_the_recommendation_never_says_sign_after_while_changes_wait_for_legal():
    """F5: ``legal_open`` > 0 — never "Sign after", whatever the points say; 0 (no
    round, or Ask's temporary review) — AM-160's line exactly as before. A change Legal
    answered "Ask the client" is not open for Legal (AM-411 r1): with nothing else open
    the line is the one before, which may offer "Sign after"."""
    from legalmind.api import angles as A
    none = {"structural": [], "additional": []}

    def items(*actions):
        return [{"action": a} for a in actions]
    for points in ([], items(A.SEND_WORDING), items(A.SEND_WORDING, A.READ_IT),
                   items(A.MUST_CHANGE), items(A.ACCEPT_FAVOURABLE)):
        for open_ in (1, 55):
            said = A.recommendation(points, none, 3, legal_open=open_)
            assert said and "Sign after" not in said and said.startswith(
                f"Not ready to sign: {open_} of the client's changes wait")
    assert A.recommendation(items(A.SEND_WORDING, A.READ_IT), none, 2, legal_open=55) == (
        "Not ready to sign: 55 of the client's changes wait for Legal, and 2 points are "
        "still to decide.")
    assert A.recommendation([], none, 2, decided=3, legal_open=1) == (
        "Not ready to sign: 1 of the client's changes waits for Legal.")
    # AM-411: the rows asked of the client are answered, so legal_open is 0 — unchanged
    assert A.recommendation(items(A.SEND_WORDING), none, 1, legal_open=0) == \
        A.recommendation(items(A.SEND_WORDING), none, 1) == (
        "Sign after 1 change to ask them for. Legal decides.")
    assert A.recommendation([], none, 0, legal_open=5) is None   # nothing measured


def test_a_change_asked_of_the_client_is_not_waiting_for_legal(api, db, owner, tmp_path,
                                                               published):
    """AM-411 r1: Legal answered "Ask the client" — that change is answered, so it is not
    in `changes_left_legal` and the recommendation does not count it as waiting."""
    from tests.test_ab214_ask_client import _asked
    from tests.test_version_comparison import V1
    c, theirs, review, lawyer = _asked(api, db, owner, tmp_path)
    counts = api.get(f"{V1}/contracts/{c.id}").json()["data"]["counts"]
    assert counts["changes_total"] >= 1 and counts["changes_left_legal"] == 0
    said = api.get(f"{V1}/reviews/{review.id}/angles").json()["data"]["recommendation"]
    assert "client's changes wait" not in (said or "")


# ------------------------------------- R2 is never weaker than before (verification 2026-11-19)
_A = "1. Fees are payable within 30 days of invoice."
_B = "2. This Agreement is governed by the laws of India."
_C = "3. Notices shall be given in writing to the registered office."
_D = "4. The Term is one year from the Effective Date."
_SAME = "This clause is intentionally left blank."
_PAY = "2. Payment is due monthly. Interest accrues on late sums."
_CAP = "2. Liability is capped at the fees paid. The cap does not apply to fraud."
_IND = "3. Each party indemnifies the other for third-party claims."
_TRACKED_A = p(r("1. Fees are payable within "), d("30", 1), i("60", 2), r(" days of invoice."))


def _docs(*blocks):
    return build(*(b if b.startswith("<w:") else p(r(b)) for b in blocks))


_NUM = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr>'


def auto(*runs: str) -> str:
    """A paragraph numbered by Word's automatic numbering (no number in its text)."""
    return f"<w:p {W}><w:pPr>{_NUM}</w:pPr>{''.join(runs)}</w:p>"


def auto_gone(text: str, n: int) -> str:
    """An automatically numbered paragraph deleted whole."""
    return (f'<w:p {W}><w:pPr>{_NUM}<w:rPr><w:del w:id="{n + 1}" {_AT}/></w:rPr></w:pPr>'
            f"{d(text, n)}</w:p>")


_FIRST, _SECOND = "The cap is the fees paid.", "The cap does not apply to fraud."
_THIRD, _LAST = "Each party indemnifies the other.", "The term is one year."
_TRACKED_FIRST = r("The cap is the ") + d("fees", 1) + i("charges", 2) + r(" paid.")


#: (case, ours, theirs, how many untracked rows: an int is exact, "+" is at least one)
UNMARKED_CASES = [
    ("every change marked", [_A, _B, _C, _D],
     [_TRACKED_A, _B, p(r("3. Notices shall be given in writing"), i(" by email", 3),
                        r(" to the registered office.")), _D,
      p(i("5. New clause inserted under a mark.", 4))], 0),
    ("a repeated sentence edited silently", [_A, "2. Payment is due monthly. " + _SAME, _C,
                                             "4. " + _SAME],
     [_A, "2. Payment is due monthly. This clause is intentionally left open.", _C,
      "4. " + _SAME], "+"),
    ("one of two identical clauses deleted silently", [_A, "2. " + _SAME, "3. " + _SAME, _D],
     [_A, "3. " + _SAME, _D], "+"),
    ("an identical clause inserted silently", [_A, "2. " + _SAME, _D],
     [_A, "2. " + _SAME, "3. " + _SAME, _D], "+"),
    ("a figure changed silently", [_A, _B, _C, _D],
     ["1. Fees are payable within 60 days of invoice.", _B, _C, _D], 1),
    ("a figure after an abbreviation, beside a tracked edit",
     [_A, "2. The setup fee is Rs. 99.50. It is payable once.", _C, _D],
     [_A, p(r("2. The setup fee is Rs. 199.50. It is payable "), d("once", 1), i("twice", 2),
            r(".")), _C, _D], "+"),
    ("a figure after an abbreviation", [_A, "2. The setup fee is Rs. 99.50. It is payable once.",
                                        _C, _D],
     [_A, "2. The setup fee is Rs. 199.50. It is payable once.", _C, _D], "+"),
    ("a cross-reference after an abbreviation",
     [_A, "2. Liability is capped as set out in Sec. 4.2. Nothing else applies.", _C, _D],
     [_A, "2. Liability is capped as set out in Sec. 9.2. Nothing else applies.", _C, _D], "+"),
    ("two sentences swapped", [_A, _PAY, _C, _D],
     [_A, "2. Interest accrues on late sums. Payment is due monthly.", _C, _D], "+"),
    ("two clauses swapped", [_A, _B, _C, _D], [_A, _C, _B, _D], "+"),
    ("a silent edit inside a tracked clause", [_A, _B, _C, _D],
     [p(r("1. Fees are payable within "), d("30", 1), i("60", 2), r(" days of each invoice.")),
      _B, _C, _D], 1),
    ("a sentence deleted silently", [_A, _PAY, _C, _D], [_A, "2. Payment is due monthly.", _C, _D],
     "+"),
    ("a clause deleted silently", [_A, _B, _C, _D], [_A, _C, _D], "+"),
    ("a sentence deleted silently inside a tracked clause", [_A, _PAY, _C, _D],
     [_A, p(r("2. Payment is due "), d("monthly", 1), i("quarterly", 2), r(".")), _C, _D], "+"),
    ("a sentence inserted silently", [_A, _B, _C, _D],
     [_A, _B[:-1] + ". Courts at Mumbai have exclusive jurisdiction.", _C, _D], "+"),
    ("a clause inserted silently", [_A, _B, _C, _D],
     [_A, _B, "3. The Customer waives all claims.", "4." + _C[2:], "5." + _D[2:]], "+"),
    ("the negative control", [_A, _B, _C, _D],
     [_TRACKED_A, _B, _C, "4. The Term is two years from the Effective Date."], 1),
    ("a sentence moved silently to the next clause", [_A, _CAP, _IND, _D],
     [_A, "2. Liability is capped at the fees paid.",
      "3. The cap does not apply to fraud. Each party indemnifies the other for third-party "
      "claims.", _D], "+"),
    ("the same move beside a tracked edit", [_A, _CAP, _IND, _D],
     [_TRACKED_A, "2. Liability is capped at the fees paid.",
      "3. The cap does not apply to fraud. Each party indemnifies the other for third-party "
      "claims.", _D], "+"),
    # round 2 (verification 2026-11-19): regrouping under Word's automatic numbering, a
    # deletion equal to a line elsewhere, a symbol-font glyph, a zero-width mark in a word
    ("a paragraph regrouped to the next clause under automatic numbering",
     [auto(r(_FIRST)), p(r(_SECOND)), auto(r(_THIRD)), auto(r(_LAST))],
     [auto(_TRACKED_FIRST), auto(r(_SECOND)), p(r(_THIRD)), auto(r(_LAST))], "+"),
    ("a paragraph regrouped to the next clause with typed numbers",
     ["1. " + _FIRST, _SECOND, "2. " + _THIRD, "3. " + _LAST],
     [p(r("1. ") + _TRACKED_FIRST), "2. " + _SECOND, _THIRD, "3. " + _LAST], "+"),
    ("a line deleted silently that equals a clause deleted whole under a mark",
     [auto(r("Fees are due monthly.")), p(r("Not used.")),
      p(r("Interest accrues on late sums.")), auto(r("Not used.")), auto(r(_LAST))],
     [auto(r("Fees are due monthly.")), p(r("Interest accrues on late sums.")),
      auto_gone("Not used.", 5), auto(r(_LAST))], "+"),
    ("a last line deleted silently that equals the next clause deleted whole",
     ["1. Fees are due monthly.", "Not used.", "2. Not used.", "3. " + _LAST],
     ["1. Fees are due monthly.", gone("2. Not used.", 5), "3. " + _LAST], "+"),
    ("a silent edit in a regrouped window beside a tracked edit",
     [auto(r(_FIRST)), p(r(_SECOND)), auto(r(_THIRD)), auto(r(_LAST))],
     [auto(_TRACKED_FIRST), auto(r("The cap does not apply to wilful default.")),
      p(r(_THIRD)), auto(r(_LAST))], "+"),
    ("a symbol-font glyph changed silently beside a tracked edit",
     [_A, "2. Auto-renewal: \uf0a8 applies.", "3. " + _LAST],
     [_TRACKED_A, p(r("2. Auto-renewal: \uf0fe applies."), i(" Yes", 3)), "3. " + _LAST],
     "+"),
    ("a zero-width mark put inside a word", ["1. The Supplier shall not be liable.", "2. " + _LAST],
     [p(r("1. The Supplier shall n\u200bot be liable."), i(" Ever.", 1)), "2. " + _LAST], "+"),
    ("half a clause moved into the next clause's first line",
     ["1. " + _FIRST + " " + _SECOND, "2. " + _THIRD],
     [p(r("1. " + _FIRST), i(" Tracked.", 1)), _SECOND + " 2. " + _THIRD], "+"),
]


@pytest.mark.parametrize(("case", "ours", "theirs", "expected"), UNMARKED_CASES,
                         ids=[c[0] for c in UNMARKED_CASES])
def test_a_silent_edit_is_never_hidden(db, owner, tmp_path, case, ours, theirs, expected):
    """Every edit made without a mark is flagged on a row, and a fully marked copy flags
    none — a figure after "Rs." or a cross-reference after "Sec.", a repeated clause, a
    sentence moved across a clause boundary included. Each case reads the same or
    stronger than the reading before batch 1."""
    listed = _listed(db, owner, tmp_path, _docs(*ours), _docs(*theirs))
    flagged = sum(c["untracked"] for c in listed["changes"])
    assert flagged >= 1 if expected == "+" else flagged == expected, _rows(listed)
    # never incoherent: a row whose text differs is marked, flagged, or both
    assert all(c["tracked"] or c["untracked"] for c in listed["changes"]), _rows(listed)


# ------------------------------------- the reading changed; routes and answers did not
def _routing_world(db, owner, tmp_path, monkeypatch):
    """Pairs that exercise every route and effect, Priyen's automatic acceptance and a
    tracked returned copy — each listed with what the snapshot below pins."""
    from legalmind.domain import enums as E
    from tests.test_negotiation import _pair, _review
    from tests.test_version_comparison import _version
    monkeypatch.setattr(negotiation, "auto_rule", lambda db, review: True)
    C, R = E.FindingClassification, E.RuleOutcome
    out = []
    for before, after, findings in (
            ("9. Liability is capped.", "9. Liability is uncapped.", []),
            ("9. Liability is capped, always.", "9. Liability is capped; always",
             [(0, C.MATCH, R.ACCEPTABLE)]),
            ("9. Liability is capped.", "9. Liability is capped at fees.",
             [(0, C.MATCH, R.ACCEPTABLE)]),
            ("9. Liability is capped.", "9. Liability is capped lower.",
             [(0, C.DEVIATION, R.ACCEPTABLE)]),
            ("9. Liability is capped.", "9. Liability is capped higher.",
             [(0, C.DEVIATION, R.UNACCEPTABLE)]),
            ("9. The Customer\u2019s fees \u2014 monthly.", "9. The Customer's fees - monthly.",
             [])):
        c = _contract(db, owner)
        v1, v2 = _pair(db, c, before, after)
        _review(db, v2, findings)
        out.append((c, v1, v2))
    c = _contract(db, owner)
    v1 = _version(db, c, 1, [("1", "Fees", "1. Fees are due monthly."),
                             ("2", "Law", "2. Governed by Indian law.")])
    v2 = _version(db, c, 2, [("1", "Scope", "1. The Services are hosting."),
                             ("2", "Fees", "2. Fees are due monthly."),
                             ("3", "Law", "3. Governed by Indian law."),
                             (None, None, "SCHEDULE A\nPrice list")])
    out.append((c, v1, v2))
    c = _contract(db, owner)
    out.append((c, _ingest(db, tmp_path, c, plain(*OURS), "ours.docx"),
                _ingest(db, tmp_path, c, build(EDITED, gone(OURS[1], 3), p(r(OURS[2])),
                                               p(r(OURS[3]))), "theirs.docx")))
    return out


#: recorded with origin/main 44290f60's `negotiation.changes` on the pairs above:
#: (kind, clause, route, route reason, effect, measured, accepted automatically) per row,
#: and the list's own count of rows accepted automatically
ROUTES_BEFORE_BATCH_1 = [
    [[
        ['MODIFIED', '9', 'holder', 'NO_STANDARD_MEASURES_IT', 'NEGATIVE', 'NOT_MEASURED', False],
    ], 0],
    [[
        ['MODIFIED', '9', 'owner', 'STILL_MATCHES_OUR_STANDARD', 'NEUTRAL', None, True],
    ], 1],
    [[
        ['MODIFIED', '9', 'holder', 'MEASURED_BY_A_STANDARD', 'NEGATIVE', 'REVIEW', False],
    ], 0],
    [[
        ['MODIFIED', '9', 'favour', 'IN_OUR_FAVOUR', 'POSITIVE', None, True],
    ], 1],
    [[
        ['MODIFIED', '9', 'holder', 'MEASURED_BY_A_STANDARD', 'NEGATIVE', 'WORSE', False],
    ], 0],
    [[
        ['MODIFIED', '9', 'owner', 'FORMATTING_ONLY', 'NEUTRAL', None, True],
    ], 1],
    [[
        ['ADDED', '1', 'holder', 'NO_STANDARD_MEASURES_IT', 'NEGATIVE', 'NOT_MEASURED', False],
        ['NEW_ANNEXURE', None, 'holder', 'NO_STANDARD_MEASURES_IT', 'NEGATIVE', 'NOT_MEASURED', False],
    ], 0],
    [[
        ['MODIFIED', '1', 'holder', 'NO_STANDARD_MEASURES_IT', 'NEGATIVE', 'NOT_MEASURED', False],
        ['DELETED', '2', 'holder', 'NO_STANDARD_MEASURES_IT', 'NEGATIVE', 'NOT_MEASURED', False],
    ], 0],
]


def _routes(listed) -> list:
    return [[[c["kind"], c["clause"]["number"], c["route"], c["route_reason"],
              c["effect_for_us"], c.get("measured"), bool((c["answer"] or {}).get("auto"))]
             for c in listed["changes"]], listed["summary"]["auto_accepted"]]


def test_routes_effects_and_automatic_answers_are_unchanged(db, owner, tmp_path, monkeypatch):
    """Batch 1 changed how a change is READ (untracked, pairing, comments), never where it
    goes: route, effect and Priyen's automatic acceptance are what they were."""
    got = [_routes(negotiation.changes(db, c, v1, v2, legal_position=True))
           for c, v1, v2 in _routing_world(db, owner, tmp_path, monkeypatch)]
    assert got == ROUTES_BEFORE_BATCH_1


def test_a_long_marked_up_copy_is_read_quickly(db, owner, tmp_path):
    """A generous guard, not a benchmark: 150 clauses, every fifth edited under a mark,
    every seventh deleted whole — the change list in well under the bound on CI's slowest
    runner (0.08 s locally on 2026-11-19, so the 10 s bound catches a blow-up, never a drift). The real-file timing is the report's."""
    import time
    clauses = [f"{n}. Clause {n} sets out obligation number {n} of the parties in plain "
               f"words, with its own figure of {n * 3} days." for n in range(1, 151)]
    blocks = []
    for n, text in enumerate(clauses, start=1):
        if n % 7 == 0:
            blocks.append(gone(text, 1000 + n * 2))
        elif n % 5 == 0:
            head, tail = text.split(" days", 1)
            blocks.append(p(r(head.rsplit(" ", 1)[0] + " "), d(head.rsplit(" ", 1)[1], 3000 + n),
                            i(str(n * 4), 4000 + n), r(" days" + tail)))
        else:
            blocks.append(p(r(text)))
    c = _contract(db, owner)
    v1 = _ingest(db, tmp_path, c, plain(*clauses), "ours.docx")
    v2 = _ingest(db, tmp_path, c, build(*blocks), "theirs.docx")
    started = time.perf_counter()
    listed = negotiation.changes(db, c, v1, v2, legal_position=True)
    took = time.perf_counter() - started
    assert listed["summary"]["untracked"] == 0 and listed["summary"]["total"] > 40
    assert took < 10.0, took
