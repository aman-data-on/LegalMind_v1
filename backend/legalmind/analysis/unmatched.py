"""UNMATCHED_PROVISION observations — `REC-02`, `D-4` resolved (owner, 2026-09-01).

`REC-02` (locked): a provision in the counterparty document with no corresponding
configured Requirement is a **document-level observation**, never a Finding
Classification. It left the persistence model, surfacing and review treatment
NOT YET SPECIFIED (docs/04-analysis-engine/EDGE_CASES/ANALYSIS_ORCHESTRATOR_GAP.md,
"D-4"), naming the exact fork: write nothing (D-4a, the status quo) or write
one row per clause that matched no Requirement (D-4b).

The owner resolved D-4 this session: build D-4b, and route every unmatched
provision to a human for their own look (never presumed negative — REC-02 rule
1 stands unchanged; a human looks because the system has no baseline to judge
it against, not because the clause is assumed risky).

--------------------------------------------------------------------------
Why this needs none of D-1/D-2/D-3's still-open decisions
--------------------------------------------------------------------------
D-4b's literal wording ("matched no Requirement above threshold") reads as
needing D-1's confirm_threshold — the single most protected number in the
specification, explicitly gated on real-contract calibration (35.10) that has
not happened. This module does NOT decide that threshold, and does not need
to: "matched" here is defined operationally as *"a Finding of this Review
actually cites this evidence"* — a fact already fully decided by the existing,
already-calibrated mapping/evaluation pipeline, not a new scored judgment.
Every clause that never entered any Finding's or Evaluation's evidence set —
regardless of why (no candidate Requirement of the right type existed, the
candidate scored below whatever threshold, or nothing was ever attempted) —
is, definitionally, unmatched. No new number is invented; D-1, D-2 and D-3
stay exactly as open as they were.

--------------------------------------------------------------------------
The unit is a CLAUSE, not a raw evidence row
--------------------------------------------------------------------------
A document's paragraphs commonly split a clause across several evidence rows —
its heading ("2. Payment") and its body sentence(s) as separate rows. A
Requirement's mapping typically matches the substantive body text, never the
bare heading. Treating each row independently would flag every heading in a
document as its own "unmatched provision" even when the clause it introduces
matched perfectly — noise, not a fact a lawyer needs. So rows are grouped by
clause exactly the way the workspace's own outline already groups them
(`outlineStatus` in the frontend — the same rule in two languages): a row that
carries a `section_number`/`section_title` opens a new clause and every
following row belongs to it until the next one does. A clause counts as
matched if ANY of its rows were cited; an unmatched clause is recorded ONCE,
at its anchor row (the heading when one exists), never once per sentence.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M


def _clause_groups(
    rows: Sequence[M.DocumentEvidence],
) -> list[list[M.DocumentEvidence]]:
    """Reading-order rows -> clause groups, mirroring the frontend's
    `outlineStatus`: a heading row opens a group; unheaded rows join the
    currently open group, or stand alone before any heading has appeared."""
    groups: list[list[M.DocumentEvidence]] = []
    for row in rows:
        opens_new_group = bool(row.section_number or row.section_title)
        if opens_new_group or not groups:
            groups.append([row])
        else:
            groups[-1].append(row)
    return groups


def record_unmatched_provisions(db: DBSession, review: M.Review,
                                document_version_id: UUID) -> int:
    """One `UnmatchedProvision` row per CLAUSE this Review's Findings never
    cited (anchored at the clause's heading row when it has one). Called once,
    inside `run_analysis`'s own transaction, after every Finding and
    Evaluation of the Review exists — `assert_analysable` already refuses a
    second analysis of the same Review, so this never double-runs and never
    collides with `UNIQUE(review_id, evidence_id)`.
    """
    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == document_version_id)
        .order_by(M.DocumentEvidence.page_number.asc().nulls_last(),
                 M.DocumentEvidence.start_offset.asc().nulls_last(),
                 M.DocumentEvidence.id.asc())
    ).scalars().all()
    if not rows:
        return 0

    cited = set(db.execute(
        select(M.FindingEvidence.evidence_id)
        .join(M.Finding, M.Finding.id == M.FindingEvidence.finding_id)
        .where(M.Finding.review_id == review.id)
    ).scalars().all())
    cited |= set(db.execute(
        select(M.EvaluationEvidence.evidence_id)
        .join(M.Evaluation, M.Evaluation.id == M.EvaluationEvidence.evaluation_id)
        .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
        .where(M.Finding.review_id == review.id)
    ).scalars().all())

    written = 0
    for group in _clause_groups(rows):
        if any(row.id in cited for row in group):
            continue
        db.add(M.UnmatchedProvision(review_id=review.id, evidence_id=group[0].id))
        written += 1
    if written:
        db.flush()
    return written
