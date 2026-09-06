"""Contract archive — AB-12 r6 (2026-09-05), replacing AM-37's two-mode delete.

Under AM-37 a contract that had never been analysed was HARD-deleted: row,
versions, evidence and the stored bytes destroyed. AB-12 withdraws that path
entirely. There is no DELETE verb on a contract any more; there is `archive`, its
mirror `restore`, and the rule that an archived contract is read-only.

The tests that matter most here are the ones asserting what SURVIVES an archive
— every one of them, for a contract that was never analysed, which is exactly
the case the old code destroyed. A regression that quietly reintroduces a
destructive branch would pass every "it disappeared from the list" test and fail
these.
"""

from __future__ import annotations

import uuid

from legalmind.api.permission_map import ENDPOINT_PERMISSIONS
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import bespoke_role, grant, grant_role, make_user, sign_in

V1 = "/api/v1"


def _owner(db, api, *, permissions=None):
    user = make_user(db)
    if permissions is None:
        grant_role(db, user, P.ROLE_USER)
    else:
        grant(db, user, bespoke_role(db, f"ARC-{uuid.uuid4().hex[:6]}", permissions))
    sign_in(api, db, user)
    return user


def _contract(db, owner, *, name="ACME MSA"):
    contract = M.Contract(owner_id=owner.id, name=name, status=E.ContractStatus.DRAFT)
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
    snapshot = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id)
    db.add(snapshot)
    db.flush()
    review = M.Review(contract_id=contract.id, document_version_id=version.id,
                      configuration_snapshot_id=snapshot.id,
                      status=E.ReviewStatus.ANALYSIS_COMPLETE, created_by=owner.id)
    db.add(review)
    db.flush()
    return review


def _archive(api, contract):
    return api.post(f"{V1}/contracts/{contract.id}/archive")


# =====================================================================
# Nothing is destroyed — the point of the record
# =====================================================================
def test_archiving_an_unanalysed_contract_destroys_nothing(api, db, seeded, tmp_path):
    """The case AM-37 hard-deleted. Row, version, evidence AND the bytes stay."""
    from legalmind.api import storage as api_storage

    owner = _owner(db, api)
    contract = _contract(db, owner)
    backend = api_storage.get_storage()
    key = backend.put(b"%PDF-1.4 pretend", suggested_name="msa.pdf")
    version = _version(db, contract, owner, storage_key=key)

    response = _archive(api, contract)

    assert response.status_code == 200
    assert response.json()["data"]["archived_at"] is not None
    db.expire_all()
    assert db.get(M.Contract, contract.id) is not None
    assert db.get(M.DocumentVersion, version.id) is not None
    assert backend.exists(key), "the uploaded file must survive an archive"


