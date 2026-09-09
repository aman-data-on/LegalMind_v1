"""The AB-12 persona matrix — RELEASE-BLOCKING, in the spirit of Step 54.4.

Four people, as the owner described them on 2026-09-05:

```text
Aman, Rahul    Department Users in SALES — each runs their own deals
Neha           Department Lead of SALES — her own deals, plus every SALES deal
Priya          a Department User in OPS — another department entirely
Platform admin accounts and departments, never contract content
Developer      break-glass, never legal authority
```

Every assertion here goes through the HTTP surface, because that is where the
rule has to hold. Where a persona must NOT see something, the answer is 404 —
never 403 — so that permission level never reveals existence (SEC-07).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from legalmind.api.permission_map import ENDPOINT_PERMISSIONS
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
from legalmind.security import permissions as P
from tests.conftest import (
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
)

V1 = "/api/v1"


# ---------------------------------------------------------------- fixtures
def _department(db, code):
    d = M.Department(code=code, name=code.title())
    db.add(d)
    db.flush()
    return d


def _person(db, role, department=None, *, name=None):
    user = make_user(db)
    if name:
        user.name = name
    grant_role(db, user, role)
    if department is not None:
        user.department_id = department.id
    db.flush()
    return user


@pytest.fixture
def org(db, seeded, requirement_version):
    sales = _department(db, "SALES")
    ops = _department(db, "OPS")
    aman = _person(db, P.ROLE_USER, sales, name="Aman")
    rahul = _person(db, P.ROLE_USER, sales, name="Rahul")
    neha = _person(db, P.ROLE_DEPARTMENT_LEAD, sales, name="Neha")
    priya = _person(db, P.ROLE_USER, ops, name="Priya")
    admin = _person(db, P.ROLE_PLATFORM_ADMIN, name="Platform Admin")
    dev = _person(db, P.ROLE_DEVELOPER, sales, name="Developer")

    review = make_review_for(db, aman)              # Aman -> Client X
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding)
    priyas_review = make_review_for(db, priya)      # Priya -> Client Z

    return {"sales": sales, "ops": ops, "aman": aman, "rahul": rahul, "neha": neha,
            "priya": priya, "admin": admin, "dev": dev, "review": review,
            "finding": finding, "evaluation": evaluation,
            "contract_id": review.contract_id,
            "version_id": review.document_version_id,
            "priyas_review": priyas_review}


def _reads(contract_id, version_id, review, finding, evaluation):
    """Every read surface anchored on one contract, in one place."""
    return [
        f"{V1}/contracts/{contract_id}",
        f"{V1}/document-versions/{version_id}",
        f"{V1}/document-versions/{version_id}/evidence",
        f"{V1}/document-versions/{version_id}/content",
        f"{V1}/reviews/{review.id}",
        f"{V1}/reviews/{review.id}/findings",
        f"{V1}/reviews/{review.id}/report",
        f"{V1}/findings/{finding.id}",
        f"{V1}/findings/{finding.id}/evaluations",
        f"{V1}/evaluations/{evaluation.id}/decisions",
    ]


def _conversation_on(api, contract_id):
    return api.post(f"{V1}/conversations", json={"contract_id": str(contract_id)})


# =====================================================================
# Department User — own deals, and nothing else exists
# =====================================================================
def test_a_department_user_reaches_every_surface_of_their_own_deal(api, db, org):
    sign_in(api, db, org["aman"])
    for url in _reads(org["contract_id"], org["version_id"], org["review"],
                      org["finding"], org["evaluation"]):
        status = api.get(url).status_code
        # `/content` 404s here only because the fixture stored no bytes.
        assert status == 200 or url.endswith("/content"), (url, status)
    assert _conversation_on(api, org["contract_id"]).status_code == 201


def test_a_department_user_sees_why_their_finding_is_what_it_is(api, db, org):
    """AB-12 r7 — MATCH / DEVIATION / MISSING must be understandable to the
    person whose deal it is: the expected value and the explanation are present."""
    sign_in(api, db, org["aman"])
    body = api.get(f"{V1}/findings/{org['finding'].id}").json()["data"]
    evaluation = body["evaluations"][0]
    for field in ("rule_outcome", "expected_value", "comparison", "explanation"):
        assert field in evaluation, field


def test_a_colleagues_deal_does_not_exist_for_a_department_user(api, db, org):
    """Rahul is in the same department as Aman and still gets 404 on every
    surface of Aman's deal — department membership widens nothing without
    `department.view`."""
    sign_in(api, db, org["rahul"])
    for url in _reads(org["contract_id"], org["version_id"], org["review"],
                      org["finding"], org["evaluation"]):
        assert api.get(url).status_code == 404, url
    assert _conversation_on(api, org["contract_id"]).status_code == 404
    listed = {row["id"] for row in api.get(f"{V1}/contracts").json()["data"]}
    assert str(org["contract_id"]) not in listed
    reviews = {row["id"] for row in api.get(f"{V1}/reviews").json()["data"]}
    assert str(org["review"].id) not in reviews


def test_a_foreign_id_and_a_nonexistent_id_are_byte_identical(api, db, org):
    """The enumeration oracle SEC-07 forbids: the body for someone else's
    contract must equal the body for a contract that never existed."""
    sign_in(api, db, org["rahul"])
    foreign = api.get(f"{V1}/contracts/{org['contract_id']}")
    nowhere = api.get(f"{V1}/contracts/{uuid.uuid4()}")
    assert foreign.status_code == nowhere.status_code == 404
    # Identical apart from the per-request correlation id (49.9).
    def strip(response):
        return {k: v for k, v in response.json()["error"].items() if k != "request_id"}
    assert strip(foreign) == strip(nowhere)


def test_a_department_user_cannot_transfer_change_standards_or_destroy(api, db, org):
    sign_in(api, db, org["aman"])
    # Transfer: the contract is visible (it is Aman's), the operation is not theirs.
    assert api.post(f"{V1}/contracts/{org['contract_id']}/transfer",
                    json={"new_owner_id": str(org["rahul"].id),
                          "reason": "handing over"}).status_code == 403
    # Standards: no `configuration.*` at all.
    assert api.get(f"{V1}/requirements").status_code == 403
    assert api.post(f"{V1}/requirements", json={"code": "X-1"}).status_code == 403
    # Destroy: Aman OWNS this contract, so DELETE is his to use (AM-55) — that
    # capability, and its refusal for a non-owner, are covered in
    # test_contract_archive.py, not a permission boundary this test asserts.
    # Accounts: not theirs either.
    assert api.get(f"{V1}/users").status_code == 403
    assert api.get(f"{V1}/departments/mine/members").status_code == 403


def test_department_scope_is_refused_to_a_department_user(api, db, org):
    sign_in(api, db, org["rahul"])
    assert api.get(f"{V1}/contracts?scope=department").status_code == 403
    assert api.get(f"{V1}/contracts/summary?scope=department").status_code == 403


# =====================================================================
# Department Lead — her own deals plus every SALES deal, read-only
# =====================================================================
def test_the_lead_reads_every_surface_of_a_department_deal(api, db, org):
    sign_in(api, db, org["neha"])
    for url in _reads(org["contract_id"], org["version_id"], org["review"],
                      org["finding"], org["evaluation"]):
        status = api.get(url).status_code
        assert status == 200 or url.endswith("/content"), (url, status)
    # And may ask about it — the conversation is hers alone (r8).
    assert _conversation_on(api, org["contract_id"]).status_code == 201


def test_the_department_list_holds_the_departments_deals_and_names_their_owners(
        api, db, org):
    neha_review = make_review_for(db, org["neha"])
    sign_in(api, db, org["neha"])

    own = {row["id"] for row in api.get(f"{V1}/contracts").json()["data"]}
    assert own == {str(neha_review.contract_id)}

    department = api.get(f"{V1}/contracts?scope=department").json()["data"]
    ids = {row["id"] for row in department}
    assert ids == {str(org["contract_id"]), str(neha_review.contract_id)}
    assert {row["owner_name"] for row in department} == {"Aman", "Neha"}
    assert str(org["priyas_review"].contract_id) not in ids, "OPS is another department"

    summary = api.get(f"{V1}/contracts/summary?scope=department").json()["data"]
    assert summary["total"] == 2

    reviews = {row["id"] for row in api.get(f"{V1}/reviews").json()["data"]}
    assert org["review"].id.__str__() in reviews
    assert str(org["priyas_review"].id) not in reviews


def test_another_departments_deal_does_not_exist_for_the_lead(api, db, org):
    """AB-12 r3 — "never globally". Neha holds `department.view` and Priya's
    deal is still a 404 on every surface."""
    sign_in(api, db, org["neha"])
    priyas = org["priyas_review"]
    assert api.get(f"{V1}/contracts/{priyas.contract_id}").status_code == 404
    assert api.get(f"{V1}/reviews/{priyas.id}").status_code == 404
    assert api.get(f"{V1}/document-versions/{priyas.document_version_id}").status_code == 404
    assert _conversation_on(api, priyas.contract_id).status_code == 404


def test_the_lead_cannot_write_to_a_colleagues_deal(api, db, org):
    """Reads widen to the department; writes never do. To act on Aman's deal,
    Neha takes ownership first (an audited transfer) — so "who may change this
    contract" always has a one-word answer."""
    sign_in(api, db, org["neha"])
    cid = org["contract_id"]
    assert api.patch(f"{V1}/contracts/{cid}", json={"name": "renamed"}).status_code == 404
    assert api.post(f"{V1}/contracts/{cid}/document-versions", content=b"%PDF-1.4 x",
                    headers={"content-type": "application/pdf",
                             "x-filename": "x.pdf"}).status_code == 404
    assert api.post(f"{V1}/contracts/{cid}/archive").status_code == 404
    assert api.post(f"{V1}/reviews/{org['review'].id}/analyze").status_code == 404
    # Existence hidden, not merely refused (47.7) — 404, same as every other
    # write above, not a 405: the route exists, this caller just can't see it.
    assert api.delete(f"{V1}/contracts/{cid}").status_code == 404
    db.expire_all()
    assert db.get(M.Contract, cid).name != "renamed"


