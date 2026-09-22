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

import contextlib
import contextvars
import dataclasses
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist import (
    capability,
    embedding_runtime,
    generation,
    guardrails,
    intent,
    planner,
    positions,
    rerank,
    rescue,
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
    # The whole cited span, for the reader who opens the evidence rather than
    # skimming it. No new disclosure: retrieval already authorized this chunk for
    # this caller (`AM-25` r6/r7), and `excerpt` was only ever a display truncation.
    text: str
    retrieval_score: float


@dataclass(frozen=True)
class AskOutcome:
    conversation_id: UUID
    message_id: UUID
    answer_state: AssistAnswerState
    text: str
    #: The reader asked for the source's own words (`AM-76` r2), so the quote in
    #: `positions` is the answer and the UI opens it rather than collapsing it.
    exact_text_requested: bool = False
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
    # Stage durations in milliseconds (2026-09-17), for the release gate and the log
    # — never serialised to a reader. `ai_answers.latency_ms` keeps its meaning (the
    # provider call alone); this is the whole ask, stage by stage.
    timings: dict = field(default_factory=dict)


# Stage timing (2026-09-17). Before this, the only latency anywhere in the lane was
# the provider call, so a slow ask could not say WHICH of retrieval, generation,
# verification or the fallbacks was slow. A context variable rather than a threaded
# argument, so no helper's signature changes and a helper that is not inside an ask
# simply records nothing. Accumulates, because positions can be searched twice.
_TIMINGS: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "assist_timings", default=None)


# The ten-stage pipeline's order, for reporting. Stages that did not run for a given
# question are simply absent — a question answered from the document never searches
# the statutes, and a sequence that claimed otherwise would be theatre.
STAGE_ORDER = ("planning", "retrieval", "rescue", "rerank", "positions", "statutes",
               "generation", "position_aid", "statute_generation", "verification",
               "fallbacks", "total")


def progress_sequence(timings: dict) -> list[dict]:
    """The stages this answer actually passed through, in pipeline order, with what
    each cost. Deliberately NOT reader-facing labels: the UI owns copy, and this
    product answers in Hindi as well as English (`AM-69`), so English strings baked
    into the API would be wrong in exactly the place they are read aloud."""
    return [{"stage": name, "ms": timings[name]}
            for name in STAGE_ORDER if name in timings and name != "total"]


@contextlib.contextmanager
def _stage(name: str):
    timings = _TIMINGS.get()
    started = time.monotonic()
    try:
        yield
    finally:
        if timings is not None:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            timings[name] = timings.get(name, 0) + elapsed_ms


_MARKER = re.compile(r"\[(\d{1,2})\]")


def _renumber_markers(text_out: str, cited_indexes: list[int]) -> str:
    """Make the reader's [n] and the citation list's [n] the same number.

    The model cites evidence by its 1-based position in the list it was shown; the
    response lists only the chunks that were actually cited, in ascending order. So an
    answer citing only the third excerpt read "[3]" beside a list whose single entry
    was rendered "[1]" (`AskDock.tsx` numbers by list index). Renumbered AFTER
    verification, which still runs on the model's own indices; display only.
    """
    position = {index: k for k, index in enumerate(cited_indexes, start=1)}
    return _MARKER.sub(
        lambda m: f"[{position[int(m.group(1))]}]" if int(m.group(1)) in position
        else m.group(0), text_out)


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


#: How many of a Finding's cited rows are admitted. Small: a Finding cites the
#: clause it is about, not the document.
FINDING_CITED_LIMIT = 4


def _inherited_finding(db: DBSession, conversation_id: UUID) -> UUID | None:
    """The Finding the most recent turn of this conversation was asked about.

    Why a follow-up inherits it (2026-09-11). "Is this acceptable?" carries no
    subject of its own — that is what makes it a follow-up — so dropping the pin
    on the very next question is what made the owner's flow 8 retrieve nothing
    while the clause it meant was on screen. The existing memory already resolves
    the anchor QUESTION; this resolves the anchor EVIDENCE the same way.

    Only the immediately preceding turn is consulted, and only when the current
    question is anaphoric, so a new standalone question is never quietly seeded
    with a stale clause.
    """
    schema = config.assist_schema()
    row = db.execute(text(f'''
        SELECT r.filters->>'finding_id'
          FROM "{schema}".retrieval_runs r
          JOIN "{schema}".messages m ON m.id = r.message_id
         WHERE m.conversation_id = :c AND r.filters ? 'finding_id'
         ORDER BY m.ordinal DESC LIMIT 1
    '''), {"c": conversation_id}).first()
    return UUID(row[0]) if row and row[0] else None


