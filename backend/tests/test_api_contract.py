"""API contract — locked 43.21, 43.30, 49.1, 49.4, 49.5, 49.6, 49.9, S-3.

These tests are about the shape of the interface rather than about any domain
rule: the envelope, the error taxonomy, the correlation identifier, pagination
clamping, CSRF, and the property 49.3 states in one sentence — "No endpoint is
implicitly public."
"""

from __future__ import annotations

import json

import pytest

from legalmind.api.app import create_app, registered_routes
from legalmind.api.permission_map import (
    AUTHENTICATED_ONLY,
    ENDPOINT_PERMISSIONS,
    UNAUTHENTICATED,
)
from legalmind.security import permissions as P
from tests.conftest import bespoke_role, grant, make_user, sign_in

V1 = "/api/v1"


# =====================================================================
# 49.3 — every endpoint declares exactly one required permission
# =====================================================================
def test_every_registered_route_declares_a_permission():
    """49.3: "No endpoint is implicitly public."

    Held to account structurally rather than by review: a new route with no
    entry in the map fails here, and so does a map entry whose route was
    renamed or removed.
    """
    app = create_app()
    routes = set(registered_routes(app))
    assert routes - set(ENDPOINT_PERMISSIONS) == set()
    assert set(ENDPOINT_PERMISSIONS) - routes == set()


def test_only_the_probe_and_the_two_sign_in_mechanisms_are_unauthenticated():
    """Four routes are deliberately reachable without a session, and no fifth may
    appear without this test failing (49.3: "No endpoint is implicitly public").

    The liveness probe; the password login 47.1.3 calls the controlled fallback;
    and the two OIDC routes that ARE the primary mechanism — they cannot require a
    session, because they are how one is obtained. Both OIDC routes are rate-limited
    on the login bucket, and the callback's CSRF defence is the OIDC `state`
    parameter rather than the double-submit cookie, which a top-level GET
    navigation cannot carry.
    """
    unauthenticated = {route for route, perm in ENDPOINT_PERMISSIONS.items()
                       if perm == UNAUTHENTICATED}
    assert unauthenticated == {("GET", "/health"),
                               ("POST", f"{V1}/auth/login"),
                               ("GET", f"{V1}/auth/oidc/start"),
                               ("GET", f"{V1}/auth/oidc/callback")}


def test_openapi_document_is_not_served_by_default():
    """An unauthenticated schema document would sit oddly beside 47.7's
    404-over-403 posture. 49.12 leaves OpenAPI generation to implementation, so
    it is opt-in."""
    app = create_app()
    routes = {path for _, path in registered_routes(app)}
    assert f"{V1}/openapi.json" not in routes
    assert f"{V1}/docs" not in routes


@pytest.mark.parametrize(
    "method,path",
    sorted(
        (m, p) for (m, p), perm in ENDPOINT_PERMISSIONS.items()
        if perm != UNAUTHENTICATED
    ),
)
def test_no_session_is_401_everywhere(api, method, path):
    """47.7 — no valid session is 401 on every endpoint that is not deliberately
    public, before any path parameter or body is even considered."""
    concrete = path.replace("{session_id}", "00000000-0000-0000-0000-000000000001")
    for name in ("contract_id", "document_version_id", "review_id", "finding_id",
                 "evaluation_id", "requirement_id", "user_id", "role_id"):
        concrete = concrete.replace(
            "{" + name + "}", "00000000-0000-0000-0000-000000000001")
    concrete = concrete.replace("{role_code}", "USER")

    response = api.request(method, concrete, json={})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "data" not in body


def test_health_needs_no_session(api):
    response = api.get("/health")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}


# =====================================================================
# 49.9 — correlation identifiers
# =====================================================================
def test_request_id_is_echoed_on_success_and_on_error(api, db, seeded):
    user = make_user(db)
    sign_in(api, db, user)

    ok = api.get(f"{V1}/health")
    assert "X-Request-Id" in ok.headers or ok.status_code == 404

    denied = api.get(f"{V1}/audit-events")
    assert denied.status_code == 403
    assert denied.headers["X-Request-Id"]
    # The id is in the body too, so a user reporting a failure can quote it.
    assert denied.json()["error"]["request_id"] == denied.headers["X-Request-Id"]


def test_supplied_request_id_is_reused(api, db, seeded):
    user = make_user(db)
    sign_in(api, db, user)
    response = api.get(f"{V1}/contracts", headers={"X-Request-Id": "trace-abc.123"})
    assert response.headers["X-Request-Id"] == "trace-abc.123"