def test_the_lead_never_sees_a_colleagues_ask_history(api, db, org):
    """AB-12 r8 — the contract is a business record; the conversation is the
    asker's own. Neha reads every document in SALES and not one of Aman's
    questions about them."""
    sign_in(api, db, org["aman"])
    conversation_id = _conversation_on(api, org["contract_id"]).json()["data"]["id"]

    sign_in(api, db, org["neha"])
    assert api.get(f"{V1}/conversations/{conversation_id}").status_code == 404
    listed = {row["id"] for row in api.get(f"{V1}/conversations").json()["data"]}
    assert conversation_id not in listed
    filtered = api.get(f"{V1}/conversations?contract_id={org['contract_id']}").json()["data"]
    assert conversation_id not in {row["id"] for row in filtered}


def test_a_cross_owner_read_by_the_lead_is_audited_with_its_basis(api, db, org):
    sign_in(api, db, org["neha"])
    api.get(f"{V1}/contracts/{org['contract_id']}")
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.CONTRACT_READ_VIA_DEPARTMENT_SCOPE)).scalars().one()
    assert event.actor_id == org["neha"].id
    assert event.entity_id == org["contract_id"]
    assert event.after_state["basis"] == "department"
    assert event.after_state["owner_id"] == str(org["aman"].id)


