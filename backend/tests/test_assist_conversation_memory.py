"""Conversation memory for Ask (2026-09-10) — bounded, questions-only, retrieval-first.

A follow-up ("what about clause 17.2?") is resolved by the requester's own earlier
questions in the SAME conversation: they widen the retrieval query and are listed to the
model as context. What they never do is the subject of most tests here:

  - add evidence — every chunk is retrieved fresh for the current question, inside the
    same document-version scope the request named;
  - widen authorization — positions and statutes are searched with the caller's LIVE
    permission set, whatever an earlier turn was allowed to see;
  - carry an earlier ANSWER, a position or a statute section into the payload
    (`AM-30` t2/t3, `AM-32` r4) — only the requester's own questions travel;
  - cross a conversation boundary.

Generation is faked at the single seam; retrieval is pinned where the test is about the
flow rather than the ranking (the same technique `test_assist_ask` uses).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import generation, service, store
from tests.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    _conversation,
    _ratified_positions,
    indexed_contract,
    storage,
)

FIRST = "What is the termination notice period?"
FOLLOW_UP = "What about clause 17.2?"


def _capturing_generation(monkeypatch):
    """A fake `generate` that records every call — question, evidence and the prior
    questions it was given — and answers with the first sentence of the first excerpt,
    which is grounded by construction."""
    calls: list[dict] = []

    def fake(question, evidence, *, environment, request_id=None, prior_questions=()):
        calls.append({"question": question, "evidence": list(evidence),
                      "prior": list(prior_questions)})
        return generation.GenerationResult(
            text=evidence[0].split(".")[0].strip() + " [1].", model="fake",
            prompt_version="test", payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(service.generation, "generate", fake)
    return calls


def _pinned_retrieval(monkeypatch, db, version_id, *, open_=True, needle="terminate"):
    """`search_hybrid` returning the one indexed chunk containing `needle`, and
    recording the query and the version it was asked to search."""
    seen: list[dict] = []
    row = db.execute(text(
        f'SELECT id, evidence_id, content FROM "{config.assist_schema()}".chunks '
        'WHERE document_version_id = :d AND content ILIKE :n ORDER BY ordinal LIMIT 1'),
        {"d": version_id, "n": f"%{needle}%"}).first()
    hit = store.SearchHit(chunk_id=row[0], evidence_id=row[1], content=row[2],
                          page_number=1, section_number=None, section_title=None,
                          source_type="NATIVE_TEXT", retrieval_score=0.9)

    def fake(db_, *, document_version_id, query, embed_query, limit=None):
        seen.append({"query": query, "document_version_id": document_version_id})
        return store.RetrievalOutcome(
            hits=[hit] if open_ else [], gate_open=open_, lexical_hit=open_,
            vector_top_score=None, vector_peak_gap=None, strategy_version="pinned",
            embedding_model=None)
    monkeypatch.setattr(service.store, "search_hybrid", fake)
    return seen


def _run_for(db, conversation_id, ordinal):
    """The retrieval run recorded for the USER turn at `ordinal`."""
    schema = config.assist_schema()
    return db.execute(text(f"""
        SELECT r.query_text, r.filters FROM "{schema}".retrieval_runs r
          JOIN "{schema}".messages m ON m.id = r.message_id
         WHERE m.conversation_id = :c AND m.ordinal = :o
    """), {"c": conversation_id, "o": ordinal}).first()


def _user_message_ids(db, conversation_id):
    schema = config.assist_schema()
    return [r[0] for r in db.execute(text(
        f'SELECT id FROM "{schema}".messages WHERE conversation_id = :c AND role = \'USER\' '
        'ORDER BY ordinal'), {"c": conversation_id}).all()]


# ==========================================================================
# The behaviour
# ==========================================================================
def test_a_follow_up_is_resolved_by_the_previous_question(db, user, indexed_contract,
                                                          monkeypatch):
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    seen = _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)

    first = service.ask(db, conversation_id=conv, document_version_id=version.id,
                        question=FIRST, permissions=USER_PERMS)
    second = service.ask(db, conversation_id=conv, document_version_id=version.id,
                         question=FOLLOW_UP, permissions=USER_PERMS)

    assert first.answer_state.value == second.answer_state.value == "ANSWERED"
    # Retrieval for the follow-up carried the earlier question's words …
    assert seen[0]["query"] == FIRST
    assert seen[1]["query"] == f"{FIRST} {FOLLOW_UP}"
    # … the model was asked the follow-up itself, with the earlier question as context …
    assert calls[1]["question"] == FOLLOW_UP
    assert calls[1]["prior"] == [FIRST]
    assert calls[0]["prior"] == []
    # … and the answer is cited against evidence retrieved for THIS turn.
    assert second.citations and second.citations[0].chunk_id == first.citations[0].chunk_id


def test_a_pronoun_follow_up_gets_the_same_treatment(db, user, indexed_contract, monkeypatch):
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question="Does the contract allow termination for convenience?",
                permissions=USER_PERMS)
    out = service.ask(db, conversation_id=conv, document_version_id=version.id,
                      question="What happens after that?", permissions=USER_PERMS)
    assert out.answer_state.value == "ANSWERED"
    assert calls[1]["prior"] == ["Does the contract allow termination for convenience?"]


def test_a_self_contained_question_is_not_expanded(db, user, indexed_contract, monkeypatch):
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    seen = _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=FIRST, permissions=USER_PERMS)
    later = "What is the liability cap under this Agreement?"
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=later, permissions=USER_PERMS)
    assert seen[1]["query"] == later
    assert calls[1]["prior"] == []
    assert _run_for(db, conv, 2).filters.get("follow_up_of") is None


def test_the_anchor_is_the_most_recent_self_contained_question(db, user, indexed_contract,
                                                               monkeypatch):
    """Bounded: a long conversation contributes the most recent question that stands on
    its own — never the whole transcript."""
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    questions = ["What is the termination notice period?",
                 "What is the liability cap under this Agreement?",
                 "Who bears the cost of insurance under the contract?",
                 "What about clause 17.2?"]
    for q in questions:
        service.ask(db, conversation_id=conv, document_version_id=version.id,
                    question=q, permissions=USER_PERMS)
    assert calls[-1]["prior"] == [questions[2]]
    ids = _user_message_ids(db, conv)
    run = _run_for(db, conv, 6)
    assert run.filters["follow_up_of"] == [str(ids[2])]
    assert run.query_text == f"{questions[2]} {questions[3]}"


def test_a_chain_of_follow_ups_keeps_its_anchor(db, user, indexed_contract, monkeypatch):
    """Measured live (2026-09-10): concatenating every earlier question flattened the
    vector and closed the gate; anchor + current opened it. So the index sees the
    anchor and the current question, and the model sees the anchor and the question
    just before — the two turns that say what "that" is."""
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    seen = _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    chain = [FIRST, "What about clause 17.2?", "Does that notice have to be in writing?"]
    for q in chain:
        service.ask(db, conversation_id=conv, document_version_id=version.id,
                    question=q, permissions=USER_PERMS)
    assert seen[1]["query"] == f"{FIRST} {chain[1]}"
    assert seen[2]["query"] == f"{FIRST} {chain[2]}"
    assert calls[2]["prior"] == [FIRST, chain[1]]
    ids = _user_message_ids(db, conv)
    assert _run_for(db, conv, 4).filters["follow_up_of"] == [str(ids[0]), str(ids[1])]


def test_a_long_earlier_question_is_clipped(db, user, indexed_contract, monkeypatch):
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    long_question = "What is the termination notice period " + "in detail " * 80 + "?"
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=long_question, permissions=USER_PERMS)
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=FOLLOW_UP, permissions=USER_PERMS)
    assert len(calls[1]["prior"][0]) <= service.PRIOR_QUESTION_CHARS


# ==========================================================================
# The boundaries
# ==========================================================================
def test_conversations_are_isolated(db, user, indexed_contract, monkeypatch):
    """A follow-up in one conversation never sees another conversation's questions —
    not in retrieval, not in the payload, not in the record."""
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    seen = _pinned_retrieval(monkeypatch, db, version.id)
    conv_a = _conversation(db, user, contract)
    conv_b = _conversation(db, user, contract)
    service.ask(db, conversation_id=conv_a, document_version_id=version.id,
                question=FIRST, permissions=USER_PERMS)
    service.ask(db, conversation_id=conv_b, document_version_id=version.id,
                question=FOLLOW_UP, permissions=USER_PERMS)
    assert seen[1]["query"] == FOLLOW_UP
    assert calls[1]["prior"] == []
    assert FIRST not in calls[1]["question"]
    assert _run_for(db, conv_b, 0).filters.get("follow_up_of") is None


def test_an_earlier_answer_never_reaches_the_model(db, user, indexed_contract, monkeypatch):
    """`AM-30` t2: the requester's question and this request's spans. The earlier
    ANSWER — generated text — is not among them, so a token only it contains must
    appear nowhere in the follow-up's payload."""
    contract, version = indexed_contract
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    calls: list[dict] = []
    marker = "ZEBRA-PLUM-ANSWER-TOKEN"

    def fake(question, evidence, *, environment, request_id=None, prior_questions=()):
        calls.append({"question": question, "evidence": list(evidence),
                      "prior": list(prior_questions)})
        # Grounded (first sentence, cited) with a marker the document does not hold.
        return generation.GenerationResult(
            text=f"{evidence[0].split('.')[0].strip()} {marker} [1].", model="fake",
            prompt_version="test", payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(service.generation, "generate", fake)

    first = service.ask(db, conversation_id=conv, document_version_id=version.id,
                        question=FIRST, permissions=USER_PERMS)
    assert first.answer_state.value == "ANSWERED" and marker in first.text
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=FOLLOW_UP, permissions=USER_PERMS)
    everything = " ".join([calls[1]["question"], *calls[1]["prior"], *calls[1]["evidence"]])
    assert marker not in everything
    assert calls[1]["prior"] == [FIRST]


