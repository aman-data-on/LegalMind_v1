"""The deal brief and what we told the client — batch 3+4 (AB-218, 2026-11-20).

* ``GET /contracts/{id}/brief`` — the one-minute brief above the contract's tabs, for
  both personas, built here from the same sources every screen counts from: the counts
  are `deal_counts` itself (`AM-291`: one count) and the points `review_progress`'s
  ``to_decide`` through it. What the client asks for is one line per clause group the
  client changed, in contract order; what we told them only for a reader of positions
  (`legal_position.view`, LEGAL-02 — omitted, never nulled); our own mistake is the
  `OUR_ENTITY` observation (`AM-241`). A `legal.decision` holder also gets the Legal
  changes grouped by Legal's own ties — "goes further", "as we told them", "not
  discussed" — which add up to ``changes_left_legal``, the client's comments and the
  points no single clause holds. Read under the READ traversal (SEC-07: one 404).
* ``POST /contracts/{id}/positions`` and ``POST /contracts/{id}/positions/{key}`` —
  Legal records what we told the client, or its next version (replaced, re-tied,
  withdrawn). Only a `legal.decision` holder who may negotiate this contract
  (`contract_negotiable`: sent to Legal, assigned, or created by them — `AM-288` r2);
  the deal owner gets 403, anyone out of scope the one 404. Nothing is deleted.

A position is never a Legal Decision and never reaches the client: no reply, package,
annexure, send or export reads it (`workflow.positions`).
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select

from legalmind.analysis import consistency, negotiation
from legalmind.api.angles import whole_contract_points
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.routers.contracts import negotiation_stages
from legalmind.api.routers.negotiation import (
    _changes,
    _legal_left,
    _round_changes,
    client_version,
    deal_counts,
)
from legalmind.api.schemas import DealPositionWrite
from legalmind.db import models as M
from legalmind.db.lookup import contract_signed
from legalmind.mapping.service import load_clauses
from legalmind.security import permissions as P
from legalmind.security.authorization import LEGAL_BASES, negotiation_basis
from legalmind.security.errors import Forbidden, NotVisible
from legalmind.workflow import positions

router = APIRouter(tags=["negotiation"], route_class=CommitBeforeResponse)

#: the brief's "What the client asks for": this many lines, then "and N more"
ASKS_SHOWN = 6
_QUOTE_WORDS = 24
_LEADING_NUMBER = re.compile(r"^\W*\d+(?:\.\d+)*\.?\s*")


def _short(text: str) -> str:
    words = _LEADING_NUMBER.sub("", " ".join((text or "").split())).split(" ")
    return " ".join(words[:_QUOTE_WORDS]) + ("…" if len(words) > _QUOTE_WORDS else "")


def _quote(row: dict) -> tuple[str, bool]:
    """The client's own words on a row: the first sentence they wrote, else the first
    they removed (``removed``), else the clause."""
    lettered = (row.get("lawyer") or {}).get("points") or []
    said = next((p["after"] for p in lettered if p["after"]), None)
    if said:
        return _short(said), False
    gone = next((p["before"] for p in lettered if p["before"]), None)
    if gone:
        return _short(gone), True
    side = row["after"] or row["before"] or {}
    return _short(side.get("text", "")), row["after"] is None


def _line(row: dict, headings: dict[str, str]) -> dict[str, Any]:
    """A change as one brief line: its clause's top number and title, and the client's
    own words."""
    clause = row["clause"]
    top = (clause["number"] or "").split(".")[0].rstrip(".")
    quote, removed = _quote(row)
    title = ((clause.get("group") or {}).get("name") or headings.get(top)
             or clause["heading"] or clause.get("name") or quote[:60])
    return {"title": title.capitalize() if title.isupper() else title,     # no caps
            "clause": top or None, "quote": quote, "removed": removed,
            "row_key": row["row_key"]}


def _asks(rows: list[dict], headings: dict[str, str]) -> list[dict[str, Any]]:
    """One line per clause group the client changed, in contract order; formatting-only
    rows are not an ask."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["route_reason"] == negotiation.FORMATTING_ONLY:
            continue
        clause = row["clause"]
        top = (clause["number"] or "").split(".")[0].rstrip(".")
        key = f"{top}|{(clause.get('group') or {}).get('key') or ''}" if top \
            else f"|{clause['heading'] or row['row_key']}"
        if key not in out:
            out[key] = _line(row, headings)
    return list(out.values())


