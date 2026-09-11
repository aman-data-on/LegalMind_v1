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
    intent,
    positions,
    routing,
    statutes,
    store,
)

# `AM-25` r4 — routed to the evaluator, never answered generatively. The screen is
# `intent.is_comparison_question` (2026-09-08): the regex it replaced passed every
# natural phrasing of the manager's own question, and each was then refused as "not
# found in the selected document" — see tests/test_assist_intent.py for the matrix.
from legalmind.assist.state import REFUSAL_TEXT, AssistAnswerState  # noqa: F401
from legalmind.observability.logs import log_event
from legalmind.security import permissions as P

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
    # Domain C (`AM-32` r7/r8, `AM-47`): the statute answer, generated over statute
    # evidence ONLY and cited Act + section — its own field, never merged (`AM-45` r2).
    statutes: dict | None = None


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


# Conversation memory (2026-09-10) — bounded, and questions only. Authorized by `AM-58`
# (AB-19, 2026-09-11), which amends `AM-30` t2 for exactly this addition. The comment
# here previously asserted t2 already permitted it; an audit found t2 is a closed
# allow-list naming only the question, this request's chunk spans and the prompt
# template, so the record was amended rather than the claim repeated (rule 5).
#
# The router has already established that the caller owns this conversation
# (`_visible_conversation`), so reading its earlier USER turns discloses nothing the
# caller did not write — `AM-58` r7. Earlier ASSISTANT turns are never read here
# (`AM-58` r2): an answer is not evidence, and admitting one would let generated text
# ground a later claim, which is what `AM-25` r5's verification exists to prevent.
PRIOR_TURNS_SCANNED = 4       # how far back a follow-up looks for its anchor
PRIOR_QUESTION_CHARS = 300


def _prior_questions(db: DBSession, conversation_id: UUID,
                     exclude_message_id: UUID) -> list[tuple[UUID, str]]:
    """The requester's last `PRIOR_TURNS_SCANNED` questions in THIS conversation, oldest
    first, each clipped to `PRIOR_QUESTION_CHARS`. Never another conversation's."""
    schema = config.assist_schema()
    rows = db.execute(text(f"""
        SELECT id, content FROM "{schema}".messages
         WHERE conversation_id = :c AND role = 'USER' AND id <> :m
         ORDER BY ordinal DESC LIMIT :n
    """), {"c": conversation_id, "m": exclude_message_id, "n": PRIOR_TURNS_SCANNED}).all()
    return [(r[0], (r[1] or "")[:PRIOR_QUESTION_CHARS].strip()) for r in reversed(rows)
            if (r[1] or "").strip()]


def _resolve_follow_up(prior: list[tuple[UUID, str]],
                       question: str) -> tuple[list[tuple[UUID, str]], str]:
    """The context for a follow-up: its ANCHOR — the most recent earlier question that
    stands on its own — and the question immediately before it when that differs.

    Measured live 2026-09-10 on the owner's MSA: "what is the termination notice
    period?" → "what about clause 14.3?" → "does that notice have to be in writing?"
    With every earlier question concatenated into the retrieval query the vector went
    flat and the gate closed (top 0.463); anchor + current opened it (0.612) and
    retrieved §14.1/§14.3. Intermediate follow-ups carry no content of their own, so
    they only dilute — the anchor is what the chain is about. Returns
    ``(context_turns, retrieval_query)``; the model sees the context turns, the index
    sees anchor + current.
    """
    anchors = [t for t in prior if not intent.is_follow_up(t[1])]
    anchor = anchors[-1] if anchors else prior[-1]
    context = [anchor] if anchor == prior[-1] else [anchor, prior[-1]]
    return context, f"{anchor[1]} {question}"


#: How much of a Finding's first cited passage seeds the retrieval query. Enough to
#: carry the clause's own vocabulary, short enough not to swamp the question itself.
FINDING_SEED_CHARS = 240


