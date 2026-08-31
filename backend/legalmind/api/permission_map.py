"""Endpoint → permission mapping — locked 49.3.

Locked 38.24 leaves **endpoint naming** outside the locked boundary and 49.3 says
so again: "Endpoint naming remains outside the locked boundary (38.24); the
**permission mapping** is the part that matters and is normative here."

This module is therefore the normative part, transcribed from 49.3's table and
held as data so a test can assert two things that prose cannot:

1. every route the application registers appears here — 49.3: "No endpoint is
   implicitly public";
2. no route silently drifts to a different permission than the locked table.

Where 49.3 groups several paths on one row, each concrete route gets its own
entry. Where a route is an implementation convenience 49.3 does not list (a
Requirement's creation, an escalation's withdrawal), it reuses the permission
49.3 assigns to its sibling operation rather than introducing a new mapping.
"""

from __future__ import annotations

from typing import Final

from legalmind.security import permissions as P

# Sentinels, so that "requires no permission" is always a deliberate statement
# rather than a missing entry.
AUTHENTICATED_ONLY: Final = "*authenticated*"
UNAUTHENTICATED: Final = "*unauthenticated*"

API_PREFIX: Final = "/api/v1"


ENDPOINT_PERMISSIONS: Final[dict[tuple[str, str], str]] = {
    # ---- liveness -------------------------------------------------------
    # Deliberately unauthenticated and deliberately contentless: it reports that
    # the process is up and nothing else. Step 53 is where probes are specified.
    ("GET", "/health"): UNAUTHENTICATED,

    # ---- 49.2 authentication -------------------------------------------
    ("POST", f"{API_PREFIX}/auth/login"): UNAUTHENTICATED,
    ("POST", f"{API_PREFIX}/auth/logout"): AUTHENTICATED_ONLY,
    ("GET", f"{API_PREFIX}/auth/session"): AUTHENTICATED_ONLY,
    ("DELETE", f"{API_PREFIX}/auth/sessions/{{session_id}}"): P.USER_MANAGE,

    # ---- 49.3 contracts & documents ------------------------------------
    ("GET", f"{API_PREFIX}/contracts"): P.CONTRACT_VIEW,
    ("POST", f"{API_PREFIX}/contracts"): P.CONTRACT_CREATE,
    ("GET", f"{API_PREFIX}/contracts/{{contract_id}}"): P.CONTRACT_VIEW,
    ("PATCH", f"{API_PREFIX}/contracts/{{contract_id}}"): P.CONTRACT_UPDATE,
    ("POST", f"{API_PREFIX}/contracts/{{contract_id}}/document-versions"):
        P.DOCUMENT_UPLOAD,
    ("GET", f"{API_PREFIX}/document-versions/{{document_version_id}}"):
        P.DOCUMENT_VIEW,
    ("GET", f"{API_PREFIX}/document-versions/{{document_version_id}}/content"):
        P.DOCUMENT_DOWNLOAD,

    # ---- 49.3 reviews, findings, evaluations, decisions -----------------
    ("POST", f"{API_PREFIX}/reviews"): P.REVIEW_CREATE,
    # ⚠️ INTERPRETATION, not a locked mapping. Locked 49.3's table has no analysis
    # row, but 49.8 ("Analysis job submission accepts an Idempotency-Key") and
    # 49.10 ("rate limiting ... analysis submission") both presuppose the endpoint.
    # Endpoint naming is outside the locked boundary (38.24) while the permission
    # mapping is normative, so the closest locked grant is used rather than a new
    # permission name being invented: the caller is causing their own Review's
    # analysis to run. Flagged for owner confirmation.
    ("POST", f"{API_PREFIX}/reviews/{{review_id}}/analyze"): P.REVIEW_CREATE,
    ("GET", f"{API_PREFIX}/reviews"): P.REVIEW_VIEW,
    ("GET", f"{API_PREFIX}/reviews/{{review_id}}"): P.REVIEW_VIEW,
    ("GET", f"{API_PREFIX}/reviews/{{review_id}}/findings"): P.FINDING_VIEW,
    ("GET", f"{API_PREFIX}/reviews/{{review_id}}/report"): P.REPORT_VIEW,
    # 49.3's own row. Formats were NOT YET SPECIFIED (49.12) until the owner's
    # 2026-08-31 directive named PDF and DOCX — recorded in AUTO_MODE_DECISIONS.
    ("POST", f"{API_PREFIX}/reviews/{{review_id}}/export"): P.EXPORT_GENERATE,
    ("GET", f"{API_PREFIX}/findings/{{finding_id}}"): P.FINDING_VIEW,
    ("GET", f"{API_PREFIX}/findings/{{finding_id}}/evaluations"): P.EVALUATION_VIEW,
    # 49.3 maps escalation to review.view, NOT to legal.decision: locked Step 4
    # is explicit that escalation means "this requires authorized review" and
    # does not mean "I approve this deviation". Withdrawal is the same act
    # reversed and carries the same permission.
    ("POST", f"{API_PREFIX}/findings/{{finding_id}}/escalate"): P.REVIEW_VIEW,
    ("DELETE", f"{API_PREFIX}/findings/{{finding_id}}/escalate"): P.REVIEW_VIEW,
    ("POST", f"{API_PREFIX}/evaluations/{{evaluation_id}}/decisions"):
        P.LEGAL_DECISION,
    ("GET", f"{API_PREFIX}/evaluations/{{evaluation_id}}/decisions"): P.FINDING_VIEW,

    # ---- 49.3 legal configuration --------------------------------------
    ("GET", f"{API_PREFIX}/requirements"): P.CONFIGURATION_VIEW,
    ("GET", f"{API_PREFIX}/requirements/{{requirement_id}}"): P.CONFIGURATION_VIEW,
    ("POST", f"{API_PREFIX}/requirements"): P.CONFIGURATION_DRAFT,
    ("POST", f"{API_PREFIX}/requirements/{{requirement_id}}/versions"):
        P.CONFIGURATION_DRAFT,
    ("POST", f"{API_PREFIX}/requirements/{{requirement_id}}/standard"):
        P.CONFIGURATION_DRAFT,
    ("GET", f"{API_PREFIX}/configuration/snapshots"): P.REVIEW_CREATE,
    ("POST", f"{API_PREFIX}/configuration/publish"): P.CONFIGURATION_PUBLISH,

    # ---- 49.3 audit -----------------------------------------------------
    ("GET", f"{API_PREFIX}/audit-events"): P.AUDIT_VIEW,

    # ---- 49.3 administration -------------------------------------------
    ("GET", f"{API_PREFIX}/users"): P.USER_MANAGE,
    ("POST", f"{API_PREFIX}/users"): P.USER_MANAGE,
    ("GET", f"{API_PREFIX}/users/{{user_id}}"): P.USER_MANAGE,
    ("PATCH", f"{API_PREFIX}/users/{{user_id}}"): P.USER_MANAGE,
    ("POST", f"{API_PREFIX}/users/{{user_id}}/roles"): P.USER_MANAGE,
    ("DELETE", f"{API_PREFIX}/users/{{user_id}}/roles/{{role_code}}"): P.USER_MANAGE,
    ("GET", f"{API_PREFIX}/roles"): P.ROLE_MANAGE,
    ("POST", f"{API_PREFIX}/roles"): P.ROLE_MANAGE,
    ("PATCH", f"{API_PREFIX}/roles/{{role_id}}"): P.ROLE_MANAGE,
}


