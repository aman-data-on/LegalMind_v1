"""Domain A — position chunks over the ratified Company Standards (`AM-32` r3–r5).

Three properties of this module are locked consequences, not preferences:

**The ratified standard is the single source of truth** (r3). There is no positions
content table; a chunk's `content` is composed exclusively of the ratified file's own
verbatim fields, and the row FK-references the *published* `company_standard_versions`
row it derives from. Re-chunking a standard first hard-deletes the chunks of every
version of that standard (the `AM-27` r5 principle applied to configuration), so a
superseded version's text can never keep answering.

**Domain A output is extractive-only** (r4). Nothing in this module builds a
generation payload, and `service.py` must never pass a position chunk to
`generation.generate` — `AM-30` t3 forbids any Company Standard value in an egressing
payload. `tests/test_positions.py` pins the import boundary: this module imports no
generation code.

**Access is `assist.ask` AND `configuration.view`, inside the query** (r5). The
search function takes the caller's resolved permission set and returns nothing —
indistinguishable from an empty corpus — without both. There is no separate
"forbidden" outcome (`AM-25` r6/r7).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.db import models as M
from legalmind.observability.logs import log_event
from legalmind.security import permissions as P

CHUNKING_ALGORITHM_VERSION = "positions-verbatim-1"

RATIFIED_STANDARDS_DIR = (
    Path(__file__).resolve().parents[2] / "config" / "company_standards")


class PositionChunkingRefused(Exception):
    """Raised when a ratified file cannot be chunked without inventing something."""


@dataclass(frozen=True)
class PositionHit:
    position_chunk_id: UUID
    standard_code: str
    document_type: str
    source_clause: str | None
    content: str
    score: float


def _compose_content(payload: dict) -> str:
    """The chunk text — the ratified file's own verbatim fields, nothing authored.

    The identifying prefix (code, clause, type) is what makes "what is our
    arbitration policy?" findable by lexical search; the quote is the answer a
    Domain A result renders verbatim (r4).
    """
    parts = [
        f"{payload['requirement_code']}",
        f"{payload['source_clause']}",
        f"({payload['configuration']['document_type']})",
        f"— {payload['source_document']}:",
        payload["source_quote"],
    ]
    return " ".join(p for p in parts if p)


def _published_version(db: DBSession, code: str) -> M.CompanyStandardVersion | None:
    """The current standard version for a code — the import tool's own resolution."""
    req = db.execute(
        select(M.Requirement).where(M.Requirement.code == code)
    ).scalars().first()
    if req is None:
        return None
    latest_rv = db.execute(
        select(M.RequirementVersion)
        .where(M.RequirementVersion.requirement_id == req.id)
        .order_by(M.RequirementVersion.version_number.desc())
        .limit(1)).scalars().first()
    if latest_rv is None:
        return None
    return db.execute(
        select(M.CompanyStandardVersion)
        .where(M.CompanyStandardVersion.requirement_version_id == latest_rv.id)
        .order_by(M.CompanyStandardVersion.version_number.desc())
        .limit(1)).scalars().first()


def chunk_ratified_standards(db: DBSession, *,
                             directory: Path | None = None) -> list[str]:
    """(Re)build Domain A chunks from the ratified files against the imported rows.

    Refuses (rather than skips) a file whose standard is not imported, or one
    missing its verbatim fields — a silently-skipped position would be a search
    surface that quietly lies about coverage.
    """
    schema = config.assist_schema()
    src = directory or RATIFIED_STANDARDS_DIR
    files = sorted(src.glob("*.json"))
    if not files:
        raise PositionChunkingRefused(f"no ratified standards in {src}")

    report: list[str] = []
    for path in files:
        payload = json.loads(path.read_text())
        code = payload.get("requirement_code")
        for field in ("requirement_code", "source_quote", "source_clause",
                      "source_document"):
            if not payload.get(field):
                raise PositionChunkingRefused(
                    f"{path.name}: missing {field!r} — a position chunk is composed "
                    "of the ratified file's own verbatim fields and cannot be "
                    "invented (rule 21)")
        document_type = (payload.get("configuration") or {}).get("document_type")
        if not document_type:
            raise PositionChunkingRefused(
                f"{path.name}: missing configuration.document_type")

        version = _published_version(db, code)
        if version is None:
            raise PositionChunkingRefused(
                f"{path.name}: standard {code!r} has no imported "
                "company_standard_versions row — run "
                "tools.import_ratified_standards first")

        # r3 lifecycle: delete chunks of EVERY version of this standard's
        # requirement, then chunk the current version. CASCADE removes embeddings.
        db.execute(sql_text(f"""
            DELETE FROM "{schema}".position_chunks
            WHERE standard_code = :code
        """), {"code": code})

        db.execute(sql_text(f"""
            INSERT INTO "{schema}".position_chunks
                (id, standard_version_id, standard_code, document_type, ordinal,
                 content, source_clause, chunking_algorithm_version)
            VALUES (:id, :version_id, :code, :doc_type, 0, :content, :clause, :algo)
        """), {
            "id": str(uuid4()),
            "version_id": str(version.id),
            "code": code,
            "doc_type": document_type,
            "content": _compose_content(payload),
            "clause": payload["source_clause"],
            "algo": CHUNKING_ALGORITHM_VERSION,
        })
        report.append(f"{code}: chunked (version row {version.id})")

    # 53.3 discipline: counts and codes only, never standard text.
    log_event("assist.positions.chunked", count=len(report))
    embed_positions(db)
    return report


