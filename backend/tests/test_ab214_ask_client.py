"""AB-214 `AM-411` (C-33, option a) — every document synthetic, no client.

A point waiting on the client because Legal answered "Ask the client" does not block the
contract decisions Sign after our changes / Do not sign / On hold; it blocks Sign as is;
an internal clarification blocks as `AM-178` says; the question leaves in our reply; and
on the client's next version the point is open to Legal again.
"""

from __future__ import annotations

import io
import uuid
import zipfile

from sqlalchemy import select

from legalmind.analysis.negotiation import reply_open_points
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.workflow import contract_outcome
from legalmind.workflow.decisions import carry_decisions, carry_forward, record_decision
from legalmind.workflow.review_lifecycle import advance_after_analysis
from tests.conftest import make_evaluation, sign_in
from tests.test_e2e_batch_cd import QUESTION
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _docx,
    _first,
    _ingest,
    _review,
    _url,
    owner,
)
from tests.test_negotiation_carry import _point, _prepared, _theirs_rv
from tests.test_negotiation_wording import (  # noqa: F401 — `published` is a fixture
    THEIRS,
    _lawyer,
    _measured,
    _send,
    published,
)
from tests.test_version_comparison import V1


def _outcome(api, review, outcome, expected=0):
    return api.post(f"{V1}/reviews/{review.id}/outcome", json={
        "outcome": outcome, "justification": "as answered", "expected_version": expected})


def _asked(api, db, owner, tmp_path):
    c, theirs, review = _measured(db, tmp_path, owner)
    advance_after_analysis(db, review)            # as the analysis leaves it: with Legal
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    change = _changes(api, c)["changes"][0]
    r = api.post(_url(c, change["row_key"]), json=_first("ask_client", client_note=QUESTION))
    assert r.status_code == 201, r.text
    return c, theirs, review, lawyer


def test_ask_the_client_leaves_the_contract_decision_open_but_never_sign_as_is(
        api, db, owner, tmp_path):
    c, theirs, review, lawyer = _asked(api, db, owner, tmp_path)
    finding = db.scalars(select(M.Finding).where(M.Finding.review_id == review.id)).one()
    assert finding.status is E.FindingStatus.AWAITING_CLARIFICATION
    decision = db.scalars(select(M.LegalDecision)).one()
    mark = db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.DECISION_ASKED_CLIENT)).one()
    assert (mark.entity_id, mark.actor_id) == (decision.id, lawyer.id)       # audited
    state = api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]
    assert (state["ready"], state["waiting_on_client"], state["sign_as_is_allowed"]) \
        == (True, True, False)
    counts = api.get(f"{V1}/contracts/{c.id}").json()["data"]["counts"]
    assert counts["decision_for_me"] is True                 # the lawyer's header step
    todo = [t for t in api.get(f"{V1}/todo").json()["data"]["items"]
            if t["kind"] == "contract_decision"]
    assert len(todo) == 1 and "question goes to the client" in todo[0]["sentence"]

    assert _outcome(api, review, "SIGN_AS_IS").status_code == 422
    assert db.scalars(select(M.ContractOutcomeRecord)).all() == []
    assert _outcome(api, review, "SIGN_WITH_CHANGES").status_code == 201
    # not every point is decided: the Review is never RESOLVED or CLOSED by this
    assert review.status is E.ReviewStatus.LEGAL_REVIEW
    assert finding.status is E.FindingStatus.AWAITING_CLARIFICATION
    got = api.get(f"{V1}/contracts/{c.id}").json()["data"]
    assert got["negotiation_stage"]["stage"] == "READY_TO_SEND"
    assert got["counts"]["decision_for_me"] is False          # recorded: nothing due
    for outcome, version in (("ON_HOLD", 1), ("DO_NOT_SIGN", 2)):
        assert _outcome(api, review, outcome, version).status_code == 201


def test_an_internal_clarification_still_blocks_the_contract_decision(
        api, db, owner, tmp_path):
    """`AM-178` r1 as locked: a clarification not asked of the client blocks every
    outcome, and a point still to decide beside a client question blocks too."""
    c, _, review = _measured(db, tmp_path, owner)
    advance_after_analysis(db, review)
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    change = _changes(api, c)["changes"][0]
    ev_id = uuid.UUID(change["review"]["after"][0]["evaluation_ids"][0])
    record_decision(db, actor_id=lawyer.id, evaluation_id=ev_id,
                    decision_type=E.DecisionType.REQUEST_CLARIFICATION,
                    justification="asking a colleague")
    assert contract_outcome.decidable(db, review) is None
    assert api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]["ready"] is False
    for outcome in ("SIGN_WITH_CHANGES", "DO_NOT_SIGN", "ON_HOLD", "SIGN_AS_IS"):
        assert _outcome(api, review, outcome).status_code == 422
    # Legal then asks the client on the change itself: that clarification is the client's
    assert api.post(_url(c, change["row_key"]), json=_first(
        "ask_client", client_note=QUESTION)).status_code == 201
    assert contract_outcome.decidable(db, review) == contract_outcome.ASKED
    # ... but a second Evaluation of the point, still undecided, keeps AM-178 shut
    make_evaluation(db, db.get(M.Finding, db.get(M.Evaluation, ev_id).finding_id),
                    classification=E.FindingClassification.DEVIATION,
                    rule_outcome=E.RuleOutcome.UNACCEPTABLE, scope_key="second")
    assert contract_outcome.decidable(db, review) is None


def test_the_question_leaves_in_our_reply_and_the_point_comes_back_open(
        api, db, owner, tmp_path):
    c, theirs, review, lawyer = _asked(api, db, owner, tmp_path)
    assert _outcome(api, review, "SIGN_WITH_CHANGES").status_code == 201
    reply, reply_review = _prepared(api, db, c)
    got = api.get(f"{V1}/document-versions/{reply.id}/content")
    # the reply's own Review reads the client's unchanged words: the same question,
    # carried — "Waiting for the client", and the reply may leave with it
    finding, ev = _point(db, reply_review, _theirs_rv(db, review), reply)
    assert reply_open_points(db, reply) is not None           # undecided: blocked
    assert carry_decisions(db, reply_review) == 1
    assert finding.status is E.FindingStatus.AWAITING_CLARIFICATION
    assert reply_open_points(db, reply) is None
    got = api.get(f"{V1}/document-versions/{reply.id}/content")
    assert got.status_code == 200
    with zipfile.ZipFile(io.BytesIO(got.content)) as z:
        assert QUESTION in z.read("word/comments.xml").decode()

    # the client's next version, same words: nothing is carried — Legal decides it
    sign_in(api, db, owner)
    again = _ingest(db, tmp_path, c, _docx(THEIRS), "theirs-2.docx")
    again.doc_metadata = {**(again.doc_metadata or {}), "version_role": "CLIENT_MODIFIED"}
    db.flush()
    next_review = _review(db, again, [])
    point, _ = _point(db, next_review, _theirs_rv(db, review), again)
    assert carry_decisions(db, next_review) == 0
    assert carry_forward(db, next_review) == 0
    assert point.status is E.FindingStatus.DECISION_REQUIRED
    assert contract_outcome.decidable(db, next_review) is None
    # r7: our reply left their words where we asked, so the round is read against our
    # version before it — the asked change is listed again, for Legal to answer
    assert reply.doc_metadata["reply_asked"] == 1
    listed = _changes(api, c)
    assert listed["from"]["version_number"] == 1
    assert [ch["answer"] for ch in listed["changes"]] == [None]
