"""Contracts, documents, reviews, configuration, report and administration.

Locked references: 49.3, 49.6, 49.8, Step 29, Step 34, 42.4, 42.12, ENG-09,
F-8, F-9, S-8, S-9, S-10, SEC-05.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_review_for,
    make_user,
    sign_in,
)

V1 = "/api/v1"

DOCX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document")


@pytest.fixture
def owner(db, seeded):
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    return user


def build_docx(paragraphs: list[str]) -> bytes:
    import docx
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


# =====================================================================
# Contracts
# =====================================================================
def test_create_read_and_patch_a_contract(api, db, owner):
    sign_in(api, db, owner)
    created = api.post(f"{V1}/contracts",
                       json={"name": "ACME MSA", "contract_type": "MSA"})
    assert created.status_code == 201
    contract_id = created.json()["data"]["id"]
    assert created.json()["data"]["owner_id"] == str(owner.id)
    assert created.json()["data"]["status"] == "DRAFT"

    patched = api.patch(f"{V1}/contracts/{contract_id}",
                        json={"status": "ACTIVE"})
    assert patched.json()["data"]["status"] == "ACTIVE"
    assert api.get(f"{V1}/contracts/{contract_id}"
                   ).json()["data"]["name"] == "ACME MSA"


def test_put_is_not_accepted_on_a_contract(api, db, owner):
    """49.1 — PUT is not used, so it is not routed."""
    sign_in(api, db, owner)
    created = api.post(f"{V1}/contracts", json={"name": "ACME MSA"})
    contract_id = created.json()["data"]["id"]
    assert api.request("PUT", f"{V1}/contracts/{contract_id}",
                       json={"name": "x"}).status_code in {404, 405}


# =====================================================================
# Document upload and download — Step 34
# =====================================================================
def test_upload_produces_a_document_version_and_evidence(api, db, owner):
    sign_in(api, db, owner)
    contract_id = api.post(f"{V1}/contracts",
                           json={"name": "ACME MSA"}).json()["data"]["id"]

    response = api.post(
        f"{V1}/contracts/{contract_id}/document-versions",
        content=build_docx(["1. Limitation of Liability",
                            "Liability is capped at fees paid."]),
        headers={"Content-Type": DOCX_MIME, "X-Filename": "msa.docx"})
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["document_version"]["version_number"] == 1
    assert body["document_version"]["processing_status"] == "COMPLETED"
    assert body["evidence_count"] >= 1
    assert body["duplicate_of"] is None
    # Storage coordinates are never part of the resource.
    assert "storage_key" not in body["document_version"]


def test_upload_with_mismatched_magic_bytes_is_rejected(api, db, owner):
    """34.16 — the declared content type is a claim, not a fact. This is the case
    the sniffing exists for."""
    sign_in(api, db, owner)
    contract_id = api.post(f"{V1}/contracts",
                           json={"name": "ACME MSA"}).json()["data"]["id"]
    response = api.post(f"{V1}/contracts/{contract_id}/document-versions",
                        content=b"#!/bin/sh\nrm -rf /\n",
                        headers={"Content-Type": "application/pdf",
                                 "X-Filename": "not-really.pdf"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UPLOAD_REJECTED"
    assert db.execute(select(M.DocumentVersion)).first() is None


def test_reupload_reports_the_duplicate_rather_than_suppressing_it(api, db, owner):
    """34.5 / Step 33.9 — whether a re-upload is a new contractual version is a
    business decision, so the duplicate is reported, never silently dropped."""
    sign_in(api, db, owner)
    contract_id = api.post(f"{V1}/contracts",
                           json={"name": "ACME MSA"}).json()["data"]["id"]
    payload = build_docx(["1. Limitation of Liability"])
    headers = {"Content-Type": DOCX_MIME, "X-Filename": "msa.docx"}

    first = api.post(f"{V1}/contracts/{contract_id}/document-versions",
                     content=payload, headers=headers).json()["data"]
    second = api.post(f"{V1}/contracts/{contract_id}/document-versions",
                      content=payload, headers=headers).json()["data"]
    assert second["duplicate_of"] == first["document_version"]["id"]
    assert second["document_version"]["version_number"] == 2


def test_download_returns_the_preserved_original(api, db, owner):
    sign_in(api, db, owner)
    contract_id = api.post(f"{V1}/contracts",
                           json={"name": "ACME MSA"}).json()["data"]["id"]
    payload = build_docx(["1. Limitation of Liability"])
    version_id = api.post(
        f"{V1}/contracts/{contract_id}/document-versions", content=payload,
        headers={"Content-Type": DOCX_MIME, "X-Filename": "msa.docx"}
    ).json()["data"]["document_version"]["id"]

    response = api.get(f"{V1}/document-versions/{version_id}/content")
    assert response.status_code == 200
    # 34.2 / 34.5 — byte-for-byte the original.
    assert response.content == payload
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in response.headers["Content-Disposition"]


def test_download_is_a_permission_distinct_from_view(api, db, owner):
    sign_in(api, db, owner)
    contract_id = api.post(f"{V1}/contracts",
                           json={"name": "ACME MSA"}).json()["data"]["id"]
    version_id = api.post(
        f"{V1}/contracts/{contract_id}/document-versions",
        content=build_docx(["1. Liability"]),
        headers={"Content-Type": DOCX_MIME, "X-Filename": "msa.docx"}
    ).json()["data"]["document_version"]["id"]

    # A second identity owning nothing cannot even see it (41.24)...
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, stranger)
    assert api.get(f"{V1}/document-versions/{version_id}").status_code == 404

    # ...while the owner without document.download is refused the bytes but not
    # the metadata.
    narrow = bespoke_role(db, "VIEW_NOT_DOWNLOAD",
                          [P.CONTRACT_VIEW, P.DOCUMENT_VIEW])
    limited = make_user(db)
    grant(db, limited, narrow)
    contract = db.get(M.Contract, __import__("uuid").UUID(contract_id))
    contract.owner_id = limited.id
    db.flush()
    sign_in(api, db, limited)
    assert api.get(f"{V1}/document-versions/{version_id}").status_code == 200
    assert api.get(f"{V1}/document-versions/{version_id}/content"
                   ).status_code == 403


# =====================================================================
# Reviews — 49.8 idempotency
# =====================================================================
def test_review_creation_is_idempotent(api, db, owner):
    """49.8 — idempotent on ``(document_version_id, configuration_snapshot_id)``,
    so a retry cannot produce two Reviews of the same document against the same
    configuration (43.28)."""
    review = make_review_for(db, owner)
    sign_in(api, db, owner)
    body = {"document_version_id": str(review.document_version_id),
            "configuration_snapshot_id": str(review.configuration_snapshot_id)}

    first = api.post(f"{V1}/reviews", json=body)
    second = api.post(f"{V1}/reviews", json=body)
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert db.execute(
        select(M.Review).where(
            M.Review.document_version_id == review.document_version_id)
    ).scalars().all().__len__() == 1


def test_review_creation_for_someone_elses_document_is_404(api, db, owner):
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    theirs = make_review_for(db, stranger)

    sign_in(api, db, owner)
    response = api.post(f"{V1}/reviews", json={
        "document_version_id": str(theirs.document_version_id),
        "configuration_snapshot_id": str(theirs.configuration_snapshot_id)})
    assert response.status_code == 404


# =====================================================================
# Report — F-8 / F-9 / 36.10
# =====================================================================
def test_report_carries_no_risk_score_or_verdict(api, db, owner,
                                                 requirement_version):
    """36.10 forbids a risk score as the primary V1 legal output; F-8 makes risk
    a *configured* display mapping. None is configured, and ENG-09 says an absent
    configuration value fails closed rather than defaulting — so the field is
    absent, not guessed."""
    from tests.conftest import make_evaluation, make_finding

    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version)
    make_evaluation(db, finding, rule_outcome=E.RuleOutcome.APPROVAL_REQUIRED)

    sign_in(api, db, owner)
    body = api.get(f"{V1}/reviews/{review.id}/report").json()["data"]

    for forbidden in ("risk", "risk_score", "risk_level", "verdict", "overall"):
        assert forbidden not in body
    assert body["classification_counts"] == {"DEVIATION": 1}
    assert body["findings_requiring_decision"] == 1
    assert body["coverage"]["requirements_with_findings"] == 1
    # F-9 — a ratio over evaluated Requirements, carrying no legal meaning.
    assert body["alignment"] == {"requirements_evaluated": 1, "matched": 0,
                                "ratio": 0.0}


# =====================================================================
# Configuration — Step 29, 42.12, ENG-09
# =====================================================================
def _legal_admin(db):
    user = make_user(db)
    grant_role(db, user, P.ROLE_LEGAL_ADMIN)
    return user


def test_publish_fails_closed_when_configuration_is_incomplete(api, db, seeded):
    """ENG-09 — publishing a partial snapshot would produce Reviews that silently
    skipped a Requirement, so it is refused and the Requirement is named."""
    admin = _legal_admin(db)
    requirement = M.Requirement(code="LIABILITY-001", status=E.ConfigStatus.ACTIVE)
    db.add(requirement); db.flush()
    db.add(M.RequirementVersion(
        requirement_id=requirement.id, version_number=1, name="Liability",
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=admin.id))
    db.flush()

    sign_in(api, db, admin)
    response = api.post(f"{V1}/configuration/publish", json={})
    assert response.status_code == 422
    assert "LIABILITY-001" in response.json()["error"]["message"]
    assert db.execute(select(M.ConfigurationSnapshot)).first() is None


def test_draft_and_publish_produces_a_stable_snapshot(api, db, seeded):
    """Step 29 / rule 16 — a draft never affects a comparison until published,
    and republishing identical configuration reuses the identical snapshot, which
    is what keeps determinism (rule 9)."""
    admin = _legal_admin(db)
    sign_in(api, db, admin)

    created = api.post(f"{V1}/requirements", json={"code": "LIABILITY-001"})
    assert created.status_code == 201
    requirement_id = created.json()["data"]["id"]

    # NOTE: the payloads below are STRUCTURAL placeholders supplied by the test,
    # not a legal position. Rule 21 — real Company Standards and Legal Rules must
    # come from the owner; this asserts the mechanism, not any legal content.
    versioned = api.post(f"{V1}/requirements/{requirement_id}/versions", json={
        "name": "Limitation of Liability",
        "evaluator_type": "NUMERIC_COMPARISON",
        "company_standard": {"unit": "months"},
        "mapping_rules": {"exact_phrase": []},
        "evaluation_rules": {"scope_required": True},
        "legal_rule": {"rule_type": "THRESHOLD", "configuration": {}},
    })
    assert versioned.status_code == 201

    # Still DRAFT, so it is not in a snapshot yet.
    assert api.post(f"{V1}/configuration/publish",
                    json={}).status_code == 422

    first = api.post(f"{V1}/configuration/publish",
                     json={"requirement_codes": ["LIABILITY-001"]})
    assert first.status_code == 201
    assert first.json()["data"]["requirement_count"] == 1
    assert first.json()["data"]["reused_existing"] is False

    again = api.post(f"{V1}/configuration/publish", json={})
    assert again.json()["data"]["id"] == first.json()["data"]["id"]
    assert again.json()["data"]["reused_existing"] is True


def test_a_new_requirement_version_never_edits_the_previous_one(api, db, seeded):
    """Rule 16 / AUD-04 — a historical Review must reproduce from the exact
    versions it used, which is only possible if versions are appended."""
    admin = _legal_admin(db)
    sign_in(api, db, admin)
    requirement_id = api.post(f"{V1}/requirements",
                              json={"code": "TERMINATION-001"}
                              ).json()["data"]["id"]
    draft = {"name": "Termination", "evaluator_type": "PRESENCE",
             "company_standard": {}, "mapping_rules": {},
             "evaluation_rules": {}}
    api.post(f"{V1}/requirements/{requirement_id}/versions", json=draft)
    api.post(f"{V1}/requirements/{requirement_id}/versions",
             json={**draft, "name": "Termination (revised)"})

    body = api.get(f"{V1}/requirements/{requirement_id}").json()["data"]
    assert [v["version_number"] for v in body["versions"]] == [1, 2]
    assert body["versions"][0]["name"] == "Termination"


def test_configuration_view_does_not_confer_draft(api, db, seeded):
    """Step 23 / 47.4 — Legal Reviewer may view configuration but not author it."""
    reviewer = make_user(db)
    grant_role(db, reviewer, P.ROLE_LEGAL_REVIEWER)
    sign_in(api, db, reviewer)
    assert api.get(f"{V1}/requirements").status_code == 200
    assert api.post(f"{V1}/requirements", json={"code": "X-1"}).status_code == 403


def test_legal_admin_cannot_publish_without_the_permission(api, db, seeded):
    narrow = make_user(db)
    grant(db, narrow, bespoke_role(db, "DRAFT_ONLY",
                                   [P.CONFIGURATION_VIEW, P.CONFIGURATION_DRAFT]))
    sign_in(api, db, narrow)
    assert api.post(f"{V1}/configuration/publish", json={}).status_code == 403


# =====================================================================
# Administration — S-8, S-9, S-10, SEC-05
# =====================================================================
def _super_admin(db):
    user = make_user(db)
    grant_role(db, user, P.ROLE_SUPER_ADMIN)
    return user


def test_a_new_account_holds_no_roles(api, db, seeded):
    """47.1.3 r3 — authority is always a later, deliberate grant."""
    sign_in(api, db, _super_admin(db))
    created = api.post(f"{V1}/users", json={"email": "New.User@Example.test",
                                            "name": "New User"})
    assert created.status_code == 201
    assert created.json()["data"]["roles"] == []
    assert created.json()["data"]["email"] == "new.user@example.test"


def test_cannot_grant_an_authority_one_does_not_hold(api, db, seeded):
    """S-8 — the vulnerability the external reference describes, in LegalMind's
    terms: any administrator able to grant the highest privilege through an
    ordinary role assignment defeats ROLE-05 entirely."""
    admin = _super_admin(db)
    target = make_user(db)
    sign_in(api, db, admin)

    response = api.post(f"{V1}/users/{target.id}/roles",
                        json={"role_code": P.ROLE_LEGAL_DECISION_AUTHORITY})
    assert response.status_code == 403
    assert "escalation refused" in response.json()["error"]["message"]


def test_granting_legal_authority_is_audited_as_such(api, db, seeded):
    """47.9 — a legal-authority change gets its own action, so it is findable
    without knowing which role codes happen to carry ``legal.*``."""
    granter = make_user(db)
    grant(db, granter, bespoke_role(
        db, "AUTHORITY_GRANTER",
        [P.USER_MANAGE, P.LEGAL_DECISION, P.LEGAL_APPROVE_CUSTOMIZATION]))
    target = make_user(db)

    sign_in(api, db, granter)
    response = api.post(f"{V1}/users/{target.id}/roles",
                        json={"role_code": P.ROLE_LEGAL_DECISION_AUTHORITY})
    assert response.status_code == 201
    assert P.ROLE_LEGAL_DECISION_AUTHORITY in response.json()["data"]["roles"]

    actions = set(db.execute(select(M.AuditEvent.action)).scalars().all())
    assert "admin.role_granted" in actions
    assert "admin.legal_authority_granted" in actions


def test_cannot_administer_a_more_privileged_account(api, db, seeded):
    """S-9 — the guard covers editing, not only granting. Without it an
    administrator who cannot grant ``legal.decision`` could disable the account
    that holds it and reach the same outcome."""
    admin = _super_admin(db)
    authority = make_user(db)
    grant(db, authority, bespoke_role(db, "AUTH_HOLDER", [P.LEGAL_DECISION]))

    sign_in(api, db, admin)
    response = api.patch(f"{V1}/users/{authority.id}",
                         json={"status": "DISABLED"})
    assert response.status_code == 403


def test_disabling_the_last_legal_authority_is_refused(api, db, seeded):
    """SEC-05 — never zero legal authorities.

    Only ACTIVE users count: a disabled account cannot authenticate by any route
    (47.1.3), so counting its grant would satisfy SEC-05 on paper while leaving
    exactly the stalled Review the rule exists to prevent (Step 31 r18).
    """
    holder = make_user(db)
    grant(db, holder, bespoke_role(db, "SOLE_AUTHORITY",
                                   [P.LEGAL_DECISION, P.USER_MANAGE]))
    sign_in(api, db, holder)
    response = api.patch(f"{V1}/users/{holder.id}", json={"status": "DISABLED"})
    assert response.status_code == 403
    assert "Legal" in response.json()["error"]["message"]
    assert db.get(M.User, holder.id).status is E.UserStatus.ACTIVE


def test_revoking_the_last_legal_authority_role_is_refused(api, db, seeded):
    holder = make_user(db)
    role = bespoke_role(db, "SOLE_AUTHORITY_2",
                        [P.LEGAL_DECISION, P.USER_MANAGE])
    grant(db, holder, role)
    sign_in(api, db, holder)
    response = api.delete(f"{V1}/users/{holder.id}/roles/{role.code}")
    assert response.status_code == 403


def test_disabling_an_account_revokes_its_sessions_immediately(api, db, seeded):
    """S-2 — a disabled account must not keep working for the rest of a live
    session."""
    admin = _super_admin(db)
    target = make_user(db)
    grant_role(db, target, P.ROLE_USER)

    from legalmind.security.sessions import create_session
    victim_session = create_session(db, target)

    sign_in(api, db, admin)
    assert api.patch(f"{V1}/users/{target.id}",
                     json={"status": "DISABLED"}).status_code == 200
    db.refresh(victim_session)
    assert victim_session.revoked_at is not None


def test_role_permission_replacement_refuses_escalation(api, db, seeded):
    """S-8 applied to permissions rather than roles — otherwise PATCH /roles
    would be the route that bypasses ``require_can_grant_role``."""
    admin = _super_admin(db)
    role = bespoke_role(db, "ORDINARY", [P.CONTRACT_VIEW])
    sign_in(api, db, admin)

    response = api.patch(f"{V1}/roles/{role.id}",
                         json={"permissions": [P.CONTRACT_VIEW,
                                               P.LEGAL_DECISION]})
    assert response.status_code == 403
    assert set(db.execute(
        select(M.Permission.name)
        .join(M.RolePermission,
              M.RolePermission.permission_id == M.Permission.id)
        .where(M.RolePermission.role_id == role.id)
    ).scalars().all()) == {P.CONTRACT_VIEW}


def test_role_permission_replacement_is_audited_with_before_and_after(api, db,
                                                                     seeded):
    """S-10 / 43.26 — the whole set changes or none of it does, and the change is
    recorded on both sides so an authority change is reconstructable."""
    admin = _super_admin(db)
    role = bespoke_role(db, "ORDINARY_2", [P.CONTRACT_VIEW])
    sign_in(api, db, admin)

    response = api.patch(f"{V1}/roles/{role.id}",
                         json={"permissions": [P.AUDIT_VIEW, P.USER_MANAGE]})
    assert response.status_code == 200
    assert response.json()["data"]["permissions"] == sorted(
        [P.AUDIT_VIEW, P.USER_MANAGE])

    event = db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.action == "admin.permission_changed",
               M.AuditEvent.entity_id == role.id)
        .order_by(M.AuditEvent.id)
    ).scalars().all()[-1]
    assert event.before_state == {"permissions": [P.CONTRACT_VIEW]}
    assert P.USER_MANAGE in event.after_state["permissions"]


def test_unknown_permission_name_is_rejected(api, db, seeded):
    admin = _super_admin(db)
    role = bespoke_role(db, "ORDINARY_3", [])
    sign_in(api, db, admin)
    response = api.patch(f"{V1}/roles/{role.id}",
                         json={"permissions": ["contract.obliterate"]})
    assert response.status_code == 422


def test_role_listing_marks_which_roles_confer_legal_authority(api, db, seeded):
    """Makes the ROLE-05 boundary visible to an administrator without them having
    to know which permission names are special."""
    admin = make_user(db)
    grant(db, admin, bespoke_role(db, "ROLE_ADMIN_ONLY", [P.ROLE_MANAGE]))
    sign_in(api, db, admin)

    roles = {r["code"]: r for r in
             api.get(f"{V1}/roles", params={"page_size": 100}).json()["data"]}
    assert roles[P.ROLE_LEGAL_DECISION_AUTHORITY]["confers_legal_authority"] == [
        P.LEGAL_APPROVE_CUSTOMIZATION, P.LEGAL_DECISION]
    # Locked Step 23 — Super Admin confers none of it.
    assert roles[P.ROLE_SUPER_ADMIN]["confers_legal_authority"] == []


# =====================================================================
# S-5 / 49.10 — rate limiting
# =====================================================================
def test_login_is_rate_limited(api, db, seeded):
    """49.10 — applied to authentication. Thresholds are deployment
    configuration, so the test drives the configured limit rather than asserting
    a specific number."""
    from legalmind.api import ratelimit
    from legalmind.api.routers import auth as auth_router

    for _ in range(ratelimit.LOGIN.max_requests):
        assert api.post(f"{V1}/auth/login",
                        json={"email": "nobody@example.test",
                              "password": "x"}).status_code == 401

    limited = api.post(f"{V1}/auth/login",
                       json={"email": "nobody@example.test", "password": "x"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    # 49.10 — no detail about the limit's shape.
    assert "Retry-After" not in limited.headers
    assert "limit" not in limited.json()["error"]["message"].lower()
    assert isinstance(auth_router.limiter, ratelimit.InProcessRateLimiter)
