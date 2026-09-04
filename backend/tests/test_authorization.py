"""Tier-4 authorization tests — RELEASE-BLOCKING per Step 54.4.

Locked 41.24: "A user must never be able to access another user's Contract,
Document Version, Review, Finding, or Legal Decision merely by changing an ID
in an API request."
"""

from __future__ import annotations

import uuid
from datetime import UTC

import pytest
from sqlalchemy import select

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
from legalmind.security.errors import Forbidden, NotVisible
from legalmind.security.guards import (
    assert_administrative_authority_preserved,
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
from tests.conftest import (
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
)


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
    from datetime import datetime
    owner = make_user(db)
    review = make_review_for(db, owner)
    reviewer = make_user(db)
    a = M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                           assigned_by=owner.id)
    db.add(a); db.flush()
    assert can_see_review(db, reviewer.id, review) is True
    a.revoked_at = datetime.now(UTC)
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


def test_guard_covers_deleting_a_more_privileged_account(db, seeded):
    """S-9 names deleting alongside editing. Deleting the account that holds
    `legal.decision` destroys that authority just as surely as editing it."""
    weaker = make_user(db)
    grant_role(db, weaker, P.ROLE_SUPER_ADMIN)      # user.manage, no legal.*

    stronger = make_user(db)
    grant_role(db, stronger, P.ROLE_LEGAL_DECISION_AUTHORITY)

    with pytest.raises(Forbidden, match="escalation refused"):
        require_can_administer_user(db, weaker.id, stronger.id)


def test_last_administrator_cannot_be_left_with_zero_admins(db, seeded):
    """Self-administration bypasses S-9's escalation check, but it must not be
    able to zero out ``user.manage`` — the last admin revoking their own admin
    role, or disabling their own account, would lock the org out permanently."""
    with pytest.raises(Forbidden, match="no user able to manage users or roles"):
        assert_administrative_authority_preserved(db, previous_count=1)

    holder = make_user(db)
    grant_role(db, holder, P.ROLE_SUPER_ADMIN)
    assert_administrative_authority_preserved(db, previous_count=1)   # no raise


def test_sole_admin_cannot_lock_the_org_out_over_http(api, db, seeded):
    """The whole journey, through the real routes: the last administrator
    cannot strip their own admin role or disable their own account.

    Guard-level tests prove the rule; this proves it is actually *reached* by
    the endpoints the Admin screen calls."""
    sole_admin = make_user(db)
    grant_role(db, sole_admin, P.ROLE_SUPER_ADMIN)
    sign_in(api, db, sole_admin)

    revoked = api.delete(
        f"/api/v1/users/{sole_admin.id}/roles/{P.ROLE_SUPER_ADMIN}")
    assert revoked.status_code == 403, revoked.text
    assert "manage users" in revoked.text

    disabled = api.patch(f"/api/v1/users/{sole_admin.id}",
                         json={"status": "DISABLED"})
    assert disabled.status_code == 403, disabled.text

    # ...and still holds the role, so the refusal did not half-apply.
    assert P.USER_MANAGE in effective_permissions(db, sole_admin.id)

    # With a second administrator present, both operations are permitted again.
    second = make_user(db)
    grant_role(db, second, P.ROLE_SUPER_ADMIN)
    assert api.delete(
        f"/api/v1/users/{sole_admin.id}/roles/{P.ROLE_SUPER_ADMIN}"
    ).status_code == 200


# =====================================================================
# SEC-05 — never zero legal authorities
# =====================================================================
def test_refuses_to_leave_zero_legal_authorities(db, seeded):
    with pytest.raises(Forbidden, match="no user able to make a Legal Decision"):
        assert_legal_authority_remains(db)

    holder = make_user(db)
    grant_role(db, holder, P.ROLE_LEGAL_DECISION_AUTHORITY)
    assert_legal_authority_remains(db)               # no raise


# =====================================================================
# REC-09 — "explicit Legal scope" (resolves F-6)
# =====================================================================
# Locked `REC-09` defines the term locked Step 24 r6 uses and no locked record
# defined. Before it, BOTH branches of r6 were unimplementable — nothing populates
# `review_assignments`, and "explicit Legal scope" had no criterion — so a Legal
# Reviewer could reach no Review at all while every Legal-workflow test passed
# through a fixture the product could not produce.
#
# Two conditions, each traceable to a locked rule, and neither implies the other.
def _legal_user(db, *, with_decision_authority=False):
    user = make_user(db)
    grant_role(db, user, P.ROLE_LEGAL_REVIEWER)
    if with_decision_authority:
        grant_role(db, user, P.ROLE_LEGAL_DECISION_AUTHORITY)
    return user