def test_a_position_shown_earlier_never_enters_a_later_payload(
        db, user, indexed_contract, tmp_path, monkeypatch):
    """`AM-32` r4 across turns: the organization's position quoted beside turn one is
    not carried into turn two's generation payload by way of memory."""
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    first = service.ask(db, conversation_id=conv, document_version_id=version.id,
                        question="What is our approved position on widget handling care?",
                        permissions=USER_PERMS)
    assert first.positions and "Widgets shall be handled" in first.positions[0]["content"]
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question="What does that require of the handler?", permissions=USER_PERMS)
    everything = " ".join([calls[1]["question"], *calls[1]["prior"], *calls[1]["evidence"]])
    assert "Widgets shall be handled" not in everything


def test_memory_never_widens_what_the_caller_may_read(db, user, indexed_contract, tmp_path,
                                                      monkeypatch):
    """The earlier question asked about "our approved position" and was shown one. The
    follow-up arrives from a caller WITHOUT the grant — the position is not shown, even
    though the resolved question still names the organization."""
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    _capturing_generation(monkeypatch)
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    first = service.ask(db, conversation_id=conv, document_version_id=version.id,
                        question="What is our approved position on widget handling care?",
                        permissions=USER_PERMS)
    assert first.positions
    later = service.ask(db, conversation_id=conv, document_version_id=version.id,
                        question="What about that for the customer?",
                        permissions=frozenset({"assist.ask"}))
    assert later.positions == []
    assert "POSITIONS" not in later.domains


