"""Audit trail — locked 49.3, 42.18, AUD-01, 47.9.

Read-only by construction: there is no POST, PATCH or DELETE here, and the table
is append-only at the database level anyway (AUD-01 trigger), so nothing in the
API is what protects it.

Locked 47.9 adds one requirement that shapes the projection: "failed-login records
must not become an enumeration oracle in any surfaced view". No submitted email is
ever recorded, so there is nothing here to withhold — but see
``serialize_audit_event`` for why the state payloads are gated.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import paginated
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.serializers import (
    ADMINISTRATIVE_ACTION_PREFIXES,
    audit_lookups,
    serialize_audit_event,
)
from legalmind.db import models as M
from legalmind.security import permissions as P

router = APIRouter(tags=["audit"])


@router.get("/audit-events")
def list_audit_events(
    guard: Guard = Depends(get_guard),
    page: Page = Depends(page_params),
    # 49.6 — an allow-list, so a filter cannot become an arbitrary query.
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=100),
    entity_id: UUID | None = Query(default=None),
    actor_id: UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    administrative: bool = Query(default=False),
) -> dict:
    """``administrative=true`` narrows to identity-and-access events — the
    account lifecycle a platform administrator is answerable for, without the
    legal-workflow traffic they cannot read the payloads of anyway. Matched by
    the same prefixes the payload gate uses, so the filter and the gate can never
    disagree about what "administrative" means.

    ``since``/``until`` are a half-open range on the recorded timestamp. Still an
    allow-list (49.6): the caller chooses among these parameters and no other.
    """
    guard.permission(P.AUDIT_VIEW)
    stmt = select(M.AuditEvent)
    if action is not None:
        stmt = stmt.where(M.AuditEvent.action == action)
    if entity_type is not None:
        stmt = stmt.where(M.AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(M.AuditEvent.entity_id == entity_id)
    if actor_id is not None:
        stmt = stmt.where(M.AuditEvent.actor_id == actor_id)
    if since is not None:
        stmt = stmt.where(M.AuditEvent.timestamp >= since)
    if until is not None:
        stmt = stmt.where(M.AuditEvent.timestamp < until)
    if administrative:
        stmt = stmt.where(or_(*(M.AuditEvent.action.startswith(prefix)
                                for prefix in ADMINISTRATIVE_ACTION_PREFIXES)))
    rows, total = run(guard.db, stmt, page,
                      M.AuditEvent.timestamp.desc(), M.AuditEvent.id.desc())
    actors, labels = audit_lookups(guard.db, list(rows))
    return paginated(
        [serialize_audit_event(e, legal_position=guard.sees_legal_position,
                               actors=actors, labels=labels)
         for e in rows],
        page=page.page, page_size=page.page_size, total=total)
