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

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.agent import attachments, ledger
from legalmind.assist.ingestion import chunking
from legalmind.assist.knowledge import authority, constitution, positions, store
from legalmind.assist.knowledge import statutes as statute_corpus
from legalmind.assist.query.planner import stems as _stems
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
    """Constitution, ratified standards, the statutes and a document. `sources` may only
    NARROW what the caller is already permitted. `document_version_id` defaults to the
    selected document; it may name another document only if the caller may read it
    (A-65). Repealed and superseded statute text only with `include_superseded`."""
    query: Query
    sources: Annotated[list[Literal["constitution", "positions", "statutes",
                                    "documents"]],
                       Field(min_length=1, max_length=4)] = [
        "documents", "constitution", "positions", "statutes"]  # the document first (P1)
    document_version_id: AnId | None = None
    include_superseded: bool = False
    k: K = 5


class FindDocumentsArgs(_Args):
    """Documents the caller may read whose name carries these words (A-65)."""
    name: Query
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
    #: Who the record applies to (P2): a position's agreement type ("MSA agreements
    #: only"), a Constitution item's breadcrumb, "the selected document".
    scope: str | None = None
    #: The cross-encoder's relevance to the query — it orders, never admits (`AM-106`).
    relevance: float | None = None


class Quality(BaseModel):
    model_config = ConfigDict(frozen=True)
    gate_open: bool
    lexical_hit: bool
    top_score: float | None
    count_returned: int
    #: The shipped rescue judge looked at a shut document gate (one model call).
    rescue_called: bool = False


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_id: str
    state: Literal["current", "stale", "unavailable"]
    ref: str | None = None
    authority: str | None = None
    text: str | None = None
    location: str | None = None


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
    documents: tuple[dict, ...] = ()
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
    #: None → `WHOLE_DOCUMENT_CHARS`; a slow provider's lean profile sets 0 (ranked).
    whole_document_chars: int | None = None

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
    """THE document-scope resolution. No id: the selected document (the conversation's
    own contract, latest version). An id: a version of the selected contract, or —
    A-65, owner 2026-10-04 — of ANY other contract the caller may read, by the
    product's one read rule (`can_read_contract`: owner, department, Legal scope).
    None for every failure — malformed, missing, unreadable — the same envelope."""
    if document_version_id is None:
        if ctx.contract_id is None:
            return None
        return ctx.db.execute(text(
            "SELECT id FROM document_versions WHERE contract_id = :k "
            "ORDER BY version_number DESC LIMIT 1"), {"k": ctx.contract_id}).scalar()
    try:
        wanted = UUID(document_version_id)
    except ValueError:
        wanted = None              # the same query runs, and finds nothing
    row = ctx.db.execute(text(
        "SELECT id, contract_id FROM document_versions WHERE id = CAST(:v AS uuid)"),
        {"v": str(wanted) if wanted else None}).first()
    if row is None:
        return None
    return row[0] if row[1] == ctx.contract_id or _readable(ctx, row[1]) else None


def _readable(ctx: ToolContext, contract_id: UUID) -> bool:
    from legalmind.db import models as M
    from legalmind.security.authorization import can_read_contract
    contract = ctx.db.get(M.Contract, contract_id)
    return (contract is not None and P.ASSIST_ASK in ctx.permissions
            and can_read_contract(ctx.db, ctx.user_id, contract))


#: Words that name a KIND of document, not a particular one — never enough to say the
#: reader named a document (A-65).
_GENERIC = frozenset([
    "agreement", "agreements", "contract", "contracts", "document", "documents",
    "service", "services", "level", "levels", "master", "terms", "term", "draft",
    "final", "original", "copy", "signed", "version", "limited", "private", "schedule",
    "annexure", "customer", "client", "policy", "policies", "order", "form",
    "amendment", "addendum", "partner", "vendor", "distribution", "standard",
    "company"])


def name_tokens(text_: str) -> set[str]:
    """The distinctive words of a document's name (A-65)."""
    return {w for w in re.findall(r"[a-z0-9]{4,}", text_.lower()) if w not in _GENERIC}


WHOLE_DOCUMENT_CHARS = 240_000          # ~60k tokens (owner mission, backlog 1)
#: D4 (owner 2026-10-07): the clauses a question names, forced into a RANKED document's
#: evidence whatever their rank — a clause on page 22 of a 28-page agreement, asked for
#: by name, was cut by the k. At most this many records, the numbered ones first.
NAMED_CLAUSES_MAX = 4