def embed_positions(db: DBSession) -> int:
    """Embed every position chunk that lacks a vector — `AM-32`'s
    `position_chunk_embeddings`, filled (2026-09-09) with the calibrated model.

    Best-effort in the sense `indexing._embed_chunks` gives the word: a missing model
    never fails chunking, because lexical retrieval works without vectors and the
    extractive answer's correctness never depends on them. What vectors add is
    RECALL for a paraphrased question — "how much notice ends the NDA early?" shares
    no lexeme with "terminated by either Party … thirty (30) days' notice" — and
    the calibrated gate decides whether a vector-only neighbour is evidence at all.
    """
    from legalmind.assist import calibration, embedding_runtime, store

    if not embedding_runtime.available():
        return 0
    schema = config.assist_schema()
    rows = db.execute(sql_text(f"""
        SELECT pc.id, pc.content FROM "{schema}".position_chunks pc
         WHERE NOT EXISTS (SELECT 1 FROM "{schema}".position_chunk_embeddings e
                            WHERE e.position_chunk_id = pc.id)
         ORDER BY pc.standard_code, pc.ordinal
    """)).all()
    if not rows:
        return 0
    vectors = embedding_runtime.embed_texts([r[1] for r in rows])
    if vectors is None:
        return 0
    identity = embedding_runtime.identity() or calibration.EMBEDDING_MODEL_REPO
    name, _, revision = identity.partition("@")
    model_id = store.register_embedding_model(
        db, name=name, version=revision or calibration.EMBEDDING_MODEL_REVISION,
        dimensions=calibration.EMBEDDING_DIMENSIONS,
        checksum=embedding_runtime.checksum_fragment() or "unrecorded")
    vtype = store.vector_type(db)
    db.execute(sql_text(f"""
        INSERT INTO "{schema}".position_chunk_embeddings
            (id, position_chunk_id, embedding_model_id, embedding)
        VALUES (:i, :c, :m, CAST(:v AS {vtype}))
        ON CONFLICT (position_chunk_id, embedding_model_id) DO NOTHING
    """), [{"i": str(uuid4()), "c": r[0], "m": model_id,
            "v": "[" + ",".join(f"{x:.6f}" for x in vec) + "]"}
           for r, vec in zip(rows, vectors, strict=True)])
    log_event("assist.positions.embedded", count=len(rows))
    return len(rows)


