"""Key Obligations — descriptive extraction, mechanically kept that way.

Generation is faked at the single seam. What these tests pin: only well-formed,
grounded, judgment-free lines are persisted; the descriptive/judgment boundary
is the guardrail's, not the prompt's; extraction is idempotent-by-refusal on an
immutable version; failure records a FAILED run so "never extracted" and
"extracted, nothing found" stay distinguishable; and the endpoints sit behind
the normal Guard chain with `finding.view`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from legalmind import config
from legalmind.assist import generation, guardrails, obligations
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME
from tests.test_ingestion import build_docx

PARAGRAPHS = [
    "3. Payment",
    "The Customer shall pay all fees within thirty days of the invoice date.",
    "4. Support",
    "The Provider shall respond to support requests within one business day.",
]


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


@pytest.fixture
def uploaded(db, storage, user):
    contract = M.Contract(owner_id=user.id, name="Obligations MSA",
                          contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=user.id, data=build_docx(PARAGRAPHS),
                             filename="msa.docx", declared_mime=DOCX_MIME)
    return contract, result.document_version


def _fake_raw(monkeypatch, text_out):
    def fake(prompt, *, prompt_version, environment, request_id=None,
             evidence_count=None, max_output_tokens=1024):
        return generation.GenerationResult(
            text=text_out, model="fake-model@test", prompt_version=prompt_version,
            payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(obligations.generation, "generate_raw", fake)


# ==========================================================================
# The guardrail — a judgment is not an obligation
# ==========================================================================
@pytest.mark.parametrize("line,judgment", [
    ("The Customer shall pay all fees within thirty days", False),
    ("This clause complies with our standard", True),
    ("The cap is an unacceptable risk", True),
    ("We recommend accepting this provision", True),
    ("The provision deviates from the company position", True),
])
def test_judgment_language_is_detected(line, judgment):
    assert guardrails.is_judgment_language(line) is judgment


# ==========================================================================
# Parsing + persistence — only well-formed, grounded, judgment-free lines
# ==========================================================================
def test_grounded_descriptive_lines_are_persisted(db, uploaded, monkeypatch):
    _, version = uploaded
    _fake_raw(monkeypatch,
              "PARTY: Customer | OBLIGATION: Pay all fees within thirty days of "
              "the invoice date. | [1]\n"
              "PARTY: Provider | OBLIGATION: Respond to support requests within "
              "one business day. | [2]\n"
              # Judgment vocabulary — must be discarded by the guardrail:
              "PARTY: Customer | OBLIGATION: This clause is an unacceptable "
              "risk. | [1]\n"
              # Ungrounded marker — must be discarded:
              "PARTY: Customer | OBLIGATION: Provide quarterly reports. | [99]\n"
              # Malformed — must be discarded:
              "The Customer also does other things.")
    result = obligations.extract_obligations(db, document_version_id=version.id)
    assert result.extracted is True
    assert [o.party_label for o in result.obligations] == ["Customer", "Provider"]

    payload = obligations.read_obligations(db, version.id)
    assert payload["extracted"] is True
    labels = {g["party_label"] for g in payload["groups"]}
    assert labels == {"Customer", "Provider"}
    for group in payload["groups"]:
        for item in group["items"]:
            assert item["evidence_id"], "every stored obligation is grounded"


def test_no_obligation_is_ever_a_finding_or_axis_value(db, uploaded, monkeypatch):
    """The assist lane writes only its own schema — nothing in the locked
    findings/evaluations tables moves."""
    _, version = uploaded
    _fake_raw(monkeypatch,
              "PARTY: Customer | OBLIGATION: Pay all fees within thirty days. | [1]")
    before = db.execute(select(M.Finding)).scalars().all()
    obligations.extract_obligations(db, document_version_id=version.id)
    after = db.execute(select(M.Finding)).scalars().all()
    assert len(before) == len(after) == 0


def test_extraction_is_idempotent_by_refusal(db, uploaded, monkeypatch):
    _, version = uploaded
    _fake_raw(monkeypatch,
              "PARTY: Customer | OBLIGATION: Pay all fees within thirty days. | [1]")
    first = obligations.extract_obligations(db, document_version_id=version.id)
    assert first.extracted and len(first.obligations) == 1

    calls = []
    monkeypatch.setattr(obligations.generation, "generate_raw",
                        lambda *a, **k: calls.append(1))
    second = obligations.extract_obligations(db, document_version_id=version.id)
    assert second.extracted is True
    assert not calls, "an immutable version's completed extraction is never redone"


def test_a_refusal_records_a_failed_run_and_stays_not_extracted(db, uploaded,
                                                                monkeypatch):
    _, version = uploaded

    def refuse(*a, **k):
        raise generation.GenerationRefused("gate closed")
    monkeypatch.setattr(obligations.generation, "generate_raw", refuse)
    result = obligations.extract_obligations(db, document_version_id=version.id)
    assert result.extracted is False
    assert result.error_code == "GenerationRefused"

    schema = config.assist_schema()
    status = db.execute(text(f"""
        SELECT status FROM "{schema}".obligation_extraction_runs
         WHERE document_version_id = :d
    """), {"d": version.id}).scalar_one()
    assert status == "FAILED"
    assert obligations.read_obligations(db, version.id)["extracted"] is False


def test_none_reply_is_extracted_with_no_groups(db, uploaded, monkeypatch):
    """"Extracted, nothing found" is a COMPLETED state distinguishable from
    "never extracted"."""
    _, version = uploaded
    _fake_raw(monkeypatch, "NONE")
    result = obligations.extract_obligations(db, document_version_id=version.id)
    assert result.extracted is True and result.obligations == []
    payload = obligations.read_obligations(db, version.id)
    assert payload == {"extracted": True, "groups": []}


# ==========================================================================
# The endpoints — Guard chain, finding.view
# ==========================================================================
def test_endpoints_extract_and_read(api, db, seeded, user, storage, monkeypatch):
    from tests.conftest import grant_role, sign_in

    grant_role(db, user, "USER")
    sign_in(api, db, user)
    created = api.post("/api/v1/contracts",
                       json={"name": "Obligations", "contract_type": "MSA"})
    contract_id = created.json()["data"]["id"]
    up = api.post(f"/api/v1/contracts/{contract_id}/document-versions",
                  content=build_docx(PARAGRAPHS),
                  headers={"content-type": DOCX_MIME, "x-filename": "msa.docx"})
    version_id = up.json()["data"]["document_version"]["id"]

    _fake_raw(monkeypatch,
              "PARTY: Customer | OBLIGATION: Pay all fees within thirty days. | [1]")
    posted = api.post(f"/api/v1/document-versions/{version_id}/extract-obligations")
    assert posted.status_code == 200
    assert posted.json()["data"]["extracted"] is True

    got = api.get(f"/api/v1/document-versions/{version_id}/obligations")
    assert got.status_code == 200
    payload = got.json()["data"]
    assert payload["extracted"] is True
    assert payload["groups"][0]["party_label"] == "Customer"


def test_endpoints_are_404_for_an_invisible_version(api, db, seeded, user, storage):
    from tests.conftest import grant_role, make_user, sign_in

    owner = make_user(db)
    grant_role(db, owner, "USER")
    grant_role(db, user, "USER")
    contract = M.Contract(owner_id=owner.id, name="Not yours",
                          contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=owner.id, data=build_docx(PARAGRAPHS),
                             filename="msa.docx", declared_mime=DOCX_MIME)
    version_id = result.document_version.id

    sign_in(api, db, user)
    assert api.post(
        f"/api/v1/document-versions/{version_id}/extract-obligations"
    ).status_code == 404
    assert api.get(
        f"/api/v1/document-versions/{version_id}/obligations"
    ).status_code == 404
