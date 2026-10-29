"""Mapping persistence — locked Step 28 r7, r15; 35.18, 35.20.

Locked 35.20: mapping rules are versioned as part of Legal Configuration, so a
mapping run reads its rules from the Review's configuration snapshot — never
from current configuration. That is what makes a mapping reproducible from the
Document Version plus configuration versions (Step 28 r15).

Locked Step 28 r8: Requirement mapping is separate from Company Standard
evaluation. This module produces mapping states and evidence; it produces no
classification, no rule outcome and no Finding.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.db.lookup import latest_completed_run_id
from legalmind.mapping.engine import Clause, MappingResult, map_document
from legalmind.mapping.rules import MappingRules


@dataclass(frozen=True)
class MappingRun:
    """Result of mapping one Review's document against its snapshot config."""

    review_id: UUID
    results: dict[UUID, MappingResult]

    def state_of(self, requirement_version_id: UUID):
        return self.results[requirement_version_id].state


#: A DOCX header or footer row (``metadata.part``, parsing._docx_furniture): page
#: furniture, never a clause. Nothing read them before legalmind-ingest-v5, so leaving
#: them out keeps every clause reader's input exactly as it was (BR-4). Footnotes,
#: endnotes and text boxes are body content and stay.
PAGE_FURNITURE = ("header", "footer")


def body_rows(rows: Iterable[M.DocumentEvidence]) -> list[M.DocumentEvidence]:
    """``rows`` without page furniture — the one filter every clause reader shares."""
    return [e for e in rows
            if (e.evidence_metadata or {}).get("part") not in PAGE_FURNITURE]


def _marks(meta: dict) -> dict | None:
    """The tracked changes and comments the reader kept on a row, with the row's wording
    before them (`original`), or None."""
    revision = meta.get("revision") or {}
    changes = revision.get("changes") or []
    comments = meta.get("comments") or []
    return ({"changes": changes, "comments": comments,
             "original": revision.get("original")} if changes or comments else None)


def load_clauses(db: DBSession, document_version_id: UUID) -> list[Clause]:
    """Load extracted evidence as mapping candidates.

    Only evidence from the LATEST COMPLETED processing run is used: a failed
    earlier attempt is retained for history (42.5) but must not contribute
    clauses, or a partially-extracted retry could resurrect stale text.
    """
    # One run IS the document (P-8, 2026-09-06) — the same choice every other
    # reader makes, made in one place.
    run_id = latest_completed_run_id(db, document_version_id)
    if run_id is None:
        return []

    rows = body_rows(db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.processing_run_id == run_id)
        .order_by(M.DocumentEvidence.page_number, M.DocumentEvidence.start_offset)
    ).scalars().all())
    return [
        Clause(
            evidence_id=e.id,
            content=e.content,
            section_number=e.section_number,
            section_title=e.section_title,
            page_number=e.page_number,
            is_heading=bool((e.evidence_metadata or {}).get("heading")),
            marks=_marks(e.evidence_metadata or {}),
        )
        for e in rows
    ]


def load_snapshot_mapping_rules(
    db: DBSession, snapshot_id: UUID
) -> dict[UUID, MappingRules]:
    """Read mapping rules from the Review's configuration snapshot.

    Locked Step 30 / AUD-04: a Review never changes configuration midway, and a
    historical Review must reproduce from the exact versions it used. Reading
    current configuration here would silently break both.
    """
    rows = db.execute(
        select(
            M.ConfigurationSnapshotItem.requirement_version_id,
            M.MappingRuleVersion.rules,
        )
        .join(
            M.MappingRuleVersion,
            M.MappingRuleVersion.id
            == M.ConfigurationSnapshotItem.mapping_rule_version_id,
        )
        .where(M.ConfigurationSnapshotItem.snapshot_id == snapshot_id)
    ).all()
    return {rv_id: MappingRules.from_config(rules or {}) for rv_id, rules in rows}


def run_mapping(db: DBSession, review: M.Review) -> MappingRun:
    """Map a Review's document against its snapshot configuration."""
    clauses = load_clauses(db, review.document_version_id)
    rules = load_snapshot_mapping_rules(db, review.configuration_snapshot_id)
    return MappingRun(review_id=review.id, results=map_document(rules, clauses))
