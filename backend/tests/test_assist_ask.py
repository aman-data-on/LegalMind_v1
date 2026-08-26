"""The ask flow — retrieval gate, sufficiency, verification, refusal, persistence.

Generation is faked at the single interface (`AM-26` r1 makes that the seam), so these
tests cover everything AROUND the model: the gate refusing, the sufficiency check
keeping the model uncalled, citation verification rejecting ungrounded output, the
identical refusal wording, and the audit trail a reviewer needs to reconstruct any of
it. No test here talks to a network; `test_import_boundaries.py` guarantees nothing
else in the package can either.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import embedding_runtime, generation, guardrails, service
from legalmind.assist.calibration import gate_is_open
from legalmind.assist.indexing import index_document_version
from legalmind.assist.state import REFUSAL_TEXT, AssistAnswerState
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME
from tests.test_ingestion import build_docx

PARAGRAPHS = [
    "17.2 Limitation of Liability",
    "Neither party's aggregate liability under this Agreement shall exceed the total "
    "fees paid in the twelve months immediately preceding the event giving rise to "
    "the claim, save in respect of death or personal injury caused by negligence.",
    "22. Termination for Convenience",
    "Either party may terminate this Agreement for convenience on ninety days prior "
    "written notice to the other party.",
]


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


@pytest.fixture
def indexed_contract(db, storage, user):
    contract = M.Contract(owner_id=user.id, name="Ask MSA", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=user.id, data=build_docx(PARAGRAPHS),
                             filename="msa.docx", declared_mime=DOCX_MIME)
    index_document_version(db, result.document_version.id)
    return contract, result.document_version


def _conversation(db, user, contract):
    return service.create_conversation(db, user_id=user.id, contract_id=contract.id)


# ==========================================================================
# The calibrated gate as a pure function
# ==========================================================================
def test_the_gate_refuses_when_nothing_matched():
    assert gate_is_open(lexical_hit=False, vector_scores=[]) is False


def test_a_lexical_hit_opens_the_gate_regardless_of_vectors():
    """Measured: lexical refuses 13/13 unanswerable questions on its own, so a
    lexical hit is trustworthy evidence whatever the vector side thinks."""
    assert gate_is_open(lexical_hit=True, vector_scores=[]) is True
    assert gate_is_open(lexical_hit=True, vector_scores=[0.1, 0.09]) is True


def test_a_flat_vector_profile_stays_closed():
    """The calibrated PEAK_MARGIN: a top hit that does not stand out from the field
    is a nearest neighbour, not evidence — the exact failure dense retrieval has."""
    assert gate_is_open(False, [0.62, 0.61, 0.60, 0.61, 0.59]) is False


def test_a_peaked_vector_profile_above_the_floor_opens():
    assert gate_is_open(False, [0.72, 0.42, 0.40, 0.38]) is True


def test_below_the_floor_never_opens_however_peaked():
    assert gate_is_open(False, [0.49, 0.10, 0.05]) is False


# ==========================================================================
# Citation verification as a pure function (AM-28 r2: no prompt, no model)
# ==========================================================================
CHUNKS = [
    "Neither party's aggregate liability shall exceed the total fees paid in the "
    "twelve months immediately preceding the claim.",
    "Either party may terminate for convenience on ninety days written notice.",
]


def test_a_grounded_cited_answer_passes():
    answer = ("The aggregate liability is capped at the total fees paid in the "
              "twelve months preceding the claim [1].")
    v = guardrails.verify_answer(answer, CHUNKS)
    assert v.passed and v.state is AssistAnswerState.ANSWERED
    assert any(c.grounded and c.chunk_index == 1 for c in v.citations)


def test_an_uncited_sentence_fails_verification():
    v = guardrails.verify_answer("The cap is twelve months of fees.", CHUNKS)
    assert not v.passed and v.state is AssistAnswerState.CLAIM_UNSUPPORTED
    assert any("no citation" in f for f in v.failures)


def test_a_citation_to_a_nonexistent_chunk_fails():
    v = guardrails.verify_answer("The cap is twelve months of fees [7].", CHUNKS)
    assert not v.passed
    assert any("does not exist" in f for f in v.failures)


def test_a_fabricated_claim_with_a_real_citation_fails_grounding():
    """The near-miss case the retrieval gate structurally cannot catch — measured,
    not assumed. The citation exists; the CONTENT does not ground in it."""
    answer = ("The customer must maintain comprehensive cyber insurance of five "
              "million dollars [1].")
    v = guardrails.verify_answer(answer, CHUNKS)
    assert not v.passed
    assert any("does not ground" in f for f in v.failures)


def test_the_models_own_not_found_becomes_evidence_insufficient():
    v = guardrails.verify_answer("NOT FOUND", CHUNKS)
    assert v.state is AssistAnswerState.EVIDENCE_INSUFFICIENT
    assert not v.failures


def test_guardrails_import_no_model_and_no_prompt():
    """`AM-28` r2, verbatim: tested independently of prompt and model code, and does
    not import them."""
    import ast
    import pathlib

    source = pathlib.Path(guardrails.__file__).read_text()
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {m for m in imported
                 if "generation" in m or "onnx" in m or "embedding" in m}
    assert not forbidden, f"guardrails imports model/prompt code: {forbidden}"


# ==========================================================================
# The ask flow end to end (generation faked at the single seam)
# ==========================================================================
def _fake_generation(monkeypatch, text_out):
    def fake(question, evidence, *, environment, request_id=None):
        return generation.GenerationResult(
            text=text_out, model="fake-model@test", prompt_version="test-1",
            payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(service.generation, "generate", fake)


def test_an_answerable_question_is_answered_with_citations(db, user, indexed_contract,
                                                           monkeypatch):
    contract, version = indexed_contract
    embedding_runtime.reset_for_tests()
    _fake_generation(monkeypatch,
                     "The aggregate liability shall not exceed the total fees paid "
                     "in the twelve months immediately preceding the claim [1].")
    conversation = _conversation(db, user, contract)
    outcome = service.ask(db, conversation_id=conversation,
                          document_version_id=version.id,
                          question='"aggregate liability" twelve months')
    assert outcome.answer_state is AssistAnswerState.ANSWERED
    assert outcome.citations, "an answered question must carry citations"
    top = outcome.citations[0]
    assert top.section_ref == "17.2" or "aggregate liability" in top.excerpt

    schema = config.assist_schema()
    persisted = db.execute(text(f"""
        SELECT a.answer_state, a.model_identity, count(c.id)
          FROM "{schema}".ai_answers a
          LEFT JOIN "{schema}".answer_citations c ON c.answer_id = a.id
         WHERE a.message_id = :m GROUP BY a.id
    """), {"m": outcome.message_id}).first()
    assert persisted[0] == "ANSWERED" and persisted[1] == "fake-model@test"
    assert persisted[2] >= 1, "verified citations must persist (AM-27)"


def test_an_unanswerable_question_refuses_without_calling_the_model(
        db, user, indexed_contract, monkeypatch):
    """`AM-29` r3's first outcome, and the calibrated gate doing its job."""
    contract, version = indexed_contract
    embedding_runtime.reset_for_tests()
    called = []
    def explode(*a, **k):
        called.append(1)
        raise AssertionError("the model must not be called when the gate is closed")
    monkeypatch.setattr(service.generation, "generate", explode)

    conversation = _conversation(db, user, contract)
    outcome = service.ask(db, conversation_id=conversation,
                          document_version_id=version.id,
                          question="zzz cryogenic sublease of maritime salvage zzz")
    assert outcome.answer_state is AssistAnswerState.NO_EVIDENCE_RETRIEVED
    assert outcome.text == REFUSAL_TEXT
    assert not called