_GENERIC_STEMS = _stems(" ".join(_GENERIC))


_NUM = r"\d{1,3}(?:\.\d{1,3}){0,3}[a-z]{0,2}"
#: A keyword and the numbers after it: "clause 17.2", "s. 74", and a list, which is how
#: the model writes its statute queries ("section 73 74 liability cap": s. 74 was read as
#: no section at all, 2026-10-07), "sections 73 and 74", "ss. 73-74".
_NUMBERED = re.compile(
    rf"\b(?:sections?|clauses?|articles?|para(?:graph)?s?|secs?\.|ss?\.|cl\.)\s*"
    rf"({_NUM}(?:\s*(?:,|and|&|or|/|-|to)?\s*{_NUM}\b)*)", re.I)


def clause_numbers(query: str) -> list[str]:
    """The clause or section numbers a question names, in its order, each once."""
    return list(dict.fromkeys(n.lower() for m in _NUMBERED.finditer(query)
                              for n in re.findall(_NUM, m.group(1), re.I)))


def _numbered(ref: str | None, n: str) -> bool:
    ref = (ref or "").lower()
    return ref == n or ref.startswith(n + ".")


def _pick(items: list, numbers: list[str], ref: Callable[[Any], str | None],
          extra: Callable[[Any], bool] | None = None) -> list:
    """Up to NAMED_CLAUSES_MAX of `items` (document order): each named number's own
    clause first, in the question's order, then its sub-clauses, then `extra`'s. Taken
    in document order alone, "clause 17.2 of the MSA and clause 13 of the ToS" filled
    every place with the MSA's 13, 13.1, 13.2 … and never reached 17.2 (D6 live check)."""
    def number(n: str) -> Callable[[Any], bool]:
        return lambda x: _numbered(ref(x), n)
    out: list = []
    passes = [(number(n), once) for once in (True, False) for n in numbers]
    passes += [(extra, False)] if extra else []
    for wanted, once in passes:
        for x in items:
            if len(out) >= NAMED_CLAUSES_MAX:
                return out
            if x not in out and wanted(x):
                out.append(x)
                if once:
                    break
    return out


def named_clauses(ctx: ToolContext, version: UUID, query: str,
                  numbers: list[str] | None = None) -> list[tuple[Any, str]]:
    """The version's clause chunks the question names, as (hit, heading): by number
    ("clause 13.1" is 13.1 and its sub-clauses), then by heading (every heading word in
    the question, generic words like "agreement" aside: "indemnity" names
    "11 · INDEMNIFICATION"; "enforceable" alone does not name "3 · Enforcement and
    Penalties", which half the words did). A clause the text continues is one record,
    and a bare heading row ("11. INDEMNIFICATION", 19 characters) is none: it took a
    place and gave the model no clause (2026-10-08). `numbers` alone, no heading words:
    the clauses a shown clause refers to."""
    words = _stems(query) - _GENERIC_STEMS if numbers is None else set()
    numbers = clause_numbers(query) if numbers is None else numbers
    if not numbers and not words:
        return []
    ids = list(ctx.db.execute(text(
        f'SELECT id FROM "{config.assist_schema()}".chunks '
        "WHERE document_version_id = :v ORDER BY ordinal"), {"v": version}).scalars())
    found = store.chunks_by_id(ctx.db, document_version_id=version, chunk_ids=ids)
    headings = store.section_headings(ctx.db, ids)
    hits = [h for i, h in enumerate(found) if not (i and chunking.runs_on(
        found[i - 1].content, h.content,
        page_break=found[i - 1].page_number != h.page_number))]

    def by_heading(h) -> bool:
        stems = _stems(re.sub(r"\d", " ", headings.get(h.chunk_id, ""))) - _GENERIC_STEMS
        return bool(stems) and stems <= words
    out: list[tuple[Any, str]] = []
    for h in _pick(hits, numbers, lambda h: h.section_ref, by_heading):
        heading = headings.get(h.chunk_id, "")
        if store.is_fragment(h.content):           # a bare heading: its first clause
            at = found.index(h)
            h = next((x for x in found[at + 1:] if not store.is_fragment(x.content)),
                     None)
        if h is not None and all(h.chunk_id != o.chunk_id for o, _ in out):
            out.append((h, heading))
    return out


def _document_chars(ctx: ToolContext, version: UUID) -> int:
    return ctx.db.execute(text(
        "SELECT coalesce(sum(length(content)), 0) "
        f'FROM "{config.assist_schema()}".chunks WHERE document_version_id = :v'),
        {"v": version}).scalar() or 0


