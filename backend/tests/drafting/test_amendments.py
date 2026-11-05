"""Amendments after signing — `AM-267`, built under `AM-309` (design 11 §6, R-9/R-11).

The STRUCTURAL placeholder and synthetic text only (rule 21). The AMENDMENT template here
is a test row whose frame is the DRAFT reference frame approved inside the test (as the
Special Conditions tests do) — never seeded, never published by the code.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import effective
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.drafting.test_special_conditions import (  # noqa: F401 — fixtures
    V1,
    _ingest,
    _package,
    _paragraph,
    _set,
    lawyer,
    negotiated,
    sc_template,
)
from tests.test_execution import PEOPLE, STAMP, _decide


def _edited(data: bytes, old: str, new: str) -> bytes:
    import io

    import docx as D
    doc = D.Document(io.BytesIO(data))
    _set(_paragraph(doc, old), new)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _sign(db, api, contract, agreed, storage):
    """The client signs ``agreed`` as it is: Sign as is, a matching signed copy, the
    stamp and both authorities, Mark signed."""
    review = db.execute(select(M.Review).where(
        M.Review.document_version_id == agreed.id)).scalars().first()
    _decide(db, review)
    signed = _ingest(db, Path(storage.root).parent, contract, storage.get(agreed.storage_key),
                     "CLIENT_MODIFIED")
    body = {**STAMP, "signatories": PEOPLE, "signed_document_version_id": str(signed.id)}
    r = api.post(f"{V1}/contracts/{contract.id}/execution", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["blockers"] == [], r.json()["data"]["blockers"]
    r = api.post(f"{V1}/contracts/{contract.id}/mark-signed",
                 json={"document_version_id": str(signed.id), "expected_version": 1})
    assert r.status_code == 200, r.text
    return signed


@pytest.fixture
def signed_deal(db, api, negotiated, lawyer):
    """Round 1's final contract (v3), linked to a client and signed (v4 FINAL_SIGNED)."""
    contract, _, _, storage = negotiated
    client = M.Counterparty(name="Client A", created_by=lawyer.id)
    db.add(client)
    db.flush()
    contract.counterparty_id = client.id
    db.flush()
    v3 = _package(db, api, contract)
    v4 = _sign(db, api, contract, v3, storage)
    return contract, v3, v4, storage


def _amend(api, contract, **body):
    return api.post(f"{V1}/contracts/{contract.id}/amendments", json=body or None)


def test_only_a_signed_contract_is_amended_and_never_an_amendment(db, api, negotiated):
    contract, _, _, _ = negotiated
    r = _amend(api, contract)
    assert r.status_code == 409 and "only a signed contract" in r.json()["error"]["message"]


def test_the_database_holds_the_rule_whoever_writes_the_row(db, signed_deal, lawyer):
    contract, _, _, _ = signed_deal

    def child(**kw):
        row = M.Contract(owner_id=lawyer.id, name="x", status=E.ContractStatus.DRAFT,
                         **{"contract_type": "AMENDMENT",
                            "counterparty_id": contract.counterparty_id,
                            "governed_by_contract_id": contract.id, **kw})
        with db.begin_nested():
            db.add(row)
            db.flush()
        return row

    ok = child()
    other = M.Counterparty(name="Client B", created_by=lawyer.id)
    db.add(other)
    db.flush()
    unsigned = M.Contract(owner_id=lawyer.id, name="u", status=E.ContractStatus.DRAFT,
                          counterparty_id=contract.counterparty_id)
    db.add(unsigned)
    db.flush()
    for refused in ({"counterparty_id": other.id}, {"counterparty_id": None},
                    {"contract_type": "MSA"}, {"governed_by_contract_id": ok.id},
                    {"governed_by_contract_id": unsigned.id}):
        with pytest.raises(DBAPIError):
            child(**refused)
    with pytest.raises(DBAPIError), db.begin_nested():   # the parent keeps its client
        contract.counterparty_id = other.id
        db.flush()


