"""Conversation-scoped user material — Ask plan 1.1–1.5, tables `AM-110`, owner decisions
A4-1…A4-3.

A paste or a chat file belongs to ONE conversation and never becomes a Contract (A4-1).
It is extracted with the existing parsers, chunked with the existing chunker and
searched with the same lexical + vector + calibrated-gate shape as a document — a thin
sibling of `store.search_hybrid` over its own tables, so the document path stays
byte-identical.

Two choices the design note left open, decided here (DECISIONS A-15):

  * NO RAW BYTES ARE KEPT. Storage keys are content-addressed and the backend has no
    delete, so purging an attachment's bytes could delete the same file someone else
    uploaded as a Dashboard document. Only the extracted chunks are kept, and those
    expire. `storage_key` stays NULL.
  * PROCESSING IS INLINE. Text, DOCX and text-layer PDF extract in well under a second at
    10 MB; a scan needing OCR fails as `OCR_REQUIRED` rather than queueing.
    ponytail: inline extraction, move to the QUEUE_ASSIST worker if OCR is wanted.

Access: every function takes a conversation id the router has already proved the
caller owns (`_visible_conversation`); the scope is a WHERE clause before ranking
(`AM-25` r6). Nothing here logs content, filenames or extracted text (`AM-30` t5).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.ingestion.chunking import (
    CHUNKING_ALGORITHM_VERSION,
    blank_fields,
    chunk_evidence,
)
from legalmind.observability.logs import log_event

PASTE, FILE = "PASTE", "FILE"
QUESTION_MAX_CHARS = 2000          # the typed question's own cap, unchanged (plan 1.1)
#: What the thread records for a turn that only brought material, and the reply to it —
#: fixed words, and never the material itself (the thread reaches the model, `AM-58`).
MATERIAL_TURN = "[Pasted text saved as an attachment]"
MATERIAL_SAVED = "Saved your text as an attachment. What would you like to know about it?"
#: The same turn with attachments off: the text stays in the thread, nothing is saved.
MATERIAL_READ = ("I have your text. What would you like to know about it — how it reads "
                 "against our standards, or what the law says?")
READY, FAILED, EXPIRED = "READY", "FAILED", "EXPIRED"


class AttachmentRejected(Exception):
    """Refused before anything is stored: a code, never the material."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Attachment:
    id: UUID
    kind: str
    filename: str | None
    mime_type: str
    byte_size: int
    status: str
    failure_code: str | None
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class AttachmentHit:
    chunk_id: UUID
    attachment_id: UUID
    content: str
    location: str | None
    retrieval_score: float


@dataclass(frozen=True)
class AttachmentSearch:
    hits: list[AttachmentHit]
    gate_open: bool


@dataclass
class _Row:
    """A parsed segment in the shape `chunk_evidence` reads."""
    id: int
    content: str
    page_number: int | None
    start_offset: int | None
    end_offset: int | None
    location: str | None


_COLUMNS = ("id, kind, filename, mime_type, byte_size, status, failure_code, "
            "created_at, expires_at")


def _schema() -> str:
    return config.assist_schema()


def list_for(db: DBSession, conversation_id: UUID) -> list[Attachment]:
    rows = db.execute(text(
        f'SELECT {_COLUMNS} FROM "{_schema()}".conversation_attachments '
        "WHERE conversation_id = :c ORDER BY created_at"), {"c": conversation_id}).all()
    return [Attachment(*r) for r in rows]


def texts_newest_first(db: DBSession, conversation_id: UUID) -> list[str]:
    """Each READY, unexpired attachment's text, its chunks in order, newest first — where
    a pasted list of points lives once the paste has become material (D1). Newest is
    not "the one just pasted": the same text pasted again reuses its saved row."""
    rows = db.execute(text(
        f'SELECT a.id, c.content FROM "{_schema()}".conversation_attachments a '
        f'JOIN "{_schema()}".attachment_chunks c ON c.attachment_id = a.id '
        "WHERE a.conversation_id = :c AND a.status = 'READY' AND a.expires_at > now() "
        "ORDER BY a.created_at DESC, c.ordinal"), {"c": conversation_id}).all()
    texts: dict = {}
    for att, content in rows:
        texts.setdefault(att, []).append(content)
    return ["\n".join(chunks) for chunks in texts.values()]


