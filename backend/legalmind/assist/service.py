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
import functools
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.agent import attachments, ledger
from legalmind.assist.ingestion import embedding_runtime
from legalmind.assist.knowledge import positions, statutes, store
from legalmind.assist.llm import generation
from legalmind.assist.query import (
    capability,
    conversational,
    intent,
    planner,
    routing,
    understanding,
)
from legalmind.assist.retrieval import rerank, rescue

# `AM-25` r4 — routed to the evaluator, never answered generatively. The screen is
# `intent.is_comparison_question` (2026-09-08): the regex it replaced passed every
# natural phrasing of the manager's own question, and each was then refused as "not
# found in the selected document" — see tests/test_assist_intent.py for the matrix.
from legalmind.assist.state import AssistAnswerState
from legalmind.assist.verification import guardrails
from legalmind.observability.logs import log_event
from legalmind.security import permissions as P
from legalmind.security.errors import SecurityError

EVALUATOR_ROUTE_TEXT = (
    "This question asks how the document stands against the organization's approved "
    "position. That comparison is made by the deterministic evaluator, not the "
    "assistant — its Findings for this document are attached below.")
NEEDS_DOCUMENT_TEXT = (
    "This asks whether a document meets a standard, and no document is open in this "
    "conversation. Open the document you want assessed and ask again — the comparison "
    "is made by the deterministic evaluator against that document's Findings.")
NEEDS_AUTHORITY_TEXT = (
    "This asks whether a document complies with a law. The evaluator measures a "
    "document against the organization's ratified Company Standards, and none of them "
    "is derived from an Act — a statute states the law, it does not set the position "
    "the organization has approved. I can read what the Act itself says, or how the "
    "document stands against the approved standards, but those are two different "
    "questions and I will not answer one as though it were the other.")
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
    #: The quote IS the answer — either because it was asked for (r2) or because no
    #: paraphrase verified (r4). `text` then only points AT the quote, so a UI that
    #: collapses it shows the reader a standard code and no law at all. Strictly
    #: wider than `exact_text_requested`; the two are not interchangeable.
    quote_is_the_answer: bool = False
    citations: list[CitationView] = field(default_factory=list)
    #: Cited records `answer_citations` has no column for — the Constitution and the
    #: reader's material — for the ledger (Ask plan 1.7, A5-3). Never serialised.
    ledger_extra: tuple = ()
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
    #: The agent path's cited records, one per legend key (`source_views`), for the
    #: structured Sources list — text as the turn showed it, under its permissions.
    sources: list[dict] = field(default_factory=list)


# Stage timing (2026-09-17). Before this, the only latency anywhere in the lane was
# the provider call, so a slow ask could not say WHICH of retrieval, generation,
# verification or the fallbacks was slow. A context variable rather than a threaded
# argument, so no helper's signature changes and a helper that is not inside an ask
# simply records nothing. Accumulates, because positions can be searched twice.
_TIMINGS: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "assist_timings", default=None)

# PHASE 13 (`AM-94`) — the per-request trace: which path answered and why, what it
# retrieved and cited (identifiers only), what it cost. Filled as the ask runs and
# emitted once, as `assist.ask.trace`, by `ask`.
_TRACE: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "assist_trace", default=None)
LEGACY = "legacy"
MULTI_SOURCE = "multi_source"


def _trace(**fields: Any) -> None:
    trace = _TRACE.get()
    if trace is not None:
        trace.update(fields)


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


def _release_connection(db: DBSession) -> None:
    """Commit the request's transaction immediately before a provider call, so the
    pooled connection is returned for the duration of the network round-trip
    (system design review §6.4, 2026-09-29). Set as `generation.BEFORE_EGRESS` by
    `ask()` and by nothing else: the analysis lane keeps one transaction per Review.

    What is committed at that point is the reader's own USER turn and the retrieval
    run — a turn without an answer is the state the reader already sees while
    waiting, and a replayed conversation lists it as a question like any other.
    Every write that follows — the answer, its citations, the audit row of the call
    — stays in ONE transaction, committed by `CommitBeforeResponse` as before.

    Never under a savepoint: a commit closes it, and the caller's later
    `savepoint.rollback()` would raise. The multi-source path closes its savepoint
    before it generates for exactly this reason; this refuses, loudly, rather than
    commit through one.
    """
    if db.in_nested_transaction():
        log_event("assist.db.release_skipped", level=logging.WARNING,
                  reason="egress under a savepoint keeps the connection")
        return
    db.commit()


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


class ConversationConflict(SecurityError):
    """409 — two turns reached one conversation at the same moment."""

    status_code = 409
    code = "CONVERSATION_TURN_CONFLICT"


def _append_turn(db: DBSession, conversation_id: UUID, role: str, content: str) -> UUID:
    """Persist a turn at the conversation's next ordinal.

    Two requests on one conversation at once — a second tab, a client's retry — both
    read the same `max(ordinal)`, and `uq_messages_conversation_ordinal` refuses the
    second insert. That refusal surfaced as an internal error (design review §9,
    2026-09-29). Now the insert runs under a savepoint, the ordinal is re-read once,
    and only a second collision is reported — as a 409 the reader can act on.
    """
    for _ in range(2):
        ordinal = _next_ordinal(db, conversation_id)
        savepoint = db.begin_nested()
        try:
            message_id = _persist_turn(db, conversation_id, ordinal, role, content)
            savepoint.commit()
            return message_id
        except IntegrityError:
            savepoint.rollback()
    raise ConversationConflict("another turn reached this conversation at the same "
                               "moment; send the question again")


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


def social_text(social: conversational.Social | None) -> tuple[str, AssistAnswerState]:
    """The fixed reply to a social turn (`AM-109`), or the scope sentence when `social`
    is None — shared by the shipped path and the agent's pre-router (Phase 4, P8)."""
    if social is None:
        return conversational.SCOPE_REPLY, AssistAnswerState.NO_EVIDENCE_RETRIEVED
    if social is conversational.Social.IDENTITY:
        try:
            return capability.answer(), AssistAnswerState.ANSWERED
        except capability.CapabilityManifestUnavailable:
            return (conversational.REPLY[conversational.Social.GREETING],
                    AssistAnswerState.ANSWERED)
    return conversational.REPLY.get(social, ""), AssistAnswerState.ANSWERED


