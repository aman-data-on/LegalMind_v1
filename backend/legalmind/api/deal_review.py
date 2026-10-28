"""A client's documents reviewed side by side — `AM-229` (owner, 2026-10-28: "first legal
assistant ko pata hona chahiye na dono ek sath … give me into the side by side review so
it easy to review and into easy language").

Each chat file is reviewed on its own by the Dashboard's engine (`temporary_review`); this
lines the reviews up, one row per topic (Requirement) across the files, and states each
row's status from two things only: the engine's own action for each file's point
(`angles`, the Constitution's §24/§25 words) and what the READER said — which file is
signed and which one wins where they differ. The documents' own precedence clauses are
shown, never applied (locked F-6; owner, 2026-10-28: "always ask me"). Nothing here
decides a legal question: no rule, threshold or reading is added (rule 7).

Lives in the API layer because it reads the evaluator's output (`AM-25` r1).
"""

from __future__ import annotations

from typing import Any

from legalmind.api import angles as A
from legalmind.api.temporary_review import TemporaryReview

#: a row's status, worst first — the reader's words come from the frontend
MUST_CHANGE = "MUST_CHANGE"  # 🔴 the engine: must change before signing (§25.1)
ASK_CHANGE = "ASK_CHANGE"  # 🟠 differs, or missing: send our wording / Legal decides
LEGAL_DECIDES = "LEGAL_DECIDES"  # ⚖ a person reads it: conflict, unclear, no boundary
AGREED = "AGREED"  # 🔒 the signed document that wins states it
FINE = "FINE"  # 🟢 matches our position
_WORST = (MUST_CHANGE, ASK_CHANGE, LEGAL_DECIDES, AGREED, FINE)

_DECIDE = {A.READ_IT, A.CONFLICT_DECIDE, A.UNDEFINED}


def cell_status(classification: str, action: str | None) -> str:
    """One file's point, in the engine's own terms — never re-judged here."""
    if action == A.MUST_CHANGE:
        return MUST_CHANGE
    if action in _DECIDE or classification in ("CONFLICT", "UNABLE_TO_EVALUATE"):
        return LEGAL_DECIDES
    if action in (A.SEND_WORDING, A.NO_WORDING) or classification in (
        "DEVIATION",
        "MISSING",
    ):
        return ASK_CHANGE
    return FINE  # MATCH, or in our favour (A.FAVOURABLE)


def _worst(statuses: list[str]) -> str:
    return min(statuses, key=_WORST.index) if statuses else LEGAL_DECIDES


def _changed_clauses(angles: dict[str, Any]) -> set[str]:
    changes = angles.get("client_changes") or {}
    return {
        c["clause"]
        for s in changes.get("sections", [])
        for c in s["changes"]
        if c.get("clause")
    }


def build(
    reviews: list[TemporaryReview], *, signed: set[str], wins: str | None
) -> dict[str, Any]:
    """The side-by-side review. ``signed``: the attachment ids the reader said are signed;
    ``wins``: the attachment id the reader said prevails where the files differ, or None
    (not said — every difference is a person's decision)."""
    files: list[dict[str, Any]] = []
    rows_by_code: dict[str, dict[str, Any]] = {}
    for rv in reviews:
        fid, angles = str(rv.attachment_id), rv.angles or {}
        items = {i["finding_id"]: i for i in (angles.get("legal") or {}).get("items", [])}
        proposals = angles.get("counter_proposals") or {}
        changed = _changed_clauses(angles)
        changes = angles.get("client_changes") or {}
        files.append(
            {
                "id": fid,
                "name": rv.filename,
                "refused": rv.refused,
                "signed": fid in signed,
                "wins": fid == wins,
                "changes": changes.get("changes", 0),
                "notes": changes.get("notes", []),
                "precedence": [
                    o["text"]
                    for o in (angles.get("observations") or {}).get("structural", [])
                    if o.get("kind") == "PRECEDENCE"
                ],
                # a client's change no standard measured: shown to be read, never judged
                "unchecked": [
                    {"section": s["section"], "title": s["title"], **c}
                    for s in changes.get("sections", [])
                    for c in s["changes"]
                    if not c.get("measured_by")
                ],
            }
        )
        for f in rv.findings:
            req, item = f["requirement"], items.get(f["id"])
            # the clause row, never its heading ("16 INDEMNIFICATION" led the real MSA's
            # evidence): the first row long enough to be a clause, else the first
            rows = f.get("evidence") or [{}]
            lead_row = next(
                (e for e in rows if len((e.get("content") or "").strip()) >= 40), rows[0])
            evidence = [lead_row]
            clause = lead_row.get("section_number")
            constitution = req.get("constitution") or {}
            row = rows_by_code.setdefault(
                req["code"],
                {
                    # the Constitution's own topic name; the standard's sentence below
                    "code": req["code"],
                    "topic": constitution.get("topic") or req.get("description"),
                    "detail": req.get("description"),
                    "rule": {
                        k: v
                        for k, v in (req.get("constitution") or {}).items()
                        if k != "basis"
                    },
                    "cells": {},
                },
            )
            expected = next(
                (
                    e["expected_value"]
                    for e in f.get("evaluations", [])
                    if "expected_value" in e
                ),
                None,
            )
            if expected is not None:  # omitted without legal_position (SEC-07)
                row["rule"]["value"] = expected
            action = item["action"] if item else None
            row["cells"][fid] = {
                "finding_id": f["id"],
                "classification": f["classification"],
                "status": cell_status(f["classification"], action),
                "action": action,
                "quote": (evidence[0].get("content") or "")[:400],
                "clause": clause,
                "page": evidence[0].get("page_number"),
                "changed": bool(clause) and clause in changed,
                "actual": next(
                    (e.get("actual_value") for e in f.get("evaluations", [])), None
                ),
                **({"proposal": proposals[f["id"]]} if f["id"] in proposals else {}),
            }
    rows = [_decide(row, signed=signed, wins=wins) for row in rows_by_code.values()]
    for r in rows:
        # what the row asks of the reader: its own status or a worse one another file has
        r["needs"] = _worst([r["status"], *[x["status"] for x in r["also"]]])
    rows.sort(key=lambda r: (_WORST.index(r["needs"]), r["topic"] or ""))
    return {
        "files": files,
        "rows": rows,
        "wins": wins,
        "counts": {s: sum(r["needs"] == s for r in rows) for s in _WORST},
    }


