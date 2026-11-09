"""Contracts and document upload — locked 49.3, 41.24, Step 34; scoped by AB-12.

Two read scopes and one write scope (AB-12):

```text
scope=own          my contracts                          every Department User
scope=department   every contract owned by someone in    `department.view` — the
                   my department, mine included          Department Lead
writes             my contracts only                     everyone, always
```

A list returns only what a ``GET /{id}`` would return, and a ``GET /{id}`` for a
contract outside the caller's scope is a 404, never a 403 — existence is itself
a disclosure (47.7). Archived contracts (AB-12 r6) leave the default lists,
stay readable by id, and refuse every write with 409.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import Select, event, false, func, or_, select
from sqlalchemy.exc import DBAPIError
from starlette.concurrency import run_in_threadpool

from legalmind.analysis import negotiation
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.routers import execution
from legalmind.api.routers.amendments import refusal, relations
from legalmind.api.schemas import (
    ContractCreate,
    ContractTransfer,
    ContractUpdate,
    clean_name,
)
from legalmind.api.serializers import (
    declared_metadata,
    serialize_contract,
    serialize_document_version,
)
from legalmind.api.storage import get_storage
from legalmind.config import max_upload_bytes
from legalmind.db import models as M
from legalmind.domain import deal_stage as DS
from legalmind.domain import enums as E
from legalmind.domain.client_profile import FINAL_SIGNED
from legalmind.drafting import blank
from legalmind.evaluation.user_status import folded_user_status_counts
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.authorization import (
    DEPARTMENT,
    OWNER,
    contract_read_basis,
)
from legalmind.security.errors import Forbidden, NotVisible
from legalmind.worker.dispatch import dispatch_indexing, dispatch_ocr

router = APIRouter(tags=["contracts"], route_class=CommitBeforeResponse)


#: Implementation addition (2026-09-01, owner-directed Documents redesign): the
#: four states the list/summary UI needs, computed from data the row already
#: carries — never a new lifecycle enum (rule 3), never a new Finding
#: Classification (REC-02's own boundary). Fully derived from
#: `latest_version.processing_status`, `latest_analysis.review_status` and
#: `latest_analysis.classification_counts`, which is exactly what
#: `analysisCell`/`rowNeedsAttention` already derive client-side — this is the
#: SAME rule, computed once, server-side, so list filtering/sorting and the
#: summary tiles can never disagree with each other or with the row itself.
_IN_FLIGHT_REVIEW_STATUSES = {"DRAFT", "UPLOADED", "PROCESSING"}
#: QA-005 (2026-10-29): an analysis that never finished has no counts, which read as
#: "No issues". It needs a person, never a green tick (rule 15).
UNFINISHED_REVIEW_STATUSES = {"ANALYSIS_FAILED", "CANCELLED"}
STATUS_BUCKETS = ("draft", "analyzing", "needs_attention", "analyzed")


def _status_bucket(item: dict, stage: str | None = None) -> str:
    # `AM-298`: a signed deal waits on nobody; nor does a Final one (`AM-318`)
    if stage in (DS.NegotiationStage.SIGNED, DS.NegotiationStage.FINAL):
        return "analyzed"
    version = item.get("latest_version")
    if version is None or version.get("processing_status") != "COMPLETED":
        return "draft"
    analysis = item.get("latest_analysis")
    if analysis is None:
        return "draft"
    if analysis.get("review_status") in _IN_FLIGHT_REVIEW_STATUSES:
        return "analyzing"
    if analysis.get("review_status") in UNFINISHED_REVIEW_STATUSES:
        return "needs_attention"
    counts = analysis.get("user_status_counts") or {}
    if any(n > 0 for status, n in counts.items() if status != "ACCEPTABLE"):
        return "needs_attention"
    return "analyzed"


SCOPES = ("own", "department", "legal")


def _scoped_contracts(guard: Guard, scope: str, *, archived: bool) -> Select:
    """The list-side statement of the same rule `contract_read_basis` applies by
    id (49.6: a list never leaks a row a GET would 404 on).

    ``own`` is ownership. ``department`` (AB-12 r3) is every contract whose owner
    is in the caller's department — it needs `department.view` (403 without) AND
    a department to be scoped to: a Lead nobody has placed yet matches nothing,
    never everything. ``legal`` (AM-288) is what a Legal reviewer may read: its own
    and every contract sent to Legal, assigned to them or created by them.
    """
    if scope not in SCOPES:
        raise BusinessRuleRejected(f"unknown scope {scope!r}; expected one of {SCOPES}")
    if scope == "legal":
        # AM-288 r1/r3 — what Legal may read: its own, plus every contract a GET would
        # open on a Legal basis (assigned, created, or a Review in Legal scope). The
        # same branches as `contract_read_basis`, in SQL; never a global read.
        guard.permission(P.LEGAL_REVIEW)
        me = guard.user_id
        first_upload = (select(M.DocumentVersion.uploaded_by)
                        .where(M.DocumentVersion.contract_id == M.Contract.id)
                        .order_by(M.DocumentVersion.version_number).limit(1)
                        .correlate(M.Contract).scalar_subquery())
        assigned = (select(M.Review.contract_id)
                    .join(M.ReviewAssignment, M.ReviewAssignment.review_id == M.Review.id)
                    .where(M.ReviewAssignment.user_id == me,
                           M.ReviewAssignment.revoked_at.is_(None)))
        escalated = (select(M.Review.contract_id)
                     .join(M.Finding, M.Finding.review_id == M.Review.id)
                     .join(M.Escalation, M.Escalation.finding_id == M.Finding.id)
                     .where(M.Escalation.withdrawn_at.is_(None)))
        decided = (select(M.Review.contract_id)
                   .join(M.Finding, M.Finding.review_id == M.Review.id)
                   .join(M.LegalDecision, M.LegalDecision.finding_id == M.Finding.id)
                   .where(M.Review.status == E.ReviewStatus.RESOLVED))
        in_review = select(M.Review.contract_id).where(
            M.Review.status == E.ReviewStatus.LEGAL_REVIEW)
        stmt = select(M.Contract).where(or_(
            M.Contract.owner_id == me, first_upload == me,
            M.Contract.id.in_(assigned), M.Contract.id.in_(escalated),
            M.Contract.id.in_(decided), M.Contract.id.in_(in_review)))
    elif scope == "department":
        guard.permission(P.DEPARTMENT_VIEW)
        if guard.department_id is None:
            stmt = select(M.Contract).where(false())
        else:
            stmt = (select(M.Contract)
                    .join(M.User, M.User.id == M.Contract.owner_id)
                    .where(M.User.department_id == guard.department_id))
    else:
        stmt = select(M.Contract).where(M.Contract.owner_id == guard.user_id)
    return stmt.where(M.Contract.archived_at.is_not(None) if archived
                      else M.Contract.archived_at.is_(None))


def _owner_names(guard: Guard, contracts: list[M.Contract]) -> dict[UUID, str]:
    """Whose deal each row is — needed the moment a list can hold more than
    the caller's own. One query for the page; a colleague's display name is
    already visible through the department members list, so nothing new is
    disclosed."""
    owner_ids = {c.owner_id for c in contracts}
    if not owner_ids:
        return {}
    rows = guard.db.execute(
        select(M.User.id, M.User.name).where(M.User.id.in_(owner_ids))).all()
    return {row[0]: row[1] for row in rows}


@router.get("/contracts")
def list_contracts(
    guard: Guard = Depends(get_guard),
    page: Page = Depends(page_params),
    q: str | None = Query(default=None, max_length=500),
    contract_type: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None),
    sort: str = Query(default="created_desc"),
    scope: str = Query(default="own"),
    archived: bool = Query(default=False),
    counterparty_id: str | None = Query(default=None, max_length=64),
    stage: str | None = Query(default=None),
) -> dict:
    """49.6 — the same object-level scope as ``GET /contracts/{id}``.

    ``q``/``contract_type``/``sort`` filter and order in SQL. ``status`` is a
    DERIVED bucket (`_status_bucket`) that does not exist as a contracts-table
    column, so it cannot be pushed into the same ``WHERE`` — the scoped set is
    bounded (one account's, or one department's, never a global scan), so it is
    computed once over every matching id and paginated in Python, exactly the
    precedent `_list_summaries` already set for the per-row projection.

    ``archived=true`` lists ONLY archived contracts (AB-12 r6) — the shelf, kept
    apart from the working list rather than mixed into it.

    ``counterparty_id`` narrows to one client, and the literal ``none`` narrows
    to the contracts linked to NO client (2026-09-10, Client Profiles): that is
    what the "link an existing document to this client" picker offers, so a
    document already in LegalMind never has to be uploaded a second time just
    because Client Profiles arrived. It only ever narrows the caller's own
    scoped set — never a way to reach another owner's paper.
    """
    guard.permission(P.CONTRACT_VIEW)
    stmt = _scoped_contracts(guard, scope, archived=archived)
    if q:
        stmt = stmt.where(M.Contract.name.ilike(f"%{q.strip()}%"))
    if contract_type:
        stmt = stmt.where(M.Contract.contract_type == contract_type)
    if counterparty_id == "none":
        stmt = stmt.where(M.Contract.counterparty_id.is_(None))
    elif counterparty_id:
        try:
            stmt = stmt.where(M.Contract.counterparty_id == UUID(counterparty_id))
        except ValueError:
            raise BusinessRuleRejected(
                "counterparty_id must be a UUID or the literal 'none'") from None

    order = {
        "created_desc": (M.Contract.created_at.desc(), M.Contract.id.desc()),
        "created_asc": (M.Contract.created_at.asc(), M.Contract.id.asc()),
        "name_asc": (M.Contract.name.asc(), M.Contract.id.asc()),
        "name_desc": (M.Contract.name.desc(), M.Contract.id.desc()),
    }.get(sort, (M.Contract.created_at.desc(), M.Contract.id.desc()))

    if status not in (None, *STATUS_BUCKETS):
        raise BusinessRuleRejected(
            f"unknown status filter {status!r}; expected one of {STATUS_BUCKETS}")

    if stage not in (None, *DS.NEGOTIATION_STAGES):
        raise BusinessRuleRejected(
            f"unknown stage filter {stage!r}; expected one of {DS.NEGOTIATION_STAGES}")

    if status is None and stage is None:
        rows, total = run(guard.db, stmt, page, *order)
        summaries = _list_summaries(guard, [c.id for c in rows])
        stages = negotiation_stages(guard, list(rows))
    else:
        # The bucket and the stage depend on data no contracts-table WHERE can
        # reach, so filter-then-paginate rather than paginate-then-filter.
        all_rows = guard.db.execute(stmt.order_by(*order)).scalars().all()
        summaries = _list_summaries(guard, [c.id for c in all_rows])
        stages = negotiation_stages(guard, list(all_rows))
        matched = [c for c in all_rows
                   if status in (None, _status_bucket(summaries.get(c.id, {}),
                                                      stages.get(c.id, {}).get("stage")))
                   and stage in (None, stages.get(c.id, {}).get("stage"))]
        total = len(matched)
        start = (page.page - 1) * page.page_size
        rows = matched[start:start + page.page_size]

    owner_names = _owner_names(guard, list(rows))
    counts = _deal_counts(guard, list(rows))
    payload = []
    for c in rows:
        item = serialize_contract(c)
        item["owner_name"] = owner_names.get(c.owner_id)
        item.update(summaries.get(c.id, {"latest_version": None,
                                         "latest_analysis": None}))
        if c.id in stages:
            item["negotiation_stage"] = stages[c.id]
        item["counts"] = counts[c.id]
        payload.append(item)
    return paginated(payload,
                     page=page.page, page_size=page.page_size, total=total)


@router.get("/contracts/summary")
def contracts_summary(guard: Guard = Depends(get_guard),
                      scope: str = Query(default="own")) -> dict:
    """The Dashboard's stat tiles — real counts across EVERY contract in the
    caller's chosen scope, not just the current page (49.6 scope; additive, no
    locked row). One aggregation, computed the same way each row's own status
    is (`_status_bucket`), so a tile and a row can never disagree.
    """
    guard.permission(P.CONTRACT_VIEW)
    contracts = guard.db.execute(
        _scoped_contracts(guard, scope, archived=False)).scalars().all()
    ids = [c.id for c in contracts]
    summaries = _list_summaries(guard, ids)
    stages = negotiation_stages(guard, list(contracts))
    tally = dict.fromkeys(STATUS_BUCKETS, 0)
    for cid in ids:
        stage = stages.get(cid, {}).get("stage")
        tally[_status_bucket(summaries.get(cid, {}), stage)] += 1
    stage_tally = dict.fromkeys(DS.NEGOTIATION_STAGES, 0)
    for item in stages.values():
        stage_tally[item["stage"]] += 1
    return data({
        # AM-260 — the Contracts stage tiles; omitted without `document.view`
        **({"stages": stage_tally} if P.DOCUMENT_VIEW in guard.permissions else {}),
        "total": len(ids),
        "draft": tally["draft"],
        "analyzing": tally["analyzing"],
        "needs_attention": tally["needs_attention"],
        "analyzed": tally["analyzed"],
    })


def _list_summaries(guard: Guard, contract_ids: list[UUID]) -> dict[UUID, dict]:
    """Per-row `latest_version` / `latest_analysis` for the Documents list —
    2026-08-31 UX correction (Step 49 implementation addition, the #187
    precedent): the list answers "what did analysis find" instead of echoing a
    lifecycle enum. Three page-bounded grouped queries; no N+1.

    Permission-layered like every projection: version metadata needs
    `document.view`; the analysis block needs `review.view`; the
    classification counts inside it additionally need `finding.view` and are
    OMITTED (never nulled) without it — Step 24 r8's rule applied here.
    """
    if not contract_ids or P.DOCUMENT_VIEW not in guard.permissions:
        return {}
    versions = guard.db.execute(
        select(M.DocumentVersion)
        .where(M.DocumentVersion.contract_id.in_(contract_ids))
        .order_by(M.DocumentVersion.contract_id,
                  M.DocumentVersion.version_number.desc())
    ).scalars().all()
    latest_version: dict[UUID, M.DocumentVersion] = {}
    for version in versions:
        latest_version.setdefault(version.contract_id, version)

    out: dict[UUID, dict] = {}
    for cid, version in latest_version.items():
        out[cid] = {"latest_version": {
            "id": str(version.id),
            "version_number": version.version_number,
            "processing_status": version.processing_status.value,
            # when THIS version was uploaded — what a picker dates and orders by,
            # not when the contract was first created (review, 2026-10-21)
            "created_at": version.created_at.isoformat() if version.created_at else None,
            # Declared source / counterparty / effective date (2026-09-06), so
            # the edit dialog can show them and the intake's counterparty
            # datalist can converge on names the caller ALREADY sees in this
            # list — no separate "all counterparties" endpoint, which would
            # disclose names across owners. Same `document.view` gate as the
            # version itself; omitted when undeclared.
            **declared_metadata(version),
        }, "latest_analysis": None}

    if P.REVIEW_VIEW not in guard.permissions or not latest_version:
        return out
    reviews = guard.db.execute(
        select(M.Review)
        .where(M.Review.document_version_id.in_(
            [v.id for v in latest_version.values()]))
        .order_by(M.Review.document_version_id,
                  M.Review.created_at.desc(), M.Review.id.desc())
    ).scalars().all()
    latest_review: dict[UUID, M.Review] = {}
    for r in reviews:
        latest_review.setdefault(r.document_version_id, r)

    counts: dict[UUID, dict[str, int]] = {}
    if latest_review and P.FINDING_VIEW in guard.permissions:
        grouped = guard.db.execute(
            select(M.Finding.review_id, M.Finding.classification, func.count())
            .where(M.Finding.review_id.in_([r.id for r in latest_review.values()]))
            .group_by(M.Finding.review_id, M.Finding.classification)
        ).all()
        for review_id, classification, n in grouped:
            counts.setdefault(review_id, {})[classification.value] = n
        folded = folded_user_status_counts(
            guard.db, [r.id for r in latest_review.values()],
            legal_position=guard.sees_legal_position)
    else:
        folded = {}

    for cid, version in latest_version.items():
        review = latest_review.get(version.id)
        if review is None:
            continue
        analysis = {
            "review_id": str(review.id),
            "review_status": review.status.value,
            "created_at": (review.created_at.isoformat()
                           if review.created_at else None),
            "completed_at": (review.completed_at.isoformat()
                             if review.completed_at else None),
        }
        if P.FINDING_VIEW in guard.permissions:
            analysis["classification_counts"] = counts.get(review.id, {})
            analysis["user_status_counts"] = folded.get(review.id, {})
        out[cid]["latest_analysis"] = analysis
    return out


def negotiation_stages(guard: Guard, contracts: list[M.Contract]) -> dict[UUID, dict]:
    """`AM-260` — each contract's derived stage (`domain.deal_stage`), batched.

    Layered like `_list_summaries`: versions need `document.view` (omitted without it);
    the review and contract-decision facts need `review.view`, and without it the stage
    is derived from the versions alone."""
    if not contracts or P.DOCUMENT_VIEW not in guard.permissions:
        return {}
    db = guard.db
    versions: dict[UUID, list[DS.VersionFacts]] = {}
    latest_id: dict[UUID, tuple[int, UUID]] = {}
    # a signed copy ever named on the execution record (a replaced wrong copy too) is
    # not the agreed text's successor: the stage reads past it until "Mark signed"
    # makes the current one FINAL_SIGNED (AM-297; `execution.agreed` reads the same)
    copies = execution.signed_copy_ids(db, [c.id for c in contracts])
    for v in db.execute(select(M.DocumentVersion).where(
            M.DocumentVersion.contract_id.in_([c.id for c in contracts]))).scalars():
        role = (v.doc_metadata or {}).get("version_role")
        if v.id in copies and role != FINAL_SIGNED:
            continue
        versions.setdefault(v.contract_id, []).append(DS.VersionFacts(
            v.version_number, v.created_at, role,
            v.sent_at, bool(negotiation.answers(v.doc_metadata)),
            bool(negotiation.final_of(v.doc_metadata))))
        if v.version_number > latest_id.get(v.contract_id, (-1, v.id))[0]:
            latest_id[v.contract_id] = (v.version_number, v.id)

    facts: dict[UUID, DS.ReviewFacts] = {}
    if P.REVIEW_VIEW in guard.permissions and latest_id:
        by_version = {vid: cid for cid, (_, vid) in latest_id.items()}
        latest_review: dict[UUID, M.Review] = {}
        for r in db.execute(select(M.Review).where(
                M.Review.document_version_id.in_(by_version))
                .order_by(M.Review.created_at.desc(), M.Review.id.desc())).scalars():
            latest_review.setdefault(by_version[r.document_version_id], r)
        rids = [r.id for r in latest_review.values()]
        assigned: dict[UUID, datetime] = dict(db.execute(
            select(M.ReviewAssignment.review_id, func.min(M.ReviewAssignment.created_at))
            .where(M.ReviewAssignment.review_id.in_(rids),
                   M.ReviewAssignment.revoked_at.is_(None))
            .group_by(M.ReviewAssignment.review_id)).tuples().all())
        outcome: dict[UUID, M.ContractOutcomeRecord] = {}
        for rec in db.execute(select(M.ContractOutcomeRecord)
                              .where(M.ContractOutcomeRecord.review_id.in_(rids))
                              .order_by(M.ContractOutcomeRecord.version_number.desc())
                              ).scalars():
            outcome.setdefault(rec.review_id, rec)
        # AM-293 r1: a review with an undecided point — our reply then cannot leave
        undecided = set(db.execute(select(M.Finding.review_id).where(
            M.Finding.review_id.in_(rids),
            M.Finding.status.in_(negotiation._UNDECIDED))).scalars())
        for cid, r in latest_review.items():
            since = assigned.get(r.id)          # "Send for review" (AM-167), as AM-179
            o = outcome.get(r.id)
            if o is not None and r.reopened_at and r.reopened_at > o.created_at:
                o = None                                  # AM-175: reopened since
            facts[cid] = DS.ReviewFacts(in_review_since=since,
                                        outcome=o.outcome.value if o else None,
                                        outcome_at=o.created_at if o else None,
                                        reply_cleared=(r.status in negotiation._ANALYSED
                                                       and r.id not in undecided))
    now = datetime.now(UTC)
    return {c.id: DS.stage_payload(*DS.derive_stage(
        c.created_at, versions.get(c.id, []), facts.get(c.id)), now) for c in contracts}


def _deal_counts(guard: Guard, contracts: list[M.Contract]) -> dict[UUID, dict]:
    """`AM-291` — the one `counts` object (`negotiation.deal_counts`)."""
    from legalmind.api.routers.negotiation import deal_counts  # circular at import

    return deal_counts(guard, contracts)


def _require_linkable(guard: Guard, counterparty_id: UUID) -> None:
    """A contract may point only at a counterparty this caller can already see.
    Linking is how visibility is GRANTED (AB-13 r6), so an existence check alone
    let anyone pull another department's client into their own scope. Unknown
    and out-of-scope give the same refusal, so this is no existence oracle."""
    from legalmind.api.routers.counterparties import _readable  # circular at import

    try:
        _readable(guard, counterparty_id)
    except NotVisible:
        raise BusinessRuleRejected("unknown counterparty") from None


@router.post("/contracts", status_code=201)
def create_contract(body: ContractCreate,
                    guard: Guard = Depends(get_guard)) -> dict:
    """`counterparty_id` is optional and new on 2026-09-10 (Client Profiles).

    It exists so an upload begun from a client profile lands linked in ONE
    call. Create-then-patch instead would leave an orphan contract behind every
    time the second call failed — the document would then be in LegalMind but
    not on the client's page, which is the one outcome this feature exists to
    prevent. Same AB-13 r2 rule as on update: an unknown id is refused rather
    than stored, `contract.update` is additionally required (naming who a deal
    is with is maintaining it, r5), and the link is audited, because the "show
    me everything for this company" view is derived entirely from it.
    """
    guard.permission(P.CONTRACT_CREATE)
    if body.counterparty_id is not None:
        guard.permission(P.CONTRACT_UPDATE)
        _require_linkable(guard, body.counterparty_id)
    contract = M.Contract(owner_id=guard.user_id, name=body.name,
                          contract_type=body.contract_type,
                          counterparty_id=body.counterparty_id,
                          issuing_entity=body.issuing_entity,
                          status=E.ContractStatus.DRAFT)
    guard.db.add(contract)
    guard.db.flush()
    audit.record(guard.db, action=audit.CONTRACT_CREATED, entity_type="contract",
                 entity_id=contract.id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"name": contract.name, "issuing_entity": contract.issuing_entity})
    if body.counterparty_id is not None:
        audit.record(
            guard.db, action=audit.CONTRACT_COUNTERPARTY_LINKED,
            entity_type="contract", entity_id=contract.id,
            actor_id=guard.user_id, request_id=guard.request_id,
            before={"counterparty_id": None},
            after={"counterparty_id": str(body.counterparty_id)},
        )
    return data(serialize_contract(contract))


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The contract with its document versions, newest first.

    `document_versions` is an implementation addition (2026-08-30, UI phase): a
    document-anchored workspace opened on a contract must be able to find its
    document through the API, and nothing listed versions — the legacy screen only
    ever showed the version it had just uploaded. Additive, same permission the
    contract already required (a version is reachable only through a contract the
    caller can see — 47.6 one level down), and the summary is the existing
    `serialize_document_version` shape, so nothing new is disclosed. Recorded in
    Step 49's implementation-additions section.
    """
    # Read scope: owner, department (AB-12 r3), or `REC-09` Legal scope.
    contract = guard.contract_readable(contract_id, P.CONTRACT_VIEW)
    versions = guard.db.execute(
        select(M.DocumentVersion)
        .where(M.DocumentVersion.contract_id == contract.id)
        .order_by(M.DocumentVersion.version_number.desc(), M.DocumentVersion.id.desc())
    ).scalars().all()
    payload = serialize_contract(contract)
    payload["owner_name"] = _owner_names(guard, [contract]).get(contract.owner_id)
    payload["document_versions"] = [serialize_document_version(v) for v in versions]
    if len(versions) == 1:
        # AM-302: one version made from our blank template opens on its Changes, which
        # compare it with that template (the link is read from its own text)
        link = blank.link(guard.db, contract, versions[0])
        if link is not None:
            payload["document_versions"][0]["made_from_template"] = link["said"]
    stage = negotiation_stages(guard, [contract]).get(contract.id)
    if stage is not None:
        payload["negotiation_stage"] = stage
    payload["counts"] = _deal_counts(guard, [contract])[contract.id]
    # AM-316: the published template it was generated from (omitted for an upload)
    made = guard.db.execute(
        select(M.TemplateVersion).join(
            M.ContractDraft, M.ContractDraft.template_version_id == M.TemplateVersion.id)
        .where(M.ContractDraft.contract_id == contract.id)
        .order_by(M.ContractDraft.created_at).limit(1)).scalar_one_or_none()
    if made is not None:
        def named(tv: M.TemplateVersion) -> str | None:
            return ((tv.source or {}).get("catalogue") or {}).get("name")
        # template re-check #3: a version with no name of its own takes the newest name
        # recorded for the same template, never the generic one
        name = named(made) or next((n for tv in guard.db.execute(
            select(M.TemplateVersion).where(
                M.TemplateVersion.template_key == made.template_key)
            .order_by(M.TemplateVersion.version.desc())).scalars()
            if (n := named(tv))), None)
        payload["made_from"] = {
            "template_key": made.template_key, "version": made.version,
            "doc_type": made.doc_type, "brand": made.brand, "name": name,
            # template re-check #4: withdrawn since — information only, blocks nothing
            **({"withdrawn": True} if made.status == "RETIRED" else {})}
    # AM-309: the signed contract it amends and its amendments — readable ones only
    payload.update(relations(guard, contract))
    return data(payload)


