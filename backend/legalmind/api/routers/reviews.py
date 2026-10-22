"""Reviews and the review report — locked 49.3, 49.6, 49.8, Step 30.

Review visibility is rooted in the Contract (AB-12): the contract's owner, the
owner's department lead (`department.view`), an active Legal assignment, or
`REC-09` Legal scope — and nothing else, not role name (r12). The list query
below mirrors ``can_see_review`` deliberately, and a test asserts the two cannot
disagree, because a list that leaked one row a ``GET`` would 404 on is the same
defect as an IDOR (49.6).

**There is no endpoint that sets Review status.** Locked Step 30 r3 says users
cannot arbitrarily set it and r16 says summaries are derived; the lifecycle is
advanced by the workflow, not asserted by a caller. The one closing step (r11) follows
from the reviewer's recorded decision on the contract (AM-174), never from a status.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import func, or_, select

from legalmind.analysis.service import AnalysisNotPermitted
from legalmind.api import angles, ratelimit
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.reporting import outcome_payload, report_payload
from legalmind.api.schemas import ContractOutcomeCreate, ReviewAssign, ReviewCreate
from legalmind.api.serializers import serialize_finding, serialize_review
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.authorization import can_read_contract
from legalmind.security.resolver import has_permission
from legalmind.worker.dispatch import DispatchMode, dispatch_analysis
from legalmind.workflow import contract_outcome as CO

router = APIRouter(tags=["reviews"], route_class=CommitBeforeResponse)

# Module-level; in-process by default, the Redis-backed limiter when
# LEGALMIND_RATELIMIT_BACKEND=redis (see ratelimit.limiter_from_env).
_limiter: ratelimit.RateLimiter = ratelimit.limiter_from_env()


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
    # Ownership is the CONTRACT's (AB-12 r5): a transferred deal carries its
    # analysis history to the new owner, and `created_by` stays as history.
    owned = select(M.Contract.id).where(M.Contract.owner_id == guard.user_id)
    scopes = [M.Review.contract_id.in_(owned), M.Review.id.in_(assigned)]

    # Department scope (AB-12 r3): every review of every contract owned by
    # someone in the caller's department. Permission AND a department — a Lead
    # nobody has placed yet widens nothing.
    if guard.sees_department:
        department_contracts = (
            select(M.Contract.id)
            .join(M.User, M.User.id == M.Contract.owner_id)
            .where(M.User.department_id == guard.department_id)
        )
        scopes.append(M.Review.contract_id.in_(department_contracts))

    # Permission first, then resource scope — locked Step 24 r12's own ordering. A
    # caller without `legal.review` never widens beyond ownership and assignment.
    if P.LEGAL_REVIEW in guard.permissions:
        escalated = (
            select(M.Finding.review_id)
            .join(M.Escalation, M.Escalation.finding_id == M.Finding.id)
            .where(M.Escalation.withdrawn_at.is_(None))
        )
        scopes.append(M.Review.status == E.ReviewStatus.LEGAL_REVIEW)
        # AM-174: decided by Legal, awaiting the decision on the contract
        scopes.append((M.Review.status == E.ReviewStatus.RESOLVED) & M.Review.id.in_(
            select(M.Finding.review_id)
            .join(M.LegalDecision, M.LegalDecision.finding_id == M.Finding.id)))
        scopes.append(M.Review.id.in_(escalated))

    return select(M.Review).where(or_(*scopes))


def _with_document(guard: Guard, reviews: list[M.Review]) -> list[dict]:
    """Serialize Reviews with the document identity the caller is entitled to.

    Why this lives here (2026-09-04). Every screen that lists Reviews needs the
    document's NAME, and all three of them used to fetch it client-side with one
    `GET /contracts/{id}` per row. That endpoint is **ownership-scoped**
    (`require_contract_visible`), while THIS list is Review-scoped and includes
    Legal scope (`REC-09`) — so for a `legal.review` holder looking at someone
    else's Review, every one of those fetches 404s. The rows then rendered a
    raw UUID prefix and linked to a workspace that answers "Not found.", while
    the Report link beside them worked perfectly. Reported live: 14 of 20 rows.

    The name is not a new disclosure class: a caller who can see the Review can
    already read this document's verbatim clause text through
    `GET /reviews/{id}/report` (unmatched-provision excerpts). Naming the
    document it came from discloses strictly less than that.

    `document_accessible` is a statement about the CALLER, not the document —
    the same kind of fact `GET /auth/session` already returns as `permissions`,
    and it exists so the UI can stop offering a link it knows will 404 (rule 18:
    presentation only; the server still refuses on its own).

    One query for the page's contracts, so this cannot become an N+1 again.
    """
    contract_ids = {r.contract_id for r in reviews}
    contracts = {} if not contract_ids else {
        c.id: c for c in guard.db.execute(
            select(M.Contract).where(M.Contract.id.in_(contract_ids))
        ).scalars().all()
    }
    # AB-100: which of these the owner sent to THIS caller — their own queue first
    sent = set() if not reviews else set(guard.db.execute(
        select(M.ReviewAssignment.review_id).where(
            M.ReviewAssignment.user_id == guard.user_id,
            M.ReviewAssignment.revoked_at.is_(None),
            M.ReviewAssignment.review_id.in_([r.id for r in reviews]))).scalars())
    # AM-174: each Review's current decision on the contract, one query
    outcomes = {} if not reviews else {
        rid: o.value for rid, o, _ in guard.db.execute(
            select(M.ContractOutcomeRecord.review_id, M.ContractOutcomeRecord.outcome,
                   M.ContractOutcomeRecord.version_number)
            .where(M.ContractOutcomeRecord.review_id.in_([r.id for r in reviews]))
            .order_by(M.ContractOutcomeRecord.version_number))}
    payload = []
    for review in reviews:
        contract = contracts.get(review.contract_id)
        item = serialize_review(review)
        item["document_name"] = contract.name if contract is not None else None
        item["document_type"] = contract.contract_type if contract is not None else None
        # Exactly the rule the workspace this links to will apply — which since
        # the owner's 2026-09-04 ruling is `can_read_contract`: ownership OR
        # `REC-09` Legal scope. The field answers "will this open for YOU", so it
        # has to move with that rule; otherwise the UI would withhold a link that
        # now works, which is what it did for Legal until this changed.
        item["document_accessible"] = bool(
            contract is not None
            and can_read_contract(guard.db, guard.user_id, contract)
        )
        item["sent_to_you"] = review.id in sent
        item["contract_outcome"] = outcomes.get(review.id)
        payload.append(item)
    return payload


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
    return paginated(_with_document(guard, list(rows)),
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
    # 47.6 — reachable only through a Contract the caller OWNS: creating a
    # Review is a write, so department scope does not reach it, and an archived
    # contract refuses it (AB-12 r6).
    guard.contract(version.contract_id, P.REVIEW_CREATE)

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
    review = guard.review(review_id, P.REVIEW_VIEW)
    return data(_with_document(guard, [review])[0])


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
    # Analysis is a write on the contract: owner only, and never on an archived
    # contract (AB-12 r6). A department lead reads the analysis; the owner runs it.
    guard.contract(review.contract_id, P.REVIEW_CREATE)

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


@router.get("/reviews/{review_id}/angles")
def review_angles(review_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The ⚖️ Legal and 💼 Business angles and the counter-proposals (`AM-152`) —
    built by code from the Findings, the document's own figures and the Constitution's
    own drafting language; never generated. Same access as the Findings."""
    review = guard.review(review_id, P.FINDING_VIEW)
    return data(angles.review_angles(guard.db, review,
                                     legal_position=guard.sees_legal_position))


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
    return data(report_payload(guard.db, review,
                               legal_position=guard.sees_legal_position))


