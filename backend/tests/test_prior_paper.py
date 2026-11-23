"""Batch 8 item 1 (`AM-464`/`AM-465`): "already agreed before" — a change or a point of
the client's paper beside what we signed or finalised with the same client earlier.

Every document is synthetic and names no client (54.6). The labels are information only:
the tests pin that they never move a route, an effect, a measured word or an answer, and
that a contract this reader may not read is never named, counted or used (rule 18).
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from legalmind.api import prior_paper
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.mapping.engine import Clause
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_api_resources import DOCX_MIME, build_docx
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _ingest,
    _review,
    owner,
)
from tests.test_negotiation_reply import OURS, THEIRS
from tests.test_version_comparison import V1

#: what we signed with the client earlier: clause 2 already as the client now asks,
#: clause 1 as we sent it, clause 3 (which the client deletes) — no clause 4 or 5
SIGNED = [OURS[0], THEIRS[1], OURS[2]]
CODE = "PRIOR-TEST-001"


def _client(db, owner):
    cp = M.Counterparty(name="Client Co", created_by=owner.id)
    db.add(cp)
    db.flush()
    return cp


def _signed(db, tmp_path, owner, cp, role="FINAL_SIGNED", paper=SIGNED):
    c = _contract(db, owner)
    c.name, c.counterparty_id = "Earlier deal", cp.id
    v = _ingest(db, tmp_path, c, _docx(*paper), "signed.docx")
    v.doc_metadata = {**(v.doc_metadata or {}), "version_role": role}
    db.flush()
    return c, v


def _deal(db, tmp_path, owner, cp):
    c = _contract(db, owner)
    c.counterparty_id = cp.id
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(*THEIRS), "theirs.docx")
    return c, theirs


def _by_clause(listed):
    return {(ch["clause"]["number"] or "").rstrip("."): ch for ch in listed["changes"]}


def _stripped(listed: dict) -> str:
    """The list as it is without any earlier contract: `prior` and `prior_papers` out."""
    out = {k: v for k, v in listed.items() if k != "prior_papers"}
    out["changes"] = [{k: v for k, v in ch.items() if k != "prior"}
                      for ch in listed["changes"]]
    return json.dumps(out, sort_keys=True, default=str)


def test_a_clause_in_our_signed_contract_with_the_client_reads_same(api, db, owner,
                                                                    tmp_path):
    cp = _client(db, owner)
    x, _ = _signed(db, tmp_path, owner, cp)
    y, _ = _deal(db, tmp_path, owner, cp)
    listed = _changes(api, y)
    rows = _by_clause(listed)
    prior = rows["2"]["prior"]                  # the client's "Singapore" is what we signed
    assert prior["state"] == "SAME" and prior["contract_id"] == str(x.id)
    assert (prior["name"], prior["kind"]) == ("Earlier deal", "SIGNED")
    assert listed["prior_papers"] == [{k: v for k, v in prior.items() if k != "state"}]


def test_a_clause_changed_since_signing_reads_changed_and_a_new_one_new(api, db, owner,
                                                                        tmp_path):
    cp = _client(db, owner)
    _signed(db, tmp_path, owner, cp)
    y, _ = _deal(db, tmp_path, owner, cp)
    rows = _by_clause(_changes(api, y))
    assert rows["1"]["prior"]["state"] == "CHANGED"       # 60 days; we signed 30
    assert rows["5"]["prior"]["state"] == "NEW"           # never in what we signed


def test_a_deleted_clause_we_had_signed_reads_in_signed(api, db, owner, tmp_path):
    cp = _client(db, owner)
    _signed(db, tmp_path, owner, cp)
    y, _ = _deal(db, tmp_path, owner, cp)
    deleted = next(ch for ch in _changes(api, y)["changes"] if ch["kind"] == "DELETED")
    assert deleted["prior"]["state"] == "IN_SIGNED"


@pytest.mark.parametrize(("stage", "counts"), [
    ("SIGNED", True), ("FINAL", True),
    ("DRAFTING", False), ("WITH_CLIENT", False), ("CLIENT_RETURNED", False)])
def test_a_final_contract_counts_and_a_draft_or_with_client_does_not(
        api, db, owner, tmp_path, monkeypatch, stage, counts):
    cp = _client(db, owner)
    x, _ = _signed(db, tmp_path, owner, cp)
    y, _ = _deal(db, tmp_path, owner, cp)
    monkeypatch.setattr(prior_paper, "derive_stages",
                        lambda db, cs: {c.id: {"stage": stage} for c in cs})
    listed = _changes(api, y)
    assert ("prior_papers" in listed) is counts
    if counts:
        assert listed["prior_papers"][0]["kind"] == stage


def test_an_unreadable_signed_contract_is_silently_absent(api, db, owner, tmp_path):
    """Another department's owner signed with the same client: no `prior`, no
    `prior_papers`, no brief count — the response byte-identical to no earlier contract."""
    cp = _client(db, owner)
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    x, _ = _signed(db, tmp_path, stranger, cp)
    y, _ = _deal(db, tmp_path, owner, cp)
    sign_in(api, db, owner)
    hidden = _changes(api, y)
    brief = api.get(f"{V1}/contracts/{y.id}/brief").json()["data"]
    x.counterparty_id = None                                  # no earlier contract at all
    db.flush()
    assert json.dumps(_changes(api, y), sort_keys=True) == json.dumps(hidden,
                                                                       sort_keys=True)
    assert "prior_papers" not in hidden and all("prior" not in c for c in hidden["changes"])
    assert "already_agreed" not in brief
    assert api.get(f"{V1}/contracts/{y.id}/brief").json()["data"] == brief


def test_prior_never_changes_route_effect_or_answer(api, db, owner, tmp_path):
    cp = _client(db, owner)
    x, _ = _signed(db, tmp_path, owner, cp)
    y, theirs = _deal(db, tmp_path, owner, cp)
    _review(db, theirs, [(1, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    labelled = _changes(api, y)
    assert any("prior" in ch for ch in labelled["changes"])
    x.counterparty_id = None
    db.flush()
    plain = _changes(api, y)
    assert "prior_papers" not in plain
    assert _stripped(labelled) == _stripped(plain)


def test_a_cross_owner_paper_read_is_audited_as_an_open(api, db, owner, tmp_path):
    """A Department Lead reads a deal beside a colleague's signed paper with the same
    client: the paper is read under department scope and recorded as opening it would
    be; a colleague without that scope never sees it."""
    dept = M.Department(code="PRIORTEST", name="Prior test")
    db.add(dept)
    db.flush()
    colleague, lead = make_user(db), make_user(db)
    grant_role(db, colleague, P.ROLE_USER)
    grant_role(db, lead, P.ROLE_DEPARTMENT_LEAD)
    for user in (owner, colleague, lead):
        user.department_id = dept.id
    db.flush()
    cp = _client(db, owner)
    x, _ = _signed(db, tmp_path, colleague, cp)
    y, _ = _deal(db, tmp_path, owner, cp)
    assert "prior_papers" not in _changes(api, y)        # the owner may not read x
    sign_in(api, db, lead)
    assert _changes(api, y)["prior_papers"][0]["contract_id"] == str(x.id)
    assert db.execute(select(M.AuditEvent.id).where(
        M.AuditEvent.entity_id == x.id, M.AuditEvent.actor_id == lead.id,
        M.AuditEvent.action == audit.CONTRACT_READ_VIA_DEPARTMENT_SCOPE)).first()


def test_counting_skips_prior(api, db, owner, tmp_path, monkeypatch):
    """The lists and the To-do count with `deal_counts`; no earlier contract is read."""
    cp = _client(db, owner)
    _signed(db, tmp_path, owner, cp)
    _deal(db, tmp_path, owner, cp)

    def refuse(*_a, **_k):
        raise AssertionError("an earlier contract was read while counting")
    monkeypatch.setattr(prior_paper, "papers", refuse)
    assert api.get(f"{V1}/contracts").status_code == 200
    assert api.get(f"{V1}/todo").status_code == 200


def _angles(api, review):
    r = api.get(f"{V1}/reviews/{review.id}/angles")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_a_point_with_the_same_fact_as_signed_reads_same(api, db, owner, tmp_path):
    cp = _client(db, owner)
    x, signed = _signed(db, tmp_path, owner, cp)
    _review(db, signed, [(1, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)],
            code=CODE)
    y, theirs = _deal(db, tmp_path, owner, cp)
    review = _review(db, theirs, [(1, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)], code=CODE)
    [item] = _angles(api, review)["legal"]["items"]
    assert item["prior"]["state"] == "SAME" and item["prior"]["contract_id"] == str(x.id)


def test_a_point_measured_differently_reads_changed(api, db, owner, tmp_path):
    cp = _client(db, owner)
    _, signed = _signed(db, tmp_path, owner, cp)
    _review(db, signed, [(1, E.FindingClassification.MATCH, E.RuleOutcome.ACCEPTABLE)],
            code=CODE)
    y, theirs = _deal(db, tmp_path, owner, cp)
    review = _review(db, theirs, [(1, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)], code=CODE)
    [item] = _angles(api, review)["legal"]["items"]
    assert item["prior"]["state"] == "CHANGED"


def test_a_point_with_no_earlier_review_carries_no_prior(api, db, owner, tmp_path):
    cp = _client(db, owner)
    _signed(db, tmp_path, owner, cp)               # filed as signed: never reviewed
    y, theirs = _deal(db, tmp_path, owner, cp)
    review = _review(db, theirs, [(1, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)], code=CODE)
    [item] = _angles(api, review)["legal"]["items"]
    assert "prior" not in item


def test_brief_counts_changes_already_agreed(api, db, owner, tmp_path):
    cp = _client(db, owner)
    x, _ = _signed(db, tmp_path, owner, cp)
    y, _ = _deal(db, tmp_path, owner, cp)
    rows = _by_clause(_changes(api, y))
    agreed = api.get(f"{V1}/contracts/{y.id}/brief").json()["data"]["already_agreed"]
    assert agreed["count"] == 1 and agreed["rows"] == [rows["2"]["row_key"]]
    assert agreed["contract"]["contract_id"] == str(x.id)
    assert agreed["contract"]["kind"] == "SIGNED"


def test_file_signed_earlier_from_the_client_page(api, db, owner, tmp_path):
    """R1.6 (`AM-465`): the client page's "Signed earlier, for reference" — a new
    contract with this client, its one file uploaded and declared Final signed through
    the existing declaration (`AM-298` r1): SIGNED, origin SIGNED_OUTSIDE, audited; a
    contract with a second version is refused (409)."""
    cp = _client(db, owner)
    cid = api.post(f"{V1}/contracts", json={"name": "Earlier deal",
                                            "counterparty_id": str(cp.id)}).json()["data"]["id"]
    up = api.post(f"{V1}/contracts/{cid}/document-versions",
                  content=build_docx(SIGNED),
                  headers={"Content-Type": DOCX_MIME, "X-Filename": "signed.docx",
                           "X-Version-Role": "COMPANY_DRAFT"})
    assert up.status_code == 201, up.text
    vid = up.json()["data"]["document_version"]["id"]
    r = api.patch(f"{V1}/document-versions/{vid}", json={"version_role": "FINAL_SIGNED"})
    assert r.status_code == 200, r.text
    contract = api.get(f"{V1}/contracts/{cid}").json()["data"]
    assert contract["negotiation_stage"]["stage"] == "SIGNED"
    state = api.get(f"{V1}/contracts/{cid}/execution").json()["data"]
    assert state["execution"]["origin"] == "SIGNED_OUTSIDE"
    assert db.execute(select(M.AuditEvent.id).where(
        M.AuditEvent.action == audit.EXECUTION_RECORDED)).first()
    # a contract that already holds the client's paper is negotiated: refused
    other = api.post(f"{V1}/contracts", json={"name": "Negotiated"}).json()["data"]["id"]
    for role in ("CLIENT_MODIFIED", "COMPANY_DRAFT"):
        last = api.post(f"{V1}/contracts/{other}/document-versions",
                        content=build_docx([*SIGNED, role]),
                        headers={"Content-Type": DOCX_MIME, "X-Filename": f"{role}.docx",
                                 "X-Version-Role": role})
    r = api.patch(f"{V1}/document-versions/{last.json()['data']['document_version']['id']}",
                  json={"version_role": "FINAL_SIGNED"})
    assert r.status_code == 409


def _clauses(*rows: tuple[str | None, str]) -> list[Clause]:
    return [Clause(evidence_id=uuid.uuid4(), content=t, section_number=n) for n, t in rows]


def test_a_clause_beside_a_changed_table_reads_same_and_a_changed_sentence_changed():
    """As `AM-462` (c8) reads a clause with a price table under it: the clause's own
    words are the ones we signed, though this deal's table differs."""
    prose = (("6", "6. Disputes are heard by the courts at the agreed seat."),)
    signed = _clauses(*prose, (None, "| 1 | GPU node | 04 |"))
    theirs = _clauses(*prose, (None, "| 1 | GPU node | 05 |"))
    read = prior_paper._aligned(signed, theirs)
    assert read["state"] == ["SAME"]
    reworded = _clauses(("6", "6. Disputes are heard by the courts at another seat."),
                        (None, "| 1 | GPU node | 04 |"))
    assert prior_paper._aligned(signed, reworded)["state"] == ["CHANGED"]


def test_the_signing_date_on_the_record_dates_the_earlier_contract(api, db, owner, tmp_path):
    """A copy filed as signed says when it was signed once the owner adds who signed."""
    cp = _client(db, owner)
    x, signed = _signed(db, tmp_path, owner, cp)
    db.add(M.Execution(contract_id=x.id, version_number=1, recorded_by=owner.id,
                       signed_document_version_id=signed.id, origin="SIGNED_OUTSIDE",
                       signatories=[{"party": "CLIENT", "signed_on": "2026-10-21"},
                                    {"party": "OURS", "signed_on": "2026-10-23"}]))
    db.flush()
    y, _ = _deal(db, tmp_path, owner, cp)
    assert _changes(api, y)["prior_papers"][0]["agreed_on"] == "2026-10-23"
