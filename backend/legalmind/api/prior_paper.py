"""Batch 8 item 1 (`AM-464`): "already agreed before" — whether a clause or a point of
the client's paper was already in a contract we signed or finalised with the same client.

Information only (rules 10/13): never a Finding, a route, an effect, an answer, the
automatic acceptance or a Legal Decision — it is added to a change list or an angles
payload after all of those are made (R1.5). Rule 18 (R1.7): another contract is named,
counted or read only when this reader may read it (`can_read_contract`, the read rule
itself), checked before any of its text is loaded; each one used is resolved through
`guard.contract_readable`, so a read across owners is audited as opening it would be.
Every key is omitted, never nulled, where nothing qualifies (SEC-07).
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select

from legalmind.analysis import negotiation, reader_generation
from legalmind.api.angles import _rows as point_rows
from legalmind.api.deps import Guard
from legalmind.api.routers import execution
from legalmind.api.routers.amendments import _final_signed, _signed_at
from legalmind.api.routers.contracts import derive_stages
from legalmind.db import models as M
from legalmind.mapping.engine import Clause
from legalmind.mapping.service import load_clauses
from legalmind.security import permissions as P
from legalmind.security.authorization import can_read_contract

#: the stages whose agreed text counts (owner Q2: both, each labelled)
AGREED = ("SIGNED", "FINAL")
# ponytail: one client holds a handful of signed papers; raise when one holds more
_PAPERS = 5
SAME, CHANGED, NEW, IN_SIGNED = "SAME", "CHANGED", "NEW", "IN_SIGNED"
_NUMBER = re.compile(r"\d[\d.]*")


def papers(guard: Guard, contract: M.Contract) -> list[dict[str, Any]]:
    """The client's other contracts that are SIGNED or FINAL and this reader may read,
    most recent first, at most `_PAPERS` — each with its agreed text (`_final_signed`:
    the signed copy, else the final copy) and when it was agreed (`_signed_at`)."""
    db = guard.db
    if contract.counterparty_id is None or P.DOCUMENT_VIEW not in guard.permissions:
        return []
    others = [c for c in db.execute(select(M.Contract).where(
        M.Contract.counterparty_id == contract.counterparty_id,
        M.Contract.id != contract.id, M.Contract.archived_at.is_(None))
        .order_by(M.Contract.id)).scalars()
        if can_read_contract(db, guard.user_id, c)]             # R1.7: before any text
    stages = derive_stages(db, others)
    found: list[dict[str, Any]] = []
    for c in others:
        kind = (stages.get(c.id) or {}).get("stage")
        version = _final_signed(db, c.id) if kind in AGREED else None
        if version is not None:
            found.append({"contract": c, "version": version, "kind": kind,
                          "at": _agreed_on(db, c.id, version)})
    found.sort(key=lambda p: (p["at"], str(p["contract"].id)), reverse=True)
    for p in found[:_PAPERS]:
        guard.contract_readable(p["contract"].id, P.DOCUMENT_VIEW)   # audited, as opened
    return found[:_PAPERS]


def _agreed_on(db, contract_id: UUID, version: M.DocumentVersion) -> date:
    """When it was agreed: the latest signing date its record names (a copy filed as
    signed says it when the owner adds who signed), else `_signed_at` (the record
    confirmed, or Final), else when the agreed copy was filed."""
    record = execution.current(db, contract_id)
    said = [s["signed_on"] for s in (record.signatories or []) if s.get("signed_on")] \
        if record is not None else []
    if said:
        return date.fromisoformat(max(said))
    return (_signed_at(db, contract_id) or version.created_at).date()


def public(paper: dict[str, Any]) -> dict[str, str]:
    return {"contract_id": str(paper["contract"].id), "name": paper["contract"].name,
            "agreed_on": paper["at"].isoformat(), "kind": paper["kind"]}


def _words(text: str) -> str:
    """A clause's words as `negotiation.same_words` compares them, a leading clause
    number aside (renumbering is not a change)."""
    tokens = negotiation._tokens(text, None)
    return " ".join(tokens[1:] if tokens and _NUMBER.fullmatch(tokens[0]) else tokens)


def _same(o: dict, n: dict) -> bool:
    """The same words (`AM-317` r1 / `AM-321` r2) — or, as `AM-462` (c8) reads a clause
    beside a changed table, only table rows or short title lines differ: the clause's
    own wording is the one we signed."""
    if negotiation.same_words(o["text"], n["text"], o["number"], n["number"]):
        return True
    rows = dict(zip(n["evidence_ids"], n["texts"], strict=True))
    changed = negotiation.changed_rows(o, n)
    return bool(changed) and all(negotiation._row_by_row(rows[e]) for e in changed)


def _aligned(ours: list[Clause], theirs: list[Clause]) -> dict[str, Any]:
    """The client's units against the earlier contract's — the pairing every change list
    makes (`_units`, `_align`, headings folded): SAME (the same words), CHANGED (paired,
    other words) or NEW (unpaired), by the client's evidence row; and the earlier
    contract's clauses as words, for a clause the client deleted."""
    old, new = negotiation._units(ours), negotiation._units(theirs)
    state = [NEW] * len(new)
    for i, j, _ in negotiation.fold_headings(old, new, negotiation._align(old, new)):
        if i is not None and j is not None:
            state[j] = SAME if _same(old[i], new[j]) else CHANGED
    return {"at": {e: j for j, u in enumerate(new) for e in u["evidence_ids"]},
            "state": state, "words": sorted({_words(u["text"]) for u in old})}