def _constitution_context(ctx: ToolContext, recs: list[Record]) -> list[Record]:
    """A Constitution hit read as the reader of the Constitution reads it (A-83): its
    numbered section (`constitution.expand` — the shipped path's parent context: the
    position with its basis, status and labelled historical exceptions), one record per
    section. Weakness was judged on the hit itself, before this. Following the
    sections' cross-references was measured and dropped: no needed item, only noise."""
    from legalmind.assist.retrieval.retrieval import CONTEXT_CHARS
    out, sections = [], set()
    for r in recs:
        if r.ref in sections:
            continue
        sections.add(r.ref)
        whole = constitution.expand(ctx.db, UUID(r.item_id), max_chars=CONTEXT_CHARS) \
            if r.item_id else ""
        out.append(r.model_copy(update={"text": whole or r.text}))
    return out


def _whole_document(ctx: ToolContext, version: UUID, label: str,
                    scope: str) -> list[Record]:
    """Every chunk of the version in document order, as records — a block that carries on
    the previous block's sentence joined to the record it continues (one clause, one
    record: a claim on 17.1 was judged against the half without "data"), by the same
    rule `store.clause_text` applies when the ledger re-reads it (A-83), located by its
    clause number, else page or heading."""
    ids = list(ctx.db.execute(text(
        f'SELECT id FROM "{config.assist_schema()}".chunks '
        "WHERE document_version_id = :v ORDER BY ordinal"), {"v": version}).scalars())
    hits = {h.chunk_id: h for h in store.chunks_by_id(ctx.db, document_version_id=version,
                                                      chunk_ids=ids)}
    headings = store.section_headings(ctx.db, ids)
    annex = store.annexes(ctx.db, ids)
    out: list[Record] = []
    prev = None
    for cid in ids:
        h = hits.get(cid)
        if h is None:
            continue
        joins = (out and prev is not None and prev.evidence_id != h.evidence_id
                 and chunking.runs_on(prev.content, h.content,
                                      page_break=prev.page_number != h.page_number))
        prev = h
        if joins:
            out[-1] = out[-1].model_copy(
                update={"text": f"{out[-1].text.rstrip()} {h.content}"})
            continue
        location = annexed(document_location(h, headings.get(cid)), annex.get(cid))
        out.append(Record(ref=f"DOC:{cid}", source="documents", item_id=str(cid),
                          text=h.content, authority=label,
                          status="executed" if label == "EXECUTED_DOCUMENT" else "draft",
                          location=location, scope=scope))
    return out


def annexed(location: str | None, annex: str | None) -> str | None:
    """A location inside an annexure names it — "Annexure-2, 3", never a bare "3" the
    main body also numbers (`store.annexes`)."""
    if not annex or not location or location.lower().startswith(annex.lower()):
        return location
    return f"{annex}, {location}"


def document_location(hit, heading: str | None) -> str | None:
    """Where a document record is (P4): its clause number, else its page, else the
    clause heading it is scored with — except a table, whose place in the extracted
    order is not its place in the document (DOCX tables follow the body text), so it
    never borrows the last heading (C4.1: the tier table read "15 · Miscellaneous")."""
    table = hit is not None and "TABLE" in (hit.source_type or "").upper()
    return ((hit.section_ref if hit else None)
            or (f"p.{hit.page_number}" if hit and hit.page_number else None)
            or ("a table in the document" if table else heading) or None)


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
    from legalmind.assist.ingestion import embedding_runtime
    return embedding_runtime.embed_query


# ------------------------------------------------------------------------------ tools
def _positions(ctx: ToolContext, query: str, k: int):
    hits = positions.search_positions(ctx.db, query=query, permissions=ctx.permissions,
                                      limit=k)
    recs = [Record(ref=f"POS:{h.standard_code}", source="positions",
                   authority="COMPANY_STANDARD", status="current",
                   location=h.source_clause, text=h.content,
                   item_id=str(h.position_chunk_id)) for h in hits]
    return recs, _quality(ctx.db, query, recs, [h.score for h in hits])


_POOL = {"constitution": "CONSTITUTION", "positions": "POSITIONS",
         "statutes": "STATUTES", "documents": "DOCUMENT"}