def test_archiving_preserves_the_review_and_its_findings(api, db, seeded):
    """Rule 17: historical Reviews stay reproducible."""
    owner = _owner(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    review = _review_on(db, contract, version, owner)

    _archive(api, contract)
    db.expire_all()

    assert db.get(M.Review, review.id) is not None
    assert db.get(M.DocumentVersion, version.id) is not None


def test_archive_is_an_audited_event(api, db, seeded):
    owner = _owner(db, api)
    contract = _contract(db, owner)

    _archive(api, contract)

    event = db.query(M.AuditEvent).filter_by(action=audit.CONTRACT_ARCHIVED).one()
    assert event.entity_id == contract.id
    assert event.actor_id == owner.id
    assert event.after_state["archived_at"]


def test_no_route_destroys_a_contract(api, db, seeded):
    """There is no DELETE verb on a contract in the permission map, and the
    server answers one with 405 — not 404, not 200. The row is untouched."""
    assert ("DELETE", f"{V1}/contracts/{{contract_id}}") not in ENDPOINT_PERMISSIONS
    owner = _owner(db, api)
    contract = _contract(db, owner)

    assert api.delete(f"{V1}/contracts/{contract.id}").status_code == 405
    assert db.get(M.Contract, contract.id) is not None


def test_no_route_mutates_a_document_version(api, db, seeded):
    """Original uploaded evidence is immutable (Step 26, AB-12 §5): the API has
    no PUT or DELETE on a document version, and no route that touches its file,
    its evidence or its processing record.

    The ONE write is `PATCH /document-versions/{id}` (2026-09-06): the
    uploader's DECLARED source / counterparty / effective date, into locked
    42.4's `metadata` JSONB — never the bytes, never the evidence. Owner ruling
    2026-09-06 on locked 33.7 / 34.15 r3: correctable only while the version has
    no Review, refused (409) afterwards — pinned in
    `test_api_resources.test_declared_metadata_is_fixed_once_a_review_exists`.
    It carries the permission that already creates the version."""
    for (method, path) in ENDPOINT_PERMISSIONS:
        if "/document-versions/" in path:
            assert method in ("GET", "POST", "PATCH"), (method, path)
            if method == "POST":
                # `/reprocess` (2026-09-06, Option C) is the one POST that writes:
                # a NEW processing run over the preserved original — never the
                # file, never existing evidence — and only while nothing relies
                # on the current reading (pinned in test_api_resources).
                assert path.endswith(("/suggest-type", "/extract-obligations",
                                      "/reprocess")), path
            if method == "PATCH":
                assert path == f"{V1}/document-versions/{{document_version_id}}", path
                assert ENDPOINT_PERMISSIONS[(method, path)] == P.DOCUMENT_UPLOAD


# =====================================================================
# Visibility — off the working list, still readable
# =====================================================================
def test_an_archived_contract_leaves_the_working_list_and_the_summary(api, db, seeded):
    owner = _owner(db, api)
    contract = _contract(db, owner, name="Shelved MSA")
    before = api.get(f"{V1}/contracts/summary").json()["data"]["total"]

    _archive(api, contract)

    listed = api.get(f"{V1}/contracts").json()["data"]
    assert all(row["id"] != str(contract.id) for row in listed)
    assert api.get(f"{V1}/contracts/summary").json()["data"]["total"] == before - 1


def test_the_archived_list_holds_only_archived_contracts(api, db, seeded):
    owner = _owner(db, api)
    live = _contract(db, owner, name="Live")
    shelved = _contract(db, owner, name="Shelved")
    _archive(api, shelved)

    ids = {row["id"] for row in api.get(f"{V1}/contracts?archived=true").json()["data"]}
    assert ids == {str(shelved.id)}
    assert str(live.id) not in ids


def test_an_archived_contract_is_still_readable_by_its_owner(api, db, seeded):
    """Archive hides, it does not erase: "what did LegalMind know about this
    contract?" must stay answerable. The detail says it is archived."""
    owner = _owner(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    _archive(api, contract)

    detail = api.get(f"{V1}/contracts/{contract.id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["archived_at"] is not None
    assert api.get(f"{V1}/document-versions/{version.id}").status_code == 200


def test_an_archived_contract_is_still_a_404_for_a_stranger(api, db, seeded):
    stranger = make_user(db)
    victim = _contract(db, stranger)
    victim.archived_at = __import__("datetime").datetime.now(__import__("datetime").UTC)
    db.flush()

    _owner(db, api)
    assert api.get(f"{V1}/contracts/{victim.id}").status_code == 404


# =====================================================================
# Read-only — every write is a 409
# =====================================================================
def test_an_archived_contract_refuses_every_write(api, db, seeded):
    owner = _owner(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    snapshot = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id)
    db.add(snapshot)
    db.flush()
    _archive(api, contract)

    assert api.patch(f"{V1}/contracts/{contract.id}", json={"name": "x"}).status_code == 409
    assert api.post(f"{V1}/contracts/{contract.id}/document-versions",
                    content=b"%PDF-1.4 fake",
                    headers={"content-type": "application/pdf",
                             "x-filename": "x.pdf"}).status_code == 409
    assert api.post(f"{V1}/reviews", json={
        "document_version_id": str(version.id),
        "configuration_snapshot_id": str(snapshot.id)}).status_code == 409
    # Archiving twice is a 409 too, so the second actor cannot hide in a no-op.
    assert _archive(api, contract).status_code == 409
    db.expire_all()
    assert db.get(M.Contract, contract.id).name == "ACME MSA"


def test_analysis_is_refused_on_an_archived_contract(api, db, seeded):
    owner = _owner(db, api)
    contract = _contract(db, owner)
    version = _version(db, contract, owner)
    review = _review_on(db, contract, version, owner)
    review.status = E.ReviewStatus.DRAFT
    db.flush()
    _archive(api, contract)

    assert api.post(f"{V1}/reviews/{review.id}/analyze").status_code == 409


# =====================================================================
# Restore — the mirror
# =====================================================================
def test_restore_brings_the_contract_back_and_is_audited(api, db, seeded):
    owner = _owner(db, api)
    contract = _contract(db, owner, name="Back again")
    _archive(api, contract)

    response = api.post(f"{V1}/contracts/{contract.id}/restore")

    assert response.status_code == 200
    assert response.json()["data"]["archived_at"] is None
    assert any(row["id"] == str(contract.id)
               for row in api.get(f"{V1}/contracts").json()["data"])
    assert api.patch(f"{V1}/contracts/{contract.id}",
                     json={"name": "writable again"}).status_code == 200
    actions = {e.action for e in db.query(M.AuditEvent).all()}
    assert audit.CONTRACT_RESTORED in actions


def test_restoring_a_live_contract_is_a_409(api, db, seeded):
    owner = _owner(db, api)
    contract = _contract(db, owner)
    assert api.post(f"{V1}/contracts/{contract.id}/restore").status_code == 409


# =====================================================================
# Authorization — ownership is the scope, permission is the operation
# =====================================================================
def test_another_users_contract_cannot_be_archived(api, db, seeded):
    """404 rather than 403: a permission level must never reveal existence."""
    stranger = make_user(db)
    victim = _contract(db, stranger, name="Someone else's MSA")

    _owner(db, api)
    assert _archive(api, victim).status_code == 404
    assert api.post(f"{V1}/contracts/{victim.id}/restore").status_code == 404
    db.expire_all()
    assert db.get(M.Contract, victim.id).archived_at is None


def test_archive_requires_the_contract_archive_permission(api, db, seeded):
    owner = _owner(db, api, permissions=[P.CONTRACT_VIEW, P.CONTRACT_CREATE])
    contract = _contract(db, owner)

    assert _archive(api, contract).status_code == 403
    db.expire_all()
    assert db.get(M.Contract, contract.id).archived_at is None


def test_archive_requires_a_csrf_token(api, db, seeded):
    owner = _owner(db, api)
    contract = _contract(db, owner)
    del api.headers["X-CSRF-Token"]

    assert _archive(api, contract).status_code == 403


def test_who_holds_the_archive_grant():
    """A Department User and a Department Lead archive their OWN deals; the
    Platform Admin — accounts, never content (Step 24 r8/r9) — holds nothing
    of the kind."""
    assert P.CONTRACT_ARCHIVE in P.DEFAULT_ROLE_GRANTS[P.ROLE_USER]
    assert P.CONTRACT_ARCHIVE in P.DEFAULT_ROLE_GRANTS[P.ROLE_DEPARTMENT_LEAD]
    assert P.CONTRACT_ARCHIVE not in P.DEFAULT_ROLE_GRANTS[P.ROLE_PLATFORM_ADMIN]
    assert "contract.delete" not in P.ALL_PERMISSIONS
