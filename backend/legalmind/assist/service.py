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
import uuid
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist import (
    embedding_runtime,
    generation,
    guardrails,
    positions,
    routing,
    store,
)

# `AM-25` r4 — routed to the evaluator, never answered generatively. The screen is
# `intent.is_comparison_question` (2026-09-08): the regex it replaced passed every
# natural phrasing of the manager's own question, and each was then refused as "not
# found in the selected document" — see tests/test_assist_intent.py for the matrix.
from legalmind.assist.state import REFUSAL_TEXT, AssistAnswerState  # noqa: F401
from legalmind.observability.logs import log_event

EVALUATOR_ROUTE_TEXT = (
    "This question asks how the document stands against the organization's approved "
    "position. That comparison is made by the deterministic evaluator, not the "
    "assistant — its Findings for this document are attached below.")
EVALUATOR_NO_REVIEW_TEXT = (
    "This question asks how the document stands against the organization's approved "
    "position. That comparison is made by the deterministic evaluator, not the "
    "assistant, and no analysis has been run for this document version yet — run a "
    "Review to see its Findings.")


@dataclass(frozen=True)
class CitationView:
    chunk_id: UUID
    # The evidence row the chunk was cut from — the unit every UI highlight shares.
    evidence_id: UUID
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
    # The evaluator handoff (AM-25 r4), structured rather than prose: the latest Review
    # of this document version and its Findings by classification. READ from the
    # authoritative tables — the assist lane writes nothing there (AM-25 r2) and never
    # produces a classification of its own; it only points at ones the engine made.
    comparison: dict | None = None
    # Domain A (`AM-32` r4): the organization's ratified positions, QUOTED VERBATIM
    # with standard code + source clause, never paraphrased and never in a generation
    # payload. A separate section with its own citation grammar (`AM-32` r1).
    positions: list[dict] = field(default_factory=list)
    # The routing decision — which authorized domains were candidates (`AM-25` r6).
    domains: tuple[str, ...] = ()


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
                       outcome: store.RetrievalOutcome, *,
                       document_version_id: UUID,
                       domains: tuple[str, ...] = ("DOCUMENT",)) -> UUID:
    """The retrieval record behind the answer — `AM-27`'s `retrieval_runs`.

    Chunk ids and scores only, never text (r6), plus the gate's raw features so the
    refusal is reconstructable from the row alone, and the document version the
    retrieval was scoped to so the answer's provenance needs no inference.
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
    # `filters` is the column AM-27 describes as part of "the retrieval record
    # behind an answer: query, filters, chunk ids, scores", and the document scope
    # is the only filter this retrieval applies. Recording it here makes the
    # version an answer was read from a first-class part of the record instead of
    # something a reader has to infer from a chunk id — no new column, and no
    # document text (r6 stands: identifiers and scores only).
    # `domains` is the routing decision (2026-09-08) — which authorized sources were
    # candidates for this question — so the answer's provenance names its route.
    filters = _json.dumps({"document_version_id": str(document_version_id),
                           "domains": list(domains)})
    db.execute(text(f"""
        INSERT INTO "{schema}".retrieval_runs
            (id, message_id, query_text, filters, results, strategy_version)
        VALUES (:i, :m, :q, CAST(:f AS jsonb), CAST(:r AS jsonb), :v)
    """), {"i": run_id, "m": message_id, "q": question, "f": filters,
           "r": results, "v": outcome.strategy_version})
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
             retrieval_run_id: UUID | None, state: AssistAnswerState,
             route: routing.RoutePlan) -> AskOutcome:
    """Every refusal path converges here — one wording per candidate set, whatever
    the cause (`AM-29` r4 as amended by `AM-46`; see `routing.refusal_text`)."""
    wording = routing.refusal_text(route)
    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", wording)
    _persist_answer(db, reply_id, retrieval_run_id, state,
                    model=None, prompt_version_id=None, latency_ms=None)
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=state, text=wording,
                      domains=tuple(d.value for d in route.domains))


def _persist_position_citations(db: DBSession, answer_id: UUID,
                                hits: list[positions.PositionHit]) -> None:
    """Domain A citations — `answer_citations.position_chunk_id` (`AM-32` modified
    tables; the CHECK enforces exactly one chunk reference per row)."""
    schema = config.assist_schema()
    for ordinal, hit in enumerate(hits):
        db.execute(text(f"""
            INSERT INTO "{schema}".answer_citations
                (id, answer_id, position_chunk_id, claim_ordinal)
            VALUES (:i, :a, :c, :o)
        """), {"i": uuid.uuid4(), "a": answer_id, "c": hit.position_chunk_id,
               "o": 1000 + ordinal})


def _position_views(hits: list[positions.PositionHit]) -> list[dict]:
    return [{"position_chunk_id": str(h.position_chunk_id),
             "standard_code": h.standard_code, "document_type": h.document_type,
             "source_clause": h.source_clause, "content": h.content,
             "retrieval_score": round(h.score, 4)} for h in hits]


POSITIONS_ONLY_TEXT = ("The organization's approved position relevant to this question "
                       "is quoted below, verbatim from the ratified standard.")
POSITIONS_BESIDE_TEXT = (
    "No answer was found in the selected document. The organization's approved "
    "position relevant to this question is quoted below.")
POSITION_LIMIT = 3


def _latest_review_summary(db: DBSession, document_version_id: UUID) -> dict | None:
    """The newest Review of this version with its Finding counts by classification.

    Counts only — no Finding text, no evidence — because the caller has already been
    authorized for the CONTRACT (assist.ask), and reading a Finding needs finding.view,
    which the Review screen enforces on open. Pointing at a Review the caller can then
    open is the same disclosure the Documents list already makes.
    """
    row = db.execute(text("""
        SELECT r.id, r.status::text FROM reviews r
         WHERE r.document_version_id = :d
         ORDER BY r.created_at DESC LIMIT 1"""), {"d": document_version_id}).first()
    if row is None:
        return None
    counts = dict(db.execute(text("""
        SELECT classification::text, count(*) FROM findings
         WHERE review_id = :r GROUP BY classification"""), {"r": row[0]}).all())
    return {"review_id": str(row[0]), "review_status": row[1],
            "findings_by_classification": {k: int(v) for k, v in counts.items()}}


def ask(db: DBSession, *, conversation_id: UUID, document_version_id: UUID | None,
        question: str, permissions: frozenset[str] = frozenset(),
        request_id: str | None = None) -> AskOutcome:
    """Answer a question from the authorized sources it needs, or refuse honestly.

    The caller (the API layer) has already authorized the conversation and, when there
    is one, the document version, through the existing Guard — `AM-25` r6's
    pre-retrieval, server-side authorization — and passes the caller's RESOLVED
    permission set so `routing.plan` can exclude every domain the caller may not read
    before a single query runs. This function then keeps the scope inside every query.

    Sources are never merged (`AM-32` r1): the document is answered generatively and
    cited by page/section; the organization's positions are quoted verbatim and cited
    by standard code and source clause; a comparison question is handed to the
    deterministic evaluator's Findings. Each arrives in its own field.
    """
    question = (question or "").strip()
    ordinal = _next_ordinal(db, conversation_id)
    user_message_id = _persist_turn(db, conversation_id, ordinal, "USER", question)

    # `permissions` empty means a caller that did not pass them — the service-level
    # tests. Treat as document-only, which is exactly the pre-router behaviour.
    if not permissions:
        permissions = frozenset({"assist.ask"})
    route = routing.plan(question, has_document=document_version_id is not None,
                         permissions=permissions)
    domains = tuple(d.value for d in route.domains)
    log_event("assist.ask.routed", request_id=request_id,
              conversation_id=str(conversation_id), domains=",".join(domains),
              comparison=str(route.comparison),
              statute_shaped=str(route.statute_shaped))

    # Domain A — extractive, authorized inside the query (AM-32 r4/r5). Retrieved
    # first because it is cheap, local, and never touches the model.
    position_hits: list[positions.PositionHit] = []
    if route.has(routing.Domain.POSITIONS):
        position_hits = positions.search_positions(
            db, query=question, permissions=permissions, limit=POSITION_LIMIT)

    # AM-25 r4 — the evaluator's question, never answered generatively.
    if route.comparison:
        comparison = _latest_review_summary(db, document_version_id)
        route_text = EVALUATOR_ROUTE_TEXT if comparison else EVALUATOR_NO_REVIEW_TEXT
        reply_id = _persist_turn(db, conversation_id, ordinal + 1, "ASSISTANT",
                                 route_text)
        answer_id = _persist_answer(db, reply_id, None,
                                    AssistAnswerState.EVIDENCE_INSUFFICIENT,
                                    model=None, prompt_version_id=None, latency_ms=None)
        _persist_position_citations(db, answer_id, position_hits)
        log_event("assist.ask.routed_to_evaluator", request_id=request_id,
                  conversation_id=str(conversation_id))
        return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                          answer_state=AssistAnswerState.EVIDENCE_INSUFFICIENT,
                          text=route_text, routed_to_evaluator=True,
                          comparison=comparison, positions=_position_views(position_hits),
                          domains=domains)

    if not route.has(routing.Domain.DOCUMENT):
        # No document in scope: positions are the only thing that can answer.
        return _positions_or_refusal(db, conversation_id, user_message_id, None,
                                     position_hits, route, domains,
                                     AssistAnswerState.NO_EVIDENCE_RETRIEVED,
                                     request_id)

    retrieval = store.search_hybrid(
        db, document_version_id=document_version_id, query=question,
        embed_query=embedding_runtime.embed_query)
    run_id = _persist_retrieval(db, user_message_id, question, retrieval,
                                document_version_id=document_version_id, domains=domains)

    if not retrieval.gate_open:
        log_event("assist.ask.refused", request_id=request_id, cause="gate_closed",
                  conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.NO_EVIDENCE_RETRIEVED, request_id)

    chunk_texts = [h.content for h in retrieval.hits]
    if not guardrails.evidence_is_sufficient(chunk_texts):
        # The model is NOT called at all — AM-29 r3's second outcome, verbatim.
        log_event("assist.ask.refused", request_id=request_id, cause="insufficient",
                  conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.EVIDENCE_INSUFFICIENT, request_id)

    try:
        # Document chunks ONLY reach the model. Position text never does (AM-32 r4).
        result = generation.generate(question, chunk_texts,
                                     environment=config.environment(),
                                     request_id=request_id)
    except generation.GenerationRefused as exc:
        # Gate closed, or no credential: an operational condition, surfaced to the
        # user as the one refusal wording (r4) and logged with its real cause.
        log_event("assist.ask.refused", request_id=request_id,
                  cause="generation_refused", detail=type(exc).__name__,
                  conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.EVIDENCE_INSUFFICIENT, request_id)
    except generation.GenerationUnavailable:
        log_event("assist.ask.refused", request_id=request_id,
                  cause="generation_unavailable", level=logging.WARNING,
                  operational_failure=True, conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.EVIDENCE_INSUFFICIENT, request_id)

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
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains, state, request_id)

    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", result.text)
    answer_id = _persist_answer(db, reply_id, run_id, AssistAnswerState.ANSWERED,
                                model=result.model,
                                prompt_version_id=_prompt_version_id(db),
                                latency_ms=result.latency_ms)
    _persist_citations(db, answer_id, verification, retrieval.hits)
    _persist_position_citations(db, answer_id, position_hits)

    cited_indexes = sorted({c.chunk_index for c in verification.citations
                            if c.grounded})
    citations = [
        CitationView(
            chunk_id=retrieval.hits[i - 1].chunk_id,
            evidence_id=retrieval.hits[i - 1].evidence_id,
            page_number=retrieval.hits[i - 1].page_number,
            section_ref=retrieval.hits[i - 1].section_ref,
            excerpt=retrieval.hits[i - 1].content[:240],
            retrieval_score=retrieval.hits[i - 1].retrieval_score)
        for i in cited_indexes
    ]
    log_event("assist.ask.answered", request_id=request_id,
              conversation_id=str(conversation_id), citations=str(len(citations)),
              positions=str(len(position_hits)))
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=AssistAnswerState.ANSWERED,
                      text=result.text, citations=citations,
                      positions=_position_views(position_hits), domains=domains)


def _positions_or_refusal(db: DBSession, conversation_id: UUID, message_id: UUID,
                          run_id: UUID | None, position_hits: list, route, domains,
                          state: AssistAnswerState, request_id: str | None) -> AskOutcome:
    """The document did not answer (or there was none). If the organization's
    position does, the turn is ANSWERED extractively — `AM-32` r4's "ratified text
    quoted verbatim with its citation". Otherwise the one refusal for this route."""
    if not position_hits:
        return _refusal(db, conversation_id, message_id, run_id, state, route)
    wording = (POSITIONS_BESIDE_TEXT if route.has(routing.Domain.DOCUMENT)
               else POSITIONS_ONLY_TEXT)
    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", wording)
    answer_id = _persist_answer(db, reply_id, run_id, AssistAnswerState.ANSWERED,
                                model=None, prompt_version_id=None, latency_ms=None)
    _persist_position_citations(db, answer_id, position_hits)
    log_event("assist.ask.answered_from_positions", request_id=request_id,
              conversation_id=str(conversation_id), positions=str(len(position_hits)))
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=AssistAnswerState.ANSWERED, text=wording,
                      positions=_position_views(position_hits), domains=domains)