def _scopes(ctx: ToolContext, cands: list) -> dict[str, tuple[str | None, str | None]]:
    """(scope, location) per candidate ref, from the records themselves: a position's
    agreement type and source clause, a Constitution item's breadcrumb and section, a
    document chunk's clause number or page (P2, P4). Never inferred from text."""
    schema = config.assist_schema()
    out: dict[str, tuple[str | None, str | None]] = {}
    pos = [c.item_id for c in cands if c.domain == "POSITIONS"]
    for r in ctx.db.execute(text(
            f'SELECT id, document_type, source_clause FROM "{schema}".position_chunks '
            "WHERE id = ANY(:ids)"), {"ids": pos}).all() if pos else []:
        out[str(r[0])] = (f"{r[1]} agreements only" if r[1] else None, r[2])
    const = [c.item_id for c in cands if c.domain == "CONSTITUTION"]
    for r in ctx.db.execute(text(
            f'SELECT id, breadcrumb, section_path FROM "{schema}".knowledge_items '
            "WHERE id = ANY(:ids)"), {"ids": const}).all() if const else []:
        out[str(r[0])] = (r[1], f"§{r[2]}" if r[2] else None)
    stat = [c.item_id for c in cands if c.domain == "STATUTES"]
    for r in ctx.db.execute(text(
            f'SELECT c.id, s.official_title, c.section_number, c.sub_section FROM '
            f'"{schema}".statute_chunks c JOIN "{schema}".statutes s ON s.id = '
            "c.statute_id WHERE c.id = ANY(:ids)"), {"ids": stat}).all() if stat else []:
        unit = r[2] if "schedule" in r[2].lower() else f"s. {r[2]}"  # as `.citation`
        out[str(r[0])] = (None, f"{r[1]}, {unit}" + (f" {r[3]}" if r[3] else ""))
    return out


