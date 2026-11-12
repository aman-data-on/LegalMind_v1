"""CLM slice S2 follow-up (AB-152, 2026-11-03): decisions carried onto our reply, a
deleted measured clause answered by a holder, and "Keep ours" on the client's paper.

* Carry-forward (`AM-284` r2, `AM-293` r1): our reply's own Review takes the effective
  decisions already made on the client's version for the same requirement and the same
  wording — an accepted deviation, or the wording a holder approved — so the gate opens;
  wording changed after approval is never carried, and the gate stays shut.
* `AM-281`: a measured clause of ours the client deleted carries no Evaluation on their
  side — a holder's answer, reason required, audited — never a 409.
* Paper first: "Keep ours" is our standard clause where one anchors the row, else it is
  not offered and is refused (409 NOTHING_OF_OURS).

Every document and clause here is synthetic structural text (rule 21).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from legalmind.analysis.negotiation import reply_open_points
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.workflow.decisions import carry_decisions
from tests.conftest import make_evaluation, make_finding, sign_in
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
    THEIRS,
    WORDING,
    _lawyer,
    _measured,
    _publish_clause,
    _send,
    _wording,
    published,
)
from tests.test_version_comparison import V1


def _point(db, review, rv_id, version):
    """A DEVIATION on ``review`` for requirement version ``rv_id``, reading every
    evidence row of ``version`` — the reply's own analysis, made by hand."""
    finding = make_finding(db, review, db.get(M.RequirementVersion, rv_id))
    ev = make_evaluation(db, finding, classification=E.FindingClassification.DEVIATION,
                         rule_outcome=E.RuleOutcome.UNACCEPTABLE)
    for e in db.scalars(select(M.DocumentEvidence.id).where(
            M.DocumentEvidence.document_version_id == version.id)):
        db.add(M.EvaluationEvidence(evaluation_id=ev.id, evidence_id=e,
                                    relationship_type=E.EvidenceRelationshipType.PRIMARY))
    db.flush()
    return finding, ev


def _theirs_rv(db, review):
    return db.scalars(select(M.Finding.requirement_version_id)
                      .where(M.Finding.review_id == review.id)).one()


def _content(api, version_id):
    return api.get(f"{V1}/document-versions/{version_id}/content")


def _prepared(api, db, c):
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    return (db.get(M.DocumentVersion, uuid.UUID(body["document_version"]["id"])),
            db.get(M.Review, uuid.UUID(body["review_id"])))


# ------------------------------------------------------------------ carry-forward
def test_an_accepted_client_deviation_is_carried_and_the_gate_opens(
        api, db, owner, tmp_path):
    c, theirs, review = _measured(db, tmp_path, owner)
    lawyer = _lawyer(db)
    change = _changes(api, c)["changes"][0]
    ev_id = uuid.UUID(change["review"]["after"][0]["evaluation_ids"][0])
    original = M.LegalDecision(finding_id=db.get(M.Evaluation, ev_id).finding_id,
                               evaluation_id=ev_id,
                               decision_type=E.DecisionType.ACCEPT_DEVIATION,
                               justification="accepted for this deal",
                               decided_by=lawyer.id, version_number=1)
    db.add(original)
    db.flush()
    assert api.post(_url(c, change["row_key"]),
                    json=_first("accept_theirs")).status_code == 201
    reply, reply_review = _prepared(api, db, c)
    finding, ev = _point(db, reply_review, _theirs_rv(db, review), reply)
    assert _content(api, reply.id).status_code == 409             # undecided: blocked

    assert carry_decisions(db, reply_review) == 1
    carried = db.scalars(select(M.LegalDecision).where(
        M.LegalDecision.evaluation_id == ev.id)).one()
    assert carried.decision_type is E.DecisionType.ACCEPT_DEVIATION
    assert carried.decided_by == lawyer.id
    assert carried.justification.startswith(
        f"Carried from version {theirs.version_number} — same wording")
    event = db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.DECISION_CARRIED)).one()
    assert event.after_state["carried_from_decision_id"] == str(original.id)
    assert finding.status is E.FindingStatus.RESOLVED
    # never ACCEPTABLE: the engine's outcome stands, a person's decision answers it
    assert ev.rule_outcome is E.RuleOutcome.UNACCEPTABLE
    assert reply_open_points(db, reply) is None
    assert _content(api, reply.id).status_code == 200
    assert carry_decisions(db, reply_review) == 0                 # idempotent