def preroute(question: str, *, has_prior: bool, has_document: bool,
             has_material: bool = False, prior_offer: bool = False) -> str | None:
    """The shipped path's pre-router as one function (`_ask`'s first screens, same
    order): a social turn, an off-scope request, a message with no subject and nothing
    to refer to. The fixed reply, or None when the message needs an answer."""
    # A bare paste — material, no question — is acknowledged with zero model calls; a
    # model given one analyses it unasked or loops (owner, 2026-10-07).
    if (attachments.carries_material(question)
            and not attachments.split_paste(question)[0]):
        return attachments.MATERIAL_READ
    social = conversational.kind(question, prior_offer=prior_offer)
    if social is not None:
        return social_text(social)[0]
    question = conversational.strip_social(question)
    if conversational.off_scope(question):
        return social_text(None)[0]
    # The capability question (`AM-68`) — the agent path never ran `routing.plan`, so
    # "how can you help me?" reached the model: 4 calls, 12 s (2026-10-07).
    if config.capability_route_enabled() and intent.is_capability_question(question):
        try:
            return capability.answer(question=question)
        except capability.CapabilityManifestUnavailable:
            pass
    # `AM-118`: a question about the reader's own agreement with none in the chat is
    # answered with what to provide, never from the company's standard as if it were
    # theirs; a broad intent gets one clarifying question.
    if not has_document and not has_material:
        topic = conversational.their_document_topic(question, has_prior=has_prior)
        if topic is not None:
            return conversational.needs_document(topic)
    clarify = conversational.vague_intent(question)
    if clarify is not None:
        return clarify
    if (not has_prior and not has_document and not has_material
            and intent.has_no_subject(question)):
        return social_text(conversational.Social.UNCLEAR)[0]
    return None


def _social_reply(db: DBSession, conversation_id: UUID,
                  social: conversational.Social | None,
                  request_id: str | None) -> AskOutcome:
    """`AM-109` — the fixed reply to a social turn, persisted like any other answer.
    States no legal content, so it is ANSWERED with no domain, as the capability
    route is (`AM-68`). `social` None is an out-of-scope request: the scope sentence,
    recorded as the refusal it is."""
    text_out, state = social_text(social)
    reply_id = _append_turn(db, conversation_id, "ASSISTANT", text_out)
    _persist_answer(db, reply_id, None, state,
                    model=None, prompt_version_id=None, latency_ms=None)
    log_event("assist.ask.social", request_id=request_id,
              conversation_id=str(conversation_id),
              kind=social.value if social else "OFF_SCOPE")
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=state, text=text_out, domains=())


def material_saved(db: DBSession, *, conversation_id: UUID,
                   request_id: str | None) -> AskOutcome:
    """A turn that only brought material (plan 1.1): recorded with fixed words on both
    sides, nothing retrieved, nothing generated."""
    _append_turn(db, conversation_id, "USER", attachments.MATERIAL_TURN)
    reply_id = _append_turn(db, conversation_id, "ASSISTANT", attachments.MATERIAL_SAVED)
    _persist_answer(db, reply_id, None, AssistAnswerState.ANSWERED,
                    model=None, prompt_version_id=None, latency_ms=None)
    log_event("assist.ask.material_saved", request_id=request_id,
              conversation_id=str(conversation_id))
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=AssistAnswerState.ANSWERED,
                      text=attachments.MATERIAL_SAVED, domains=())


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
    # A social turn ("hi", "thanks") is not a question: it anchors no follow-up and
    # carries no topic (`AM-109`); a social lead is dropped from one that is.
    return [(r[0], conversational.strip_social((r[1] or "")[:PRIOR_QUESTION_CHARS]))
            for r in reversed(rows)
            if (r[1] or "").strip() and conversational.kind(r[1]) is None]


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
                        contract_id: UUID | None, model: str | None = None) -> UUID:
    schema = config.assist_schema()
    conversation_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".conversations (id, user_id, contract_id, model)
        VALUES (:i, :u, :c, :m)
    """), {"i": conversation_id, "u": user_id, "c": contract_id, "m": model})
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
    lookup = text(f"""
        SELECT id FROM "{schema}".prompt_versions
         WHERE code = :c ORDER BY version_number DESC LIMIT 1
    """)
    existing = db.execute(lookup, {"c": code}).scalar()
    if existing:
        return existing
    # The first questions after a prompt-version bump arrive together and every
    # one finds no row. `ON CONFLICT DO NOTHING` lets one insert win and the rest
    # read it back — found by the 2026-09-29 load validation, where the loser's
    # IntegrityError failed its whole question.
    db.execute(text(f"""
        INSERT INTO "{schema}".prompt_versions (id, code, version_number, template)
        VALUES (:i, :c, 1, :t)
        ON CONFLICT (code, version_number) DO NOTHING
    """), {"i": uuid.uuid4(), "c": code, "t": template})
    return db.execute(lookup, {"c": code}).scalar_one()


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
    reply_id = _append_turn(db, conversation_id, "ASSISTANT", wording)
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
# Neither sentence claims relevance or counts the standards: this is the path where
# no paraphrase verified, so the only thing the system can honestly assert is what it
# is showing and that it is unchanged. The quote below is the answer.
POSITIONS_ONLY_TEXT = ("The approved position is quoted below, word for word — I could "
                       "not restate it without going beyond what it says.")
POSITIONS_BESIDE_TEXT = (
    "No answer was found in the selected document. The approved position is quoted "
    "below, word for word.")
# The reader asked for the source's own words (`AM-76`; `intent.is_exact_text_request`).
# `AM-78` r3 — fixed, never generated: the zero-tolerance Legal Rule, in the reader's
# words. It names the routing only; no threshold or rule configuration (`LEGAL-02`).
LEGAL_REVIEW_TEXT = "Any deviation from this position needs Legal review."
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
      3. the rescue judge reconsidering a SHUT gate (`assist/retrieval/rescue.py`)
      4. the cross-encoder REORDERING what was admitted (`assist/retrieval/rerank.py`)

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
    # `assist/retrieval/rescue.py`. The only signal left is reading the chunk.
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
        finding_id: UUID | None = None, model: str = "gemini") -> AskOutcome:
    """`_ask`, timed stage by stage. One `assist.ask.timings` event per question and
    the same numbers on the outcome, so the release gate can report p50/p95 per
    stage through the production path rather than the provider call alone.

    `model` is an id the router has already validated (`model_router.resolve`); it
    picks the agent's provider."""
    timings: dict[str, int] = {}
    usage: dict[str, Any] = {}
    trace: dict[str, Any] = {"selected_path": LEGACY, "path": LEGACY,
                             "flag": config.ask_multi_source(),
                             "has_document": document_version_id is not None}
    token = _TIMINGS.set(timings)
    usage_token = generation.USAGE.set(usage)
    trace_token = _TRACE.set(trace)
    release_token = generation.BEFORE_EGRESS.set(
        functools.partial(_release_connection, db))
    rescue_calls: list = []
    rescue_token = rescue.CALLS.set(rescue_calls)
    started = time.monotonic()
    owner = conversation_owner(db, conversation_id)
    if config.ask_agent_mode() == "on" and owner is not None:
        try:
            return _agent_answer(db, conversation_id, owner, question, permissions,
                                 request_id, model)
        finally:
            _TIMINGS.reset(token)
            generation.USAGE.reset(usage_token)
            _TRACE.reset(trace_token)
            generation.BEFORE_EGRESS.reset(release_token)
            rescue.CALLS.reset(rescue_token)
    try:
        outcome = _ask(db, conversation_id=conversation_id,
                       document_version_id=document_version_id, question=question,
                       permissions=permissions, request_id=request_id,
                       finding_id=finding_id)
    finally:
        _TIMINGS.reset(token)
        generation.USAGE.reset(usage_token)
        _TRACE.reset(trace_token)
        generation.BEFORE_EGRESS.reset(release_token)
        rescue.CALLS.reset(rescue_token)
    # The rescue judge is reached from retrieval, below any per-path audit list; every
    # call it made in this request is audited here, once (`AM-30` t5).
    for result, judged in rescue_calls:
        _audit_calls(db, [result], conversation_id, request_id, judged)
    timings["total"] = int((time.monotonic() - started) * 1000)
    stage_fields: dict[str, Any] = {f"{k}_ms": str(v) for k, v in timings.items()}
    log_event("assist.ask.timings", request_id=request_id,
              conversation_id=str(conversation_id), **stage_fields)
    _emit_trace(trace, usage, timings, outcome, request_id, conversation_id)
    _record_ledger(db, outcome)
    if config.ask_agent_mode() != "off":
        # Phase 3 B6: the agent runs BESIDE the shipped answer and only its log line
        # survives; `outcome` below is the shipped one, whatever the agent produced.
        # (`on` answers above; it reaches here only when the conversation has no owner.)
        from legalmind.assist.agent import agent
        owner = conversation_owner(db, conversation_id)
        if owner is not None:
            agent.shadow(db, conversation_id=conversation_id, user_id=owner,
                         permissions=permissions or frozenset({"assist.ask"}),
                         message=question, request_id=request_id)
    return dataclasses.replace(outcome, timings=dict(timings))


