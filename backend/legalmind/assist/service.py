"""The ask flow — question in, grounded answer or honest refusal out.

The pipeline, every stage of which persists its record so a reviewer can reconstruct
why LegalMind answered or refused (question → retrieved chunks → scores → gate decision
→ accepted evidence → generation input hash → verification → answer/refusal):

    authorize (caller, via Guard)                      AM-25 r6/r8
      → hybrid retrieval, gate applied inside          calibration.py, AM-25 r6
      → sufficiency check (model NOT called if weak)   AM-29 r3, guardrails
      → generation through the single interface        AM-26 r1, AM-30, AM-31
      → mechanical citation verification               AM-25 r5, guardrails
      → persist conversation/message/run/answer/citations   AM-27 tables

Two hard rules shape the routing. `AM-25` r4: a question asking whether a document
meets a standard is never answered generatively — it belongs to the deterministic
evaluator, and `_is_compliance_question` refuses it with a pointer rather than an
answer. `AM-29` r4: every refusal a user sees carries the identical wording, whatever
its cause, because a distinguishable refusal is an oracle (`AM-25` r6/r7).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist import embedding_runtime, generation, guardrails, store
from legalmind.assist.state import REFUSAL_TEXT, AssistAnswerState
from legalmind.observability.logs import log_event

# `AM-25` r4 — routed to the evaluator, never answered generatively. Deliberately a
# conservative textual screen: false positives cost a pointer to the Review screen,
# false negatives are caught again by the prompt's rule 4 and citation verification.
_COMPLIANCE_SHAPE = re.compile(
    r"\b(complian[ct]|meets? our|satisf(?:y|ies) (?:our|the) "
    r"(?:standard|polic)|acceptable to us|match(?:es)? our (?:standard|position))\b",
    re.IGNORECASE)

EVALUATOR_ROUTE_TEXT = (
    "This question asks whether a document meets an organizational standard. "
    "That determination is made by the deterministic evaluator, not the assistant — "
    "run or open a Review for this contract to see it.")


@dataclass(frozen=True)
class CitationView:
    chunk_id: UUID
    page_number: int | None
    section_ref: str | None
    excerpt: str
    retrieval_score: float


@dataclass(frozen=True)
class AskOutcome:
    conversation_id: UUID
    message_id: UUID
    answer_state: AssistAnswerState
    text: str
    citations: list[CitationView] = field(default_factory=list)
    routed_to_evaluator: bool = False


def _persist_turn(db: DBSession, conversation_id: UUID, ordinal: int,
                  role: str, content: str) -> UUID:
    schema = config.assist_schema()
    message_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".messages (id, conversation_id, ordinal, role, content)
        VALUES (:i, :c, :o, :r, :t)
    """), {"i": message_id, "c": conversation_id, "o": ordinal, "r": role, "t": content})
    return message_id


def _next_ordinal(db: DBSession, conversation_id: UUID) -> int:
    schema = config.assist_schema()
    current = db.execute(text(
        f'SELECT coalesce(max(ordinal), -1) FROM "{schema}".messages '
        'WHERE conversation_id = :c'), {"c": conversation_id}).scalar_one()
    return int(current) + 1


def create_conversation(db: DBSession, *, user_id: UUID,
                        contract_id: UUID | None) -> UUID:
    schema = config.assist_schema()
    conversation_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".conversations (id, user_id, contract_id)
        VALUES (:i, :u, :c)
    """), {"i": conversation_id, "u": user_id, "c": contract_id})
    return conversation_id


def conversation_owner(db: DBSession, conversation_id: UUID) -> UUID | None:
    schema = config.assist_schema()
    return db.execute(text(
        f'SELECT user_id FROM "{schema}".conversations WHERE id = :i'),
        {"i": conversation_id}).scalar()


def _persist_retrieval(db: DBSession, message_id: UUID, question: str,
                       outcome: store.RetrievalOutcome) -> UUID:
    """The retrieval record behind the answer — `AM-27`'s `retrieval_runs`.

    Chunk ids and scores only, never text (r6), plus the gate's raw features so the
    refusal is reconstructable from the row alone.
    """
    import json as _json

    schema = config.assist_schema()
    run_id = uuid.uuid4()
    results = _json.dumps({
        "hits": [{"chunk_id": str(h.chunk_id),
                  "score": round(h.retrieval_score, 6)} for h in outcome.hits],
        "gate": {"open": outcome.gate_open,
                 "lexical_hit": outcome.lexical_hit,
                 "vector_top_score": outcome.vector_top_score,
                 "vector_peak_gap": outcome.vector_peak_gap},
        "embedding_model": outcome.embedding_model,
    })
    db.execute(text(f"""
        INSERT INTO "{schema}".retrieval_runs
            (id, message_id, query_text, results, strategy_version)
        VALUES (:i, :m, :q, CAST(:r AS jsonb), :v)
    """), {"i": run_id, "m": message_id, "q": question, "r": results,
           "v": outcome.strategy_version})
    return run_id


def _persist_answer(db: DBSession, message_id: UUID, retrieval_run_id: UUID | None,
                    state: AssistAnswerState, *, model: str | None,
                    prompt_version_id: UUID | None, latency_ms: int | None) -> UUID:
    schema = config.assist_schema()
    answer_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".ai_answers
            (id, message_id, retrieval_run_id, answer_state, model_identity,
             prompt_version_id, latency_ms)
        VALUES (:i, :m, :r, :s, :mo, :p, :l)
    """), {"i": answer_id, "m": message_id, "r": retrieval_run_id, "s": state.value,
           "mo": model, "p": prompt_version_id, "l": latency_ms})
    return answer_id


