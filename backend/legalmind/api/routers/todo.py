"""My To-do — `AM-264` (AB-150, CLM R8, 2026-11-02).

What is waiting on THE CALLER, resolved server-side (rule 18) from the same scopes every
other list uses — nothing here widens what a caller can read:

```text
decide             points I can decide       `legal.decision`, Reviews in my scope
second_approval    a colleague's decision    `legal.decision`; the standard needs a
                   awaiting my co-signature  second person (Step 31 r15); not mine
client_returned    the client returned a     my deals (owner or `AM-259` collaborator)
                   version — our turn        at CLIENT_RETURNED (`AM-260`), none mine
changes_to_answer  changes left to me        the same deal, in its place (`AM-291`: one
                                             task per contract per person)
reply_ready        our reply is ready to     the same deals at READY_TO_SEND (`AM-293`:
                   send                      nothing undecided in it)
contract_decision  every point is decided —  `legal.decision`; the latest version's
                   record the decision on    Review is with me, RESOLVED, and holds no
                   the contract              current contract decision (`AM-318`)
prepare_final      every change is answered  my deals at CLIENT_RETURNED with nothing
                   — prepare the final       left, or Ready for the final contract
                   contract                  (`AM-318`)
answered           Legal answered me         my escalations / reviews I sent, 14 days
```

Every item is a fixed sentence, a link and a date: never clause text, a position or a
counterparty name. Archived contracts and superseded versions wait on nobody.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select

from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.routers.amendments import final_copy
from legalmind.api.routers.contracts import negotiation_stages
from legalmind.api.routers.negotiation import deal_counts
from legalmind.api.routers.reviews import _visible_reviews, with_legal
from legalmind.db import models as M
from legalmind.db.lookup import contract_signed
from legalmind.domain import enums as E
from legalmind.evaluation.workflow import current_decision, second_person_needed
from legalmind.security import permissions as P
from legalmind.security.authorization import can_read_contract
from legalmind.workflow.review_lifecycle import is_superseded
from legalmind.workflow.review_progress import review_progress

router = APIRouter(tags=["todo"], route_class=CommitBeforeResponse)

KINDS = ("decide", "second_approval", "client_returned", "changes_to_answer",
         "reply_ready", "answered", "contract_decision", "prepare_final")
#: AM-318: the two closing sentences, said the same way wherever they appear
DECIDE_CONTRACT = "Every point is decided. Record the decision on the contract."
PREPARE_FINAL = "Every change is answered. Prepare the final contract."
#: ponytail: no "seen" state exists, so an answer leaves the list after a fixed window;
#: a read marker (the notifications table, `AM-273`) is the upgrade.
ANSWERED_WINDOW = timedelta(days=14)
_ACTIVE = (E.ReviewStatus.ANALYSIS_COMPLETE, E.ReviewStatus.LEGAL_REVIEW)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def contract_link(contract_id: UUID, tab: str = "") -> str:
    """The readable contract path (`AM-263`)."""
    return f"/contracts/{contract_id}" + (f"/{tab}" if tab else "")


def _item(kind: str, contract: M.Contract, sentence: str, link: str,
          since: datetime | None, **extra: Any) -> dict:
    return {"kind": kind, "contract_id": str(contract.id), "contract_name": contract.name,
            "sentence": sentence, "link": link,
            "since": since.isoformat() if since else None, **extra}


def _decisions(guard: Guard) -> list[dict]:
    """Points I can decide and co-signatures I owe, per Review."""
    db, me = guard.db, guard.user_id
    reviews = db.execute(
        _visible_reviews(guard)
        .join(M.Contract, M.Contract.id == M.Review.contract_id)
        .where(M.Review.status.in_(_ACTIVE), M.Contract.archived_at.is_(None),
               with_legal(me),                  # B11: what is with Legal now
               M.Review.id.in_(select(M.Finding.review_id).where(
                   M.Finding.status == E.FindingStatus.DECISION_REQUIRED)))
    ).scalars().all()
    out: list[dict] = []
    for review in reviews:
        if is_superseded(db, review):
            continue
        contract = db.get(M.Contract, review.contract_id)
        assert contract is not None
        link = contract_link(contract.id)
        progress = review_progress(db, review, legal_position=guard.sees_legal_position)
        waiting = db.execute(
            select(M.Finding.created_at).where(
                M.Finding.review_id == review.id,
                M.Finding.status == E.FindingStatus.DECISION_REQUIRED)
            .order_by(M.Finding.created_at)).scalars().first()
        cosign: list[datetime] = []
        # ponytail: one query per undecided Evaluation; bounded by the open points in
        # scope. A grouped query is the upgrade if a Legal queue grows into hundreds.
        for ev in db.execute(
                select(M.Evaluation)
                .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
                .where(M.Finding.review_id == review.id,
                       M.Finding.status == E.FindingStatus.DECISION_REQUIRED)).scalars():
            d = current_decision(db, ev.id)
            if (d is None or d.decision_type is E.DecisionType.REQUEST_CLARIFICATION
                    or d.decided_by == me
                    or not second_person_needed(db, ev, d.decided_by)):  # AM-289
                continue
            prev = db.execute(select(M.LegalDecision).where(
                M.LegalDecision.evaluation_id == ev.id,
                M.LegalDecision.version_number == d.version_number - 1)).scalar()
            if prev is None or prev.decision_type is not d.decision_type \
                    or prev.decided_by == d.decided_by:
                cosign.append(d.created_at)
        if cosign:
            out.append(_item("second_approval", contract, _plural(
                len(cosign), "decision awaits your second approval.",
                "decisions await your second approval."), link, min(cosign),
                review_id=str(review.id), count=len(cosign)))
        if progress["to_decide"]:
            # N13: the client's changes waiting on the same person, in the same line
            changes = deal_counts(guard, [contract])[contract.id].get(
                "changes_left_for_me", 0)
            points = _plural(progress["to_decide"], "point", "points")
            sentence = (f"{points} and {_plural(changes, 'change', 'changes')} await "
                        "your decision." if changes else _plural(
                            progress["to_decide"], "point awaits your decision.",
                            "points await your decision."))
            out.append(_item("decide", contract, sentence, link, waiting,
                             review_id=str(review.id), count=progress["to_decide"],
                             **({"changes": changes} if changes else {})))
    return out + _contract_decisions(guard)


def _contract_decisions(guard: Guard) -> list[dict]:
    """`AM-318` A3: a Review with me whose points are all decided and whose contract
    decision is due — on the latest version of a deal that is not Final or signed."""
    db, me = guard.db, guard.user_id
    Rec = M.ContractOutcomeRecord
    out: list[dict] = []
    for review in db.execute(
            _visible_reviews(guard)
            .join(M.Contract, M.Contract.id == M.Review.contract_id)
            .where(M.Review.status == E.ReviewStatus.RESOLVED,
                   M.Contract.archived_at.is_(None), with_legal(me))).scalars():
        if is_superseded(db, review) or contract_signed(db, review.contract_id):
            continue
        latest = db.execute(select(Rec).where(Rec.review_id == review.id)
                            .order_by(Rec.version_number.desc()).limit(1)).scalar()
        if latest is not None and not (review.reopened_at
                                       and review.reopened_at > latest.created_at):
            continue
        contract = db.get(M.Contract, review.contract_id)
        assert contract is not None
        out.append(_item("contract_decision", contract, DECIDE_CONTRACT,
                         contract_link(contract.id),
                         review.reopened_at or review.completed_at or review.created_at,
                         review_id=str(review.id)))
    return out


def _my_deals(guard: Guard) -> list[dict]:
    """Client returns on the deals I own or collaborate on, and the changes left to me."""
    db = guard.db
    if P.DOCUMENT_VIEW not in guard.permissions:
        return []
    mine = db.execute(select(M.Contract).where(
        M.Contract.archived_at.is_(None),
        or_(M.Contract.owner_id == guard.user_id, M.Contract.id.in_(
            select(M.ContractCollaborator.contract_id).where(
                M.ContractCollaborator.user_id == guard.user_id))))).scalars().all()
    # AM-280 r2/r3: a collaborator who moved department reads nothing here, so the
    # deal waits on them no more and its name is never shown to them
    mine = [c for c in mine if can_read_contract(db, guard.user_id, c)]
    stages = negotiation_stages(guard, list(mine))
    returned = [c for c in mine if stages.get(c.id, {}).get("stage") == "CLIENT_RETURNED"]
    counts = deal_counts(guard, returned)
    out: list[dict] = [
        _item("reply_ready", c, "Our reply is ready to send to the client.",
              contract_link(c.id), datetime.fromisoformat(stages[c.id]["since"]),
              days=stages[c.id]["days"])
        for c in mine if stages.get(c.id, {}).get("stage") == "READY_TO_SEND"]
    out += [_item("prepare_final", c, PREPARE_FINAL, contract_link(c.id),
                  datetime.fromisoformat(stages[c.id]["since"]),
                  days=stages[c.id]["days"])
            for c in mine if stages.get(c.id, {}).get("stage") == "READY_TO_SIGN"]
    for contract in returned:
        stage, n = stages[contract.id], counts[contract.id]
        # `AM-291`: ONE task per contract per person — the changes left to me; the
        # return itself once every change is answered (our reply is next) or while the
        # list cannot be read; nothing while what is left waits on Legal
        left, total = n.get("changes_left_for_me", 0), n.get("changes_total", 0)
        if not left and n.get("changes_left"):
            continue
        kind, sentence = ("client_returned",
                          "The client returned a new version — it is our turn.")
        if "changes_total" in n and not n.get("changes_left"):
            kind, sentence = "prepare_final", PREPARE_FINAL       # AM-318 A3
        if left:
            verb = "is" if left == 1 else "are"
            kind = "changes_to_answer"
            sentence = (f"{left} of {_plural(total, 'change', 'changes')} {verb} "
                        "yours to answer.")
        out.append(_item(kind, contract, sentence, contract_link(contract.id, "changes"),
                         datetime.fromisoformat(stage["since"]), days=stage["days"],
                         counts=n, **({"count": left} if left else {})))
    return out


def _answers(guard: Guard) -> list[dict]:
    """Legal's answers to what I asked: my escalations, and the reviews I sent."""
    db, me = guard.db, guard.user_id
    cutoff = datetime.now(UTC) - ANSWERED_WINDOW
    rows: dict[tuple[UUID, str], datetime] = {}
    for contract_id, at in db.execute(
            select(M.Review.contract_id, M.LegalDecision.created_at)
            .join(M.Finding, M.Finding.review_id == M.Review.id)
            .join(M.Escalation, M.Escalation.finding_id == M.Finding.id)
            .join(M.LegalDecision, M.LegalDecision.finding_id == M.Finding.id)
            .where(M.Escalation.raised_by == me, M.Escalation.withdrawn_at.is_(None),
                   M.LegalDecision.created_at >= M.Escalation.created_at,
                   M.LegalDecision.created_at >= cutoff,
                   M.LegalDecision.decided_by != me)):
        key = (contract_id, "escalation")
        rows[key] = max(rows.get(key, at), at)
    for contract_id, at in db.execute(
            select(M.Review.contract_id, M.ContractOutcomeRecord.created_at)
            .join(M.ReviewAssignment, M.ReviewAssignment.review_id == M.Review.id)
            .join(M.ContractOutcomeRecord,
                  M.ContractOutcomeRecord.review_id == M.Review.id)
            .where(M.ReviewAssignment.assigned_by == me,
                   M.ContractOutcomeRecord.created_at >= cutoff,
                   M.ContractOutcomeRecord.decided_by != me)):
        key = (contract_id, "outcome")
        rows[key] = max(rows.get(key, at), at)
    words = {"escalation": "Legal recorded a decision on the point you escalated.",
             "outcome": "The reviewer recorded the decision on the contract you sent."}
    out: list[dict] = []
    for (contract_id, what), at in rows.items():
        contract = db.get(M.Contract, contract_id)
        # B10: nothing waits on a signed contract; AM-318: nor on a Final one
        if contract is None or contract.archived_at is not None \
                or not can_read_contract(db, me, contract) \
                or contract_signed(db, contract.id) \
                or final_copy(db, contract.id) is not None:
            continue
        out.append(_item("answered", contract, words[what],
                         contract_link(contract.id), at))
    return out


@router.get("/todo")
def todo(guard: Guard = Depends(get_guard)) -> dict:
    """Everything waiting on the caller, oldest first (`AM-264`). Each kind needs what
    its source already needs; a caller holding none of it gets an empty list."""
    items: list[dict] = []
    if P.REVIEW_VIEW in guard.permissions:
        if P.LEGAL_DECISION in guard.permissions:
            items += _decisions(guard)
        items += _answers(guard)
    if P.CONTRACT_VIEW in guard.permissions:
        items += _my_deals(guard)
    items.sort(key=lambda i: i["since"] or "")
    return data({"items": items,
                 "counts": {k: sum(i["kind"] == k for i in items) for k in KINDS}})
