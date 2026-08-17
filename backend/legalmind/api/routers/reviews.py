"""Reviews and the review report — locked 49.3, 49.6, 49.8, Step 30.

Review visibility follows locked Step 24 / ROLE-07 exactly: ownership or an active
Legal assignment, and nothing else — not role name (r12). The list query below
mirrors ``can_see_review`` deliberately, and a test asserts the two cannot
disagree, because a list that leaked one row a ``GET`` would 404 on is the same
defect as an IDOR (49.6).

**There is no endpoint that sets Review status.** Locked Step 30 r3 says users
cannot arbitrarily set it and r16 says summaries are derived; the lifecycle is
advanced by the workflow, not asserted by a caller.
"""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, or_, select

from legalmind.analysis.service import AnalysisNotPermitted, run_analysis
from legalmind.api import ratelimit
from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.schemas import ReviewCreate
from legalmind.api.serializers import serialize_finding, serialize_review
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.security.authorization import require_contract_visible

router = APIRouter(tags=["reviews"])

# Module-level so a deployment can swap in the Redis-backed limiter without
# touching a route (see ratelimit.InProcessRateLimiter).
_limiter: ratelimit.RateLimiter = ratelimit.InProcessRateLimiter()


def _visible_reviews(guard: Guard):
    """The list-scope counterpart of ``can_see_review`` (Step 24 r2, r6)."""
    assigned = (
        select(M.ReviewAssignment.review_id)
        .where(M.ReviewAssignment.user_id == guard.user_id,
               M.ReviewAssignment.revoked_at.is_(None))
    )
    return select(M.Review).where(
        or_(M.Review.created_by == guard.user_id, M.Review.id.in_(assigned))
    )


@router.get("/reviews")
def list_reviews(
    guard: Guard = Depends(get_guard),
    page: Page = Depends(page_params),
    # 49.6 — filters are an allow-list. Arbitrary field filtering is not
    # supported, so a filter can never become a probe for a field the caller may
    # not see.
    status: E.ReviewStatus | None = Query(default=None),
    contract_id: UUID | None = Query(default=None),
) -> dict:
    guard.permission(P.REVIEW_VIEW)
    stmt = _visible_reviews(guard)
    if status is not None:
        stmt = stmt.where(M.Review.status == status)
    if contract_id is not None:
        stmt = stmt.where(M.Review.contract_id == contract_id)
    rows, total = run(guard.db, stmt, page,
                      M.Review.created_at.desc(), M.Review.id.desc())
    return paginated([serialize_review(r) for r in rows],
                     page=page.page, page_size=page.page_size, total=total)


@router.post("/reviews", status_code=201)
def create_review(body: ReviewCreate, guard: Guard = Depends(get_guard)) -> dict:
    """Locked 49.8 — idempotent on ``(document_version_id,
    configuration_snapshot_id)``.

    Scoped additionally to the creator: two users may legitimately review the same
    document version against the same snapshot, and returning one user's Review to
    the other would leak it (Step 24 r4).

    The Review is created in ``DRAFT``, the locked Step 30 initial state. Note a
    tension worth recording rather than resolving: locked 42.13 makes
    ``document_version_id`` NOT NULL, so a Review cannot exist before its document
    is uploaded, which leaves DRAFT and UPLOADED describing the same real
    situation. Starting at DRAFT keeps every locked transition reachable and
    invents nothing.
    """
    guard.permission(P.REVIEW_CREATE)

    version = guard.db.get(M.DocumentVersion, body.document_version_id)
    if version is None:
        from legalmind.security.errors import NotVisible
        raise NotVisible("document version not found")
    # 47.6 — reachable only through a Contract the caller can see.
    require_contract_visible(guard.db, guard.user_id, version.contract_id)

    snapshot = guard.db.get(M.ConfigurationSnapshot, body.configuration_snapshot_id)
    if snapshot is None:
        raise BusinessRuleRejected("unknown configuration snapshot")

    existing = guard.db.execute(
        select(M.Review).where(
            M.Review.document_version_id == body.document_version_id,
            M.Review.configuration_snapshot_id == body.configuration_snapshot_id,
            M.Review.created_by == guard.user_id,
        ).order_by(M.Review.created_at, M.Review.id)
    ).scalars().first()
    if existing is not None:
        # 43.28 — a retry must not create a second Review. Returning the original
        # is the specified behaviour, not a silent no-op.
        return data(serialize_review(existing))

    review = M.Review(
        contract_id=version.contract_id,
        document_version_id=version.id,
        configuration_snapshot_id=snapshot.id,
        status=E.ReviewStatus.DRAFT,
        created_by=guard.user_id,
    )
    guard.db.add(review)
    guard.db.flush()
    return data(serialize_review(review))


