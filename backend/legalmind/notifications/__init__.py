"""In-app notifications and their e-mail — `AM-273` m3 (AB-150, 2026-11-02), R9.

A notification is a closed `kind`, a contract and a link. Its sentence is FIXED and
rendered when read, so nothing written here can carry clause text, a position or a
counterparty name. In-app the sentence names the contract — and only while the reader
can still read it (a transferred deal turns back into "a contract"). The e-mail never
names it: m3 allows the fixed sentence and a link, and the link is resolved through
normal authorization when it is opened.

Mail goes out only after the transaction commits, so a rolled-back event sends nothing.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event
from legalmind.outbound import mail
from legalmind.security import permissions as P
from legalmind.security.authorization import can_read_contract, can_see_review

DECISION_REQUESTED = "DECISION_REQUESTED"
DECIDED = "DECIDED"
CLIENT_RETURNED = "CLIENT_RETURNED"
ANSWER_CHANGED_BY_COLLEAGUE = "ANSWER_CHANGED_BY_COLLEAGUE"

#: The closed set. `{contract}` is the contract's name in-app, "a contract" in e-mail.
SENTENCES: dict[str, str] = {
    DECISION_REQUESTED: "A colleague asked you to decide a point on {contract}.",
    DECIDED: "A point on {contract} has been decided.",
    CLIENT_RETURNED: "The client returned a new version of {contract}.",
    ANSWER_CHANGED_BY_COLLEAGUE: "A colleague changed an answer on {contract}.",
}
UNNAMED = "a contract"
SUBJECT = "LegalMind: you have a new notification"


def _link(kind: str, contract_id: UUID) -> str:
    return f"/contracts/{contract_id}" + ("/changes" if kind == CLIENT_RETURNED else "")


def notify(db: DBSession, user_ids, kind: str, contract: M.Contract, *,
           actor_id: UUID | None = None) -> int:
    """One notice per recipient (never the actor), skipped when the same notice is
    already waiting unread. Returns how many were written."""
    if kind not in SENTENCES:
        raise ValueError(f"unknown notification kind {kind!r}")
    written = 0
    for user_id in dict.fromkeys(u for u in user_ids if u and u != actor_id):
        if db.execute(select(M.Notification.id).where(
                M.Notification.user_id == user_id, M.Notification.kind == kind,
                M.Notification.contract_id == contract.id,
                M.Notification.read_at.is_(None)).limit(1)).first():
            continue
        db.add(M.Notification(user_id=user_id, kind=kind, contract_id=contract.id,
                              link=_link(kind, contract.id)))
        user = db.get(M.User, user_id)
        if user is not None and user.email and user.status is E.UserStatus.ACTIVE:
            _queue_mail(db, user.email, kind, _link(kind, contract.id))
        written += 1
    db.flush()
    return written


# ---------------------------------------------------------------- the events
def escalation_raised(db: DBSession, review: M.Review, *, actor_id: UUID) -> int:
    """Asked to decide: every active Legal Decision Authority who can see the Review."""
    holders = db.execute(
        select(M.User.id).distinct()
        .join(M.UserRole, M.UserRole.user_id == M.User.id)
        .join(M.RolePermission, M.RolePermission.role_id == M.UserRole.role_id)
        .join(M.Permission, M.Permission.id == M.RolePermission.permission_id)
        .where(M.Permission.name == P.LEGAL_DECISION,
               M.User.status == E.UserStatus.ACTIVE)).scalars().all()
    contract = db.get(M.Contract, review.contract_id)
    if contract is None:
        return 0
    return notify(db, [u for u in holders if can_see_review(db, u, review)],
                  DECISION_REQUESTED, contract, actor_id=actor_id)


def decision_recorded(db: DBSession, finding: M.Finding, review: M.Review, *,
                      actor_id: UUID) -> int:
    """Decided: whoever raised the point, and the contract's owner."""
    contract = db.get(M.Contract, review.contract_id)
    if contract is None:
        return 0
    raisers = db.execute(select(M.Escalation.raised_by)
                         .where(M.Escalation.finding_id == finding.id)).scalars().all()
    return notify(db, [*raisers, contract.owner_id], DECIDED, contract, actor_id=actor_id)


def client_returned(db: DBSession, contract: M.Contract, *, actor_id: UUID) -> int:
    """A new CLIENT_MODIFIED version: the owner and every collaborator."""
    collaborators = db.execute(
        select(M.ContractCollaborator.user_id)
        .where(M.ContractCollaborator.contract_id == contract.id)).scalars().all()
    return notify(db, [contract.owner_id, *collaborators], CLIENT_RETURNED, contract,
                  actor_id=actor_id)


# ---------------------------------------------------------------- reading
def view(db: DBSession, user_id: UUID, n: M.Notification) -> dict:
    contract = db.get(M.Contract, n.contract_id) if n.contract_id else None
    named = contract is not None and can_read_contract(db, user_id, contract)
    return {"id": str(n.id), "kind": n.kind, "link": n.link,
            "sentence": SENTENCES[n.kind].format(
                contract=contract.name if named and contract else UNNAMED),
            "created_at": n.created_at.isoformat(),
            "read_at": n.read_at.isoformat() if n.read_at else None}


def mark_all_read(db: DBSession, user_id: UUID) -> None:
    db.execute(update(M.Notification)
               .where(M.Notification.user_id == user_id,
                      M.Notification.read_at.is_(None))
               .values(read_at=datetime.now(UTC)))


# ---------------------------------------------------------------- e-mail, after commit
def _message(to: str, kind: str, link: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = mail.sender(), to, SUBJECT
    base = os.environ.get("LEGALMIND_PUBLIC_URL", "").rstrip("/")
    msg.set_content(f"{SENTENCES[kind].format(contract=UNNAMED)}\n\n"
                    f"Open it in LegalMind: {base}{link}\n")
    return msg


def _queue_mail(db: DBSession, to: str, kind: str, link: str) -> None:
    if mail.transport() is None:
        return                              # default: no mail at all
    pending = db.info.setdefault("notification_mail", [])
    if not pending:
        event.listen(db, "after_commit", _deliver, once=True)
        event.listen(db, "after_rollback", _discard, once=True)
    pending.append(_message(to, kind, link))


def _discard(session: DBSession) -> None:
    session.info.pop("notification_mail", None)


def _deliver(session: DBSession) -> None:
    transport = mail.transport()
    for msg in session.info.pop("notification_mail", []):
        try:
            if transport is not None:
                transport.send(msg)
        except Exception as exc:          # a mail failure never fails the request
            log_event("notification.mail_failed", error=type(exc).__name__)
