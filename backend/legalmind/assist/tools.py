"""The Ask agent's tool layer — Ask plan Phase 2 (2.1–2.6), architecture v2.1 §5.3.

Seven read-only tools the Phase 3 agent loop will offer the model. Each one WRAPS code
that already ships — `constitution.search`, `positions.search_positions`,
`statutes.search_statutes`, `store.search_hybrid`, `attachments`, `ledger.refetch` — and
adds only a contract around it: strict arguments, an authorization boundary, a response
envelope and quality signals. No second retrieval, ranking or permission rule exists here.

Not exposed by any endpoint and not wired into Ask until Phase 3; only tests call it.

THE CONTRACT (DECISIONS A-23 … A-26):

  WHO is never an argument. `ToolContext` is built by server code from the authenticated
  user, their live permission set and a conversation that user owns. The model supplies
  only the fields of one tool's argument model — `extra="forbid"`, so a `user_id`,
  `permissions`, `department` or any other unknown field is refused, never ignored.

  ONE ANSWER FOR "NOT YOURS". Every ID a model may pass (a document version, an
  attachment) resolves in ONE query that joins the authorization rule; malformed,
  missing, nonexistent and another user's IDs all return the identical `NOT_FOUND`
  envelope by the same code path. Evidence keys answer per key with the ledger's own
  `unavailable`. An over-long or out-of-schema value is `INVALID_ARGUMENT` — no valid ID
  is ever that shape, so the bound reveals nothing.

  READ-ONLY. Every call runs inside a SAVEPOINT that is always rolled back, so no path can
  leave a write behind; the tests also prove none is attempted (`pg_stat_xact`). No tool
  calls the provider: the rescue judge is not reached (`search_hybrid` without a pool),
  and Phase 3's model re-searches instead (architecture §12). Ledger keys are assigned
  when an answer is recorded, not by a tool — a tool that assigned them would write.

  QUALITY SIGNALS from existing semantics, never invented. Documents and attachments:
  the calibrated gate's own `gate_open` / lexical hit / top score. Constitution,
  positions and statutes admit only what passes their own rule, so `gate_open` is "the
  domain returned something"; `lexical_hit` is the calibrated strict match (a returned
  record carries every query lexeme); `top_score` is the first record's own score, None
  when nothing returned. Non-search tools report `count_returned` only.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist import (
    attachments,
    authority,
    constitution,
    ledger,
    positions,
    store,
)
from legalmind.assist import statutes as statute_corpus
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

MAX_K = 8
#: A question a person would type; long pasted material is an attachment, not a query.
MAX_QUERY_CHARS = 500
#: Longer than any id or key this system issues (a UUID is 36); short enough to bound
#: the work an argument can cause.
MAX_ID_CHARS = 64

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                         max_length=MAX_QUERY_CHARS)]
AnId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                        max_length=MAX_ID_CHARS)]
K = Annotated[int, Field(ge=1, le=MAX_K)]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SearchKnowledgeArgs(_Args):
    """Constitution, ratified standards and the conversation's own document. `sources`
    may only NARROW what the caller is already permitted; `document_version_id` may only
    name a version of the conversation's own contract."""
    query: Query
    sources: Annotated[list[Literal["constitution", "positions", "documents"]],
                       Field(min_length=1, max_length=3)] = [
        "constitution", "positions", "documents"]
    document_version_id: AnId | None = None
    k: K = 5


class CompanyPositionArgs(_Args):
    """The ratified positions, verbatim (`AM-32` r4)."""
    topic: Query
    k: K = 5


class SearchStatutesArgs(_Args):
    """The admitted statute corpus. Repealed and superseded text only when asked."""
    query: Query
    include_superseded: bool = False
    k: K = 5


class GetEvidenceArgs(_Args):
    """Re-fetch ledger records of THIS conversation by key (Ask plan 1.8)."""
    evidence_ids: Annotated[list[AnId], Field(min_length=1, max_length=MAX_K)]