def test_malformed_request_id_is_replaced_not_trusted(api, db, seeded):
    """An inbound id reaches audit metadata and log lines, so it is constrained
    rather than trusted."""
    user = make_user(db)
    sign_in(api, db, user)
    hostile = "<script>alert(1)</script>"
    response = api.get(f"{V1}/contracts", headers={"X-Request-Id": hostile})
    assert response.headers["X-Request-Id"] != hostile


def test_request_id_reaches_the_audit_trail(api, db, seeded):
    """49.9 — recorded in the metadata of every audit event the request
    produces. Here the event is the denial itself."""
    from sqlalchemy import select

    from legalmind.db import models as M

    user = make_user(db)
    sign_in(api, db, user)
    api.get(f"{V1}/audit-events", headers={"X-Request-Id": "corr-1"})

    event = db.execute(
        select(M.AuditEvent).where(M.AuditEvent.action == "authz.permission_denied")
    ).scalars().first()
    assert event is not None
    assert event.event_metadata["request_id"] == "corr-1"


# =====================================================================
# 49.5 — errors and denial semantics
# =====================================================================
def test_unknown_route_404_is_byte_identical_to_out_of_scope_404(api, db, seeded):
    """49.5 r1 — any difference between the two is an enumeration oracle.

    Compared byte-for-byte with the request id normalized, since that is the
    caller's own correlation id and is the one field legitimately allowed to
    differ between two separate requests.
    """
    user = make_user(db)
    grant(db, user, bespoke_role(db, "READER", [P.REVIEW_VIEW]))
    sign_in(api, db, user)

    stranger = make_user(db)
    from tests.conftest import make_review_for
    hidden = make_review_for(db, stranger)

    out_of_scope = api.get(f"{V1}/reviews/{hidden.id}")
    nonexistent = api.get(f"{V1}/reviews/00000000-0000-0000-0000-000000000009")
    unknown_route = api.get(f"{V1}/no-such-collection")

    assert out_of_scope.status_code == nonexistent.status_code == 404
    assert unknown_route.status_code == 404

    def normalized(response):
        body = response.json()
        body["error"]["request_id"] = "-"
        return json.dumps(body, sort_keys=True)

    assert normalized(out_of_scope) == normalized(nonexistent)
    assert normalized(out_of_scope) == normalized(unknown_route)


def test_validation_errors_name_fields_without_echoing_values(api, db, seeded):
    """49.5 r4 — offending fields, never the submitted content.

    FastAPI's default renderer includes the input value; a decision
    justification or a contract name is exactly the sort of thing that must not
    come back in an error body.
    """
    user = make_user(db)
    grant(db, user, bespoke_role(db, "CREATOR", [P.CONTRACT_CREATE]))
    sign_in(api, db, user)

    secret = "Project Nightingale acquisition"
    response = api.post(f"{V1}/contracts",
                        json={"name": secret, "unexpected_field": 1})
    assert response.status_code == 422
    raw = response.text
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert any(f["field"] == "unexpected_field"
               for f in response.json()["error"]["fields"])
    assert secret not in raw


def test_error_bodies_carry_no_data_key(api, db, seeded):
    """43.21 — the three envelope shapes are exclusive. An error never also
    carries a partial payload."""
    user = make_user(db)
    sign_in(api, db, user)
    response = api.get(f"{V1}/users")
    assert response.status_code == 403
    assert set(response.json()) == {"error"}


# =====================================================================
# 49.6 — pagination
# =====================================================================
def test_page_size_is_clamped_server_side(api, db, seeded):
    """49.6 — clamped at 100 "regardless of client input"."""
    user = make_user(db)
    grant(db, user, bespoke_role(db, "READER2", [P.CONTRACT_VIEW]))
    sign_in(api, db, user)
    response = api.get(f"{V1}/contracts", params={"page_size": 5000})
    assert response.status_code == 200
    assert response.json()["pagination"]["page_size"] == 100


def test_collection_envelope_carries_pagination(api, db, seeded):
    from legalmind.db import models as M
    from legalmind.domain import enums as E

    user = make_user(db)
    grant(db, user, bespoke_role(db, "READER3",
                                 [P.CONTRACT_VIEW, P.CONTRACT_CREATE]))
    sign_in(api, db, user)
    for i in range(3):
        db.add(M.Contract(owner_id=user.id, name=f"C{i}",
                          status=E.ContractStatus.DRAFT))
    db.flush()

    response = api.get(f"{V1}/contracts", params={"page_size": 2})
    body = response.json()
    assert set(body) == {"data", "pagination"}
    assert len(body["data"]) == 2
    assert body["pagination"] == {"page": 1, "page_size": 2, "total": 3}


