"""API authorization and authentication — locked 41.24, 43.23, 47.1, 47.5–47.9.

The tests that matter most here are the ones about what a Super Admin *cannot*
do. Locked Step 23 says Super Admin has "No automatic Legal Decision authority"
and locked Step 24 r8 says a Super Admin "does not automatically have access to
confidential contract or Legal content". Both are asserted through the HTTP
surface, because that is where the external MoS reference's ``is_super`` pattern
would have leaked.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.security.passwords import hash_password
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
    sign_out,
)

V1 = "/api/v1"


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def owner(db, seeded):
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    return user


@pytest.fixture
def owned_review(db, owner):
    return make_review_for(db, owner)


@pytest.fixture
def finding_with_evaluation(db, owned_review, requirement_version):
    finding = make_finding(db, owned_review, requirement_version)
    evaluation = make_evaluation(
        db, finding, classification=E.FindingClassification.DEVIATION,
        rule_outcome=E.RuleOutcome.APPROVAL_REQUIRED)
    return finding, evaluation


def _legal_authority(db, *, also_customization: bool = True):
    """A user holding Legal Decision authority, assigned to nothing yet.

    Locked Step 24 r6 means authority alone is not access: they still need an
    assignment to see a Review, which is the point of several tests below.
    """
    user = make_user(db)
    grant_role(db, user, P.ROLE_LEGAL_REVIEWER)
    perms = [P.LEGAL_DECISION]
    if also_customization:
        perms.append(P.LEGAL_APPROVE_CUSTOMIZATION)
    grant(db, user, bespoke_role(db, f"AUTH_{user.id.hex[:6]}", perms))
    return user


def _assign(db, review, user, by):
    db.add(M.ReviewAssignment(review_id=review.id, user_id=user.id,
                              assigned_by=by.id))
    db.flush()


# =====================================================================
# 47.7 / 41.24 — out of scope is 404, not 403
# =====================================================================
def test_another_users_contract_is_404_not_403(api, db, owner):
    stranger = make_user(db)
    hidden = M.Contract(owner_id=stranger.id, name="Their MSA",
                        status=E.ContractStatus.ACTIVE)
    db.add(hidden); db.flush()

    sign_in(api, db, owner)
    response = api.get(f"{V1}/contracts/{hidden.id}")
    assert response.status_code == 404


def test_another_users_review_findings_and_evaluations_are_all_404(
        api, db, owner, requirement_version):
    """47.6 — the traversal Evaluation → Finding → Review → Contract → owner.
    Changing an id at any level of it is a 404 (41.24)."""
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    hidden_review = make_review_for(db, stranger)
    hidden_finding = make_finding(db, hidden_review, requirement_version)
    hidden_evaluation = make_evaluation(db, hidden_finding)

    sign_in(api, db, owner)
    for path in (f"{V1}/reviews/{hidden_review.id}",
                 f"{V1}/reviews/{hidden_review.id}/findings",
                 f"{V1}/reviews/{hidden_review.id}/report",
                 f"{V1}/findings/{hidden_finding.id}",
                 f"{V1}/findings/{hidden_finding.id}/evaluations",
                 f"{V1}/evaluations/{hidden_evaluation.id}/decisions"):
        assert api.get(path).status_code == 404, path


def test_a_list_never_leaks_what_a_get_would_404_on(api, db, owner):
    """49.6 — "a list never leaks an object a GET would 404 on". A leak here
    would be the same defect as an IDOR, arriving by a different route."""
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    hidden = make_review_for(db, stranger)
    mine = make_review_for(db, owner)

    sign_in(api, db, owner)
    body = api.get(f"{V1}/reviews", params={"page_size": 100}).json()
    ids = {item["id"] for item in body["data"]}
    assert str(mine.id) in ids
    assert str(hidden.id) not in ids


def test_the_list_scope_agrees_with_can_see_review(api, db, owner):
    """The list query and ``can_see_review`` are two implementations of locked
    Step 24; if they ever disagree, one of them is a disclosure."""
    from legalmind.security.authorization import can_see_review

    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    assigned = make_review_for(db, stranger)
    _assign(db, assigned, owner, stranger)
    make_review_for(db, stranger)               # neither owned nor assigned
    make_review_for(db, owner)

    sign_in(api, db, owner)
    listed = {item["id"] for item in
              api.get(f"{V1}/reviews", params={"page_size": 100}).json()["data"]}
    every = db.execute(select(M.Review)).scalars().all()
    expected = {str(r.id) for r in every if can_see_review(db, owner.id, r)}
    assert listed == expected
    assert str(assigned.id) in listed           # r5/r6 — assignment grants access


# =====================================================================
# 43.23 — object scope before operation permission
# =====================================================================
def test_visible_object_without_permission_is_403(api, db, owner, owned_review):
    """47.7 — "object is visible; user lacks the operation permission" → 403."""
    reader = make_user(db)
    grant(db, reader, bespoke_role(db, "SCOPED_ONLY", [P.REVIEW_VIEW]))
    _assign(db, owned_review, reader, owner)

    sign_in(api, db, reader)
    # Visible via assignment, but report.view was never granted.
    assert api.get(f"{V1}/reviews/{owned_review.id}").status_code == 200
    assert api.get(f"{V1}/reviews/{owned_review.id}/report").status_code == 403


def test_invisible_object_is_404_even_with_every_permission(api, db, owner):
    """Object scope is resolved first, so permission level never reveals
    existence."""
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    hidden = make_review_for(db, stranger)

    everything = make_user(db)
    grant(db, everything, bespoke_role(db, "EVERYTHING", P.ALL_PERMISSIONS))
    sign_in(api, db, everything)
    assert api.get(f"{V1}/reviews/{hidden.id}/report").status_code == 404


def test_denials_are_audited(api, db, owner, owned_review):
    """SEC-09 / 47.9 — a refusal is recorded even though the request aborts."""
    sign_in(api, db, owner)
    api.get(f"{V1}/audit-events")

    event = db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.action == "authz.permission_denied")
    ).scalars().first()
    assert event is not None
    assert event.actor_id == owner.id
    assert event.after_state["permission"] == P.AUDIT_VIEW


def test_probing_an_invisible_object_is_audited(api, db, owner):
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    hidden = make_review_for(db, stranger)

    sign_in(api, db, owner)
    api.get(f"{V1}/reviews/{hidden.id}")

    event = db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.action == "authz.object_not_visible")
    ).scalars().first()
    assert event is not None
    assert event.entity_id == hidden.id


# =====================================================================
# SEC-02 / ROLE-05 — the Super Admin boundary, over HTTP
# =====================================================================
def test_super_admin_cannot_see_a_review(api, db, owner, owned_review):
    """Locked Step 24 r8. Platform administration is not contract access, so the
    answer is 404 — a Super Admin does not even learn the Review exists."""
    admin = make_user(db)
    grant_role(db, admin, P.ROLE_SUPER_ADMIN)
    sign_in(api, db, admin)
    assert api.get(f"{V1}/reviews/{owned_review.id}").status_code == 404


def test_super_admin_cannot_record_a_decision(api, db, owner,
                                              finding_with_evaluation):
    """Locked Step 23 — a Super Admin without that Legal permission cannot
    approve the customization merely because they are a Super Admin."""
    _, evaluation = finding_with_evaluation
    admin = make_user(db)
    grant_role(db, admin, P.ROLE_SUPER_ADMIN)
    _assign(db, db.get(M.Review, db.get(M.Finding, evaluation.finding_id).review_id),
            admin, owner)

    sign_in(api, db, admin)
    response = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                        json={"decision_type": "ACCEPT_DEVIATION",
                              "justification": "administratively convenient"})
    assert response.status_code == 403
    assert db.execute(select(M.LegalDecision)).first() is None


def test_legal_review_does_not_confer_legal_decision(api, db, owner,
                                                     finding_with_evaluation):
    """47.5 r2 — Step 23: "Make Legal Decisions **when explicitly permitted**"."""
    finding, evaluation = finding_with_evaluation
    reviewer = make_user(db)
    grant_role(db, reviewer, P.ROLE_LEGAL_REVIEWER)
    _assign(db, db.get(M.Review, finding.review_id), reviewer, owner)

    sign_in(api, db, reviewer)
    response = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                        json={"decision_type": "ACCEPT_DEVIATION",
                              "justification": "reviewed and accepted"})
    assert response.status_code == 403
    assert P.LEGAL_REVIEW in {
        p for p in api.get(f"{V1}/auth/session").json()["data"]["permissions"]}


def test_approve_customization_needs_the_additional_grant(
        api, db, owner, finding_with_evaluation):
    """49.3 / 47.5 — ``legal.approve_customization`` is required *in addition to*
    ``legal.decision``. A holder of only the latter can accept a deviation but
    cannot approve a customization."""
    finding, evaluation = finding_with_evaluation
    decider = _legal_authority(db, also_customization=False)
    _assign(db, db.get(M.Review, finding.review_id), decider, owner)

    sign_in(api, db, decider)
    refused = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                       json={"decision_type": "APPROVE_CUSTOMIZATION",
                             "justification": "bespoke wording agreed"})
    assert refused.status_code == 403

    allowed = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                       json={"decision_type": "ACCEPT_DEVIATION",
                             "justification": "within tolerance as advised"})
    assert allowed.status_code == 201


def test_legal_authority_without_assignment_still_cannot_reach_the_review(
        api, db, owner, finding_with_evaluation):
    """Locked Step 24 r6 — Legal access is by assignment. Authority is not
    access, and the refusal is 404 so the Review's existence stays private."""
    _, evaluation = finding_with_evaluation
    decider = _legal_authority(db)
    sign_in(api, db, decider)
    response = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                        json={"decision_type": "ACCEPT_DEVIATION",
                              "justification": "..."})
    assert response.status_code == 404


