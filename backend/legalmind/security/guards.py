"""Authority guards — Step 47 §47.5, S-8, S-9.

These prevent authority from being created or destroyed improperly. Both are
adapted from the external MoS reference and then extended: its guard covered
GRANTING a role but, by its own admission, not editing or deleting a
more-privileged account. LegalMind does not inherit that hole (S-9).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.security.errors import Forbidden
from legalmind.security.resolver import effective_permissions


# Locked S-8 names the permissions the escalation guard applies to, verbatim:
# "applied to `legal.decision`, `legal.approve_customization`, `role.manage` and
# `platform.manage`". The guard compares only these.
#
# Comparing the FULL permission sets instead would be wrong, not merely stricter.
# Locked Step 23 gives Super Admin no contract or Legal content access at all
# (Step 24 r8/r9), so an ordinary User holds `contract.view` that a Super Admin
# does not — and a whole-set difference would read that as the User being "more
# privileged" and lock the Super Admin out of administering anyone. Different is
# not the same as higher; the locked list is what distinguishes them.
ESCALATION_GUARDED_PERMISSIONS: frozenset[str] = frozenset({
    P.LEGAL_DECISION,
    P.LEGAL_APPROVE_CUSTOMIZATION,
    P.ROLE_MANAGE,
    P.PLATFORM_MANAGE,
})


def require_can_grant_role(db: DBSession, actor_id: UUID, role_id: UUID) -> None:
    """S-8 — a user may not grant an authority they do not themselves hold."""
    actor = effective_permissions(db, actor_id)
    target = _role_permissions(db, role_id) & ESCALATION_GUARDED_PERMISSIONS
    escalation = target - actor
    if escalation:
        raise Forbidden(
            "escalation refused: cannot grant permissions the actor does not "
            f"hold: {sorted(escalation)}"
        )


def require_can_administer_user(db: DBSession, actor_id: UUID,
                                target_user_id: UUID) -> None:
    """S-9 — the guard covers editing and deleting, not only granting.

    Without this, a user could not *grant* legal authority but could delete or
    edit an account that holds it, which reaches the same outcome by another
    route.
    """
    if actor_id == target_user_id:
        return
    actor = effective_permissions(db, actor_id)
    target = effective_permissions(db, target_user_id) & ESCALATION_GUARDED_PERMISSIONS
    excess = target - actor
    if excess:
        raise Forbidden(
            "escalation refused: target holds permissions the actor does not: "
            f"{sorted(excess)}"
        )


def assert_legal_authority_remains(db: DBSession) -> None:
    """SEC-05 — never zero legal authorities.

    A configuration change that left no user holding ``legal.decision`` would
    stall every Review requiring one, making locked Step 31 r18 and Step 30 r7
    unsatisfiable. Called after any change that could remove the last holder.

    Only ACTIVE users count. A suspended or disabled account cannot authenticate
    by any route (47.1.3), so a grant it still holds cannot resolve anything —
    counting it would satisfy SEC-05 on paper while leaving exactly the stalled
    Review the rule exists to prevent.
    """
    if count_legal_authorities(db) == 0:
        raise Forbidden(
            "refused: this change would leave no user able to make a Legal "
            "Decision (SEC-05)"
        )


def count_legal_authorities(db: DBSession) -> int:
    """How many ACTIVE users can currently make a Legal Decision."""
    return db.execute(
        select(func.count(func.distinct(M.UserRole.user_id)))
        .select_from(M.UserRole)
        .join(M.RolePermission, M.RolePermission.role_id == M.UserRole.role_id)
        .join(M.Permission, M.Permission.id == M.RolePermission.permission_id)
        .join(M.User, M.User.id == M.UserRole.user_id)
        .where(M.Permission.name == P.LEGAL_DECISION,
               M.User.status == E.UserStatus.ACTIVE)
    ).scalar_one()


def assert_legal_authority_preserved(db: DBSession, previous_count: int) -> None:
    """SEC-05 as a *change* rule rather than an absolute one.

    Locked 47.5 r6 says "a configuration change **must not leave** the system with
    no user holding ``legal.decision``". A system that had none before the change
    was not left that way by it — refusing there would block every unrelated role
    edit on a freshly provisioned deployment, before the first Legal Decision
    Authority has been appointed.

    ``assert_legal_authority_remains`` keeps the absolute reading for callers that
    genuinely require a holder to exist.
    """
    if previous_count and count_legal_authorities(db) == 0:
        raise Forbidden(
            "refused: this change would leave no user able to make a Legal "
            "Decision (SEC-05)"
        )


def _role_permissions(db: DBSession, role_id: UUID) -> frozenset[str]:
    rows = db.execute(
        select(M.Permission.name)
        .join(M.RolePermission, M.RolePermission.permission_id == M.Permission.id)
        .where(M.RolePermission.role_id == role_id)
    ).scalars().all()
    return frozenset(rows)