def _escalate(db, review, requirement_version, raised_by):
    finding = make_finding(db, review, requirement_version)
    make_evaluation(db, finding)
    db.add(M.Escalation(finding_id=finding.id, raised_by=raised_by.id,
                        reason="structural escalation for the test"))
    db.flush()
    return finding


def test_legal_scope_via_lifecycle_status(db, seeded):
    """`REC-09` (b) — Step 30's `LEGAL_REVIEW` means "one or more Findings require an
    authorized Legal decision", which the ENGINE derives with no human escalation."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    counsel = _legal_user(db)

    assert can_see_review(db, counsel.id, review) is False      # DRAFT: not in scope

    review.status = E.ReviewStatus.LEGAL_REVIEW
    db.flush()
    assert can_see_review(db, counsel.id, review) is True


def test_legal_scope_via_escalation_survives_resolution(db, seeded, requirement_version):
    """`REC-09` (a), and the reason (b) alone is insufficient.

    A user may escalate a Finding on a `RESOLVED` Review, and Step 30's state machine
    has **no `RESOLVED → LEGAL_REVIEW` edge** — so an escalation-only Review is never
    reachable through condition (b). Without (a), `ROLE-04`'s "this requires authorized
    review" would be unheard.
    """
    owner = make_user(db)
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.RESOLVED
    db.flush()
    counsel = _legal_user(db)

    assert can_see_review(db, counsel.id, review) is False
    _escalate(db, review, requirement_version, owner)
    assert can_see_review(db, counsel.id, review) is True
    # And the Review really is not in LEGAL_REVIEW — condition (a) is doing the work.
    assert review.status is E.ReviewStatus.RESOLVED


def test_withdrawing_the_escalation_removes_legal_scope(db, seeded, requirement_version):
    """Scope is a live property, not a one-way door — mirroring `AM-23`'s
    `withdrawn_at` and the revoked-assignment rule above."""
    from datetime import datetime

    owner = make_user(db)
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.RESOLVED
    db.flush()
    counsel = _legal_user(db)
    finding = _escalate(db, review, requirement_version, owner)
    assert can_see_review(db, counsel.id, review) is True

    escalation = db.execute(
        select(M.Escalation)
        .where(M.Escalation.finding_id == finding.id)).scalars().one()
    escalation.withdrawn_at = datetime.now(UTC)
    db.flush()
    assert can_see_review(db, counsel.id, review) is False


def test_legal_scope_requires_the_permission_not_the_status_alone(db, seeded):
    """Step 24 r12 — "permission + resource scope, not simply role name".

    An ordinary User does not gain access to someone else's Review because it entered
    `LEGAL_REVIEW`. The scope half is necessary and not sufficient.
    """
    owner = make_user(db)
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    db.flush()

    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    assert has_permission(db, stranger.id, P.LEGAL_REVIEW) is False
    assert can_see_review(db, stranger.id, review) is False
    with pytest.raises(NotVisible):
        require_review_visible(db, stranger.id, review.id)


def test_super_admin_still_gets_no_legal_content(db, seeded):
    """Step 24 r8 — unchanged by `REC-09`. `SUPER_ADMIN` holds no `legal.review`, so
    an in-scope Review stays invisible to it. The widening is to Legal, not to
    administration."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    db.flush()

    sa = make_user(db)
    grant_role(db, sa, P.ROLE_SUPER_ADMIN)
    assert can_see_review(db, sa.id, review) is False


def test_legal_scope_is_not_ownership(db, seeded):
    """Step 24 r16, r17 — access for Legal work, not business ownership.

    `REC-09` requires this rather than weakening it: the Review's owner is unchanged,
    the owner keeps access, and Legal scope does not reach the owner's OTHER Reviews.
    """
    owner = make_user(db)
    in_scope = make_review_for(db, owner)
    in_scope.status = E.ReviewStatus.LEGAL_REVIEW
    out_of_scope = make_review_for(db, owner)          # same owner, still DRAFT
    db.flush()
    counsel = _legal_user(db)

    assert can_see_review(db, counsel.id, in_scope) is True
    assert can_see_review(db, counsel.id, out_of_scope) is False
    assert in_scope.created_by == owner.id
    assert can_see_review(db, owner.id, in_scope) is True


