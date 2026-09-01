"""Contract deletion — owner approval 2026-09-01, closing the gap `AM-31` left open.

`AM-31` said, under "What this record does NOT decide": *"No hard-delete path for
a Contract exists today, and this record does not create one or assume its
shape."* The owner decided the shape on 2026-09-01, and it is two modes behind
one verb:

* **never analyzed** (no Review) → hard delete: row, versions, processing runs,
  evidence, stored bytes, assist chunks and obligation extractions all go.
* **analyzed** (a Review exists) → soft delete: `deleted_at` is stamped, the
  contract leaves every response, and findings/decisions/audit stay put.

The split exists to keep **rule 17** — append-only audit, historical Reviews stay
reproducible — intact. The tests that matter most in this file are therefore the
ones asserting what SURVIVES a soft delete, not the ones asserting what a hard
delete removes: a regression that quietly hard-deletes an analyzed contract would
destroy legal history, and it would look like a passing delete to everything
else.
"""

from __future__ import annotations

import uuid

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from tests.conftest import bespoke_role, grant, make_user, sign_in

V1 = "/api/v1"


def _deleter(db, api, *, permissions=None):
    """A signed-in user who owns their contracts and may delete them."""
    user = make_user(db)
    grant(db, user, bespoke_role(
        db, f"DEL-{uuid.uuid4().hex[:6]}",
        permissions if permissions is not None
        else [P.CONTRACT_VIEW, P.CONTRACT_CREATE, P.CONTRACT_DELETE,
              P.DOCUMENT_VIEW]))
    sign_in(api, db, user)
    return user


def _contract(db, owner, *, name="ACME MSA"):
    contract = M.Contract(owner_id=owner.id, name=name,
                          status=E.ContractStatus.DRAFT)
    db.add(contract)
    db.flush()
    return contract


def _version(db, contract, owner, *, storage_key="k"):
    version = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="msa.pdf",
        mime_type="application/pdf", file_size_bytes=10, file_hash="h",
        storage_key=storage_key,
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=owner.id)
    db.add(version)
    db.flush()
    return version


def _review_on(db, contract, version, owner):
    snapshot = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex,
                                       created_by=owner.id)
    db.add(snapshot)
    db.flush()
    review = M.Review(contract_id=contract.id, document_version_id=version.id,
                      configuration_snapshot_id=snapshot.id,
                      status=E.ReviewStatus.ANALYSIS_COMPLETE,
                      created_by=owner.id)
    db.add(review)
    db.flush()
    return review


# =====================================================================
# The hard-delete branch — a contract that was never analyzed
# =====================================================================
def test_an_unanalyzed_contract_is_hard_deleted(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    _version(db, contract, owner)

    response = api.delete(f"{V1}/contracts/{contract.id}")

    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True, "mode": "hard"}
    assert db.get(M.Contract, contract.id) is None


def test_hard_delete_removes_the_document_versions_with_it(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)

    api.delete(f"{V1}/contracts/{contract.id}")

    assert db.get(M.DocumentVersion, version.id) is None


def test_hard_delete_removes_the_stored_bytes(api, db, seeded, tmp_path):
    """The file itself, not just the row pointing at it.

    A row deleted while its bytes stay on disk is exactly the shape of an
    accidental retention: nothing in the product would ever show it again, and
    nothing would ever collect it either.
    """
    from legalmind.api import storage as api_storage

    owner = _deleter(db, api)
    contract = _contract(db, owner)
    backend = api_storage.get_storage()
    key = backend.put(b"%PDF-1.4 pretend", suggested_name="msa.pdf")
    assert backend.exists(key)
    _version(db, contract, owner, storage_key=key)

    api.delete(f"{V1}/contracts/{contract.id}")

    assert not backend.exists(key)


# =====================================================================
# The soft-delete branch — rule 17's guarantee, which is the point
# =====================================================================
def test_an_analyzed_contract_is_soft_deleted(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    _review_on(db, contract, version, owner)

    response = api.delete(f"{V1}/contracts/{contract.id}")

    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True, "mode": "soft"}
    db.expire_all()
    row = db.get(M.Contract, contract.id)
    assert row is not None, "an analyzed contract must never be destroyed"
    assert row.deleted_at is not None


def test_soft_delete_preserves_the_review_and_its_findings(api, db, seeded):
    """Rule 17: historical Reviews stay reproducible.

    This is the assertion that stops a future refactor from "simplifying" the
    two modes into one hard delete.
    """
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    review = _review_on(db, contract, version, owner)

    api.delete(f"{V1}/contracts/{contract.id}")
    db.expire_all()

    assert db.get(M.Review, review.id) is not None
    assert db.get(M.DocumentVersion, version.id) is not None


