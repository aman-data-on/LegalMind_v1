"""R10 — colleagues (`AM-259`) and filing an Ask attachment (`AM-269` r2), AB-150.
Synthetic material only (rule 21)."""
from __future__ import annotations

import uuid
from urllib.parse import quote

import pytest
from sqlalchemy import func, select

from legalmind import notifications
from legalmind.assist import service
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_ingestion import build_docx

V1 = "/api/v1"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
RETURNED = build_docx(["1. Fees", "Fees are payable within sixty days of invoice."])


def _dept(db):
    d = M.Department(code=f"D{uuid.uuid4().hex[:8]}", name="Sales")
    db.add(d)
    db.flush()
    return d


@pytest.fixture
def team(db, seeded):
    sales, other = _dept(db), _dept(db)
    owner, mate, outsider, lead = (make_user(db) for _ in range(4))
    for u, d in ((owner, sales), (mate, sales), (outsider, other), (lead, sales)):
        u.department_id = d.id
        grant_role(db, u, P.ROLE_USER)
    grant_role(db, lead, P.ROLE_DEPARTMENT_LEAD)
    contract = M.Contract(owner_id=owner.id, name="Synthetic MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    return owner, mate, outsider, lead, contract


def _url(contract, user=None):
    base = f"{V1}/contracts/{contract.id}/collaborators"
    return base if user is None else f"{base}/{user.id}"


def _upload(api, contract):
    return api.post(f"{V1}/contracts/{contract.id}/document-versions", content=RETURNED,
                    headers={"Content-Type": DOCX, "X-Filename": "returned.docx"})


def test_the_owner_adds_a_same_department_colleague_and_not_an_outsider(db, api, team):
    owner, mate, outsider, _, contract = team
    sign_in(api, db, owner)
    listed = api.get(_url(contract)).json()["data"]
    assert listed["can_manage"] and {c["id"] for c in listed["candidates"]} >= {str(mate.id)}
    assert str(outsider.id) not in {c["id"] for c in listed["candidates"]}

    r = api.post(_url(contract), json={"user_id": str(outsider.id)})
    assert r.status_code == 422, r.text
    r = api.post(_url(contract), json={"user_id": str(mate.id)})
    assert r.status_code == 201, r.text
    assert [c["id"] for c in r.json()["data"]["collaborators"]] == [str(mate.id)]
    assert db.execute(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.CONTRACT_COLLABORATOR_ADDED,
        M.AuditEvent.entity_id == contract.id)).scalar_one() == 1

    assert api.delete(_url(contract, mate)).json()["data"]["collaborators"] == []


def test_a_lead_may_add_and_a_colleague_or_stranger_may_not(db, api, team):
    owner, mate, outsider, lead, contract = team
    sign_in(api, db, mate)              # same department, no department.view: no scope
    assert api.post(_url(contract), json={"user_id": str(mate.id)}).status_code == 404
    sign_in(api, db, outsider)
    assert api.get(_url(contract)).status_code == 404
    sign_in(api, db, lead)
    assert api.post(_url(contract), json={"user_id": str(mate.id)}).status_code == 201


def test_a_collaborator_uploads_and_answers_but_never_archives_transfers_or_deletes(
        db, api, team):
    owner, mate, outsider, _, contract = team
    sign_in(api, db, outsider)
    assert _upload(api, contract).status_code == 404       # non-collaborator: 404

    db.add(M.ContractCollaborator(contract_id=contract.id, user_id=mate.id,
                                  added_by=owner.id))
    db.flush()
    sign_in(api, db, mate)
    assert _upload(api, contract).status_code == 201
    assert api.post(f"{V1}/contracts/{contract.id}/archive").status_code == 404
    assert api.delete(f"{V1}/contracts/{contract.id}").status_code == 404
    assert api.post(f"{V1}/contracts/{contract.id}/transfer",
                    json={"new_owner_id": str(mate.id), "reason": "x"}).status_code in (
                        403, 404)
    # AM-280: a collaborator SEES the contract, so managing it is a 403, never custody
    assert api.post(_url(contract), json={"user_id": str(mate.id)}).status_code == 403
    assert api.get(f"{V1}/contracts/{contract.id}").status_code == 200


# ------------------------------------------------------------- Ask files a returned copy
def _attached(db, api, user):
    conversation = service.create_conversation(db, user_id=user.id, contract_id=None)
    r = api.post(f"{V1}/conversations/{conversation}/attachments", content=RETURNED,
                 headers={"Content-Type": DOCX, "X-Filename": "returned.docx"})
    assert r.status_code == 201, r.text
    return conversation, r.json()["data"]["id"]


def _versions(db, contract):
    return db.execute(select(func.count()).select_from(M.DocumentVersion)
                      .where(M.DocumentVersion.contract_id == contract.id)).scalar_one()


def test_an_attachment_is_filed_only_on_the_readers_action(db, api, team):
    owner, mate, outsider, _, contract = team
    db.add(M.ContractCollaborator(contract_id=contract.id, user_id=mate.id,
                                  added_by=owner.id))
    db.flush()
    sign_in(api, db, mate)
    conversation, attachment = _attached(db, api, mate)
    assert _versions(db, contract) == 0, "attaching in Ask created a version by itself"
    base = f"{V1}/conversations/{conversation}/attachments/{attachment}"
    assert [t["id"] for t in api.get(f"{base}/file-targets").json()["data"]] == [
        str(contract.id)]

    headers = {"Content-Type": DOCX, "X-Filename": quote("returned.docx")}
    wrong = api.post(f"{base}/file", params={"contract_id": str(contract.id)},
                     content=RETURNED + b"x", headers=headers)
    assert wrong.status_code == 422 and _versions(db, contract) == 0

    r = api.post(f"{base}/file", params={"contract_id": str(contract.id)},
                 content=RETURNED, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["document_version"]["version_role"] == "CLIENT_MODIFIED"
    assert _versions(db, contract) == 1
    assert db.execute(select(M.Notification.kind)
                      .where(M.Notification.user_id == owner.id)).scalars().all() == [
        notifications.CLIENT_RETURNED]
    assert db.execute(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.ASSIST_ATTACHMENT_FILED)).scalar_one() == 1


def test_filing_into_a_contract_the_reader_cannot_write_is_a_404(db, api, team):
    owner, mate, outsider, _, contract = team
    sign_in(api, db, outsider)
    conversation, attachment = _attached(db, api, outsider)
    base = f"{V1}/conversations/{conversation}/attachments/{attachment}"
    assert api.get(f"{base}/file-targets").json()["data"] == []
    r = api.post(f"{base}/file", params={"contract_id": str(contract.id)},
                 content=RETURNED, headers={"Content-Type": DOCX, "X-Filename": "r.docx"})
    assert r.status_code == 404 and _versions(db, contract) == 0
    sign_in(api, db, owner)                 # someone else's chat: the same 404
    assert api.get(f"{base}/file-targets").status_code == 404
