"""Object-level authorization — Step 47 §47.6 / SEC-06, scoped by AB-12.

Locked 41.24: "A user must never be able to access another user's Contract,
Document Version, Review, Finding, or Legal Decision merely by changing an ID
in an API request."

Locked 43.23 fixes the ordering: authentication -> role/permission -> object
scope -> operation -> domain operation. Authorization happens BEFORE the
domain operation, never after fetching.

**The Contract is the root of every scope decision** (AB-12). A Review, a
Finding, an Evaluation, a Document Version and its evidence are all reached
through the Contract they belong to, and the caller's relationship to that
Contract is one of:

```text
OWNER        contract.owner_id == caller                        read + write
DEPARTMENT   caller holds `department.view` AND the owner is in  read only
             the caller's department (users.department_id)
LEGAL_SCOPE  caller holds `legal.review` AND a Review of the     read only
             contract is in `REC-09` Legal scope — retained for
             a future legal workflow, no holder in the initial one
(none)       404 — existence is itself a disclosure (SEC-07)
```

Writes are OWNER only. A Department Lead who needs to act on a colleague's deal
takes ownership first (an explicit, audited transfer) — so "who may change this
contract" always has a one-word answer.

Visibility follows locked Step 24, as amended:
  r2  the creator is the initial owner unless explicitly transferred — the
      Contract's `owner_id` is that owner, and a transfer moves the Reviews
      with it (AB-12 r5); `reviews.created_by` stays as history
  r4  a User cannot access another User's Reviews by default
  r6  Legal Reviewer access is by assignment and/or explicit Legal scope
      (`REC-09`; `review_assignments` has no writer in V1)
  r8  a platform administrator has no automatic access to content
  r12 access is permission + resource scope, not role name
  r16 Legal access does not transfer ownership
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import ReviewStatus
from legalmind.security.errors import Forbidden, NotVisible
from legalmind.security.permissions import DEPARTMENT_VIEW, LEGAL_REVIEW
from legalmind.security.resolver import effective_permissions, has_permission

# The three bases on which a caller may read a Contract. Strings rather than an
# enum: they are recorded into `audit_events.after_state` and read back by humans.
OWNER: Final = "owner"
DEPARTMENT: Final = "department"
LEGAL_SCOPE: Final = "legal_scope"


# --------------------------------------------------------------------------
# Department boundary — AB-12 r3
# --------------------------------------------------------------------------
def department_of(db: DBSession, user_id: UUID) -> UUID | None:
    return db.execute(
        select(M.User.department_id).where(M.User.id == user_id)
    ).scalar_one_or_none()


def same_department(db: DBSession, user_a: UUID, user_b: UUID) -> bool:
    """Both accounts in the SAME, NON-NULL department.

    `NULL == NULL` is deliberately false: two accounts outside any department
    share nothing. There is no "everyone" department, and a Lead with no
    department set sees exactly their own deals until an administrator places
    them — never the whole platform (AB-12 r3: "never globally").
    """
    a = department_of(db, user_a)
    return a is not None and a == department_of(db, user_b)


# --------------------------------------------------------------------------
# Contract — the root
# --------------------------------------------------------------------------
def contract_read_basis(db: DBSession, user_id: UUID,
                        contract: M.Contract) -> str | None:
    """Why this caller may READ this Contract, or ``None`` if they may not.

    Archived contracts are readable on the same bases (AB-12 r6: archive is not
    deletion — "what did LegalMind know about this contract?" must stay
    answerable). Writes are refused separately, by the Guard.
    """
    if contract.owner_id == user_id:
        return OWNER
    permissions = effective_permissions(db, user_id)
    if DEPARTMENT_VIEW in permissions and same_department(db, user_id, contract.owner_id):
        return DEPARTMENT
    if LEGAL_REVIEW in permissions:
        reviews = db.execute(
            select(M.Review).where(M.Review.contract_id == contract.id)
        ).scalars().all()
        if any(review_in_legal_scope(db, review) for review in reviews):
            return LEGAL_SCOPE
    return None


def can_read_contract(db: DBSession, user_id: UUID, contract: M.Contract) -> bool:
    return contract_read_basis(db, user_id, contract) is not None


def require_contract_readable(db: DBSession, user_id: UUID,
                              contract_id: UUID) -> M.Contract:
    """Resolve a Contract for READING, or raise NotVisible.

    404 for "does not exist" and "not in your scope" alike (SEC-07): a contract
    out of scope and one that never existed are indistinguishable.
    """
    contract = db.get(M.Contract, contract_id)
    if contract is None or not can_read_contract(db, user_id, contract):
        raise NotVisible("contract not found")
    return contract


def require_contract_owned(db: DBSession, user_id: UUID,
                           contract_id: UUID) -> M.Contract:
    """Resolve a Contract for WRITING — ownership only, or raise NotVisible.

    Upload, update, archive, review creation and analysis all come through
    here. Department scope and Legal scope are read scopes and never become a
    way to alter someone else's paper (Step 24 r16/r17). This is the single
    choke point for by-id write access, so every write path inherits the rule
    rather than each remembering it.

    Note what this does NOT check: whether the contract is archived. An owner
    naming their own archived contract gets a 409 from the Guard, not a 404 —
    they are allowed to know it exists; they are not allowed to change it.
    """
    contract = db.get(M.Contract, contract_id)
    if contract is None or contract.owner_id != user_id:
        raise NotVisible("contract not found")
    return contract


# --------------------------------------------------------------------------
# Review visibility — rooted in the Contract
# --------------------------------------------------------------------------
def _has_legal_assignment(db: DBSession, review_id: UUID, user_id: UUID) -> bool:
    """Step 24 r6 — Legal Reviewer access is controlled by assignment."""
    return db.execute(
        select(M.ReviewAssignment.review_id).where(
            M.ReviewAssignment.review_id == review_id,
            M.ReviewAssignment.user_id == user_id,
            M.ReviewAssignment.revoked_at.is_(None),
        )
    ).first() is not None


def review_in_legal_scope(db: DBSession, review: M.Review) -> bool:
    """Whether a Review is in **Legal scope** — locked `REC-09`.

    `REC-09` defines the term locked Step 24 r6 uses and no locked record defined:

    ```text
    (a) any Finding has an escalation that has not been withdrawn
                                                    (Step 24 r5, AM-23)
    (b) the Review lifecycle status is LEGAL_REVIEW  (Step 30)
    ```

    Both are required, and neither implies the other. A user may escalate a Finding on
    a `RESOLVED` Review, and Step 30's state machine has no `RESOLVED → LEGAL_REVIEW`
    edge — so without (a) that escalation would be invisible to Legal. Conversely the
    engine derives `LEGAL_REVIEW` with no human escalation at all (Step 30 r6), and
    Step 30 defines that status as "one or more Findings require an authorized Legal
    decision" — so without (b), work the *engine* raised would wait for a human to
    escalate it first.

    This is a property of the **Review**, not of the caller. The caller's half is
    `legal.review`, checked separately — locked Step 24 r12: "permission + resource
    scope, not simply role name."
    """
    if review.status is ReviewStatus.LEGAL_REVIEW:
        return True
    return db.execute(
        select(M.Escalation.id)
        .join(M.Finding, M.Finding.id == M.Escalation.finding_id)
        .where(M.Finding.review_id == review.id,
               M.Escalation.withdrawn_at.is_(None))
        .limit(1)
    ).first() is not None


def can_see_review(db: DBSession, user_id: UUID, review: M.Review) -> bool:
    """Contract scope (owner or department), legal assignment, or Legal scope.
    Nothing else — not role name (r12).

    The first branch is what makes ownership transfer coherent (AB-12 r5): a
    Review follows its Contract, so the new owner sees the analysis history and
    the previous owner stops seeing it, without touching `reviews.created_by`.

    Legal scope confers **view access only**: it is not ownership (r16, r17) and
    not decision authority, which stays an explicit `legal.decision` grant
    checked per Evaluation (SEC-02, SEC-05, ROLE-05).
    """
    contract = db.get(M.Contract, review.contract_id)
    if (contract is not None
            and contract_read_basis(db, user_id, contract) in (OWNER, DEPARTMENT)):
        return True
    if _has_legal_assignment(db, review.id, user_id):
        return True
    if has_permission(db, user_id, LEGAL_REVIEW):
        return review_in_legal_scope(db, review)
    return False


def require_review_visible(db: DBSession, user_id: UUID,
                           review_id: UUID) -> M.Review:
    """Resolve a Review or raise NotVisible — 404 for both "does not exist" and
    "not yours" (SEC-07)."""
    review = db.get(M.Review, review_id)
    if review is None or not can_see_review(db, user_id, review):
        raise NotVisible("review not found")
    return review


# --------------------------------------------------------------------------
# Traversal: Legal Decision -> Evaluation -> Finding -> Review -> Contract
# --------------------------------------------------------------------------
def require_finding_visible(db: DBSession, user_id: UUID,
                            finding_id: UUID) -> M.Finding:
    finding = db.get(M.Finding, finding_id)
    if finding is None:
        raise NotVisible("finding not found")
    require_review_visible(db, user_id, finding.review_id)
    return finding


def require_evaluation_visible(db: DBSession, user_id: UUID,
                               evaluation_id: UUID) -> M.Evaluation:
    ev = db.get(M.Evaluation, evaluation_id)
    if ev is None:
        raise NotVisible("evaluation not found")
    require_finding_visible(db, user_id, ev.finding_id)
    return ev


# --------------------------------------------------------------------------
# The composed check used at every API entry point (43.23 ordering)
# --------------------------------------------------------------------------
def authorize_review_operation(db: DBSession, user_id: UUID, review_id: UUID,
                               permission: str) -> M.Review:
    """Object scope first, then operation permission.

    Order matters for disclosure: a user who cannot see the object gets 404
    regardless of their permissions, so permission level never reveals
    existence.
    """
    review = require_review_visible(db, user_id, review_id)
    if permission not in effective_permissions(db, user_id):
        raise Forbidden(f"missing permission: {permission}")
    return review


def authorize_evaluation_operation(db: DBSession, user_id: UUID,
                                   evaluation_id: UUID,
                                   permission: str) -> M.Evaluation:
    ev = require_evaluation_visible(db, user_id, evaluation_id)
    if permission not in effective_permissions(db, user_id):
        raise Forbidden(f"missing permission: {permission}")
    return ev


# --------------------------------------------------------------------------
# LEGAL-02 — internal legal position is permission-gated.
# --------------------------------------------------------------------------
# 49.7 r5 names "rule_outcome, thresholds and rule_configuration"; 49.5 r2 adds
# that no response may disclose "thresholds, rule outcomes or
# rule_configuration". The set below is that prohibition applied to the fields an
# Evaluation actually serializes:
#
#   rule_outcome           the outcome itself
#   expected_value         the threshold
#   operator               the comparison direction — the Rule step of the chain
#   comparison             expected-vs-actual, i.e. the threshold restated
#   explanation            reconstructs Evidence -> Fact -> STANDARD -> RULE ->
#                          Result, so it necessarily contains the standard and
#                          the rule. Rule 12's explainability is satisfied FOR
#                          THE AUDIENCE INTERNAL LEGAL POSITIONS ARE FOR — every
#                          holder of legal_position.view — which is precisely
#                          what LEGAL-02 permission-controls.
#   rule_configuration     locked 49.7 r4, named explicitly
#   legal_rule_version_id  identifies which Legal Rule was applied
#
# NOT in this set, deliberately: classification, actual_value, evaluated_facts,
# evidence and requires_decision. Those describe the COUNTERPARTY'S OWN CONTRACT
# and the fact that authorized review is needed — neither is an internal legal
# position, and 49.7's own worked example returns all of them ungated.
#
# Who holds `legal_position.view` changed under AB-12 r7: every Department User
# holds it, because the department IS the audience for the organisation's
# position on its own deals. The gate itself is unchanged and still bites for
# any account without the grant — a platform administrator, or a future
# counterparty-facing role.
LEGAL_POSITION_FIELDS = (
    "rule_outcome",
    "expected_value",
    "operator",
    "comparison",
    "explanation",
    "rule_configuration",
    "legal_rule_version_id",
)


def redact_legal_position(payload: dict, permitted: bool) -> dict:
    """OMIT, never null (49.7 r5 / Step 52.4).

    A null would still signal that a value exists. Omission conveys nothing.
    """
    if permitted:
        return payload
    return {k: v for k, v in payload.items() if k not in LEGAL_POSITION_FIELDS}