# =====================================================================
# 47.1 — authentication
# =====================================================================
def _password_user(db, email, password, *, status=E.UserStatus.ACTIVE):
    user = M.User(email=email, name="Fallback User", status=status)
    db.add(user); db.flush()
    db.add(M.UserIdentity(user_id=user.id, provider=E.IdentityProvider.PASSWORD,
                          credential_hash=hash_password(password)))
    db.flush()
    return user


def test_password_login_establishes_a_session(api, db, seeded):
    user = _password_user(db, "fallback@example.test", "correct horse battery")
    grant_role(db, user, P.ROLE_USER)

    response = api.post(f"{V1}/auth/login",
                        json={"email": "fallback@example.test",
                              "password": "correct horse battery"})
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["user_id"] == str(user.id)
    assert P.REVIEW_VIEW in body["permissions"]
    # SEC-01 — the session id travels only in an HttpOnly cookie.
    assert "session_id" not in body
    set_cookie = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie and "Secure" in set_cookie


def test_no_endpoint_returns_credential_material(api, db, seeded):
    """S-4 — excluded at the repository layer, not by response filtering."""
    user = _password_user(db, "fallback2@example.test", "a very long password")
    grant_role(db, user, P.ROLE_SUPER_ADMIN)
    sign_in(api, db, user)

    for path in (f"{V1}/auth/session", f"{V1}/users", f"{V1}/users/{user.id}"):
        raw = api.get(path).text
        assert "credential_hash" not in raw
        assert "scrypt$" not in raw