def _titled(row: dict, headings: dict[str, str]) -> bool:
    """Whether a row's clause has a heading of its own (else `_line` titles it with the
    client's words)."""
    clause = row["clause"]
    top = (clause["number"] or "").split(".")[0].rstrip(".")
    return bool((clause.get("group") or {}).get("name") or headings.get(top)
                or clause["heading"] or clause.get("name"))


def _not_marked(listed: dict, headings: dict[str, str]) -> dict[str, Any] | None:
    """Batch 8 R2.5 (`AM-461`): the changes the client made with no tracked change and
    no highlight — first in the brief, for both personas (no position in it): the count,
    the first lines in contract order, and whether highlights were read on their file.
    None when every change is marked (the key is then omitted)."""
    rows = [r for r in listed["changes"] if negotiation.not_marked(r)]
    if not rows:
        return None
    return {"count": len(rows), "total": len(listed["changes"]),
            "highlights_read": bool(listed["summary"].get("highlights_read")),
            # a title only where the clause has a heading — never its own words twice
            "rows": [{k: v for k, v in _line(r, headings).items()
                      if k != "title" or _titled(r, headings)}
                     for r in rows[:ASKS_SHOWN]],
            "more": max(0, len(rows) - ASKS_SHOWN)}


def _named(row: dict) -> str:
    """A change as Legal's list names it: its clause and title — the clause's heading,
    else its own first words."""
    label = negotiation.clause_label(row["clause"]) or ""
    if row["clause"]["heading"] or row["clause"].get("name"):
        return label
    words = _short((row["after"] or row["before"] or {}).get("text", "")).split(" ")
    return " ".join([label, *words[:6]]).strip() + ("…" if len(words) > 6 else "")


def _headings(db, version_id: UUID) -> dict[str, str]:
    """Each top-level clause's own heading on the client's paper (the first wins)."""
    out: dict[str, str] = {}
    for unit in negotiation._units(load_clauses(db, version_id)):
        number = (unit["number"] or "").rstrip(".")
        if number and "." not in number and unit["heading"]:
            out.setdefault(number, unit["heading"])
    return out


#: the brief's status, decided here (rule 18) — the screen only words it (`lib/labels`)
NOT_SENT, WITH_LEGAL = "NOT_SENT", "WITH_LEGAL"
WITH_LEGAL_AND_YOURS = "WITH_LEGAL_AND_YOURS"
YOURS_TO_ANSWER, POINTS_OPEN, SEND_REPLY = "YOURS_TO_ANSWER", "POINTS_OPEN", "SEND_REPLY"
REPLY_READY, WITH_CLIENT = "REPLY_READY", "WITH_CLIENT"
SEND_POINTS_TO_LEGAL, ALL_ANSWERED = "SEND_POINTS_TO_LEGAL", "ALL_ANSWERED"
LEGAL_QUEUE, LEGAL_POINTS, LEGAL_NOTHING = "LEGAL_QUEUE", "LEGAL_POINTS", "LEGAL_NOTHING"
#: round 5: no analysed Review of the client's version yet (reading, or failed) — the
#: points are unknown, so nothing is "ready to send" and nothing is "answered"
CHECKING = "CHECKING"
#: UI-01 (2026-11-23): stages whose next act is not a reply. FINAL ends the deal cycle
#: (`AM-318`) and SIGNED says itself (no line), so both win over every count;
#: READY_TO_SIGN makes the final contract, ON_HOLD waits on the client — never "Send our
#: reply"
FINAL_READY, PREPARE_FINAL, ON_HOLD = "FINAL_READY", "PREPARE_FINAL", "ON_HOLD"
_ENDED: dict[str, str | None] = {"FINAL": FINAL_READY, "SIGNED": None}
_STAGE_STATUS = {"READY_TO_SEND": REPLY_READY, "WITH_CLIENT": WITH_CLIENT,  # AM-260
                 "READY_TO_SIGN": PREPARE_FINAL, "ON_HOLD": ON_HOLD}


