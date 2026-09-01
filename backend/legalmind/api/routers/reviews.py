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

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import or_, select

from legalmind.analysis.service import AnalysisNotPermitted
from legalmind.api import ratelimit
from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.reporting import report_payload
from legalmind.api.schemas import ReviewCreate
from legalmind.api.serializers import serialize_finding, serialize_review
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.security.authorization import require_contract_visible
from legalmind.worker.dispatch import DispatchMode, dispatch_analysis

router = APIRouter(tags=["reviews"])

# Module-level so a deployment can swap in the Redis-backed limiter without
# touching a route (see ratelimit.InProcessRateLimiter).
_limiter: ratelimit.RateLimiter = ratelimit.InProcessRateLimiter()


def _visible_reviews(guard: Guard):
    """The list-scope counterpart of ``can_see_review`` (Step 24 r2, r6, `REC-09`).

    These are two implementations of one locked rule, and a test asserts they cannot
    disagree — if the list returned one row a `GET` would 404 on, that is the same
    defect as an IDOR (49.6).

    The third branch is locked `REC-09`'s Legal scope. It is also the **Legal queue**:
    `REC-09` creates no queue resource, because Step 24's "Legal Queue" is named once
    in an example diagram and specified nowhere, so Legal work is found through this
    list under the same scope rule as every other caller.
    """
    assigned = (
        select(M.ReviewAssignment.review_id)
        .where(M.ReviewAssignment.user_id == guard.user_id,
               M.ReviewAssignment.revoked_at.is_(None))
    )
    scopes = [M.Review.created_by == guard.user_id, M.Review.id.in_(assigned)]

    # Permission first, then resource scope — locked Step 24 r12's own ordering. A
    # caller without `legal.review` never widens beyond ownership and assignment.
    if P.LEGAL_REVIEW in guard.permissions:
        escalated = (
            select(M.Finding.review_id)
            .join(M.Escalation, M.Escalation.finding_id == M.Finding.id)
            .where(M.Escalation.withdrawn_at.is_(None))
        )
        scopes.append(M.Review.status == E.ReviewStatus.LEGAL_REVIEW)
        scopes.append(M.Review.id.in_(escalated))

    return select(M.Review).where(or_(*scopes))


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
    response: Response,
    guard: Guard = Depends(get_guard),
    idempotency_key: str | None = Header(default=None, max_length=200),
) -> dict:
    """Submit this Review for analysis — 44.2/44.40, 55.1, 49.8, 49.10.

    **Permission is an interpretation.** Locked 49.3's table has no analysis row,
    though 49.8 and 49.10 both presuppose the endpoint; `review.create` is the
    closest locked grant. Recorded in ``permission_map`` and flagged there.

    **Queued when a broker is configured (55.1), inline when not.** The two modes call
    the same `run_analysis`, so submission mode cannot change a legal outcome — only
    who waits for it. `worker.dispatch` chooses; the caller does not.

    ```text
    202 + mode=queued    a worker will run it; poll GET /reviews/{id} for progress
    201 + mode=inline    it already ran, and the outcome is in this response
    ```

    Progress is the Review lifecycle and nothing else (52.7), which is why the queued
    response carries no job state to poll instead.

    **Idempotency (43.28, 49.8).** A repeat returns the original outcome rather than
    re-running: analysis refuses a Review that already has Findings, and that refusal
    is reported as the already-analysed state, not as an error. Duplicating legal
    output would be the worse failure.
    """
    review = guard.review(review_id, P.REVIEW_CREATE)

    # S-5 / 49.10 — analysis is the expensive path. Keyed per user so one caller
    # cannot exhaust the limit for everyone.
    _limiter.check(f"analysis:{guard.user_id}", ratelimit.ANALYSIS)

    try:
        dispatch = dispatch_analysis(guard.db, review, actor_id=guard.user_id,
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

    if dispatch.mode is DispatchMode.QUEUED:
        # 202: accepted, not complete. Reporting 201 here would claim Findings exist.
        response.status_code = 202
        return data({
            "review_id": str(dispatch.review_id),
            # The Review's *current* lifecycle state — unchanged until a worker picks
            # the job up. Locked Step 30 has no QUEUED state and none is invented.
            "review_status": dispatch.review_status,
            "mode": dispatch.mode.value,
            "task_id": dispatch.task_id,
            "idempotency_key": idempotency_key,
        })

    # INLINE mode always carries a run; `AnalysisDispatch` types it optionally because
    # QUEUED mode genuinely has none. Asserting here states the invariant instead of
    # leaving six unguarded attribute reads for a reader to verify.
    run = dispatch.run
    assert run is not None, "INLINE dispatch must carry an AnalysisRun"
    return data({
        "mode": dispatch.mode.value,
        "review_id": str(run.review_id),
        # Step 30 is the single source of progress (52.7) — no separate job state.
        "review_status": run.review_status,
        "requirements_in_snapshot": run.requirements_in_snapshot,
        "findings_created": run.findings_created,
        # Locked F-1 — coverage, not a gap: nothing was required and nothing found.
        "skipped_as_optional": run.skipped_as_optional,
        # REC-02 / D-4 — a document-level observation, never a Finding.
        "unmatched_provisions": run.unmatched_provisions,
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
    return data(report_payload(guard.db, review))