def test_unknown_wrong_and_disabled_are_byte_identical(api, db, seeded):
    """S-7 / 47.1.1 r3 — identical responses for unknown account, wrong
    credential and disabled account. Any difference is account enumeration."""
    _password_user(db, "real@example.test", "the right password")
    _password_user(db, "off@example.test", "the right password",
                   status=E.UserStatus.DISABLED)

    attempts = [
        {"email": "nobody@example.test", "password": "whatever"},
        {"email": "real@example.test", "password": "the wrong password"},
        {"email": "off@example.test", "password": "the right password"},
    ]
    bodies = []
    for attempt in attempts:
        response = api.post(f"{V1}/auth/login", json=attempt)
        assert response.status_code == 401
        body = response.json()
        body["error"]["request_id"] = "-"
        bodies.append(json.dumps(body, sort_keys=True))
        assert "set-cookie" not in response.headers
    assert len(set(bodies)) == 1


def test_failed_login_records_no_submitted_email(api, db, seeded):
    """47.9 — "failed-login records must not become an enumeration oracle in any
    surfaced view". The safest way to guarantee that is never to record it."""
    api.post(f"{V1}/auth/login",
             json={"email": "probe@example.test", "password": "x"})
    events = db.execute(
        select(M.AuditEvent).where(M.AuditEvent.action == "auth.login_failed")
    ).scalars().all()
    assert events
    for event in events:
        assert event.actor_id is None
        assert "probe@example.test" not in json.dumps(
            [event.before_state, event.after_state, event.event_metadata])


