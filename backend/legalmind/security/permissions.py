"""Permission catalogue — Step 47 / SEC-04.

Names follow the dotted convention. Three of them are fixed by locked Step 23
and are reproduced verbatim: ``legal.review``, ``legal.decision``,
``legal.approve_customization``.
"""

from __future__ import annotations

from typing import Final

# --- Contracts & documents ------------------------------------------------
CONTRACT_VIEW: Final = "contract.view"
CONTRACT_CREATE: Final = "contract.create"
CONTRACT_UPDATE: Final = "contract.update"
CONTRACT_DELETE: Final = "contract.delete"
DOCUMENT_UPLOAD: Final = "document.upload"
DOCUMENT_VIEW: Final = "document.view"
DOCUMENT_DOWNLOAD: Final = "document.download"

# --- Reviews, findings, evaluations --------------------------------------
REVIEW_CREATE: Final = "review.create"
REVIEW_VIEW: Final = "review.view"
FINDING_VIEW: Final = "finding.view"
FINDING_COMMENT: Final = "finding.comment"
EVALUATION_VIEW: Final = "evaluation.view"

# --- Legal authority (Step 23 — locked names) -----------------------------
LEGAL_REVIEW: Final = "legal.review"
LEGAL_DECISION: Final = "legal.decision"
LEGAL_APPROVE_CUSTOMIZATION: Final = "legal.approve_customization"

# --- Internal legal position (LEGAL-02) -----------------------------------
LEGAL_POSITION_VIEW: Final = "legal_position.view"

# --- Legal configuration --------------------------------------------------
CONFIGURATION_VIEW: Final = "configuration.view"
CONFIGURATION_DRAFT: Final = "configuration.draft"
CONFIGURATION_PUBLISH: Final = "configuration.publish"
CONFIGURATION_DEPRECATE: Final = "configuration.deprecate"

# --- Reporting ------------------------------------------------------------
REPORT_VIEW: Final = "report.view"
REPORT_GENERATE: Final = "report.generate"
EXPORT_GENERATE: Final = "export.generate"

# --- Audit & administration ----------------------------------------------
AUDIT_VIEW: Final = "audit.view"
USER_MANAGE: Final = "user.manage"
ROLE_MANAGE: Final = "role.manage"
PLATFORM_MANAGE: Final = "platform.manage"


CATALOGUE: Final[dict[str, tuple[str, ...]]] = {
    "Contracts": (CONTRACT_VIEW, CONTRACT_CREATE, CONTRACT_UPDATE, CONTRACT_DELETE),
    "Documents": (DOCUMENT_UPLOAD, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD),
    "Reviews": (REVIEW_CREATE, REVIEW_VIEW),
    "Findings": (FINDING_VIEW, FINDING_COMMENT),
    "Evaluations": (EVALUATION_VIEW,),
    "Legal authority": (LEGAL_REVIEW, LEGAL_DECISION, LEGAL_APPROVE_CUSTOMIZATION),
    "Internal legal position": (LEGAL_POSITION_VIEW,),
    "Legal configuration": (CONFIGURATION_VIEW, CONFIGURATION_DRAFT,
                            CONFIGURATION_PUBLISH, CONFIGURATION_DEPRECATE),
    "Reporting": (REPORT_VIEW, REPORT_GENERATE, EXPORT_GENERATE),
    "Audit": (AUDIT_VIEW,),
    "Administration": (USER_MANAGE, ROLE_MANAGE, PLATFORM_MANAGE),
}

ALL_PERMISSIONS: Final[tuple[str, ...]] = tuple(
    p for group in CATALOGUE.values() for p in group
)