def test_the_lead_manages_the_standards_and_a_user_does_not(api, db, org):
    sign_in(api, db, org["neha"])
    assert api.get(f"{V1}/requirements").status_code == 200
    created = api.post(f"{V1}/requirements", json={"code": f"LEAD-{uuid.uuid4().hex[:4]}"})
    assert created.status_code == 201
    assert ("POST", f"{V1}/configuration/publish") in ENDPOINT_PERMISSIONS
    assert ENDPOINT_PERMISSIONS[("POST", f"{V1}/configuration/publish")] == P.CONFIGURATION_PUBLISH
    assert P.CONFIGURATION_PUBLISH in P.DEFAULT_ROLE_GRANTS[P.ROLE_DEPARTMENT_LEAD]
    assert P.CONFIGURATION_PUBLISH not in P.DEFAULT_ROLE_GRANTS[P.ROLE_USER]


def test_a_lead_in_no_department_sees_only_her_own_deals(api, db, org):
    """The permission alone widens nothing — there must be a department to be
    scoped to. The safe direction for an account nobody has placed yet."""
    org["neha"].department_id = None
    db.flush()
    sign_in(api, db, org["neha"])
    assert api.get(f"{V1}/contracts/{org['contract_id']}").status_code == 404
    assert api.get(f"{V1}/contracts?scope=department").json()["data"] == []
    assert api.get(f"{V1}/departments/mine/members").json()["data"] == {
        "department": None, "members": []}


