"""Tier-4 authorization tests — RELEASE-BLOCKING per Step 54.4.

Locked 41.24: "A user must never be able to access another user's Contract,
Document Version, Review, Finding, or Legal Decision merely by changing an ID
in an API request."
"""

from __future__ import annotations

import uuid

import pytest

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.security.authorization import (
    authorize_evaluation_operation,
    authorize_review_operation,
    can_see_review,
    redact_legal_position,
    require_review_visible,
)
from legalmind.security.errors import Forbidden, NotVisible, Unauthenticated
from legalmind.security.guards import (
    assert_legal_authority_remains,
    require_can_administer_user,
    require_can_grant_role,
)
from legalmind.security.resolver import (
    assert_no_bypass_reaches_legal_authority,
    effective_permissions,
    has_permission,
    holds_legal_decision_authority,
)
from tests.conftest import grant_role, make_evaluation, make_finding, make_review_for, make_user


# =====================================================================
# SEC-02 — the single most important control in Step 47
# =====================================================================
def test_super_admin_has_no_legal_decision_authority(db, seeded):
    """Locked Step 23: "Super Admin — No automatic Legal Decision authority".

    "A Super Admin without that Legal permission cannot approve the
    customization merely because they are a Super Admin."
    """
    sa = make_user(db)
    grant_role(db, sa, P.ROLE_SUPER_ADMIN)

    assert has_permission(db, sa.id, P.PLATFORM_MANAGE) is True
    assert has_permission(db, sa.id, P.USER_MANAGE) is True

    assert has_permission(db, sa.id, P.LEGAL_DECISION) is False
    assert has_permission(db, sa.id, P.LEGAL_APPROVE_CUSTOMIZATION) is False
    assert holds_legal_decision_authority(db, sa.id) is False


def test_super_admin_has_no_legal_content_access(db, seeded):
    """Locked Step 24 r8 — no automatic access to confidential Legal content."""
    sa = make_user(db)
    grant_role(db, sa, P.ROLE_SUPER_ADMIN)
    assert has_permission(db, sa.id, P.LEGAL_POSITION_VIEW) is False
    assert has_permission(db, sa.id, P.REVIEW_VIEW) is False


def test_super_admin_cannot_reach_another_users_review(db, seeded):
    """Step 24 r8 + 41.24 — platform administration is not content access."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    sa = make_user(db)
    grant_role(db, sa, P.ROLE_SUPER_ADMIN)

    assert can_see_review(db, sa.id, review) is False
    with pytest.raises(NotVisible):
        require_review_visible(db, sa.id, review.id)


def test_legal_review_does_not_confer_legal_decision(db, seeded):
    """SEC-05 — Step 23: decisions only "when explicitly permitted"."""
    reviewer = make_user(db)
    grant_role(db, reviewer, P.ROLE_LEGAL_REVIEWER)
    assert has_permission(db, reviewer.id, P.LEGAL_REVIEW) is True
    assert has_permission(db, reviewer.id, P.LEGAL_DECISION) is False


def test_legal_admin_does_not_get_legal_decision(db, seeded):
    admin = make_user(db)
    grant_role(db, admin, P.ROLE_LEGAL_ADMIN)
    assert has_permission(db, admin.id, P.CONFIGURATION_PUBLISH) is True
    assert has_permission(db, admin.id, P.LEGAL_DECISION) is False


def test_no_bypass_may_reach_legal_authority(db):
    """Defence in depth: if a bypass is ever added it cannot reach legal.*."""
    with pytest.raises(AssertionError, match="SEC-02 violated"):
        assert_no_bypass_reaches_legal_authority({P.PLATFORM_MANAGE, P.LEGAL_DECISION})
    assert_no_bypass_reaches_legal_authority({P.PLATFORM_MANAGE, P.USER_MANAGE})


# =====================================================================
# SEC-03 — multi-role union; how Step 4's two Admins differ
# =====================================================================
def test_legal_authority_via_additional_role(db, seeded):
    """Locked Step 4: Admin A and Admin B hold the same primary role and differ
    in legal approval authority. Under the locked many-to-many user_roles that
    is an ADDITIONAL role assignment."""
    admin_a = make_user(db)
    grant_role(db, admin_a, P.ROLE_LEGAL_ADMIN)

    admin_b = make_user(db)
    grant_role(db, admin_b, P.ROLE_LEGAL_ADMIN)
    grant_role(db, admin_b, P.ROLE_LEGAL_DECISION_AUTHORITY)

    assert holds_legal_decision_authority(db, admin_a.id) is False
    assert holds_legal_decision_authority(db, admin_b.id) is True
    # identical in every other respect
    a = effective_permissions(db, admin_a.id)
    b = effective_permissions(db, admin_b.id)
    assert b - a == P.LEGAL_AUTHORITY_PERMISSIONS


def test_permissions_are_the_union_of_roles(db, seeded):
    u = make_user(db)
    grant_role(db, u, P.ROLE_USER)
    grant_role(db, u, P.ROLE_LEGAL_REVIEWER)
    perms = effective_permissions(db, u.id)
    assert P.REVIEW_CREATE in perms       # from USER
    assert P.LEGAL_REVIEW in perms        # from LEGAL_REVIEWER


def test_permission_revocation_takes_effect_immediately(db, seeded):
    """S-1 — authority is resolved fresh per request, never cached in a session."""
    from sqlalchemy import select
    u = make_user(db)
    role = grant_role(db, u, P.ROLE_USER)
    assert has_permission(db, u.id, P.REVIEW_CREATE) is True

    perm = db.execute(select(M.Permission)
                      .where(M.Permission.name == P.REVIEW_CREATE)).scalar_one()
    db.execute(M.RolePermission.__table__.delete().where(
        (M.RolePermission.role_id == role.id)
        & (M.RolePermission.permission_id == perm.id)))
    db.flush()
    assert has_permission(db, u.id, P.REVIEW_CREATE) is False


# =====================================================================
# SEC-06 / 41.24 — object-level authorization (IDOR matrix)
# =====================================================================
def test_owner_can_see_own_review(db, seeded):
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = make_review_for(db, owner)
    assert can_see_review(db, owner.id, review) is True


def test_other_user_cannot_see_review_by_id(db, seeded):
    """Step 24 r4 — no access by default, even with review.view granted."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    other = make_user(db)
    grant_role(db, other, P.ROLE_USER)          # has review.view
    assert has_permission(db, other.id, P.REVIEW_VIEW) is True
    with pytest.raises(NotVisible):
        require_review_visible(db, other.id, review.id)