def test_approved_wording_is_carried_onto_the_reply(api, db, owner, tmp_path):
    c, _, review = _measured(db, tmp_path, owner)
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    assert _wording(api, c, _changes(api, c)["changes"][0]).status_code == 201
    reply, reply_review = _prepared(api, db, c)
    _, ev = _point(db, reply_review, _theirs_rv(db, review), reply)
    assert carry_decisions(db, reply_review) == 1
    carried = db.scalars(select(M.LegalDecision).where(
        M.LegalDecision.evaluation_id == ev.id)).one()
    assert carried.decision_type is E.DecisionType.APPROVE_CUSTOMIZATION
    assert carried.decided_by == lawyer.id
    assert _content(api, reply.id).status_code == 200


def test_wording_changed_after_approval_is_not_carried(api, db, owner, tmp_path):
    c, theirs, review = _measured(db, tmp_path, owner)
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    assert _wording(api, c, _changes(api, c)["changes"][0]).status_code == 201
    # our next version reads other words than the ones approved
    reply = _ingest(db, tmp_path, c, _docx(WORDING.replace("12", "24")), "reply.docx")
    reply.doc_metadata = {"version_role": "COMPANY_DRAFT", "reply_to": str(theirs.id)}
    db.flush()
    reply_review = _review(db, reply, [])
    _point(db, reply_review, _theirs_rv(db, review), reply)
    assert carry_decisions(db, reply_review) == 0
    r = _content(api, reply.id)
    assert r.status_code == 409 and r.json()["error"]["reason"] == "UNDECIDED_POINTS"


