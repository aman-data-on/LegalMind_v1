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
from sqlalchemy import Select, false, func, select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.schemas import ContractCreate, ContractTransfer, ContractUpdate
from legalmind.api.serializers import (
    declared_metadata,
    serialize_contract,
    serialize_document_version,
)
from legalmind.api.storage import get_storage
from legalmind.config import max_upload_bytes
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.authorization import (
    DEPARTMENT,
    OWNER,
    contract_read_basis,
)
from legalmind.evaluation.user_status import by_finding, counts as user_status_counts
from legalmind.security.errors import Forbidden
from legalmind.worker.dispatch import dispatch_indexing, dispatch_ocr

router = APIRouter(tags=["contracts"])


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
STATUS_BUCKETS = ("draft", "analyzing", "needs_attention", "analyzed")


def _status_bucket(item: dict) -> str:
    version = item.get("latest_version")
    if version is None or version.get("processing_status") != "COMPLETED":
        return "draft"
    analysis = item.get("latest_analysis")
    if analysis is None:
        return "draft"
    if analysis.get("review_status") in _IN_FLIGHT_REVIEW_STATUSES:
        return "analyzing"
    counts = analysis.get("user_status_counts") or {}
    if any(n > 0 for status, n in counts.items() if status != "ACCEPTED"):
        return "needs_attention"
    return "analyzed"


SCOPES = ("own", "department")


def _scoped_contracts(guard: Guard, scope: str, *, archived: bool) -> Select:
    """The list-side statement of the same rule `contract_read_basis` applies by
    id (49.6: a list never leaks a row a GET would 404 on).

    ``own`` is ownership. ``department`` (AB-12 r3) is every contract whose owner
    is in the caller's department — it needs `department.view` (403 without) AND
    a department to be scoped to: a Lead nobody has placed yet matches nothing,
    never everything. Legal scope has no list here; it is Review-shaped and
    lives in `GET /reviews`.
    """
    if scope not in SCOPES:
        raise BusinessRuleRejected(f"unknown scope {scope!r}; expected one of {SCOPES}")
    if scope == "department":
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
    """
    guard.permission(P.CONTRACT_VIEW)
    stmt = _scoped_contracts(guard, scope, archived=archived)
    if q:
        stmt = stmt.where(M.Contract.name.ilike(f"%{q.strip()}%"))
    if contract_type:
        stmt = stmt.where(M.Contract.contract_type == contract_type)

    order = {
        "created_desc": (M.Contract.created_at.desc(), M.Contract.id.desc()),
        "created_asc": (M.Contract.created_at.asc(), M.Contract.id.asc()),
        "name_asc": (M.Contract.name.asc(), M.Contract.id.asc()),
        "name_desc": (M.Contract.name.desc(), M.Contract.id.desc()),
    }.get(sort, (M.Contract.created_at.desc(), M.Contract.id.desc()))

    if status not in (None, *STATUS_BUCKETS):
        raise BusinessRuleRejected(
            f"unknown status filter {status!r}; expected one of {STATUS_BUCKETS}")

    if status is None:
        rows, total = run(guard.db, stmt, page, *order)
        summaries = _list_summaries(guard, [c.id for c in rows])
    else:
        # The bucket depends on analysis data no contracts-table WHERE can
        # reach, so filter-then-paginate rather than paginate-then-filter.
        all_rows = guard.db.execute(stmt.order_by(*order)).scalars().all()
        summaries = _list_summaries(guard, [c.id for c in all_rows])
        matched = [c for c in all_rows
                  if _status_bucket(summaries.get(c.id, {})) == status]
        total = len(matched)
        start = (page.page - 1) * page.page_size
        rows = matched[start:start + page.page_size]

    owner_names = _owner_names(guard, list(rows))
    payload = []
    for c in rows:
        item = serialize_contract(c)
        item["owner_name"] = owner_names.get(c.owner_id)
        item.update(summaries.get(c.id, {"latest_version": None,
                                         "latest_analysis": None}))
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
    ids = guard.db.execute(
        _scoped_contracts(guard, scope, archived=False).with_only_columns(M.Contract.id)
    ).scalars().all()
    summaries = _list_summaries(guard, list(ids))
    tally = dict.fromkeys(STATUS_BUCKETS, 0)
    for cid in ids:
        tally[_status_bucket(summaries.get(cid, {}))] += 1
    return data({
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
        statuses = by_finding(guard.db, [r.id for r in latest_review.values()])
    else:
        statuses = {}

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
            analysis["user_status_counts"] = user_status_counts(
                statuses.get(review.id, {}))
        out[cid]["latest_analysis"] = analysis
    return out


@router.post("/contracts", status_code=201)
def create_contract(body: ContractCreate,
                    guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.CONTRACT_CREATE)
    contract = M.Contract(owner_id=guard.user_id, name=body.name,
                          contract_type=body.contract_type,
                          status=E.ContractStatus.DRAFT)
    guard.db.add(contract)
    guard.db.flush()
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
    return data(payload)


@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: UUID, body: ContractUpdate,
                    guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract(contract_id, P.CONTRACT_UPDATE)
    if body.name is not None:
        contract.name = body.name
    if body.contract_type is not None and body.contract_type != contract.contract_type:
        # AM-50 (2026-09-09): the type is still recorded only through this
        # ordinary update, and the trail now says WHO determined it — the reader,
        # or the intake applying a confident suggestion. Analysis still refuses
        # an undeclared type; nothing here changes what the evaluator does.
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
    if "counterparty_id" in body.model_fields_set:
        # AB-13 r2 — who this deal is with. A nonexistent id is refused rather
        # than stored: a dangling link is worse than no link. Sent as null it
        # unlinks. Audited either way (r8), because this is the fact the whole
        # "show me everything for this company" view is derived from.
        target = body.counterparty_id
        if target is not None and guard.db.get(M.Counterparty, target) is None:
            raise BusinessRuleRejected("unknown counterparty")
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
    return data(serialize_contract(contract))


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
    if "%" not in value:
        return value
    raw_bytes = _PERCENT_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), value)
    return raw_bytes.encode("latin-1").decode("utf-8", errors="replace")


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
    """
    guard.contract(contract_id, P.DOCUMENT_UPLOAD)

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
    payload = await request.body()
    if len(payload) > limit:
        raise BusinessRuleRejected(f"upload exceeds the {limit}-byte limit")
    if not payload:
        raise BusinessRuleRejected("the request body is empty")

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
        declared_mime=request.headers.get("content-type", ""),
        defer_ocr=True,
    )

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