def _finding_seed(db: DBSession, finding_id: UUID) -> str:
    """Retrieval vocabulary for a question asked ABOUT a Finding (2026-09-11).

    "Why is this a deviation?" carries almost no retrievable content of its own, so
    without help it retrieves nothing and the reader gets a refusal about a Finding
    that is on their screen. This seeds the query with the requirement's title in
    words and the opening of the passage the Evaluation already cited, so retrieval
    lands on the clause the Finding is about.

    RETRIEVAL ONLY, and that distinction is the whole point. The seed widens the
    QUERY, which is local SQL and a local embedding; it never reaches a payload.
    `AM-30` t3 and `AM-32` r4 stand unchanged: the classification, the Rule Outcome
    and the Company Standard value are not in this string and never egress. The
    passages themselves are already-permitted contract text (`AM-30` t2), and they
    are re-retrieved through the normal scoped query rather than injected as hits,
    so authorization stays inside the retrieval (`AM-25` r6).

    Reuses `explanations.gather` rather than a second assembly of the same facts.
    """
    from legalmind.assist import explanations
    from legalmind.db import models as M
    finding = db.get(M.Finding, finding_id)
    if finding is None:
        return ""
    grounding = explanations.gather(db, finding)
    passage = grounding.passages[0][:FINDING_SEED_CHARS] if grounding.passages else ""
    return " ".join(part for part in (grounding.title, passage) if part).strip()


