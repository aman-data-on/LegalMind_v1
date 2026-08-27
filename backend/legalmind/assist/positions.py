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
    return report


def search_positions(db: DBSession, *, query: str, permissions: frozenset[str],
                     limit: int = 10) -> list[PositionHit]:
    """Domain A lexical retrieval, authorization inside the function (r5).

    Without BOTH assist.ask and configuration.view the result is [], exactly the
    shape an empty corpus returns — `AM-25` r6/r7. Lexical-first: the shared
    embedding machinery joins in the vector increment; the extractive answer's
    correctness never depends on it.
    """
    if P.ASSIST_ASK not in permissions or P.CONFIGURATION_VIEW not in permissions:
        return []
    schema = config.assist_schema()
    rows = db.execute(sql_text(f"""
        SELECT id, standard_code, document_type, source_clause, content,
               ts_rank(content_tsv, plainto_tsquery('english', :q)) AS score
        FROM "{schema}".position_chunks
        WHERE content_tsv @@ plainto_tsquery('english', :q)
        ORDER BY score DESC, standard_code
        LIMIT :limit
    """), {"q": query, "limit": limit}).all()
    log_event("assist.positions.searched", hits=len(rows),
              level=logging.DEBUG)
    return [PositionHit(position_chunk_id=r.id, standard_code=r.standard_code,
                        document_type=r.document_type, source_clause=r.source_clause,
                        content=r.content, score=float(r.score))
            for r in rows]