def test_ungrounded_generation_never_reaches_the_user(db, user, indexed_contract,
                                                      monkeypatch):
    """`AM-25` r5: the model answered; verification failed; the user sees the
    refusal, not the fabrication."""
    contract, version = indexed_contract
    embedding_runtime.reset_for_tests()
    _fake_generation(monkeypatch,
                     "The customer must carry five million dollars of cyber "
                     "insurance [1].")
    conversation = _conversation(db, user, contract)
    outcome = service.ask(db, conversation_id=conversation,
                          document_version_id=version.id,
                          question='"aggregate liability" twelve months')
    assert outcome.answer_state is AssistAnswerState.CLAIM_UNSUPPORTED
    assert outcome.text == REFUSAL_TEXT
    assert "five million" not in outcome.text


def test_a_compliance_question_routes_to_the_evaluator(db, user, indexed_contract):
    """`AM-25` r4 — never answered generatively, with or without a model."""
    contract, version = indexed_contract
    conversation = _conversation(db, user, contract)
    outcome = service.ask(db, conversation_id=conversation,
                          document_version_id=version.id,
                          question="Does this liability clause meet our standard?")
    assert outcome.routed_to_evaluator
    assert "deterministic evaluator" in outcome.text


def test_every_refusal_carries_the_identical_wording(db, user, indexed_contract,
                                                     monkeypatch):
    """`AM-29` r4 — one wording for every cause, or the difference is an oracle."""
    contract, version = indexed_contract
    embedding_runtime.reset_for_tests()
    texts = set()

    outcome = service.ask(db, conversation_id=_conversation(db, user, contract),
                          document_version_id=version.id,
                          question="zzz unrelated maritime salvage zzz")
    texts.add(outcome.text)

    _fake_generation(monkeypatch, "Fabricated uncited claim about insurance.")
    outcome = service.ask(db, conversation_id=_conversation(db, user, contract),
                          document_version_id=version.id,
                          question='"aggregate liability" twelve months')
    texts.add(outcome.text)

    assert texts == {REFUSAL_TEXT}