class ListAttachmentsArgs(_Args):
    """No arguments: always this conversation's own material."""


class SearchAttachmentArgs(_Args):
    """Inside ONE of this conversation's attachments."""
    attachment_id: AnId
    query: Query
    k: K = 5


class AskUserArgs(_Args):
    """End the turn with one clarifying question (architecture §5.2: at most one)."""
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                               max_length=300)]
    options: Annotated[list[Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=80)]],
        Field(max_length=4)] = []


class Record(BaseModel):
    model_config = ConfigDict(frozen=True)
    ref: str                     # natural key: CONST: / POS: / STAT: / DOC: / ATT:
    #: constitution · positions · statutes · documents · attachments
    source: str
    authority: str
    status: str
    location: str | None
    text: str
    #: The row behind the record (chunk / item id) — the ledger's fast-path pointer.
    item_id: str | None = None
    #: How many of the query's terms the record carries (Constitution, statutes): those
    #: searches fuse an UNGATED vector list, so a record below their own two-term
    #: lexical floor is a pure nearest neighbour — weak evidence (A-37).
    matched_terms: int | None = None
    query_terms: int | None = None


class Quality(BaseModel):
    model_config = ConfigDict(frozen=True)
    gate_open: bool
    lexical_hit: bool
    top_score: float | None
    count_returned: int


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_id: str
    state: Literal["current", "stale", "unavailable"]
    ref: str | None = None
    authority: str | None = None
    text: str | None = None


class ToolResult(BaseModel):
    """The one envelope every tool returns. `error` is None on success."""
    model_config = ConfigDict(frozen=True)
    tool: str
    error: Literal["NOT_FOUND", "INVALID_ARGUMENT"] | None = None
    records: tuple[Record, ...] = ()
    quality: Quality | None = None
    by_source: dict[str, Quality] | None = None
    evidence: tuple[EvidenceRecord, ...] = ()
    attachments: tuple[dict, ...] = ()
    question: str | None = None
    options: tuple[str, ...] = ()
    count_returned: int = 0


@dataclass(frozen=True)
class ToolContext:
    """Built by SERVER code, never from model output (Ask plan 2.3)."""
    db: DBSession
    user_id: UUID
    permissions: frozenset[str]
    conversation_id: UUID
    contract_id: UUID | None

    @classmethod
    def open(cls, db: DBSession, *, user_id: UUID, permissions: frozenset[str],
             conversation_id: UUID) -> ToolContext:
        """The conversation must be the caller's own — `NotVisible` otherwise, the same
        discipline as the router's `_visible_conversation`. A contract the caller can
        no longer read is dropped from scope here, once, for every tool."""
        from legalmind.db import models as M
        from legalmind.security.authorization import can_read_contract
        row = db.execute(text(
            f'SELECT user_id, contract_id FROM "{config.assist_schema()}".conversations '
            "WHERE id = :c"), {"c": conversation_id}).first()
        if row is None or row[0] != user_id:
            raise NotVisible("conversation", conversation_id)
        contract = db.get(M.Contract, row[1]) if row[1] is not None else None
        readable = (contract is not None and P.ASSIST_ASK in permissions
                    and can_read_contract(db, user_id, contract))
        return cls(db, user_id, frozenset(permissions), conversation_id,
                   contract.id if readable and contract is not None else None)


# ---------------------------------------------------------------------------- helpers
def _strict_lexical(db: DBSession, query: str, texts: list[str]) -> bool:
    """The calibrated gate's lexical signal: a record carrying EVERY query lexeme."""
    if not texts:
        return False
    return bool(db.execute(text(
        "SELECT bool_or(to_tsvector('english', t) @@ "
        "websearch_to_tsquery('english', :q)) "
        "FROM unnest(CAST(:ts AS text[])) AS t"), {"q": query, "ts": texts}).scalar())