def test_the_lead_holds_no_global_legal_scope(db, seeded):
    """`legal.review` widens to every escalated Review on the platform (`REC-09`)
    — exactly the "sees everything globally" AB-12 r3 forbids."""
    assert P.LEGAL_REVIEW not in P.DEFAULT_ROLE_GRANTS[P.ROLE_DEPARTMENT_LEAD]
    assert not set(P.DEFAULT_ROLE_GRANTS[P.ROLE_DEPARTMENT_LEAD]) & P.LEGAL_AUTHORITY_PERMISSIONS


# =====================================================================
# Ownership transfer — AB-12 r5
# =====================================================================
def test_the_lead_transfers_a_deal_and_every_consequence_follows(api, db, org):
    # Aman asked a question about his deal before handing it over.
    sign_in(api, db, org["aman"])
    conversation_id = _conversation_on(api, org["contract_id"]).json()["data"]["id"]

    sign_in(api, db, org["neha"])
    members = api.get(f"{V1}/departments/mine/members").json()["data"]
    assert {m["name"] for m in members["members"]} >= {"Aman", "Rahul", "Neha"}
    assert "Priya" not in {m["name"] for m in members["members"]}

    response = api.post(f"{V1}/contracts/{org['contract_id']}/transfer",
                        json={"new_owner_id": str(org["rahul"].id),
                              "reason": "Aman on leave for two weeks"})
    assert response.status_code == 200
    assert response.json()["data"]["owner_id"] == str(org["rahul"].id)
    assert response.json()["data"]["owner_name"] == "Rahul"

    # The audit row: previous owner, new owner, actor, reason, contract, time.
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.CONTRACT_OWNERSHIP_TRANSFERRED)).scalars().one()
    assert event.entity_id == org["contract_id"]
    assert event.actor_id == org["neha"].id
    assert event.before_state == {"owner_id": str(org["aman"].id)}
    assert event.after_state["owner_id"] == str(org["rahul"].id)
    assert event.after_state["reason"] == "Aman on leave for two weeks"
    assert event.timestamp is not None

    # Rahul now has the deal, its versions, its analysis history — and may write.
    sign_in(api, db, org["rahul"])
    for url in _reads(org["contract_id"], org["version_id"], org["review"],
                      org["finding"], org["evaluation"]):
        status = api.get(url).status_code
        assert status == 200 or url.endswith("/content"), (url, status)
    assert api.patch(f"{V1}/contracts/{org['contract_id']}",
                     json={"name": "Client X (Rahul)"}).status_code == 200
    # But not Aman's questions.
    assert api.get(f"{V1}/conversations/{conversation_id}").status_code == 404

    # Aman lost the deal and its history...
    sign_in(api, db, org["aman"])
    assert api.get(f"{V1}/contracts/{org['contract_id']}").status_code == 404
    assert api.get(f"{V1}/reviews/{org['review'].id}").status_code == 404
    # ...and keeps his own Ask history, which is his, not the contract's.
    assert api.get(f"{V1}/conversations/{conversation_id}").status_code == 200
    # He can no longer ask NEW questions about a document he cannot read.
    assert api.post(f"{V1}/conversations/{conversation_id}/messages",
                    json={"question": "still mine?"}).status_code == 404