@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: UUID, body: ContractUpdate,
                    guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract(contract_id, P.CONTRACT_UPDATE)
    try:
        # AM-309: the governed-by trigger refuses an amendment's type or client moving,
        # or a parent's while it has amendments — said as 409, never a 500
        with guard.db.begin_nested():
            _apply_update(guard, contract_id, contract, body)
    except DBAPIError as exc:
        raise Conflict(refusal(exc)) from exc
    return data(serialize_contract(contract))


def _apply_update(guard: Guard, contract_id: UUID, contract: M.Contract,
                  body: ContractUpdate) -> None:
    if body.name is not None:
        contract.name = body.name
    if body.contract_type is not None and body.contract_type != contract.contract_type:
        # AM-50 (2026-09-09): the type is still recorded only through this
        # ordinary update, and the trail says WHO determined it — the reader, or
        # the intake applying a confident suggestion. Since AM-51 the type is one
        # optional applicability signal, never a gate; since AM-61 every
        # requirement it did or did not bring in is recorded with its reason.
        # AM-51 r5's "a type change re-runs the analysis" is NOT implemented
        # here: an already-analysed Review refuses re-analysis (43.28) and a new
        # Review on the same version + snapshot + creator is the SAME Review
        # under 49.8's idempotency key — see CONFLICTS.md C-21 for the amendment
        # that would be needed. A reader re-analyses by uploading a new version.
        before_type = {"contract_type": contract.contract_type}
        contract.contract_type = body.contract_type
        audit.record(
            guard.db, action=audit.CONTRACT_TYPE_DECLARED,
            entity_type="contract", entity_id=contract_id,
            actor_id=guard.user_id, request_id=guard.request_id,
            before=before_type,
            after={"contract_type": body.contract_type,
                   "source": body.contract_type_source or "HUMAN"},
        )
    if body.status is not None and body.status != contract.status:
        # P-1 (2026-09-06): the lifecycle state is DECLARED by the owner — Step 2's
        # Draft / Active / Superseded — never inferred from a date or a version,
        # and every change is on the audit trail (AUD-01). No transition is
        # forbidden: a wrong click must be correctable, and the trail says who
        # changed what and when. Same permission and owner scope as any edit.
        before = {"status": contract.status.value}
        contract.status = body.status
        audit.record(
            guard.db, action=audit.CONTRACT_STATUS_CHANGED,
            entity_type="contract", entity_id=contract_id,
            actor_id=guard.user_id, request_id=guard.request_id,
            before=before, after={"status": contract.status.value},
        )
    if "issuing_entity" in body.model_fields_set \
            and body.issuing_entity != contract.issuing_entity:
        # AM-287 r1 — chosen by a person, audited
        audit.record(guard.db, action=audit.CONTRACT_ISSUING_ENTITY_SET,
                     entity_type="contract", entity_id=contract_id,
                     actor_id=guard.user_id, request_id=guard.request_id,
                     before={"issuing_entity": contract.issuing_entity},
                     after={"issuing_entity": body.issuing_entity})
        contract.issuing_entity = body.issuing_entity
    if "counterparty_id" in body.model_fields_set:
        # AB-13 r2 — who this deal is with. A nonexistent id is refused rather
        # than stored: a dangling link is worse than no link. Sent as null it
        # unlinks. Audited either way (r8), because this is the fact the whole
        # "show me everything for this company" view is derived from.
        target = body.counterparty_id
        if target is not None:
            _require_linkable(guard, target)
        if target != contract.counterparty_id:
            before_link = {"counterparty_id": (str(contract.counterparty_id)
                                               if contract.counterparty_id else None)}
            contract.counterparty_id = target
            audit.record(
                guard.db, action=audit.CONTRACT_COUNTERPARTY_LINKED,
                entity_type="contract", entity_id=contract_id,
                actor_id=guard.user_id, request_id=guard.request_id,
                before=before_link,
                after={"counterparty_id": str(target) if target else None},
            )
    contract.updated_at = datetime.now(UTC)
    guard.db.flush()