def create_conversation(db: DBSession, *, user_id: UUID,
                        contract_id: UUID | None) -> UUID:
    schema = config.assist_schema()
    conversation_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".conversations (id, user_id, contract_id)
        VALUES (:i, :u, :c)
    """), {"i": conversation_id, "u": user_id, "c": contract_id})
    return conversation_id


class ConversationAlreadyScoped(Exception):
    """Raised when a conversation that already has a contract is asked to take another.

    Not a permission problem and not a 404 — the caller owns this conversation and can
    see it. The router maps it to a business-rule rejection with wording that tells the
    reader what to do instead (start a new chat).
    """


def attach_contract(db: DBSession, *, conversation_id: UUID, contract_id: UUID) -> None:
    """Give a document-less conversation a document, keeping every earlier turn.

    Why this is permitted, and why it is narrow (2026-09-11). Nothing locked binds a
    conversation to a contract: `AM-27` registers `conversations` as "an assist-lane
    session" and defines no column and no cardinality, and DESIGN_DECISIONS.md's own
    note on conversation scope says "Nothing here was locked." The one-contract binding
    was the shape of the table, not a decision — so a reader who has been asking about
    the organization's standards and then attaches the agreement keeps their thread
    instead of losing it to a new chat.

    ONLY `NULL -> contract`. Re-pointing a conversation that already has one is refused:
    the earlier turns' citations carry `evidence_id`s belonging to the FIRST document's
    reading order, and silently changing the scope underneath them would leave every one
    of them pointing at a row that is no longer in the conversation's document. A second
    attachment starts a new chat, and the UI says so before it happens.

    Authorization is the router's, before this is called, and it is re-applied on every
    subsequent ask: `AM-25` r6 is about the caller's scope at retrieval time, which this
    does not touch.
    """
    schema = config.assist_schema()
    # RETURNING rather than `rowcount`: it is the same single round trip, it is
    # typed (SQLAlchemy's `Result` exposes `rowcount` only on the cursor subtype,
    # which mypy rejects here), and it says what it checks.
    updated = db.execute(text(f"""
        UPDATE "{schema}".conversations SET contract_id = :k
         WHERE id = :i AND contract_id IS NULL
        RETURNING id
    """), {"k": contract_id, "i": conversation_id}).first()
    if updated is None:
        # The row exists and is the caller's (the router established both), so the only
        # way to match nothing is that a contract is already set. Guarded in SQL rather
        # than by a read-then-write so two concurrent attaches cannot both win.
        raise ConversationAlreadyScoped(conversation_id)


def conversation_owner(db: DBSession, conversation_id: UUID) -> UUID | None:
    schema = config.assist_schema()
    return db.execute(text(
        f'SELECT user_id FROM "{schema}".conversations WHERE id = :i'),
        {"i": conversation_id}).scalar()


def _persist_retrieval(db: DBSession, message_id: UUID, question: str,
                       outcome: store.RetrievalOutcome, *,
                       document_version_id: UUID | None,
                       domains: tuple[str, ...] = ("DOCUMENT",),
                       statute_hits: list | None = None,
                       follow_up_of: list[UUID] | None = None) -> UUID:
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
        # Domain C hits — ids and scores only (r6), so the statute half of the
        # answer is reconstructable from the same row.
        "statute_hits": [{"statute_chunk_id": str(h.statute_chunk_id),
                          "score": round(h.score, 6)} for h in (statute_hits or [])],
    })
    # `filters` is the column AM-27 describes as part of "the retrieval record
    # behind an answer: query, filters, chunk ids, scores", and the document scope
    # is the only filter this retrieval applies. Recording it here makes the
    # version an answer was read from a first-class part of the record instead of
    # something a reader has to infer from a chunk id — no new column, and no
    # document text (r6 stands: identifiers and scores only).
    # `domains` is the routing decision (2026-09-08) — which authorized sources were
    # candidates for this question — so the answer's provenance names its route.
    # `follow_up_of` (2026-09-10): the earlier USER turns whose text was added to
    # this retrieval's query, so the record shows WHY `query_text` is longer than
    # the message — ids only, the text is already on those rows.
    filters_dict: dict = {"document_version_id": (str(document_version_id)
                                                  if document_version_id else None),
                          "domains": list(domains)}
    if follow_up_of:
        filters_dict["follow_up_of"] = [str(i) for i in follow_up_of]
    filters = _json.dumps(filters_dict)
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
    held = (tuple(statutes.holdings(db))
            if routing.Domain.STATUTES in route.searched else ())
    wording = routing.refusal_text(route, statute_holdings=held)
    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", wording)
    _persist_answer(db, reply_id, retrieval_run_id, state,
                    model=None, prompt_version_id=None, latency_ms=None)
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=state, text=wording,
                      domains=tuple(d.value for d in route.searched))


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


def _persist_statute_citations(db: DBSession, answer_id: UUID,
                               hits: list[statutes.StatuteHit], cited: list[int]) -> None:
    """Domain C citations — `answer_citations.statute_chunk_id`, one row per VERIFIED
    claim→section link (the same discipline as document citations)."""
    schema = config.assist_schema()
    for ordinal, index in enumerate(cited):
        db.execute(text(f"""
            INSERT INTO "{schema}".answer_citations
                (id, answer_id, statute_chunk_id, claim_ordinal)
            VALUES (:i, :a, :c, :o)
        """), {"i": uuid.uuid4(), "a": answer_id, "c": hits[index - 1].statute_chunk_id,
               "o": 2000 + ordinal})


def _statute_views(hits: list[statutes.StatuteHit], cited: list[int]) -> list[dict]:
    return [{"statute_chunk_id": str(hits[i - 1].statute_chunk_id),
             "citation": hits[i - 1].citation,
             "official_title": hits[i - 1].official_title,
             "section_number": hits[i - 1].section_number,
             "sub_section": hits[i - 1].sub_section,
             "marginal_note": hits[i - 1].marginal_note,
             "excerpt": hits[i - 1].content[:240],
             "retrieval_score": round(hits[i - 1].score, 4)} for i in cited]


def _answer_statutes(db: DBSession, conversation_id: UUID, question: str,
                     hits: list[statutes.StatuteHit], *, request_id: str | None,
                     prior_questions: list[str] | None = None) -> dict:
    """Generate over statute evidence ONLY (AM-32 r8), verify mechanically, and return
    the Domain C section — or its own refusal state. Never touches document text."""
    if not hits:
        return {"answer_state": AssistAnswerState.NO_EVIDENCE_RETRIEVED.value,
                "text": None, "citations": []}
    texts = [h.content for h in hits]
    if not guardrails.evidence_is_sufficient(texts):
        return {"answer_state": AssistAnswerState.EVIDENCE_INSUFFICIENT.value,
                "text": None, "citations": []}
    try:
        result = generation.generate(question, texts, environment=config.environment(),
                                     request_id=request_id,
                                     **_context_kwargs(prior_questions))
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        log_event("assist.ask.statutes_refused", request_id=request_id,
                  cause=type(exc).__name__, conversation_id=str(conversation_id))
        return {"answer_state": AssistAnswerState.EVIDENCE_INSUFFICIENT.value,
                "text": None, "citations": []}
    from legalmind.security import audit as audit_log

    audit_log.record(
        db, action=audit_log.ASSIST_GENERATION_CALLED, entity_type="conversation",
        entity_id=conversation_id, request_id=request_id,
        after={"model": result.model, "prompt_version": result.prompt_version,
               "payload_sha256": result.payload_sha256, "evidence_chunks": len(texts),
               "domain": "STATUTES"})
    verification = guardrails.verify_answer(result.text, texts)
    if not verification.passed:
        return {"answer_state": verification.state.value, "text": None, "citations": []}
    cited = sorted({c.chunk_index for c in verification.citations if c.grounded})
    return {"answer_state": AssistAnswerState.ANSWERED.value, "text": result.text,
            "citations": _statute_views(hits, cited), "_cited": cited,
            "_model": result.model, "_latency_ms": result.latency_ms}


def _position_views(hits: list[positions.PositionHit],
                    findings: dict[str, dict] | None = None) -> list[dict]:
    return [{"position_chunk_id": str(h.position_chunk_id),
             "standard_code": h.standard_code, "document_type": h.document_type,
             "source_clause": h.source_clause, "content": h.content,
             "retrieval_score": round(h.score, 4),
             "finding": (findings or {}).get(h.standard_code)} for h in hits]


def _findings_for_standards(db: DBSession, document_version_id: UUID | None,
                            codes: set[str],
                            permissions: frozenset[str]) -> dict[str, dict]:
    """The evaluator's EXISTING Finding for each quoted standard on the latest
    Review of this version — `{standard_code: {finding_id, classification,
    user_status}}` (owner, 2026-09-10: "Assessment: Match / Deviation / Needs
    decision, when applicable").

    READ, never produced: Ask points at a Finding the deterministic engine already
    made, the `AM-45` r4 handoff precedent; it still generates no verdict (`AM-25`
    r4). Reading a Finding needs `finding.view`, so without it the map is empty
    and the position is quoted alone — the same shape as "no Review yet".
    """
    if document_version_id is None or not codes or P.FINDING_VIEW not in permissions:
        return {}
    from legalmind.domain.enums import FindingClassification
    from legalmind.domain.user_status import user_status

    review = db.execute(text("""
        SELECT r.id FROM reviews r
         WHERE r.document_version_id = :d
         ORDER BY r.created_at DESC LIMIT 1"""), {"d": document_version_id}).first()
    if review is None:
        return {}
    rows = db.execute(text("""
        SELECT rq.code, f.id, f.classification::text
          FROM findings f
          JOIN requirement_versions rv ON rv.id = f.requirement_version_id
          JOIN requirements rq ON rq.id = rv.requirement_id
         WHERE f.review_id = :r AND rq.code = ANY(:codes)"""),
        {"r": review[0], "codes": sorted(codes)}).all()
    # The word follows the Finding's own classification (AM-56) — the same
    # projection `evaluation.user_status.by_finding` applies, read from `domain`.
    return {code: {"finding_id": str(fid), "classification": cls,
                   "user_status": user_status(FindingClassification(cls))}
            for code, fid, cls in rows}


POSITIONS_ONLY_TEXT = ("The organization's approved position relevant to this question "
                       "is quoted below, verbatim from the ratified standard.")
POSITIONS_BESIDE_TEXT = (
    "No answer was found in the selected document. The organization's approved "
    "position relevant to this question is quoted below.")
POSITION_LIMIT = 3


def _latest_review_summary(db: DBSession,
                           document_version_id: UUID | None) -> dict | None:
    """The newest Review of this version with its Finding counts by classification.

    Counts only — no Finding text, no evidence — because the caller has already been
    authorized for the CONTRACT (assist.ask), and reading a Finding needs finding.view,
    which the Review screen enforces on open. Pointing at a Review the caller can then
    open is the same disclosure the Documents list already makes.
    """
    if document_version_id is None:      # a document-less conversation
        return None
    row = db.execute(text("""
        SELECT r.id, r.status::text FROM reviews r
         WHERE r.document_version_id = :d
         ORDER BY r.created_at DESC LIMIT 1"""), {"d": document_version_id}).first()
    if row is None:
        return None
    counts: dict[str, int] = {
        str(k): int(n) for k, n in db.execute(text("""
        SELECT classification::text, count(*) FROM findings
         WHERE review_id = :r GROUP BY classification"""), {"r": row[0]}).all()}
    return {"review_id": str(row[0]), "review_status": row[1],
            "findings_by_classification": {k: int(v) for k, v in counts.items()}}


def ask(db: DBSession, *, conversation_id: UUID, document_version_id: UUID | None,
        question: str, permissions: frozenset[str] = frozenset(),
        request_id: str | None = None,
        finding_id: UUID | None = None) -> AskOutcome:
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

    # Conversation memory (2026-09-10). A follow-up — "what about clause 7?" — is
    # resolved by the requester's own earlier questions: they widen the RETRIEVAL
    # query and the routing input, and they are listed to the model as context.
    # They never add evidence (every chunk below is retrieved fresh, inside the same
    # authorization and version scope), never widen a domain the caller may not read
    # (`routing.plan` still takes the caller's live permission set), and an earlier
    # ANSWER is never read (`AM-30` t2). The persisted USER turn is the raw question.
    prior = _prior_questions(db, conversation_id, user_message_id)
    follow_up = bool(prior) and intent.is_follow_up(question)
    prior_texts: list[str] = []
    follow_up_of: list[UUID] = []
    resolved = question
    if follow_up:
        context, resolved = _resolve_follow_up(prior, question)
        prior_texts = [content for _, content in context]
        follow_up_of = [message_id for message_id, _ in context]

    # Asked ABOUT a Finding (2026-09-11): the router has already authorized it and
    # confirmed it belongs to this conversation's contract. Its requirement and cited
    # clause seed the RETRIEVAL query only — never the payload (see `_finding_seed`).
    if finding_id is not None:
        seed = _finding_seed(db, finding_id)
        if seed:
            resolved = f"{seed} {resolved}"

    # `permissions` empty means a caller that did not pass them — the service-level
    # tests. Treat as document-only, which is exactly the pre-router behaviour.
    if not permissions:
        permissions = frozenset({"assist.ask"})
    route = routing.plan(resolved, has_document=document_version_id is not None,
                         permissions=permissions,
                         statutes_available=statutes.available(db))
    domains = tuple(d.value for d in route.domains)
    log_event("assist.ask.routed", request_id=request_id,
              conversation_id=str(conversation_id), domains=",".join(domains),
              comparison=str(route.comparison),
              statute_shaped=str(route.statute_shaped),
              follow_up=str(follow_up))

    # Domain A — extractive, authorized inside the query (AM-32 r4/r5). Retrieved
    # first because it is cheap, local, and never touches the model.
    position_hits: list[positions.PositionHit] = []
    if route.has(routing.Domain.POSITIONS):
        position_hits = positions.search_positions(
            db, query=resolved, permissions=permissions, limit=POSITION_LIMIT)
    # Domain C — retrieved now, answered separately below (AM-32 r8, AM-47 r4).
    statute_hits: list[statutes.StatuteHit] = []
    if route.has(routing.Domain.STATUTES):
        statute_hits = statutes.search_statutes(db, query=resolved,
                                                permissions=permissions)

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

    if document_version_id is None or not route.has(routing.Domain.DOCUMENT):
        # No document in scope: statutes and/or positions are what can answer. The
        # retrieval record is written by the convergence point, after the fallback
        # sources have been consulted, so it names everything that was searched.
        # (`document_version_id is None` is the fail-closed narrowing main added —
        # what the route already meant, stated so the type checker can see it.)
        return _positions_or_refusal(db, conversation_id, user_message_id, None,
                                     position_hits, route, domains,
                                     AssistAnswerState.NO_EVIDENCE_RETRIEVED,
                                     request_id, statute_hits=statute_hits,
                                     question=question, permissions=permissions,
                                     retrieval_query=resolved,
                                     prior_questions=prior_texts,
                                     follow_up_of=follow_up_of)

    retrieval = store.search_hybrid(
        db, document_version_id=document_version_id, query=resolved,
        embed_query=embedding_runtime.embed_query)
    run_id = _persist_retrieval(db, user_message_id, resolved, retrieval,
                                document_version_id=document_version_id, domains=domains,
                                statute_hits=statute_hits, follow_up_of=follow_up_of)

    chunk_texts = [h.content for h in retrieval.hits]
    if not retrieval.gate_open or not guardrails.evidence_is_sufficient(chunk_texts):
        # The document does not answer. AM-50 r2: the other authorized sources are
        # consulted before any refusal — inside `_positions_or_refusal`, where
        # EVERY non-answer converges (2026-09-09), so a document whose retrieval
        # gate opened but whose evidence the model judged non-responsive falls
        # through exactly like one whose gate never opened. The uploaded document
        # is never a hard filter on what may be answered.
        cause = "gate_closed" if not retrieval.gate_open else "insufficient"
        state = (AssistAnswerState.NO_EVIDENCE_RETRIEVED if not retrieval.gate_open
                 else AssistAnswerState.EVIDENCE_INSUFFICIENT)
        log_event("assist.ask.refused", request_id=request_id, cause=cause,
                  conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains, state, request_id,
                                     statute_hits=statute_hits, question=question,
                                     permissions=permissions, retrieval_query=resolved,
                                     prior_questions=prior_texts)

    try:
        # Document chunks ONLY reach the model. Position text never does (AM-32 r4).
        result = generation.generate(question, chunk_texts,
                                     environment=config.environment(),
                                     request_id=request_id,
                                     **_context_kwargs(prior_texts))
    except generation.GenerationRefused as exc:
        # Gate closed, or no credential: an operational condition, surfaced to the
        # user as the one refusal wording (r4) and logged with its real cause.
        log_event("assist.ask.refused", request_id=request_id,
                  cause="generation_refused", detail=type(exc).__name__,
                  conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.EVIDENCE_INSUFFICIENT, request_id,
                                     statute_hits=statute_hits, question=question,
                                     permissions=permissions, retrieval_query=resolved,
                                     prior_questions=prior_texts)
    except generation.GenerationUnavailable:
        log_event("assist.ask.refused", request_id=request_id,
                  cause="generation_unavailable", level=logging.WARNING,
                  operational_failure=True, conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.EVIDENCE_INSUFFICIENT, request_id,
                                     statute_hits=statute_hits, question=question,
                                     permissions=permissions, retrieval_query=resolved,
                                     prior_questions=prior_texts)

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
    if verification.passed and intent.is_verdict_statement(result.text):
        # A grounded sentence can still be a VERDICT — a document that says "this
        # clause complies with our approved standard" is grounded and is exactly
        # the statement the assistant may never make (AM-25 r1/r4; Constitution
        # §29.1.1 distinction 5). Mechanical, outside the model, as AM-28 r2 wants.
        log_event("assist.ask.refused", request_id=request_id, cause="verdict_language",
                  conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.CLAIM_UNSUPPORTED, request_id,
                                     statute_hits=statute_hits, question=question,
                                     permissions=permissions, retrieval_query=resolved,
                                     prior_questions=prior_texts)
    if not verification.passed:
        # CLAIM_UNSUPPORTED or the model's own NOT FOUND — either way the generated
        # text never reaches the user (AM-25 r5).
        state = verification.state
        log_event("assist.ask.refused", request_id=request_id,
                  cause="verification", state=state.value,
                  failures=str(len(verification.failures)),
                  conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains, state, request_id,
                                     statute_hits=statute_hits, question=question,
                                     permissions=permissions, retrieval_query=resolved,
                                     prior_questions=prior_texts)

    # The company standard BESIDE the document's answer (owner, 2026-09-10: the
    # answer should read "Agreement evidence… Company Standard… Assessment…").
    # The document answered, so its text is the answer; the ratified position
    # relevant to the same question is quoted in its own section — separate
    # field, separate citation grammar, disagreement shown never adjudicated
    # (`AM-45` r2) — and never enters the generation payload (`AM-32` r4).
    # Authorization is the route's: POSITIONS is in the fallback set only for a
    # caller who may read positions, and the domain is recorded whenever it was
    # SEARCHED, whether or not anything matched (`AM-46`).
    if routing.Domain.POSITIONS in route.fallback and not position_hits:
        position_hits = positions.search_positions(
            db, query=resolved, permissions=permissions, limit=POSITION_LIMIT)
        domains = routing.ordered((*domains, routing.Domain.POSITIONS.value))
        _record_fallthrough(db, user_message_id, run_id, question, domains, statute_hits)
    position_findings = _findings_for_standards(
        db, document_version_id, {h.standard_code for h in position_hits}, permissions)

    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", result.text)
    answer_id = _persist_answer(db, reply_id, run_id, AssistAnswerState.ANSWERED,
                                model=result.model,
                                prompt_version_id=_prompt_version_id(db),
                                latency_ms=result.latency_ms)
    _persist_citations(db, answer_id, verification, retrieval.hits)
    _persist_position_citations(db, answer_id, position_hits)
    statute_section = None
    if statute_hits:
        statute_section = _answer_statutes(db, conversation_id, question, statute_hits,
                                           request_id=request_id,
                                           prior_questions=prior_texts)
        _persist_statute_citations(db, answer_id, statute_hits or [],
                                   statute_section.pop("_cited", []))
        statute_section = {k: v for k, v in statute_section.items()
                           if not k.startswith("_")}

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
                      positions=_position_views(position_hits, position_findings),
                      domains=domains, statutes=statute_section)


STATUTES_ONLY_TEXT = ("Answered from the approved statute corpus, cited by Act and "
                      "section below.")
STATUTES_BESIDE_TEXT = (
    "No answer was found in the selected document. The approved statute corpus answers "
    "below, cited by Act and section.")


def _consult_fallbacks(db: DBSession, conversation_id: UUID, question: str,
                       route: routing.RoutePlan, domains: tuple[str, ...],
                       position_hits: list, statute_hits: list,
                       permissions: frozenset[str], request_id: str | None):
    """Search every authorized source the primary route did not already search.

    The one place the "document as knowledge boundary" defect was fixed (2026-09-09).
    Every non-answer — gate closed, evidence too thin, the model's own NOT FOUND, a
    failed citation check, an unavailable model — arrives here before it can become
    a refusal, and each fallback domain the caller may read is consulted with the
    same authorization-inside-the-query retrieval the primary route uses. The
    fallback set is fixed by the route (permissions, document, corpus availability),
    never by what was found, so the recorded `domains` and the refusal wording stay
    a function of facts the caller already holds (`AM-46`).
    """
    searched = set(domains)
    consulted: list[str] = []
    for domain in route.fallback:
        if domain.value in searched:
            continue
        if domain is routing.Domain.POSITIONS and not position_hits:
            position_hits = positions.search_positions(
                db, query=question, permissions=permissions, limit=POSITION_LIMIT)
        elif domain is routing.Domain.STATUTES and not statute_hits:
            # Source priority, not a fixed sweep: the statute corpus is a fallback
            # for a question about the law (statute-shaped) or for one nothing
            # closer could answer. A contract question the organization's own
            # position already answers is NOT also put to 5,000 statute sections —
            # measured live, that produced a grounded Copyright Act answer about
            # licence termination beside the relevant position on notice periods.
            if position_hits and not route.statute_shaped:
                continue
            statute_hits = statutes.search_statutes(
                db, query=question, permissions=permissions,
                require_semantic=not route.statute_shaped)
        consulted.append(domain.value)
    if consulted:
        domains = routing.ordered((*domains, *consulted))
        log_event("assist.ask.fell_through", request_id=request_id,
                  conversation_id=str(conversation_id), to=",".join(consulted),
                  positions=str(len(position_hits)), statutes=str(len(statute_hits)))
    return domains, position_hits, statute_hits


def _record_fallthrough(db: DBSession, message_id: UUID, run_id: UUID | None,
                        question: str, domains: tuple[str, ...],
                        statute_hits: list,
                        follow_up_of: list[UUID] | None = None) -> UUID | None:
    """Keep the retrieval record honest about what was searched: the run row names
    every consulted domain and the statute hits (ids + scores only, `AM-27` r6)."""
    import json as _json

    schema = config.assist_schema()
    if run_id is None:
        if not statute_hits and not domains:
            return None
        return _persist_retrieval(
            db, message_id, question,
            store.RetrievalOutcome(hits=[], gate_open=True, lexical_hit=True,
                                   vector_top_score=None, vector_peak_gap=None,
                                   strategy_version="sources-fallback-1",
                                   embedding_model=None),
            document_version_id=None, domains=domains, statute_hits=statute_hits,
            follow_up_of=follow_up_of)
    db.execute(text(f"""
        UPDATE "{schema}".retrieval_runs
           SET filters = jsonb_set(filters, '{{domains}}', CAST(:d AS jsonb)),
               results = jsonb_set(results, '{{statute_hits}}', CAST(:s AS jsonb))
         WHERE id = :i
    """), {"i": run_id, "d": _json.dumps(list(domains)),
           "s": _json.dumps([{"statute_chunk_id": str(h.statute_chunk_id),
                              "score": round(h.score, 6)} for h in statute_hits])})
    return run_id


def _context_kwargs(prior_questions: list[str] | None) -> dict:
    """`prior_questions=` for `generation.generate`, only when there are any — so a
    first question's call is byte-identical to before, and every test double that
    fakes `generate` without the keyword keeps working."""
    return {"prior_questions": tuple(prior_questions)} if prior_questions else {}


def _positions_or_refusal(db: DBSession, conversation_id: UUID, message_id: UUID,
                          run_id: UUID | None, position_hits: list, route, domains,
                          state: AssistAnswerState, request_id: str | None, *,
                          statute_hits: list | None = None,
                          question: str = "",
                          permissions: frozenset[str] = frozenset(),
                          retrieval_query: str | None = None,
                          prior_questions: list[str] | None = None,
                          follow_up_of: list[UUID] | None = None) -> AskOutcome:
    """The document did not answer (or there was none). The other authorized
    sources may still: the organization's position is quoted extractively (`AM-32`
    r4), the statute corpus is answered over its own evidence (r8). Otherwise the
    one refusal for this route — issued only after every authorized source has
    been consulted."""
    statute_hits = list(statute_hits or [])
    retrieval_query = retrieval_query or question
    domains, position_hits, statute_hits = _consult_fallbacks(
        db, conversation_id, retrieval_query, route, tuple(domains), position_hits,
        statute_hits, permissions, request_id)
    run_id = _record_fallthrough(db, message_id, run_id, retrieval_query, domains,
                                 statute_hits, follow_up_of=follow_up_of)
    statute_section = None
    if statute_hits:
        statute_section = _answer_statutes(db, conversation_id, question, statute_hits,
                                           request_id=request_id,
                                           prior_questions=prior_questions)
    answered_section = (statute_section
                        if statute_section and statute_section.get("text") else None)
    statute_answered = answered_section is not None
    if not position_hits and not statute_answered:
        return _refusal(db, conversation_id, message_id, run_id, state, route)
    if statute_answered:
        wording = (STATUTES_BESIDE_TEXT if route.has(routing.Domain.DOCUMENT)
                   else STATUTES_ONLY_TEXT)
    else:
        wording = (POSITIONS_BESIDE_TEXT if route.has(routing.Domain.DOCUMENT)
                   else POSITIONS_ONLY_TEXT)
    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", wording)
    answer_id = _persist_answer(
        db, reply_id, run_id, AssistAnswerState.ANSWERED,
        model=answered_section.get("_model") if answered_section else None,
        prompt_version_id=_prompt_version_id(db) if statute_answered else None,
        latency_ms=answered_section.get("_latency_ms") if answered_section else None)
    _persist_position_citations(db, answer_id, position_hits)
    if statute_section is not None:
        _persist_statute_citations(db, answer_id, statute_hits or [],
                                   statute_section.pop("_cited", []))
        statute_section = {k: v for k, v in statute_section.items()
                           if not k.startswith("_")}
    log_event("assist.ask.answered_from_other_sources", request_id=request_id,
              conversation_id=str(conversation_id), positions=str(len(position_hits)),
              statutes=str(statute_answered))
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=AssistAnswerState.ANSWERED, text=wording,
                      positions=_position_views(position_hits), domains=domains,
                      statutes=statute_section)
