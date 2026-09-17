"""Authorization boundaries for the Ask lane — P1 Priority 1 (2026-09-11).

The property under test is that **every retrieval result is authorized before it
can become model context or reach a screen**, and that each isolation property
holds on its own rather than by luck of another one holding:

  document/version scope · Company Position grant · statute corpus ·
  owner and department isolation · conversation memory · replay

Two of these were NOT holding before this file existed, both on the replay path
(`GET /conversations/{id}`), which checked only that the caller created the
conversation:

  * a caller whose `legal_position.view` had been revoked still received the
    verbatim Company Position, its `standard_code` and its `source_clause`
    (`LEGAL-02`); and
  * a caller who had lost scope on the contract still received the cited clause
    excerpts.

Both are fixed by re-checking authorization at replay time, and both are pinned
below. The live ask path was already correct on every one of these and is pinned
here too, so a future change cannot quietly move the enforcement out of it.

Nothing here asserts a legal conclusion; every document is synthetic (rule 21).
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from legalmind import config
from legalmind.assist import embedding_runtime, generation, service, store
from legalmind.db import models as M
from tests.conftest import grant_role, make_user, sign_in, without_legal_position
from tests.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    _conversation,
    _ratified_positions,
    _synthetic_statute,
    indexed_contract,
    needs_embedding_model,
    storage,
)

NARROW = frozenset({"assist.ask"})


def _no_generation(monkeypatch):
    monkeypatch.setattr(generation, "generate", lambda *a, **k: (_ for _ in ()).throw(
        generation.GenerationUnavailable("off")))


def _ask(db, conv, version_id, question, permissions=USER_PERMS):
    return service.ask(db, conversation_id=conv, document_version_id=version_id,
                       question=question, permissions=permissions)


# ==========================================================================
# 1-2. Document and version scope — enforced in the SQL, not after it
# ==========================================================================
# Two of these ten cases assert that an authorized document IS retrieved and
# cited — case 1 directly, case 4c by reading the same citation back on replay.
# Both need a real hybrid hit, which needs the local embedding model; CI has no
# model provisioned, so retrieval is lexical-only there and the shape cannot
# occur (`AM-26` r5 — absence is a mode, not an error). They reuse the marker
# `test_assist_ask.py` already defines for this, rather than asserting a
# different engine. The eight WITHHOLDING cases carry no such dependency and
# run everywhere — which is the half that must never regress.
@needs_embedding_model
def test_1_an_authorized_document_is_retrieved_and_cited(db, user, indexed_contract,
                                                         monkeypatch):
    contract, version = indexed_contract
    monkeypatch.setattr(service.generation, "generate", lambda q, ev, **k:
                        generation.GenerationResult(
                            text=ev[0].split(".")[0].strip() + " [1].", model="fake",
                            prompt_version="test", payload_sha256="0" * 64, latency_ms=1))
    out = _ask(db, _conversation(db, user, contract), version.id,
               "What is the termination notice period?")
    assert out.answer_state.value == "ANSWERED" and out.citations
    schema = config.assist_schema()
    for c in out.citations:
        owner = db.execute(text(f'SELECT document_version_id FROM "{schema}".chunks '
                                'WHERE id = :i'), {"i": c.chunk_id}).scalar()
        assert str(owner) == str(version.id)


def test_2_retrieval_cannot_cross_a_document_version_boundary(db, storage, user,
                                                              monkeypatch):
    """The store layer directly: two indexed versions, and a query whose words
    appear in BOTH must still return only the version it was scoped to. Pins the
    WHERE clause rather than the API check that usually shields it."""
    from tests.test_assist_indexing import _ingested
    embedding_runtime.reset_for_tests()
    a = _ingested(db, storage, user)
    b = _ingested(db, storage, user)
    from legalmind.assist.indexing import index_document_version
    index_document_version(db, a.id)
    index_document_version(db, b.id)
    assert a.id != b.id
    schema = config.assist_schema()
    for scoped in (a, b):
        out = store.search_hybrid(db, document_version_id=scoped.id,
                                  query="termination convenience notice", embed_query=None)
        for hit in out.hits:
            owner = db.execute(text(f'SELECT document_version_id FROM "{schema}".chunks '
                                    'WHERE id = :i'), {"i": hit.chunk_id}).scalar()
            assert str(owner) == str(scoped.id), "a hit escaped its document version"
        # The heading-redirect walk is bounded by the same scope.
        for hit in out.hits:
            target = store._clause_after(db, scoped.id, hit)
            if target is not None:
                owner = db.execute(text(f'SELECT document_version_id FROM "{schema}".chunks '
                                        'WHERE id = :i'), {"i": target.chunk_id}).scalar()
                assert str(owner) == str(scoped.id), "a redirect escaped its version"


def test_2b_another_users_document_version_is_a_byte_identical_404(api, db, seeded, user,
                                                                   storage, monkeypatch):
    from tests.test_assist_indexing import _ingested
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    theirs = _ingested(db, storage, stranger)
    grant_role(db, user, "USER")
    sign_in(api, db, user)
    mine = api.post("/api/v1/contracts",
                    json={"name": "Mine", "contract_type": "MSA"}).json()["data"]["id"]
    conv = api.post("/api/v1/conversations", json={"contract_id": mine}).json()["data"]["id"]
    unknown = api.post(f"/api/v1/conversations/{conv}/messages",
                       json={"question": "anything at all?",
                             "document_version_id": str(uuid.uuid4())})
    theirs_reply = api.post(f"/api/v1/conversations/{conv}/messages",
                            json={"question": "anything at all?",
                                  "document_version_id": str(theirs.id)})
    assert unknown.status_code == theirs_reply.status_code == 404
    assert unknown.json()["error"]["message"] == theirs_reply.json()["error"]["message"]


# ==========================================================================
# 3-4. Company Positions — granted, and revoked mid-conversation
# ==========================================================================
def test_3_an_authorized_position_is_disclosed(db, user, indexed_contract, tmp_path,
                                               monkeypatch):
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    _no_generation(monkeypatch)
    out = _ask(db, _conversation(db, user, contract), version.id,
               "What is our approved position on widget handling care?")
    assert out.positions and out.positions[0]["standard_code"] == "TESTPOS-MSA-001"


def test_4_live_ask_stops_disclosing_a_position_the_moment_the_grant_is_gone(
        db, user, indexed_contract, tmp_path, monkeypatch):
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    _no_generation(monkeypatch)
    conv = _conversation(db, user, contract)
    question = "What is our approved position on widget handling care?"
    assert _ask(db, conv, version.id, question).positions
    # Same conversation, next turn, caller no longer holds the grant.
    assert _ask(db, conv, version.id, question, NARROW).positions == []


def test_4b_replay_stops_disclosing_a_position_the_grant_no_longer_covers(
        api, db, seeded, user, indexed_contract, tmp_path, monkeypatch):
    """The defect this file was written for. Owning the conversation is not the
    right to re-read what it quoted (`LEGAL-02`); the material is OMITTED, not
    nulled (`SEC-07`)."""
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    _no_generation(monkeypatch)
    grant_role(db, user, "USER")
    conv = _conversation(db, user, contract)
    assert _ask(db, conv, version.id,
                "What is our approved position on widget handling care?").positions
    db.commit()

    without_legal_position(db, user)
    db.execute(text("""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE name = 'configuration.view')"""))
    db.commit()
    sign_in(api, db, user)

    reply = api.get(f"/api/v1/conversations/{conv}")
    assert reply.status_code == 200
    turns = reply.json()["data"]["messages"]
    assert turns, "the transcript itself is still the caller's own to read"
    assert not [p for t in turns for p in t.get("positions", [])], \
        "a revoked position grant must withhold the position on replay too"


@needs_embedding_model
def test_4c_replay_withholds_clause_excerpts_once_the_contract_is_out_of_scope(
        api, db, seeded, user, indexed_contract, monkeypatch):
    contract, version = indexed_contract
    monkeypatch.setattr(service.generation, "generate", lambda q, ev, **k:
                        generation.GenerationResult(
                            text=ev[0].split(".")[0].strip() + " [1].", model="fake",
                            prompt_version="test", payload_sha256="0" * 64, latency_ms=1))
    grant_role(db, user, "USER")
    conv = _conversation(db, user, contract)
    assert _ask(db, conv, version.id, "What is the termination notice period?").citations
    db.commit()

    stranger = make_user(db)          # the deal is transferred away (AB-12 `contract.transfer`)
    contract.owner_id = stranger.id
    db.flush(); db.commit()
    sign_in(api, db, user)

    reply = api.get(f"/api/v1/conversations/{conv}")
    assert reply.status_code == 200
    turns = reply.json()["data"]["messages"]
    assert not [c for t in turns for c in t.get("citations", [])], \
        "clause excerpts must not survive losing scope on the contract"


# ==========================================================================
# 5. Statutes
# ==========================================================================
def test_5_the_statute_corpus_needs_assist_ask_and_is_otherwise_an_empty_corpus(
        db, user, tmp_path, monkeypatch):
    from legalmind.assist import statutes
    _synthetic_statute(db, tmp_path)
    permitted = statutes.search_statutes(db, query="widget handling care",
                                         permissions=USER_PERMS)
    refused = statutes.search_statutes(db, query="widget handling care",
                                       permissions=frozenset())
    assert permitted and refused == [], "the corpus must be gated by assist.ask"


# ==========================================================================
# 6-7. Multiple versions, and what deletion removes
# ==========================================================================
def test_6_each_version_answers_from_itself(db, storage, user, monkeypatch):
    from legalmind.assist.indexing import index_document_version
    from tests.test_assist_indexing import _ingested
    embedding_runtime.reset_for_tests()
    v1 = _ingested(db, storage, user)
    v2 = _ingested(db, storage, user)
    index_document_version(db, v1.id); index_document_version(db, v2.id)
    schema = config.assist_schema()
    for v in (v1, v2):
        n = db.execute(text(f'SELECT count(*) FROM "{schema}".chunks '
                            'WHERE document_version_id = :d'), {"d": v.id}).scalar()
        assert n > 0


def test_7_deleting_a_contract_removes_its_chunks_and_embeddings(db, storage, user):
    from legalmind.assist.indexing import index_document_version
    from tests.test_assist_indexing import _ingested
    version = _ingested(db, storage, user)
    index_document_version(db, version.id)
    schema = config.assist_schema()
    count = lambda: db.execute(text(  # noqa: E731
        f'SELECT count(*) FROM "{schema}".chunks WHERE document_version_id = :d'),
        {"d": version.id}).scalar()
    assert count() > 0
    contract = db.get(M.Contract, version.contract_id)
    db.delete(contract); db.flush()
    assert count() == 0, "a hard-deleted contract must leave no retrievable chunk"


# ==========================================================================
# 8. Owner and department isolation — this codebase's actual isolation unit
# ==========================================================================
def test_8_a_stranger_cannot_reach_another_owners_conversation(api, db, seeded, user,
                                                               indexed_contract):
    contract, _ = indexed_contract
    grant_role(db, user, "USER")
    conv = _conversation(db, user, contract)
    db.commit()
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    seen = api.get(f"/api/v1/conversations/{conv}")
    absent = api.get(f"/api/v1/conversations/{uuid.uuid4()}")
    assert seen.status_code == absent.status_code == 404
    assert seen.json()["error"]["message"] == absent.json()["error"]["message"]


# ==========================================================================
# 9-10. Fallback and mixed sources stay inside the caller's grants
# ==========================================================================
def test_9_fallback_consults_only_domains_the_caller_may_read(db, user, indexed_contract,
                                                              tmp_path, monkeypatch):
    _ratified_positions(db, user, tmp_path)
    _synthetic_statute(db, tmp_path)
    contract, version = indexed_contract
    _no_generation(monkeypatch)
    question = "Which colour must the quarterly invoices be printed in?"
    wide = _ask(db, _conversation(db, user, contract), version.id, question)
    narrow = _ask(db, _conversation(db, user, contract), version.id, question, NARROW)
    assert wide.domains == ("DOCUMENT", "POSITIONS", "STATUTES")
    assert narrow.domains == ("DOCUMENT", "STATUTES")   # positions never consulted
    assert narrow.positions == []


def test_10_a_mixed_source_question_keeps_each_source_in_its_own_field(
        db, user, indexed_contract, tmp_path, monkeypatch):
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    monkeypatch.setattr(service.generation, "generate", lambda q, ev, **k:
                        generation.GenerationResult(
                            text=ev[0].split(".")[0].strip() + " [1].", model="fake",
                            prompt_version="test", payload_sha256="0" * 64, latency_ms=1))
    out = _ask(db, _conversation(db, user, contract), version.id,
               "What is our approved position on widget handling care?")
    assert out.positions, "the position is carried in its own field"
    assert "Widgets shall be handled" not in (out.text or ""), \
        "position text is never merged into the generated answer (AM-32 r4)"