def search_knowledge(ctx: ToolContext, a: SearchKnowledgeArgs, *,
                     rescue: bool = False) -> ToolResult:
    """The current pipeline's OWN retrieval (Phase 4, A-39): the query plan, the broad
    authorized candidate pool and the cross-encoder rerank (`retrieval.candidates`,
    `retrieval.rerank`) — so the agent sees what the shipped answer sees. Phase 3 used
    plain hybrid search and missed the selected document's clauses the shipped path
    found (G8, G12). The rescue judge runs only when the agent loop asks for it
    (`rescue=True`: the seed search of the message, A-57) — never at the model's call."""
    from legalmind.assist.query import query_plan, routing
    from legalmind.assist.retrieval import evidence, retrieval
    from legalmind.assist.retrieval import rescue as rescue_judge
    version = None
    if "documents" in a.sources:
        version = _version_in_scope(ctx, a.document_version_id)
        if a.document_version_id is not None and version is None:
            return ToolResult(tool="search_knowledge", error="NOT_FOUND")
    wanted = list(dict.fromkeys(a.sources))
    domains = []
    # Demo mission backlog 1 (A-77): a document small enough is READ WHOLE, every clause
    # block in order with its evidence id and clause number — ranking a 14k-token
    # contract down to five chunks is how the second clause (17.7, 8.3, the cap) never
    # reached the model. Larger documents keep ranked retrieval and its gate.
    whole = ("documents" in wanted and version is not None
             and P.ASSIST_ASK in ctx.permissions and _document_chars(ctx, version)
             <= (WHOLE_DOCUMENT_CHARS if ctx.whole_document_chars is None
                 else ctx.whole_document_chars))
    if ("documents" in wanted and version is not None and not whole
            and P.ASSIST_ASK in ctx.permissions):
        domains.append(routing.Domain.DOCUMENT)
    if ({"constitution", "positions"} & set(wanted)
            and positions.can_read(ctx.permissions)):
        domains.append(routing.Domain.POSITIONS)
    # The law is searched with everything else (2026-10-06): left to a separate tool the
    # model chose, it was called 0 times in a 19-turn data-protection conversation and
    # every statement about the DPDP and IT Acts came from the Constitution's reading.
    if "statutes" in wanted and P.ASSIST_ASK in ctx.permissions:
        domains.append(routing.Domain.STATUTES)
    by_source: dict[str, Quality] = {}
    records: list[Record] = []
    empty = Quality(gate_open=False, lexical_hit=False, top_score=None, count_returned=0)
    if not domains and not whole:
        return ToolResult(tool="search_knowledge", records=(),
                          by_source=dict.fromkeys(wanted, empty), count_returned=0)
    route = routing.RoutePlan(comparison=False, domains=tuple(domains) or (
        routing.Domain.POSITIONS,), statute_shaped=False,
        include_superseded=a.include_superseded)
    plan = query_plan.plan(a.query, has_document=version is not None, prior=(),
                           instruction=a.query)
    # The judge's calls that actually returned, collected as the shipped request
    # collects them (`rescue.CALLS`); a disabled or unavailable judge made none.
    judged = rescue_judge.CALLS.set([])
    try:
        pool = retrieval.rerank(retrieval.candidates(
            ctx.db, plan, route, permissions=ctx.permissions,
            document_version_id=version, rescue=rescue), plan)
        rescue_calls = len(rescue_judge.CALLS.get() or [])
    finally:
        rescue_judge.CALLS.reset(judged)
    label = "DRAFT_DOCUMENT"
    doc_scope = "the selected document"
    if version is not None:
        label = authority.of_document(store.version_role(ctx.db, version)) or label
        if version != _version_in_scope(ctx, None):
            # A-65: another document the reader may read — labelled as itself, so it
            # never passes for the selected one.
            name = ctx.db.execute(text(
                "SELECT c.name FROM contracts c JOIN document_versions v "
                "ON v.contract_id = c.id WHERE v.id = :v"), {"v": version}).scalar()
            doc_scope = f'another document: "{name}"'
    picked = {s: pool.by_domain.get(_POOL[s], [])[:a.k] if domains else []
              for s in wanted if not (whole and s == "documents")}
    named = (named_clauses(ctx, version, a.query)
             if "documents" in picked and version is not None else [])
    asked_named = bool(named)            # the question's own clauses open the gate
    if "documents" in picked and version is not None:
        # Cross-references (roadmap §9): a shown clause "Subject to Clause 5.1" brings
        # 5.1, within what the named clauses leave of the cap. Ranked, Bonsai's T5
        # answer said "subject to clause 5.1" and could not say what 5.1 provides
        # (2026-10-08); read whole, every clause is already there.
        cited = [n for t in [*(c.text for c in picked["documents"]),
                             *(h.content for h, _ in named)]
                 for n in clause_numbers(t)]
        room = NAMED_CLAUSES_MAX - len(named)
        if cited and room > 0:
            named += named_clauses(ctx, version, "", numbers=cited)[:room]
    if named:
        have = {c.item_id for c in picked["documents"]}
        for h, heading in named:
            if h.chunk_id not in have:
                have.add(h.chunk_id)
                picked["documents"].append(retrieval.Candidate(
                    routing.Domain.DOCUMENT.value, f"DOC:{h.chunk_id}", h.chunk_id,
                    h.content, 1.0, note=heading))
    # The sections of a named Act the question names, as the shipped bundle takes them
    # (`evidence.py`, `exact_reference`): in, whatever their rank, and past the floor —
    # "Contract Act section 73 74" kept s. 73 first after the rerank, then dropped it at
    # the floor (relevance -8.3), and s. 74 never reached the k (2026-10-07).
    numbers = clause_numbers(a.query)
    exact = [c for c in pool.by_domain.get(_POOL["statutes"], [])
             if numbers and retrieval.exact_reference(c, plan, numbers)
             ] if "statutes" in picked and domains else []
    if exact:
        have = {c.item_id for c in picked["statutes"]}
        picked["statutes"] += [c for c in exact if c.item_id not in have][
            :NAMED_CLAUSES_MAX]
    to_judge = [c for s in ("statutes", "positions") for c in picked.get(s, [])]
    admits = _bundle_admits(ctx, plan, pool, to_judge, a.include_superseded)
    off_topic = {str(c.item_id) for c in picked.get("positions", [])
                 if evidence.off_topic(c, a.query)}
    scoped = _scopes(ctx, [c for cs in picked.values() for c in cs])
    annex = store.annexes(ctx.db, [c.item_id for c in picked.get("documents", [])])
    doc_hits = ({h.chunk_id: h for h in store.chunks_by_id(
        ctx.db, document_version_id=version,
        chunk_ids=[c.item_id for c in picked.get("documents", [])])}
        if version is not None else {})
    if whole and version is not None:
        recs = _whole_document(ctx, version, label, doc_scope)
        records += recs
        by_source["documents"] = Quality(gate_open=True, lexical_hit=True, top_score=None,
                                          count_returned=len(recs))
    # The statutes last, so the sections a shown Constitution record cites can join them
    # (`_cited_sections`); every other source keeps its order.
    for source in sorted((s for s in wanted if s in picked),
                         key=lambda s: s == "statutes"):
        cands = picked[source]
        law_cited: list = []
        if source == "statutes":
            law_cited = _cited_sections(ctx, [r.text for r in records
                                              if r.source == "constitution"],
                                        {c.ref for c in cands}, a.query)
            scoped |= _scopes(ctx, law_cited)    # their location, as every record has
            cands = cands + law_cited
        recs = []
        for c in cands:
            not_in_force = None
            scope, location = scoped.get(str(c.item_id), (None, None))
            if source == "documents":
                h = doc_hits.get(c.item_id)
                scope = doc_scope
                # The clause number, else the page, else the clause heading the
                # pipeline scores with the chunk (`store.section_headings`) — a DOCX
                # without pagination still gets a location a reader can find (P4).
                location = document_location(h, c.note)
                # A-71/A-83: the chunk's whole clause (the block it continues, the
                # blocks that carry it on) — the same text the ledger re-reads.
                clause = store.clause_text(ctx.db, c.item_id)
                body = clause[0] if clause else c.text
                location = annexed((clause[1] if clause and clause[1] else None)
                                   or location, annex.get(c.item_id))
            elif source == "statutes":
                read = statute_corpus.read_time_text(ctx.db, c.item_id)
                body, not_in_force = read if read else (c.text, None)
            else:
                body = c.text
            recs.append(Record(
                ref=c.ref, source=source, item_id=str(c.item_id), text=body,
                authority=label if source == "documents" else (
                    c.authority or "COMPANY_STANDARD"),
                status=("executed" if label == "EXECUTED_DOCUMENT" else "draft")
                if source == "documents" else "not yet in force"
                if source == "statutes" and not_in_force
                else (c.status or "CURRENT").lower(),
                location=location, scope=scope, relevance=c.relevance))
        if source == "constitution":
            recs = _with_terms(ctx.db, a.query, recs)          # the weak test (A-37)
            recs = _constitution_context(ctx, recs)             # A-83, after it
        if source == "statutes":
            named_ids = {str(c.item_id) for c in [*exact, *law_cited]}
            recs = [r for r in _with_terms(ctx.db, a.query, recs)
                    if r.item_id in named_ids
                    or (_admitted(r) if admits is None else r.item_id in admits)]
        if source == "positions":
            recs = [r for r in recs if r.item_id not in off_topic
                    and (admits is None or r.item_id in admits)]
        # A clause the reader named and the document has is in it (D4), as a
        # Constitution section named by number is (`retrieval.candidates` step 3).
        gate = (bool(pool.document_gate or asked_named) if source == "documents"
                else bool(recs))
        by_source[source] = Quality(
            gate_open=gate, lexical_hit=_strict_lexical(ctx.db, a.query,
                                                        [r.text for r in recs]),
            top_score=recs[0].relevance if recs else None, count_returned=len(recs),
            rescue_called=source == "documents" and bool(rescue_calls))
        records += recs
    return ToolResult(tool="search_knowledge", records=tuple(records),
                      by_source=by_source, count_returned=len(records))


