"""Idempotent seeding of the permission catalogue and canonical roles.

Adapted from external pattern U-8, with its most important property retained:
**a newly added permission is never auto-granted to a non-super role.** An
administrator's deliberate trimming of a grant must never be silently undone by
a later deployment — the same class of mistake locked Step 9 prevents when it
says drafts must never silently affect comparisons.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.security import permissions as P


def sync_permission_catalogue(db: DBSession) -> int:
    """Insert any missing permission. Never removes or re-grants."""
    existing = set(db.execute(select(M.Permission.name)).scalars().all())
    added = 0
    for group, names in P.CATALOGUE.items():
        for name in names:
            if name not in existing:
                db.add(M.Permission(name=name, permission_group=group))
                added += 1
    db.flush()
    return added


def seed_roles(db: DBSession) -> int:
    """Create canonical roles (Step 23) if absent. Never renames or deletes."""
    existing = set(db.execute(select(M.Role.code)).scalars().all())
    added = 0
    for code, name in P.ROLE_NAMES.items():
        if code not in existing:
            db.add(M.Role(code=code, name=name))
            added += 1
    db.flush()
    return added


def seed_default_grants(db: DBSession, *, only_if_role_empty: bool = True) -> int:
    """Apply default grants from Step 23's locked role summary.

    ``only_if_role_empty`` defaults to True so re-running never restores a grant
    an administrator has since removed.
    """
    perms = {p.name: p.id for p in db.execute(select(M.Permission)).scalars()}
    roles = {r.code: r for r in db.execute(select(M.Role)).scalars()}
    added = 0
    for code, names in P.DEFAULT_ROLE_GRANTS.items():
        role = roles.get(code)
        if role is None:
            continue
        current = set(db.execute(
            select(M.RolePermission.permission_id)
            .where(M.RolePermission.role_id == role.id)
        ).scalars().all())
        if current and only_if_role_empty:
            continue
        for name in names:
            pid = perms.get(name)
            if pid is not None and pid not in current:
                db.add(M.RolePermission(role_id=role.id, permission_id=pid))
                added += 1
    db.flush()
    return added


def bootstrap(db: DBSession) -> dict[str, int]:
    return {
        "permissions": sync_permission_catalogue(db),
        "roles": seed_roles(db),
        "grants": seed_default_grants(db),
    }
