"""E2E fix batch C (AB-211) and the A+B leftovers — every document synthetic, no client.

* AM-395: the wording to send back is our own clause as we sent it; a holder's answer
  on a measured change records their Legal Decision once (sales records none).
* AM-399: "Ask the client" on any change — the question goes into our reply as a Word
  comment, the client's text stays, no Legal Decision on an unmeasured change.
* 6d: the review table carries Effect for us and Source.
* AM-398 r2: one stage for every reader; Legal's queue lists a deal sent to them.
* AM-393: signing readiness reads the derived stage, never its own outcome list.
"""

from __future__ import annotations

import io
import uuid
import zipfile

from sqlalchemy import select

from legalmind.api import angles
from legalmind.api.routers import execution
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.workflow import contract_outcome
from tests.conftest import sign_in
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _first,
    _ingest,
    _review,
    _url,
    owner,
)
from tests.test_negotiation_wording import (  # noqa: F401 — `published` is a fixture
    OURS,
    REPLY,
    _lawyer,
    _measured,
    _send,
    published,
)
from tests.test_version_comparison import V1

QUESTION = "Which data centre do you mean in this clause?"


def _decisions(db, change):
    ids = [uuid.UUID(e) for f in change["review"]["after"] for e in f["evaluation_ids"]]
    return db.scalars(select(M.LegalDecision).where(
        M.LegalDecision.evaluation_id.in_(ids))).all()


# ---------------------------------------------------------------- AM-395
def test_the_wording_to_send_back_is_our_own_clause(api, db, owner, tmp_path):
    """C1 (a): the client changed clause 9 — the card quotes OUR clause 9 as we sent it,
    labelled with its source, never the Constitution's generic paragraph."""
    _, _, review = _measured(db, tmp_path, owner)
    for ev in db.scalars(select(M.EvaluationEvidence).join(
            M.Evaluation, M.Evaluation.id == M.EvaluationEvidence.evaluation_id)
            .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
            .where(M.Finding.review_id == review.id)):      # the roll-up, as evaluated
        db.add(M.FindingEvidence(finding_id=db.get(M.Evaluation, ev.evaluation_id)
                                 .finding_id, evidence_id=ev.evidence_id,
                                 relationship_type=ev.relationship_type))
    db.flush()
    got = angles.review_angles(db, review, legal_position=True)
    proposal = next(iter(got["counter_proposals"].values()))
    assert proposal["kind"] == "OUR_CLAUSE"
    assert proposal["text"] == OURS
    assert "version 1" in proposal["label"] and "clause 9" in proposal["label"]
    # a reader without the legal position gets the action, never the wording (SEC-07)
    assert angles.review_angles(db, review, legal_position=False)["counter_proposals"] == {}


def test_a_lawyers_answer_is_their_decision_once_and_sales_records_none(
        api, db, owner, tmp_path):
    """C3: keep ours by the holder → REQUIRE_COMPANY_STANDARD on the clause's point,
    with the answer's reason, recorded once; the deal owner's keep ours records none."""
    c, _, review = _measured(db, tmp_path, owner)
    change = _changes(api, c)["changes"][0]
    assert api.post(_url(c, change["row_key"]), json=_first("keep_ours")).status_code == 201
    assert _decisions(db, change) == []                     # sales: no Legal Decision
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    change = _changes(api, c)["changes"][0]
    r = api.post(_url(c, change["row_key"]), json={
        "answer": "keep_ours", "reason": "our cap stands",
        "expected_version": change["answer"]["version_number"]})
    assert r.status_code == 201, r.text
    made = _decisions(db, change)
    assert [(d.decision_type, d.justification, d.decided_by) for d in made] == [
        (E.DecisionType.REQUIRE_COMPANY_STANDARD, "our cap stands", lawyer.id)]
    # answering again the same way never records it twice
    change = _changes(api, c)["changes"][0]
    assert api.post(_url(c, change["row_key"]), json={
        "answer": "keep_ours", "reason": "still ours",
        "expected_version": change["answer"]["version_number"]}).status_code == 201
    assert len(_decisions(db, change)) == 1