def test_an_amendment_is_its_own_contract_from_the_agreed_text(
        db, api, signed_deal, lawyer, seeded):
    contract, v3, _, storage = signed_deal
    r = _amend(api, contract)
    assert r.status_code == 201, r.text
    made = r.json()["data"]
    amendment = db.get(M.Contract, uuid.UUID(made["id"]))
    assert (amendment.contract_type, amendment.counterparty_id,
            amendment.governed_by_contract_id) == ("AMENDMENT", contract.counterparty_id,
                                                   contract.id)
    assert made["name"] == f"Amendment to {contract.name}"
    assert made["governed_by"]["id"] == str(contract.id)
    v1 = db.get(M.DocumentVersion, uuid.UUID(made["document_version"]["id"]))
    assert v1.file_hash == v3.file_hash and v1.doc_metadata["copy_of"] == str(v3.id)
    clauses, status, _ = effective.effective_clauses(db, v1.id)
    assert status == effective.APPLIED                    # the effective text, copied
    assert db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.CONTRACT_AMENDMENT_CREATED,
        M.AuditEvent.entity_id == amendment.id)).scalar_one()
    # the contract lists it; never an amendment of the amendment
    shown = api.get(f"{V1}/contracts/{contract.id}").json()["data"]
    assert [a["id"] for a in shown["amendments"]] == [str(amendment.id)]
    assert "governed_by" not in shown
    again = _amend(api, amendment)
    assert again.status_code == 409 and "never another amendment" in again.json()[
        "error"]["message"]
    # readability: someone who reads the amendment but not the contract sees no link,
    # and the contract's text is the same 404 as a contract that does not exist
    reader = make_user(db)
    grant_role(db, reader, P.ROLE_USER)
    amendment.owner_id = reader.id
    db.flush()
    sign_in(api, db, reader)
    mine = api.get(f"{V1}/contracts/{amendment.id}").json()["data"]
    assert "governed_by" not in mine and mine["amendments"] == []
    hidden = api.get(f"{V1}/contracts/{amendment.id}/effective")
    unknown = api.get(f"{V1}/contracts/{uuid.uuid4()}/effective")
    assert hidden.status_code == unknown.status_code == 404
    def said(r):
        return {k: v for k, v in r.json()["error"].items() if k != "request_id"}
    assert said(hidden) == said(unknown)
    assert _amend(api, contract).status_code == 404


def test_prepare_amendment_needs_an_approved_amendment_template(
        db, api, signed_deal, lawyer):
    contract, _, _, storage = signed_deal
    amendment = db.get(M.Contract, uuid.UUID(_amend(api, contract).json()["data"]["id"]))
    v1 = db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == amendment.id)).scalar_one()
    # a fresh amendment, v1 only: the missing template is what it says, first
    assert [b["code"] for b in api.get(f"{V1}/contracts/{amendment.id}/package").json()[
        "data"]["blockers"]] == ["NO_AMENDMENT_TEMPLATE"]
    _returned(db, api, amendment, v1, storage)
    dry = api.get(f"{V1}/contracts/{amendment.id}/package").json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["NO_AMENDMENT_TEMPLATE"]
    r = api.post(f"{V1}/contracts/{amendment.id}/package",
                 json={"expected_entries_sha256": "0" * 64})
    assert r.status_code == 409
    assert r.json()["error"] == {**r.json()["error"], "code": "NO_AMENDMENT_TEMPLATE",
                                 "message": "No approved amendment template yet."}


def _returned(db, api, amendment, v1, storage):
    """The client's amendment: 4.1 changed once more, answered (no standard measures it:
    the holder's answer)."""
    from urllib.parse import quote
    _ingest(db, Path(storage.root).parent, amendment, _edited(
        storage.get(v1.storage_key),
        "Clause C.1 text with Placeholder Term Two, as the client asks.",
        "Clause C.1 text with Placeholder Term Two, as amended."), "CLIENT_MODIFIED")
    url = f"{V1}/contracts/{amendment.id}/changes"
    rows = api.get(url).json()["data"]["changes"]
    assert [(r["kind"], r["clause"]["number"], r["in_package"]) for r in rows] == [
        ("MODIFIED", "4.1", "replace")]
    assert api.post(f"{url}/{quote(rows[0]['row_key'], safe='')}/answers", json={
        "answer": "accept_theirs", "expected_version": 0, "reason": "Agreed"}
    ).status_code == 201


def _signed_amendment(db, api, signed_deal, lawyer, sc_template):
    """An amendment made from the agreed text, prepared with a test AMENDMENT template
    (the reference frame, approved inside the test) and signed on its own record."""
    contract, _, _, storage = signed_deal
    amendment = db.get(M.Contract, uuid.UUID(_amend(api, contract).json()["data"]["id"]))
    a1 = db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == amendment.id)).scalar_one()
    _returned(db, api, amendment, a1, storage)
    snapshot = db.execute(select(M.ConfigurationSnapshot)).scalars().first()
    db.add(M.TemplateVersion(           # a test row: the approved reference frame
        template_key="TEST.AMENDMENT", version=1, status="PUBLISHED", doc_type="AMENDMENT",
        layout={"title": "Amendment", "special_conditions": {
            "frame": sc_template.layout["special_conditions"]["frame"]}},
        clauses=[], variables=[], annexures=[], assets={}, source={}, content_hash="0" * 64,
        checked_snapshot_id=snapshot.id, created_by=lawyer.id, published_by=lawyer.id))
    db.flush()
    a3 = _package(db, api, amendment)
    return amendment, a1, a3, _sign(db, api, amendment, a3, storage)


