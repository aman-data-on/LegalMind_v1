"""What Legal told the client on a deal — batch 3+4 "deal brief" (AB-218).

A position is Legal's own words (≤ 500 characters), optionally the day they were told,
and the client changes Legal tied to it: "As we told them" (``AS_TOLD``) or "Goes
further than we told them" (``BEYOND``). Append-only and versioned per key: every save
is a new row (`DealPosition`), the current one the highest ``version_number``.

A tie is a LABEL on a change row, read by the Changes tab and the brief only. It never
enters `analysis.negotiation.changes` — so it can never change a route, an effect, an
answer, a Rule Outcome or the automatic acceptance (AM-384) — and it is never a Legal
Decision (rule 13). Nothing that builds a reply, a package, an annexure, a send or an
export reads this module (LEGAL-02).
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.security import audit

AS_TOLD, BEYOND = "AS_TOLD", "BEYOND"
TIES = (AS_TOLD, BEYOND)
TEXT_MAX = 500


class PositionChanged(Exception):
    """A colleague saved this position first (the version named is not the current)."""


class RowTiedElsewhere(Exception):
    """A change is already tied to another current position."""


def history(db: DBSession, contract_id: UUID) -> dict[str, list[M.DealPosition]]:
    """Every version of every position on this contract, by key, oldest first."""
    out: dict[str, list[M.DealPosition]] = {}
    for row in db.execute(select(M.DealPosition)
                          .where(M.DealPosition.contract_id == contract_id)
                          .order_by(M.DealPosition.created_at,
                                    M.DealPosition.version_number)).scalars():
        out.setdefault(row.position_key, []).append(row)
    return out


def current(db: DBSession, contract_id: UUID) -> list[M.DealPosition]:
    """The positions in force: each key's latest version, unless it was withdrawn — in
    the order they were first recorded."""
    return [rows[-1] for rows in history(db, contract_id).values()
            if not rows[-1].withdrawn]


def ties(positions: list[M.DealPosition]) -> dict[str, tuple[str, M.DealPosition]]:
    """row_key -> (tie, its position), from the current positions only."""
    return {key: (tie, p) for p in positions for key, tie in (p.ties or {}).items()}


def record(db: DBSession, contract: M.Contract, *, actor_id: UUID, request_id: str,
           text: str, told_on: date | None, tied: Mapping[str, str],
           position_key: str | None = None, expected_version: int = 0,
           withdrawn: bool = False) -> M.DealPosition:
    """A new version of a position (a new one when ``position_key`` is None). Refuses
    a stale ``expected_version`` (`PositionChanged`) and a row another current position
    already ties (`RowTiedElsewhere`). Audited without the words (LEGAL-02)."""
    rows = history(db, contract.id).get(position_key or "", []) if position_key else []
    latest = rows[-1].version_number if rows else 0
    if position_key is not None and not rows:
        raise LookupError(position_key)
    if expected_version != latest:
        raise PositionChanged(position_key)
    if not withdrawn:
        others = {k for p in current(db, contract.id) if p.position_key != position_key
                  for k in (p.ties or {})}
        if others & set(tied):
            raise RowTiedElsewhere(sorted(others & set(tied))[0])
    row = M.DealPosition(contract_id=contract.id,
                         position_key=position_key or uuid.uuid4().hex[:16],
                         version_number=latest + 1, text=text, told_on=told_on,
                         ties={} if withdrawn else dict(tied), withdrawn=withdrawn,
                         recorded_by=actor_id)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:                  # a concurrent save took the number
        raise PositionChanged(position_key) from exc
    audit.record(db, action=audit.DEAL_POSITION_RECORDED, entity_type="contract",
                 entity_id=contract.id, actor_id=actor_id, request_id=request_id,
                 after={"position_key": row.position_key,
                        "version_number": row.version_number,
                        "withdrawn": withdrawn, "ties": len(row.ties)})
    return row


def view(db: DBSession, p: M.DealPosition, *, writer: bool) -> dict[str, Any]:
    """A position for the page. Every reader of positions gets the words and the day;
    a writer (Legal) also its key, version, ties and who recorded it."""
    out: dict[str, Any] = {"text": p.text,
                           "told_on": p.told_on.isoformat() if p.told_on else None}
    if writer:
        out.update(position_key=p.position_key, version_number=p.version_number,
                   ties=dict(p.ties or {}), recorded_at=p.created_at.isoformat(),
                   recorded_by=db.execute(select(M.User.name).where(
                       M.User.id == p.recorded_by)).scalar())
    return out