def status(counts: dict, stage: str | None, *, legal: bool,
           had_legal: bool = True) -> str | None:
    """Who acts next, from the one count (`deal_counts`) and the deal's stage. Legal: its
    queue (changes and points), or the points alone with no round. The deal owner: the
    changes with Legal, theirs to answer, the points with Legal or still to send to it
    (an open point is never hidden: round 3, D1), then the reply — "Legal answered every
    change" only where a change went to Legal (``had_legal``); None with no round (the
    Summary's points line stands in). Points unknown (no analysed Review — round 5):
    never a send or "answered" code, CHECKING instead. A stage with no reply to send
    says so (UI-01): the deal's end first, then Ready to sign and On hold."""
    points = counts.get("points_open") or 0
    known = "points_open" in counts
    if legal:
        if "changes_total" in counts and (counts.get("changes_left_legal") or points):
            return LEGAL_QUEUE
        if not known:
            return CHECKING
        return LEGAL_POINTS if points else LEGAL_NOTHING
    if stage in _ENDED:
        return _ENDED[stage]
    if "changes_total" not in counts:
        return None
    left_legal = counts.get("changes_left_legal") or 0
    mine = counts.get("changes_left_for_me") or 0
    if left_legal and not counts.get("sent_to_legal"):
        return NOT_SENT
    if left_legal:
        return WITH_LEGAL_AND_YOURS if mine else WITH_LEGAL
    if mine:
        return YOURS_TO_ANSWER
    if not known:
        return CHECKING
    if points:                              # the reply waits for them (AM-293)
        return POINTS_OPEN if counts.get("sent_to_legal") else SEND_POINTS_TO_LEGAL
    if counts.get("changes_left"):          # someone else's to answer: no send line
        return None
    if stage in _STAGE_STATUS:
        return _STAGE_STATUS[stage]
    # U1 r2 (D1): the client's version is back, every change accepted and nothing waits on
    # the client — no reply to send, the final contract is next: the To-do's own test
    # (`todo.py` prepare_final, CLIENT_RETURNED only; never once the final waits on Legal)
    if stage == "CLIENT_RETURNED" and not counts.get("changes_ours") \
            and not counts.get("points_waiting"):
        return PREPARE_FINAL
    return SEND_REPLY if had_legal else ALL_ANSWERED


def _writer(guard: Guard, contract: M.Contract) -> bool:
    """Whether THIS reader may record what we told the client — presentation only; the
    write checks again (`contract_negotiable` + `legal.decision`)."""
    return (P.LEGAL_DECISION in guard.permissions and contract.archived_at is None
            and negotiation_basis(guard.db, guard.user_id, contract) in LEGAL_BASES
            and not contract_signed(guard.db, contract.id))


def _legal(guard: Guard, rows: list[dict], listed: dict,
           review: M.Review | None) -> dict[str, Any]:
    """Legal's part: the Legal changes still open, by Legal's own tie (they add up to
    ``changes_left_legal``), the client's comments and the points on the whole
    contract. Grouping only — every change is still answered one by one."""
    tied = positions.ties(positions.current(guard.db, UUID(listed["contract_id"])))
    waiting = _legal_left(rows)
    left = [c for c in rows if c["row_key"] in waiting]
    beyond = [{"row_key": c["row_key"], "clause": _named(c)}
              for c in left if tied.get(c["row_key"], ("",))[0] == positions.BEYOND]
    as_told = sum(tied.get(c["row_key"], ("",))[0] == positions.AS_TOLD for c in left)
    commented = [*(c["clause"] for c in rows if (c["after"] or {}).get("comments")),
                 *(e["clause"] for e in listed.get("comments_elsewhere") or [])]
    note = None if review is None else guard.db.execute(
        select(M.ReviewAssignment.note).where(
            M.ReviewAssignment.review_id == review.id,
            M.ReviewAssignment.revoked_at.is_(None))
        .order_by(M.ReviewAssignment.created_at.desc()).limit(1)).scalar()
    return {"beyond": beyond, "as_told": as_told,
            "not_discussed": len(left) - len(beyond) - as_told,
            "comments": list(dict.fromkeys(c["number"] for c in commented
                                           if c["number"])),
            "whole_contract": (whole_contract_points(guard.db, review)
                               if review is not None else []),
            # AM-408: the deal owner's "Note for Legal", beside "Add what we told them"
            **({"note": note} if note else {})}