def _matched(db: DBSession, query: str, texts: list[str]) -> list[int]:
    """Per text, the number of the query's lexemes it contains (english stemming, the
    same lexemes the lexical searches match on)."""
    if not texts:
        return []
    return [int(n) for n in db.execute(text(
        "SELECT (SELECT count(*) FROM "
        "unnest(tsvector_to_array(to_tsvector('english', :q))) l "
        "WHERE to_tsvector('english', t) @@ to_tsquery('english', quote_literal(l))) "
        "FROM unnest(CAST(:ts AS text[])) WITH ORDINALITY AS u(t, n) ORDER BY n"),
        {"q": query, "ts": texts}).scalars()]


def _with_terms(db: DBSession, query: str, recs: list[Record]) -> list[Record]:
    counts = _matched(db, query, [r.text for r in recs])
    total = _matched(db, query, [query])[0] if recs else 0
    return [r.model_copy(update={"matched_terms": n, "query_terms": total})
            for r, n in zip(recs, counts, strict=True)]


def _quality(db, query: str, records: list[Record], scores: list[float]) -> Quality:
    return Quality(gate_open=bool(records),
                   lexical_hit=_strict_lexical(db, query, [r.text for r in records]),
                   top_score=scores[0] if scores else None,
                   count_returned=len(records))


def _version_in_scope(ctx: ToolContext, document_version_id: str | None) -> UUID | None:
    """THE document-scope resolution: one query, authorization joined. None for every
    failure — malformed, missing, another contract's, another user's."""
    if ctx.contract_id is None:
        return None
    if document_version_id is None:
        return ctx.db.execute(text(
            "SELECT id FROM document_versions WHERE contract_id = :k "
            "ORDER BY version_number DESC LIMIT 1"), {"k": ctx.contract_id}).scalar()
    try:
        wanted = UUID(document_version_id)
    except ValueError:
        wanted = None              # the same query runs, and finds nothing
    return ctx.db.execute(text(
        "SELECT id FROM document_versions "
        "WHERE id = CAST(:v AS uuid) AND contract_id = :k"),
        {"v": str(wanted) if wanted else None, "k": ctx.contract_id}).scalar()


def _attachment_in_scope(ctx: ToolContext, attachment_id: str) -> UUID | None:
    try:
        wanted: str | None = str(UUID(attachment_id))
    except ValueError:
        wanted = None
    return ctx.db.execute(text(
        f'SELECT id FROM "{config.assist_schema()}".conversation_attachments '
        "WHERE id = CAST(:a AS uuid) AND conversation_id = :c AND status = 'READY' "
        "AND expires_at > now()"), {"a": wanted, "c": ctx.conversation_id}).scalar()


def _embed():
    from legalmind.assist import embedding_runtime
    return embedding_runtime.embed_query


# ------------------------------------------------------------------------------ tools
def _constitution(ctx: ToolContext, query: str, k: int):
    hits = constitution.search(ctx.db, query=query, permissions=ctx.permissions, limit=k)
    recs = [Record(ref=f"CONST:{h.section_path}", source="constitution",
                   authority=h.authority, status=h.status, location=h.section_path,
                   text=h.content, item_id=str(h.item_id)) for h in hits]
    recs = _with_terms(ctx.db, query, recs)
    return recs, _quality(ctx.db, query, recs, [h.score for h in hits])


def _positions(ctx: ToolContext, query: str, k: int):
    hits = positions.search_positions(ctx.db, query=query, permissions=ctx.permissions,
                                      limit=k)
    recs = [Record(ref=f"POS:{h.standard_code}", source="positions",
                   authority="COMPANY_STANDARD", status="current",
                   location=h.source_clause, text=h.content,
                   item_id=str(h.position_chunk_id)) for h in hits]
    return recs, _quality(ctx.db, query, recs, [h.score for h in hits])


