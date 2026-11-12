"""The caller's own notifications — `AM-273` m3 (AB-150, 2026-11-02), R9.

Only ever the caller's rows: another person's notification is the same 404 as one that
does not exist (SEC-07). No permission beyond being signed in — a notice is addressed
to its reader, and its link is authorized again when it is opened.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from legalmind import notifications
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.db import models as M
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["notifications"], route_class=CommitBeforeResponse)

#: ponytail: the newest 50 only; paginate when someone keeps more than that.
LIMIT = 50


@router.get("/notifications")
def list_notifications(guard: Guard = Depends(get_guard)) -> dict:
    rows = guard.db.execute(
        select(M.Notification).where(M.Notification.user_id == guard.user_id)
        .order_by(M.Notification.created_at.desc(), M.Notification.id)
        .limit(LIMIT)).scalars().all()
    unread = guard.db.execute(
        select(func.count()).select_from(M.Notification)
        .where(M.Notification.user_id == guard.user_id,
               M.Notification.read_at.is_(None))).scalar_one()
    return data({"unread": unread,
                 "items": [notifications.view(guard.db, guard.user_id, n) for n in rows]})


@router.post("/notifications/read-all")
def read_all(guard: Guard = Depends(get_guard)) -> dict:
    notifications.mark_all_read(guard.db, guard.user_id)
    return data({"unread": 0})


@router.post("/notifications/{notification_id}/read")
def read_one(notification_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    n = guard.db.get(M.Notification, notification_id)
    if n is None or n.user_id != guard.user_id:
        raise NotVisible("notification not found")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
        guard.db.flush()
    return data(notifications.view(guard.db, guard.user_id, n))