def split_paste(message: str) -> tuple[str, str]:
    """(question, material) from a message over the question cap (plan 1.1). The
    question is a paragraph that asks — the last, else the first — when it ends in "?"
    and fits the cap; the rest is material. No such paragraph: all of it is material
    and the question is "", answered with `MATERIAL_SAVED`. Deterministic; nothing is
    reworded."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", message.strip()) if p.strip()]
    for i in ((len(paras) - 1, 0) if len(paras) > 1 else ()):
        if paras[i].endswith("?") and len(paras[i]) <= QUESTION_MAX_CHARS:
            return paras[i], "\n\n".join(paras[:i] + paras[i + 1:])
    return "", message.strip()


#: Pasted material is the user's text, not a question: at least this long once the
#: question paragraph is set aside (a short clause runs ~60 words / 400 characters).
MATERIAL_MIN_CHARS, MATERIAL_MIN_WORDS = 400, 60
_REQUEST = re.compile(r"^\W*(?:please|pls|kindly|can|could|would|will|check|review|"
                      r"explain|summari[sz]e|compare|tell|what|why|how|is|are|does|do|"
                      r"draft|analy[sz]e|list|give|show|help)\b", re.I)


#: A last sentence that asks the assistant for something ("Let me know our position on
#: this") — a reader describing a situation, not pasting one (review, 2026-10-07).
_ASKS = re.compile(r"\b(?:let|tell|help|advise|show|give)\s+(?:me|us)\b|"
                   r"\b(?:can|could|should|do|must|would)\s+(?:we|i)\b|"
                   r"\b(?:can|could|would|will)\s+you\b", re.I)


def carries_material(message: str) -> bool:
    """A message UNDER the question cap that is mostly pasted material (`AM-118` r3):
    a clause or an e-mail with no question — which a model then analysed unasked — or
    with a question paragraph beside it. Material is split off by `split_paste` and
    becomes the conversation's own citable record, exactly as a paste over the cap
    does. A question that is all question ("Please check whether…", one long
    paragraph ending "?") stays a question."""
    question, material = split_paste(message)
    last = re.split(r"(?<=[.!;])\s+", message.strip())[-1]
    if not question and ("?" in message or _REQUEST.match(message) or _ASKS.search(last)):
        return False
    return (len(material) >= MATERIAL_MIN_CHARS
            and len(material.split()) >= MATERIAL_MIN_WORDS)


def scope(db: DBSession, conversation_id: UUID) -> UUID | None:
    """The conversation id when Ask may search its material — the flag on and at
    least one READY, unexpired attachment — else None."""
    if not config.ask_attachments_enabled():
        return None
    found = db.execute(text(
        f'SELECT 1 FROM "{_schema()}".conversation_attachments '
        "WHERE conversation_id = :c AND status = 'READY' AND expires_at > now() LIMIT 1"),
        {"c": conversation_id}).first()
    return conversation_id if found else None


def check_size(data: bytes, kind: str) -> None:
    """A4-3's limits, before anything is validated, parsed or stored."""
    limits = config.ask_attachment_limits()
    if kind == PASTE and len(data.decode("utf-8", errors="replace")) \
            > limits["max_paste_chars"]:
        raise AttachmentRejected("PASTE_TOO_LONG")
    if kind == FILE and len(data) > limits["max_bytes"]:
        raise AttachmentRejected("FILE_TOO_LARGE")