_SOURCE_KIND = {"C": "constitution", "H": "constitution", "P": "position",
                "S": "statute", "D": "document", "U": "material"}


def source_views(db: DBSession, items: list[tuple]) -> list[dict]:
    """The Sources list as data (owner's manager, 2026-10-07: read at the end, click to
    see where it came from): per legend key its kind, location, scope and the text the
    turn cited; a document clause also names its evidence row and version, so the
    reader can open it in place. `items` are (key, text, location, ref, scope, state).
    Built only from records the caller may read — live from the turn, on replay from
    `ledger.refetch` under current permissions; an unreadable one is never passed in,
    so it is absent, not blank (SEC-07)."""
    chunk_ids = [ref[4:] for _, _, _, ref, _, _ in items
                 if (ref or "").startswith("DOC:")]
    rows = {str(r[0]): r for r in db.execute(text(
        "SELECT id, evidence_id, document_version_id "
        f'FROM "{config.assist_schema()}".chunks WHERE id::text = ANY(:i)'),
        {"i": chunk_ids}).all()} if chunk_ids else {}
    out = []
    for key, body, location, ref, scope, state in items:
        view = {"key": key, "kind": _SOURCE_KIND.get(key[:1], "document"),
                "location": location, "text": body}
        if scope:
            view["scope"] = scope
        if state and state != "current":
            view["state"] = state
        row = rows.get((ref or "")[4:]) if (ref or "").startswith("DOC:") else None
        if row is not None:
            view["evidence_id"], view["document_version_id"] = str(row[1]), str(row[2])
        out.append(view)
    return out


def _agent_answer(db: DBSession, conversation_id: UUID, owner: UUID, question: str,
                  permissions: frozenset[str], request_id: str | None,
                  model: str = "gemini") -> AskOutcome:
    """Agent mode `on` (demo mission, 2026-10-04): the agent's verified reply IS the
    answer, in every environment since the owner turned it on for everyone (A-88,
    2026-10-06). The agent's floor answers when the model fails."""
    from legalmind.assist.agent import agent, model_router, tools
    question = (question or "").strip()
    _append_turn(db, conversation_id, "USER", question)
    ctx = tools.ToolContext.open(db, user_id=owner,
                                 permissions=permissions or frozenset({"assist.ask"}),
                                 conversation_id=conversation_id)
    t = agent.run_turn(model_router.provider(model), ctx, question, request_id=request_id)
    reply = _append_turn(db, conversation_id, "ASSISTANT", t.text())
    # the model whose words are shown: the final call or its repair — never a decision
    # step or the rescue judge, and none for the floor, which code writes (2026-10-07)
    wrote = None if t.outcome in ("floor", "prerouted") else next(
        (c.model for c in reversed(t.calls) if c.role in ("final", "repair")), None)
    # A fixed reply ran no model, so it has no model time: NULL, which the footer reads
    # as "instant" — a floor keeps its time, because a model did run and its draft was
    # not used (`AM-122`; "Answered without a model · 4 ms" read as a mystery).
    answer = _persist_answer(db, reply, None, AssistAnswerState.ANSWERED, model=wrote,
                             prompt_version_id=None,
                             latency_ms=(None if t.outcome == "prerouted"
                                         else t.stages_ms.get("total")))
    if t.registry is not None:
        t.registry.persist(reply, answer, t.cited)
    agent._audit(db, t, conversation_id, request_id)
    # the live turn's stages and per-call latency/tokens — production saw only per-call
    # latency before (latency diagnosis 2026-10-07 §8); ids and numbers only
    log_event("assist.agent.turn", request_id=request_id,
              conversation_id=str(conversation_id), model=model, **agent.turn_log(t))
    shown = t.registry.evidence() if t.registry is not None else {}
    sources = source_views(db, [
        (k, shown[k].text, shown[k].location, t.registry.shown[k].record.source_ref,
         shown[k].scope, "current")
        for k in dict.fromkeys(t.cited) if k in shown and t.registry is not None
        and not (shown[k].scope or "").startswith("another document")])
    return AskOutcome(conversation_id=conversation_id, message_id=reply,
                      answer_state=AssistAnswerState.ANSWERED, text=t.text(),
                      timings=dict(t.stages_ms), sources=sources)


