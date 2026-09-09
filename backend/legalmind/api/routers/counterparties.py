"""Counterparties — the company on the other side of a deal (AB-13, 2026-09-06).

**Visibility is rooted in the Contract** (r6), exactly as AB-12 r5 roots Reviews:
a counterparty is visible when the caller can see at least one contract linked to
it, under the scope AB-12 already defines. There is deliberately **no endpoint
that lists every counterparty** — "we have a deal with X" is the class of fact
`SEC-07`/`LEGAL-02` keep inside its scope, and a global list would disclose the
organisation's entire negotiating book to any account.

**No new permission** (r5): `contract.view` reads and `contract.update` writes.
Naming who a contract is with is part of maintaining that contract.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import CompoundSelect, Select, select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.routers.contracts import _scoped_contracts
from legalmind.api.schemas import CounterpartyCreate, CounterpartyUpdate
from legalmind.api.serializers import serialize_contract, serialize_counterparty
from legalmind.db import models as M
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["counterparties"])


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
    scopes = ["own"]
    if P.DEPARTMENT_VIEW in guard.permissions:
        scopes.append("department")
    reachable = any(
        counterparty_id in {i for i in guard.db.execute(
            _visible_counterparty_ids(guard, scope)).scalars().all() if i is not None}
        for scope in scopes
    )
    row = guard.db.get(M.Counterparty, counterparty_id) if reachable else None
    if row is None:
        raise NotVisible("counterparty not found")
    return row


@router.get("/counterparties")
def list_counterparties(guard: Guard = Depends(get_guard),
                        scope: str = "own") -> dict:
    """The companies this caller actually deals with — never the whole book (r6)."""
    guard.permission(P.CONTRACT_VIEW)
    ids = [i for i in guard.db.execute(_visible_counterparty_ids(guard, scope))
           .scalars().all() if i is not None]
    if not ids:
        return data([])
    rows = guard.db.execute(
        select(M.Counterparty).where(M.Counterparty.id.in_(ids))
        .order_by(M.Counterparty.name, M.Counterparty.id)
    ).scalars().all()
    return data([serialize_counterparty(c) for c in rows])


@router.post("/counterparties", status_code=201)
def create_counterparty(body: CounterpartyCreate,
                        guard: Guard = Depends(get_guard)) -> dict:
    """`contract.update` (r5) — you are naming a company you are about to link.

    Deliberately NOT unique on name: two genuinely different companies may share
    one, and a unique constraint would make the second one unrecordable. The
    convergence affordance is the picker, which shows what already exists.
    """
    guard.permission(P.CONTRACT_UPDATE)
    row = M.Counterparty(
        name=body.name, industry=body.industry,
        relationship_notes=body.relationship_notes, created_by=guard.user_id)
    guard.db.add(row)
    guard.db.flush()
    audit.record(guard.db, action=audit.COUNTERPARTY_CREATED,
                 entity_type="counterparty", entity_id=row.id,
                 actor_id=guard.user_id, request_id=guard.request_id,
                 after={"name": row.name})
    return data(serialize_counterparty(row))


@router.get("/counterparties/{counterparty_id}")
def get_counterparty(counterparty_id: UUID,
                     guard: Guard = Depends(get_guard)) -> dict:
    """The profile AND its documents — this is the manager's "related documents"
    answer (r3): every contract for this company, in one place, derived from the
    link rather than from a relationship table. Scoped: the list holds only
    contracts this caller could already open one by one (49.6)."""
    row = _readable(guard, counterparty_id)
    contracts = guard.db.execute(
        _readable_contracts(guard)
        .where(M.Contract.counterparty_id == counterparty_id)
        .order_by(M.Contract.created_at.desc(), M.Contract.id.desc())
    ).scalars().all()
    payload = serialize_counterparty(row)
    payload["contracts"] = [serialize_contract(c) for c in contracts]
    return data(payload)


@router.patch("/counterparties/{counterparty_id}")
def update_counterparty(counterparty_id: UUID, body: CounterpartyUpdate,
                        guard: Guard = Depends(get_guard)) -> dict:
    """`contract.update` (r5), and every change audited (r8) — a shared profile
    that several people may edit is exactly what AUD-01 exists for."""
    row = _readable(guard, counterparty_id)
    guard.permission(P.CONTRACT_UPDATE)
    before = {"name": row.name, "industry": row.industry,
              "relationship_notes": row.relationship_notes}
    for field in body.model_fields_set:
        value = getattr(body, field)
        if field == "name" and value is None:
            continue                       # a company with no name is no identity
        setattr(row, field, value)
    guard.db.flush()
    after = {"name": row.name, "industry": row.industry,
             "relationship_notes": row.relationship_notes}
    if after != before:
        audit.record(guard.db, action=audit.COUNTERPARTY_UPDATED,
                     entity_type="counterparty", entity_id=row.id,
                     actor_id=guard.user_id, request_id=guard.request_id,
                     before=before, after=after)
    return data(serialize_counterparty(row))
