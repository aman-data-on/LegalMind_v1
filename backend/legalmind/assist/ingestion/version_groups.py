"""Near-duplicate document versions share a version group — Ask plan 1.13, `AM-110`.

Two uploads of one agreement — a re-sent copy, a lightly revised draft — should be cited
as one agreement in several versions, never as two agreements. The group is DERIVED
from the evidence text and stored in `document_version_attributes`; nothing upstream
reads it to decide anything, and the evidence itself is untouched.

Text alone never groups. Measured on the real corpus (2026-10-01): copies and revisions
of one agreement scored 0.82–1.0 word 5-shingle Jaccard and unrelated documents below
0.10, but two DIFFERENT clients' agreements on one template scored 1.0. So a version is
compared only with the same contract's other versions and with versions of contracts
linked to the SAME counterparty; with no counterparty, only within its own contract.
A wrong merge would hide an agreement, which is worse than a missed group.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.db.lookup import latest_completed_run_id

ALGORITHM_VERSION = "shingle5-jaccard-0.75"
SHINGLE_WORDS = 5
# Between 0.82 (the lowest true pair measured) and 0.10 (the highest unrelated pair).
SAME_AGREEMENT = 0.75
_WORD = re.compile(r"[a-z0-9]+")


def shingles(content: str) -> set[tuple[str, ...]]:
    words = _WORD.findall(content.lower())
    n = SHINGLE_WORDS
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def similarity(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0


def _text(db: DBSession, document_version_id: UUID) -> str:
    """The version's text as its latest completed run read it (one run IS the document,
    P-8) — never two segmentations merged."""
    return " ".join(db.execute(text(
        "SELECT content FROM document_evidence WHERE document_version_id = :v "
        "AND processing_run_id = :r "
        "ORDER BY page_number NULLS FIRST, start_offset NULLS FIRST, id"),
        {"v": document_version_id,
         "r": latest_completed_run_id(db, document_version_id)}).scalars())


def _candidates(db: DBSession, document_version_id: UUID) -> list[tuple[UUID, UUID]]:
    """(version, its group) for every grouped version this one may join."""
    schema = config.assist_schema()
    return [(r[0], r[1]) for r in db.execute(text(f"""
        SELECT a.document_version_id, a.version_group
          FROM document_versions me
          JOIN contracts mc ON mc.id = me.contract_id
          JOIN "{schema}".document_version_attributes a ON a.document_version_id <> me.id
          JOIN document_versions dv ON dv.id = a.document_version_id
          JOIN contracts c ON c.id = dv.contract_id
         WHERE me.id = :v
           AND (c.id = mc.id OR (mc.counterparty_id IS NOT NULL
                                 AND c.counterparty_id = mc.counterparty_id))
         ORDER BY a.computed_at, a.document_version_id
    """), {"v": document_version_id}).all()]


def assign(db: DBSession, document_version_id: UUID) -> UUID:
    """Record this version's group: the best candidate at or above SAME_AGREEMENT, or
    a new group of its own. Idempotent — re-assigning keeps the stored row current."""
    content = _text(db, document_version_id)
    mine = shingles(content)
    best: tuple[float, UUID] | None = None
    for other, group in _candidates(db, document_version_id):
        score = similarity(mine, shingles(_text(db, other)))
        if score >= SAME_AGREEMENT and (best is None or score > best[0]):
            best = (score, group)
    group = best[1] if best else document_version_id
    db.execute(text(f"""
        INSERT INTO "{config.assist_schema()}".document_version_attributes
               (id, document_version_id, version_group, normalized_text_sha256,
                similarity, algorithm_version)
        VALUES (:i, :v, :g, :h, :s, :a)
        ON CONFLICT (document_version_id) DO UPDATE
           SET version_group = EXCLUDED.version_group,
               normalized_text_sha256 = EXCLUDED.normalized_text_sha256,
               similarity = EXCLUDED.similarity,
               algorithm_version = EXCLUDED.algorithm_version, computed_at = now()
    """), {"i": uuid.uuid4(), "v": document_version_id, "g": group,
           "h": hashlib.sha256(" ".join(_WORD.findall(content.lower())).encode())
           .hexdigest(),
           "s": best[0] if best else None, "a": ALGORITHM_VERSION})
    return group


def group_of(db: DBSession, document_version_id: UUID) -> UUID | None:
    return db.execute(text(
        f'SELECT version_group FROM "{config.assist_schema()}"'
        ".document_version_attributes "
        "WHERE document_version_id = :v"), {"v": document_version_id}).scalar()