def _record_ledger(db: DBSession, outcome: AskOutcome) -> None:
    """Ask plan 1.6/1.7 — what this answer cited, under ledger keys, on every path:
    the rows `answer_citations` holds, plus the Constitution and material refs."""
    if outcome.answer_state is not AssistAnswerState.ANSWERED:
        return
    answer_id = db.execute(text(
        f'SELECT id FROM "{config.assist_schema()}".ai_answers WHERE message_id = :m'),
        {"m": outcome.message_id}).scalar()
    if answer_id is not None:
        ledger.record_answer(db, conversation_id=outcome.conversation_id,
                             answer_id=answer_id, turn_message_id=outcome.message_id,
                             extra=outcome.ledger_extra)


def _emit_trace(trace: dict, usage: dict, timings: dict, outcome: AskOutcome,
                request_id: str | None, conversation_id: UUID) -> None:
    """One `assist.ask.trace` per question (roadmap §18). Identifiers, versions,
    counts, tokens and latency only — no question text, no retrieved or document
    text, no answer text; a failure is recorded by its KIND, never its sentence."""
    rate_in = os.environ.get("LEGALMIND_GEMINI_USD_PER_M_IN")
    rate_out = os.environ.get("LEGALMIND_GEMINI_USD_PER_M_OUT")
    cost = None
    if rate_in and rate_out:
        with contextlib.suppress(ValueError):
            cost = round(usage.get("prompt_tokens", 0) * float(rate_in) / 1e6
                         + usage.get("output_tokens", 0) * float(rate_out) / 1e6, 6)
    log_event("assist.ask.trace", request_id=request_id,
              conversation_id=str(conversation_id), message_id=str(outcome.message_id),
              answer_state=outcome.answer_state.value,
              domains=list(outcome.domains), **trace,
              gemini_calls=usage.get("calls", 0),
              gemini_failed_calls=usage.get("failed_calls", 0),
              prompt_tokens=usage.get("prompt_tokens", 0),
              output_tokens=usage.get("output_tokens", 0),
              provider_finishes=usage.get("finish_reasons", []),
              prompt_versions=usage.get("prompt_versions", []),
              model=generation._model(), estimated_usd=cost,
              latency_ms=timings.get("total"),
              stages_ms={k: v for k, v in timings.items() if k != "total"})


def _ask_path(document_version_id: UUID | None) -> str:
    """`LEGALMIND_ASK_MULTI_SOURCE` (`AM-106`): on (default) → the multi-source path
    for every conversation; no_document → it only where no document is in scope;
    off → the previous path for all. No share, no hash, no cohort."""
    flag = config.ask_multi_source()
    if flag == "on" or (flag == "no_document" and document_version_id is None):
        return MULTI_SOURCE
    return LEGACY


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
    user_message_id = _append_turn(db, conversation_id, "USER", question)

    # `AM-109` — a turn that is ONLY social is answered here, before a follow-up can
    # resolve against it and before any retrieval: "thanks" re-answered the previous
    # legal question, and "hi" came back as a statute-corpus refusal. Fixed wording,
    # no source, no model; "who are you" / "help" take the capability manifest.
    social = conversational.kind(question)
    if social is not None:
        return _social_reply(db, conversation_id, social, request_id)
    # A social lead around a real question is not part of it ("Hi, what is our cap?").
    # The stored turn above keeps the reader's own words.
    question = conversational.strip_social(question)
    if conversational.off_scope(question):
        # A poem or the weather was searched, and a topic inherited from earlier turns
        # turned "write me a poem" into a confidentiality answer (`AM-109`).
        return _social_reply(db, conversation_id, None, request_id)

    # Conversation memory (2026-09-10). A follow-up — "what about clause 7?" — is
    # resolved by the requester's own earlier questions: they widen the RETRIEVAL
    # query and the routing input, and they are listed to the model as context.
    # They never add evidence (every chunk below is retrieved fresh, inside the same
    # authorization and version scope), never widen a domain the caller may not read
    # (`routing.plan` still takes the caller's live permission set), and an earlier
    # ANSWER is never read (`AM-30` t2). The persisted USER turn is the raw question.
    prior = _prior_questions(db, conversation_id, user_message_id)
    if not prior and document_version_id is None and intent.has_no_subject(question):
        # "what about it?" with nothing before it and no document: searching it
        # returned whatever shares the most stop words. Ask what they mean instead.
        return _social_reply(db, conversation_id,
                             conversational.Social.UNCLEAR, request_id)
    # An EXACT-TEXT request is always about something already discussed — "the
    # clause", "that wording", "it". It carries no subject of its own, so left
    # unresolved its retrieval query is "quote ... clause ... verbatim", which matches
    # no clause in the document. Measured 2026-09-22 on a live NDA: "Quote the
    # termination clause verbatim", asked straight after a termination answer,
    # retrieved ZERO document chunks and fell through to two ratified standards for
    # VENDOR_AGREEMENT and DISTRIBUTION_AGREEMENT — neither the reader's document nor
    # its type. It inherits the previous turn's subject for the same reason a
    # follow-up does, through the same resolver; with no prior turn nothing changes.
    # The question AS ASKED, read once. Routing separately understands the RESOLVED
    # query (question + inherited subject) — they are different strings and mean
    # different things, so each gets its own reading rather than one being reused for
    # the other.
    asked = understanding.understand(question)
    follow_up = bool(prior) and (asked.follow_up or asked.exact_text)
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
                         statutes_available=statutes.available(db),
                         statute_jurisdictions=statutes.jurisdictions(db))
    # Ask plan 1.3: the conversation's own material is searched in the document lane,
    # as the reader's — never on the evaluator's question, which needs a Review.
    material = attachments.scope(db, conversation_id)
    if material is not None and not route.comparison:
        route = dataclasses.replace(route, domains=tuple(
            d for d in routing._ORDER if d in {*route.domains, routing.Domain.DOCUMENT}))
    domains = tuple(d.value for d in route.domains)
    # `AM-68` r2 — the capability route, before ANY retrieval. Returning here is the
    # enforcement: nothing below this line can reach a document, a position, a statute
    # or a Finding, so the guarantee is structural rather than a promise. On by
    # default since `AM-68` was approved; `LEGALMIND_CAPABILITY_ROUTE=off` rolls it back.
    # `AM-25` r5 — a general explanation resolves to no retrieved evidence, so it is not
    # generated. The question is still RECOGNISED, which is the fix: it no longer falls
    # through to the POSITIONS fallback and comes back as three Company Standards.
    if getattr(route, "general_knowledge", False):
        reply_id = _append_turn(db, conversation_id, "ASSISTANT", GENERAL_KNOWLEDGE_TEXT)
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
            reply_id = _append_turn(db, conversation_id, "ASSISTANT", text_out)
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
    # plan is advisory and fails closed to None — see `assist/query/planner.py`. It steers
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
                topic=topic, allow_relax=_relax_allowed(route))
    # Domain C — retrieved now, answered separately below (AM-32 r8, AM-47 r4).
    statute_hits: list[statutes.StatuteHit] = []
    if route.has(routing.Domain.STATUTES):
        with _stage("statutes"):
            statute_hits = statutes.search_statutes(db, query=resolved,
                                                    include_superseded=route.include_superseded,
                                                    permissions=permissions)

    # AM-25 r4 — the evaluator's question, never answered generatively.
    # A COMPLIANCE ASSESSMENT whose prerequisites are not met is reported as itself.
    # Falling through here is what used to turn "does our NDA comply with the DPDP
    # Act?" into an ordinary position lookup, answering a question the reader did not
    # ask and attaching a yardstick they did not name.
    if route.unmet:
        text_out = (NEEDS_AUTHORITY_TEXT if "NEEDS_AUTHORITY" in route.unmet
                    else NEEDS_DOCUMENT_TEXT)
        reply_id = _append_turn(db, conversation_id, "ASSISTANT", text_out)
        _persist_answer(db, reply_id, None, AssistAnswerState.EVIDENCE_INSUFFICIENT,
                        model=None, prompt_version_id=None, latency_ms=None)
        log_event("assist.ask.needs_prerequisite", request_id=request_id,
                  conversation_id=str(conversation_id), unmet=",".join(route.unmet))
        return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                          answer_state=AssistAnswerState.EVIDENCE_INSUFFICIENT,
                          text=text_out, domains=domains)

    if route.comparison:
        comparison = _latest_review_summary(db, document_version_id)
        route_text = EVALUATOR_ROUTE_TEXT if comparison else EVALUATOR_NO_REVIEW_TEXT
        reply_id = _append_turn(db, conversation_id, "ASSISTANT", route_text)
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

    # PHASE 13 (`AM-94`) — THE branch point, after every screen above (general
    # knowledge, capability, unmet prerequisite, the evaluator's question), none of
    # which it changes. `None` means the multi-source path declined, and the question
    # continues below exactly as it always has.
    if _ask_path(document_version_id) == MULTI_SOURCE:
        multi = _ask_multi_source(
            db, conversation_id=conversation_id, user_message_id=user_message_id,
            question=question, resolved=resolved, prior_texts=prior_texts,
            # Every bounded earlier question, newest last: the planner takes the topic
            # of the most recent one that HAS one, so FIRST → CLAIM → "and the law on
            # that?" keeps FIRST's topic although CLAIM is the anchor. Whether a turn
            # inherits at all is the planner's rule (`query_plan.plan`).
            topic_context=[content for _, content in prior],
            route=route,
            domains=domains, permissions=permissions,
            document_version_id=document_version_id, position_hits=position_hits,
            statute_hits=statute_hits, follow_up_of=follow_up_of, request_id=request_id,
            pinned_evidence=cited_evidence, material=material)
        if multi is not None:
            return multi

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
                topic=topic, allow_relax=_relax_allowed(route),
                require_semantic=True)
        domains = routing.ordered((*domains, routing.Domain.POSITIONS.value))
        _record_fallthrough(db, user_message_id, run_id, question, domains, statute_hits)
    position_findings = _findings_for_standards(
        db, document_version_id, {h.standard_code for h in position_hits}, permissions)

    cited_indexes = sorted({c.chunk_index for c in verification.citations
                            if c.grounded})
    answer_text = _renumber_markers(result.text, cited_indexes)
    reply_id = _append_turn(db, conversation_id, "ASSISTANT", answer_text)
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


