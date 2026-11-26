"""Source integrity B1 — the one gate on what leaves LegalMind for a client (`AM-273`/
`AB-150` amendment, owner yes 2026-11-26): copies checked and recorded, client files
refused server-side, a Legal-only override (`legal.review`, never `legal.decision`) with
a reason, and mark-sent recording what went out. Every page and draft is synthetic."""
from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy import select, text

from legalmind import config, notifications
from legalmind.analysis import negotiation
from legalmind.assist.knowledge import published
from legalmind.assist.knowledge import source_check as sc
from legalmind.db import models as M
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.assist.knowledge.test_source_check import NEW, OLD, SLA_LS
from tests.conftest import grant_role, make_user, sign_in
from tests.test_negotiation import _contract, _docx, _ingest, _review
from tests.test_negotiation_wording import _send
from tests.test_version_comparison import V1

CHECK = f"{V1}/outgoing/check"
INCIDENT = "As per our SLA, power uptime is 99.95% for dual-power servers."
REDRAFT = "As per our SLA, power uptime is 99.9% for dual-power servers."


@pytest.fixture
def policies(db, tmp_path, monkeypatch):
    monkeypatch.setenv("LEGALMIND_SOURCE_MATERIAL_DIR", str(tmp_path / "material"))
    published.ingest(db, SLA_LS, OLD, read_on=datetime.date(2026, 10, 9))
    published.ingest(db, SLA_LS, NEW, read_on=datetime.date(2026, 11, 2))
    db.execute(text(f'UPDATE "{config.assist_schema()}".knowledge_sources '
                    "SET last_checked_ok_at = now() WHERE status = 'CURRENT'"))


def _person(api, db, role):
    user = make_user(db)
    grant_role(db, user, role)
    sign_in(api, db, user)
    return user


def _codes(r):
    return [p["code"] for p in r.json()["data"]["problems"]]


def test_copy_email_blocks_the_old_figure_and_passes_the_redraft(api, db, seeded,
                                                                 policies):
    _person(api, db, P.ROLE_USER)
    r = api.post(CHECK, json={"surface": "copy_email", "text": INCIDENT})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["blocked"] and _codes(r) == ["OLD_FIGURE"]
    assert body["problems"][0]["current_wording"] == "Power (Dual Power Servers) | 99.9%"
    assert body["can_override"] is False
    ok = api.post(CHECK, json={"surface": "copy_email", "text": REDRAFT}).json()["data"]
    assert ok == {"problems": [], "blocked": False, "overridden": False,
                  "can_override": False}
    rows = db.execute(select(M.AuditEvent.after_state).where(
        M.AuditEvent.action == audit.OUTGOING_CHECKED)).scalars().all()
    assert [r["blocked"] for r in rows] == [True, False]
    assert all(INCIDENT not in str(r) and r["policy_versions"] for r in rows)


def test_a_sales_override_is_403_and_a_legal_override_passes_with_hashes(
        api, db, seeded, policies):
    _person(api, db, P.ROLE_USER)
    r = api.post(CHECK, json={"surface": "copy_email", "text": INCIDENT,
                              "override_reason": "client asked for the old figure"})
    assert r.status_code == 403
    lawyer = _person(api, db, P.ROLE_LEGAL_REVIEWER)
    assert api.post(CHECK, json={"surface": "copy_email", "text": INCIDENT,
                                 "override_reason": "  "}).status_code == 422
    r = api.post(CHECK, json={"surface": "copy_email", "text": INCIDENT,
                              "override_reason": "Legal confirmed with the client"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["blocked"] is False and r.json()["data"]["overridden"]
    row = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.OUTGOING_OVERRIDDEN)).scalar_one()
    assert row.actor_id == lawyer.id
    assert row.after_state["reason"] == "Legal confirmed with the client"
    hashes = db.execute(text(
        f'SELECT source_type, file_sha256 FROM "{config.assist_schema()}".'
        "knowledge_sources WHERE status = 'CURRENT'")).all()
    assert row.after_state["policy_versions"] == dict(hashes)
    assert P.LEGAL_DECISION not in {P.LEGAL_REVIEW}     # the override's permission


def test_paste_to_check_is_not_recorded_and_flags_internal_ids(api, db, seeded,
                                                               policies):
    _person(api, db, P.ROLE_USER)
    leak = f"See [C3] and record {uuid.uuid4()} for details."
    r = api.post(CHECK, json={"surface": "paste_check", "text": leak})
    assert _codes(r) == ["INTERNAL_ID"] and r.json()["data"]["blocked"]
    assert db.execute(select(M.AuditEvent).where(M.AuditEvent.action.in_(
        [audit.OUTGOING_CHECKED, audit.OUTGOING_OVERRIDDEN]))).first() is None


def test_the_deal_review_copy_only_warns(api, db, seeded, policies):
    _person(api, db, P.ROLE_USER)
    r = api.post(CHECK, json={"surface": "deal_review", "text": INCIDENT})
    assert _codes(r) == ["OLD_FIGURE"] and r.json()["data"]["blocked"] is False