def test_stale_context_never_answers_from_memory(db, user, indexed_contract, monkeypatch):
    """The earlier question was answered; the follow-up's own retrieval finds nothing
    (gate closed). Memory supplies no evidence, so the model is not called and the
    turn falls through to the other sources or refuses — never an answer from what
    was said before."""
    contract, version = indexed_contract
    calls = _capturing_generation(monkeypatch)
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=FIRST, permissions=USER_PERMS)
    _pinned_retrieval(monkeypatch, db, version.id, open_=False)
    out = service.ask(db, conversation_id=conv, document_version_id=version.id,
                      question=FOLLOW_UP, permissions=USER_PERMS)
    assert out.answer_state.value != "ANSWERED"
    assert len(calls) == 1, "no generation for a turn whose retrieval found nothing"
    assert out.text.startswith("Information not found in the selected document")


def test_a_follow_up_is_retrieved_against_the_version_asked_about(api, db, seeded, user,
                                                                  monkeypatch):
    """Through the API: turn one read v1, the follow-up names v2. Retrieval runs on v2
    and the reply says so — the earlier question resolves the reference, it does not
    pin the document."""
    from tests.test_assist_ask_version_context import _two_version_contract
    _, v1, v2, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    calls = _capturing_generation(monkeypatch)
    real = store.search_hybrid
    searched: list = []

    def recording(db_, *, document_version_id, query, embed_query, limit=None):
        searched.append(str(document_version_id))
        return real(db_, document_version_id=document_version_id, query=query,
                    embed_query=embed_query, limit=limit)
    monkeypatch.setattr(service.store, "search_hybrid", recording)

    first = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                     json={"question": '"prior written notice" termination for convenience',
                           "document_version_id": v1["id"]})
    assert first.status_code == 201, first.text
    reply = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                     json={"question": "What about clause 22?", "document_version_id": v2["id"]})
    assert reply.status_code == 201, reply.text
    data = reply.json()["data"]
    assert searched == [v1["id"], v2["id"]]
    assert data["document_version_id"] == v2["id"] and data["version_number"] == 2
    if data["answer_state"] == "ANSWERED":
        schema = config.assist_schema()
        for c in data["citations"]:
            owner = db.execute(text(f'SELECT document_version_id FROM "{schema}".chunks '
                                    'WHERE id = :i'), {"i": c["chunk_id"]}).scalar_one()
            assert str(owner) == v2["id"], "every citation belongs to the version asked about"
        assert calls[-1]["prior"] == ['"prior written notice" termination for convenience']