#: The multi-source answer's own markers, and the legend that resolves them.
_ANSWER_MARKER = re.compile(r"\s?\[(\d{1,2})\]|[\s,]*\[(?:A|M)\]")
MULTI_SOURCE_STRATEGY = "multi-source-1"


def _ask_multi_source(db: DBSession, *, conversation_id: UUID, user_message_id: UUID,
                      question: str, resolved: str, prior_texts: list[str],
                      topic_context: list[str], route,
                      domains: tuple[str, ...], permissions: frozenset[str],
                      document_version_id: UUID | None, position_hits: list,
                      statute_hits: list, follow_up_of: list[UUID],
                      request_id: str | None,
                      pinned_evidence: list[UUID] | tuple[UUID, ...] = (),
                      material: UUID | None = None) -> AskOutcome | None:
    """The validated PHASE 9–12 path (`AM-85`–`AM-93`) in production: plan → broad
    authorized candidates → rerank → evidence bundle → claim contracts → Gemini →
    every check → the verified answer.

    It answers only when that path produced a VERIFIED generated answer. Otherwise
    — nothing answerable, generation unavailable, or verification failing — it
    returns None and the legacy path below answers or refuses exactly as it does
    today, so this path can only add a verified answer, never a new refusal or a
    new kind of fallback text. The caller's live permissions scope every search
    (`retrieval.candidates` → the same permission-checked searches the legacy path
    uses); nothing here reads a domain the router did not authorize.
    """
    from legalmind.assist.query import query_plan
    from legalmind.assist.retrieval import evidence as evidence_mod
    from legalmind.assist.retrieval import retrieval
    from legalmind.assist.synthesis import answer as answer_mod

    _trace(selected_path=MULTI_SOURCE, path=MULTI_SOURCE)
    calls: list[generation.GenerationResult] = []

    def _recorded(fn):
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            calls.append(result)
            return result
        return wrapped

    def _fell_back(exc: Exception) -> None:
        _audit_calls(db, calls, conversation_id, request_id, 0)   # any egress is audited
        _trace(path=LEGACY, fallback_kind=f"multi_source_error:{type(exc).__name__}")
        log_event("assist.ask.multi_source_failed", level=logging.WARNING,
                  request_id=request_id, error=type(exc).__name__,
                  conversation_id=str(conversation_id), operational_failure=True)

    # Every database read this path makes runs under a savepoint, so a failed query
    # cannot poison the transaction the legacy path then continues in. The savepoint
    # is CLOSED before the provider is called: the connection is released for the
    # round-trip (`_release_connection`), and `respond` touches no table after
    # `prepare` — which is why `prepare` runs here and not inside it.
    savepoint = db.begin_nested()
    try:
        with _stage("planning"):
            # Roadmap §15: the planner inherits the earlier TOPIC when this turn names
            # none — "What if the customer says they were promised 6 months?" after an
            # early-termination question. That turn is not anaphoric, so `prior_texts`
            # (which also reach the retrieval query and the model) stay empty; the
            # topic still carries, exactly as the benchmark validated. Only the topic:
            # the earlier question's claims and figures never do (`query_plan.plan`).
            plan = query_plan.plan(resolved, has_document=(document_version_id is not None
                                                           or material is not None),
                                   prior=tuple(topic_context), instruction=question)
        with _stage("retrieval"):
            pool = retrieval.candidates(db, plan, route, permissions=permissions,
                                        document_version_id=document_version_id,
                                        pinned_evidence=tuple(pinned_evidence),
                                        material=material)
        with _stage("rerank"):
            pool = retrieval.rerank(pool, plan)
        bundle = evidence_mod.build(db, plan, pool, retrieval.select(pool, plan))
        _trace(plan_lanes=sorted(plan.lanes), plan_parts=len(plan.sub_questions),
               retrievers=sorted(pool.searched), candidates=len(pool.refs()),
               evidence_refs=[x.ref for x in bundle.shown()],
               answerable=bundle.answerable)
        if not bundle.answerable:
            savepoint.rollback()
            _trace(path=LEGACY, fallback_kind="multi_source_not_answerable")
            return None
        prepared = answer_mod.prepare(bundle, question, db)
    except Exception as exc:                  # the legacy path is the proven one
        savepoint.rollback()
        _fell_back(exc)
        return None
    savepoint.commit()
    try:
        with _stage("generation"):
            ans = answer_mod.respond(
                bundle, question, environment=config.environment(),
                prior_questions=tuple(prior_texts), request_id=request_id,
                prepared=prepared,
                generate=_recorded(generation.generate_contract_answer),
                repair=_recorded(functools.partial(
                    generation.generate_bundle_repair,
                    template=generation.CONTRACT_PROMPT_TEMPLATE)))
    except Exception as exc:
        _fell_back(exc)
        return None
    _audit_calls(db, calls, conversation_id, request_id, len(ans.refs))
    _trace(generated=ans.generated, gemini_ms=ans.latency_ms, prepare_ms=ans.prepare_ms,
           verify_ms=ans.verify_ms, verifier=config.nli_model_repo(),
           verifier_revision=config.nli_model_revision(),
           provider_finish=ans.finish_reason,
           verification_failures=sorted({_failure_kind(f) for f in ans.failures}))
    if not ans.generated:
        _trace(path=LEGACY, fallback_kind="multi_source_not_verified")
        return None
    text_out, cited_refs = _multi_source_text(ans, bundle)
    run_id = _persist_multi_source_run(db, user_message_id, resolved, plan, pool, bundle,
                                       cited_refs, document_version_id, domains,
                                       follow_up_of)
    cited_codes = {r.removeprefix("POS:") for r in cited_refs if r.startswith("POS:")}
    cited_positions = [h for h in position_hits if h.standard_code in cited_codes]
    cited_statutes = [h for h in statute_hits
                      if f"STAT:{h.official_title.removeprefix('The ')}:"
                         f"{h.section_number}" in cited_refs]
    reply_id = _append_turn(db, conversation_id, "ASSISTANT", text_out)
    answer_id = _persist_answer(
        db, reply_id, run_id, AssistAnswerState.ANSWERED, model=ans.model,
        prompt_version_id=_prompt_version_id(db, generation.CONTRACT_PROMPT_VERSION,
                                             generation.CONTRACT_PROMPT_TEMPLATE),
        latency_ms=ans.latency_ms)
    _persist_position_citations(db, answer_id, cited_positions)
    # The document's cited clauses as citations, in marker order ([1]..[d]), recorded
    # in `answer_citations` so a reloaded conversation shows the same links.
    doc_hits = store.chunks_by_id(
        db, document_version_id=document_version_id,
        chunk_ids=[UUID(r.removeprefix("DOC:")) for r in cited_refs
                   if r.startswith("DOC:")]) if document_version_id else []
    _persist_citations(db, answer_id, list(range(1, len(doc_hits) + 1)), doc_hits)
    # D15 "cite both blocks": a cited clause that runs on into the next block is shown
    # with that block, labelled, in the SAME card — the answer was verified against
    # both (`retrieval.with_context`), and a separate card would renumber the legend.
    runs_on = {h.chunk_id: store.continuation(db, h.chunk_id) for h in doc_hits}

    def _with_continuation(h) -> str:
        m = runs_on[h.chunk_id]
        if m is None:
            return h.content
        page = f" on page {m.page_number}" if m.page_number else ""
        return f"{h.content}\n[continued{page}]\n{m.content}"
    citations = [CitationView(chunk_id=h.chunk_id, evidence_id=h.evidence_id,
                              page_number=h.page_number, section_ref=h.section_ref,
                              excerpt=h.content[:240], text=_with_continuation(h),
                              retrieval_score=h.retrieval_score) for h in doc_hits]
    statute_section = None
    if cited_statutes:
        cited_idx = list(range(1, len(cited_statutes) + 1))
        _persist_statute_citations(db, answer_id, cited_statutes, cited_idx)
        statute_section = {"text": "", "citations": _statute_views(cited_statutes,
                                                                    cited_idx)}
    if any(runs_on.values()):
        import json as _json
        db.execute(text(f"""
            UPDATE "{config.assist_schema()}".retrieval_runs
               SET results = jsonb_set(results, '{{continuations}}', CAST(:c AS jsonb))
             WHERE id = :r"""), {"r": run_id, "c": _json.dumps(
            {f"DOC:{k}": str(m.chunk_id) for k, m in runs_on.items() if m})})
    _trace(cited_refs=cited_refs, cited_positions=len(cited_positions),
           cited_statutes=len(cited_statutes),
           cited_constitution=sum(r.startswith("CONST:") for r in cited_refs))
    log_event("assist.ask.answered", request_id=request_id,
              conversation_id=str(conversation_id), citations=str(len(cited_refs)),
              positions=str(len(cited_positions)))
    by_ref = {src.ref: src for src in bundle.shown()}
    extra = tuple(ledger.Record(
        ("H" if src.candidate.authority == "HISTORICAL_EXCEPTION" else "C")
        if ref.startswith("CONST:") else "U", ref, src.candidate.item_id,
        src.candidate.text, src.candidate.authority or "COMPANY_CONSTITUTION",
        src.candidate.status.lower(), ref.removeprefix("CONST:")
        if ref.startswith("CONST:") else None)
        for ref in cited_refs if ref.startswith(("CONST:", "ATT:"))
        for src in [by_ref.get(ref)] if src is not None)
    return AskOutcome(conversation_id=conversation_id, message_id=reply_id,
                      answer_state=AssistAnswerState.ANSWERED, text=text_out,
                      citations=citations,
                      positions=_position_views(cited_positions), domains=domains,
                      statutes=statute_section, ledger_extra=extra)