@router.get("/reviews/{review_id}")
def get_review(review_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    return data(serialize_review(guard.review(review_id, P.REVIEW_VIEW)))


@router.post("/reviews/{review_id}/analyze", status_code=201)
def analyze_review(
    review_id: UUID,
    guard: Guard = Depends(get_guard),
    idempotency_key: str | None = Header(default=None, max_length=200),
) -> dict:
    """Run the locked analysis pipeline over this Review — 44.2/44.40, 49.8, 49.10.

    **Permission is an interpretation.** Locked 49.3's table has no analysis row,
    though 49.8 and 49.10 both presuppose the endpoint; `review.create` is the
    closest locked grant. Recorded in ``permission_map`` and flagged there.

    **Runs synchronously.** Locked Step 39 includes Celery/Redis and Step 30's
    `PROCESSING` state exists for the asynchronous case, but no worker is deployed —
    so this is honestly synchronous rather than pretending to be a queued job. The
    orchestrator is a plain service function precisely so moving it behind a worker
    later changes the caller, not the analysis.

    **Idempotency (43.28, 49.8).** A repeat returns the original outcome rather than
    re-running: the orchestrator refuses a Review that already has Findings, and that
    refusal is reported as the already-analysed state, not as an error. Duplicating
    legal output would be the worse failure.
    """
    review = guard.review(review_id, P.REVIEW_CREATE)

    # S-5 / 49.10 — analysis is the expensive path. Keyed per user so one caller
    # cannot exhaust the limit for everyone.
    _limiter.check(f"analysis:{guard.user_id}", ratelimit.ANALYSIS)

    try:
        run = run_analysis(guard.db, review, actor_id=guard.user_id,
                           request_id=guard.request_id)
    except AnalysisNotPermitted as exc:
        # 49.8 — a repeat is not an error. Report what already exists so a retry is
        # indistinguishable from the original call's aftermath.
        return data({
            "review_id": str(review.id),
            "review_status": review.status.value,
            "already_analysed": True,
            "detail": str(exc),
            "idempotency_key": idempotency_key,
        })

    return data({
        "review_id": str(run.review_id),
        # Step 30 is the single source of progress (52.7) — no separate job state.
        "review_status": run.review_status,
        "requirements_in_snapshot": run.requirements_in_snapshot,
        "findings_created": run.findings_created,
        # Locked F-1 — coverage, not a gap: nothing was required and nothing found.
        "skipped_as_optional": run.skipped_as_optional,
        "requirements": [
            {
                "requirement_code": outcome.requirement_code,
                "mapping_state": outcome.mapping_state,
                "finding_id": str(outcome.finding_id) if outcome.finding_id else None,
                "classification": outcome.classification,
                "evaluation_count": outcome.evaluation_count,
                "skipped_as_optional": outcome.skipped_as_optional,
                # A configuration failure, never a legal conclusion.
                "failure": outcome.failure,
                # REC-07 — diagnostic metadata only; cannot alter a Finding.
                "diagnostics": outcome.diagnostics,
            }
            for outcome in run.outcomes
        ],
        "idempotency_key": idempotency_key,
    })


@router.get("/reviews/{review_id}/findings")
def list_findings(
    review_id: UUID,
    guard: Guard = Depends(get_guard),
    page: Page = Depends(page_params),
    classification: E.FindingClassification | None = Query(default=None),
    status: E.FindingStatus | None = Query(default=None),
) -> dict:
    """Every item nests its Evaluations.

    49.7 r1 — a Finding's ``classification`` is a derived summary and is never
    returned without them, in a list any more than in a single resource.
    """
    guard.review(review_id, P.FINDING_VIEW)
    stmt = select(M.Finding).where(M.Finding.review_id == review_id)
    if classification is not None:
        stmt = stmt.where(M.Finding.classification == classification)
    if status is not None:
        stmt = stmt.where(M.Finding.status == status)
    rows, total = run(guard.db, stmt, page,
                      M.Finding.created_at, M.Finding.id)
    return paginated(
        [serialize_finding(guard.db, f,
                           legal_position=guard.sees_legal_position)
         for f in rows],
        page=page.page, page_size=page.page_size, total=total)


@router.get("/reviews/{review_id}/report")
def review_report(review_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Reporting-layer aggregation — F-8, F-9, locked 36.10, Step 9.

    Two things are deliberately absent.

    **No risk score or risk label.** Locked 36.10 forbids a risk score as the
    primary V1 legal output, and F-8 makes risk a *configured* display mapping
    owned by the reporting layer and versioned under Step 29. No such mapping is
    configured, and ENG-09 says an absent configuration value fails closed rather
    than defaulting — so the field is omitted rather than invented.

    **No overall verdict.** F-9 makes the alignment figure a ratio over evaluated
    Requirements that "carries no legal meaning and cannot alter a Finding". It is
    reported as counts plus a ratio, and never as a conclusion.
    """
    review = guard.review(review_id, P.REPORT_VIEW)

    findings = guard.db.execute(
        select(M.Finding).where(M.Finding.review_id == review_id)
    ).scalars().all()

    classifications = Counter(f.classification.value for f in findings)
    statuses = Counter(f.status.value for f in findings)

    requirements_in_snapshot = guard.db.execute(
        select(func.count())
        .select_from(M.ConfigurationSnapshotItem)
        .where(M.ConfigurationSnapshotItem.snapshot_id
               == review.configuration_snapshot_id)
    ).scalar_one()

    unmatched = guard.db.execute(
        select(func.count()).select_from(M.UnmatchedProvision)
        .where(M.UnmatchedProvision.review_id == review_id)
    ).scalar_one()

    evaluated = len(findings)
    matched = classifications.get(E.FindingClassification.MATCH.value, 0)

    return data({
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
    })