def test_the_persisted_user_turn_is_the_raw_question(db, user, indexed_contract, monkeypatch):
    """The transcript shows what the user typed; the expansion lives on the retrieval
    run (`query_text` + `filters.follow_up_of`), where a reviewer can reconstruct it."""
    contract, version = indexed_contract
    _capturing_generation(monkeypatch)
    _pinned_retrieval(monkeypatch, db, version.id)
    conv = _conversation(db, user, contract)
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=FIRST, permissions=USER_PERMS)
    service.ask(db, conversation_id=conv, document_version_id=version.id,
                question=FOLLOW_UP, permissions=USER_PERMS)
    schema = config.assist_schema()
    turns = db.execute(text(f'SELECT content FROM "{schema}".messages WHERE conversation_id = :c '
                            "AND role = 'USER' ORDER BY ordinal"), {"c": conv}).scalars().all()
    assert turns == [FIRST, FOLLOW_UP]
    run = _run_for(db, conv, 2)
    assert run.query_text == f"{FIRST} {FOLLOW_UP}"
    assert run.filters["follow_up_of"] == [str(_user_message_ids(db, conv)[0])]


def test_the_prompt_lists_earlier_questions_as_context_not_evidence():
    """The template itself: prior questions appear under their own header, the
    evidence numbering is untouched, and a first question renders no such block."""
    captured: list[str] = []

    def fake_raw(prompt, **kwargs):
        captured.append(prompt)
        raise generation.GenerationRefused("captured")
    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(generation, "generate_raw", fake_raw)
        with _pytest.raises(generation.GenerationRefused):
            generation.generate(FOLLOW_UP, ["Either party may terminate on notice."],
                                environment="development", prior_questions=(FIRST,))
        with _pytest.raises(generation.GenerationRefused):
            generation.generate(FIRST, ["Either party may terminate on notice."],
                                environment="development")
    with_context, without = captured
    assert generation.CONTEXT_HEADER in with_context and f"- {FIRST}" in with_context
    assert with_context.index(generation.CONTEXT_HEADER) < with_context.index("EVIDENCE:")
    assert "[1] Either party" in with_context
    assert generation.CONTEXT_HEADER not in without
    assert generation.PROMPT_VERSION == "grounded-answer-2"


@pytest.mark.parametrize("field", ["acceptable_max", "deviation_outcome"])
def test_a_forbidden_field_in_an_earlier_question_is_still_screened(field):
    """`_forbidden_payload_check` screens the whole prompt, prior questions included."""
    with pytest.raises(generation.GenerationRefused):
        generation.generate("what about that?", ["Some evidence text here for the test."],
                            environment="development",
                            prior_questions=(f"what is the {field} for this?",))
