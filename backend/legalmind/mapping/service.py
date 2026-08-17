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

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.mapping.engine import Clause, MappingResult, map_document
from legalmind.mapping.rules import MappingRules


@dataclass(frozen=True)
class MappingRun:
    """Result of mapping one Review's document against its snapshot config."""

    review_id: UUID
    results: dict[UUID, MappingResult]

    def state_of(self, requirement_version_id: UUID):
        return self.results[requirement_version_id].state


def load_clauses(db: DBSession, document_version_id: UUID) -> list[Clause]:
    """Load extracted evidence as mapping candidates.

    Only evidence from the LATEST COMPLETED processing run is used: a failed
    earlier attempt is retained for history (42.5) but must not contribute
    clauses, or a partially-extracted retry could resurrect stale text.
    """
    # Ordering note: `created_at` defaults to PostgreSQL now(), which returns
    # TRANSACTION start time — two runs created in the same transaction share
    # it, making "latest" non-deterministic. `started_at` is assigned per run
    # from the application clock, and `id` is a final deterministic tiebreak, so
    # this ordering is stable (ENG-11).
    run_id = db.execute(
        select(M.DocumentProcessingRun.id)
        .where(
            M.DocumentProcessingRun.document_version_id == document_version_id,
            M.DocumentProcessingRun.status == "COMPLETED",
        )
        .order_by(
            M.DocumentProcessingRun.started_at.desc().nullslast(),
            M.DocumentProcessingRun.created_at.desc(),
            M.DocumentProcessingRun.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if run_id is None:
        return []

    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.processing_run_id == run_id)
        .order_by(M.DocumentEvidence.page_number, M.DocumentEvidence.start_offset)
    ).scalars().all()
    return [
        Clause(
            evidence_id=e.id,
            content=e.content,
            section_number=e.section_number,
            section_title=e.section_title,
            page_number=e.page_number,
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
