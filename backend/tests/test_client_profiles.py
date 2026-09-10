"""Client Profiles — owner instruction, 2026-09-10.

The feature is an ORGANISING LAYER over what already exists, and these tests are
written to hold it to that. The three things most easily got wrong, and pinned
here first:

1. **No second document store.** A client's documents are its contracts, and a
   contract belongs to exactly one client through `contracts.counterparty_id`.
   Nothing is copied, and linking an existing document creates no new row.
2. **One unified list, never folders.** The profile returns every document for a
   client in ONE array regardless of type. `test_the_document_list_is_one_list_
   whatever_the_types_are` is the structural version of the owner's "do not
   create MSA/NDA/SLA sections".
3. **Versions are never overwritten**, and Company Draft / Client Modified /
   Final Signed stay three distinct declarations — in particular a client's
   redline is NOT the signed copy.

And the standing one: the profile screen discloses nothing beyond the caller's
existing contract scope (AB-13 r6).
"""

from __future__ import annotations

import uuid

import pytest

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.client_profile import CLIENT_STATUSES, VERSION_ROLES
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in, sign_out

V1 = "/api/v1"


@pytest.fixture
def owner(db, seeded):
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    return user


def make_client(api, name="Acme Technologies", **fields) -> dict:
    response = api.post(f"{V1}/counterparties", json={"name": name, **fields})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def make_document(api, name, *, counterparty_id=None, contract_type=None) -> dict:
    body: dict = {"name": name}
    if counterparty_id:
        body["counterparty_id"] = counterparty_id
    if contract_type:
        body["contract_type"] = contract_type
    response = api.post(f"{V1}/contracts", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def add_version(db, contract_id, number, *, role=None) -> M.DocumentVersion:
    """A version row directly, because these tests are about FILING, not
    ingestion — parsing a real PDF here would test the parser again and make
    every case slow for no added coverage. Ingestion has its own suite."""
    version = M.DocumentVersion(
        contract_id=uuid.UUID(contract_id) if isinstance(contract_id, str)
        else contract_id,
        version_number=number,
        original_filename=f"v{number}.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        file_hash=uuid.uuid4().hex,
        storage_key=f"k/{uuid.uuid4().hex}",
        processing_status=E.ProcessingStatus.COMPLETED,
        uploaded_by=next(iter(db.execute(
            __import__("sqlalchemy").select(M.User.id)).scalars().all())),
        doc_metadata={"version_role": role} if role else None,
    )
    db.add(version)
    db.flush()
    return version


# =====================================================================
# The profile itself
# =====================================================================
def test_a_client_profile_records_only_what_a_human_typed(api, db, owner):
    """Rule 21's discipline applied to company data: an unknown field is
    OMITTED, never nulled, so the screen can say "Not available" honestly
    rather than rendering a dash that looks like something was checked."""
    sign_in(api, db, owner)
    bare = make_client(api, "Unknown Co")
    assert bare["name"] == "Unknown Co"
    assert bare["status"] == "ACTIVE"           # the column default, always present
    for absent in ("industry", "website", "city", "legal_name",
                   "primary_contact_name", "account_owner_id"):
        assert absent not in bare, f"{absent} was invented"

    filled = api.patch(f"{V1}/counterparties/{bare['id']}", json={
        "industry": "Information Technology",
        "city": "Mumbai", "state_region": "Maharashtra", "country": "India",
        "website": "https://example.test",
        "primary_contact_name": "A. Person",
        "primary_contact_email": "a.person@example.test",
        "status": "PROSPECTIVE",
    }).json()["data"]
    assert filled["city"] == "Mumbai"
    assert filled["status"] == "PROSPECTIVE"
    # Cleared is absent again, not an empty string.
    cleared = api.patch(f"{V1}/counterparties/{bare['id']}",
                        json={"city": None}).json()["data"]
    assert "city" not in cleared


def test_a_blank_string_is_not_a_fact(api, db, owner):
    """"   " is nobody's industry. Trimmed to nothing on the way in, so the
    profile never shows a field that is present but empty."""
    sign_in(api, db, owner)
    row = make_client(api, "Whitespace Co", industry="   ", website="")
    assert "industry" not in row and "website" not in row


def test_a_status_outside_the_vocabulary_is_refused(api, db, owner):
    sign_in(api, db, owner)
    row = make_client(api, "Vocab Co")
    assert api.patch(f"{V1}/counterparties/{row['id']}",
                     json={"status": "CHURNED"}).status_code == 422
    assert api.post(f"{V1}/counterparties",
                    json={"name": "X", "status": "active"}).status_code == 422
    assert set(CLIENT_STATUSES) == {"ACTIVE", "PROSPECTIVE", "INACTIVE"}


def test_the_name_and_the_status_can_never_be_cleared(api, db, owner):
    """A company with no name is not an identity, and `status` is NOT NULL."""
    sign_in(api, db, owner)
    row = make_client(api, "Named Co")
    kept = api.patch(f"{V1}/counterparties/{row['id']}",
                     json={"name": None, "status": None}).json()["data"]
    assert kept["name"] == "Named Co"
    assert kept["status"] == "ACTIVE"


def test_every_profile_edit_is_on_the_audit_trail_with_only_what_changed(
        api, db, owner):
    """AUD-01 — a shared profile several people may edit. The payload carries
    the fields that MOVED; recording all fifteen on every edit would bury the
    one that did, permanently, in an append-only trail."""
    from sqlalchemy import select
    sign_in(api, db, owner)
    row = make_client(api, "Trailed Co")
    api.patch(f"{V1}/counterparties/{row['id']}", json={"city": "Pune"})
    event = db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.entity_id == uuid.UUID(row["id"]),
               M.AuditEvent.action == "counterparty.updated")
    ).scalars().one()
    assert event.after_state == {"city": "Pune"}
    assert event.before_state == {"city": None}


