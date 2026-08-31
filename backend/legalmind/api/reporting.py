"""The Review report aggregation — F-8, F-9, locked 36.10, Step 9.

Extracted from the report route so the export route (49.3's
``POST /reviews/{id}/export``) renders **the same numbers the report endpoint
serves** — one aggregation, two presentations. Nothing here interprets: counts,
a coverage pair, and an alignment ratio that F-9 locks to "carries no legal
meaning". No risk score, no verdict (36.10, F-8) — deliberately absent from the
payload, so no renderer downstream can show one.
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E


def report_payload(db: DBSession, review: M.Review) -> dict[str, Any]:
    findings = db.execute(
        select(M.Finding).where(M.Finding.review_id == review.id)
    ).scalars().all()

    classifications = Counter(f.classification.value for f in findings)
    statuses = Counter(f.status.value for f in findings)

    requirements_in_snapshot = db.execute(
        select(func.count())
        .select_from(M.ConfigurationSnapshotItem)
        .where(M.ConfigurationSnapshotItem.snapshot_id
               == review.configuration_snapshot_id)
    ).scalar_one()

    unmatched = db.execute(
        select(func.count()).select_from(M.UnmatchedProvision)
        .where(M.UnmatchedProvision.review_id == review.id)
    ).scalar_one()

    evaluated = len(findings)
    matched = classifications.get(E.FindingClassification.MATCH.value, 0)

    return {
        "review_id": str(review.id),
        "review_status": review.status.value,
        # F-1 / Step 8 — coverage reporting is what answers "which Requirements
        # were reviewed", now that an optional absent Requirement produces no
        # Finding at all. The gap between the two numbers is meaningful.
        "coverage": {
            "requirements_in_snapshot": requirements_in_snapshot,
            "requirements_with_findings": evaluated,
        },
        "classification_counts": dict(classifications),
        "status_counts": dict(statuses),
        "alignment": {
            "requirements_evaluated": evaluated,
            "matched": matched,
            "ratio": round(matched / evaluated, 4) if evaluated else None,
        },
        # REC-02 — a document-level observation, never a Finding classification.
        "unmatched_provisions": unmatched,
        "findings_requiring_decision": (
            statuses.get(E.FindingStatus.DECISION_REQUIRED.value, 0)
            + statuses.get(E.FindingStatus.AWAITING_CLARIFICATION.value, 0)
        ),
    }


def review_findings(db: DBSession, review_id: UUID) -> list[M.Finding]:
    """Every Finding of the Review, in the same stable order the list endpoint
    uses (created_at, id)."""
    return list(db.execute(
        select(M.Finding)
        .where(M.Finding.review_id == review_id)
        .order_by(M.Finding.created_at, M.Finding.id)
    ).scalars().all())