STATUTE_PRECUT = -8.0
_SEC = r"\d{1,3}[A-Za-z]{0,2}"
_SECS = rf"(?i:sections?|ss?\.)\s*({_SEC}(?:\s*(?:,|and|&|or|-|\u2013|to)\s*{_SEC})*)"
_ACT = r"([A-Z][\w ,()'-]{2,80}?(?:Act|Rules|Code|Adhiniyam)\b(?:,?\s*\d{4})?)"
#: A company source citing the law by section and Act, either way round: "Sections 73
#: and 74 of the Indian Contract Act" and §9's "Indian Contract Act 1872, Sections
#: 73–74". The Constitution's own "Section 27, Item 1" names no Act and is not law.
_CITED_LAW = (re.compile(rf"\b{_SECS}\s+of\s+(?:the\s+)?{_ACT}"),
              re.compile(rf"{_ACT},?\s+{_SECS}"))


def _line_of(text_: str, m: re.Match) -> str:
    start = text_.rfind("\n", 0, m.start()) + 1
    end = text_.find("\n", m.end())
    return text_[start:end if end >= 0 else len(text_)]


def _cited_sections(ctx: ToolContext, texts: list[str], have: set[str],
                    question: str) -> list:
    """The sections of an Act that a shown Constitution record cites, as statute
    candidates (roadmap §9, cross-references; addendum multi-hop: company reading →
    the law). §9 states "Sections 73 and 74 of the Indian Contract Act" as the basis of
    the liability position, and the answer cited the company's reading of them, never
    the sections themselves (live T4, 2026-10-08). Named, so past the floor; at most
    NAMED_CLAUSES_MAX; a repealed Act is not searched. Only a citation whose own line
    shares a content word with the question: a shown record cites many Acts, and the
    cross-encoder cannot tell them apart (ss. 73–74 -8.85/-9.42, IT Act s. 70B -10.84
    for "is the liability cap … enforceable?"), the citing line can (2026-10-08)."""
    from legalmind.assist.retrieval import retrieval
    asked_words = _stems(question) - _GENERIC_STEMS - {"legal"}
    out: list = []
    for text_ in texts:
        for secs, act in ((m.group(1), m.group(2)) if i == 0 else (m.group(2), m.group(1))
                          for i, pattern in enumerate(_CITED_LAW)
                          for m in pattern.finditer(text_)
                          if _stems(_line_of(text_, m)) & asked_words):
            numbers = {n.upper() for n in re.findall(_SEC, secs)}
            asked = f" {statute_corpus.expand_aliases(act)} "
            query = act + " " + " ".join(f"section {n}" for n in sorted(numbers))
            for h in statute_corpus.search_statutes(ctx.db, query=query, limit=10,
                                                     permissions=ctx.permissions,
                                                     candidates=True):
                c = retrieval.Candidate(
                    _POOL["statutes"], f"STAT:{h.official_title.removeprefix('The ')}:"
                    f"{h.section_number}", h.statute_chunk_id, h.content, 1.0,
                    *authority.of_statute(h.official_title), note=h.marginal_note or "")
                if (h.section_number.upper() in numbers and c.ref not in have
                        and retrieval._is_named_act(c, asked)):
                    have.add(c.ref)
                    out.append(c)
                    if len(out) >= NAMED_CLAUSES_MAX:
                        return out
    return out