def _finding_evidence_ids(db: DBSession, finding_id: UUID) -> list[UUID]:
    """The evidence rows THIS Finding's Evaluations cited.

    Why by id rather than by text (2026-09-11, corrected after measuring). The
    first version of this seeded the retrieval QUERY with the requirement's title
    and the opening of the cited clause. The seed was faithful and the query was
    recorded correctly — and it made things worse: lexical search ANDs every
    stemmed term, so a longer query is a NARROWER one, and "why is this a
    deviation?" retrieved nothing while the clause sat in the same document. Seen
    live: the run's `query_text` was the whole clause opening and the answer was
    still NO_EVIDENCE_RETRIEVED.

    A Finding already knows which rows it is about, so they are fetched by id and
    cannot be missed. Authorization is unchanged — the caller resolved the Finding
    through the Guard, and the chunk lookup is still scoped to the one document
    version (`AM-25` r6).
    """
    rows = db.execute(text("""
        SELECT DISTINCT ee.evidence_id
          FROM evaluations ev
          JOIN evaluation_evidence ee ON ee.evaluation_id = ev.id
         WHERE ev.finding_id = :f
         LIMIT :lim
    """), {"f": finding_id, "lim": FINDING_CITED_LIMIT}).all()
    return [r[0] for r in rows]


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
                       follow_up_of: list[UUID] | None = None,
                       finding_id: UUID | None = None,
                       plan: dict | None = None) -> UUID:
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
    # The Finding this turn was asked about (2026-09-11). Recorded for the same
    # reason the version is: so the provenance of the admitted rows is on the row
    # rather than inferred — and so a FOLLOW-UP can inherit it (see `ask`).
    if finding_id:
        filters_dict["finding_id"] = str(finding_id)
    # The query plan (2026-09-17): the topic that narrowed Domain A and the
    # reformulations that ran beside the question — enums and short phrases derived
    # from the user's own question, so the record can say WHY retrieval was aimed
    # where it was. No chunk text, nothing a reader is shown.
    if plan:
        filters_dict["plan"] = plan
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


