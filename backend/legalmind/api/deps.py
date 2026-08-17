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

from functools import cached_property
from typing import Any, Iterator
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession, sessionmaker

from legalmind.api.context import SESSION_COOKIE, request_id_of
from legalmind.config import database_url
from legalmind.db import models as M
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.authorization import (
    require_contract_visible,
    require_evaluation_visible,
    require_finding_visible,
    require_review_visible,
)
from legalmind.security.errors import Forbidden, NotVisible, Unauthenticated
from legalmind.security.resolver import effective_permissions
from legalmind.security.sessions import Principal, resolve_session

_engine = None
_sessionmaker = None


def _factory():
    """Lazy, so importing the app never opens a connection — the test harness
    replaces this dependency entirely."""
    global _engine, _sessionmaker
    if _sessionmaker is None:
        _engine = create_engine(database_url(), future=True, pool_pre_ping=True)
        _sessionmaker = sessionmaker(bind=_engine, future=True)
    return _sessionmaker


def get_db() -> Iterator[DBSession]:
    """One transaction per request — locked 43.26.

    The whole request commits or none of it does, so a partially written Finding
    or a decision without its audit event is not representable.
    """
    db = _factory()()
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
    """Resolve the server-side session — locked SEC-01, S-1.

    Only ``user_id`` comes out of the session. Authority is resolved from the
    database on every request, so a permission revoked mid-session takes effect
    on the very next one.
    """
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise Unauthenticated("no session cookie")
    try:
        session_id = UUID(raw)
    except (ValueError, AttributeError):
        # A malformed cookie is indistinguishable from being signed out (47.1.1
        # r2) — never an error that discloses anything about session state.
        raise Unauthenticated("no valid session") from None
    return resolve_session(db, session_id)


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
        # The request is about to abort, which would roll the audit row back with
        # it. Committing here is safe precisely because authorization runs BEFORE
        # any domain operation (43.23): there is nothing else in the transaction.
        self.db.commit()
        raise Forbidden(f"missing permission: {permission}")

    def _audit_not_visible(self, entity_type: str, entity_id: UUID) -> None:
        A.record(self.db, action=A.AUTHZ_OBJECT_NOT_VISIBLE,
                 entity_type=entity_type, entity_id=entity_id,
                 actor_id=self.user_id, request_id=self.request_id)
        self.db.commit()


def get_guard(request: Request, db: DBSession = Depends(get_db),
              principal: Principal = Depends(get_principal)) -> Guard:
    return Guard(request, db, principal)
