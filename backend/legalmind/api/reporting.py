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
from legalmind.evaluation.user_status import folded_user_status_counts
from legalmind.security import audit as A
from legalmind.workflow import contract_outcome as CO
from legalmind.workflow.review_progress import review_progress


def _analysed_as(db: DBSession, review: M.Review) -> str | None:
    """The type the analysis run measured the paper as (AM-180: declared, or read from
    the paper's own title) — from the run's own audit record."""
    event = db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.action == A.ANALYSIS_RUN_RECORDED,
               M.AuditEvent.entity_type == "review",
               M.AuditEvent.entity_id == review.id)
        .order_by(M.AuditEvent.timestamp.desc())
    ).scalars().first()
    value = (event.after_state or {}).get("document_type") if event is not None else None
    return value if isinstance(value, str) else None


def _applicability(db: DBSession, review: M.Review) -> list[dict[str, Any]]:
    event = db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.action == A.ANALYSIS_RUN_RECORDED,
               M.AuditEvent.entity_type == "review",
               M.AuditEvent.entity_id == review.id)
        .order_by(M.AuditEvent.timestamp.desc())
    ).scalars().first()
    if event is None:
        return []
    rows = (event.after_state or {}).get("applicability") or []
    return [r for r in rows if isinstance(r, dict)]


def report_payload(db: DBSession, review: M.Review, *,
                   legal_position: bool = True) -> dict[str, Any]:
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
    # REC-02 / D-4 (owner, 2026-09-01) — WHICH provisions, not just how many, so
    # a human can actually look at each one. Reading order matches every other
    # evidence listing in the product (page, offset, then id — BR-6: id is a random
    # uuid4, so it alone is no reading order); the excerpt length
    # matches the assist lane's own citation convention (240 chars).
    unmatched_detail = db.execute(
        select(M.DocumentEvidence)
        .join(M.UnmatchedProvision,
              M.UnmatchedProvision.evidence_id == M.DocumentEvidence.id)
        .where(M.UnmatchedProvision.review_id == review.id)
        .order_by(M.DocumentEvidence.page_number.asc().nulls_last(),
                 M.DocumentEvidence.start_offset.asc().nulls_last(),
                 M.DocumentEvidence.id.asc())
    ).scalars().all()

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
            # AM-61 — every pinned Requirement's applicability outcome and reason,
            # from the analysis run's own audit record: what was NOT measured is
            # shown, never inferred from a count. Empty for runs that predate it.
            "applicability": _applicability(db, review),
        },
        "analysed_as": _analysed_as(db, review),
        "classification_counts": dict(classifications),
        # The reader's three words (owner, 2026-09-09) — the Summary and the
        # report speak ACCEPTABLE / REQUIRES_MODIFICATION / NEEDS_DECISION; the engine's
        # classifications above stay for audit.
        "user_status_counts": folded_user_status_counts(
            db, [review.id], legal_position=legal_position).get(review.id, {}),
        "status_counts": dict(statuses),
        "alignment": {
            "requirements_evaluated": evaluated,
            "matched": matched,
            "ratio": round(matched / evaluated, 4) if evaluated else None,
        },
        # REC-02 — a document-level observation, never a Finding classification.
        "unmatched_provisions": unmatched,
        # D-4 (owner, 2026-09-01): every unmatched provision is routed to a
        # human — never presumed negative (REC-02 rule 1), just outside the
        # system's comparison baseline. Never a Finding, never a classification,
        # never a Legal Decision input.
        "unmatched_provisions_detail": [{
            "evidence_id": str(row.id),
            "page_number": row.page_number,
            "section_number": row.section_number,
            "section_title": row.section_title,
            "excerpt": row.content[:240],
        } for row in unmatched_detail],
        # who decided what, when and why (owner, 2026-10-21) — each Evaluation's current
        # decision, oldest first; the reason is the decider's own words
        "decisions": _decisions(db, review),
        "contract_outcome": outcome_payload(db, review),
        # where the review stands — the same derivation the workspace reads (AM-179)
        "progress": review_progress(db, review, legal_position=legal_position),
        "findings_requiring_decision": (
            statuses.get(E.FindingStatus.DECISION_REQUIRED.value, 0)
            + statuses.get(E.FindingStatus.AWAITING_CLARIFICATION.value, 0)
        ),
    }


def _decisions(db: DBSession, review: M.Review) -> list[dict[str, Any]]:
    rows = db.execute(
        select(M.LegalDecision, M.Requirement.code, M.RequirementVersion.name, M.User)
        .join(M.Finding, M.Finding.id == M.LegalDecision.finding_id)
        .join(M.RequirementVersion,
              M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .outerjoin(M.User, M.User.id == M.LegalDecision.decided_by)
        .where(M.Finding.review_id == review.id)
        .order_by(M.LegalDecision.created_at, M.LegalDecision.version_number)).all()
    current: dict[UUID, dict[str, Any]] = {}
    for decision, code, name, user in rows:        # the last version per Evaluation wins
        current[decision.evaluation_id] = {
            "finding_id": str(decision.finding_id),
            "requirement_code": code, "requirement_name": name,
            "decision_type": decision.decision_type.value,
            "decided_by_name": (user.name or user.email) if user else None,
            "decided_at": (decision.created_at.isoformat()
                           if decision.created_at else None),
            "justification": decision.justification,
            "version_number": decision.version_number,
        }
    return sorted(current.values(), key=lambda d: d["decided_at"] or "")


def outcome_payload(db: DBSession, review: M.Review) -> dict[str, Any]:
    """AM-174 — the decision on the whole contract: the code's suggestion, whether it
    can be recorded yet, and every version (the last is current)."""
    chain = CO.history(db, review.id)
    names = {u.id: u.name or u.email for u in db.execute(
        select(M.User).where(M.User.id.in_({c.decided_by for c in chain}))).scalars()
    } if chain else {}
    return {
        # the code's suggestion from the point decisions now; a person chooses
        "suggested": CO.suggest(CO.current_types(db, review.id)).value,
        "ready": review.status in {E.ReviewStatus.RESOLVED, E.ReviewStatus.CLOSED},
        "history": [{"outcome": c.outcome.value, "suggested": c.suggested.value,
                     "justification": c.justification,
                     "decided_by_name": names.get(c.decided_by),
                     "decided_at": c.created_at.isoformat() if c.created_at else None,
                     "version_number": c.version_number} for c in chain],
    }


def review_findings(db: DBSession, review_id: UUID) -> list[M.Finding]:
    """Every Finding of the Review, in the same stable order the list endpoint
    uses (created_at, id)."""
    return list(db.execute(
        select(M.Finding)
        .where(M.Finding.review_id == review_id)
        .order_by(M.Finding.created_at, M.Finding.id)
    ).scalars().all())