def test_an_unchanged_patch_writes_no_audit_row(api, db, owner):
    from sqlalchemy import func, select
    sign_in(api, db, owner)
    row = make_client(api, "Idle Co", city="Pune")
    before = db.execute(select(func.count()).select_from(M.AuditEvent)).scalar_one()
    api.patch(f"{V1}/counterparties/{row['id']}", json={"city": "Pune"})
    assert db.execute(
        select(func.count()).select_from(M.AuditEvent)).scalar_one() == before


# =====================================================================
# Documents under a client — ONE list, no duplication
# =====================================================================
def test_a_client_reuses_the_existing_document_record_and_copies_nothing(
        api, db, owner):
    """The central requirement. Linking a document to a client changes ONE
    nullable column on the contract that already exists — no second contract,
    no second version, no second file."""
    from sqlalchemy import func, select
    sign_in(api, db, owner)
    client = make_client(api, "Reuse Co")
    document = make_document(api, "Existing MSA")
    add_version(db, document["id"], 1)

    contracts_before = db.execute(
        select(func.count()).select_from(M.Contract)).scalar_one()
    versions_before = db.execute(
        select(func.count()).select_from(M.DocumentVersion)).scalar_one()

    api.patch(f"{V1}/contracts/{document['id']}",
              json={"counterparty_id": client["id"]})

    assert db.execute(
        select(func.count()).select_from(M.Contract)).scalar_one() == contracts_before
    assert db.execute(
        select(func.count()).select_from(M.DocumentVersion)
    ).scalar_one() == versions_before

    profile = api.get(f"{V1}/counterparties/{client['id']}").json()["data"]
    assert [c["id"] for c in profile["contracts"]] == [document["id"]]