def test_transfer_is_bounded_by_the_department(api, db, org):
    sign_in(api, db, org["neha"])
    # Out of the department: refused, with the same message as a nonexistent user.
    to_priya = api.post(f"{V1}/contracts/{org['contract_id']}/transfer",
                        json={"new_owner_id": str(org["priya"].id), "reason": "no"})
    to_nobody = api.post(f"{V1}/contracts/{org['contract_id']}/transfer",
                         json={"new_owner_id": str(uuid.uuid4()), "reason": "no"})
    assert to_priya.status_code == to_nobody.status_code == 422
    assert to_priya.json()["error"]["message"] == to_nobody.json()["error"]["message"]
    # Another department's deal: not visible, so not transferable — 404.
    assert api.post(f"{V1}/contracts/{org['priyas_review'].contract_id}/transfer",
                    json={"new_owner_id": str(org["rahul"].id),
                          "reason": "no"}).status_code == 404
    # To a disabled colleague: refused.
    org["rahul"].status = E.UserStatus.DISABLED
    db.flush()
    assert api.post(f"{V1}/contracts/{org['contract_id']}/transfer",
                    json={"new_owner_id": str(org["rahul"].id),
                          "reason": "no"}).status_code == 422
    db.expire_all()
    assert db.get(M.Contract, org["contract_id"]).owner_id == org["aman"].id


def test_transfer_requires_a_reason(api, db, org):
    sign_in(api, db, org["neha"])
    assert api.post(f"{V1}/contracts/{org['contract_id']}/transfer",
                    json={"new_owner_id": str(org["rahul"].id)}).status_code == 422


# =====================================================================
# Platform Admin — accounts and departments, never content
# =====================================================================
def test_the_platform_admin_manages_accounts_and_departments(api, db, org):
    sign_in(api, db, org["admin"])
    assert api.get(f"{V1}/users").status_code == 200
    created = api.post(f"{V1}/departments", json={"code": "legal", "name": "Legal"})
    assert created.status_code == 201
    department_id = created.json()["data"]["id"]
    assert created.json()["data"]["code"] == "LEGAL"

    moved = api.patch(f"{V1}/users/{org['priya'].id}", json={"department_id": department_id})
    assert moved.status_code == 200
    assert moved.json()["data"]["department"]["code"] == "LEGAL"
    cleared = api.patch(f"{V1}/users/{org['priya'].id}", json={"department_id": None})
    assert cleared.json()["data"]["department"] is None
    assert api.patch(f"{V1}/users/{org['priya'].id}",
                     json={"department_id": str(uuid.uuid4())}).status_code == 422
    assert {e.action for e in db.query(M.AuditEvent).all()} >= {
        A.ADMIN_DEPARTMENT_CREATED, "admin.user_updated"}


def test_the_platform_admin_has_no_business_visibility(api, db, org):
    """Step 24 r8/r9 — an administrator can place people in departments and
    still cannot open one deal in any of them."""
    sign_in(api, db, org["admin"])
    assert api.get(f"{V1}/contracts/{org['contract_id']}").status_code == 404
    assert api.get(f"{V1}/reviews/{org['review'].id}").status_code == 404
    assert api.get(f"{V1}/contracts").status_code == 403       # no contract.view at all
    assert api.get(f"{V1}/contracts?scope=department").status_code == 403


