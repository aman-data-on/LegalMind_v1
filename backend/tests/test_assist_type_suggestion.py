"""Type suggestion — assist lane proposes, only a human records (owner, 2026-08-31).

Generation is faked at the single seam. What these tests pin: the parse admits only
exact Step 6 codes (no normalisation, matching `validate_document_type`); every
failure shape degrades to `confident: false`; the function writes an audit event and
NOTHING to `contracts`; and the endpoint sits behind the normal Guard chain.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from legalmind.assist import generation, type_suggestion
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME
from tests.test_ingestion import build_docx

PARAGRAPHS = [
    "MASTER SERVICES AGREEMENT",
    "This Master Services Agreement is entered into between the parties and "
    "governs the provision of services described in the applicable order forms.",
]


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


@pytest.fixture
def uploaded(db, storage, user):
    contract = M.Contract(owner_id=user.id, name="Untitled intake",
                          contract_type=None, status=E.ContractStatus.DRAFT)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=user.id, data=build_docx(PARAGRAPHS),
                             filename="acme-msa.docx", declared_mime=DOCX_MIME)
    return contract, result.document_version


def _fake_raw(monkeypatch, text_out):
    def fake(prompt, *, prompt_version, environment, request_id=None,
             evidence_count=None, max_output_tokens=1024):
        return generation.GenerationResult(
            text=text_out, model="fake-model@test", prompt_version=prompt_version,
            payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(type_suggestion.generation, "generate_raw", fake)


# ==========================================================================
# Parsing — only an exact Step 6 code is ever suggested
# ==========================================================================
def test_an_exact_code_is_confident():
    got = type_suggestion._parse("TYPE: MSA\nREASON: The title names it.")
    assert got.suggested_type == "MSA"
    assert got.confident is True
    assert got.reason == "The title names it."


@pytest.mark.parametrize("reply", [
    "TYPE: NONE\nREASON: unclear",
    "TYPE: msa\nREASON: lowercase is a near-miss, refused not upcased",
    "TYPE: MASTER SERVICES AGREEMENT\nREASON: prose",
    "This document is an MSA.",          # no TYPE: line at all
    "",
])
def test_everything_else_degrades_to_not_confident(reply):
    got = type_suggestion._parse(reply)
    assert got.suggested_type is None
    assert got.confident is False


# ==========================================================================
# The function — writes an audit event, never the contract
# ==========================================================================
def test_a_confident_suggestion_writes_audit_and_not_the_contract(
        db, user, uploaded, monkeypatch):
    contract, version = uploaded
    _fake_raw(monkeypatch, "TYPE: MSA\nREASON: The opening line names it.")

    got = type_suggestion.suggest_document_type(
        db, document_version_id=version.id)
    assert got.suggested_type == "MSA" and got.confident

    db.flush()
    db.refresh(contract)
    assert contract.contract_type is None, (
        "Q9's substance: only the human's own PATCH ever records the type")

    events = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == "assist.type_suggestion_called")).scalars().all()
    assert len(events) == 1
    after = events[0].after_state
    assert after["suggested_type"] == "MSA"
    assert after["payload_sha256"] == "0" * 64
    assert "OPENING TEXT" not in str(after), "hash only, never the payload"


def test_generation_refusal_degrades_to_not_confident(db, uploaded, monkeypatch):
    def refuse(*a, **k):
        raise generation.GenerationRefused("gate closed")
    monkeypatch.setattr(type_suggestion.generation, "generate_raw", refuse)
    _, version = uploaded
    got = type_suggestion.suggest_document_type(db, document_version_id=version.id)
    assert got == type_suggestion.NOT_CONFIDENT


def test_a_version_with_no_evidence_is_not_confident(db, user, monkeypatch):
    called = []
    monkeypatch.setattr(type_suggestion.generation, "generate_raw",
                        lambda *a, **k: called.append(1))
    contract = M.Contract(owner_id=user.id, name="Empty", contract_type=None,
                          status=E.ContractStatus.DRAFT)
    db.add(contract)
    db.flush()
    version = M.DocumentVersion(contract_id=contract.id, version_number=1,
                                original_filename="x.pdf", file_hash="0" * 64,
                                mime_type="application/pdf", file_size_bytes=1,
                                storage_key="none", uploaded_by=user.id,
                                processing_status=E.ProcessingStatus.FAILED)
    db.add(version)
    db.flush()
    got = type_suggestion.suggest_document_type(db, document_version_id=version.id)
    assert got == type_suggestion.NOT_CONFIDENT
    assert not called, "the model is never called with nothing to show it"


# ==========================================================================
# The endpoint — Guard chain, honest degradation
# ==========================================================================
def test_endpoint_suggests_for_a_visible_version(api, db, seeded, user, storage,
                                                 monkeypatch):
    from tests.conftest import grant_role, sign_in

    grant_role(db, user, "USER")
    sign_in(api, db, user)
    created = api.post("/api/v1/contracts", json={"name": "Intake"})
    contract_id = created.json()["data"]["id"]
    up = api.post(f"/api/v1/contracts/{contract_id}/document-versions",
                  content=build_docx(PARAGRAPHS),
                  headers={"content-type": DOCX_MIME, "x-filename": "acme-msa.docx"})
    version_id = up.json()["data"]["document_version"]["id"]

    _fake_raw(monkeypatch, "TYPE: MSA\nREASON: The opening line names it.")
    reply = api.post(f"/api/v1/document-versions/{version_id}/suggest-type")
    assert reply.status_code == 200
    payload = reply.json()["data"]
    assert payload == {"suggested_type": "MSA", "confident": True,
                       "reason": "The opening line names it."}


def test_endpoint_is_404_for_an_invisible_version(api, db, seeded, user, storage,
                                                  monkeypatch):
    from tests.conftest import grant_role, make_user, sign_in

    owner = make_user(db)
    grant_role(db, owner, "USER")
    grant_role(db, user, "USER")
    contract = M.Contract(owner_id=owner.id, name="Not yours",
                          contract_type=None, status=E.ContractStatus.DRAFT)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=owner.id, data=build_docx(PARAGRAPHS),
                             filename="msa.docx", declared_mime=DOCX_MIME)

    sign_in(api, db, user)
    reply = api.post(
        f"/api/v1/document-versions/{result.document_version.id}/suggest-type")
    assert reply.status_code == 404