def search_positions(db: DBSession, *, query: str, permissions: frozenset[str],
                     limit: int = 10, embed_query=None) -> list[PositionHit]:
    """Domain A hybrid retrieval, authorization inside the function (r5).

    Without assist.ask AND (configuration.view OR legal_position.view) the result is
    [], exactly the shape an empty corpus returns — `AM-25` r6/r7. Lexical-first: a
    lexical hit is trusted on its own (the calibrated finding). The vector increment
    (2026-09-09) is the shared embedding machinery `AM-32` r9 names: the question's
    embedding is compared with the stored position vectors and neighbours are
    admitted only through the SAME calibrated gate the document retrieval uses
    (`calibration.gate_is_open` — floor plus peak margin), then fused with the
    lexical ranking by reciprocal rank. The extractive answer's correctness never
    depends on it; what it adds is recall for a paraphrase.

    ``embed_query`` is injectable for tests; by default the runtime's own callable.
    """
    # `AM-32` r5 as amended by `AM-44` (2026-09-08): `configuration.view` OR
    # `legal_position.view` — see `routing.positions_permitted` for the reasoning.
    if P.ASSIST_ASK not in permissions or not (
            P.CONFIGURATION_VIEW in permissions or P.LEGAL_POSITION_VIEW in permissions):
        return []
    schema = config.assist_schema()
    # OR-semantics with a match floor (2026-09-08). `plainto_tsquery` ANDs every
    # lexeme, so a natural question — "what is our approved position on widget
    # handling?" — matched nothing because "approved" and "position" are not in the
    # standard's text. The lexemes of the question are OR-ed instead, and a chunk
    # must share at least two of them (one, for a one-word question) so a single
    # common word never fetches the whole corpus. Ranked by matched lexemes, then
    # ts_rank, then code — deterministic for identical input.
    rows = db.execute(sql_text(f"""
        WITH q AS (
            SELECT tsvector_to_array(to_tsvector('english', :q)) AS lex
        ), scored AS (
            SELECT pc.id, pc.standard_code, pc.document_type, pc.source_clause,
                   pc.content,
                   (SELECT count(*)
                      FROM q, unnest(tsvector_to_array(pc.content_tsv)) l
                     WHERE l = ANY(q.lex)) AS matched,
                   ts_rank(pc.content_tsv,
                           to_tsquery('english', (SELECT array_to_string(lex, ' | ')
                                                    FROM q))) AS score
              FROM "{schema}".position_chunks pc
             WHERE (SELECT cardinality(lex) FROM q) > 0
        )
        SELECT id, standard_code, document_type, source_clause, content, score, matched
          FROM scored
         WHERE matched >= LEAST(2, (SELECT cardinality(lex) FROM q))
         ORDER BY matched DESC, score DESC, standard_code
         LIMIT :limit
    """), {"q": query, "limit": limit}).all()
    lexical = [PositionHit(position_chunk_id=r.id, standard_code=r.standard_code,
                           document_type=r.document_type, source_clause=r.source_clause,
                           content=r.content, score=float(r.score))
               for r in rows]
    vector = _vector_neighbours(db, query, limit=limit, embed_query=embed_query)
    hits = _fuse(lexical, vector, limit)
    log_event("assist.positions.searched", hits=len(hits), lexical=len(lexical),
              vector=len(vector), level=logging.DEBUG)
    return hits


def _vector_neighbours(db: DBSession, query: str, *, limit: int,
                       embed_query=None) -> list[PositionHit]:
    """Gated nearest neighbours over `position_chunk_embeddings`. [] when no model
    is available, when nothing is embedded, or when the calibrated gate stays shut."""
    from legalmind.assist import calibration, embedding_runtime, store

    embed = embed_query or embedding_runtime.embed_query
    embedded = embed(query) if query and query.strip() else None
    if embedded is None:
        return []
    vector, _identity = embedded
    schema = config.assist_schema()
    op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
    vtype = store.vector_type(db)
    literal = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    rows = db.execute(sql_text(f"""
        SELECT pc.id, pc.standard_code, pc.document_type, pc.source_clause, pc.content,
               1 - (pe.embedding {op} CAST(:q AS {vtype})) AS cosine
          FROM "{schema}".position_chunk_embeddings pe
          JOIN "{schema}".position_chunks pc ON pc.id = pe.position_chunk_id
         ORDER BY pe.embedding {op} CAST(:q AS {vtype}), pc.standard_code
         LIMIT :lim
    """), {"q": literal, "lim": max(limit, calibration.RETRIEVAL_TOP_K)}).all()
    scores = [float(r.cosine) for r in rows]
    if not calibration.gate_is_open(False, scores):
        return []
    return [PositionHit(position_chunk_id=r.id, standard_code=r.standard_code,
                        document_type=r.document_type, source_clause=r.source_clause,
                        content=r.content, score=float(r.cosine))
            for r in rows if float(r.cosine) >= calibration.EVIDENCE_COSINE_FLOOR][:limit]


def _fuse(lexical: list[PositionHit], vector: list[PositionHit],
          limit: int) -> list[PositionHit]:
    """Reciprocal rank fusion (k=60). An exact tie goes to the vector side: a gated
    cosine is a stronger relevance signal than two shared lexemes (measured live: a
    liability standard sharing "agreement" and "give" with a notice question tied
    with the notice standard the vector had ranked first, and an alphabetical
    tie-break put liability on top). Deterministic: insertion order breaks ties."""
    fused: dict[UUID, float] = {}
    by_id: dict[UUID, PositionHit] = {}
    for rank, hit in enumerate(vector, start=1):
        key = hit.position_chunk_id
        fused[key] = fused.get(key, 0.0) + 1 / (60 + rank)
        by_id.setdefault(hit.position_chunk_id, hit)
    for rank, hit in enumerate(lexical, start=1):
        key = hit.position_chunk_id
        fused[key] = fused.get(key, 0.0) + 1 / (60 + rank)
        by_id.setdefault(hit.position_chunk_id, hit)
    order = list(fused)
    ordered = sorted(order, key=lambda i: (-fused[i], order.index(i)))
    return [by_id[i] for i in ordered[:limit]]