def test_the_document_list_is_one_list_whatever_the_types_are(api, db, owner):
    """The owner's structural requirement: "All of these must appear together
    in ONE document list". The API returns one flat array in one order and
    offers no per-type grouping — so a client screen CANNOT render MSA/NDA/SLA
    folders without inventing a structure the server does not have.

    Six types, one array, and the type travels as a field on the row."""
    sign_in(api, db, owner)
    client = make_client(api, "Mixed Co")
    types = ["MSA", "NDA", "SLA", "AMENDMENT", "ORDER_FORM", "OTHER"]
    for code in types:
        make_document(api, f"{code} document", counterparty_id=client["id"],
                      contract_type=code)

    profile = api.get(f"{V1}/counterparties/{client['id']}").json()["data"]
    assert isinstance(profile["contracts"], list)
    assert len(profile["contracts"]) == len(types)
    assert sorted(c["contract_type"] for c in profile["contracts"]) == sorted(types)
    # The payload has no grouping key of any kind — nothing to render as folders.
    assert not any(key in profile for key in
                   ("contracts_by_type", "groups", "sections", "folders"))


def test_creating_a_document_from_a_client_profile_links_it_in_one_call(
        api, db, owner):
    sign_in(api, db, owner)
    client = make_client(api, "Direct Co")
    document = make_document(api, "Straight to the client",
                             counterparty_id=client["id"])
    assert document["counterparty_id"] == client["id"]
    profile = api.get(f"{V1}/counterparties/{client['id']}").json()["data"]
    assert [c["id"] for c in profile["contracts"]] == [document["id"]]


def test_a_document_cannot_be_created_against_a_client_that_does_not_exist(
        api, db, owner):
    """A dangling link is worse than no link (AB-13 r2), and it would put a
    document on nobody's page."""
    sign_in(api, db, owner)
    refused = api.post(f"{V1}/contracts", json={"name": "Orphan",
                                                "counterparty_id": str(uuid.uuid4())})
    assert refused.status_code == 422
    assert "counterparty" in refused.json()["error"]["message"]


def test_the_unlinked_filter_finds_documents_that_predate_client_profiles(
        api, db, owner):
    """"Do not require users to upload the same document again just because
    Client Profiles was introduced." The picker that avoids that is
    `?counterparty_id=none`."""
    sign_in(api, db, owner)
    client = make_client(api, "Later Co")
    historical = make_document(api, "Historical NDA")
    linked = make_document(api, "Already linked", counterparty_id=client["id"])

    unlinked = api.get(f"{V1}/contracts", params={"counterparty_id": "none"}).json()
    ids = {c["id"] for c in unlinked["data"]}
    assert historical["id"] in ids
    assert linked["id"] not in ids

    just_this_client = api.get(f"{V1}/contracts",
                               params={"counterparty_id": client["id"]}).json()
    assert [c["id"] for c in just_this_client["data"]] == [linked["id"]]


def test_a_malformed_counterparty_filter_is_refused_not_ignored(api, db, owner):
    """Silently ignoring it would show the caller every contract while the UI
    still said it was filtered — the class of quiet wrongness ENG-09 names."""
    sign_in(api, db, owner)
    assert api.get(f"{V1}/contracts",
                   params={"counterparty_id": "not-a-uuid"}).status_code == 422


# =====================================================================
# Versions — preserved, and three distinct roles
# =====================================================================
def test_the_three_version_roles_stay_three_distinct_declarations(api, db, owner):
    """"Do not assume that the Client Modified Version is always the final
    signed version. They are separate concepts." Pinned as data: three
    versions, three roles, and the signed one is identified on its own."""
    sign_in(api, db, owner)
    client = make_client(api, "Negotiating Co")
    document = make_document(api, "Master Services Agreement",
                             counterparty_id=client["id"], contract_type="MSA")
    for number, role in enumerate(VERSION_ROLES, start=1):
        add_version(db, document["id"], number, role=role)

    profile = api.get(f"{V1}/counterparties/{client['id']}").json()["data"]
    row = profile["contracts"][0]
    assert row["version_count"] == 3
    # Newest first, and every earlier version still present — nothing overwrote
    # anything (locked 33.7 / Step 26: a version is immutable once created).
    assert [v["version_number"] for v in row["versions"]] == [3, 2, 1]
    assert [v["version_role"] for v in row["versions"]] == [
        "FINAL_SIGNED", "CLIENT_MODIFIED", "COMPANY_DRAFT"]
    assert row["signed"] is True


