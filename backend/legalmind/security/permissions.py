"""Permission catalogue and canonical roles — Step 47 / SEC-04, amended by AB-12.

**Who uses LegalMind** (owner interview, 2026-09-05 — AB-12):

```text
Department User   runs their own deals: upload, analyse, read findings, ask
Department Lead   a Department User who also sees every deal in THEIR department,
                  transfers ownership inside it, and owns the Company Standards
Platform Admin    accounts, roles, departments, audit — never contract content
Developer         break-glass for debugging — never legal authority
```

Nobody approves a deviation inside LegalMind in the initial workflow (AB-12 r9):
a deviation is FLAGGED, and the yes/no happens outside the system. The legal
roles below are therefore **retained for a future legal workflow**, not active.

**How authority composes** — ROLE → PERMISSIONS → RESOURCE SCOPE → ACTION:

```text
permission        says WHAT the holder may do            (this module)
scope             says on WHICH objects                  (security/authorization.py)
                  OWN          contract.owner_id == caller
                  DEPARTMENT   `department.view` AND owner in the caller's department
                  PLATFORM     accounts and roles — no contract content at all
```

Names follow the dotted convention. Three of them are fixed by locked Step 23 and
are reproduced verbatim: ``legal.review``, ``legal.decision``,
``legal.approve_customization``.
"""

from __future__ import annotations

from typing import Final

# --- Contracts & documents ------------------------------------------------
CONTRACT_VIEW: Final = "contract.view"
CONTRACT_CREATE: Final = "contract.create"
CONTRACT_UPDATE: Final = "contract.update"
#: Archive (and restore) — AB-12 r6. Was `contract.delete` (AM-37); renamed
#: because nothing destroys a contract any more: an archived contract keeps its
#: document, versions, findings, reviews and audit trail, and can be read later.
CONTRACT_ARCHIVE: Final = "contract.archive"
#: Move a contract to another owner in the same department — AB-12 r5. The
#: Department Lead's coverage tool ("Aman is on leave; Neha takes the deal").
CONTRACT_TRANSFER: Final = "contract.transfer"
DOCUMENT_UPLOAD: Final = "document.upload"
DOCUMENT_VIEW: Final = "document.view"
DOCUMENT_DOWNLOAD: Final = "document.download"

# --- Department scope (AB-12 r3) -------------------------------------------
#: Widens READ scope from "my contracts" to "my department's contracts" — the
#: contract, its versions, evidence, reviews, findings, evaluations, reports and
#: comparisons. It is a SCOPE widener, not a new capability: every read still
#: needs its own permission (`document.view`, `finding.view`, …). It never widens
#: writes, and it never reaches another user's Ask history (AB-12 r8).
DEPARTMENT_VIEW: Final = "department.view"

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

# --- Internal legal position (LEGAL-02, as amended by AB-12 r7) ------------
#: Sees WHY a finding is what it is: the expected value, the comparison and the
#: explanation chain. AB-12 r7 grants it to every Department User for their own
#: contracts — the department IS the audience for the organisation's position;
#: "ordinary users" in LEGAL-02 means the counterparty, who never has an account.
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

# --- Assist lane (AB-3/AB-4) ----------------------------------------------
# AB-3's "Not changed" block anticipated exactly this: "The permission catalogue —
# extended by assist-lane access permissions only; no legal authority permission
# added, none altered." One permission: asking a grounded question about a document
# the holder can already view. It confers no legal authority of any kind (AM-25 r8).
ASSIST_ASK: Final = "assist.ask"

# --- Audit & administration ----------------------------------------------
AUDIT_VIEW: Final = "audit.view"
USER_MANAGE: Final = "user.manage"
ROLE_MANAGE: Final = "role.manage"
PLATFORM_MANAGE: Final = "platform.manage"