def test_a_policy_not_rechecked_for_27_hours_blocks_the_copy(api, db, seeded, policies):
    db.execute(text(f'UPDATE "{config.assist_schema()}".knowledge_sources SET '
                    "last_checked_ok_at = now() - interval '27 hours'"))
    _person(api, db, P.ROLE_USER)
    r = api.post(CHECK, json={"surface": "copy_email", "text": REDRAFT})
    assert _codes(r) == ["NOT_RECHECKED"] and r.json()["data"]["blocked"]


@pytest.mark.parametrize("mark", ["copy_of", "reply_to"])
def test_a_client_file_with_the_old_figure_is_refused_server_side(
        api, db, seeded, policies, tmp_path, monkeypatch, mark):
    owner = _person(api, db, P.ROLE_USER)
    contract = _contract(db, owner)
    version = _ingest(db, tmp_path, contract, _docx("1. Fees.", INCIDENT), "ours.docx")
    version.doc_metadata = {**version.doc_metadata, mark: str(uuid.uuid4())}
    db.flush()
    monkeypatch.setattr(negotiation, "reply_open_points", lambda db, v: None)
    url = f"{V1}/document-versions/{version.id}/content"
    r = api.get(url)
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "SOURCE_CHECK_BLOCKED"
    assert [p["code"] for p in r.json()["error"]["problems"]] == ["OLD_FIGURE"]
    # a lawyer overrides THIS file's exact problems; then it downloads
    sign_in(api, db, owner)
    assert api.post(CHECK, json={"surface": "download",
                                 "document_version_id": str(version.id),
                                 "override_reason": "ok"}).status_code == 403
    lawyer = make_user(db)
    grant_role(db, lawyer, P.ROLE_LEGAL_REVIEWER)
    _send(db, _review(db, version, []), lawyer)    # how Legal reads a contract
    sign_in(api, db, lawyer)
    o = api.post(CHECK, json={"surface": "download", "document_version_id":
                              str(version.id), "override_reason": "Legal agreed"})
    assert o.status_code == 200, o.text
    assert api.get(url).status_code == 200


def test_mark_sent_records_the_policy_versions_and_figures(api, db, seeded, policies,
                                                          tmp_path):
    owner = _person(api, db, P.ROLE_USER)
    contract = _contract(db, owner)
    version = _ingest(db, tmp_path, contract, _docx("1. Fees.", REDRAFT), "ours.docx")
    r = api.post(f"{V1}/document-versions/{version.id}/mark-sent")
    assert r.status_code == 200, r.text
    after = db.execute(select(M.AuditEvent.after_state).where(
        M.AuditEvent.action == audit.DOCUMENT_VERSION_SENT,
        M.AuditEvent.entity_id == version.id)).scalar_one()
    assert after["figures"] == ["99.9%"] and after["source_problems"] == []
    assert after["policy_versions"][SLA_LS.source_type]


def test_notification_mail_carries_no_figure_and_no_clause_text():
    for kind in notifications.SENTENCES:
        body = notifications._message("a@example.test", kind,
                                      "/contracts/x").get_content()
        assert sc.figures(body) == [] and sc.policy_figures(body) == []
        assert "clause" not in body.lower()


def test_copy_email_names_a_changed_cited_passage_and_refuses_internal_records(
        api, db, seeded, policies):
    from legalmind.assist.agent import ledger
    from tests.assist.agent.test_assist_tools import _answered_with, _conv
    owner = _person(api, db, P.ROLE_USER)
    conv = _conv(db, owner)
    turn, answer = _answered_with(db, conv)
    old = db.execute(text(
        f'SELECT k.id, k.content FROM "{config.assist_schema()}".knowledge_items k '
        f'JOIN "{config.assist_schema()}".knowledge_sources s ON s.id = k.source_id '
        "WHERE s.status = 'SUPERSEDED' AND k.content LIKE 'Power (Dual%'")).one()
    keys = ledger.record_answer(db, conversation_id=conv, answer_id=answer,
                                turn_message_id=turn, extra=[
                                    ledger.Record("C", "PUB:power", old.id, old.content,
                                                  "APPROVED_COMPANY_DOCUMENT", "current"),
                                    ledger.Record("P", "POS:X@1", None, "a position",
                                                  "COMPANY_STANDARD", "current")])
    r = api.post(CHECK, json={"surface": "copy_email", "text": REDRAFT,
                              "conversation_id": str(conv), "keys": keys})
    assert r.status_code == 200, r.text
    found = r.json()["data"]["problems"]
    assert [p["code"] for p in found] == ["CHANGED", "INTERNAL_SOURCE"]
    assert found[0]["current_wording"] == "Power (Dual Power Servers) | 99.9%"
    assert "a position" not in r.text                  # never the internal text
    stranger = _person(api, db, P.ROLE_USER)
    assert stranger and api.post(CHECK, json={
        "surface": "copy_email", "text": REDRAFT, "conversation_id": str(conv),
        "keys": keys}).status_code == 404