@router.post("/contracts/{contract_id}/archive")
def archive_contract(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Put a contract on the shelf — AB-12 r6, replacing AM-37's two-mode delete.

    Nothing is destroyed. The document, every version, the evidence, the
    reviews, findings, decisions, Ask citations and the audit trail all stay
    exactly where they are, so "what did LegalMind know about this contract at
    that point in time?" stays answerable for as long as the database exists.
    What changes: the contract leaves the working lists, every write to it is
    refused with 409, and it stays readable by its owner and department lead.

    Owner-scoped like every write; `guard.contract` also refuses a contract
    that is already archived, so archiving twice is a 409 rather than a silent
    no-op that would hide the second actor from the trail.
    """
    contract = guard.contract(contract_id, P.CONTRACT_ARCHIVE)
    before = serialize_contract(contract)
    contract.archived_at = datetime.now(UTC)
    contract.updated_at = contract.archived_at
    guard.db.flush()
    audit.record(
        guard.db, action=audit.CONTRACT_ARCHIVED,
        entity_type="contract", entity_id=contract_id,
        actor_id=guard.user_id, request_id=guard.request_id, before=before,
        after={"archived_at": contract.archived_at.isoformat()},
    )
    return data(serialize_contract(contract))


@router.post("/contracts/{contract_id}/restore")
def restore_contract(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The mirror of archive — same permission, same owner scope, audited."""
    contract = guard.contract(contract_id, P.CONTRACT_ARCHIVE, allow_archived=True)
    if contract.archived_at is None:
        raise Conflict("this contract is not archived")
    before = serialize_contract(contract)
    contract.archived_at = None
    contract.updated_at = datetime.now(UTC)
    guard.db.flush()
    audit.record(
        guard.db, action=audit.CONTRACT_RESTORED,
        entity_type="contract", entity_id=contract_id,
        actor_id=guard.user_id, request_id=guard.request_id, before=before,
        after={"archived_at": None},
    )
    return data(serialize_contract(contract))


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(contract_id: UUID, guard: Guard = Depends(get_guard)) -> None:
    """Genuinely destroy a contract — AM-55, beside Archive, not instead of it.

    Owner's explicit choice, made after the tradeoff was named: unlike Archive,
    this reaches an analyzed contract too, and its Reviews, Findings,
    Evaluations, Legal Decisions and evidence go with it (DB-level
    `ON DELETE CASCADE` on the whole subtree — see migration
    a1b2c3d4e5f6). Rule 17 (historical Reviews stay reproducible) no longer
    holds for what gets deleted here; Archive is what rule 17 protects.

    What survives: this audit row. `audit_events` has no FK to `contracts`
    (entity_id is polymorphic), so "a contract existed and was deleted by X at
    T" stays answerable even though the contract's content does not.
    """
    contract = guard.contract(contract_id, P.CONTRACT_ARCHIVE, allow_archived=True)
    before = serialize_contract(contract)
    # QA-038: the uploaded originals go too, once the rows are gone for good — a file
    # removed before a rollback would leave rows pointing at nothing. Keys are per upload.
    versions = guard.db.execute(
        select(M.DocumentVersion)
        .where(M.DocumentVersion.contract_id == contract_id)).scalars().all()
    # AM-276: a signed contract — a FINAL_SIGNED version or an execution record — is
    # archived, never deleted (the executions FK is RESTRICT besides)
    if any((v.doc_metadata or {}).get("version_role") == FINAL_SIGNED
           for v in versions) or execution.current(guard.db, contract_id) is not None:
        raise Conflict("this contract has a signing record, so it cannot be deleted — "
                       "archive it instead")
    keys = [v.storage_key for v in versions]
    # QA-085: what was destroyed, by whom it was uploaded — the rows go with it
    before["document_versions"] = [
        {"id": str(v.id), "version_number": v.version_number, "file_hash": v.file_hash,
         "uploaded_by": str(v.uploaded_by)} for v in versions]
    storage = get_storage()
    event.listen(guard.db, "after_commit",
                 lambda _session: [storage.discard(k) for k in keys], once=True)
    guard.db.delete(contract)
    guard.db.flush()
    audit.record(
        guard.db, action=audit.CONTRACT_DELETED,
        entity_type="contract", entity_id=contract_id,
        actor_id=guard.user_id, request_id=guard.request_id, before=before,
        after=None,
    )


@router.post("/contracts/{contract_id}/transfer")
def transfer_contract(contract_id: UUID, body: ContractTransfer,
                      guard: Guard = Depends(get_guard)) -> dict:
    """Move a deal to a colleague — AB-12 r5. The Department Lead's coverage tool.

    Three checks, in the locked 43.23 order, and all of them server-side:

    1. **Visibility** — the contract is in the caller's read scope (404 if not).
    2. **Permission** — `contract.transfer` (403 without it).
    3. **Boundary** — the caller holds the contract as owner or through
       DEPARTMENT scope (Legal scope is read-only and never custody), and the
       new owner is an ACTIVE account in the caller's own department. A target
       outside it is refused with the same message as one that does not exist,
       so this endpoint is not a probe for other departments' accounts.

    What moves: the contract, and with it — because visibility is rooted in the
    contract (`can_see_review`) — every version, review, finding, report and
    annotation. What does not: `reviews.created_by` (history), and any Ask
    conversation, which stays with the person who asked (AB-12 r8).
    """
    contract = guard.contract_readable(contract_id, P.CONTRACT_TRANSFER)
    basis = contract_read_basis(guard.db, guard.user_id, contract)
    if basis not in (OWNER, DEPARTMENT):
        # A `legal.review` holder who was also granted `contract.transfer` can
        # SEE the contract through Legal scope; custody still is not theirs.
        raise Forbidden(
            "transfer requires ownership or department scope over the contract")
    if contract.archived_at is not None:
        raise Conflict("this contract is archived; restore it before transferring it")
    if guard.department_id is None:
        raise BusinessRuleRejected(
            "you are not in a department, so there is nobody to transfer to")
    new_owner = guard.db.get(M.User, body.new_owner_id)
    if (new_owner is None
            or new_owner.status is not E.UserStatus.ACTIVE
            or new_owner.department_id != guard.department_id):
        raise BusinessRuleRejected(
            "the new owner must be an active member of your department")
    if new_owner.id == contract.owner_id:
        raise BusinessRuleRejected("that user already owns this contract")

    previous_owner_id = contract.owner_id
    contract.owner_id = new_owner.id
    contract.updated_at = datetime.now(UTC)
    guard.db.flush()
    audit.record(
        guard.db, action=audit.CONTRACT_OWNERSHIP_TRANSFERRED,
        entity_type="contract", entity_id=contract_id,
        actor_id=guard.user_id, request_id=guard.request_id,
        before={"owner_id": str(previous_owner_id)},
        after={"owner_id": str(new_owner.id), "reason": body.reason},
    )
    payload = serialize_contract(contract)
    payload["owner_name"] = new_owner.name
    return data(payload)


_PERCENT_ESCAPE = re.compile(r"%([0-9A-Fa-f]{2})")


def _decode_percent_encoded_filename(value: str) -> str:
    """Decode a ``%XX``-escaped filename — the other half of the client's
    ``encodeURIComponent`` fix (2026-09-03).

    HTTP header values are restricted to ISO-8859-1 bytes, and a filename
    carrying any character outside that range made the browser's ``fetch``
    throw before the request ever left the tab — no request reached this
    endpoint at all, and the caller saw only a generic client-side error. The
    client now percent-encodes ``X-Filename``; this reverses it.

    A hand-rolled decoder rather than ``urllib.parse.unquote``: this router
    sits in the authoritative API path, where `AM-25` r9 / `AM-30` t1 forbid
    any network-capable import, and the import-boundary test (rightly)
    cannot distinguish ``urllib.parse`` from ``urllib.request`` by import
    root — it would flag this file as reaching the network, which it never
    does. This handles exactly what ``encodeURIComponent`` produces:
    percent-escaped UTF-8 byte sequences. A value with no ``%`` sequences
    (any existing non-browser caller sending the header un-encoded) passes
    through unchanged.
    """
    if "%" in value:
        raw_bytes = _PERCENT_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), value)
        value = raw_bytes.encode("latin-1").decode("utf-8", errors="replace")
    # QA-033/052/072: control and bidi-override characters are never part of a name, a
    # folder in it is not either, and an empty name reads as "document"
    return re.split(r"[\\/]", clean_name(value))[-1].strip() or "document"