def _audit_calls(db, calls, conversation_id, request_id, evidence_chunks: int) -> None:
    """AM-30 t5 — every egress audited, whether or not its text is shown, and also
    when the path fails after the provider returned (it fell back unaudited before)."""
    from legalmind.security import audit as audit_log
    for result in calls:
        audit_log.record(
            db, action=audit_log.ASSIST_GENERATION_CALLED, entity_type="conversation",
            entity_id=conversation_id, request_id=request_id,
            after={"provider": getattr(result, "provider", "gemini"),
                   "model": result.model,
                   "model_version": getattr(result, "model_version", None),
                   "prompt_version": result.prompt_version,
                   "payload_sha256": result.payload_sha256,
                   "evidence_chunks": evidence_chunks})


def _failure_kind(failure: str) -> str:
    """A verification failure's KIND for the trace — cut before any quoted, cited or
    bracketed part, so no evidence text reaches the log ("antecedent of 'that sum' in
    [2] lost ('...')" kept 60 characters of source text before)."""
    return re.split(r"""[:(\["]| '| of \[""", failure, maxsplit=1)[0].strip()[:60]


def _multi_source_text(ans, bundle) -> tuple[str, list[str]]:
    """The verified answer for the existing response contract: its claim markers
    renumbered in order of first use, [A]/[M] (internal to the payload) removed, and
    a deterministic Sources legend — each number's citation label, nothing else —
    because the main answer's markers resolve only against a DOCUMENT's sources in
    the current UI, and a no-document answer has none. Returns the cited refs in
    that order (what `retrieval_runs.results` records)."""
    from legalmind.assist.synthesis import answer as answer_mod

    by_ref = {s.ref: s for s in bundle.shown()}
    body = _layered(ans.text, getattr(ans, "layers", ()))
    # One number per SOURCE, not per claim: three claims of §16 were listed as three
    # identical "§16" lines in the legend (2026-09-27).
    refs: list[str] = []
    for m in re.finditer(r"\[(\d{1,2})\]", body):
        n = int(m.group(1))
        if 1 <= n <= len(ans.refs) and ans.refs[n - 1] not in refs:
            refs.append(ans.refs[n - 1])
    # The reader's own document first (`AM-106`): its clauses take [1]..[d], so they
    # line up with the answer's `citations` — the list the document view links a
    # marker to — and the Constitution, standards and law follow in the legend.
    refs = [r for r in refs if r.startswith("DOC:")] + \
        [r for r in refs if not r.startswith("DOC:")]

    def _marker(m: re.Match) -> str:                  # [A]/[M]: removed with their comma
        key = m.group(1)
        ok = key and 1 <= int(key) <= len(ans.refs)
        return f" [{refs.index(ans.refs[int(key) - 1]) + 1}]" if ok else ""
    text_out = "\n\n".join(_ANSWER_MARKER.sub(_marker, block).strip()
                           for block in body.split("\n\n"))
    text_out = re.sub(r"(\[\d{1,2}\])(?:\s?\1)+", r"\1", text_out)   # "[1] [1]" → "[1]"
    labels = []
    for i, ref in enumerate(refs, 1):
        if ref.startswith("DOC:"):
            continue        # the document's clauses are the answer's citation cards
        source = by_ref.get(ref)
        labels.append(f"[{i}] " + (answer_mod.citation(source) if source else ref))
    if labels:
        # Its own block, one "- " line per source: the answer renderer lists a block
        # only when every line is a list line, so "Sources" on the first line ran the
        # whole legend into one paragraph ("Sources [1] … [2] …").
        text_out += "\n\nSources\n\n" + "\n".join(
            f"- {x}" if len(labels) > 1 else x for x in labels)
    return text_out, refs


