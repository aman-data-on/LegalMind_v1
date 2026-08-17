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

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import paginated
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.serializers import serialize_audit_event
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
) -> dict:
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
    rows, total = run(guard.db, stmt, page,
                      M.AuditEvent.timestamp.desc(), M.AuditEvent.id.desc())
    return paginated(
        [serialize_audit_event(e, legal_position=guard.sees_legal_position)
         for e in rows],
        page=page.page, page_size=page.page_size, total=total)