def _read(db, paper: M.DocumentVersion, after: M.DocumentVersion) -> dict[str, Any]:
    """`_aligned` for one earlier contract and the client's version — kept per process
    under the comparison's own content key (P2 `process_memo`), so a page reload aligns
    nothing again; a new reading of either side is a new key."""
    ours, theirs = load_clauses(db, paper.id), load_clauses(db, after.id)
    if not ours or not theirs:
        return {"at": {}, "state": [], "words": []}
    ours, theirs = reader_generation.as_one_reader(db, paper.id, after.id, ours, theirs)
    key = negotiation._core_key(db, paper, after, None, False, ours, theirs)
    return negotiation.process_memo(key, "prior", lambda: _aligned(ours, theirs))


def _state(row: dict, read: dict[str, Any]) -> str | None:
    after = row.get("after")
    if after:
        units = {read["at"][e] for e in after["evidence_ids"] if e in read["at"]}
        states = {read["state"][j] for j in units}
        return None if not states else states.pop() if len(states) == 1 else CHANGED
    before = row.get("before")
    if row["kind"] == "DELETED" and before and _words(before["text"]) in read["words"]:
        return IN_SIGNED
    return None


def label_rows(guard: Guard, contract: M.Contract, listed: dict) -> None:
    """R1.2: each change row's ``prior`` — the earlier contract whose state is SAME (or,
    for a deleted clause, IN_SIGNED), else the most recent one that pairs it; and the
    list's ``prior_papers``. Nothing is added when no earlier contract qualifies."""
    found = papers(guard, contract) if listed["changes"] else []
    if not found:
        return
    after = guard.db.get(M.DocumentVersion, UUID(listed["to"]["document_version_id"]))
    assert after is not None
    reads = [(p, _read(guard.db, p["version"], after)) for p in found]
    for row in listed["changes"]:
        got = [(p, s) for p, r in reads if (s := _state(row, r))]
        if got:
            p, s = next((g for g in got if g[1] in (SAME, IN_SIGNED)), got[0])
            row["prior"] = {"state": s, **public(p)}
    listed["prior_papers"] = [public(p) for p in found]


def already_agreed(listed: dict) -> dict[str, Any] | None:
    """R1.4: the brief's count of changes whose clause reads the same in an earlier
    signed or final contract, with the first such contract; None when there are none."""
    rows = [c for c in listed.get("changes", ()) if (c.get("prior") or {}).get("state")
            == SAME]
    if not rows:
        return None
    first = rows[0]["prior"]
    return {"count": len(rows), "rows": [c["row_key"] for c in rows],
            "contract": {k: v for k, v in first.items() if k != "state"}}


def _fact(row: dict) -> tuple[str, str]:
    return row["classification"], json.dumps(row["actual"], sort_keys=True, default=str)


def label_points(guard: Guard, review: M.Review, angles: dict) -> None:
    """R1.3: a point's ``prior`` where an earlier contract's agreed version has a latest
    Review holding a point on the same standard — SAME when its classification and the
    figure it read are equal, else CHANGED; nothing where none measured it (a Review on
    another snapshot may not have: absence is never "new")."""
    db = guard.db
    if not {P.FINDING_VIEW, P.REVIEW_VIEW} <= set(guard.permissions):
        return
    contract = db.get(M.Contract, review.contract_id)
    found = papers(guard, contract) if contract is not None else []
    earlier = [(p, {r["code"]: _fact(r) for r in point_rows(db, r)})
               for p in found if (r := negotiation._latest_review(db, p["version"]))]
    if not earlier:
        return
    mine = {r["code"]: _fact(r) for r in point_rows(db, review)}
    items = [*angles.get("business", ()), *(angles.get("legal") or {}).get("items", ())]
    for item in items:
        code = item["requirement_code"]
        got = [(p, SAME if facts[code] == mine.get(code) else CHANGED)
               for p, facts in earlier if code in facts]
        if got:
            p, s = next((g for g in got if g[1] == SAME), got[0])
            item["prior"] = {"state": s, **public(p)}