def test_the_platform_admin_appoints_a_lead_but_never_legal_authority(api, db, org):
    """S-8: an administrator may grant what they hold. DEPARTMENT_LEAD carries no
    guarded permission, so appointing a Lead works; LEGAL_DECISION_AUTHORITY does,
    so it is refused — the administrator holds no `legal.decision` to hand out."""
    sign_in(api, db, org["admin"])
    assert api.post(f"{V1}/users/{org['rahul'].id}/roles",
                    json={"role_code": P.ROLE_DEPARTMENT_LEAD}).status_code == 201
    assert api.post(f"{V1}/users/{org['rahul'].id}/roles",
                    json={"role_code": P.ROLE_LEGAL_DECISION_AUTHORITY}).status_code == 403


def test_roles_are_served_with_their_tier(api, db, org):
    sign_in(api, db, org["admin"])
    roles = {r["code"]: r for r in api.get(f"{V1}/roles?page_size=100").json()["data"]}
    assert roles[P.ROLE_USER]["tier"] == "department"
    assert roles[P.ROLE_DEPARTMENT_LEAD]["tier"] == "department"
    assert roles[P.ROLE_PLATFORM_ADMIN]["tier"] == "platform"
    assert roles[P.ROLE_DEVELOPER]["tier"] == "break_glass"
    assert roles[P.ROLE_LEGAL_REVIEWER]["tier"] == "future_legal"
    assert roles[P.ROLE_LEGAL_DECISION_AUTHORITY]["tier"] == "future_legal"
    assert roles[P.ROLE_USER]["name"] == "Department User"


def test_the_session_names_the_callers_department(api, db, org):
    sign_in(api, db, org["neha"])
    identity = api.get(f"{V1}/auth/session").json()["data"]
    assert identity["department"]["code"] == "SALES"
    assert P.DEPARTMENT_VIEW in identity["permissions"]


# =====================================================================
# Developer — break-glass, audited, no legal authority
# =====================================================================
def test_the_developer_holds_no_legal_authority(api, db, org):
    """AB-12 r12, correcting AB-9 r2: a debugging role that could rule on a
    contract is not a debugging role. Visible object, refused operation: 403."""
    assert not set(P.DEFAULT_ROLE_GRANTS[P.ROLE_DEVELOPER]) & P.LEGAL_AUTHORITY_PERMISSIONS
    sign_in(api, db, org["dev"])
    assert api.post(f"{V1}/evaluations/{org['evaluation'].id}/decisions",
                    json={"decision_type": "ACCEPT_DEVIATION",
                          "justification": "x" * 40}).status_code == 403


def test_a_break_glass_read_is_audited_like_any_other_cross_owner_read(api, db, org):
    """The Developer is in SALES for this fixture, so their read of Aman's deal
    arrives through department scope — and lands in the trail with that basis.
    A Developer in no department would get the same 404 as anyone else."""
    sign_in(api, db, org["dev"])
    assert api.get(f"{V1}/contracts/{org['contract_id']}").status_code == 200
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.CONTRACT_READ_VIA_DEPARTMENT_SCOPE,
        M.AuditEvent.actor_id == org["dev"].id)).scalars().one()
    assert event.after_state["basis"] == "department"

    org["dev"].department_id = None
    db.flush()
    assert api.get(f"{V1}/contracts/{org['contract_id']}").status_code == 404


# =====================================================================
# Standards history stays reproducible — the snapshot is on every Review
# =====================================================================
def test_a_review_names_the_configuration_it_was_evaluated_against(api, db, org):
    """Step 30 / AUD-04: publishing a new standard never mutates an existing
    Review, because each Review pins its configuration snapshot. That pin is on
    the wire, for the owner and the lead alike."""
    for who in (org["aman"], org["neha"]):
        sign_in(api, db, who)
        body = api.get(f"{V1}/reviews/{org['review'].id}").json()["data"]
        assert body["configuration_snapshot_id"] == str(org["review"].configuration_snapshot_id)