def _bundle_admits(ctx: ToolContext, plan, pool, cands: list,
                   superseded: bool) -> set[str] | None:
    """The shipped evidence bundle's judgment of these statute and position candidates
    (`evidence.build`, `AM-88`), so the live path admits what the measured one does. Its
    floors are calibrated on a source's parent context, scored against the question and
    each sub-question; applied to the bare chunk's score, they admitted no statute at
    all for "What is the maximum penalty under the DPDP Act?" (s. 33 ranked first,
    -4.68 against a -2.0 floor), and no floor at all let the 12-month liability cap
    answer early-termination questions (agent seed: wrong-source 9 of 82 golden cases,
    2026-10-08). None when the reranker cannot score: the callers keep their term
    rules. Superseded text stays when the caller asked for it."""
    from legalmind.assist.retrieval import evidence, retrieval
    if not cands:
        return set()
    # Scoring a statute's parent context is the cost (a 4,000-character pair per query
    # and sub-question); one already far below the floor is not scored. Over the 82
    # golden cases' 410 statute candidates, none scoring under -8.0 on its chunk was
    # admitted on its context (the lowest admitted: -7.37) — 113 not scored.
    scored = [c for c in cands if c.relevance is None or c.relevance >= STATUTE_PRECUT
              or c.domain != _POOL["statutes"] or retrieval.exact_reference(c, plan)
              or retrieval.titled_reference(c, plan)]
    if not scored:
        return set()
    sources = evidence.build(ctx.db, plan, pool, scored).sources
    if all(s.relevance is None for s in sources):
        return None
    return {str(s.candidate.item_id) for s in sources
            if s.supports or s.named or (superseded and s.reason == "NOT_CURRENT")}


def _admitted(rec: Record) -> bool:
    """A statute section reaches the model only past the shipped bundle's statute floor
    (`AM-88`), or — no reranker — carrying min(2, query terms) of the query's terms
    (A-37): the candidate pool is ungated recall, and its tail is unrelated Acts."""
    from legalmind.assist.retrieval.evidence import RELEVANCE_FLOOR
    if rec.relevance is not None:
        return rec.relevance >= RELEVANCE_FLOOR["STATUTES"]
    return (rec.matched_terms or 0) >= min(2, rec.query_terms or 1)


def get_company_position(ctx: ToolContext, a: CompanyPositionArgs) -> ToolResult:
    recs, q = _positions(ctx, a.topic, a.k)
    return ToolResult(tool="get_company_position", records=tuple(recs), quality=q,
                      count_returned=len(recs))