def test_logout_revokes_immediately(api, db, seeded):
    """SEC-01 / S-2 — revocation is immediate, not on expiry."""
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    session = sign_in(api, db, user)

    assert api.post(f"{V1}/auth/logout").status_code == 200
    # The cookie jar is cleared by the response, so present it again explicitly:
    # the server must refuse it regardless of what the client still holds.
    from legalmind.api.context import SESSION_COOKIE
    api.cookies.set(SESSION_COOKIE, str(session.id))
    assert api.get(f"{V1}/auth/session").status_code == 401


def test_authority_revoked_mid_session_takes_effect_on_the_next_request(
        api, db, seeded, requirement_version):
    """S-1 — nothing about what a user MAY DO is trusted from the session.

    This is the property that makes server-side sessions worth their cost, and
    the reason the stateless-JWT model was rejected (47.1.2).
    """
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(
        db, finding, rule_outcome=E.RuleOutcome.APPROVAL_REQUIRED)

    decider = _legal_authority(db)
    _assign(db, review, decider, owner)
    sign_in(api, db, decider)

    first = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                     json={"decision_type": "REQUEST_CLARIFICATION",
                           "justification": "need the schedule"})
    assert first.status_code == 201

    authority_role = db.execute(
        select(M.Role).where(M.Role.code.like("AUTH_%"))
    ).scalars().first()
    db.execute(
        M.UserRole.__table__.delete().where(
            M.UserRole.user_id == decider.id,
            M.UserRole.role_id == authority_role.id))
    db.flush()

    second = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                      json={"decision_type": "ACCEPT_DEVIATION",
                            "justification": "resolved after clarification"})
    assert second.status_code == 403


def test_session_endpoint_reports_permissions_for_presentation_only(
        api, db, seeded):
    """43.31 / 47.6 r3 — the array drives UI gating and nothing else. Holding it
    changes no server-side answer, which is what the next two lines assert."""
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    sign_in(api, db, user)

    body = api.get(f"{V1}/auth/session").json()["data"]
    assert P.AUDIT_VIEW not in body["permissions"]
    assert api.get(f"{V1}/audit-events").status_code == 403


def test_signed_out_client_gets_401_not_403(api, db, seeded):
    user = make_user(db)
    grant_role(db, user, P.ROLE_SUPER_ADMIN)
    sign_in(api, db, user)
    assert api.get(f"{V1}/audit-events").status_code == 200
    sign_out(api)
    assert api.get(f"{V1}/audit-events").status_code == 401