# --------------------------------------------------------------------------
# SEC-02 / SEC-05 — the permissions no bypass may ever reach.
#
# Locked Step 23: "Super Admin — No automatic Legal Decision authority" and
# "A Super Admin without that Legal permission cannot approve the customization
# merely because they are a Super Admin."
#
# Locked Step 24 r8: "Super Admin does not automatically have access to
# confidential contract or Legal content."
#
# These require an EXPLICIT grant. Never inherited, never implied, never
# reachable by any bypass or wildcard path.
# --------------------------------------------------------------------------
LEGAL_AUTHORITY_PERMISSIONS: Final[frozenset[str]] = frozenset({
    LEGAL_DECISION,
    LEGAL_APPROVE_CUSTOMIZATION,
})


def is_legal_authority(permission: str) -> bool:
    return permission in LEGAL_AUTHORITY_PERMISSIONS


# --------------------------------------------------------------------------
# Role codes. Step 23 (ROLE-06) is the canonical role set and supersedes the
# earlier illustrative list in 42.3 ("Initial roles: USER, ADMIN, SUPER_ADMIN").
#
# LEGAL_DECISION_AUTHORITY is the SEC-03 mechanism: legal authority is carried
# as an ADDITIONAL role assignment, which is how two users holding the same
# primary role differ in legal authority (locked Step 4's Admin A / Admin B).
# --------------------------------------------------------------------------
ROLE_USER: Final = "USER"
ROLE_LEGAL_REVIEWER: Final = "LEGAL_REVIEWER"
ROLE_LEGAL_ADMIN: Final = "LEGAL_ADMIN"
ROLE_SUPER_ADMIN: Final = "SUPER_ADMIN"
ROLE_LEGAL_DECISION_AUTHORITY: Final = "LEGAL_DECISION_AUTHORITY"

ROLE_NAMES: Final[dict[str, str]] = {
    ROLE_USER: "User",
    ROLE_LEGAL_REVIEWER: "Legal Reviewer",
    ROLE_LEGAL_ADMIN: "Legal Admin",
    ROLE_SUPER_ADMIN: "Super Admin",
    ROLE_LEGAL_DECISION_AUTHORITY: "Legal Decision Authority",
}

# Default grants — every cell traces to Step 23's locked role summary.
#
# Note what Super Admin does NOT get: no legal.*, no legal_position.view, no
# contract/review content. Locked Step 23 ("No automatic Legal Decision
# authority") and Step 24 r8/r9 ("Contract-content access and platform
# administration are separate permissions").
DEFAULT_ROLE_GRANTS: Final[dict[str, tuple[str, ...]]] = {
    ROLE_USER: (
        CONTRACT_VIEW, CONTRACT_CREATE, CONTRACT_UPDATE,
        DOCUMENT_UPLOAD, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD,
        REVIEW_CREATE, REVIEW_VIEW,
        FINDING_VIEW, FINDING_COMMENT,
        EVALUATION_VIEW,
        REPORT_VIEW,
    ),
    ROLE_LEGAL_REVIEWER: (
        CONTRACT_VIEW, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD,
        REVIEW_VIEW, FINDING_VIEW, FINDING_COMMENT, EVALUATION_VIEW,
        LEGAL_REVIEW, LEGAL_POSITION_VIEW,
        CONFIGURATION_VIEW,
        REPORT_VIEW, REPORT_GENERATE,
    ),
    ROLE_LEGAL_ADMIN: (
        CONTRACT_VIEW, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD,
        REVIEW_VIEW, FINDING_VIEW, FINDING_COMMENT, EVALUATION_VIEW,
        LEGAL_REVIEW, LEGAL_POSITION_VIEW,
        CONFIGURATION_VIEW, CONFIGURATION_DRAFT,
        CONFIGURATION_PUBLISH, CONFIGURATION_DEPRECATE,
        REPORT_VIEW, REPORT_GENERATE,
    ),
    ROLE_SUPER_ADMIN: (
        USER_MANAGE, ROLE_MANAGE, PLATFORM_MANAGE, AUDIT_VIEW,
    ),
    ROLE_LEGAL_DECISION_AUTHORITY: (
        LEGAL_DECISION, LEGAL_APPROVE_CUSTOMIZATION,
    ),
}