#: `AM-107`: how the verified answer is laid out — the direct answer first, then each
#: other layer under its own fixed label, so related rules, past negotiated deals and
#: the law never read as part of the direct answer.
LAYER_LABELS = (("RELATED", "Also relevant"),
                ("HISTORY", "Historical context — past negotiated deals, not current "
                            "policy"),
                ("LAW", "Legal background"))


# "Additionally, …" / "Finally, …" linked a sentence to the one before it in the
# model's paragraph; under its own heading it links to nothing. Only the connective
# goes — a discourse word, never a term of the claim.
_CONNECTIVE = re.compile(r"^(?:Additionally|Furthermore|Moreover|Finally|Also|In "
                         r"addition|Separately),\s+(\w)")
_RESTATES_QUESTION = re.compile(r"^(?:The (?:reader|user|question) (?:asked|asks|wants)|"
                                r"You (?:asked|want to know))\b", re.I)


def _layered(text: str, layers: tuple[str, ...]) -> str:
    """The verified sentences grouped by the layer of the first claim each cites, in
    their own order within a layer. Nothing is reworded, added or dropped: the words
    are exactly what verification passed. A sentence citing no claim ([A], [M]) stays
    with the direct answer; one that only restates the question, citing nothing, is
    left out. With no layers recorded, the text is returned unchanged."""
    from legalmind.assist.synthesis import answer as answer_mod

    if not layers:
        return text
    groups: dict[str, list[str]] = {}
    # A table (`AM-108`) is one verified unit: it stays whole, with the direct answer.
    prose, table = answer_mod.split_table(text)
    sentences = answer_mod._sentences(prose)
    for sentence in sentences:
        others = "".join(x for x in sentences if x != sentence)
        # An [A] with no figure carries nothing of the reader's to answer ("The reader
        # asked about data breach notifications under the DPDP Act [A]", browser,
        # 2026-09-29, `AM-109`); one naming the reader's figure, or a gap [M], stays.
        if _RESTATES_QUESTION.match(sentence) \
                and not re.search(r"\[\d{1,2}\]", sentence) \
                and all(m in others or (m == "[A]" and not re.search(r"\d", sentence))
                        for m in re.findall(r"\[[AM]\]", sentence)):
            continue            # "The reader asked whether …": no claim, only delay
        cited = [int(n) for n in re.findall(r"\[(\d{1,2})\]", sentence)
                 if 1 <= int(n) <= len(layers)]
        groups.setdefault(layers[cited[0] - 1] if cited else "PRIMARY",
                          []).append(sentence.strip())
    def joined(sents: list[str]) -> str:       # bullet lines stay lines
        return ("\n" if any(answer_mod._BULLET.match(x) for x in sents)
                else " ").join(sents)
    lead = groups.pop("PRIMARY", [])
    blocks = [joined(lead)] if lead else []
    if table:
        blocks.append(table)
    for layer, label in LAYER_LABELS:
        said = groups.get(layer)
        if not said:
            continue
        if not blocks and layer == "RELATED":       # nothing primary: this IS the answer
            blocks.append(joined(said))
            continue
        blocks.append(label)
        said = [_CONNECTIVE.sub(lambda m: m.group(1).upper(), x) for x in said]
        blocks.append("\n".join(x if answer_mod._BULLET.match(x) else f"- {x}"
                                 for x in said) if len(said) > 1 else said[0])
    return "\n\n".join(blocks)