def test_the_retrieval_run_makes_the_refusal_reconstructable(db, user,
                                                             indexed_contract):
    """Question → scores → gate decision, all persisted (`AM-27` retrieval_runs)."""
    contract, version = indexed_contract
    embedding_runtime.reset_for_tests()
    conversation = _conversation(db, user, contract)
    service.ask(db, conversation_id=conversation, document_version_id=version.id,
                question="zzz unrelated maritime salvage zzz")
    schema = config.assist_schema()
    run = db.execute(text(f"""
        SELECT r.results FROM "{schema}".retrieval_runs r
          JOIN "{schema}".messages m ON m.id = r.message_id
         WHERE m.conversation_id = :c
    """), {"c": conversation}).scalar()
    assert run["gate"]["open"] is False
    assert "lexical_hit" in run["gate"]


# ==========================================================================
# The AM-31 gate and the generation adapter's own refusals
# ==========================================================================
def test_the_am31_gate_is_closed_and_blocks_production():
    assert generation.AM31_GATE == "CLOSED"
    permitted, reason = generation.gate_permits_egress("production")
    assert not permitted and "AM-31" in reason
    permitted, _ = generation.gate_permits_egress("development")
    assert permitted


def test_generation_refuses_without_a_credential(monkeypatch):
    monkeypatch.delenv("LEGALMIND_GEMINI_API_KEY", raising=False)
    with pytest.raises(generation.GenerationRefused, match="credential"):
        generation.generate("q", ["evidence"], environment="development")


def test_generation_refuses_a_floating_model_alias(monkeypatch):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "test-not-a-secret")
    monkeypatch.setenv("LEGALMIND_GENERATION_MODEL", "gemini-flash-latest")
    with pytest.raises(generation.GenerationRefused, match="floating alias"):
        generation.generate("q", ["evidence"], environment="development")


def test_generation_refuses_a_payload_carrying_legal_position_fields(monkeypatch):
    """`AM-30` t3 — LEGAL-02 as an egress rule, screened before any network I/O."""
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "test-not-a-secret")
    monkeypatch.delenv("LEGALMIND_GENERATION_MODEL", raising=False)
    with pytest.raises(generation.GenerationRefused, match="LEGAL-02"):
        generation.generate("q", ['{"deviation_outcome": "UNACCEPTABLE"}'],
                            environment="development")


# ==========================================================================
# API level
# ==========================================================================
def test_ask_endpoint_answers_and_labels_scores_as_retrieval_scores(
        api, db, seeded, user, storage, monkeypatch):
    from tests.conftest import grant_role, sign_in

    embedding_runtime.reset_for_tests()
    grant_role(db, user, "USER")
    sign_in(api, db, user)

    created = api.post("/api/v1/contracts",
                       json={"name": "Ask API", "contract_type": "MSA"})
    contract_id = created.json()["data"]["id"]
    api.post(f"/api/v1/contracts/{contract_id}/document-versions",
             content=build_docx(PARAGRAPHS),
             headers={"content-type": DOCX_MIME, "x-filename": "msa.docx"})

    _fake_generation(monkeypatch,
                     "Termination for convenience requires ninety days prior "
                     "written notice [1].")
    conv = api.post("/api/v1/conversations", json={"contract_id": contract_id})
    assert conv.status_code == 201
    conversation_id = conv.json()["data"]["id"]

    reply = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                     json={"question": '"ninety days" termination notice'})
    assert reply.status_code == 201
    payload = reply.json()["data"]
    assert payload["answer_state"] == "ANSWERED"
    assert payload["citations"]
    citation = payload["citations"][0]
    assert "retrieval_score" in citation
    assert "confidence" not in str(payload), (
        "AI-03 item 16: no confidence figure anywhere in the answer surface")


def test_someone_elses_conversation_is_byte_identical_404(api, db, seeded, user,
                                                          storage):
    from tests.conftest import grant_role, make_user, sign_in

    grant_role(db, user, "USER")
    other = make_user(db)
    grant_role(db, other, "USER")

    sign_in(api, db, other)
    contract = api.post("/api/v1/contracts",
                        json={"name": "Other's", "contract_type": "MSA"})
    conv = api.post("/api/v1/conversations",
                    json={"contract_id": contract.json()["data"]["id"]})
    conversation_id = conv.json()["data"]["id"]

    sign_in(api, db, user)
    stolen = api.get(f"/api/v1/conversations/{conversation_id}")
    ghost = api.get(f"/api/v1/conversations/{uuid.uuid4()}")
    assert stolen.status_code == 404 and ghost.status_code == 404
    # The per-request correlation id differs by design; the established S-7/API-10
    # discipline (test_api_authz) is byte-identity after normalizing exactly it.
    import json as _json

    bodies = []
    for response in (stolen, ghost):
        body = response.json()
        body["error"]["request_id"] = "-"
        bodies.append(_json.dumps(body, sort_keys=True))
    assert bodies[0] == bodies[1], (
        "AM-25 r7: an unauthorized conversation must be indistinguishable from a "
        "nonexistent one")


def test_a_user_without_the_permission_cannot_ask(api, db, seeded, user):
    from tests.conftest import bespoke_role, grant, sign_in

    role = bespoke_role(db, "NO_ASSIST", ["contract.view"])
    grant(db, user, role)
    sign_in(api, db, user)
    response = api.post("/api/v1/conversations", json={})
    assert response.status_code == 403
