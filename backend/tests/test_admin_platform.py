"""The Platform Administration surface — RELEASE-BLOCKING, in the spirit of 54.4.

The administrator manages **identities, access and departments** and nothing
else. Two halves, and the second matters more than the first:

```text
CAN     accounts, status, roles, departments, membership, audit
CANNOT  a contract, a document, a finding, a report, a conversation —
        not one, not by any route, not because they can read the audit trail
```

Every assertion goes through HTTP. Where the administrator must not reach
something, the answer is 404 for an object outside their scope and 403 for an
operation they lack — never a hidden button (rule 18: UI gating is presentation
only, so it proves nothing).

RBAC itself is frozen (AB-12). Nothing here grants, widens or renames anything;
these tests pin the administration EXPERIENCE built on top of that model.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
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
)

V1 = "/api/v1"


# ---------------------------------------------------------------- fixtures
def _department(db, code, name=None):
    d = M.Department(code=code, name=name or code.title())
    db.add(d)
    db.flush()
    return d


def _person(db, role, department=None, *, name=None, status=E.UserStatus.ACTIVE):
    user = make_user(db, status=status)
    if name:
        user.name = name
    grant_role(db, user, role)
    if department is not None:
        user.department_id = department.id
    db.flush()
    return user


@pytest.fixture
def org(db, seeded, requirement_version):
    sales = _department(db, "SALES", "Sales")
    ops = _department(db, "OPS", "Operations")
    admin = _person(db, P.ROLE_PLATFORM_ADMIN, name="Platform Admin")
    neha = _person(db, P.ROLE_DEPARTMENT_LEAD, sales, name="Neha Sharma")
    aman = _person(db, P.ROLE_USER, sales, name="Aman Singh")
    rahul = _person(db, P.ROLE_USER, sales, name="Rahul Verma",
                    status=E.UserStatus.DISABLED)
    priya = _person(db, P.ROLE_USER, ops, name="Priya Nair")
    nobody = _person(db, P.ROLE_USER, None, name="Zoe Unplaced")

    review = make_review_for(db, aman)
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding)
    return {"sales": sales, "ops": ops, "admin": admin, "neha": neha, "aman": aman,
            "rahul": rahul, "priya": priya, "nobody": nobody, "review": review,
            "finding": finding, "evaluation": evaluation,
            "contract_id": review.contract_id,
            "version_id": review.document_version_id}


def _rows(response):
    return response.json()["data"]


# =====================================================================
# The roster — what an administrator can actually see about an account
# =====================================================================
def test_the_roster_reports_every_field_the_screen_shows(api, db, org):
    """No invented data: each of these comes from a table LegalMind already
    keeps, and `last_login_at`/`auth_providers` come from `user_identities`,
    which is stamped by both the password and OIDC sign-in paths."""
    db.add(M.UserIdentity(user_id=org["aman"].id,
                          provider=E.IdentityProvider.PASSWORD,
                          provider_subject=org["aman"].email,
                          credential_hash=hash_password("x" * 12),
                          last_used_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()
    sign_in(api, db, org["admin"])

    row = next(u for u in _rows(api.get(f"{V1}/users?page_size=100"))
               if u["id"] == str(org["aman"].id))

    assert row["name"] == "Aman Singh"
    assert row["email"] == org["aman"].email
    assert row["roles"] == [P.ROLE_USER]
    assert row["department"]["code"] == "SALES"
    assert row["status"] == "ACTIVE"
    assert row["auth_providers"] == ["PASSWORD"]
    assert row["last_login_at"] is not None
    assert row["created_at"] and row["updated_at"]


def test_an_account_that_has_never_signed_in_says_so_rather_than_guessing(api, db, org):
    sign_in(api, db, org["admin"])
    row = next(u for u in _rows(api.get(f"{V1}/users?page_size=100"))
               if u["id"] == str(org["nobody"].id))
    assert row["last_login_at"] is None
    assert row["auth_providers"] == [], "no credential provisioned yet is a real state"


def test_no_endpoint_returns_credential_material(api, db, org):
    """S-4 — the hash is never selected, so it cannot be filtered out by mistake."""
    db.add(M.UserIdentity(user_id=org["aman"].id,
                          provider=E.IdentityProvider.PASSWORD,
                          provider_subject=org["aman"].email,
                          credential_hash=hash_password("secret-passphrase")))
    db.flush()
    sign_in(api, db, org["admin"])
    for url in (f"{V1}/users?page_size=100", f"{V1}/users/{org['aman'].id}",
                f"{V1}/departments/{org['sales'].id}"):
        body = api.get(url).text
        assert "credential_hash" not in body
        assert "$argon2" not in body and "pbkdf2" not in body


def test_who_provisioned_an_account_comes_from_the_audit_trail(api, db, org):
    sign_in(api, db, org["admin"])
    created = api.post(f"{V1}/users", json={"email": "new@leapswitch.test",
                                            "name": "New Joiner"})
    assert created.status_code == 201
    row = api.get(f"{V1}/users/{created.json()['data']['id']}").json()["data"]
    assert row["provisioned_by"]["id"] == str(org["admin"].id)
    # An account the seed made carries no creation event, and says nothing
    # rather than attributing it to someone.
    assert api.get(f"{V1}/users/{org['aman'].id}").json()["data"]["provisioned_by"] is None


# =====================================================================
# Filtering and sorting — in SQL, over the whole roster
# =====================================================================
def test_the_roster_filters_by_role_department_status_and_the_unplaced(api, db, org):
    sign_in(api, db, org["admin"])

    leads = _rows(api.get(f"{V1}/users?role={P.ROLE_DEPARTMENT_LEAD}&page_size=100"))
    assert [u["name"] for u in leads] == ["Neha Sharma"]

    sales = _rows(api.get(f"{V1}/users?department_id={org['sales'].id}&page_size=100"))
    assert {u["name"] for u in sales} == {"Neha Sharma", "Aman Singh", "Rahul Verma"}

    disabled = _rows(api.get(f"{V1}/users?status=DISABLED&page_size=100"))
    assert [u["name"] for u in disabled] == ["Rahul Verma"]

    # "In no department" is not a department id, and it is the question that
    # matters: nobody's Lead can see this person's deals.
    unplaced = _rows(api.get(f"{V1}/users?unassigned=true&page_size=100"))
    assert {u["name"] for u in unplaced} >= {"Zoe Unplaced", "Platform Admin"}
    assert "Aman Singh" not in {u["name"] for u in unplaced}


def test_a_filter_searches_the_whole_roster_not_the_current_page(api, db, org):
    """The defect class this exists to prevent: filtering the 25 rows already
    fetched instead of the collection. Page size 1 makes it unmissable."""
    sign_in(api, db, org["admin"])
    response = api.get(f"{V1}/users?role={P.ROLE_DEPARTMENT_LEAD}&page_size=1")
    assert response.json()["pagination"]["total"] == 1
    assert _rows(response)[0]["name"] == "Neha Sharma"


def test_sorting_is_an_allow_list_and_actually_orders(api, db, org):
    sign_in(api, db, org["admin"])
    names = [u["name"] for u in _rows(api.get(f"{V1}/users?sort=name_asc&page_size=100"))]
    assert names == sorted(names)
    assert [u["name"] for u in _rows(
        api.get(f"{V1}/users?sort=name_desc&page_size=100"))] == sorted(names, reverse=True)
    # An unknown sort is refused rather than silently ignored — a silently
    # ignored sort is what made the old screen's control decorative.
    assert api.get(f"{V1}/users?sort=; DROP TABLE users").status_code == 422


def test_never_signed_in_sorts_last_not_first(api, db, org):
    db.add(M.UserIdentity(user_id=org["aman"].id,
                          provider=E.IdentityProvider.PASSWORD,
                          provider_subject=org["aman"].email,
                          last_used_at=datetime.now(UTC)))
    db.flush()
    sign_in(api, db, org["admin"])
    rows = _rows(api.get(f"{V1}/users?sort=last_login_desc&page_size=100"))
    assert rows[0]["name"] == "Aman Singh"
    assert rows[-1]["last_login_at"] is None


# =====================================================================
# Account lifecycle
# =====================================================================
def test_an_account_can_be_created_placed_and_granted_in_one_audited_act(api, db, org):
    sign_in(api, db, org["admin"])
    response = api.post(f"{V1}/users", json={
        "email": "Fresh.Joiner@Leapswitch.test", "name": "Fresh Joiner",
        "department_id": str(org["sales"].id), "role_code": P.ROLE_USER})

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["email"] == "fresh.joiner@leapswitch.test", "email is normalised"
    assert body["department"]["code"] == "SALES"
    assert body["roles"] == [P.ROLE_USER]
    actions = {e.action for e in db.query(M.AuditEvent).all()}
    assert {"admin.user_created", A.ADMIN_ROLE_GRANTED} <= actions


def test_creation_still_refuses_a_role_the_administrator_does_not_hold(api, db, org):
    """S-8 runs BEFORE the account exists, so a refusal leaves nothing behind —
    the whole point of doing it in one transaction (43.26)."""
    sign_in(api, db, org["admin"])
    response = api.post(f"{V1}/users", json={
        "email": "wouldbe@leapswitch.test", "name": "Would Be",
        "role_code": P.ROLE_LEGAL_DECISION_AUTHORITY})

    assert response.status_code == 403
    db.expire_all()
    assert db.execute(select(M.User).where(
        M.User.email == "wouldbe@leapswitch.test")).first() is None


def test_creation_refuses_an_unknown_department_or_role(api, db, org):
    sign_in(api, db, org["admin"])
    assert api.post(f"{V1}/users", json={
        "email": "a@leapswitch.test", "name": "A",
        "department_id": str(uuid.uuid4())}).status_code == 422
    assert api.post(f"{V1}/users", json={
        "email": "b@leapswitch.test", "name": "B",
        "role_code": "NOT_A_ROLE"}).status_code == 422


def test_a_duplicate_email_is_a_conflict(api, db, org):
    sign_in(api, db, org["admin"])
    assert api.post(f"{V1}/users", json={
        "email": org["aman"].email, "name": "Impostor"}).status_code == 409


def test_status_and_department_changes_round_trip_and_are_audited(api, db, org):
    sign_in(api, db, org["admin"])
    moved = api.patch(f"{V1}/users/{org['priya'].id}",
                      json={"department_id": str(org["sales"].id)})
    assert moved.json()["data"]["department"]["code"] == "SALES"

    cleared = api.patch(f"{V1}/users/{org['priya'].id}", json={"department_id": None})
    assert cleared.json()["data"]["department"] is None

    disabled = api.patch(f"{V1}/users/{org['priya'].id}", json={"status": "DISABLED"})
    assert disabled.json()["data"]["status"] == "DISABLED"
    assert api.patch(f"{V1}/users/{org['priya'].id}",
                     json={"status": "ACTIVE"}).json()["data"]["status"] == "ACTIVE"
    assert "admin.user_updated" in {e.action for e in db.query(M.AuditEvent).all()}


def test_disabling_an_account_revokes_its_sessions_immediately(api, db, org):
    """S-2 — a disabled account must not keep working for the rest of a session."""
    victim_session = None
    from legalmind.security.sessions import create_session
    victim_session = create_session(db, org["priya"])
    sign_in(api, db, org["admin"])

    api.patch(f"{V1}/users/{org['priya'].id}", json={"status": "DISABLED"})

    db.expire_all()
    assert db.get(M.UserSession, victim_session.id).revoked_at is not None


# =====================================================================
# Departments
# =====================================================================
def test_a_department_reports_its_lead_and_member_counts(api, db, org):
    sign_in(api, db, org["admin"])
    rows = {d["code"]: d for d in _rows(api.get(f"{V1}/departments?page_size=100"))}

    sales = rows["SALES"]
    assert sales["members"] == 3
    assert sales["active_members"] == 2, "Rahul is DISABLED"
    assert [lead["name"] for lead in sales["leads"]] == ["Neha Sharma"]
    assert rows["OPS"]["leads"] == [], "a department may legitimately have no lead"


def test_a_department_detail_lists_its_members_as_accounts(api, db, org):
    sign_in(api, db, org["admin"])
    body = api.get(f"{V1}/departments/{org['sales'].id}").json()["data"]
    assert {u["name"] for u in body["member_accounts"]} == {
        "Neha Sharma", "Aman Singh", "Rahul Verma"}
    assert body["members"] == 3
    assert api.get(f"{V1}/departments/{uuid.uuid4()}").status_code == 404


def test_a_department_can_be_renamed_but_never_recoded(api, db, org):
    sign_in(api, db, org["admin"])
    renamed = api.patch(f"{V1}/departments/{org['sales'].id}",
                        json={"name": "Sales & Partnerships"})
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "Sales & Partnerships"
    assert renamed.json()["data"]["code"] == "SALES"
    # The code identifies the boundary in an append-only trail: not editable.
    assert api.patch(f"{V1}/departments/{org['sales'].id}",
                     json={"code": "NEWCODE"}).status_code == 422
    assert A.ADMIN_DEPARTMENT_UPDATED in {e.action for e in db.query(M.AuditEvent).all()}


def test_a_duplicate_department_code_is_a_conflict(api, db, org):
    sign_in(api, db, org["admin"])
    assert api.post(f"{V1}/departments",
                    json={"code": "sales", "name": "Dup"}).status_code == 409


# =====================================================================
# Roles & permissions
# =====================================================================
def test_the_permission_catalogue_is_grouped_and_marks_legal_authority(api, db, org):
    sign_in(api, db, org["admin"])
    body = api.get(f"{V1}/permissions").json()["data"]
    groups = {g["group"]: g["permissions"] for g in body["groups"]}

    assert set(groups) == set(P.CATALOGUE)
    flat = {p["name"]: p for group in groups.values() for p in group}
    assert set(flat) == set(P.ALL_PERMISSIONS)
    assert flat[P.LEGAL_DECISION]["confers_legal_authority"] is True
    assert flat[P.REPORT_VIEW]["confers_legal_authority"] is False


def test_roles_are_served_with_tier_and_legal_authority_marked(api, db, org):
    sign_in(api, db, org["admin"])
    roles = {r["code"]: r for r in _rows(api.get(f"{V1}/roles?page_size=100"))}
    assert roles[P.ROLE_USER]["tier"] == "department"
    assert roles[P.ROLE_LEGAL_DECISION_AUTHORITY]["tier"] == "future_legal"
    assert roles[P.ROLE_LEGAL_DECISION_AUTHORITY]["confers_legal_authority"] == sorted(
        P.LEGAL_AUTHORITY_PERMISSIONS)
    assert roles[P.ROLE_PLATFORM_ADMIN]["confers_legal_authority"] == []


def test_the_administrator_cannot_grant_or_construct_legal_authority(api, db, org):
    """S-8 by both routes — granting the role, and editing a role to carry it."""
    sign_in(api, db, org["admin"])
    assert api.post(f"{V1}/users/{org['aman'].id}/roles",
                    json={"role_code": P.ROLE_LEGAL_DECISION_AUTHORITY}
                    ).status_code == 403

    plain = bespoke_role(db, f"PLAIN{uuid.uuid4().hex[:4]}", [P.REPORT_VIEW])
    assert api.patch(f"{V1}/roles/{plain.id}",
                     json={"permissions": [P.REPORT_VIEW, P.LEGAL_DECISION]}
                     ).status_code == 403
    db.expire_all()
    assert P.LEGAL_DECISION not in set(db.execute(
        select(M.Permission.name)
        .join(M.RolePermission, M.RolePermission.permission_id == M.Permission.id)
        .where(M.RolePermission.role_id == plain.id)).scalars())


def test_the_administrator_may_appoint_a_lead(api, db, org):
    """DEPARTMENT_LEAD carries no S-8-guarded permission, so this is allowed —
    and it is the appointment that makes department scope real."""
    sign_in(api, db, org["admin"])
    assert api.post(f"{V1}/users/{org['aman'].id}/roles",
                    json={"role_code": P.ROLE_DEPARTMENT_LEAD}).status_code == 201


# =====================================================================
# Audit — who did what, to what, when
# =====================================================================
def test_administrative_events_name_their_actor_and_target(api, db, org):
    sign_in(api, db, org["admin"])
    api.post(f"{V1}/users", json={"email": "audited@leapswitch.test",
                                  "name": "Audited"})

    events = _rows(api.get(f"{V1}/audit-events?action=admin.user_created"))
    event = events[0]
    assert event["actor"]["email"] == org["admin"].email
    assert event["entity_label"] == "audited@leapswitch.test"
    assert event["administrative"] is True
    # The payload an administrator is answerable for is legible to them.
    assert event["after_state"]["email"] == "audited@leapswitch.test"


def test_the_administrative_filter_and_the_payload_gate_agree(api, db, org):
    sign_in(api, db, org["admin"])
    api.post(f"{V1}/departments", json={"code": "LEGAL", "name": "Legal"})

    rows = _rows(api.get(f"{V1}/audit-events?administrative=true&page_size=100"))
    assert rows, "the administrator's own acts must be findable"
    for row in rows:
        assert row["administrative"] is True
        assert row["action"].startswith(("admin.", "auth."))
        # Everything the filter returns is a payload this caller may read.
        assert "after_state" in row


def test_contract_payloads_stay_hidden_from_the_platform_admin(api, db, org):
    """The line that matters: a Platform Admin reads the audit trail and still
    cannot learn a contract's name or a Lead's transfer reason from it (Step 24
    r8). The envelope is theirs; the payload is not."""
    from legalmind.security import audit as audit_module
    audit_module.record(
        db, action=audit_module.CONTRACT_OWNERSHIP_TRANSFERRED,
        entity_type="contract", entity_id=org["contract_id"],
        actor_id=org["neha"].id,
        before={"owner_id": str(org["aman"].id)},
        after={"owner_id": str(org["priya"].id),
               "reason": "Project Nightingale renegotiation"})
    audit_module.record(
        db, action=audit_module.CONTRACT_ARCHIVED, entity_type="contract",
        entity_id=org["contract_id"], actor_id=org["aman"].id,
        before={"name": "ACME Master Services Agreement"})
    db.flush()
    sign_in(api, db, org["admin"])

    body = api.get(f"{V1}/audit-events?entity_type=contract&page_size=100")
    assert body.status_code == 200
    assert "Project Nightingale" not in body.text
    assert "ACME Master Services Agreement" not in body.text
    for row in _rows(body):
        assert row["administrative"] is False
        assert "before_state" not in row, "omitted, never nulled"
        assert "after_state" not in row
        # The envelope still answers who/what/when — that is the auditor's job.
        assert row["entity_type"] == "contract" and row["entity_id"]
        assert row["entity_label"] is None, "a contract is never labelled here"


def test_the_audit_range_filter_narrows_by_time(api, db, org):
    sign_in(api, db, org["admin"])
    api.post(f"{V1}/users", json={"email": "timed@leapswitch.test", "name": "Timed"})
    # quote() because an ISO timestamp ends in `+00:00`, and a bare `+` in a
    # query string decodes as a space.
    future = quote((datetime.now(UTC) + timedelta(days=1)).isoformat())
    past = quote((datetime.now(UTC) - timedelta(days=1)).isoformat())

    assert _rows(api.get(f"{V1}/audit-events?since={future}")) == []
    assert _rows(api.get(f"{V1}/audit-events?since={past}")) != []
    assert _rows(api.get(f"{V1}/audit-events?until={past}")) == []


def test_a_user_can_be_traced_through_the_trail(api, db, org):
    """`entity_id` is what makes a per-account history possible without a new
    endpoint — the administration screen filters the existing one."""
    sign_in(api, db, org["admin"])
    api.patch(f"{V1}/users/{org['priya'].id}", json={"name": "Priya N."})
    rows = _rows(api.get(f"{V1}/audit-events?entity_id={org['priya'].id}"))
    assert rows and all(r["entity_id"] == str(org["priya"].id) for r in rows)


# =====================================================================
# THE BOUNDARY — administration is not content
# =====================================================================
def test_the_platform_admin_cannot_reach_one_piece_of_business_content(api, db, org):
    sign_in(api, db, org["admin"])
    # Collections: 403 — the permission is absent entirely.
    for url in (f"{V1}/contracts", f"{V1}/reviews", f"{V1}/conversations",
                f"{V1}/requirements"):
        assert api.get(url).status_code == 403, url
    # Objects: 404 — existence is itself a disclosure (SEC-07).
    for url in (f"{V1}/contracts/{org['contract_id']}",
                f"{V1}/reviews/{org['review'].id}",
                f"{V1}/reviews/{org['review'].id}/report",
                f"{V1}/reviews/{org['review'].id}/findings",
                f"{V1}/findings/{org['finding'].id}",
                f"{V1}/findings/{org['finding'].id}/evaluations",
                f"{V1}/document-versions/{org['version_id']}",
                f"{V1}/document-versions/{org['version_id']}/content",
                f"{V1}/document-versions/{org['version_id']}/evidence"):
        assert api.get(url).status_code in (403, 404), url


def test_the_platform_admin_cannot_read_a_private_conversation(api, db, org):
    """AB-12 r8 — administering the account that owns a conversation is not
    permission to read it. Managing identities is not reading what people said."""
    sign_in(api, db, org["aman"])
    created = api.post(f"{V1}/conversations",
                       json={"contract_id": str(org["contract_id"])})
    assert created.status_code == 201
    conversation_id = created.json()["data"]["id"]

    sign_in(api, db, org["admin"])
    assert api.get(f"{V1}/conversations/{conversation_id}").status_code == 403
    assert api.get(f"{V1}/conversations").status_code == 403


def test_the_platform_admin_cannot_transfer_or_archive_a_contract(api, db, org):
    sign_in(api, db, org["admin"])
    assert api.post(f"{V1}/contracts/{org['contract_id']}/transfer",
                    json={"new_owner_id": str(org["priya"].id),
                          "reason": "administrative"}).status_code in (403, 404)
    assert api.post(f"{V1}/contracts/{org['contract_id']}/archive"
                    ).status_code in (403, 404)


def test_managing_departments_confers_no_sight_of_their_deals(api, db, org):
    """The trap this closes: an administrator who can name a department, count
    its members and read its audit rows might be assumed to see its work."""
    sign_in(api, db, org["admin"])
    assert api.get(f"{V1}/departments/{org['sales'].id}").status_code == 200
    assert api.get(f"{V1}/contracts?scope=department").status_code == 403
    assert api.get(f"{V1}/contracts/{org['contract_id']}").status_code == 404


# =====================================================================
# THE OTHER SIDE — nobody else administers the platform
# =====================================================================
def test_a_department_user_reaches_no_administration_at_all(api, db, org):
    sign_in(api, db, org["aman"])
    for url in (f"{V1}/users", f"{V1}/roles", f"{V1}/permissions",
                f"{V1}/departments", f"{V1}/audit-events"):
        assert api.get(url).status_code == 403, url
    assert api.post(f"{V1}/users", json={"email": "x@y.test",
                                         "name": "X"}).status_code == 403
    assert api.patch(f"{V1}/users/{org['priya'].id}",
                     json={"status": "DISABLED"}).status_code == 403


def test_a_department_lead_oversees_deals_not_accounts(api, db, org):
    """AB-12 r3 gave the Lead department READ scope over contracts, and
    deliberately no account administration: they are not an administrator and
    must not have to become one."""
    sign_in(api, db, org["neha"])
    for url in (f"{V1}/users", f"{V1}/roles", f"{V1}/permissions",
                f"{V1}/departments", f"{V1}/audit-events"):
        assert api.get(url).status_code == 403, url
    # What they DO get is the transfer-target list, gated on `department.view`.
    members = api.get(f"{V1}/departments/mine/members")
    assert members.status_code == 200
    assert {m["name"] for m in members.json()["data"]["members"]} == {
        "Neha Sharma", "Aman Singh"}, "DISABLED members are not transfer targets"


def test_a_developer_administers_but_still_holds_no_legal_authority(api, db, org):
    """AB-12 r12 — break-glass reaches the admin surface and stops at legal
    authority, which is the whole distinction."""
    dev = _person(db, P.ROLE_DEVELOPER, org["sales"], name="Dev")
    sign_in(api, db, dev)
    assert api.get(f"{V1}/users").status_code == 200
    assert api.post(f"{V1}/evaluations/{org['evaluation'].id}/decisions",
                    json={"decision_type": "ACCEPT_DEVIATION",
                          "justification": "x" * 40}).status_code == 403
    assert api.post(f"{V1}/users/{org['aman'].id}/roles",
                    json={"role_code": P.ROLE_LEGAL_DECISION_AUTHORITY}
                    ).status_code == 403


def test_administration_needs_more_than_being_signed_in(api, db, org):
    """Every administration route is permission-gated, not merely authenticated
    — checked against a role holding exactly one unrelated permission."""
    stranger = make_user(db)
    grant(db, stranger, bespoke_role(db, f"NOBODY{uuid.uuid4().hex[:4]}",
                                     [P.CONTRACT_VIEW]))
    sign_in(api, db, stranger)
    for url in (f"{V1}/users", f"{V1}/roles", f"{V1}/permissions",
                f"{V1}/departments", f"{V1}/audit-events",
                f"{V1}/departments/mine/members"):
        assert api.get(url).status_code == 403, url