def test_legal_scope_confers_no_decision_authority(db, seeded, requirement_version):
    """SEC-02 / SEC-05 / ROLE-05 — visibility is not authority.

    The distinction `REC-09` must not blur: a `legal.review` holder can now SEE the
    Evaluation, and `authorize_evaluation_operation` must still refuse
    `legal.decision`. A 403 rather than a 404 is the proof that the object was visible
    and the operation was refused (47.7).
    """
    owner = make_user(db)
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    db.flush()
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding)

    reviewer = _legal_user(db)                          # legal.review, NOT decision
    assert has_permission(db, reviewer.id, P.LEGAL_DECISION) is False
    # Visible for review work…
    authorize_evaluation_operation(db, reviewer.id, evaluation.id, P.EVALUATION_VIEW)
    # …and refused for deciding.
    with pytest.raises(Forbidden):
        authorize_evaluation_operation(db, reviewer.id, evaluation.id, P.LEGAL_DECISION)

    # A holder of the explicit grant is permitted — the workflow is reachable at last.
    authority = _legal_user(db, with_decision_authority=True)
    authorize_evaluation_operation(db, authority.id, evaluation.id, P.LEGAL_DECISION)


def test_findings_and_evaluations_follow_the_review_into_legal_scope(
        db, seeded, requirement_version):
    """SEC-06's traversal — Evaluation → Finding → Review. Nothing per-object was
    added by `REC-09`; the Finding and Evaluation become reachable because the Review
    did."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding)
    counsel = _legal_user(db)

    with pytest.raises(NotVisible):
        authorize_evaluation_operation(db, counsel.id, evaluation.id, P.EVALUATION_VIEW)

    review.status = E.ReviewStatus.LEGAL_REVIEW
    db.flush()
    authorize_evaluation_operation(db, counsel.id, evaluation.id, P.EVALUATION_VIEW)
    assert finding.review_id == review.id


def test_contract_access_is_unchanged_by_rec_09(db, seeded):
    """`REC-09` deliberately does not extend to Contracts or Documents — its own
    "What this does NOT settle" says so. Asserted here so a later change that widens
    Contract visibility has to be a deliberate decision rather than a side effect."""
    from legalmind.security.authorization import require_contract_visible

    owner = make_user(db)
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    db.flush()
    counsel = _legal_user(db)

    assert can_see_review(db, counsel.id, review) is True
    with pytest.raises(NotVisible):
        require_contract_visible(db, counsel.id, review.contract_id)


def test_legal_scope_ends_when_the_review_resolves(db, seeded, requirement_version):
    """A consequence of `REC-09` worth pinning, not a defect.

    When a Legal Decision resolves the last outstanding Evaluation, the Review advances
    `LEGAL_REVIEW → RESOLVED` (Step 30 r7/r16, `_advance_if_resolved`), and a RESOLVED
    Review with no active escalation is no longer in Legal scope. **So the Legal
    Reviewer who just decided immediately loses sight of the Review.**

    This is faithful to locked Step 24 r18 — "a resolved Review remains accessible to
    its owner according to the same ownership rules, while Legal access remains governed
    by Legal scope/assignment" — and it is asserted here rather than quietly widened,
    because widening `REC-09`'s definition would exceed what was approved. Reported to
    the owner as a follow-up they may wish to decide.
    """
    owner = make_user(db)
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    db.flush()
    counsel = _legal_user(db)
    assert can_see_review(db, counsel.id, review) is True

    review.status = E.ReviewStatus.RESOLVED
    db.flush()
    assert can_see_review(db, counsel.id, review) is False
    # r18's first half is unaffected: the owner keeps access.
    assert can_see_review(db, owner.id, review) is True
    # And an escalation would bring it back into scope — condition (a) is independent
    # of the lifecycle, which is exactly why REC-09 needs both.
    _escalate(db, review, requirement_version, owner)
    assert can_see_review(db, counsel.id, review) is True