def test_legal_reviewer_needs_assignment(db, seeded):
    """Step 24 r6 — access by assignment, not by role name (r12)."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    reviewer = make_user(db)
    grant_role(db, reviewer, P.ROLE_LEGAL_REVIEWER)

    with pytest.raises(NotVisible):
        require_review_visible(db, reviewer.id, review.id)

    db.add(M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                              assigned_by=owner.id))
    db.flush()
    assert can_see_review(db, reviewer.id, review) is True


def test_assignment_does_not_transfer_ownership(db, seeded):
    """Step 24 r16/r17 — Legal access is not business ownership."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    reviewer = make_user(db)
    db.add(M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                              assigned_by=owner.id))
    db.flush()
    assert review.created_by == owner.id
    assert can_see_review(db, owner.id, review) is True


def test_revoked_assignment_removes_access(db, seeded):
    from datetime import datetime, timezone
    owner = make_user(db)
    review = make_review_for(db, owner)
    reviewer = make_user(db)
    a = M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                           assigned_by=owner.id)
    db.add(a); db.flush()
    assert can_see_review(db, reviewer.id, review) is True
    a.revoked_at = datetime.now(timezone.utc)
    db.flush()
    assert can_see_review(db, reviewer.id, review) is False


def test_traversal_evaluation_to_review_ownership(db, seeded, requirement_version):
    """SEC-06 — Evaluation -> Finding -> Review -> owner. Knowing an evaluation
    id grants nothing."""
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = make_review_for(db, owner)
    f = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, f)

    assert authorize_evaluation_operation(
        db, owner.id, ev.id, P.EVALUATION_VIEW).id == ev.id

    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    with pytest.raises(NotVisible):
        authorize_evaluation_operation(db, stranger.id, ev.id, P.EVALUATION_VIEW)