def _prompt_version_id(db: DBSession, code: str | None = None,
                       template: str | None = None) -> UUID:
    """Idempotently register a prompt template — `AM-27`'s registry.

    Defaults to the document prompt. Until 2026-09-17 this registered ONLY that one,
    so every `AM-67` reading aid was persisted with `prompt_version_id = NULL` — an
    answer whose prompt the registry could not name.
    """
    code = code or generation.PROMPT_VERSION
    template = template or generation.PROMPT_TEMPLATE
    schema = config.assist_schema()
    existing = db.execute(text(f"""
        SELECT id FROM "{schema}".prompt_versions
         WHERE code = :c ORDER BY version_number DESC LIMIT 1
    """), {"c": code}).scalar()
    if existing:
        return existing
    prompt_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".prompt_versions (id, code, version_number, template)
        VALUES (:i, :c, 1, :t)
    """), {"i": prompt_id, "c": code, "t": template})
    return prompt_id


def _persist_citations(db: DBSession, answer_id: UUID, cited_indexes: list[int],
                       hits: list) -> None:
    """One row per VERIFIED claim-to-chunk link — the row's existence IS the
    verification (`AM-27`: no `verified` flag exists on purpose).

    `claim_ordinal` is the position in `cited_indexes` — the order the live response
    lists citations in and the order `_renumber_markers` numbers them. Replay orders
    by this column, so a replayed "[2]" names the same passage the reader first saw.
    """
    schema = config.assist_schema()
    for ordinal, index in enumerate(cited_indexes):
        db.execute(text(f"""
            INSERT INTO "{schema}".answer_citations
                (id, answer_id, chunk_id, claim_ordinal)
            VALUES (:i, :a, :c, :o)
            ON CONFLICT ON CONSTRAINT uq_answer_citations_claim_chunk DO NOTHING
        """), {"i": uuid.uuid4(), "a": answer_id, "c": hits[index - 1].chunk_id,
               "o": ordinal})


def _refusal(db: DBSession, conversation_id: UUID, message_id: UUID,
             retrieval_run_id: UUID | None, state: AssistAnswerState,
             route: routing.RoutePlan, question: str = "") -> AskOutcome:
    """Every refusal path converges here — one wording per candidate set, whatever
    the cause (`AM-29` r4 as amended by `AM-46`; see `routing.refusal_text`)."""
    held = (tuple(statutes.holdings(db))
            if routing.Domain.STATUTES in route.searched else ())
    # The question named a kind of paper, and Domain A was consulted: if the ratified
    # corpus holds no position for that type, the refusal says so and names what it
    # does hold. `named in covered` stays silent — there the type IS covered and
    # retrieval simply missed, so claiming otherwise would be a new falsehood.
    named = (positions.named_document_type(question)
             if routing.Domain.POSITIONS in route.searched else None)
    covered = positions.coverage(db) if named else ()
    unheld = named if named and named not in covered else None
    wording = routing.refusal_text(route, statute_holdings=held,
                                   unheld_document_type=unheld,
                                   position_coverage=covered)
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
        with _stage("statute_generation"):
            result = generation.generate(question, texts,
                                         environment=config.environment(),
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
    if intent.is_verdict_statement(result.text):
        # The same screen the document and position lanes apply, and it was missing
        # here: a statute answer is generated text like any other, and "your document
        # complies with the approved standard" grounds perfectly well in a statute that
        # uses the word "complies". `AM-25` r4 gives that sentence to the evaluator,
        # never to the model, whichever corpus it was generated over.
        log_event("assist.ask.refused", request_id=request_id, cause="verdict_language",
                  conversation_id=str(conversation_id), domain="STATUTES")
        return {"answer_state": AssistAnswerState.EVIDENCE_INSUFFICIENT.value,
                "text": None, "citations": []}
    cited = sorted({c.chunk_index for c in verification.citations if c.grounded})
    return {"answer_state": AssistAnswerState.ANSWERED.value,
            "text": _renumber_markers(result.text, cited),
            "citations": _statute_views(hits, cited), "_cited": cited,
            "_model": result.model, "_latency_ms": result.latency_ms}


def _position_views(hits: list[positions.PositionHit],
                    findings: dict[str, dict] | None = None) -> list[dict]:
    return [{"position_chunk_id": str(h.position_chunk_id),
             "standard_code": h.standard_code, "document_type": h.document_type,
             "source_clause": h.source_clause, "content": h.content,
             # `AM-32` r4's citation is "standard code, version, source clause". The
             # version was being dropped, so a reader could not tell WHICH version of a
             # position they were shown; the status says whether it is still current.
             "standard_version": h.standard_version,
             "ratification_status": h.ratification_status,
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


# `AM-25` r5 permits no generated general knowledge, so this says what the system can
# answer instead of answering. It is a redirect, not a refusal: the reader asked a
# reasonable question and is told where the boundary is and what to ask next.
GENERAL_KNOWLEDGE_TEXT = (
    "That is a general legal question. I answer only from your own approved material — "
    "the documents you upload and your organisation's ratified standards — so this is "
    "not your company's position on it, and I have not looked anything up.\n\n"
    "What I can do instead:\n\n"
    "- Tell you what your organisation's approved standards say about it.\n"
    "- Tell you what an uploaded document says about it.\n"
    "- Compare an uploaded document against your standards.\n\n"
    "Ask me about your standards or open a document, and I will answer from the text."
)

# `AM-76` (AB-26, owner 2026-09-21) SUPERSEDES `AM-67` r3. Verbatim is no longer the
# default: a normal question is answered with a grounded paraphrase and its citation,
# and the ratified text is shown in full only when the reader asked for it or when the
# paraphrase could not be verified. These sentences are the fallback and the
# exact-text wording respectively — they are what a reader sees INSTEAD of a
# paraphrase, never appended to one.
POSITIONS_ONLY_TEXT = ("The organization's approved position relevant to this question "
                       "is quoted below, verbatim from the ratified standard.")
POSITIONS_BESIDE_TEXT = (
    "No answer was found in the selected document. The organization's approved "
    "position relevant to this question is quoted below.")
# The reader asked for the source's own words (`AM-76`; `intent.is_exact_text_request`).
POSITIONS_EXACT_TEXT = ("You asked for the exact wording. The ratified standard is "
                        "quoted below, unchanged.")
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


def plan_question(question: str, prior_questions: list[str] | tuple[str, ...] = (), *,
                  request_id: str | None = None) -> planner.QueryPlan | None:
    """The planning stage (2026-09-17), timed. None means: retrieve exactly as before.
    Runs AFTER every deterministic screen — never for a comparison, capability or
    general-knowledge question — and steers only what `retrieve_document` and the
    Domain A topic filter are given. Shared with `tools.verify_assist_quality`."""
    with _stage("planning"):
        return planner.plan(question, prior_questions, request_id=request_id)


def retrieve_document(db: DBSession, *, document_version_id: UUID,
                      retrieval_query: str, plan: planner.QueryPlan | None = None,
                      pinned_evidence: list[UUID] | tuple[UUID, ...] = (),
                      request_id: str | None = None,
                      ) -> tuple[store.RetrievalOutcome, bool]:
    """THE composition of retrieve → pin → reconsider → reorder for a document question.

    One function, called by `_ask` and by the Tier-2 gate, because a gate that
    re-implements a pipeline step measures the mirror rather than the product — the
    2026-09-16 lesson, when the gate printed 0.625 for a pipeline that had shipped the
    rescue and answered 0.828.

    Order, and it matters:

      1. hybrid search, the gate deciding on its calibrated inputs (`store.search_hybrid`;
         the planner's reformulations widen and re-order the evidence, never the gate,
         which still decides on the question's own raw scores)
      2. a Finding's cited rows pinned in, opening the gate because the evaluator already
         recorded them against this version
      3. the rescue judge reconsidering a SHUT gate (`assist/rescue.py`)
      4. the cross-encoder REORDERING what was admitted (`assist/rerank.py`)

    Step 4 is last on purpose: the gate and the rescue each see exactly the input they
    were calibrated and measured on, and the reranker changes the ORDER of the evidence
    and nothing else — not the membership, not the decision to answer.

    Returns the outcome and whether the rescue reopened the gate.
    """
    with _stage("retrieval"):
        # `extra_queries` only when there is something to pass, so that "no plan" is
        # byte-for-byte the previous call — and every existing double of
        # `search_hybrid` keeps its signature. Two explicit branches rather than a
        # dict unpack, so the type checker can see both.
        # WIDENING is its own flag and its own measurement — see
        # `config.query_expansion_enabled`. The plan still AIMS (its topic narrows
        # Domain A, its section hint is recorded) with no call and no dilution;
        # adding its reformulations as extra fused vector passes was measured twice
        # to cost evidence precision while leaving recall@10, hit@1, MRR and
        # gold-in-top-3 byte-identical, so it is off by default and a merge does not
        # turn it on.
        if plan and plan.queries and config.query_expansion_enabled():
            retrieval = store.search_hybrid(
                db, document_version_id=document_version_id, query=retrieval_query,
                embed_query=embedding_runtime.embed_query, extra_queries=plan.queries)
        else:
            retrieval = store.search_hybrid(
                db, document_version_id=document_version_id, query=retrieval_query,
                embed_query=embedding_runtime.embed_query)
    if pinned_evidence:
        # A question about a Finding can always see the clause that Finding cites.
        # These rows are ADDED to whatever search found, never substituted for it,
        # and the gate is opened because the evidence is not in doubt — the
        # evaluator already recorded it against this document version.
        pinned = store.chunks_for_evidence(
            db, document_version_id=document_version_id,
            evidence_ids=list(pinned_evidence), limit=FINDING_CITED_LIMIT)
        if pinned:
            seen = {h.chunk_id for h in pinned}
            retrieval = dataclasses.replace(
                retrieval, gate_open=True,
                hits=[*pinned, *[h for h in retrieval.hits if h.chunk_id not in seen]])

    # EVIDENCE RESCUE — a second look at a refusal, never at an answer.
    #
    # Measured 2026-09-16: the calibrated gate refuses 21 of 64 answerable questions
    # and 15 of those already hold the gold chunk. Threshold sweeps, a second
    # similarity feature and an alternative embedding model were all measured and none
    # separates those 15 from the 13 genuinely unanswerable ones — see
    # `assist/rescue.py`. The only signal left is reading the chunk.
    #
    # This can only widen an ANSWER ATTEMPT, never narrow one: it runs solely when the
    # gate is shut, and the rescued evidence then faces every screen unchanged —
    # sufficiency, citation verification, the grounding floor and the verdict screen.
    # `AM-25` r5 is untouched: the judge decides whether to TRY, the mechanical checks
    # still decide what a reader sees.
    with _stage("rescue"):
        rescued = rescue.reconsider(retrieval, retrieval_query, request_id=request_id)

    # REORDER the admitted evidence, best first — never its membership, never the gate.
    with _stage("rerank"):
        ordered = rerank.reorder(retrieval_query, rescued.hits, request_id=request_id)
    if ordered is not rescued.hits:
        rescued = dataclasses.replace(rescued, hits=ordered)
    return rescued, rescued.gate_open and not retrieval.gate_open


def ask(db: DBSession, *, conversation_id: UUID, document_version_id: UUID | None,
        question: str, permissions: frozenset[str] = frozenset(),
        request_id: str | None = None,
        finding_id: UUID | None = None) -> AskOutcome:
    """`_ask`, timed stage by stage. One `assist.ask.timings` event per question and
    the same numbers on the outcome, so the release gate can report p50/p95 per
    stage through the production path rather than the provider call alone."""
    timings: dict[str, int] = {}
    token = _TIMINGS.set(timings)
    started = time.monotonic()
    try:
        outcome = _ask(db, conversation_id=conversation_id,
                       document_version_id=document_version_id, question=question,
                       permissions=permissions, request_id=request_id,
                       finding_id=finding_id)
    finally:
        _TIMINGS.reset(token)
    timings["total"] = int((time.monotonic() - started) * 1000)
    stage_fields: dict[str, Any] = {f"{k}_ms": str(v) for k, v in timings.items()}
    log_event("assist.ask.timings", request_id=request_id,
              conversation_id=str(conversation_id), **stage_fields)
    return dataclasses.replace(outcome, timings=dict(timings))


def _ask(db: DBSession, *, conversation_id: UUID, document_version_id: UUID | None,
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
    # confirmed it belongs to this conversation's contract. The rows its Evaluation
    # CITED are admitted directly below — the question itself is left alone, because
    # lengthening it narrows the lexical query rather than widening it.
    cited_evidence: list[UUID] = []
    if finding_id is None and follow_up:
        # The subject carries over with the question it refers to.
        finding_id = _inherited_finding(db, conversation_id)
    if finding_id is not None:
        cited_evidence = _finding_evidence_ids(db, finding_id)

    # `permissions` empty means a caller that did not pass them — the service-level
    # tests. Treat as document-only, which is exactly the pre-router behaviour.
    if not permissions:
        permissions = frozenset({"assist.ask"})
    route = routing.plan(resolved, has_document=document_version_id is not None,
                         permissions=permissions,
                         statutes_available=statutes.available(db))
    domains = tuple(d.value for d in route.domains)
    # `AM-68` r2 — the capability route, before ANY retrieval. Returning here is the
    # enforcement: nothing below this line can reach a document, a position, a statute
    # or a Finding, so the guarantee is structural rather than a promise. Disabled by
    # default; `routing.plan` only sets `capability` when the flag is on, and the
    # amendment is not approved.
    # `AM-25` r5 — a general explanation resolves to no retrieved evidence, so it is not
    # generated. The question is still RECOGNISED, which is the fix: it no longer falls
    # through to the POSITIONS fallback and comes back as three Company Standards.
    if getattr(route, "general_knowledge", False):
        reply_id = _persist_turn(db, conversation_id, ordinal + 1, "ASSISTANT",
                                 GENERAL_KNOWLEDGE_TEXT)
        _persist_answer(db, reply_id, None, AssistAnswerState.NO_EVIDENCE_RETRIEVED,
                        model=None, prompt_version_id=None, latency_ms=None)
        log_event("assist.ask.general_knowledge", request_id=request_id,
                  conversation_id=str(conversation_id))
        return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                          answer_state=AssistAnswerState.NO_EVIDENCE_RETRIEVED,
                          text=GENERAL_KNOWLEDGE_TEXT, domains=())

    if getattr(route, "capability", False):
        try:
            text_out = capability.answer()
        except capability.CapabilityManifestUnavailable:
            # r4/r6: no manifest means no grounded capability answer exists. Fall
            # through to the ordinary route rather than inventing one — today's
            # behaviour, which is wrong but not fabricated.
            log_event("assist.ask.capability_manifest_unavailable",
                      request_id=request_id, conversation_id=str(conversation_id))
        else:
            reply_id = _persist_turn(db, conversation_id, ordinal + 1, "ASSISTANT",
                                     text_out)
            _persist_answer(db, reply_id, None, AssistAnswerState.ANSWERED,
                            model=None, prompt_version_id=None, latency_ms=None)
            log_event("assist.ask.capability", request_id=request_id,
                      conversation_id=str(conversation_id))
            return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                              answer_state=AssistAnswerState.ANSWERED, text=text_out,
                              domains=())
    log_event("assist.ask.routed", request_id=request_id,
              conversation_id=str(conversation_id), domains=",".join(domains),
              comparison=str(route.comparison),
              statute_shaped=str(route.statute_shaped),
              # WHY it routed (2026-09-21) — signal names only, never the question.
              statute_signals=",".join(route.statute_signals),
              follow_up=str(follow_up))

    # QUERY PLAN (2026-09-17) — what the question is ABOUT, so retrieval can be aimed.
    # After every deterministic screen (they returned above) and never for the
    # evaluator's question: `AM-25` r4 stays code, and the plan cannot reach it. The
    # plan is advisory and fails closed to None — see `assist/planner.py`. It steers
    # exactly two things: the Domain A topic filter and the document's extra queries.
    # The RAW question goes to the planner with the prior questions as context; the
    # concatenated `resolved` string still drives the lexical pass unchanged.
    made_plan = None if route.comparison else plan_question(
        question, prior_texts, request_id=request_id)
    topic = made_plan.topic if made_plan else None
    plan_filters = made_plan.as_filters() if made_plan else None

    # Domain A — extractive, authorized inside the query (AM-32 r4/r5). Retrieved
    # first because it is cheap, local, and never touches the model.
    position_hits: list[positions.PositionHit] = []
    if route.has(routing.Domain.POSITIONS):
        with _stage("positions"):
            position_hits = positions.search_positions(
                db, query=resolved, permissions=permissions, limit=POSITION_LIMIT,
                topic=topic, allow_relax=not route.statute_shaped)
    # Domain C — retrieved now, answered separately below (AM-32 r8, AM-47 r4).
    statute_hits: list[statutes.StatuteHit] = []
    if route.has(routing.Domain.STATUTES):
        with _stage("statutes"):
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
                                     topic=topic, plan=plan_filters,
                                     follow_up_of=follow_up_of)

    retrieval, was_rescued = retrieve_document(
        db, document_version_id=document_version_id, retrieval_query=resolved,
        plan=made_plan, pinned_evidence=cited_evidence, request_id=request_id)
    if was_rescued:
        log_event("assist.ask.rescued", request_id=request_id,
                  conversation_id=str(conversation_id), chunks=str(len(retrieval.hits)))

    # Persisted AFTER the reconsideration, so `retrieval_runs` records the retrieval
    # the answer was actually built on. Written before it, a rescued turn left an
    # audit row reading "gate closed, zero hits" beside an answer citing chunks —
    # `AM-27` calls this row "the retrieval record behind an answer", and it has to
    # be the one behind THAT answer.
    run_id = _persist_retrieval(db, user_message_id, resolved, retrieval,
                                document_version_id=document_version_id, domains=domains,
                                statute_hits=statute_hits, follow_up_of=follow_up_of,
                                finding_id=finding_id, plan=plan_filters)
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
                                     prior_questions=prior_texts,
                                     topic=topic, plan=plan_filters)

    try:
        # Document chunks ONLY reach the model. Position text never does (AM-32 r4).
        with _stage("generation"):
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
                                     prior_questions=prior_texts,
                                     topic=topic, plan=plan_filters)
    except generation.GenerationUnavailable:
        log_event("assist.ask.refused", request_id=request_id,
                  cause="generation_unavailable", level=logging.WARNING,
                  operational_failure=True, conversation_id=str(conversation_id))
        return _positions_or_refusal(db, conversation_id, user_message_id, run_id,
                                     position_hits, route, domains,
                                     AssistAnswerState.EVIDENCE_INSUFFICIENT, request_id,
                                     statute_hits=statute_hits, question=question,
                                     permissions=permissions, retrieval_query=resolved,
                                     prior_questions=prior_texts,
                                     topic=topic, plan=plan_filters)

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

    with _stage("verification"):
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
                                     prior_questions=prior_texts,
                                     topic=topic, plan=plan_filters)
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
                                     prior_questions=prior_texts,
                                     topic=topic, plan=plan_filters)

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
        with _stage("positions"):
            position_hits = positions.search_positions(
                db, query=resolved, permissions=permissions, limit=POSITION_LIMIT,
                topic=topic, allow_relax=not route.statute_shaped)
        domains = routing.ordered((*domains, routing.Domain.POSITIONS.value))
        _record_fallthrough(db, user_message_id, run_id, question, domains, statute_hits)
    position_findings = _findings_for_standards(
        db, document_version_id, {h.standard_code for h in position_hits}, permissions)

    cited_indexes = sorted({c.chunk_index for c in verification.citations
                            if c.grounded})
    answer_text = _renumber_markers(result.text, cited_indexes)
    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", answer_text)
    answer_id = _persist_answer(db, reply_id, run_id, AssistAnswerState.ANSWERED,
                                model=result.model,
                                prompt_version_id=_prompt_version_id(db),
                                latency_ms=result.latency_ms)
    _persist_citations(db, answer_id, cited_indexes, retrieval.hits)
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

    citations = [
        CitationView(
            chunk_id=retrieval.hits[i - 1].chunk_id,
            evidence_id=retrieval.hits[i - 1].evidence_id,
            page_number=retrieval.hits[i - 1].page_number,
            section_ref=retrieval.hits[i - 1].section_ref,
            excerpt=retrieval.hits[i - 1].content[:240],
            text=retrieval.hits[i - 1].content,
            retrieval_score=retrieval.hits[i - 1].retrieval_score)
        for i in cited_indexes
    ]
    log_event("assist.ask.answered", request_id=request_id,
              conversation_id=str(conversation_id), citations=str(len(citations)),
              positions=str(len(position_hits)))
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=AssistAnswerState.ANSWERED,
                      text=answer_text, citations=citations,
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
                       permissions: frozenset[str], request_id: str | None,
                       topic: str | None = None):
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
                db, query=question, permissions=permissions, limit=POSITION_LIMIT,
                topic=topic, allow_relax=not route.statute_shaped)
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
                        follow_up_of: list[UUID] | None = None,
                        plan: dict | None = None) -> UUID | None:
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
            follow_up_of=follow_up_of, plan=plan)
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



def _position_reading_aid(question: str, hits: list,
                          request_id: str | None) -> generation.GenerationResult | None:
    """`AM-67` — a plain-language explanation of the organization's own positions,
    rendered BESIDE the verbatim quote and never instead of it (r3).

    Returns None on every failure path, and None means the caller emits exactly what it
    emitted before this existed: the fixed sentence plus the quotes (r8). A reading aid
    that cannot be produced safely is simply absent — it never degrades the answer.

    Order matters. The locator screen runs BEFORE the model is reached (r7), because a
    stale corpus is a disclosure problem, not a quality one.
    """
    if not config.position_synthesis_enabled() or not hits:
        return None
    spans = [h.content for h in hits]
    try:
        positions.screen_for_egress(spans)
    except positions.PositionEgressRefused as exc:
        # The corpus was not re-chunked. Loud in the log, invisible to the reader.
        log_event("assist.position_synthesis.refused_stale_corpus",
                  request_id=request_id, reason=str(exc)[:200])
        return None
    try:
        result = generation.generate_position_reading_aid(
            question, spans, environment=config.environment(), request_id=request_id)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        log_event("assist.position_synthesis.unavailable", request_id=request_id,
                  reason=type(exc).__name__)
        return None
    text_out = (result.text or "").strip()
    if not text_out or text_out.upper().startswith("NOT FOUND"):
        return None
    # r5 — the same two screens a document answer passes, unchanged.
    verification = guardrails.verify_answer(text_out, spans)
    if verification.state is not AssistAnswerState.ANSWERED:
        log_event("assist.position_synthesis.ungrounded", request_id=request_id)
        return None
    # r4 — never a statement about how a document stands. The prompt asks; this enforces.
    if intent.is_verdict_statement(text_out):
        log_event("assist.position_synthesis.verdict_blocked", request_id=request_id)
        return None
    # The verified text, with the model identity and latency the audit row needs.
    return dataclasses.replace(result, text=text_out)


def _positions_or_refusal(db: DBSession, conversation_id: UUID, message_id: UUID,
                          run_id: UUID | None, position_hits: list, route, domains,
                          state: AssistAnswerState, request_id: str | None, *,
                          statute_hits: list | None = None,
                          question: str = "",
                          permissions: frozenset[str] = frozenset(),
                          retrieval_query: str | None = None,
                          prior_questions: list[str] | None = None,
                          follow_up_of: list[UUID] | None = None,
                          topic: str | None = None,
                          plan: dict | None = None) -> AskOutcome:
    """The document did not answer (or there was none). The other authorized
    sources may still: the organization's position is quoted extractively (`AM-32`
    r4), the statute corpus is answered over its own evidence (r8). Otherwise the
    one refusal for this route — issued only after every authorized source has
    been consulted."""
    statute_hits = list(statute_hits or [])
    retrieval_query = retrieval_query or question
    with _stage("fallbacks"):
        domains, position_hits, statute_hits = _consult_fallbacks(
            db, conversation_id, retrieval_query, route, tuple(domains), position_hits,
            statute_hits, permissions, request_id, topic=topic)
    run_id = _record_fallthrough(db, message_id, run_id, retrieval_query, domains,
                                 statute_hits, follow_up_of=follow_up_of, plan=plan)
    statute_section = None
    if statute_hits:
        statute_section = _answer_statutes(db, conversation_id, question, statute_hits,
                                           request_id=request_id,
                                           prior_questions=prior_questions)
    answered_section = (statute_section
                        if statute_section and statute_section.get("text") else None)
    statute_answered = answered_section is not None
    if not position_hits and not statute_answered:
        return _refusal(db, conversation_id, message_id, run_id, state, route, question)
    aid: generation.GenerationResult | None = None
    # Read off the QUESTION, deterministically — the model never decides whether its
    # own output is wanted (`AM-25` r1, `AM-76` r2).
    exact_text_requested = intent.is_exact_text_request(question)
    if statute_answered:
        wording = (STATUTES_BESIDE_TEXT if route.has(routing.Domain.DOCUMENT)
                   else STATUTES_ONLY_TEXT)
    else:
        # `AM-76` r1-r3. Three outcomes, in this order:
        #   the reader asked for exact text  -> the quote, and no paraphrase
        #   a paraphrase verified            -> the paraphrase alone
        #   it did not                       -> the quote (fail closed, r4)
        # The quote itself always remains in `positions` whichever path runs, so the
        # citation and its provenance are never lost (`AM-32` r4 untouched); what
        # changes is whether the reader is SHOWN it instead of an explanation.
        if exact_text_requested:
            wording = POSITIONS_EXACT_TEXT
        else:
            wording = (POSITIONS_BESIDE_TEXT if route.has(routing.Domain.DOCUMENT)
                       else POSITIONS_ONLY_TEXT)
            with _stage("position_aid"):
                aid = _position_reading_aid(question, position_hits, request_id)
            if aid:
                wording = aid.text
    # The answer row names the prompt that produced its generated part — the statute
    # answer's, or the reading aid's. Until 2026-09-17 the aid's was never registered,
    # so `prompt_version_id` was NULL on every `AM-67` answer.
    model: str | None = None
    prompt_id: UUID | None = None
    latency: int | None = None
    if answered_section is not None:
        model = answered_section.get("_model")
        prompt_id = _prompt_version_id(db)
        latency = answered_section.get("_latency_ms")
    elif aid is not None:
        model = aid.model
        prompt_id = _prompt_version_id(db, generation.POSITION_PROMPT_VERSION,
                                       generation.POSITION_PROMPT_TEMPLATE)
        latency = aid.latency_ms
    ordinal = _next_ordinal(db, conversation_id)
    reply_id = _persist_turn(db, conversation_id, ordinal, "ASSISTANT", wording)
    answer_id = _persist_answer(db, reply_id, run_id, AssistAnswerState.ANSWERED,
                                model=model, prompt_version_id=prompt_id,
                                latency_ms=latency)
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
                      exact_text_requested=exact_text_requested,
                      positions=_position_views(position_hits), domains=domains,
                      statutes=statute_section)