async def read_bounded(request: Request, limit: int, refused: str) -> bytes:
    """QA-073: the body read up to ``limit`` bytes and refused past it — a request with
    no Content-Length was buffered whole before the size check."""
    got = bytearray()
    async for chunk in request.stream():
        got += chunk
        if len(got) > limit:
            raise BusinessRuleRejected(refused)
    return bytes(got)


@router.post("/contracts/{contract_id}/document-versions", status_code=201)
async def upload_document_version(
    contract_id: UUID,
    request: Request,
    x_filename: str = Header(..., max_length=400),
    guard: Guard = Depends(get_guard),
    storage: StorageBackend = Depends(get_storage),
) -> dict:
    """Ingest one document version — locked Step 34, 42.4.

    **The body is the file itself**, with the declared type in ``Content-Type``
    and the original name in ``X-Filename``. Endpoint shape is outside the locked
    boundary (38.24), and this shape avoids adding a multipart parser to the path
    that handles untrusted input — locked 34.16 and Step 39's upload-validation
    item both argue for the smaller surface. The declared type is treated as a
    *claim*: ``validate_upload`` sniffs the magic bytes and rejects a mismatch.

    A duplicate is **reported, never silently suppressed** (34.5): whether a
    re-upload is a new contractual version is a business decision (Step 33.9).

    **Async only to read the body; every database call runs in the threadpool**
    (2026-10-13). Each request updates its session row (`last_seen_at`), and a
    synchronous request commits on the event loop. A blocking query here, waiting
    on that row's lock, stopped the very loop the lock holder needed to commit:
    the whole API froze, permanently, whenever the Dashboard loaded during an
    upload. Pinned by `test_upload_does_not_block_the_event_loop.py`.
    """
    # AM-259 r2: the owner or a collaborator uploads the client's returned copy
    await run_in_threadpool(guard.contract_negotiable, contract_id, P.DOCUMENT_UPLOAD)

    # The client percent-encodes this header (2026-09-03): HTTP header values are
    # restricted to ISO-8859-1 bytes, and a filename carrying any character outside
    # that range (an en dash, a curly quote, anything non-ASCII) made the browser's
    # `fetch` throw before the request even left the tab — no request ever reached
    # here, and the caller saw only a generic client-side error. Decoding back to
    # the real filename is the other half of that fix; `unquote` is lenient by
    # design and never raises, so a caller that sends the header un-encoded (any
    # existing non-browser client) still gets its literal value back unchanged.
    original_filename = _decode_percent_encoded_filename(x_filename)

    declared_length = request.headers.get("content-length")
    limit = max_upload_bytes()
    if declared_length is not None and int(declared_length) > limit:
        raise BusinessRuleRejected(f"upload exceeds the {limit}-byte limit")
    payload = await read_bounded(request, limit, f"upload exceeds the {limit}-byte limit")
    if not payload:
        raise BusinessRuleRejected("the request body is empty")
    return await run_in_threadpool(
        _ingest_upload, guard, storage, contract_id, payload,
        original_filename, request.headers.get("content-type", ""))