def _documents(ctx: ToolContext, query: str, k: int, version: UUID):
    """The top `k` candidates WHATEVER the calibrated gate decided, with its decision as
    a signal (architecture v2.1 §5.3: the gate "does not block the turn"; DECISIONS
    A-31). Measured 2026-10-03: 18 of the frozen set's 22 document misses had the gold
    clause in the top 10 behind a shut gate, so a gated tool could never show it to the
    agent. The gate's values and the current pipeline are unchanged."""
    out = store.search_hybrid(ctx.db, document_version_id=version, query=query,
                              embed_query=_embed(), limit=k, candidates=True)
    label = authority.of_document(store.version_role(ctx.db, version)) or "DRAFT_DOCUMENT"
    recs = [Record(ref=f"DOC:{h.chunk_id}", source="documents", authority=label,
                   status="executed" if label == "EXECUTED_DOCUMENT" else "draft",
                   location=h.section_ref or (f"p.{h.page_number}" if h.page_number
                                              else None), text=h.content,
                   item_id=str(h.chunk_id))
            for h in out.hits]
    # The calibrated feature itself — the question's best cosine — so "close to the
    # floor" means the same thing to the model as to the gate (B5).
    return recs, Quality(gate_open=out.gate_open, lexical_hit=out.lexical_hit,
                         top_score=out.vector_top_score, count_returned=len(recs))


def search_knowledge(ctx: ToolContext, a: SearchKnowledgeArgs) -> ToolResult:
    version = None
    if "documents" in a.sources:
        version = _version_in_scope(ctx, a.document_version_id)
        if a.document_version_id is not None and version is None:
            return ToolResult(tool="search_knowledge", error="NOT_FOUND")
    records: list[Record] = []
    by_source: dict[str, Quality] = {}
    for source in dict.fromkeys(a.sources):
        if source == "constitution":
            recs, q = _constitution(ctx, a.query, a.k)
        elif source == "positions":
            recs, q = _positions(ctx, a.query, a.k)
        elif version is not None:
            recs, q = _documents(ctx, a.query, a.k, version)
        else:                      # no document in this conversation's scope
            recs, q = [], Quality(gate_open=False, lexical_hit=False, top_score=None,
                                  count_returned=0)
        records += recs
        by_source[source] = q
    return ToolResult(tool="search_knowledge", records=tuple(records),
                      by_source=by_source, count_returned=len(records))


def get_company_position(ctx: ToolContext, a: CompanyPositionArgs) -> ToolResult:
    recs, q = _positions(ctx, a.topic, a.k)
    return ToolResult(tool="get_company_position", records=tuple(recs), quality=q,
                      count_returned=len(recs))


def search_statutes(ctx: ToolContext, a: SearchStatutesArgs) -> ToolResult:
    hits = statute_corpus.search_statutes(ctx.db, query=a.query,
                                          permissions=ctx.permissions, limit=a.k,
                                          include_superseded=a.include_superseded)
    recs = [Record(ref=f"STAT:{h.official_title.removeprefix('The ')}:{h.section_number}",
                   source="statutes",
                   authority=authority.of_statute(h.official_title)[0],
                   status=authority.of_statute(h.official_title)[1].lower(),
                   location=h.citation, text=h.content,
                   item_id=str(h.statute_chunk_id)) for h in hits]
    recs = _with_terms(ctx.db, a.query, recs)
    return ToolResult(tool="search_statutes", records=tuple(recs),
                      quality=_quality(ctx.db, a.query, recs, [h.score for h in hits]),
                      count_returned=len(recs))


def get_evidence(ctx: ToolContext, a: GetEvidenceArgs) -> ToolResult:
    """Per key: `current` (visible, text unchanged), `stale` (visible, but changed or
    superseded), `unavailable` (not visible now, expired, or never existed — one
    shape, no text). Read live under the caller's permissions (`ledger.refetch`)."""
    got = ledger.refetch(ctx.db, conversation_id=ctx.conversation_id,
                         keys=list(dict.fromkeys(a.evidence_ids)),
                         permissions=ctx.permissions, contract_id=ctx.contract_id)
    ev = tuple(EvidenceRecord(evidence_id=f.key, state=f.state,  # type: ignore[arg-type]
                              ref=f.source_ref if f.text is not None else None,
                              authority=f.authority if f.text is not None else None,
                              text=f.text) for f in got)
    return ToolResult(tool="get_evidence", evidence=ev,
                      count_returned=sum(e.state != "unavailable" for e in ev))