def add(db: DBSession, *, conversation_id: UUID, data: bytes, kind: str, mime: str,
        extracted: list | str, filename: str | None = None,
        message_id: UUID | None = None) -> Attachment:
    """Store, chunk and embed one piece of material. The same bytes twice in one
    conversation are one attachment. `extracted` is the parser's segments or its
    failure code: validation and parsing run in the API layer, which owns ingestion
    (the assist lane may not import it — `test_import_boundaries`). Raises
    `AttachmentRejected` for what is refused outright; a failure code is stored as a
    FAILED row."""
    check_size(data, kind)
    purge_expired(db)
    limits = config.ask_attachment_limits()
    digest = hashlib.sha256(data).hexdigest()
    schema = _schema()
    existing = db.execute(text(
        f'SELECT {_COLUMNS} FROM "{schema}".conversation_attachments '
        "WHERE conversation_id = :c AND content_sha256 = :h"),
        {"c": conversation_id, "h": digest}).first()
    if existing is not None:
        return Attachment(*existing)
    if len(list_for(db, conversation_id)) >= limits["max_files"]:
        raise AttachmentRejected("TOO_MANY_ATTACHMENTS")

    now = datetime.now(UTC)
    attachment_id = uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".conversation_attachments
            (id, conversation_id, message_id, kind, filename, mime_type, byte_size,
             content_sha256, status, created_at, expires_at)
        VALUES (:id, :c, :m, :k, :f, :mime, :size, :h, 'PROCESSING', :now, :exp)"""),
        {"id": attachment_id, "c": conversation_id, "m": message_id, "k": kind,
         "f": filename if kind == FILE else None, "mime": mime, "size": len(data),
         "h": digest, "now": now, "exp": now + timedelta(days=limits["ttl_days"])})

    failure = extracted if isinstance(extracted, str) else _index(db, attachment_id,
                                                                    extracted)
    db.execute(text(f"""
        UPDATE "{schema}".conversation_attachments
           SET status = :s, failure_code = :code, ready_at = :t WHERE id = :id"""),
        {"s": FAILED if failure else READY, "code": failure,
         "t": None if failure else datetime.now(UTC), "id": attachment_id})
    log_event("assist.attachment.added", attachment_id=str(attachment_id), kind=kind,
              status=FAILED if failure else READY, failure_code=failure or "",
              byte_size=str(len(data)), sha256=digest)
    return next(a for a in list_for(db, conversation_id) if a.id == attachment_id)


def _index(db: DBSession, attachment_id: UUID, segments: list) -> str | None:
    """Chunks (and, best-effort, embeddings) for one attachment; a failure code, or
    None when it is searchable."""
    rows = [_Row(i, s.content, s.page_number, s.start_offset, s.end_offset,
                 s.section_number or (f"p.{s.page_number}" if s.page_number else None))
            for i, s in enumerate(segments)]
    # A pasted thread quotes itself: the same paragraph six times became six chunks,
    # the answer cited one sentence six times and crowded out the rest (live G1,
    # 2026-10-01). Identical text within one attachment is stored once.
    seen: set[str] = set()
    chunks = []
    for c in chunk_evidence(rows):
        key = " ".join(c.content.split())
        if key not in seen:
            seen.add(key)
            chunks.append(c)
    if not chunks:
        return "NO_TEXT"
    by_row: dict[object, _Row] = {r.id: r for r in rows}
    schema = _schema()
    ids = [uuid4() for _ in chunks]
    db.execute(text(f"""
        INSERT INTO "{schema}".attachment_chunks
            (id, attachment_id, ordinal, content, location, start_offset, end_offset,
             annotations, chunking_algorithm_version)
        VALUES (:id, :a, :o, :content, :loc, :s, :e, CAST(:ann AS jsonb), :v)"""),
        [{"id": i, "a": attachment_id, "o": c.ordinal, "content": c.content,
          "loc": by_row[c.evidence_id].location, "s": c.start_offset, "e": c.end_offset,
          "ann": _annotations(c.content), "v": CHUNKING_ALGORITHM_VERSION}
         for i, c in zip(ids, chunks, strict=True)])
    _embed(db, ids, [c.content for c in chunks])
    return None


def _annotations(content: str) -> str:
    blanks = blank_fields(content)
    return json.dumps({"blank_fields": blanks} if blanks else {})


def _embed(db: DBSession, chunk_ids: list[UUID], texts: list[str]) -> None:
    """Best-effort, as `indexing._embed_chunks`: no model means lexical search only."""
    from legalmind.assist.ingestion import embedding_runtime
    from legalmind.assist.knowledge import store
    from legalmind.assist.retrieval import calibration
    if not embedding_runtime.available():
        return
    vectors = embedding_runtime.embed_texts(texts)
    if vectors is None:
        return
    identity = embedding_runtime.identity() or calibration.EMBEDDING_MODEL_REPO
    name, _, revision = identity.partition("@")
    model_id = store.register_embedding_model(
        db, name=name, version=revision or calibration.EMBEDDING_MODEL_REVISION,
        dimensions=calibration.EMBEDDING_DIMENSIONS,
        checksum=embedding_runtime.checksum_fragment() or "unrecorded")
    vtype = store.vector_type(db)
    db.execute(text(f"""
        INSERT INTO "{_schema()}".attachment_chunk_embeddings
            (id, chunk_id, embedding_model_id, embedding)
        VALUES (:id, :c, :m, CAST(:v AS {vtype}))"""),
        [{"id": uuid4(), "c": c, "m": model_id,
          "v": "[" + ",".join(f"{x:.6f}" for x in v) + "]"}
         for c, v in zip(chunk_ids, vectors, strict=True)])


def search(db: DBSession, *, conversation_id: UUID, query: str, embed_query,
           limit: int | None = None,
           attachment_id: UUID | None = None) -> AttachmentSearch:
    """The conversation's READY, unexpired material, ranked as a document is: the
    calibrated AND match and the question's own vector list decide the gate
    (`calibration.gate_is_open`); lexical OR and vector lists fused by RRF. Scope is a
    WHERE clause on both branches, before ranking."""
    from legalmind.assist.knowledge import store
    from legalmind.assist.retrieval.calibration import (
        RETRIEVAL_TOP_K,
        RRF_K,
        gate_is_open,
    )
    limit = limit or RETRIEVAL_TOP_K
    if not query.strip():
        return AttachmentSearch([], False)
    schema = _schema()
    scope = f"""JOIN "{schema}".conversation_attachments a ON a.id = c.attachment_id
                WHERE a.conversation_id = :conv AND a.status = 'READY'
                  AND a.expires_at > now()
                  AND (CAST(:att AS uuid) IS NULL OR a.id = CAST(:att AS uuid))"""
    cols = "c.id, c.attachment_id, c.content, c.location"

    def lexical(tsquery: str) -> list:
        return list(db.execute(text(f"""
            SELECT {cols}, ts_rank(c.content_tsv, {tsquery}) AS score
              FROM "{schema}".attachment_chunks c {scope}
               AND c.content_tsv @@ {tsquery}
             ORDER BY score DESC, c.ordinal LIMIT :lim"""),
            {"conv": conversation_id, "q": query, "lim": limit * 2,
             "att": attachment_id}).all())

    strict = lexical("websearch_to_tsquery('english', :q)")
    broad = lexical("to_tsquery('english', array_to_string("
                    "tsvector_to_array(to_tsvector('english', :q)), ' | '))")
    vector_rows: list = []
    embedded = embed_query(query) if embed_query else None
    if embedded is not None:
        op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
        vtype = store.vector_type(db)
        vector_rows = list(db.execute(text(f"""
            SELECT {cols}, 1 - (e.embedding {op} CAST(:v AS {vtype})) AS score
              FROM "{schema}".attachment_chunk_embeddings e
              JOIN "{schema}".attachment_chunks c ON c.id = e.chunk_id {scope}
             ORDER BY e.embedding {op} CAST(:v AS {vtype}) LIMIT :lim"""),
            {"conv": conversation_id, "lim": limit * 2, "att": attachment_id,
             "v": "[" + ",".join(f"{x:.6f}" for x in embedded[0]) + "]"}).all())
    gate = gate_is_open(bool(strict), [float(r[4]) for r in vector_rows[:limit]])

    fused: dict[UUID, float] = {}
    rows: dict[UUID, tuple] = {}
    seen = {r[0] for r in strict}
    lexical_rows = [*strict, *[r for r in broad if r[0] not in seen]]
    for ranked in (lexical_rows, vector_rows):
        for rank, r in enumerate(ranked):
            fused[r[0]] = fused.get(r[0], 0.0) + 1.0 / (RRF_K + rank + 1)
            rows.setdefault(r[0], r)
    order = sorted(fused, key=lambda i: fused[i], reverse=True)[:limit]
    return AttachmentSearch([AttachmentHit(r[0], r[1], r[2], r[3], float(r[4]))
                             for r in (rows[i] for i in order)], gate)


def purge_expired(db: DBSession, now: datetime | None = None) -> int:
    """A4-2: past `expires_at`, the material goes — its chunks, their embeddings (by
    cascade) and its ledger records (class U, with their answer links) are deleted; the
    attachment row is kept as EXPIRED (ids, size and hash only), so the audit trail
    stays whole (rule 17). Runs on every new attachment (`add`) and from
    `tools.purge_attachments` on a daily timer; reads exclude expired material either
    way, so nothing is served between expiry and the purge."""
    schema = _schema()
    ids = [r[0] for r in db.execute(text(f"""
        UPDATE "{schema}".conversation_attachments SET status = 'EXPIRED'
         WHERE status <> 'EXPIRED' AND expires_at <= :now RETURNING id"""),
        {"now": now or datetime.now(UTC)}).all()]
    if ids:
        db.execute(text(f"""
            DELETE FROM "{schema}".conversation_evidence
             WHERE attachment_chunk_id IN (SELECT id FROM "{schema}".attachment_chunks
                                            WHERE attachment_id = ANY(:ids))"""),
            {"ids": ids})
        db.execute(text(f'DELETE FROM "{schema}".attachment_chunks '
                        "WHERE attachment_id = ANY(:ids)"), {"ids": ids})
        log_event("assist.attachment.purged", count=str(len(ids)))
    return len(ids)