def _decide(row: dict[str, Any], *, signed: set[str], wins: str | None) -> dict[str, Any]:
    """A row's status and the file it rests on.

    Where the reader named a winning file and it states the point, the row rests on it —
    AGREED when that file is signed and departs from our position (it is already agreed),
    LEGAL_DECIDES when the engine could not read it. Every OTHER file that says something
    worse stays on the row (``also``): "prevails in a conflict" cannot tell a conflict
    from an addition, so an MSA term going beyond the MOU is never hidden by the MOU.
    With no winner named, files that differ are a person's decision; else the worst
    point leads.
    """
    cells = row["cells"]
    stated = {fid: c for fid, c in cells.items() if c["classification"] != "MISSING"}

    def also(lead: str | None) -> list[dict[str, Any]]:
        """Another file's worse point — except where it says what the leading file says
        (it agrees with what is agreed) or says nothing (silence contradicts nothing)."""
        said = cells[lead]["actual"] if lead in cells else None
        return [
            {"file": fid, "status": c["status"], "action": c["action"]}
            for fid, c in cells.items()
            if fid != lead
            and c["status"] in (MUST_CHANGE, ASK_CHANGE, LEGAL_DECIDES)
            and not (lead in stated and (c["classification"] == "MISSING"
                                         or (said is not None and c["actual"] == said)))
        ]

    if wins in stated:
        status = stated[wins]["status"]
        if wins in signed and status in (MUST_CHANGE, ASK_CHANGE):
            status = AGREED
        return {**row, "status": status, "decided_by": wins, "also": also(wins)}
    if (
        wins is None
        and len(stated) > 1
        and len({c["status"] for c in stated.values()}) > 1
    ):
        return {
            **row,
            "status": LEGAL_DECIDES,
            "decided_by": None,
            "also": [],
            "note": "files_differ",
        }
    lead = min(cells, key=lambda fid: _WORST.index(cells[fid]["status"]))
    return {
        **row,
        "status": cells[lead]["status"],
        "decided_by": lead,
        "also": also(lead),
    }


#: the reply carrying the assistant's questions (the questions themselves are the payload)
QUESTIONS_TEXT = (
    "Before I review these documents side by side, a few questions only you "
    "can answer. Each one changes the advice; skip any and I will say what I "
    "assumed."
)


def summary(review: dict[str, Any]) -> str:
    """The reply above the table, in fixed words from the counts — the plain-language
    summary the model writes is added beside it (`AM-232`), never in its place."""
    c = review["counts"]
    names = " and ".join(f["name"] for f in review["files"])
    parts = [
        f"{c[MUST_CHANGE]} must change",
        f"{c[ASK_CHANGE]} to ask for a change",
        f"{c[LEGAL_DECIDES]} for Legal to decide",
        f"{c[AGREED]} already agreed",
        f"{c[FINE]} fine",
    ]
    return (
        f"I reviewed {names} side by side against our positions, point by point: "
        + ", ".join(parts)
        + ". The status of every point comes from the contract "
        "review, not from me."
    )
