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
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from uuid import UUID

from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event
from legalmind.outbound import mail
from legalmind.security import permissions as P
from legalmind.security.authorization import (
    can_read_contract,
    can_see_review,
    is_collaborator,
)

DECISION_REQUESTED = "DECISION_REQUESTED"
DECIDED = "DECIDED"
CLIENT_RETURNED = "CLIENT_RETURNED"
ANSWER_CHANGED_BY_COLLEAGUE = "ANSWER_CHANGED_BY_COLLEAGUE"
LEGAL_ANSWERED_ALL = "LEGAL_ANSWERED_ALL"
SENT_TO_LEGAL = "SENT_TO_LEGAL"          # AM-474: the owner sent the review to a lawyer
TAKEN_BACK = "TAKEN_BACK"                # AM-472: the owner took it back from them

#: The closed set. `{contract}` is the contract's name in-app, "a contract" in e-mail.
SENTENCES: dict[str, str] = {
    DECISION_REQUESTED: "A colleague asked you to decide a point on {contract}.",
    DECIDED: "A point on {contract} has been decided.",
    CLIENT_RETURNED: "The client returned a new version of {contract}.",
    ANSWER_CHANGED_BY_COLLEAGUE: "A colleague changed an answer on {contract}.",
    LEGAL_ANSWERED_ALL: "Legal has answered every change on {contract}. "
                        "Your turn: send our reply.",
    # "The owner": only a contract's owner sends or takes back (AM-170 r3), and the
    # notice stores no actor — so it is true even after a later transfer
    SENT_TO_LEGAL: "The owner sent {contract} to you for Legal review.",
    TAKEN_BACK: "The owner took {contract} back from Legal.",
}
UNNAMED = "a contract"
#: M1 (U2 r4): the shortest gap between two "sent to you" e-mails, per lawyer and contract
MAIL_GAP = timedelta(minutes=15)
SUBJECT = "LegalMind: you have a new notification"


def _link(kind: str, contract_id: UUID) -> str:
    return f"/contracts/{contract_id}" + (
        "/changes" if kind in (CLIENT_RETURNED, LEGAL_ANSWERED_ALL) else "")


def notify(db: DBSession, user_ids, kind: str, contract: M.Contract, *,
           actor_id: UUID | None = None, mail_too: bool = True) -> int:
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
        if (mail_too and user is not None and user.email
                and user.status is E.UserStatus.ACTIVE):
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
    """A new CLIENT_MODIFIED version: the owner and every collaborator who still is one
    (`AM-280` r2: active, in the owner's department)."""
    collaborators = db.execute(
        select(M.ContractCollaborator.user_id)
        .where(M.ContractCollaborator.contract_id == contract.id)).scalars().all()
    return notify(db, [contract.owner_id, *(u for u in collaborators
                                            if is_collaborator(db, u, contract))],
                  CLIENT_RETURNED, contract, actor_id=actor_id)


def _hand_off(db: DBSession, review: M.Review, reviewer_id: UUID, kind: str, *,
              actor_id: UUID) -> int:
    """AM-472/AM-474 (r2): a notice for every send and every take-back. The opposite
    notice still unread on the same contract is marked read first, so the inbox says
    only what is true now; `notify` then skips a same-kind notice still waiting unread."""
    contract = db.get(M.Contract, review.contract_id)
    if contract is None:
        return 0
    opposite = TAKEN_BACK if kind == SENT_TO_LEGAL else SENT_TO_LEGAL
    # M1 (U2 r4): a take-back is in-app only; a send e-mails at most once per
    # MAIL_GAP per lawyer per contract — a send/take-back loop never floods the inbox
    recent = db.execute(select(M.Notification.id).where(
        M.Notification.user_id == reviewer_id, M.Notification.contract_id == contract.id,
        M.Notification.kind == SENT_TO_LEGAL,
        M.Notification.created_at >= func.now() - MAIL_GAP).limit(1)).first()
    db.execute(update(M.Notification)
               .where(M.Notification.user_id == reviewer_id,
                      M.Notification.contract_id == contract.id,
                      M.Notification.kind == opposite, M.Notification.read_at.is_(None))
               .values(read_at=datetime.now(UTC)))
    return notify(db, [reviewer_id], kind, contract, actor_id=actor_id,
                  mail_too=kind == SENT_TO_LEGAL and recent is None)


def review_sent(db: DBSession, review: M.Review, reviewer_id: UUID, *,
                actor_id: UUID) -> int:
    """AM-474: the lawyer the owner just sent the review to."""
    return _hand_off(db, review, reviewer_id, SENT_TO_LEGAL, actor_id=actor_id)


def review_taken_back(db: DBSession, review: M.Review, reviewer_id: UUID, *,
                      actor_id: UUID) -> int:
    """AM-472: the lawyer the owner took the review back from. Named only while they can
    still read the contract (`view`; AM-170 r4 ends an assignment-only basis here)."""
    return _hand_off(db, review, reviewer_id, TAKEN_BACK, actor_id=actor_id)


def answered_all_told(db: DBSession, contract: M.Contract, since: datetime) -> bool:
    """Whether the owner was already told for the client version received at ``since``."""
    return db.execute(select(M.Notification.id).where(
        M.Notification.user_id == contract.owner_id,
        M.Notification.kind == LEGAL_ANSWERED_ALL,
        M.Notification.contract_id == contract.id,
        M.Notification.created_at >= since).limit(1)).first() is not None


def legal_answered_all(db: DBSession, contract: M.Contract, since: datetime, *,
                       actor_id: UUID) -> int:
    """The last client change waiting for Legal was answered (batch 3+4): the deal owner,
    once per round — never again for the same client version (``since``: when it came
    in), read or unread, so a reopened and re-answered change sends nothing more."""
    if answered_all_told(db, contract, since):
        return 0
    return notify(db, [contract.owner_id], LEGAL_ANSWERED_ALL, contract,
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