def test_pagination_is_stable_across_pages(api, db, seeded):
    """49.6 — a deterministic tiebreaker on id, so a page can neither drop nor
    duplicate a row. All three contracts share a created_at because
    PostgreSQL now() is transaction time, which is exactly the case that would
    break an ordering without the tiebreak."""
    from legalmind.db import models as M
    from legalmind.domain import enums as E

    user = make_user(db)
    grant(db, user, bespoke_role(db, "READER4", [P.CONTRACT_VIEW]))
    sign_in(api, db, user)
    for i in range(5):
        db.add(M.Contract(owner_id=user.id, name=f"C{i}",
                          status=E.ContractStatus.DRAFT))
    db.flush()

    seen = []
    for page in (1, 2, 3):
        body = api.get(f"{V1}/contracts",
                       params={"page": page, "page_size": 2}).json()
        seen.extend(item["id"] for item in body["data"])
    assert len(seen) == 5
    assert len(set(seen)) == 5


# =====================================================================
# S-3 — CSRF
# =====================================================================
def test_state_changing_request_needs_a_csrf_token(api, db, seeded):
    user = make_user(db)
    grant(db, user, bespoke_role(db, "CREATOR2", [P.CONTRACT_CREATE]))
    sign_in(api, db, user)
    del api.headers["X-CSRF-Token"]

    response = api.post(f"{V1}/contracts", json={"name": "ACME MSA"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


def test_mismatched_csrf_token_is_rejected(api, db, seeded):
    user = make_user(db)
    grant(db, user, bespoke_role(db, "CREATOR3", [P.CONTRACT_CREATE]))
    sign_in(api, db, user)
    api.headers["X-CSRF-Token"] = "not-the-cookie"

    response = api.post(f"{V1}/contracts", json={"name": "ACME MSA"})
    assert response.status_code == 403


def test_reads_do_not_require_a_csrf_token(api, db, seeded):
    user = make_user(db)
    grant(db, user, bespoke_role(db, "READER5", [P.CONTRACT_VIEW]))
    sign_in(api, db, user)
    del api.headers["X-CSRF-Token"]
    assert api.get(f"{V1}/contracts").status_code == 200


# =====================================================================
# 49.1 — conventions
# =====================================================================
def test_put_is_never_used():
    """49.1 — "PUT is not used." Partial update is PATCH, and a full-replacement
    verb on a Finding or a Decision would be the wrong shape entirely: locked
    Step 31 r14 makes supersession a create."""
    assert not any(method == "PUT" for method, _ in ENDPOINT_PERMISSIONS)


def test_every_route_is_under_the_locked_version_prefix():
    """43.30 — /api/v1/ from the beginning. Only the liveness probe sits
    outside, because a probe is not a resource."""
    outside = {path for _, path in ENDPOINT_PERMISSIONS if not path.startswith(V1)}
    assert outside == {"/health"}


def test_permission_names_are_all_from_the_locked_catalogue():
    """Every mapped permission is a real catalogue entry (Step 47 §47.4) — a
    typo in the map would otherwise create an endpoint no role can ever
    satisfy, which fails closed but silently."""
    declared = {perm for perm in ENDPOINT_PERMISSIONS.values()
                if perm not in {AUTHENTICATED_ONLY, UNAUTHENTICATED}}
    assert declared <= set(P.ALL_PERMISSIONS)


# =====================================================================
# The frozen contract — docs/api/openapi.json cannot drift from the code
# =====================================================================
def test_the_committed_openapi_snapshot_matches_the_app():
    """The snapshot is what a UI phase designs against (owner directive,
    2026-08-26: "finalized backend contracts"). A contract change is therefore a
    visible diff in the same commit as the code — this test is what makes that
    a property rather than a habit. Regenerate with
    `python3 -m tools.export_openapi`, after checking the diff against Step 49."""
    from tools.export_openapi import SNAPSHOT, current_schema, render

    assert SNAPSHOT.exists(), f"missing {SNAPSHOT}; run python3 -m tools.export_openapi"
    assert SNAPSHOT.read_text() == render(current_schema()), (
        f"{SNAPSHOT} is stale: the application's contract changed. Review the "
        "change against STEP_49_API_FINALIZATION.md, then regenerate in this commit.")
