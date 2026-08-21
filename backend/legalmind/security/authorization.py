"""Object-level authorization — Step 47 §47.6 / SEC-06.

Locked 41.24: "A user must never be able to access another user's Contract,
Document Version, Review, Finding, or Legal Decision merely by changing an ID
in an API request."

Locked 43.23 fixes the ordering: authentication -> role/permission -> object
ownership -> operation -> domain operation. Authorization happens BEFORE the
domain operation, never after fetching.

Visibility follows locked Step 24:
  r3  a User can access their own Reviews
  r4  a User cannot access another User's Reviews by default
  r5  escalation makes the Review available to the authorized Legal workflow
  r6  Legal Reviewer access is by assignment and/or explicit Legal scope
      — "explicit Legal scope" defined by locked REC-09; see
      `review_in_legal_scope`. Assignment has no writer in V1 (G1,
      deferred to V2), so Legal scope is the operative branch.
  r8  Super Admin does NOT automatically have access to Legal content
  r12 access is permission + resource scope, not role name
  r16 Legal access does not transfer ownership
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import ReviewStatus
from legalmind.security.errors import Forbidden, NotVisible
from legalmind.security.permissions import LEGAL_REVIEW
from legalmind.security.resolver import effective_permissions, has_permission


# --------------------------------------------------------------------------
# Review visibility
# --------------------------------------------------------------------------
def _is_review_owner(review: M.Review, user_id: UUID) -> bool:
    """Step 24 r2 — the creator is the initial owner.

    Review ownership TRANSFER is not implemented in V1: locked 42.13 carries
    `created_by` and no `owner_id`, so transfer is not representable without
    amending a locked table. Step 24 r2 permits transfer ("unless ... explicitly
    transferred") but no locked rule requires the capability. Recorded as a V1+
    item rather than amended in.
    """
    return review.created_by == user_id


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
    """Ownership, legal assignment, or Legal scope. Nothing else — not role name (r12).

    The third branch is locked `REC-09`, which resolved finding `F-6`: before it, both
    branches of Step 24 r6 were unimplementable — nothing populates
    `review_assignments`, and "explicit Legal scope" was undefined — so a Legal
    Reviewer could reach no Review at all.

    Permission is tested before scope, in the order locked r12 states it. Legal scope
    confers **view access only**: it is not ownership (r16, r17) and not decision
    authority, which stays an explicit `legal.decision` grant checked per Evaluation
    (SEC-02, SEC-05, ROLE-05).
    """
    if _is_review_owner(review, user_id):
        return True
    if _has_legal_assignment(db, review.id, user_id):
        return True
    if has_permission(db, user_id, LEGAL_REVIEW):
        return review_in_legal_scope(db, review)
    return False


def require_review_visible(db: DBSession, user_id: UUID,
                           review_id: UUID) -> M.Review:
    """Resolve a Review or raise NotVisible.

    Returns 404-equivalent for both "does not exist" and "not yours" so the two
    are indistinguishable to the caller (SEC-07).
    """
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


def require_contract_visible(db: DBSession, user_id: UUID,
                             contract_id: UUID) -> M.Contract:
    c = db.get(M.Contract, contract_id)
    if c is None or c.owner_id != user_id:
        raise NotVisible("contract not found")
    return c


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
