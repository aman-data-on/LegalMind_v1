"""Request dependencies — the authorization boundary (locked 43.23, 47.6, 47.7).

Locked 43.23 puts authorization "at the API/service boundary, before any domain
operation" — never after fetching. ``Guard`` is that boundary, and every handler
goes through it.

**Object scope is resolved before the operation permission.** 47.7's table
describes a 403 as the case where "the object is visible; user lacks the operation
permission", so visibility is established first. Both orderings happen to be free
of an enumeration oracle — an unauthorized caller who receives 403 for every id
learns nothing — but this one matches the locked wording and matches the service
layer built in step 2, so the two cannot disagree.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import cached_property
from typing import Any
from uuid import UUID, uuid5

from fastapi import Depends, Request
from sqlalchemy.orm import Session as DBSession

from legalmind.api.context import SESSION_COOKIE, request_id_of
from legalmind.db import models as M
from legalmind.db.session import new_session
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security import tokens
from legalmind.security.authorization import (
    require_contract_visible,
    require_evaluation_visible,
    require_finding_visible,
    require_review_visible,
)
from legalmind.security.errors import Forbidden, NotVisible, Unauthenticated
from legalmind.security.resolver import effective_permissions
from legalmind.security.sessions import Principal, resolve_session


def get_db() -> Iterator[DBSession]:
    """One transaction per request — locked 43.26.

    The whole request commits or none of it does, so a partially written Finding
    or a decision without its audit event is not representable.

    The engine itself comes from ``db.session``, shared with the worker so that the
    two halves of the same image (55.1) cannot resolve the database differently. It
    is built on first use, so importing the app opens no connection and the test
    harness — which overrides this dependency — never touches it.
    """
    db = new_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_principal(request: Request,
                  db: DBSession = Depends(get_db)) -> Principal:
    """Resolve the caller's identity — locked SEC-01, S-1, and `AM-36` (AB-8).

    Two mechanisms, in a deliberate order.

    **The server-side session is tried first**, and it is the only mechanism the
    password fallback ever uses (`AM-36` t1 leaves it untouched). It is preferred
    because it is the revocable one: when both cookies are present, honouring the
    session means an administrator's revocation still bites.

    **Then the `AM-36` stateless token.** Only ``sub`` is taken from it. The
    ``email`` and ``roles`` claims are read past and discarded here — t3 makes
    them advisory, and this function is the one place a careless change could turn
    them into authority. Authority is resolved from the database on every request
    regardless of which mechanism identified the caller, so a permission revoked
    mid-session still takes effect on the very next request.

    **Account status is re-checked on the token path** (`AM-36` t4(b)). A
    server-side session is already refused the moment it is revoked; a token
    cannot be, so the one thing that must not wait 24 hours — a disabled account
    — is checked against the database here instead.
    """
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        try:
            session_id = UUID(raw)
        except (ValueError, AttributeError):
            # A malformed cookie is indistinguishable from being signed out
            # (47.1.1 r2) — never an error that discloses session state.
            raise Unauthenticated("no valid session") from None
        return resolve_session(db, session_id)

    token = request.cookies.get(tokens.TOKEN_COOKIE)
    if not token:
        raise Unauthenticated("no session cookie")
    claims = tokens.verify(token)          # raises the same non-disclosing 401
    user = db.get(M.User, claims.user_id)
    if user is None or user.status is not E.UserStatus.ACTIVE:
        # 47.1.3's status gating applies to EVERY mechanism. Amending the session
        # model must not create a route around a disabled account.
        raise Unauthenticated("no valid session")
    return Principal(user_id=claims.user_id,
                     session_id=uuid5(_TOKEN_NAMESPACE, token),
                     authenticated_at=claims.issued_at)


# A stateless token has no session row, but `Principal.session_id` is used for
# correlation in audit metadata and logs. Deriving it from the token gives a
# stable, non-reversible identifier for "this token" without inventing a row and
# without ever writing the token itself anywhere.
_TOKEN_NAMESPACE = UUID("6f0d5f1e-1c2b-4f6a-9a3d-7e8b0c1d2e3f")


class Guard:
    """The composed check every handler runs before touching the domain."""

    def __init__(self, request: Request, db: DBSession, principal: Principal):
        self.request = request
        self.db = db
        self.principal = principal

    # ---------------------------------------------------------------- basics
    @property
    def user_id(self) -> UUID:
        return self.principal.user_id

    @property
    def request_id(self) -> str:
        return request_id_of(self.request)

    @cached_property
    def permissions(self) -> frozenset[str]:
        """Resolved once per request, never across requests (S-1)."""
        return effective_permissions(self.db, self.user_id)

    @property
    def sees_legal_position(self) -> bool:
        """LEGAL-02 / 49.7 r4 — gates omission, not nulling."""
        return P.LEGAL_POSITION_VIEW in self.permissions

    # ------------------------------------------------- permission, no object
    def permission(self, permission: str) -> None:
        """For collection and non-object endpoints, where there is nothing to
        scope against and the permission is the whole gate."""
        if permission not in self.permissions:
            self._deny(permission, entity_type="endpoint", entity_id=None)

    def additional_permission(self, permission: str, *, entity_type: str,
                              entity_id: UUID) -> None:
        """A second permission on an object already resolved.

        Exists for exactly one locked case: ``legal.approve_customization`` is
        required *in addition to* ``legal.decision`` when the decision type is
        ``APPROVE_CUSTOMIZATION`` (Step 23, 47.5, 49.3).
        """
        self._require(permission, entity_type, entity_id)

    # --------------------------------------------------- object then permission
    def review(self, review_id: UUID, permission: str) -> M.Review:
        review = self._visible(require_review_visible, review_id, "review")
        self._require(permission, "review", review_id)
        return review

    def finding(self, finding_id: UUID, permission: str) -> M.Finding:
        finding = self._visible(require_finding_visible, finding_id, "finding")
        self._require(permission, "finding", finding_id)
        return finding

    def evaluation(self, evaluation_id: UUID, permission: str) -> M.Evaluation:
        ev = self._visible(require_evaluation_visible, evaluation_id, "evaluation")
        self._require(permission, "evaluation", evaluation_id)
        return ev

    def contract(self, contract_id: UUID, permission: str) -> M.Contract:
        contract = self._visible(require_contract_visible, contract_id, "contract")
        self._require(permission, "contract", contract_id)
        return contract

    def document_version(self, document_version_id: UUID,
                         permission: str) -> M.DocumentVersion:
        """Traverses to the owning Contract — locked 47.6: a Document Version is
        reachable only through a Contract the caller can see."""
        version = self.db.get(M.DocumentVersion, document_version_id)
        if version is None:
            self._audit_not_visible("document_version", document_version_id)
            raise NotVisible("document version not found")
        self._visible(require_contract_visible, version.contract_id, "contract")
        self._require(permission, "document_version", document_version_id)
        return version

    # ---------------------------------------------------------------- internals
    def _visible(self, resolver: Any, object_id: UUID, entity_type: str) -> Any:
        try:
            return resolver(self.db, self.user_id, object_id)
        except NotVisible:
            self._audit_not_visible(entity_type, object_id)
            raise

    def _require(self, permission: str, entity_type: str,
                 entity_id: UUID) -> None:
        if permission not in self.permissions:
            self._deny(permission, entity_type=entity_type, entity_id=entity_id)

    def _deny(self, permission: str, *, entity_type: str,
              entity_id: UUID | None) -> None:
        A.record(self.db, action=A.AUTHZ_PERMISSION_DENIED,
                 entity_type=entity_type, entity_id=entity_id,
                 actor_id=self.user_id, request_id=self.request_id,
                 after={"permission": permission})
        # Locked 53.5 — "permission denials; repeated denials on one object matter".
        # The object id is therefore deliberately included: without it the signal
        # cannot answer the question 53.5 asks. Identifiers only — the permission name
        # is the caller's own authority, not an internal legal position (49.5 r2).
        log_event("authz.denied", level=logging.WARNING,
                  request_id=self.request_id, actor_id=str(self.user_id),
                  permission=permission, entity_type=entity_type,
                  entity_id=str(entity_id) if entity_id else None,
                  signal="authz.denial_count")
        # The request is about to abort, which would roll the audit row back with
        # it. Committing here is safe precisely because authorization runs BEFORE
        # any domain operation (43.23): there is nothing else in the transaction.
        self.db.commit()
        raise Forbidden(f"missing permission: {permission}")

    def _audit_not_visible(self, entity_type: str, entity_id: UUID) -> None:
        A.record(self.db, action=A.AUTHZ_OBJECT_NOT_VISIBLE,
                 entity_type=entity_type, entity_id=entity_id,
                 actor_id=self.user_id, request_id=self.request_id)
        # Same 53.5 signal. An out-of-scope object returns a 404 to the caller
        # (SEC-07) and is recorded here, because a caller sweeping ids is precisely
        # the pattern "repeated denials on one object" is meant to surface.
        log_event("authz.object_not_visible", level=logging.WARNING,
                  request_id=self.request_id, actor_id=str(self.user_id),
                  entity_type=entity_type, entity_id=str(entity_id),
                  signal="authz.denial_count")
        self.db.commit()


def get_guard(request: Request, db: DBSession = Depends(get_db),
              principal: Principal = Depends(get_principal)) -> Guard:
    return Guard(request, db, principal)