def test_the_text_in_force_is_the_contract_and_its_signed_amendments(
        db, api, signed_deal, lawyer, sc_template):
    """R-9/R-11: the amendment is prepared (here with a test AMENDMENT template), reviewed,
    stamped and signed on its own record; the contract's effective text then reads its
    entry, with the original beside it."""
    contract, v3, v4, storage = signed_deal
    before = api.get(f"{V1}/contracts/{contract.id}/effective").json()["data"]
    assert before["original"]["read"] == effective.APPLIED
    assert before["amendments"] == []
    assert before["current"]["clauses"] == before["original"]["clauses"]
    amendment, a1, a3, signed = _signed_amendment(db, api, signed_deal, lawyer, sc_template)
    assert [e["target"]["number"] for e in a3.doc_metadata["special_conditions"][
        "entries"]] == ["4.1", "4.2", "5"]           # cumulative: the contract as amended
    # its own record; the contract's stays sealed as it was
    own = db.execute(select(M.Execution).where(M.Execution.contract_id == amendment.id)
                     ).scalars().all()
    assert own and own[-1].signed_document_version_id == signed.id
    assert db.execute(select(M.Execution).where(M.Execution.contract_id == contract.id)
                      .order_by(M.Execution.version_number.desc())).scalars().first(
                      ).signed_document_version_id == v4.id
    now = api.get(f"{V1}/contracts/{contract.id}/effective").json()["data"]
    assert [a["applied"] for a in now["amendments"]] == [True]
    four = next(u for u in now["current"]["clauses"] if u["number"] == "4.1")
    assert four["text"] == "Clause C.1 text with Placeholder Term Two, as amended."
    assert four["original"] == \
        "Clause C.1 text with Placeholder Term Two, as the client asks."
    assert all("original" not in u for u in now["current"]["clauses"]
               if u["number"] != "4.1")
    assert api.get(f"{V1}/contracts/{amendment.id}/effective").json()["data"] == now
    # an amendment not made from the text in force stops the chain — never a guess
    a1.doc_metadata = {**a1.doc_metadata, "copy_of": str(uuid.uuid4())}
    db.flush()
    stopped = api.get(f"{V1}/contracts/{contract.id}/effective").json()["data"]["current"]
    assert stopped["read"] == effective.NOT_APPLIED and "clauses" not in stopped
    assert "not made from the text in force" in stopped["reason"]


def test_an_unreadable_amendment_is_never_named_nor_copied(
        db, api, signed_deal, lawyer, sc_template):
    """SEC-07: the signed amendment in force passes to someone the caller cannot read.
    A new amendment then copies nothing — said in the one sentence every start-empty
    case uses — and a broken chain says "An amendment", never its name."""
    from legalmind.api.routers.amendments import NOT_COPIED
    contract = signed_deal[0]
    amendment, a1, _, _ = _signed_amendment(db, api, signed_deal, lawyer, sc_template)
    amendment.name = "Secret amendment name"
    amendment.owner_id = make_user(db).id
    db.flush()
    assert api.get(f"{V1}/contracts/{amendment.id}").status_code == 404
    made = _amend(api, contract).json()["data"]
    assert made["document_version"] is None and made["starts_empty"] == NOT_COPIED
    a1.doc_metadata = {**a1.doc_metadata, "copy_of": str(uuid.uuid4())}
    db.flush()
    now = api.get(f"{V1}/contracts/{contract.id}/effective").json()["data"]
    assert now["current"]["reason"].startswith("An amendment: ")
    assert "Secret" not in str(now)


def test_a_trigger_refusal_on_an_edit_is_a_409(db, api, signed_deal, lawyer):
    contract = signed_deal[0]
    amendment = _amend(api, contract).json()["data"]
    r = api.patch(f"{V1}/contracts/{amendment['id']}", json={"contract_type": "MSA"})
    assert r.status_code == 409
    other = M.Counterparty(name="Client B", created_by=lawyer.id)
    db.add(other)
    db.flush()
    r = api.patch(f"{V1}/contracts/{contract.id}", json={"counterparty_id": str(other.id)})
    assert r.status_code == 409 and "keeps its client and type" in r.json()["error"][
        "message"]


def test_an_order_form_is_no_amendment_and_no_chain_forms(db, api, signed_deal, lawyer):
    """`_children` lists amendments only; and a contract that already governs another is
    never made governed itself — so no chain forms in either order."""
    contract = signed_deal[0]

    def row(**kw):
        c = M.Contract(owner_id=lawyer.id, name="c", status=E.ContractStatus.DRAFT,
                       counterparty_id=contract.counterparty_id, **kw)
        db.add(c)
        db.flush()
        return c

    order = row(contract_type="ORDER_FORM", governed_by_contract_id=contract.id)
    assert api.get(f"{V1}/contracts/{contract.id}").json()["data"]["amendments"] == []
    db.add(M.DocumentVersion(       # the order form signed before the signing step
        contract_id=order.id, version_number=1, original_filename="po.pdf",
        mime_type="application/pdf", file_size_bytes=1, file_hash="h", storage_key="k",
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=lawyer.id,
        doc_metadata={"version_role": "FINAL_SIGNED"}))
    free = row(contract_type="ORDER_FORM")
    db.add(M.DocumentVersion(
        contract_id=free.id, version_number=1, original_filename="po.pdf",
        mime_type="application/pdf", file_size_bytes=1, file_hash="h", storage_key="k2",
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=lawyer.id,
        doc_metadata={"version_role": "FINAL_SIGNED"}))
    db.flush()
    row(contract_type="AMENDMENT", governed_by_contract_id=free.id)   # free governs one
    with pytest.raises(DBAPIError, match="never itself governed"), db.begin_nested():
        free.governed_by_contract_id = contract.id
        db.flush()