# --------------------------------------------------------------------------
# Locked 49.3 endpoints deliberately NOT registered.
#
# Registering these would mean inventing behaviour the specification records as
# undecided, which rule 4 forbids. Each is a reported gap, not an oversight.
# --------------------------------------------------------------------------
# ---- assist lane (AB-3/AB-4) — additive; no locked 49.x row changes ---------
ASSIST_ENDPOINTS: Final[dict[tuple[str, str], str]] = {
    ("POST", f"{API_PREFIX}/conversations"): P.ASSIST_ASK,
    # The list applies the same creator-only scope as the single GET (49.6 r4): a
    # list never leaks a conversation a GET would 404 on.
    ("GET", f"{API_PREFIX}/conversations"): P.ASSIST_ASK,
    ("GET", f"{API_PREFIX}/conversations/{{conversation_id}}"): P.ASSIST_ASK,
    ("POST", f"{API_PREFIX}/conversations/{{conversation_id}}/messages"): P.ASSIST_ASK,
    # Type suggestion (owner, 2026-08-31): a proposal for the intake pre-fill,
    # same risk profile as Ask — no new legal authority.
    ("POST", f"{API_PREFIX}/document-versions/{{document_version_id}}/suggest-type"):
        P.ASSIST_ASK,
    # Key Obligations (owner, 2026-08-31): descriptive facts about text the
    # caller can already read in full — the findings-viewer's scope, and never
    # the organization's negotiating position (LEGAL-02 does not apply).
    ("POST",
     f"{API_PREFIX}/document-versions/{{document_version_id}}/extract-obligations"):
        P.FINDING_VIEW,
    ("GET", f"{API_PREFIX}/document-versions/{{document_version_id}}/obligations"):
        P.FINDING_VIEW,
}
ENDPOINT_PERMISSIONS.update(ASSIST_ENDPOINTS)

# Added during implementation (2026-08-26), not in 49.3's table and not locked: a
# read projection of the locked Evidence model (Step 34, 42.6) under the SAME
# permission that already governs seeing the document. 49.0 excludes exact endpoint
# naming from the lock, and the rows it returns are the first link of every
# explainability chain (rule 12) — the document pane a workspace UI renders and the
# target every citation points at. Recorded in AUTO_MODE_DECISIONS.md.
IMPLEMENTATION_ADDED_ENDPOINTS: Final[dict[tuple[str, str], str]] = {
    ("GET", f"{API_PREFIX}/document-versions/{{document_version_id}}/evidence"):
        P.DOCUMENT_VIEW,
}
ENDPOINT_PERMISSIONS.update(IMPLEMENTATION_ADDED_ENDPOINTS)

NOT_IMPLEMENTED: Final[dict[tuple[str, str], str]] = {
    ("GET", f"{API_PREFIX}/auth/oidc/start"):
        "OIDC needs an approved JWT/JWKS client dependency (rule 19) and the "
        "deployment's IdP configuration. Neither exists; Step 47's password "
        "fallback is implemented instead.",
    ("GET", f"{API_PREFIX}/auth/oidc/callback"):
        "As above.",
    # /reviews/{id}/export left this list on 2026-08-31: the owner's export
    # directive specified the formats 49.12 had left open (PDF, DOCX).
}