def test_a_client_redline_alone_does_not_make_a_document_signed(api, db, owner):
    """The distinction the owner asked for, as a failing case rather than a
    comment: two versions, the newest of them the client's redline, and the
    document is NOT signed."""
    sign_in(api, db, owner)
    client = make_client(api, "Redline Co")
    document = make_document(api, "NDA", counterparty_id=client["id"],
                             contract_type="NDA")
    add_version(db, document["id"], 1, role="COMPANY_DRAFT")
    add_version(db, document["id"], 2, role="CLIENT_MODIFIED")

    profile = api.get(f"{V1}/counterparties/{client['id']}").json()["data"]
    assert profile["contracts"][0]["signed"] is False
    assert profile["signed_documents"] == 0
    assert profile["documents"] == 1


def test_an_undeclared_version_says_nothing_rather_than_guessing(api, db, owner):
    """Every version uploaded before 2026-09-10 has no role, and no role is
    inferred from its position, its filename or its age. The key is simply
    absent, and the screen shows the version number alone."""
    sign_in(api, db, owner)
    client = make_client(api, "Legacy Co")
    document = make_document(api, "Old paper", counterparty_id=client["id"])
    add_version(db, document["id"], 1)
    profile = api.get(f"{V1}/counterparties/{client['id']}").json()["data"]
    assert "version_role" not in profile["contracts"][0]["versions"][0]
    assert profile["contracts"][0]["signed"] is False


def test_a_role_is_declared_through_the_existing_version_endpoint(api, db, owner):
    """No new write path: `PATCH /document-versions/{id}` already declares
    source, counterparty and effective date into locked 42.4's JSONB, and the
    role joins them there. Nothing about versions changed structurally."""
    sign_in(api, db, owner)
    client = make_client(api, "Declaring Co")
    document = make_document(api, "MSA", counterparty_id=client["id"])
    version = add_version(db, document["id"], 1)

    declared = api.patch(f"{V1}/document-versions/{version.id}",
                         json={"version_role": "COMPANY_DRAFT",
                               "source": "ORGANIZATION"}).json()["data"]
    assert declared["version_role"] == "COMPANY_DRAFT"
    assert declared["source"] == "ORGANIZATION"

    assert api.patch(f"{V1}/document-versions/{version.id}",
                     json={"version_role": "SIGNED"}).status_code == 422


def test_version_role_and_source_are_two_axes_not_one(api, db, owner):
    """A signed version is not thereby the counterparty's paper. Kept apart
    deliberately: `source` is what the evaluator reasons about, `version_role`
    is filing, and collapsing them would lose the owner's distinction."""
    sign_in(api, db, owner)
    client = make_client(api, "Axes Co")
    document = make_document(api, "MSA", counterparty_id=client["id"])
    version = add_version(db, document["id"], 1)
    row = api.patch(f"{V1}/document-versions/{version.id}",
                    json={"version_role": "FINAL_SIGNED",
                          "source": "ORGANIZATION"}).json()["data"]
    assert row["version_role"] == "FINAL_SIGNED"
    assert row["source"] == "ORGANIZATION"


# =====================================================================
# The directory: counts, search, filters
# =====================================================================
def test_the_client_list_counts_documents_and_signed_documents(api, db, owner):
    """`signed_documents` counts DOCUMENTS, not versions: a contract with two
    executed versions is still one signed agreement, which is the question a
    non-legal reader is actually asking."""
    sign_in(api, db, owner)
    client = make_client(api, "Counting Co")
    signed = make_document(api, "Signed MSA", counterparty_id=client["id"])
    add_version(db, signed["id"], 1, role="COMPANY_DRAFT")
    add_version(db, signed["id"], 2, role="FINAL_SIGNED")
    add_version(db, signed["id"], 3, role="FINAL_SIGNED")
    make_document(api, "Draft NDA", counterparty_id=client["id"])

    listed = api.get(f"{V1}/counterparties", params={"stats": True}).json()
    row = next(c for c in listed["data"] if c["id"] == client["id"])
    assert row["documents"] == 2
    assert row["signed_documents"] == 1
    assert row["last_activity"] is not None


