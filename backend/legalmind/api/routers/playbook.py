"""What the deal owner may agree without Legal — the negotiation playbook (`AM-305`).

Read-only. Both lines quote the ratified standard's position, so both need
``legal_position.view`` (LEGAL-02) on top of the object's own visibility: the contract's
READ scope, or a PUBLISHED template a ``contract.create`` holder may see (SEC-07). The
lines are derived by `analysis.playbook` (read through `drafting.playbook`) from our
paper and the snapshot; nothing here decides a legal outcome (rule 13).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import Conflict
from legalmind.api.routers.templates import _visible
from legalmind.drafting import playbook
from legalmind.security import permissions as P

router = APIRouter(tags=["playbook"], route_class=CommitBeforeResponse)


@router.get("/contracts/{contract_id}/playbook")
def contract_playbook(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    guard.permission(P.LEGAL_POSITION_VIEW)
    return data({"contract_id": str(contract.id),
                 "points": playbook.for_contract(guard.db, contract)})


@router.get("/templates/{template_id}/playbook")
def template_playbook(template_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    tv = _visible(guard, template_id)
    guard.permission(P.LEGAL_POSITION_VIEW)
    if tv.status != "PUBLISHED":
        raise Conflict("The playbook is read from a published template.")
    points = playbook.for_template(guard.db, tv, actor_id=guard.user_id,
                                   request_id=guard.request_id)
    if points is None:
        raise Conflict("The engine could not read this template.")
    return data({"template_id": str(tv.id), "points": points})