# ---- Send for review (owner, 2026-10-21; AB-100) -----------------------------------
# The contract's owner sends its Review to ONE designated reviewer — a person who holds
# both `legal.review` and `legal.decision` (Step 24 r6's assignment, `REC-09`). The owner
# never decides their own points (SEC-01); the reviewer decides, every step audited.
# Same guards as analysis: visible and owned (else the one 404), not archived (409).
def _reviewer(user: M.User) -> dict:
    return {"user_id": str(user.id), "name": user.name, "email": user.email}


def _eligible(db) -> list[M.User]:
    users = db.execute(select(M.User).where(M.User.status == E.UserStatus.ACTIVE)
                       .order_by(M.User.name, M.User.email)).scalars()
    return [u for u in users if has_permission(db, u.id, P.LEGAL_REVIEW)
            and has_permission(db, u.id, P.LEGAL_DECISION)]


def _assignments(db, review_id: UUID) -> list[dict]:
    rows = db.execute(
        select(M.ReviewAssignment, M.User)
        .join(M.User, M.User.id == M.ReviewAssignment.user_id)
        .where(M.ReviewAssignment.review_id == review_id,
               M.ReviewAssignment.revoked_at.is_(None))
        .order_by(M.ReviewAssignment.created_at)).all()
    return [{**_reviewer(user), "assigned_by": str(a.assigned_by),
             "assigned_at": a.created_at.isoformat()} for a, user in rows]