CATALOGUE: Final[dict[str, tuple[str, ...]]] = {
    "Contracts": (CONTRACT_VIEW, CONTRACT_CREATE, CONTRACT_UPDATE, CONTRACT_ARCHIVE,
                  CONTRACT_TRANSFER),
    "Department": (DEPARTMENT_VIEW,),
    "Documents": (DOCUMENT_UPLOAD, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD),
    "Reviews": (REVIEW_CREATE, REVIEW_VIEW),
    "Findings": (FINDING_VIEW, FINDING_COMMENT),
    "Evaluations": (EVALUATION_VIEW,),
    "Legal authority": (LEGAL_REVIEW, LEGAL_DECISION, LEGAL_APPROVE_CUSTOMIZATION),
    "Internal legal position": (LEGAL_POSITION_VIEW,),
    "Legal configuration": (CONFIGURATION_VIEW, CONFIGURATION_DRAFT,
                            CONFIGURATION_PUBLISH, CONFIGURATION_DEPRECATE),
    "Reporting": (REPORT_VIEW, REPORT_GENERATE, EXPORT_GENERATE),
    "Assist": (ASSIST_ASK,),
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

#: What an identity provider may never hand out on first sign-in (AB-12 r11).
#: `config.oidc_jit_roles()` names the roles a JIT-provisioned account receives;
#: a role carrying any of these is refused at provisioning time, whatever the
#: environment says. Legal authority (SEC-01: "authentication never confers Legal
#: Decision authority") and platform administration (an IdP misconfiguration must
#: not mint an administrator).
NEVER_PROVISIONED_BY_IDP: Final[frozenset[str]] = LEGAL_AUTHORITY_PERMISSIONS | {
    USER_MANAGE, ROLE_MANAGE, PLATFORM_MANAGE,
}


def is_legal_authority(permission: str) -> bool:
    return permission in LEGAL_AUTHORITY_PERMISSIONS


# --------------------------------------------------------------------------
# Role codes — AB-12 (2026-09-05) amends Step 23 (ROLE-06) and AB-9.
#
# The codes are what `roles.code` carries in the database. Two were renamed by
# the AB-12 migration so that the code says what the person does:
#   LEGAL_ADMIN  -> DEPARTMENT_LEAD     (the same role row; assignments kept)
#   SUPER_ADMIN  -> PLATFORM_ADMIN      (the same role row; assignments kept)
#
# LEGAL_DECISION_AUTHORITY is the SEC-03 mechanism: legal authority is carried
# as an ADDITIONAL role assignment, which is how two users holding the same
# primary role differ in legal authority (locked Step 4's Admin A / Admin B).
# --------------------------------------------------------------------------
ROLE_USER: Final = "USER"
ROLE_DEPARTMENT_LEAD: Final = "DEPARTMENT_LEAD"
ROLE_PLATFORM_ADMIN: Final = "PLATFORM_ADMIN"
ROLE_DEVELOPER: Final = "DEVELOPER"
# Retained for a future legal workflow (AB-12 r10). Seeded so an existing
# database keeps its rows, hidden from the grant picker, granted to nobody by the
# initial workflow.
ROLE_LEGAL_REVIEWER: Final = "LEGAL_REVIEWER"
ROLE_LEGAL_DECISION_AUTHORITY: Final = "LEGAL_DECISION_AUTHORITY"

ROLE_NAMES: Final[dict[str, str]] = {
    ROLE_USER: "Department User",
    ROLE_DEPARTMENT_LEAD: "Department Lead",
    ROLE_PLATFORM_ADMIN: "Platform Admin",
    ROLE_DEVELOPER: "Developer",
    ROLE_LEGAL_REVIEWER: "Legal Reviewer",
    ROLE_LEGAL_DECISION_AUTHORITY: "Legal Decision Authority",
}

#: Which kind of thing each role is — so a screen can say "Department Lead"
#: instead of making an administrator decode a code, and can keep the retained
#: legal roles out of the everyday picker (AB-12 r10).
TIER_DEPARTMENT: Final = "department"
TIER_PLATFORM: Final = "platform"
TIER_BREAK_GLASS: Final = "break_glass"
TIER_FUTURE_LEGAL: Final = "future_legal"

ROLE_TIERS: Final[dict[str, str]] = {
    ROLE_USER: TIER_DEPARTMENT,
    ROLE_DEPARTMENT_LEAD: TIER_DEPARTMENT,
    ROLE_PLATFORM_ADMIN: TIER_PLATFORM,
    ROLE_DEVELOPER: TIER_BREAK_GLASS,
    ROLE_LEGAL_REVIEWER: TIER_FUTURE_LEGAL,
    ROLE_LEGAL_DECISION_AUTHORITY: TIER_FUTURE_LEGAL,
}

# What a Department User does with their OWN deals. The Lead is this plus scope.
_DEPARTMENT_USER_GRANTS: Final[tuple[str, ...]] = (
    CONTRACT_VIEW, CONTRACT_CREATE, CONTRACT_UPDATE, CONTRACT_ARCHIVE,
    DOCUMENT_UPLOAD, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD,
    REVIEW_CREATE, REVIEW_VIEW,
    FINDING_VIEW, FINDING_COMMENT,
    EVALUATION_VIEW,
    # AB-12 r7: a user must be able to see WHY their own finding is a MATCH,
    # DEVIATION or MISSING — the standard, the comparison, the explanation.
    LEGAL_POSITION_VIEW,
    REPORT_VIEW, EXPORT_GENERATE,
    ASSIST_ASK,
)

# Default grants — every cell traces to Step 23's locked role summary as amended
# by AB-12. Note what is NOT here:
#
#  * DEPARTMENT_LEAD holds no `legal.review`. That permission widens scope to
#    every escalated Review on the platform (`REC-09`), which is exactly the
#    "lead sees everything globally" AB-12 r3 forbids. Department scope is
#    `department.view`, bounded by `users.department_id`.
#  * PLATFORM_ADMIN holds no contract, review or legal permission at all —
#    locked Step 23 ("No automatic Legal Decision authority") and Step 24 r8/r9
#    ("Contract-content access and platform administration are separate").
#  * DEVELOPER holds no legal authority (AB-12 r12, correcting AB-9 r2): a
#    debugging role that could rule on a contract is not a debugging role.
#  * Nobody holds `legal.decision` by default. It stays an explicit,
#    S-8-guarded grant of LEGAL_DECISION_AUTHORITY, for a future workflow.
DEFAULT_ROLE_GRANTS: Final[dict[str, tuple[str, ...]]] = {
    ROLE_USER: _DEPARTMENT_USER_GRANTS,
    ROLE_DEPARTMENT_LEAD: (
        *_DEPARTMENT_USER_GRANTS,
        DEPARTMENT_VIEW, CONTRACT_TRANSFER,
        CONFIGURATION_VIEW, CONFIGURATION_DRAFT,
        CONFIGURATION_PUBLISH, CONFIGURATION_DEPRECATE,
        REPORT_GENERATE,
    ),
    ROLE_PLATFORM_ADMIN: (
        USER_MANAGE, ROLE_MANAGE, PLATFORM_MANAGE, AUDIT_VIEW,
    ),
    ROLE_DEVELOPER: tuple(
        p for p in ALL_PERMISSIONS if p not in LEGAL_AUTHORITY_PERMISSIONS
    ),
    ROLE_LEGAL_REVIEWER: (
        CONTRACT_VIEW, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD,
        REVIEW_VIEW, FINDING_VIEW, FINDING_COMMENT, EVALUATION_VIEW,
        LEGAL_REVIEW, LEGAL_POSITION_VIEW,
        CONFIGURATION_VIEW,
        REPORT_VIEW, REPORT_GENERATE, EXPORT_GENERATE,
        ASSIST_ASK,
    ),
    ROLE_LEGAL_DECISION_AUTHORITY: (
        LEGAL_DECISION, LEGAL_APPROVE_CUSTOMIZATION,
    ),
}
