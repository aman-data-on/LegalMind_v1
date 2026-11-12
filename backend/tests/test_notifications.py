"""R9 — told when it matters (`AM-273` m3, AB-150). Synthetic material only (rule 21)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from legalmind import notifications
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.workflow.decisions import record_decision
from legalmind.workflow.escalation import escalate_finding
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
)

V1 = "/api/v1"
CLAUSE = "Liability is capped at the fees paid in the twelve months before the claim."


def _kinds(db, user):
    return [n.kind for n in db.execute(select(M.Notification)
                                       .where(M.Notification.user_id == user.id)).scalars()]


@pytest.fixture
def people(db, seeded, requirement_version):
    owner, holder, bystander = make_user(db), make_user(db), make_user(db)
    for u in (owner, bystander):
        grant_role(db, u, P.ROLE_USER)
    grant(db, holder, bespoke_role(db, f"LDA_{uuid.uuid4().hex[:6]}",
                                   [P.LEGAL_REVIEW, P.LEGAL_DECISION, P.REVIEW_VIEW]))
    review = make_review_for(db, owner)
    contract = db.get(M.Contract, review.contract_id)
    contract.name = "Synthetic Hosting MSA"
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding, rule_outcome=E.RuleOutcome.UNACCEPTABLE)
    return owner, holder, bystander, review, finding, evaluation


def test_an_escalation_tells_the_holders_and_a_decision_tells_the_raiser(db, people):
    owner, holder, bystander, review, finding, evaluation = people
    escalate_finding(db, actor_id=owner.id, finding_id=finding.id, reason="please decide")
    assert _kinds(db, holder) == [notifications.DECISION_REQUESTED]
    assert _kinds(db, owner) == [] and _kinds(db, bystander) == []

    record_decision(db, actor_id=holder.id, evaluation_id=evaluation.id,
                    decision_type=E.DecisionType.REJECT, justification="keep ours")
    assert _kinds(db, owner) == [notifications.DECIDED]
    assert _kinds(db, holder) == [notifications.DECISION_REQUESTED]   # never the actor
    assert _kinds(db, bystander) == []


def test_a_client_returned_version_tells_the_owner_and_collaborators_only(
        db, api, people):
    owner, holder, bystander, review, *_ = people
    colleague = make_user(db)
    grant_role(db, colleague, P.ROLE_USER)
    team = M.Department(code=f"T{uuid.uuid4().hex[:6]}", name="Team")
    db.add(team)
    db.flush()
    owner.department_id = colleague.department_id = team.id   # AM-280 r2
    db.add(M.ContractCollaborator(contract_id=review.contract_id, user_id=colleague.id,
                                  added_by=owner.id))
    db.flush()
    sign_in(api, db, colleague)
    dv = M.DocumentVersion(contract_id=review.contract_id, version_number=2,
                           original_filename="back.pdf", mime_type="application/pdf",
                           file_size_bytes=1, file_hash="h2", storage_key="k2",
                           processing_status=E.ProcessingStatus.COMPLETED,
                           uploaded_by=colleague.id)
    db.add(dv)
    db.flush()
    r = api.patch(f"{V1}/document-versions/{dv.id}",
                  json={"version_role": "CLIENT_MODIFIED"})
    assert r.status_code == 200, r.text
    assert _kinds(db, owner) == [notifications.CLIENT_RETURNED]
    assert _kinds(db, colleague) == [] and _kinds(db, bystander) == []
    assert _kinds(db, holder) == []


def test_the_api_lists_only_mine_and_another_users_notice_is_a_404(db, api, people):
    owner, holder, bystander, review, finding, _ = people
    escalate_finding(db, actor_id=owner.id, finding_id=finding.id, reason="please decide")
    theirs = db.execute(select(M.Notification.id)
                        .where(M.Notification.user_id == holder.id)).scalar_one()

    sign_in(api, db, holder)
    body = api.get(f"{V1}/notifications").json()["data"]
    assert body["unread"] == 1
    assert body["items"][0]["sentence"] == ("A colleague asked you to decide a point on "
                                            "Synthetic Hosting MSA.")
    assert body["items"][0]["link"] == f"/contracts/{review.contract_id}"

    sign_in(api, db, bystander)
    assert api.get(f"{V1}/notifications").json()["data"] == {"unread": 0, "items": []}
    assert api.post(f"{V1}/notifications/{theirs}/read").status_code == 404
    assert api.post(f"{V1}/notifications/{uuid.uuid4()}/read").status_code == 404

    sign_in(api, db, holder)
    assert api.post(f"{V1}/notifications/{theirs}/read").json()["data"]["read_at"]
    api.post(f"{V1}/notifications/read-all")
    assert api.get(f"{V1}/notifications").json()["data"]["unread"] == 0


def test_mail_goes_to_the_sink_after_commit_with_no_name_and_no_clause(
        db, people, tmp_path, monkeypatch):
    owner, holder, _, review, finding, _ = people
    sink = tmp_path / "mail"
    monkeypatch.setenv("LEGALMIND_MAIL_SINK_DIR", str(sink))
    escalate_finding(db, actor_id=owner.id, finding_id=finding.id, reason=CLAUSE)
    assert not sink.exists(), "mail left before the transaction committed"
    db.commit()
    files = list(sink.glob("*.eml"))
    assert len(files) == 1
    text = files[0].read_text()
    assert holder.email in text and f"/contracts/{review.contract_id}" in text
    assert "A colleague asked you to decide a point on a contract." in text
    assert "Synthetic Hosting MSA" not in text and "Liability" not in text
    assert "twelve months" not in text


def test_no_sink_and_no_relay_means_no_mail(db, people, tmp_path, monkeypatch):
    owner, _, _, _, finding, _ = people
    monkeypatch.delenv("LEGALMIND_MAIL_SINK_DIR", raising=False)
    monkeypatch.delenv("LEGALMIND_MAIL_RELAY", raising=False)
    escalate_finding(db, actor_id=owner.id, finding_id=finding.id, reason="x")
    assert "notification_mail" not in db.info


def test_the_relay_is_chosen_only_when_named_and_the_sink_wins(monkeypatch):
    from legalmind.outbound import mail
    monkeypatch.delenv("LEGALMIND_MAIL_SINK_DIR", raising=False)
    monkeypatch.delenv("LEGALMIND_MAIL_RELAY", raising=False)
    assert mail.transport() is None
    monkeypatch.setenv("LEGALMIND_MAIL_RELAY", "relay.example.test:2525")
    relay = mail.transport()
    assert isinstance(relay, mail.RelayTransport) and relay.port == 2525
    monkeypatch.setenv("LEGALMIND_MAIL_SINK_DIR", "/nonexistent")
    assert isinstance(mail.transport(), mail.FileSinkTransport)