@router.get("/reviews/{review_id}/assignments")
def review_assignments(review_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Who has this Review now — for anyone who may see it; and, for its owner only,
    the people it may be sent to."""
    review = guard.review(review_id, P.REVIEW_VIEW)
    contract = guard.db.get(M.Contract, review.contract_id)
    owner = contract is not None and contract.owner_id == guard.user_id
    archived = contract is not None and contract.archived_at is not None
    return data({"assigned": _assignments(guard.db, review.id),
                 # whether this caller may send or withdraw (the owner, not archived)
                 "can_send": owner and not archived,
                 "eligible": ([_reviewer(u) for u in _eligible(guard.db)
                               if u.id != guard.user_id] if owner else [])})


@router.post("/reviews/{review_id}/assignments", status_code=201)
def assign_review(review_id: UUID, body: ReviewAssign,
                  guard: Guard = Depends(get_guard)) -> dict:
    review = guard.review(review_id, P.REVIEW_CREATE)
    guard.contract(review.contract_id, P.REVIEW_CREATE)      # owner only; 409 archived
    db = guard.db
    reviewer = db.get(M.User, body.user_id)
    if reviewer is None or reviewer.id not in {u.id for u in _eligible(db)}:
        raise BusinessRuleRejected("the person must hold the Legal Reviewer and Legal "
                                   "Decision Authority roles")
    if reviewer.id == guard.user_id:
        raise BusinessRuleRejected("a contract's owner never decides its own points")
    row = db.execute(select(M.ReviewAssignment).where(
        M.ReviewAssignment.review_id == review.id,
        M.ReviewAssignment.user_id == reviewer.id)).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        raise Conflict("already sent to this person")
    if row is None:
        row = M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                                 assigned_by=guard.user_id)
        db.add(row)
    else:                                   # sent again after a withdrawal
        row.revoked_at, row.assigned_by = None, guard.user_id
    db.flush()
    A.record(db, action=A.REVIEW_ASSIGNED, entity_type="review", entity_id=review.id,
             actor_id=guard.user_id, request_id=guard.request_id,
             after={"assigned_to": str(reviewer.id),
                    "contract_id": str(review.contract_id)})
    return data({"assigned": _assignments(db, review.id)})


@router.delete("/reviews/{review_id}/assignments/{user_id}")
def withdraw_review(review_id: UUID, user_id: UUID,
                    guard: Guard = Depends(get_guard)) -> dict:
    review = guard.review(review_id, P.REVIEW_CREATE)
    guard.contract(review.contract_id, P.REVIEW_CREATE)
    db = guard.db
    row = db.execute(select(M.ReviewAssignment).where(
        M.ReviewAssignment.review_id == review.id, M.ReviewAssignment.user_id == user_id,
        M.ReviewAssignment.revoked_at.is_(None))).scalar_one_or_none()
    if row is None:
        raise Conflict("this Review is not with that person")
    row.revoked_at = func.now()
    db.flush()
    A.record(db, action=A.REVIEW_ASSIGNMENT_WITHDRAWN, entity_type="review",
             entity_id=review.id, actor_id=guard.user_id, request_id=guard.request_id,
             after={"withdrawn_from": str(user_id)})
    return data({"assigned": _assignments(db, review.id)})


# ---- The decision on the whole contract (owner, 2026-10-22; AM-174) ----------------
@router.get("/reviews/{review_id}/outcome")
def review_outcome(review_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    review = guard.review(review_id, P.REVIEW_VIEW)
    return data(outcome_payload(guard.db, review))


@router.post("/reviews/{review_id}/outcome", status_code=201)
def record_outcome(review_id: UUID, body: ContractOutcomeCreate,
                   guard: Guard = Depends(get_guard)) -> dict:
    review = guard.review(review_id, P.LEGAL_DECISION)
    CO.record(guard.db, review, actor_id=guard.user_id, outcome=body.outcome,
              justification=body.justification, expected_version=body.expected_version,
              request_id=guard.request_id)
    return data({**outcome_payload(guard.db, review),
                 "review_status": review.status.value})
