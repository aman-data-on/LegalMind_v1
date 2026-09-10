"""Counterparties — the company on the other side of a deal (AB-13, 2026-09-06),
and the Client Profile built on it (owner instruction, 2026-09-10).

**Visibility is rooted in the Contract** (r6), exactly as AB-12 r5 roots Reviews:
a counterparty is visible when the caller can see at least one contract linked to
it, under the scope AB-12 already defines. There is deliberately **no endpoint
that lists every counterparty** — "we have a deal with X" is the class of fact
`SEC-07`/`LEGAL-02` keep inside its scope, and a global list would disclose the
organisation's entire negotiating book to any account.

⚠️ **The Client Profiles screen does not change that.** It is a nicer surface
over the same scoped set, never a directory of every company the organisation
deals with. Its counts, its search and its "18 total clients" are all computed
from contracts this caller could already open one by one, so the screen can
never say more than the caller was already entitled to know. A future "company
directory" is a disclosure decision for the owner, not a UI convenience.

**No new permission** (r5): `contract.view` reads and `contract.update` writes.
Naming who a contract is with is part of maintaining that contract, and
2026-09-10 adds no exception — the profile is the same row with more fields on
it, so a caller who may rename a company may also record its website.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import CompoundSelect, Select, func, or_, select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.pagination import Page, page_params
from legalmind.api.routers.contracts import _list_summaries, _scoped_contracts
from legalmind.api.schemas import CounterpartyCreate, CounterpartyUpdate
from legalmind.api.serializers import (
    PROFILE_FIELDS,
    serialize_contract,
    serialize_counterparty,
    serialize_document_version,
)
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["counterparties"])

#: The one version role that means "executed". Named once: the Client Profile's
#: "signed documents" count, the per-document signed flag and the version list's
#: badge must all agree about what signed means, and three literals in three
#: places is how they stop agreeing.
FINAL_SIGNED = "FINAL_SIGNED"

#: List orderings the client directory offers. An allow-list, per 49.6's rule
#: that filtering and ordering are never arbitrary field access.
CLIENT_SORTS = ("name_asc", "name_desc", "recent_desc", "documents_desc", "added_desc")


def _visible_counterparty_ids(guard: Guard, scope: str = "own") -> CompoundSelect:
    """The ids reachable from contracts the caller may see (r6).

    `with_only_columns` is applied to the SCOPED statement, never to a
    re-selected subquery: doing it after `.subquery().select()` puts `contracts`
    back into the FROM clause unscoped, which silently returns every
    counterparty in the database. That mistake was caught by
    `test_a_counterparty_is_never_visible_outside_the_callers_contract_scope`
    before it left the branch, and this note is why the shape matters.

    Both archive states count: an archived contract is hidden from the working
    list, not erased (AB-12 r6), and its counterparty is still a company this
    caller demonstrably knows about.
    """
    live = _scoped_contracts(guard, scope, archived=False)
    shelved = _scoped_contracts(guard, scope, archived=True)
    # ...and always what this caller CREATED. Without it a company is invisible
    # to its own author until a contract points at it, which makes linking the
    # first deal impossible — the picker would have nothing to offer. Caught by
    # `counterparty.spec.ts` before it shipped. It widens disclosure to nobody:
    # you already know about the row you just made.
    mine = select(M.Counterparty.id).where(M.Counterparty.created_by == guard.user_id)
    return (live.with_only_columns(M.Contract.counterparty_id)
            .union(shelved.with_only_columns(M.Contract.counterparty_id), mine))


def _all_visible_ids(guard: Guard) -> list[UUID]:
    """Every counterparty id this caller may see, across every read scope.

    The list screen and the profile screen resolve visibility through this one
    function so they can never disagree about which clients exist — the class of
    drift AB-13 r6's own note warns about.
    """
    scopes = ["own"]
    if P.DEPARTMENT_VIEW in guard.permissions and guard.department_id is not None:
        scopes.append("department")
    seen: set[UUID] = set()
    for scope in scopes:
        seen.update(i for i in guard.db.execute(
            _visible_counterparty_ids(guard, scope)).scalars().all() if i is not None)
    return list(seen)


def _readable_contracts(guard: Guard) -> Select:
    """Every contract this caller may read, in BOTH archive states.

    Two corrections, both found in the pre-commit review (2026-09-06):

    * **Department scope belongs here.** `_readable` grants sight of a company
      through a DEPARTMENT contract, so listing only `own` showed a Department
      Lead the company with an EMPTY document list — the persona the
      "everything for this company" view exists for saw nothing.
    * **Archived contracts belong here.** AB-12 r6 takes an archived contract
      off the working lists and destroys nothing; a company's history is not a
      working list, and hiding half of it would misrepresent the relationship.
      Each row carries `archived_at`, so the reader can tell them apart, and
      the caller could already open every one of them by id.
    """
    scopes = ["own"]
    if P.DEPARTMENT_VIEW in guard.permissions and guard.department_id is not None:
        scopes.append("department")
    parts = [_scoped_contracts(guard, scope, archived=archived)
             .with_only_columns(M.Contract.id)
             for scope in scopes for archived in (False, True)]
    ids = parts[0].union(*parts[1:]) if len(parts) > 1 else parts[0]
    return select(M.Contract).where(M.Contract.id.in_(ids))


def _readable(guard: Guard, counterparty_id: UUID) -> M.Counterparty:
    """A counterparty outside the caller's scope is a 404, byte-identical to one
    that does not exist (49.5 r1) — the same answer `guard.contract` gives.

    Reachability is decided by the SAME scoped statement the list uses, so the
    list and the detail can never disagree about what this caller may see.
    """
    guard.permission(P.CONTRACT_VIEW)
    row = (guard.db.get(M.Counterparty, counterparty_id)
           if counterparty_id in set(_all_visible_ids(guard)) else None)
    if row is None:
        raise NotVisible("counterparty not found")
    return row


# ==========================================================================
# Client Profile statistics — derived, never stored
# ==========================================================================
def _client_stats(guard: Guard, ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
    """Per-client document counts and last activity, over the caller's own
    readable contracts.

    **Derived on read, deliberately.** A stored `document_count` on the
    counterparty row would be a denormalisation that has to be right after every
    upload, archive, delete, transfer and link change — and, worse, it would be
    the SAME number for every caller, which is exactly wrong here: two people
    with different scopes must see different counts of the same company, because
    each may only count what they may open. Deriving it from the scoped
    statement makes that structural rather than remembered.

    Three page-bounded queries, no N+1. `signed_documents` counts DOCUMENTS (a
    contract with at least one executed version), not versions — "how many of
    our agreements with this client are signed?" is the question a non-legal
    reader is asking, and a contract with two signed versions is still one
    signed agreement.
    """
    empty = {"documents": 0, "signed_documents": 0, "last_activity": None}
    if not ids:
        return {}
    stats: dict[UUID, dict[str, Any]] = {i: dict(empty) for i in ids}

    rows = guard.db.execute(
        _readable_contracts(guard)
        .where(M.Contract.counterparty_id.in_(ids))
        .with_only_columns(M.Contract.id, M.Contract.counterparty_id,
                           M.Contract.updated_at)
    ).all()
    if not rows:
        return stats

    owner_of: dict[UUID, UUID] = {}
    for contract_id, counterparty_id, updated_at in rows:
        owner_of[contract_id] = counterparty_id
        entry = stats[counterparty_id]
        entry["documents"] += 1
        entry["last_activity"] = _later(entry["last_activity"], updated_at)

    # One grouped pass over the versions of exactly those contracts: the newest
    # upload (activity) and whether any of them is the executed one.
    version_rows = guard.db.execute(
        select(
            M.DocumentVersion.contract_id,
            func.max(M.DocumentVersion.created_at),
            func.count().filter(
                M.DocumentVersion.doc_metadata["version_role"].astext
                == FINAL_SIGNED),
        )
        .where(M.DocumentVersion.contract_id.in_(list(owner_of)))
        .group_by(M.DocumentVersion.contract_id)
    ).all()
    for contract_id, newest, signed in version_rows:
        entry = stats[owner_of[contract_id]]
        entry["last_activity"] = _later(entry["last_activity"], newest)
        if signed:
            entry["signed_documents"] += 1
    return stats


def _later(a: datetime | None, b: datetime | None) -> datetime | None:
    """The more recent of two possibly-absent timestamps.

    Both sides are normalised to UTC-aware before comparing: the column is
    `TIMESTAMP WITH TIME ZONE`, but a value that has been through a round trip
    in a naive form would otherwise raise `TypeError` at the comparison and take
    the whole client list down over a formatting detail.
    """
    if a is None:
        return b
    if b is None:
        return a
    return max(_aware(a), _aware(b))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    return _aware(value).isoformat() if value is not None else None


def _account_owner_names(guard: Guard,
                         rows: list[M.Counterparty]) -> dict[UUID, str]:
    """Display names for the account owners on this page — one query.

    A colleague's display name is already visible through the department members
    list and through `owner_name` on any shared contract, so nothing new is
    disclosed by naming who holds a relationship.
    """
    ids = {r.account_owner_id for r in rows if r.account_owner_id}
    if not ids:
        return {}
    return {row[0]: row[1] for row in guard.db.execute(
        select(M.User.id, M.User.name).where(M.User.id.in_(ids))).all()}


# ==========================================================================
# Endpoints
# ==========================================================================
@router.get("/counterparties")
def list_counterparties(
    guard: Guard = Depends(get_guard),
    page: Page = Depends(page_params),
    scope: str = "own",
    q: str | None = Query(default=None, max_length=500),
    status: str | None = Query(default=None, max_length=40),
    industry: str | None = Query(default=None, max_length=200),
    has_documents: bool | None = Query(default=None),
    sort: str = Query(default="name_asc"),
    stats: bool = Query(default=False),
) -> dict:
    """The companies this caller actually deals with — never the whole book (r6).

    Paginated as of 2026-09-10 (Client Profiles). The envelope's `data` is still
    the array it always was — `paginated()` adds `pagination` beside it rather
    than nesting — so every existing caller reads exactly what it read before.
    Only the default page size is new, and the picker that needs them all asks
    for a bigger page.

    `q`, `status` and `industry` filter in SQL. `has_documents` and
    `documents_desc` depend on the per-caller counts, which no counterparties
    WHERE can reach, so they are applied over the bounded scoped set in Python —
    the precedent `GET /contracts?status=` already set for a derived filter.

    `stats=true` adds `documents` / `signed_documents` / `last_activity` per
    row. Off by default so the existing picker's call stays one query.
    """
    guard.permission(P.CONTRACT_VIEW)
    if sort not in CLIENT_SORTS:
        raise BusinessRuleRejected(
            f"unknown sort {sort!r}; expected one of {CLIENT_SORTS}")

    # `scope` is honoured for compatibility with the pre-2026-09-10 caller; the
    # client screen wants everything the caller can see, which is what an
    # explicit "own" plus department scope resolves to anyway.
    ids = (_all_visible_ids(guard) if scope == "own"
           else [i for i in guard.db.execute(_visible_counterparty_ids(guard, scope))
                 .scalars().all() if i is not None])
    if not ids:
        return paginated([], page=page.page, page_size=page.page_size, total=0)

    stmt = select(M.Counterparty).where(M.Counterparty.id.in_(ids))
    if q:
        needle = f"%{q.strip()}%"
        # Name first, but a reader searching "Mumbai" or the registered name is
        # searching for the same client — matching only `name` sent them away
        # empty from a client that is plainly there.
        stmt = stmt.where(or_(M.Counterparty.name.ilike(needle),
                              M.Counterparty.legal_name.ilike(needle),
                              M.Counterparty.city.ilike(needle)))
    if status:
        stmt = stmt.where(M.Counterparty.status == status)
    if industry:
        stmt = stmt.where(M.Counterparty.industry == industry)

    rows = list(guard.db.execute(stmt).scalars().all())
    want_stats = stats or has_documents is not None or sort == "documents_desc"
    tally = _client_stats(guard, [r.id for r in rows]) if want_stats else {}

    if has_documents is not None:
        rows = [r for r in rows
                if bool(tally.get(r.id, {}).get("documents")) is has_documents]

    def key(row: M.Counterparty):
        entry = tally.get(row.id, {})
        if sort == "documents_desc":
            return (-(entry.get("documents") or 0), row.name.lower())
        if sort == "recent_desc":
            last = entry.get("last_activity") or _aware(row.updated_at)
            return (-last.timestamp(), row.name.lower())
        if sort == "added_desc":
            return (-_aware(row.created_at).timestamp(), row.name.lower())
        return (row.name.lower(), str(row.id))

    rows.sort(key=key, reverse=(sort == "name_desc"))
    total = len(rows)
    start = (page.page - 1) * page.page_size
    window = rows[start:start + page.page_size]

    owner_names = _account_owner_names(guard, window)
    payload = []
    for row in window:
        item = serialize_counterparty(row)
        if row.account_owner_id:
            item["account_owner_name"] = owner_names.get(row.account_owner_id)
        if want_stats:
            entry = tally.get(row.id, {})
            item["documents"] = entry.get("documents", 0)
            item["signed_documents"] = entry.get("signed_documents", 0)
            item["last_activity"] = _iso(entry.get("last_activity"))
        payload.append(item)
    return paginated(payload, page=page.page, page_size=page.page_size, total=total)


@router.get("/counterparties/industries")
def list_industries(guard: Guard = Depends(get_guard)) -> dict:
    """The industry values actually in use, for the list screen's filter.

    Derived from the caller's own visible clients, never a catalogue: there is
    no controlled list of industries in this product (rule 21 — the
    organisation's industry taxonomy is not ours to invent), so the filter can
    only honestly offer what somebody has typed. An empty result means nobody
    has recorded one yet, and the filter hides itself.
    """
    guard.permission(P.CONTRACT_VIEW)
    ids = _all_visible_ids(guard)
    if not ids:
        return data([])
    rows = guard.db.execute(
        select(M.Counterparty.industry)
        .where(M.Counterparty.id.in_(ids), M.Counterparty.industry.is_not(None))
        .distinct().order_by(M.Counterparty.industry)
    ).scalars().all()
    return data(list(rows))


@router.post("/counterparties", status_code=201)
def create_counterparty(body: CounterpartyCreate,
                        guard: Guard = Depends(get_guard)) -> dict:
    """`contract.update` (r5) — you are naming a company you are about to link.

    Deliberately NOT unique on name: two genuinely different companies may share
    one, and a unique constraint would make the second one unrecordable. The
    convergence affordance is the picker, which shows what already exists — and
    since 2026-09-10 the Add Client form additionally *warns*, live, when the
    name being typed already names a client this caller can see, and offers to
    open it instead. A warning is the right instrument here and a refusal is
    not: only the person typing knows whether these are two companies or one.
    """
    guard.permission(P.CONTRACT_UPDATE)
    row = M.Counterparty(
        name=body.name, industry=body.industry,
        relationship_notes=body.relationship_notes, created_by=guard.user_id)
    if body.status is not None:
        row.status = body.status
    for field in PROFILE_FIELDS:
        if field in body.model_fields_set and field not in ("industry",
                                                            "relationship_notes"):
            setattr(row, field, getattr(body, field))
    if body.account_owner_id is not None:
        row.account_owner_id = _resolve_account_owner(guard, body.account_owner_id)
    guard.db.add(row)
    guard.db.flush()
    audit.record(guard.db, action=audit.COUNTERPARTY_CREATED,
                 entity_type="counterparty", entity_id=row.id,
                 actor_id=guard.user_id, request_id=guard.request_id,
                 after={"name": row.name})
    return data(serialize_counterparty(row))


def _resolve_account_owner(guard: Guard, user_id: UUID) -> UUID:
    """The relationship's owner must be a real, active colleague in the caller's
    own department — the same boundary `contract.transfer` enforces, and for the
    same reason: an id that resolves differently depending on who is asking
    would turn this field into a probe for other departments' accounts. A target
    outside the boundary is refused with the message a nonexistent one gets.
    """
    user = guard.db.get(M.User, user_id)
    if (user is None
            or user.status is not E.UserStatus.ACTIVE
            or guard.department_id is None
            or user.department_id != guard.department_id):
        raise BusinessRuleRejected(
            "the account owner must be an active member of your department")
    return user.id


@router.get("/counterparties/{counterparty_id}")
def get_counterparty(counterparty_id: UUID,
                     guard: Guard = Depends(get_guard)) -> dict:
    """The profile AND its documents — this is the manager's "related documents"
    answer (r3): every contract for this company, in one place, derived from the
    link rather than from a relationship table. Scoped: the list holds only
    contracts this caller could already open one by one (49.6).

    Since 2026-09-10 each contract also carries what the Client Profile's one
    unified document list shows: its versions (newest first, with the declared
    role each was given), whether an executed version exists, and the same
    permission-layered `latest_version` / `latest_analysis` projection the
    Dashboard rows use — reused from `contracts.py` rather than recomputed, so
    a document cannot read one way here and another way there.

    ⚠️ **One list, never grouped by type.** The API returns a flat array in one
    order and offers no per-type grouping, because the owner's instruction makes
    that structural: document type is metadata on the row, not a folder.
    """
    row = _readable(guard, counterparty_id)
    contracts = guard.db.execute(
        _readable_contracts(guard)
        .where(M.Contract.counterparty_id == counterparty_id)
        .order_by(M.Contract.created_at.desc(), M.Contract.id.desc())
    ).scalars().all()

    payload = serialize_counterparty(row)
    if row.account_owner_id:
        payload["account_owner_name"] = _account_owner_names(
            guard, [row]).get(row.account_owner_id)

    summaries = _list_summaries(guard, [c.id for c in contracts])
    versions_by_contract = _versions_for(guard, [c.id for c in contracts])
    items = []
    for contract in contracts:
        item = serialize_contract(contract)
        item.update(summaries.get(contract.id,
                                  {"latest_version": None, "latest_analysis": None}))
        versions = versions_by_contract.get(contract.id, [])
        if P.DOCUMENT_VIEW in guard.permissions:
            item["versions"] = versions
            item["version_count"] = len(versions)
            item["signed"] = any(v.get("version_role") == FINAL_SIGNED
                                 for v in versions)
        items.append(item)
    payload["contracts"] = items

    entry = _client_stats(guard, [counterparty_id]).get(counterparty_id, {})
    payload["documents"] = entry.get("documents", 0)
    payload["signed_documents"] = entry.get("signed_documents", 0)
    payload["last_activity"] = _iso(entry.get("last_activity"))
    return data(payload)


def _versions_for(guard: Guard,
                  contract_ids: list[UUID]) -> dict[UUID, list[dict[str, Any]]]:
    """Every version of these contracts, newest first — one query, no N+1.

    Gated on `document.view` like every other version projection: a caller who
    may see that a contract exists but not read its documents gets the contract
    row and no version list, rather than a count that leaks how much paper has
    changed hands.
    """
    if not contract_ids or P.DOCUMENT_VIEW not in guard.permissions:
        return {}
    rows = guard.db.execute(
        select(M.DocumentVersion)
        .where(M.DocumentVersion.contract_id.in_(contract_ids))
        .order_by(M.DocumentVersion.contract_id,
                  M.DocumentVersion.version_number.desc())
    ).scalars().all()
    out: dict[UUID, list[dict[str, Any]]] = {}
    for version in rows:
        out.setdefault(version.contract_id, []).append(
            serialize_document_version(version))
    return out


@router.get("/counterparties/{counterparty_id}/activity")
def counterparty_activity(counterparty_id: UUID,
                          guard: Guard = Depends(get_guard),
                          limit: int = Query(default=50, ge=1, le=200)) -> dict:
    """What has happened to this client and its documents, newest first.

    **The existing audit trail, re-read — not a second history.** `audit_events`
    (42.18, AUD-01) already records every event the owner's instruction asks
    for: the client created and updated, a document's type declared, its
    counterparty linked, its status changed, a version reprocessed, an analysis
    run, a contract archived, restored, transferred or deleted. Nothing new is
    written for this screen and no event is invented for it.

    **Scope is inherited, not widened.** `GET /audit` needs `audit.view`, which
    an ordinary Department User does not hold — and rightly, because that
    endpoint spans the whole system. This one is bounded to the entity ids the
    caller can already reach: this counterparty, and the contracts of it that
    `_readable_contracts` returns. A caller who can open the profile can see its
    history and nothing else, so no new permission is required.

    **Payloads are deliberately not returned.** An audit row's before/after can
    hold an internal legal position (`LEGAL-02`), and a client activity feed is
    not the surface to relax that on. The feed answers when, what and who.
    """
    _readable(guard, counterparty_id)
    contract_ids = list(guard.db.execute(
        _readable_contracts(guard)
        .where(M.Contract.counterparty_id == counterparty_id)
        .with_only_columns(M.Contract.id)
    ).scalars().all())

    entity_ids = [counterparty_id, *contract_ids]
    rows = guard.db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.entity_id.in_(entity_ids))
        .order_by(M.AuditEvent.timestamp.desc(), M.AuditEvent.id.desc())
        .limit(limit)
    ).scalars().all()

    actor_ids = {r.actor_id for r in rows if r.actor_id}
    names = ({row[0]: row[1] for row in guard.db.execute(
        select(M.User.id, M.User.name).where(M.User.id.in_(actor_ids))).all()}
        if actor_ids else {})
    contract_names = ({row[0]: row[1] for row in guard.db.execute(
        select(M.Contract.id, M.Contract.name)
        .where(M.Contract.id.in_(contract_ids))).all()}
        if contract_ids else {})

    return data([{
        "id": str(event.id),
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": str(event.entity_id) if event.entity_id else None,
        "subject": contract_names.get(event.entity_id),
        "actor_name": names.get(event.actor_id) if event.actor_id else None,
        "timestamp": _iso(event.timestamp),
    } for event in rows])


@router.patch("/counterparties/{counterparty_id}")
def update_counterparty(counterparty_id: UUID, body: CounterpartyUpdate,
                        guard: Guard = Depends(get_guard)) -> dict:
    """`contract.update` (r5), and every change audited (r8) — a shared profile
    that several people may edit is exactly what AUD-01 exists for.

    The audit `before`/`after` carry only the fields this request actually
    changed. Recording the whole profile on every edit would bury the one field
    that moved, and an append-only trail (AUD-01) keeps that noise forever.
    """
    row = _readable(guard, counterparty_id)
    guard.permission(P.CONTRACT_UPDATE)

    tracked = ("name", "industry", "relationship_notes", "status",
               "account_owner_id", *PROFILE_FIELDS)
    before = {f: _plain(getattr(row, f)) for f in tracked}
    for field in body.model_fields_set:
        value = getattr(body, field)
        if field in ("name", "status") and value is None:
            # A company with no name is no identity, and `status` is NOT NULL.
            continue
        if field == "account_owner_id" and value is not None:
            value = _resolve_account_owner(guard, value)
        setattr(row, field, value)
    guard.db.flush()
    after = {f: _plain(getattr(row, f)) for f in tracked}

    changed = {f for f in tracked if before[f] != after[f]}
    if changed:
        audit.record(guard.db, action=audit.COUNTERPARTY_UPDATED,
                     entity_type="counterparty", entity_id=row.id,
                     actor_id=guard.user_id, request_id=guard.request_id,
                     before={f: before[f] for f in changed},
                     after={f: after[f] for f in changed})
    return data(serialize_counterparty(row))


def _plain(value: Any) -> Any:
    """JSON-safe for an audit payload — a UUID is not."""
    return str(value) if isinstance(value, UUID) else value