def _persist_multi_source_run(db: DBSession, message_id: UUID, query: str, plan, pool,
                              bundle, cited_refs: list[str],
                              document_version_id: UUID | None,
                              domains: tuple[str, ...], follow_up_of: list[UUID]) -> UUID:
    """`retrieval_runs` for a multi-source answer — identifiers and scores only (r6):
    the candidates, the evidence the bundle showed and what the answer cited,
    Constitution refs included (no citation column exists for them, owner 2026-09-26)."""
    import json as _json

    run_id = uuid.uuid4()
    filters: dict = {"document_version_id": (str(document_version_id)
                                             if document_version_id else None),
                     "domains": list(domains), "path": MULTI_SOURCE,
                     "plan": {"lanes": sorted(plan.lanes),
                              "parts": len(plan.sub_questions)}}
    if follow_up_of:
        filters["follow_up_of"] = [str(i) for i in follow_up_of]
    results = {
        "candidates": [{"ref": c.ref, "item_id": str(c.item_id), "domain": c.domain}
                       for cs in pool.by_domain.values() for c in cs][:100],
        "evidence": [{"ref": x.ref, "item_id": str(x.candidate.item_id),
                      "kind": x.kind} for x in bundle.shown()],
        "cited": cited_refs,
        "constitution_cited": [r for r in cited_refs if r.startswith("CONST:")],
    }
    db.execute(text(f"""
        INSERT INTO "{config.assist_schema()}".retrieval_runs
            (id, message_id, query_text, filters, results, strategy_version)
        VALUES (:i, :m, :q, CAST(:f AS jsonb), CAST(:r AS jsonb), :v)
    """), {"i": run_id, "m": message_id, "q": query, "f": _json.dumps(filters),
           "r": _json.dumps(results), "v": MULTI_SOURCE_STRATEGY})
    return run_id


STATUTES_ONLY_TEXT = ("Answered from the approved statute corpus, cited by Act and "
                      "section below.")
STATUTES_BESIDE_TEXT = (
    "No answer was found in the selected document. The approved statute corpus answers "
    "below, cited by Act and section.")


def _relax_allowed(route: routing.RoutePlan) -> bool:
    """May the position lane use its RELAX rescue for this question?

    The rescue admits a chunk sharing ONE lexeme, and `positions.search_positions`
    states its own premise: it is "the right trade when the reader is asking the
    organization about its own paper". This enforces that premise instead of assuming
    it. Measured on the live corpus 2026-09-23: "what's the weather in pune" reached
    the governing-law standard through `pune` — a real venue lexeme in a real
    standard — and "how long do I have to file an appeal" and "draft me an NDA"
    reached NDA standards the same way, each then quoted to the reader as "the
    organization's approved position relevant to this question".

    The strict floor is untouched, the calibrated gate is untouched, and the rescue
    still runs for every question that IS about the organization's own material —
    including "Explain our termination standard.", which shares exactly one lexeme
    with every termination chunk and is the reason the rescue exists (2026-09-16).
    """
    return (not route.statute_shaped
            and understanding.POSITION in route.asked_authority)


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
                topic=topic, allow_relax=_relax_allowed(route),
                require_semantic=True)
        elif domain is routing.Domain.STATUTES and not statute_hits:
            # Source priority, not a fixed sweep: the statute corpus is a fallback
            # for a question about the law (statute-shaped) or for one nothing
            # closer could answer. A contract question the organization's own
            # position already answers is NOT also put to 5,000 statute sections —
            # measured live, that produced a grounded Copyright Act answer about
            # licence termination beside the relevant position on notice periods.
            # PRESENCE OF ROWS IS NOT THE SAME AS "THE POSITIONS ANSWER IT".
            # Position retrieval is lexical-first and ungated — "a lexical hit is
            # trusted on its own" — so two shared lexemes returns rows. Measured
            # 2026-09-23: "within what time must a cyber incident be reported?"
            # matched CLAIM-WINDOW-SLA-001, "how long do I have to file an appeal?"
            # matched CONF-SURVIVAL-NDA-001, and on the strength of those coincidences
            # the statute corpus was never searched at all — though it holds the
            # CERT-In Directions and IT Act s.57 that answer them.
            #
            # The original rule's intent stands and is kept: a question the
            # organization's own position genuinely answers is not also put to 5,000
            # statute sections. What changes is the test. Suppression now requires
            # that the reader actually asked about the organization's material —
            # `authority` carries that — instead of inferring it from the fact that
            # a lexical query returned something.
            # "The organization's own material already answered" presupposes that the
            # question IS about the organization's own material. Two ways that is
            # true: a document is open — the reader is working on their paper, and
            # the pre-existing guard below covers exactly that case — or the question
            # asks about our position. Neither holds for the three measured failures:
            # no document, no position asked for, and a two-lexeme coincidence was
            # doing the deciding.
            own_material = (understanding.POSITION in route.asked_authority
                            or route.has(routing.Domain.DOCUMENT))
            if position_hits and not route.statute_shaped and own_material:
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
    exact_text_requested = understanding.understand(question).exact_text
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
                wording = f"{aid.text} {LEGAL_REVIEW_TEXT}"
        # `AM-78` r1 — the reader's own figure, compared exactly, never by the model.
        unstated = guardrails.unstated_figures(
            question, [h.content for h in position_hits])
        if unstated:
            wording = (f"The approved position cited here does not state "
                       f"{' or '.join(unstated)}. {wording}")
    # r2 or r4: nothing was paraphrased, so `wording` points at the quote instead of
    # being one. Not the statute path, which answers in its own section.
    quote_is_the_answer = not statute_answered and aid is None
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
    reply_id = _append_turn(db, conversation_id, "ASSISTANT", wording)
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
                      quote_is_the_answer=quote_is_the_answer,
                      positions=_position_views(position_hits), domains=domains,
                      statutes=statute_section)