def test_the_list_is_searched_and_filtered_on_the_server(api, db, owner):
    """Server-side, so it still works when a caller has hundreds of clients —
    the owner named a frontend-only filter as the thing to avoid."""
    sign_in(api, db, owner)
    zatpat = make_client(api, "Zatpat Technologies", industry="Cloud hosting",
                         city="Pune")
    make_client(api, "Other Holdings", industry="Manufacturing", city="Chennai")

    found = api.get(f"{V1}/counterparties", params={"q": "zatpat"}).json()
    assert [c["id"] for c in found["data"]] == [zatpat["id"]]
    assert found["pagination"]["total"] == 1

    # A reader searching the city is searching for the same client.
    assert [c["id"] for c in api.get(
        f"{V1}/counterparties", params={"q": "Pune"}).json()["data"]] == [zatpat["id"]]

    by_industry = api.get(f"{V1}/counterparties",
                          params={"industry": "Cloud hosting"}).json()
    assert [c["id"] for c in by_industry["data"]] == [zatpat["id"]]

    api.patch(f"{V1}/counterparties/{zatpat['id']}", json={"status": "INACTIVE"})
    assert [c["id"] for c in api.get(
        f"{V1}/counterparties",
        params={"status": "INACTIVE"}).json()["data"]] == [zatpat["id"]]


def test_has_documents_separates_a_new_profile_from_a_working_one(api, db, owner):
    sign_in(api, db, owner)
    empty = make_client(api, "Empty Co")
    working = make_client(api, "Working Co")
    make_document(api, "Some paper", counterparty_id=working["id"])

    with_docs = api.get(f"{V1}/counterparties",
                        params={"has_documents": True}).json()["data"]
    assert [c["id"] for c in with_docs] == [working["id"]]
    without = api.get(f"{V1}/counterparties",
                      params={"has_documents": False}).json()["data"]
    assert [c["id"] for c in without] == [empty["id"]]


def test_the_list_paginates_without_changing_its_envelope(api, db, owner):
    """`data` is still the array every pre-2026-09-10 caller read; `pagination`
    was added beside it, not around it."""
    sign_in(api, db, owner)
    for n in range(5):
        make_client(api, f"Client {n:02d}")
    page = api.get(f"{V1}/counterparties", params={"page_size": 2}).json()
    assert isinstance(page["data"], list) and len(page["data"]) == 2
    assert page["pagination"]["total"] == 5
    assert [c["name"] for c in page["data"]] == ["Client 00", "Client 01"]


def test_an_unknown_sort_is_refused(api, db, owner):
    sign_in(api, db, owner)
    assert api.get(f"{V1}/counterparties",
                   params={"sort": "revenue_desc"}).status_code == 422


def test_the_industry_filter_offers_only_what_somebody_typed(api, db, owner):
    """There is no industry taxonomy in this product and rule 21 forbids
    inventing one, so the filter can only honestly offer values in use."""
    sign_in(api, db, owner)
    assert api.get(f"{V1}/counterparties/industries").json()["data"] == []
    make_client(api, "Typed Co", industry="Information Technology")
    assert api.get(f"{V1}/counterparties/industries").json()["data"] == [
        "Information Technology"]


# =====================================================================
# Activity
# =====================================================================
def test_activity_is_the_existing_audit_trail_scoped_to_one_client(api, db, owner):
    """No second history is written for this screen: the rows come from
    `audit_events`, which already recorded every one of these acts."""
    sign_in(api, db, owner)
    client = make_client(api, "Busy Co")
    document = make_document(api, "MSA", counterparty_id=client["id"])
    api.patch(f"{V1}/counterparties/{client['id']}", json={"city": "Mumbai"})
    api.patch(f"{V1}/contracts/{document['id']}", json={"contract_type": "MSA"})

    feed = api.get(f"{V1}/counterparties/{client['id']}/activity").json()["data"]
    actions = [event["action"] for event in feed]
    assert "counterparty.created" in actions
    assert "counterparty.updated" in actions
    assert "contract.counterparty_linked" in actions
    assert "contract.type_declared" in actions
    # Newest first, every row attributed, and the document named.
    assert feed == sorted(feed, key=lambda e: e["timestamp"], reverse=True)
    assert all(event["actor_name"] == "Test User" for event in feed)
    assert any(event["subject"] == "MSA" for event in feed)