def search_statutes(ctx: ToolContext, a: SearchStatutesArgs) -> ToolResult:
    """The statutes alone, through the same candidate pool and cross-encoder rerank as
    `search_knowledge` — one retrieval path, one relevance rule for a statute."""
    r = search_knowledge(ctx, SearchKnowledgeArgs(
        query=a.query, sources=["statutes"], include_superseded=a.include_superseded,
        k=a.k))
    return ToolResult(tool="search_statutes", records=r.records,
                      quality=(r.by_source or {}).get("statutes"),
                      count_returned=r.count_returned)


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
                              text=f.text,
                              location=f.location if f.text is not None else None)
               for f in got)
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
    named = attachments.names(ctx.db, ctx.conversation_id)
    rows = [(h.chunk_id, h.content, h.location) for h in out.hits]
    numbers = clause_numbers(a.query)
    if numbers:                # D4 for material too: a clause the question names
        chunks = ctx.db.execute(text(
            f'SELECT id, content, location FROM "{config.assist_schema()}".'
            "attachment_chunks WHERE attachment_id = :a ORDER BY ordinal"),
            {"a": found}).all()
        have = {r[0] for r in rows}
        rows += [tuple(c) for c in _pick([c for c in chunks if c[0] not in have],
                                         numbers, lambda c: c[2])]
    recs = [Record(ref=f"ATT:{cid}", source="attachments",
                   authority=authority.USER_MATERIAL, status="current",
                   location=location, text=content, item_id=str(cid),
                   scope=named.get(found))
            for cid, content, location in rows]
    return ToolResult(tool="search_attachment", records=tuple(recs),
                      quality=Quality(gate_open=(out.gate_open
                                                 or len(rows) > len(out.hits)),
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


def find_documents(ctx: ToolContext, a: FindDocumentsArgs) -> ToolResult:
    """A-65: the documents the reader names, among those they may read — never one they
    may not (`can_read_contract` on every candidate), never its text: name, type,
    execution status, and the version id `search_knowledge` takes. The selected
    document is marked; the others are OTHER documents, never a substitute for it."""
    tokens = name_tokens(a.name)
    if not tokens or P.ASSIST_ASK not in ctx.permissions:
        return ToolResult(tool="find_documents")
    pats = [f"%{t}%" for t in sorted(tokens)]
    rows = ctx.db.execute(text(
        "SELECT DISTINCT ON (c.id) c.id, c.name, c.contract_type, v.id, "
        "v.metadata->>'version_role', v.original_filename "
        "FROM contracts c JOIN document_versions v ON v.contract_id = c.id "
        "WHERE lower(c.name) LIKE ANY(:p) OR lower(v.original_filename) LIKE ANY(:p) "
        "ORDER BY c.id, v.version_number DESC LIMIT 200"), {"p": pats}).all()
    found = []
    for cid, name, ctype, vid, role, filename in rows:
        if cid != ctx.contract_id and not _readable(ctx, cid):
            continue
        hits = len(tokens & (name_tokens(name) | name_tokens(filename or "")))
        if hits:
            found.append((hits, {"document_version_id": str(vid), "name": name,
                                 "document_type": ctype,
                                 "status": "executed" if role == "FINAL_SIGNED"
                                 else "draft or unsigned",
                                 "selected": cid == ctx.contract_id}))
    found.sort(key=lambda x: (-x[0], x[1]["name"]))
    return ToolResult(tool="find_documents",
                      documents=tuple(d for _, d in found[:a.k]),
                      count_returned=min(len(found), a.k))


TOOLS: dict[str, tuple[type[_Args], Callable[[ToolContext, Any], ToolResult]]] = {
    "search_knowledge": (SearchKnowledgeArgs, search_knowledge),
    "find_documents": (FindDocumentsArgs, find_documents),
    "get_company_position": (CompanyPositionArgs, get_company_position),
    "search_statutes": (SearchStatutesArgs, search_statutes),
    "get_evidence": (GetEvidenceArgs, get_evidence),
    "list_attachments": (ListAttachmentsArgs, list_attachments),
    "search_attachment": (SearchAttachmentArgs, search_attachment),
    "ask_user": (AskUserArgs, ask_user),
}

#: Per-call wall time in ms, appended when a list is set — the latency measurement.
TIMINGS: list[tuple[str, float]] | None = None


def run(ctx: ToolContext, name: str, arguments: dict, **options) -> ToolResult:
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
        return fn(ctx, args, **options)
    finally:
        savepoint.rollback()
        if TIMINGS is not None:
            TIMINGS.append((name, (time.perf_counter() - started) * 1000))
