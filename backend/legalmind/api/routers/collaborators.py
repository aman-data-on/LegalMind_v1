"""Contract collaborators — `AM-259` (AB-150, 2026-11-02), R10.

A collaborator answers the client's changes and uploads returned versions beside the
owner, through `require_contract_negotiable`, and reads that one contract (`AM-280` r1,
amending r3) — while ACTIVE and in the owner's department (r2). Nothing else widens: a
Legal Decision still needs `legal.decision`, and archive, delete and transfer stay with
the owner and the Lead (r3).

Who may add or remove one: the owner, or the Department Lead over the owner's department
(r1). Only an ACTIVE account in the owner's department may be added; anyone else is
refused with one message, so this is not a probe for other departments' accounts.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.schemas import Body
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.authorization import DEPARTMENT, OWNER, contract_read_basis
from legalmind.security.errors import Forbidden

router = APIRouter(tags=["contracts"], route_class=CommitBeforeResponse)


class CollaboratorAdd(Body):
    user_id: UUID


def _members(guard: Guard, contract: M.Contract) -> tuple[list[M.User], list[M.User]]:
    """(collaborators, who could be added) — the second only to someone who may add."""
    added = guard.db.execute(
        select(M.User).join(M.ContractCollaborator,
                            M.ContractCollaborator.user_id == M.User.id)
        .where(M.ContractCollaborator.contract_id == contract.id)
        .order_by(M.User.name, M.User.id)).scalars().all()
    owner = guard.db.get(M.User, contract.owner_id)
    if owner is None or owner.department_id is None or not _may_manage(guard, contract):
        return list(added), []
    taken = {contract.owner_id, *(u.id for u in added)}
    pool = guard.db.execute(
        select(M.User).where(M.User.department_id == owner.department_id,
                             M.User.status == E.UserStatus.ACTIVE)
        .order_by(M.User.name, M.User.id)).scalars().all()
    return list(added), [u for u in pool if u.id not in taken]


def _may_manage(guard: Guard, contract: M.Contract) -> bool:
    return contract_read_basis(guard.db, guard.user_id, contract) in (OWNER, DEPARTMENT)


def _managed(guard: Guard, contract_id: UUID) -> M.Contract:
    contract = guard.contract_readable(contract_id, P.CONTRACT_UPDATE)
    if not _may_manage(guard, contract):
        raise Forbidden("only the contract's owner or their Department Lead can "
                        "change who works on it")
    if contract.archived_at is not None:
        raise Conflict("this contract is archived; restore it before changing who "
                       "works on it")
    return contract


def _person(u: M.User) -> dict:
    return {"id": str(u.id), "name": u.name, "email": u.email}


def _listing(guard: Guard, contract: M.Contract) -> dict:
    added, candidates = _members(guard, contract)
    return data({"collaborators": [_person(u) for u in added],
                 "candidates": [_person(u) for u in candidates],
                 "can_manage": _may_manage(guard, contract)})


@router.get("/contracts/{contract_id}/collaborators")
def list_collaborators(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    return _listing(guard, guard.contract_readable(contract_id, P.CONTRACT_VIEW))


@router.post("/contracts/{contract_id}/collaborators", status_code=201)
def add_collaborator(contract_id: UUID, body: CollaboratorAdd,
                     guard: Guard = Depends(get_guard)) -> dict:
    contract = _managed(guard, contract_id)
    owner = guard.db.get(M.User, contract.owner_id)
    person = guard.db.get(M.User, body.user_id)
    if (person is None or owner is None or owner.department_id is None
            or person.status is not E.UserStatus.ACTIVE
            or person.department_id != owner.department_id
            or person.id == contract.owner_id):
        raise BusinessRuleRejected(
            "a collaborator must be an active member of the owner's department")
    if guard.db.get(M.ContractCollaborator, (contract.id, person.id)) is None:
        guard.db.add(M.ContractCollaborator(contract_id=contract.id, user_id=person.id,
                                            added_by=guard.user_id))
        guard.db.flush()
        audit.record(guard.db, action=audit.CONTRACT_COLLABORATOR_ADDED,
                     entity_type="contract", entity_id=contract.id,
                     actor_id=guard.user_id, request_id=guard.request_id,
                     after={"user_id": str(person.id)})
    return _listing(guard, contract)


@router.delete("/contracts/{contract_id}/collaborators/{user_id}")
def remove_collaborator(contract_id: UUID, user_id: UUID,
                        guard: Guard = Depends(get_guard)) -> dict:
    contract = _managed(guard, contract_id)
    row = guard.db.get(M.ContractCollaborator, (contract.id, user_id))
    if row is not None:
        guard.db.delete(row)
        guard.db.flush()
        audit.record(guard.db, action=audit.CONTRACT_COLLABORATOR_REMOVED,
                     entity_type="contract", entity_id=contract.id,
                     actor_id=guard.user_id, request_id=guard.request_id,
                     before={"user_id": str(user_id)})
    return _listing(guard, contract)