def test_activity_never_returns_an_audit_payload(api, db, owner):
    """A before/after can hold an internal legal position (`LEGAL-02`), and a
    client activity feed is not the surface to relax that on."""
    sign_in(api, db, owner)
    client = make_client(api, "Quiet Co")
    api.patch(f"{V1}/counterparties/{client['id']}", json={"city": "Delhi"})
    feed = api.get(f"{V1}/counterparties/{client['id']}/activity").json()["data"]
    assert feed
    for event in feed:
        assert set(event) == {"id", "action", "entity_type", "entity_id",
                              "subject", "actor_name", "timestamp"}


def test_activity_needs_no_audit_view_permission(api, db, owner):
    """An ordinary Department User holds `contract.view` and not `audit.view`,
    and must still be able to see their own client's history."""
    sign_in(api, db, owner)
    assert P.AUDIT_VIEW not in _permissions(db, owner)
    client = make_client(api, "Ordinary Co")
    assert api.get(f"{V1}/counterparties/{client['id']}/activity").status_code == 200


def _permissions(db, user):
    from legalmind.security.resolver import effective_permissions
    return effective_permissions(db, user.id)


# =====================================================================
# Scope — the profile screen widens nothing
# =====================================================================
def test_a_client_profile_is_never_visible_outside_the_callers_contract_scope(
        api, db, owner):
    """AB-13 r6, re-pinned for every route the Client Profiles screen uses.
    A better surface over the same set — never a wider one."""
    sign_in(api, db, owner)
    client = make_client(api, "Private Co")
    document = make_document(api, "Their MSA", counterparty_id=client["id"])
    add_version(db, document["id"], 1, role="FINAL_SIGNED")
    sign_out(api)

    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, stranger)

    listed = api.get(f"{V1}/counterparties", params={"stats": True}).json()
    assert listed["data"] == []
    assert listed["pagination"]["total"] == 0
    assert api.get(f"{V1}/counterparties/industries").json()["data"] == []
    assert api.get(f"{V1}/counterparties/{client['id']}").status_code == 404
    assert api.get(
        f"{V1}/counterparties/{client['id']}/activity").status_code == 404
    # Byte-identical to a client that was never created (49.5 r1).
    assert (api.get(f"{V1}/counterparties/{client['id']}").json()["error"]["code"]
            == api.get(f"{V1}/counterparties/{uuid.uuid4()}")
            .json()["error"]["code"])


def test_the_client_total_is_per_caller_not_organisation_wide(api, db, owner):
    """Two people, two different totals for the same database — which is the
    point. A shared "18 total clients" would be the global list r6 forbids,
    wearing a counter."""
    sign_in(api, db, owner)
    make_client(api, "Mine A")
    make_client(api, "Mine B")
    assert api.get(f"{V1}/counterparties").json()["pagination"]["total"] == 2
    sign_out(api)

    other = make_user(db)
    grant_role(db, other, P.ROLE_USER)
    sign_in(api, db, other)
    make_client(api, "Theirs")
    assert api.get(f"{V1}/counterparties").json()["pagination"]["total"] == 1


def test_an_account_owner_outside_the_callers_department_is_refused(api, db, owner):
    """The boundary `contract.transfer` already enforces, applied to the same
    kind of field: a target outside the caller's department is refused with the
    message a nonexistent user gets, so this is not a probe for other
    departments' accounts."""
    sign_in(api, db, owner)
    outsider = make_user(db)
    refused = api.post(f"{V1}/counterparties",
                       json={"name": "Owned Co",
                             "account_owner_id": str(outsider.id)})
    assert refused.status_code == 422
    assert "department" in refused.json()["error"]["message"]