def test_soft_delete_leaves_the_audit_trail_intact(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    _review_on(db, contract, version, owner)
    before = db.query(M.AuditEvent).count()

    api.delete(f"{V1}/contracts/{contract.id}")

    # Append-only: the trail only ever grows, and the deletion is itself an event.
    assert db.query(M.AuditEvent).count() > before


def test_both_modes_are_recorded_as_distinct_audit_actions(api, db, seeded):
    from legalmind.security import audit

    owner = _deleter(db, api)
    plain = _contract(db, owner, name="Never analyzed")
    _version(db, plain, owner)
    analyzed = _contract(db, owner, name="Analyzed")
    analyzed_version = _version(db, analyzed, owner)
    _review_on(db, analyzed, analyzed_version, owner)

    api.delete(f"{V1}/contracts/{plain.id}")
    api.delete(f"{V1}/contracts/{analyzed.id}")

    actions = {e.action for e in db.query(M.AuditEvent).all()}
    assert audit.CONTRACT_HARD_DELETED in actions
    assert audit.CONTRACT_SOFT_DELETED in actions


# =====================================================================
# Visibility — a deleted contract is gone from every read path
# =====================================================================
def test_a_soft_deleted_contract_is_absent_from_the_list(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner, name="Vanishing MSA")
    version = _version(db, contract, owner)
    _review_on(db, contract, version, owner)

    api.delete(f"{V1}/contracts/{contract.id}")
    listed = api.get(f"{V1}/contracts").json()["data"]

    assert all(row["id"] != str(contract.id) for row in listed)


def test_a_soft_deleted_contract_is_absent_from_the_summary_counts(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    _review_on(db, contract, version, owner)
    before = api.get(f"{V1}/contracts/summary").json()["data"]["total"]

    api.delete(f"{V1}/contracts/{contract.id}")
    after = api.get(f"{V1}/contracts/summary").json()["data"]["total"]

    assert after == before - 1


def test_a_soft_deleted_contract_is_a_404_by_id(api, db, seeded):
    """404, not 403 and not an empty 200 — existence is itself a disclosure
    (47.7), and a deleted contract must read exactly like one that never was."""
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    _review_on(db, contract, version, owner)

    api.delete(f"{V1}/contracts/{contract.id}")

    assert api.get(f"{V1}/contracts/{contract.id}").status_code == 404


def test_deleting_the_same_contract_twice_is_a_404(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    _review_on(db, contract, version, owner)

    assert api.delete(f"{V1}/contracts/{contract.id}").status_code == 200
    assert api.delete(f"{V1}/contracts/{contract.id}").status_code == 404


# =====================================================================
# Authorization — ownership is the scope, permission is the operation
# =====================================================================
def test_another_users_contract_cannot_be_deleted(api, db, seeded):
    """404 rather than 403: a permission level must never reveal existence."""
    stranger = make_user(db)
    victim = _contract(db, stranger, name="Someone else's MSA")

    _deleter(db, api)
    response = api.delete(f"{V1}/contracts/{victim.id}")

    assert response.status_code == 404
    assert db.get(M.Contract, victim.id) is not None


def test_delete_requires_the_contract_delete_permission(api, db, seeded):
    owner = _deleter(db, api, permissions=[P.CONTRACT_VIEW, P.CONTRACT_CREATE])
    contract = _contract(db, owner)

    response = api.delete(f"{V1}/contracts/{contract.id}")

    assert response.status_code == 403
    assert db.get(M.Contract, contract.id) is not None


def test_delete_requires_a_csrf_token(api, db, seeded):
    owner = _deleter(db, api)
    contract = _contract(db, owner)
    del api.headers["X-CSRF-Token"]

    response = api.delete(f"{V1}/contracts/{contract.id}")

    assert response.status_code == 403
    assert db.get(M.Contract, contract.id) is not None


def test_an_ordinary_user_role_can_delete_their_own_contract(db):
    """The grant the owner approved: `ROLE_USER`, scoped by ownership.

    Asserted against the default grant table rather than a bespoke role, because
    the decision was specifically that an ordinary user may delete what they
    uploaded — a bespoke-role test would pass even if that grant were dropped.
    """
    from legalmind.security.permissions import DEFAULT_ROLE_GRANTS, ROLE_USER

    assert P.CONTRACT_DELETE in DEFAULT_ROLE_GRANTS[ROLE_USER]


def test_delete_is_not_granted_to_administrative_roles(db):
    """Step 24 r8/r9: contract content and platform administration stay
    separate. Deletion is contract content, so a Super Admin does not get it by
    virtue of being an administrator."""
    from legalmind.security.permissions import (
        DEFAULT_ROLE_GRANTS,
        ROLE_SUPER_ADMIN,
    )

    assert P.CONTRACT_DELETE not in DEFAULT_ROLE_GRANTS[ROLE_SUPER_ADMIN]