# ---------------------------------------------------------------- AM-399
def test_ask_the_client_on_an_unmeasured_change(api, db, owner, tmp_path):
    """6e: no standard measures clause 9 here — Legal still asks; the reply keeps the
    client's words with our question as a comment; no Legal Decision; the suggestion is
    On hold."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx("9. Liability is capped at 3 months of fees."),
                     "theirs.docx")
    review = _review(db, theirs, [])
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    change = _changes(api, c)["changes"][0]
    assert "ask_client" in change["offers"]
    assert api.post(_url(c, change["row_key"]), json=_first("ask_client")).status_code \
        == 422                                              # the question is required
    r = api.post(_url(c, change["row_key"]), json=_first("ask_client",
                                                         client_note=QUESTION))
    assert r.status_code == 201, r.text
    stored = db.scalars(select(M.ComparisonChoice).where(
        M.ComparisonChoice.row_key == change["row_key"])).one()
    assert (stored.choice, stored.client_note) == ("ask", QUESTION)
    assert db.scalars(select(M.LegalDecision)).all() == []
    assert contract_outcome.suggest(db, review) is E.ContractOutcome.SIGN_WITH_CHANGES  # AM-405
    prepared = api.post(REPLY.format(c.id))
    assert prepared.status_code == 201, prepared.text
    reply = api.get(f"{V1}{prepared.json()['data']['downloads']['docx']}")
    with zipfile.ZipFile(io.BytesIO(reply.content)) as z:
        document = z.read("word/document.xml").decode()
        comments = z.read("word/comments.xml").decode()
    assert QUESTION in comments
    assert "<w:del " not in document                 # their words stay as they wrote them


# ---------------------------------------------------------------- 6d
def test_the_review_table_has_effect_for_us_and_source(api, db, owner, tmp_path):
    c, _, _ = _measured(db, tmp_path, owner)
    table = api.get(f"{V1}/contracts/{c.id}/changes/review-table").json()["data"]
    assert table["head"] == ["Sr", "Clause", "Original", "Requested change",
                             "Effect for us", "Source", "Updated clause", "Recommendation"]
    row = table["rows"][0]
    assert row[4] in ("Bad for us", "Legal checks") and row[5].startswith(
        "The client changed this")
    exported = api.post(f"{V1}/contracts/{c.id}/changes/review-table/export")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        assert "Effect for us" in z.read("word/document.xml").decode()


# ---------------------------------------------------------------- AM-398 r2 / 6c
def test_every_reader_gets_one_stage_and_legal_lists_what_was_sent(
        api, db, owner, tmp_path):
    """The deal owner (no `review.view`) and the lawyer read the same stage; a deal sent
    to Legal with nothing but an unmeasured change is in the lawyer's To-do."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx("9. Liability is capped at 3 months of fees."),
                     "theirs.docx")
    review = _review(db, theirs, [])
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sales_stage = api.get(f"{V1}/contracts/{c.id}").json()["data"]["negotiation_stage"]
    sign_in(api, db, lawyer)
    legal_stage = api.get(f"{V1}/contracts/{c.id}").json()["data"]["negotiation_stage"]
    assert sales_stage["stage"] == legal_stage["stage"] == "INTERNAL_REVIEW"
    todo = api.get(f"{V1}/todo").json()["data"]["items"]
    assert [i["kind"] for i in todo if i["contract_id"] == str(c.id)] == ["decide"]


# ---------------------------------------------------------------- AM-393 leftover
def test_mark_signed_reads_the_derived_stage():
    facts = {"outcome": "SIGN_WITH_CHANGES", "stage": "READY_TO_SEND", "open_points": 0}
    codes = [b["code"] for b in execution.blockers(facts, None, None, None)]
    assert "REPLY_NOT_AGREED" in codes
    ready = {**facts, "stage": "READY_TO_SIGN"}
    assert "REPLY_NOT_AGREED" not in [
        b["code"] for b in execution.blockers(ready, None, None, None)]
    assert {"READY_TO_SIGN", "FINAL"} == execution._READY


def test_an_msa_point_never_offers_constitution_wording(monkeypatch):
    """C1: an MSA standard aligned to our MSA never falls back to the Constitution's
    drafting notes (they may say twenty-one days or Pune)."""
    assert angles._msa_aligned("PAYMENT-PERIOD-MSA-001")
    assert not angles._msa_aligned("EARLY-TERM-RESTRICTION-MSA-001")
    quote = angles._msa_quote("DISPUTE-WINDOW-MSA-001")
    assert quote and quote["kind"] == "MSA_QUOTE" and "5 working days" in quote["text"]
    assert "Pune" not in quote["text"] and "twenty-one" not in quote["text"]


def test_a_changed_point_is_placed_at_the_clause_the_client_changed():
    """AB-213 D13: a point reading 19.1 and 19.4, the client changed 19.4 → 19.4."""
    from types import SimpleNamespace as NS
    clauses = [NS(evidence_id="a", section_number="19.1"),
               NS(evidence_id="b", section_number="19.4")]
    assert angles.changed_passage(["a", "b"], {"b"}, clauses) == "b"
    assert angles.changed_passage(["a"], {"b"}, clauses) is None