@router.get("/contracts/{contract_id}/brief")
def deal_brief(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    db = guard.db
    versions = list(db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == contract.id)).scalars())
    latest = max(versions, key=lambda v: v.version_number, default=None)
    theirs = client_version(versions)
    # BE-5: the open round's change list made once; the counts read the same rows
    made = (_round_changes(guard, contract, theirs, counting=False)
            if theirs is not None and P.DOCUMENT_VIEW in guard.permissions else None)
    counts = deal_counts(guard, [contract], listed={contract.id: made})[contract.id]
    stage = negotiation_stages(guard, [contract]).get(contract.id) or {}
    out: dict[str, Any] = {"counts": counts}
    rows: list[dict] = []
    listed: dict = {}
    if made is not None and "changes_total" in counts:
        listed, _, after = made
        rows = listed["changes"]
        headings = _headings(db, after.id)
        if (unmarked := _not_marked(listed, headings)) is not None:
            out["not_marked"] = unmarked                          # batch 8 R2.5, first
        asks = _asks(rows, headings)
        out.update(asks=asks[:ASKS_SHOWN], asks_more=max(0, len(asks) - ASKS_SHOWN))
    if (code := status(counts, stage.get("stage"),
                       legal=P.LEGAL_DECISION in guard.permissions,
                       had_legal=any(c["route"] == negotiation.HOLDER
                                     for c in rows))) is not None:
        out["status"] = code
    writer = _writer(guard, contract)
    if guard.sees_legal_position:                       # LEGAL-02: omitted otherwise
        out["told"] = [positions.view(db, p, writer=writer)
                       for p in positions.current(db, contract.id)]
    if latest is not None and P.DOCUMENT_VIEW in guard.permissions:
        mistake = next((o for o in consistency.observe(load_clauses(db, latest.id))
                        ["structural"] if o["kind"] == consistency.OUR_ENTITY), None)
        if mistake is not None:
            out["our_mistake"] = mistake["text"]
    if P.LEGAL_DECISION in guard.permissions:
        review = (negotiation._latest_review(db, latest)
                  if latest is not None and P.REVIEW_VIEW in guard.permissions else None)
        out["legal"] = {**_legal(guard, rows, listed or {"contract_id": str(contract.id)},
                                 review), "can_record": writer}
    return data(out)


def _write(guard: Guard, contract_id: UUID, body: DealPositionWrite,
           key: str | None) -> dict:
    contract = guard.contract_negotiable(contract_id, P.LEGAL_DECISION)
    # round 3 (lead D4): only once the deal is with Legal — a Legal basis (sent to Legal,
    # assigned, or created by them), never the owner's, a collaborator's or a Lead's
    if negotiation_basis(guard.db, guard.user_id, contract) not in LEGAL_BASES:
        raise Forbidden("Legal records what we told the client once the deal is sent "
                        "to Legal.")
    if key is None and (body.withdrawn or body.expected_version):
        raise BusinessRuleRejected("a new position starts at version 1")
    if body.ties and not body.withdrawn:
        theirs = client_version(list(guard.db.execute(select(M.DocumentVersion).where(
            M.DocumentVersion.contract_id == contract.id)).scalars()))
        rows = {} if theirs is None else {c["row_key"]: c for c in _changes(
            guard, contract, None, theirs.version_number, counting=True)[0]["changes"]}
        if any(rows.get(k, {}).get("route") != negotiation.HOLDER for k in body.ties):
            raise BusinessRuleRejected("a tie names a change of this round that Legal "
                                       "answers")
    try:
        row = positions.record(
            guard.db, contract, actor_id=guard.user_id, request_id=guard.request_id,
            text=body.text, told_on=body.told_on, tied=body.ties, position_key=key,
            expected_version=body.expected_version, withdrawn=body.withdrawn)
    except LookupError as exc:
        raise NotVisible("position not found") from exc
    except positions.PositionChanged as exc:
        raise Conflict("A colleague changed this first — reload to see it.") from exc
    except positions.RowTiedElsewhere as exc:
        raise Conflict("That change is already tied to something else we told them — "
                       "change that one first.") from exc
    return data(positions.view(guard.db, row, writer=True))


@router.post("/contracts/{contract_id}/positions", status_code=201)
def record_position(contract_id: UUID, body: DealPositionWrite,
                    guard: Guard = Depends(get_guard)) -> dict:
    return _write(guard, contract_id, body, None)


@router.post("/contracts/{contract_id}/positions/{position_key}", status_code=201)
def revise_position(contract_id: UUID, body: DealPositionWrite,
                    position_key: str = Path(..., max_length=32),
                    guard: Guard = Depends(get_guard)) -> dict:
    return _write(guard, contract_id, body, position_key)