def _ingest_upload(guard: Guard, storage: StorageBackend, contract_id: UUID,
                   payload: bytes, original_filename: str, declared_mime: str) -> dict:
    # `defer_ocr` — the ~63s-upload fix (2026-09-03). A document that needs OCR
    # returns from ingest as PROCESSING with no evidence, the request finishes in
    # native-parse time, and the OCR runs as its own background ProcessingRun
    # (42.5's OCR run type). The original bytes are already stored (34.5), so the
    # document is viewable the moment this returns. Everything not needing OCR
    # concludes inline exactly as before.
    result = ingest_document(
        guard.db, storage,
        contract_id=contract_id,
        uploaded_by=guard.user_id,
        data=payload,
        filename=original_filename,
        declared_mime=declared_mime,
        defer_ocr=True,
    )

    dv = result.document_version
    audit.record(guard.db, action=audit.DOCUMENT_UPLOADED, entity_type="contract",
                 entity_id=contract_id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"document_version_id": str(dv.id), "version_number":
                        dv.version_number, "filename": dv.original_filename,
                        "file_hash": dv.file_hash, "file_size_bytes": dv.file_size_bytes})
    if result.document_version.processing_status is E.ProcessingStatus.PROCESSING:
        # The deferred path: OCR (and then indexing, over the evidence OCR
        # writes) continues in the background; the response below says
        # PROCESSING, which is exactly the truth.
        dispatch_ocr(result.document_version.id, request_id=guard.request_id)
    else:
        # Assist-lane indexing — AB-3 / AB-4, Gate section 5b unit A2. Additive and
        # non-authoritative: it builds a derived search index over evidence the parser
        # has already produced, and it can never fail this upload. `dispatch_indexing`
        # swallows its own faults for that reason, and the response below is unchanged
        # either way — no field reports index state, because a document is ingested
        # whether or not a derived index was built.
        dispatch_indexing(guard.db, result.document_version.id,
                          request_id=guard.request_id)

    return data({
        "document_version": serialize_document_version(result.document_version),
        "processing_run": {
            "id": str(result.processing_run.id),
            "run_type": result.processing_run.run_type.value,
            "status": result.processing_run.status.value,
            "processor_version": result.processing_run.processor_version,
            "error_code": result.processing_run.error_code,
        },
        "evidence_count": result.evidence_count,
        "duplicate_of": (str(result.duplicate_of)
                         if result.duplicate_of else None),
        # 34.9 / REC-07 — diagnostics only. They never become a legal conclusion.
        "diagnostics": result.diagnostics,
    })