# --------------------------------------------- AM-281: a deleted measured clause
def test_a_holder_answers_a_measured_clause_the_client_deleted(api, db, owner, tmp_path):
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(OURS, "10. Notices by email."), "ours.docx")
    _ingest(db, tmp_path, c, _docx("10. Notices by email."), "theirs.docx")
    review = _review(db, ours, [(0, E.FindingClassification.MATCH,
                                 E.RuleOutcome.ACCEPTABLE)])
    change = _changes(api, c)["changes"][0]
    assert change["kind"] == "DELETED" and change["unmeasured"] is False
    r = api.post(_url(c, change["row_key"]), json=_first("accept_theirs"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "LEGAL_DECISION_REQUIRED"

    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    assert api.post(_url(c, change["row_key"]),
                    json=_first("accept_theirs")).status_code == 422   # no reason
    r = api.post(_url(c, change["row_key"]),
                 json=_first("accept_theirs", reason="the clause is not needed here"))
    assert r.status_code == 201, r.text
    assert _changes(api, c)["changes"][0]["holder_accepted"] is True
    r = _wording(api, c, _changes(api, c)["changes"][0])          # never 409 now
    assert r.status_code == 201, r.text
    assert r.json()["data"]["waiting_for_approval"] is False
    assert db.scalar(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.NEGOTIATION_HOLDER_ANSWERED)) == 2
    assert db.scalar(select(func.count()).select_from(M.LegalDecision)) == 0


# ------------------------------------------------- paper first: "Keep ours"
def test_keep_ours_on_the_clients_paper_is_our_standard_or_not_offered(
        api, db, owner, tmp_path):
    c = _contract(db, owner)
    paper = _ingest(db, tmp_path, c, _docx(THEIRS), "theirs.docx")
    paper.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    db.flush()
    _review(db, paper, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    row = _changes(api, c)["changes"][0]
    assert row["offers"] == ["accept_theirs", "write_wording"]
    r = api.post(_url(c, row["row_key"]), json=_first("keep_ours"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "NOTHING_OF_OURS"
    assert "no standard clause" in r.json()["error"]["message"]

    cv = _publish_clause(db, owner, row["review"]["after"][0]["requirement_code"],
                         "9. Placeholder standard clause text.")
    row = _changes(api, c)["changes"][0]
    assert row["offers"] == ["keep_ours", "accept_theirs", "write_wording"]
    r = api.post(_url(c, row["row_key"]), json=_first("keep_ours"))
    assert r.status_code == 201, r.text
    answer = r.json()["data"]["answer"]
    assert (answer["answer"], answer["clause_version_id"]) == ("use_standard", str(cv.id))


def test_the_reply_analysis_carries_the_decisions(api, db, owner, tmp_path, monkeypatch):
    """The hook: analysing our reply's Review runs the carry-forward before its
    lifecycle is chosen, so a carried point never holds the Review in Legal review."""
    from legalmind.analysis import service

    seen: list[uuid.UUID] = []
    monkeypatch.setattr(service, "carry_decisions",
                        lambda db, review, **_: seen.append(review.id) or 0)
    c, _, _ = _measured(db, tmp_path, owner)
    assert api.post(_url(c, _changes(api, c)["changes"][0]["row_key"]),
                    json=_first("keep_ours")).status_code == 201
    _, reply_review = _prepared(api, db, c)
    assert seen == [reply_review.id]


# ------------------------------------------------- AM-299 r3: an owner's acceptance carried
def _favoured(db, tmp_path, owner):
    """Clause 9 returned at 3 months, accepted in our favour by the approved rule: Better
    for us, the deal owner's to accept."""
    from tests.test_negotiation import _docx as docx_
    from tests.test_negotiation import _ingest as ingest_
    c = _contract(db, owner)
    ingest_(db, tmp_path, c, docx_(OURS), "ours.docx")
    theirs = ingest_(db, tmp_path, c, docx_(THEIRS), "theirs.docx")
    review = _review(db, theirs, [(0, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.ACCEPTABLE)])
    return c, review


def test_an_owner_acceptance_better_for_us_is_carried_and_the_gate_opens(
        api, db, owner, tmp_path):
    from legalmind.analysis.negotiation import carry_acceptances
    from legalmind.evaluation.workflow import OWNER_ACCEPTANCE_CARRIED
    assert OWNER_ACCEPTANCE_CARRIED == audit.NEGOTIATION_ACCEPTANCE_CARRIED
    c, review = _favoured(db, tmp_path, owner)
    change = _changes(api, c)["changes"][0]
    assert change["effect_for_us"] == "POSITIVE"
    assert api.post(_url(c, change["row_key"]),
                    json=_first("accept_theirs")).status_code == 201
    reply, reply_review = _prepared(api, db, c)
    finding, ev = _point(db, reply_review, _theirs_rv(db, review), reply)
    assert _content(api, reply.id).status_code == 409             # undecided until carried

    assert carry_acceptances(db, reply_review) == 1
    assert finding.status is E.FindingStatus.RESOLVED
    assert reply_open_points(db, reply) is None
    assert _content(api, reply.id).status_code == 200
    event = db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.NEGOTIATION_ACCEPTANCE_CARRIED)).one()
    assert (event.actor_id, event.entity_id, event.after_state["effect"],
            event.after_state["reason"]) == (owner.id, finding.id, "POSITIVE", "Better for us")
    # never a Legal Decision, never ACCEPTABLE — the engine's outcome stands
    assert db.scalar(select(func.count()).select_from(M.LegalDecision)) == 0
    assert ev.rule_outcome is E.RuleOutcome.UNACCEPTABLE
    assert carry_acceptances(db, reply_review) == 0                # idempotent


def test_reply_text_that_differs_from_the_accepted_row_stays_undecided(
        api, db, owner, tmp_path):
    from legalmind.analysis.negotiation import carry_acceptances
    c, review = _favoured(db, tmp_path, owner)
    change = _changes(api, c)["changes"][0]
    assert api.post(_url(c, change["row_key"]),
                    json=_first("accept_theirs")).status_code == 201
    reply, reply_review = _prepared(api, db, c)
    finding, _ = _point(db, reply_review, _theirs_rv(db, review), reply)
    for row in db.scalars(select(M.DocumentEvidence).where(
            M.DocumentEvidence.document_version_id == reply.id)):
        row.content = row.content.replace("3 months", "2 months")
    db.flush()
    assert carry_acceptances(db, reply_review) == 0
    assert finding.status is E.FindingStatus.DECISION_REQUIRED
    assert _content(api, reply.id).status_code == 409


def test_a_worse_for_us_point_keeps_the_gate(api, db, owner, tmp_path):
    """Only a holder's decision opens it — nothing the owner answers is carried."""
    from legalmind.analysis.negotiation import carry_acceptances
    c, theirs, review = _measured(db, tmp_path, owner)          # a DEVIATION against us
    change = _changes(api, c)["changes"][0]
    assert change["effect_for_us"] == "NEGATIVE"
    assert api.post(_url(c, change["row_key"]),
                    json=_first("keep_ours")).status_code == 201
    reply, reply_review = _prepared(api, db, c)
    _point(db, reply_review, _theirs_rv(db, review), reply)
    assert carry_acceptances(db, reply_review) == 0
    assert _content(api, reply.id).status_code == 409