def list_attachments(ctx: ToolContext, a: ListAttachmentsArgs) -> ToolResult:
    if P.ASSIST_ASK not in ctx.permissions:
        return ToolResult(tool="list_attachments")
    rows = tuple({"attachment_id": str(x.id), "kind": x.kind, "filename": x.filename,
                  "mime_type": x.mime_type,
                  "status": ("UNAVAILABLE" if x.status == attachments.EXPIRED
                             else x.status),
                  "failure_code": x.failure_code}
                 for x in attachments.list_for(ctx.db, ctx.conversation_id))
    return ToolResult(tool="list_attachments", attachments=rows, count_returned=len(rows))


def search_attachment(ctx: ToolContext, a: SearchAttachmentArgs) -> ToolResult:
    found = _attachment_in_scope(ctx, a.attachment_id) \
        if P.ASSIST_ASK in ctx.permissions else None
    if found is None:
        return ToolResult(tool="search_attachment", error="NOT_FOUND")
    out = attachments.search(ctx.db, conversation_id=ctx.conversation_id, query=a.query,
                             embed_query=_embed(), limit=a.k, attachment_id=found)
    recs = [Record(ref=f"ATT:{h.chunk_id}", source="attachments",
                   authority=authority.USER_MATERIAL, status="current",
                   location=h.location, text=h.content, item_id=str(h.chunk_id))
            for h in out.hits]
    return ToolResult(tool="search_attachment", records=tuple(recs),
                      quality=Quality(gate_open=out.gate_open,
                                      lexical_hit=_strict_lexical(
                                          ctx.db, a.query, [r.text for r in recs]),
                                      top_score=out.hits[0].retrieval_score
                                      if out.hits else None,
                                      count_returned=len(recs)),
                      count_returned=len(recs))


def ask_user(ctx: ToolContext, a: AskUserArgs) -> ToolResult:
    """Nothing is stored: the question is the turn's reply, which the Phase 3 loop
    persists through the ordinary answer path, exactly once."""
    return ToolResult(tool="ask_user", question=a.question, options=tuple(a.options))


TOOLS: dict[str, tuple[type[_Args], Callable[[ToolContext, Any], ToolResult]]] = {
    "search_knowledge": (SearchKnowledgeArgs, search_knowledge),
    "get_company_position": (CompanyPositionArgs, get_company_position),
    "search_statutes": (SearchStatutesArgs, search_statutes),
    "get_evidence": (GetEvidenceArgs, get_evidence),
    "list_attachments": (ListAttachmentsArgs, list_attachments),
    "search_attachment": (SearchAttachmentArgs, search_attachment),
    "ask_user": (AskUserArgs, ask_user),
}

#: Per-call wall time in ms, appended when a list is set — the latency measurement.
TIMINGS: list[tuple[str, float]] | None = None


def run(ctx: ToolContext, name: str, arguments: dict) -> ToolResult:
    """THE entry point the agent loop will use. Unknown tool, unknown field or bad value
    → `INVALID_ARGUMENT`; otherwise the tool runs inside a savepoint that is always
    rolled back, so it cannot leave a write behind."""
    entry = TOOLS.get(name)
    if entry is None or not isinstance(arguments, dict):
        return ToolResult(tool=str(name)[:40], error="INVALID_ARGUMENT")
    model, fn = entry
    try:
        args = model.model_validate(arguments)
    except ValidationError:
        return ToolResult(tool=name, error="INVALID_ARGUMENT")
    started = time.perf_counter()
    savepoint = ctx.db.begin_nested()
    try:
        return fn(ctx, args)
    finally:
        savepoint.rollback()
        if TIMINGS is not None:
            TIMINGS.append((name, (time.perf_counter() - started) * 1000))