def _prompt_version_id(db: DBSession) -> UUID:
    """Idempotently register the current prompt template — `AM-27`'s registry."""
    schema = config.assist_schema()
    existing = db.execute(text(f"""
        SELECT id FROM "{schema}".prompt_versions
         WHERE code = :c ORDER BY version_number DESC LIMIT 1
    """), {"c": generation.PROMPT_VERSION}).scalar()
    if existing:
        return existing
    prompt_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".prompt_versions (id, code, version_number, template)
        VALUES (:i, :c, 1, :t)
    """), {"i": prompt_id, "c": generation.PROMPT_VERSION,
           "t": generation.PROMPT_TEMPLATE})
    return prompt_id


def _persist_citations(db: DBSession, answer_id: UUID,
                       verification: guardrails.Verification,
                       hits: list) -> None:
    """One row per VERIFIED claim-to-chunk link — the row's existence IS the
    verification (`AM-27`: no `verified` flag exists on purpose)."""
    schema = config.assist_schema()
    seen: set[tuple[int, UUID]] = set()
    for ordinal, citation in enumerate(c for c in verification.citations if c.grounded):
        chunk_id = hits[citation.chunk_index - 1].chunk_id
        key = (citation.chunk_index, chunk_id)
        if key in seen:
            continue
        seen.add(key)
        db.execute(text(f"""
            INSERT INTO "{schema}".answer_citations
                (id, answer_id, chunk_id, claim_ordinal)
            VALUES (:i, :a, :c, :o)
            ON CONFLICT ON CONSTRAINT uq_answer_citations_claim_chunk DO NOTHING
        """), {"i": uuid.uuid4(), "a": answer_id, "c": chunk_id, "o": ordinal})


def _refusal(db: DBSession, conversation_id: UUID, message_id: UUID,
             retrieval_run_id: UUID | None, state: AssistAnswerState) -> AskOutcome:
    """Every refusal path converges here — one wording, whatever the cause (AM-29 r4)."""
    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", REFUSAL_TEXT)
    _persist_answer(db, reply_id, retrieval_run_id, state,
                    model=None, prompt_version_id=None, latency_ms=None)
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=state, text=REFUSAL_TEXT)


def ask(db: DBSession, *, conversation_id: UUID, document_version_id: UUID,
        question: str, request_id: str | None = None) -> AskOutcome:
    """Answer a question about ONE authorized document version, or refuse honestly.

    The caller (the API layer) has already authorized both the conversation and the
    document version through the existing Guard — `AM-25` r6's pre-retrieval,
    server-side authorization. This function then keeps the scope inside every query
    it runs.
    """
    question = (question or "").strip()
    ordinal = _next_ordinal(db, conversation_id)
    user_message_id = _persist_turn(db, conversation_id, ordinal, "USER", question)

    # AM-25 r4 — the evaluator's question, never answered generatively.
    if _COMPLIANCE_SHAPE.search(question):
        reply_id = _persist_turn(db, conversation_id, ordinal + 1, "ASSISTANT",
                                 EVALUATOR_ROUTE_TEXT)
        _persist_answer(db, reply_id, None, AssistAnswerState.EVIDENCE_INSUFFICIENT,
                        model=None, prompt_version_id=None, latency_ms=None)
        log_event("assist.ask.routed_to_evaluator", request_id=request_id,
                  conversation_id=str(conversation_id))
        return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                          answer_state=AssistAnswerState.EVIDENCE_INSUFFICIENT,
                          text=EVALUATOR_ROUTE_TEXT, routed_to_evaluator=True)

    retrieval = store.search_hybrid(
        db, document_version_id=document_version_id, query=question,
        embed_query=embedding_runtime.embed_query)
    run_id = _persist_retrieval(db, user_message_id, question, retrieval)

    if not retrieval.gate_open:
        log_event("assist.ask.refused", request_id=request_id, cause="gate_closed",
                  conversation_id=str(conversation_id))
        return _refusal(db, conversation_id, user_message_id, run_id,
                        AssistAnswerState.NO_EVIDENCE_RETRIEVED)

    chunk_texts = [h.content for h in retrieval.hits]
    if not guardrails.evidence_is_sufficient(chunk_texts):
        # The model is NOT called at all — AM-29 r3's second outcome, verbatim.
        log_event("assist.ask.refused", request_id=request_id, cause="insufficient",
                  conversation_id=str(conversation_id))
        return _refusal(db, conversation_id, user_message_id, run_id,
                        AssistAnswerState.EVIDENCE_INSUFFICIENT)

    try:
        result = generation.generate(question, chunk_texts,
                                     environment=config.environment(),
                                     request_id=request_id)
    except generation.GenerationRefused as exc:
        # Gate closed, or no credential: an operational condition, surfaced to the
        # user as the one refusal wording (r4) and logged with its real cause.
        log_event("assist.ask.refused", request_id=request_id,
                  cause="generation_refused", detail=type(exc).__name__,
                  conversation_id=str(conversation_id))
        return _refusal(db, conversation_id, user_message_id, run_id,
                        AssistAnswerState.EVIDENCE_INSUFFICIENT)
    except generation.GenerationUnavailable:
        log_event("assist.ask.refused", request_id=request_id,
                  cause="generation_unavailable", level=logging.WARNING,
                  operational_failure=True, conversation_id=str(conversation_id))
        return _refusal(db, conversation_id, user_message_id, run_id,
                        AssistAnswerState.EVIDENCE_INSUFFICIENT)

    # AM-30 t5 — the audit record of the egress: model, prompt version, payload
    # hash. Recorded whether or not verification later rejects the text, because the
    # call itself is what left the building. The audit table gains an event TYPE and
    # no schema change (AM-27).
    from legalmind.security import audit as audit_log

    audit_log.record(
        db, action=audit_log.ASSIST_GENERATION_CALLED, entity_type="conversation",
        entity_id=conversation_id, request_id=request_id,
        after={"model": result.model, "prompt_version": result.prompt_version,
               "payload_sha256": result.payload_sha256,
               "evidence_chunks": len(chunk_texts)})

    verification = guardrails.verify_answer(result.text, chunk_texts)
    if not verification.passed:
        # CLAIM_UNSUPPORTED or the model's own NOT FOUND — either way the generated
        # text never reaches the user (AM-25 r5).
        state = verification.state
        log_event("assist.ask.refused", request_id=request_id,
                  cause="verification", state=state.value,
                  failures=str(len(verification.failures)),
                  conversation_id=str(conversation_id))
        return _refusal(db, conversation_id, user_message_id, run_id, state)

    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", result.text)
    answer_id = _persist_answer(db, reply_id, run_id, AssistAnswerState.ANSWERED,
                                model=result.model,
                                prompt_version_id=_prompt_version_id(db),
                                latency_ms=result.latency_ms)
    _persist_citations(db, answer_id, verification, retrieval.hits)

    cited_indexes = sorted({c.chunk_index for c in verification.citations
                            if c.grounded})
    citations = [
        CitationView(
            chunk_id=retrieval.hits[i - 1].chunk_id,
            page_number=retrieval.hits[i - 1].page_number,
            section_ref=retrieval.hits[i - 1].section_ref,
            excerpt=retrieval.hits[i - 1].content[:240],
            retrieval_score=retrieval.hits[i - 1].retrieval_score)
        for i in cited_indexes
    ]
    log_event("assist.ask.answered", request_id=request_id,
              conversation_id=str(conversation_id), citations=str(len(citations)))
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=AssistAnswerState.ANSWERED,
                      text=result.text, citations=citations)