def test_unknown_and_invisible_are_both_not_visible(db, seeded):
    """SEC-07 / 49.5 r1 — the two must be indistinguishable to the caller."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    stranger = make_user(db)

    with pytest.raises(NotVisible) as invisible:
        require_review_visible(db, stranger.id, review.id)
    with pytest.raises(NotVisible) as unknown:
        require_review_visible(db, stranger.id, uuid.uuid4())

    assert type(invisible.value) is type(unknown.value)
    assert invisible.value.status_code == unknown.value.status_code == 404
    assert invisible.value.code == unknown.value.code


def test_visible_object_missing_permission_is_forbidden_not_not_found(db, seeded):
    """SEC-07 — 403 only once the object is known to be visible."""
    owner = make_user(db)
    review = make_review_for(db, owner)   # owner, but no roles granted
    with pytest.raises(Forbidden):
        authorize_review_operation(db, owner.id, review.id, P.REVIEW_VIEW)


def test_object_scope_is_checked_before_permission(db, seeded):
    """43.23 ordering — permission level must never reveal existence.

    A stranger WITHOUT review.view and a stranger WITH review.view must both
    get 404, never 403, or the response would leak that the object exists.
    """
    owner = make_user(db)
    review = make_review_for(db, owner)
    with_perm = make_user(db); grant_role(db, with_perm, P.ROLE_USER)
    without_perm = make_user(db)

    for uid in (with_perm.id, without_perm.id):
        with pytest.raises(NotVisible):
            authorize_review_operation(db, uid, review.id, P.REVIEW_VIEW)


# =====================================================================
# LEGAL-02 — confidentiality
# =====================================================================
def test_legal_position_omitted_not_nulled(db, seeded):
    """49.7 r5 / Step 52.4 — a null would still signal that a value exists."""
    payload = {"classification": "DEVIATION", "rule_outcome": "UNACCEPTABLE",
               "expected_value": {"months": 6}, "scope_key": "AGGREGATE"}
    permitted = redact_legal_position(dict(payload), True)
    assert permitted["rule_outcome"] == "UNACCEPTABLE"

    denied = redact_legal_position(dict(payload), False)
    assert "rule_outcome" not in denied
    assert "expected_value" not in denied
    assert denied["classification"] == "DEVIATION"
    assert denied["scope_key"] == "AGGREGATE"


# =====================================================================
# S-8 / S-9 — escalation guards
# =====================================================================
def test_cannot_grant_authority_one_does_not_hold(db, seeded):
    """S-8 — the vulnerability the external reference describes, in LegalMind's
    terms: any admin able to grant the highest privilege through an ordinary
    edit form."""
    from sqlalchemy import select
    legal_admin = make_user(db)
    grant_role(db, legal_admin, P.ROLE_LEGAL_ADMIN)
    authority_role = db.execute(
        select(M.Role).where(M.Role.code == P.ROLE_LEGAL_DECISION_AUTHORITY)
    ).scalar_one()

    with pytest.raises(Forbidden, match="escalation refused"):
        require_can_grant_role(db, legal_admin.id, authority_role.id)


def test_holder_may_grant_authority_they_hold(db, seeded):
    from sqlalchemy import select
    holder = make_user(db)
    grant_role(db, holder, P.ROLE_LEGAL_ADMIN)
    grant_role(db, holder, P.ROLE_LEGAL_DECISION_AUTHORITY)
    authority_role = db.execute(
        select(M.Role).where(M.Role.code == P.ROLE_LEGAL_DECISION_AUTHORITY)
    ).scalar_one()
    require_can_grant_role(db, holder.id, authority_role.id)   # no raise


def test_guard_covers_editing_a_more_privileged_account(db, seeded):
    """S-9 — the hole the external project admits to. Not inherited here."""
    weaker = make_user(db)
    grant_role(db, weaker, P.ROLE_SUPER_ADMIN)      # user.manage, no legal.*

    stronger = make_user(db)
    grant_role(db, stronger, P.ROLE_LEGAL_DECISION_AUTHORITY)

    with pytest.raises(Forbidden, match="escalation refused"):
        require_can_administer_user(db, weaker.id, stronger.id)


def test_self_administration_is_permitted(db, seeded):
    u = make_user(db)
    grant_role(db, u, P.ROLE_USER)
    require_can_administer_user(db, u.id, u.id)     # no raise


# =====================================================================
# SEC-05 — never zero legal authorities
# =====================================================================
def test_refuses_to_leave_zero_legal_authorities(db, seeded):
    with pytest.raises(Forbidden, match="no user able to make a Legal Decision"):
        assert_legal_authority_remains(db)

    holder = make_user(db)
    grant_role(db, holder, P.ROLE_LEGAL_DECISION_AUTHORITY)
    assert_legal_authority_remains(db)               # no raise
