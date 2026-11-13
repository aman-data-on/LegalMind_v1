"""The effective contract — the body as its Special Conditions vary it (`AM-307`).

A version that carries our Special Conditions annexure (our final contract, the client's
copy of it, its signed copy) is read as the contract it IS: each entry's text in place
of the clause it names, a deleted clause gone, an inserted clause after its anchor; the
annexure's own title, opening and lead sentences dropped. The evidence rows are the
file's own (rule 11) — an entry's row keeps its id, and only its section number and title
say which clause it is now.

FAIL CLOSED (rule 15): the reading is ``NOT_APPLIED`` — with its reason, never a guess —
when the annexure is missing or its lead sentences do not read as the approved frame's,
a named clause is not in the body or its heading differs, the precedence clause (or,
with ``precedence: "frame"``, the frame's precedence sentence after the opening) is
gone, or (on our own generated file) the entries differ from the record. A version with
no frame anywhere in its contract's chain reads ``NONE``: raw, exactly as before
(third-party paper and the golden corpus never come here).
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis.negotiation import (
    READ_ABSENT,
    READ_APPLIED,
    READ_NOT_APPLIED,
    READ_RAW,
)
from legalmind.db import models as M
from legalmind.drafting import model as model_
from legalmind.drafting import publish, special_conditions
from legalmind.mapping.engine import Clause
from legalmind.mapping.service import load_clauses
from legalmind.observability import log_event

NONE, APPLIED, NOT_APPLIED = READ_RAW, READ_APPLIED, READ_NOT_APPLIED
#: a later copy that holds no annexure at all (the client's own paper, a retyped copy, an
#: OCR'd scan): read raw, said so, and every change goes to a person — never a failure
ABSENT = READ_ABSENT
ABSENT_REASON = "Special Conditions not found in this copy"
_NUMBER = r"\d+(?:\.\d+)*[A-Z]?"
_SLOTS = {"target": f"(?P<target>{_NUMBER})",
          "new_number": f"(?P<new>{_NUMBER})"}
_LEAD_NUMBER = re.compile(r"^\s*\d+\.\s+")


def _flat(text: str) -> str:
    from legalmind.analysis.negotiation import _typography
    return " ".join(_typography(text).split())


def _pattern(text: str) -> re.Pattern[str]:
    """An approved frame sentence as a reading pattern: its words exact (spacing and
    typography aside), each ``{sc:…}`` slot what it stands for, a ``{variable}`` any
    text; a quoted heading optional (a sub-clause without a title of its own has none)."""
    def part(flat: str) -> str:
        parts, pos = [], 0
        for m in re.finditer(r"\{(sc:)?([A-Za-z_][\w .\-:]*)\}", flat):
            parts.append(re.escape(flat[pos:m.start()]))
            parts.append(_SLOTS.get(m.group(2), ".+?") if m.group(1) else ".+?")
            pos = m.end()
        parts.append(re.escape(flat[pos:]))
        return "".join(parts)
    pieces = re.split(r'\s*"\{sc:heading\}"', _flat(text))
    return re.compile('(?: "(?P<heading>.+?)")?'.join(part(x) for x in pieces))


def _frame_version(db: DBSession, version: M.DocumentVersion
                   ) -> tuple[M.DocumentVersion, bool] | None:
    """The final contract whose frame this version is read by, and whether it is the
    version itself: its own record (a package's, or an amendment's first version, a
    copy of the agreed final contract — `AM-309`), else the latest earlier one in the
    contract (a later package supersedes an earlier one, `AM-308`)."""
    if (version.doc_metadata or {}).get("special_conditions"):
        return version, True
    D = M.DocumentVersion
    earlier = db.execute(select(D).where(
        D.contract_id == version.contract_id, D.version_number < version.version_number,
        D.doc_metadata["special_conditions"].isnot(None))
        .order_by(D.version_number.desc()).limit(1)).scalar()
    return (earlier, False) if earlier is not None else None


def effective_clauses(db: DBSession,
                      version_id: UUID) -> tuple[list[Clause], str, str | None]:
    """``(clauses, status, reason)`` — status `NONE` (raw rows), `APPLIED`, `ABSENT`
    (a later copy without the annexure: raw rows) or `NOT_APPLIED` (raw rows, and
    ``reason`` says why the annexure was not applied). Never raises for the document's
    content: anything unexpected while reading it is NOT_APPLIED, for a person."""
    raw = load_clauses(db, version_id)
    version = db.get(M.DocumentVersion, version_id)
    found = _frame_version(db, version) if version is not None else None
    if found is None:
        return raw, NONE, None
    package, own = found
    try:
        return _apply(db, raw, package, own), APPLIED, None
    except _Absent:
        return raw, ABSENT, ABSENT_REASON
    except _NotApplied as exc:
        return raw, NOT_APPLIED, str(exc)
    except Exception as exc:    # fail closed to a person, never a 500
        log_event("analysis.special_conditions.unreadable", version_id=str(version_id),
                  error=type(exc).__name__)
        return raw, NOT_APPLIED, ("the Special Conditions could not be read "
                                  f"({type(exc).__name__})")


class _NotApplied(Exception):
    pass


class _Absent(Exception):
    pass


def _apply(db: DBSession, raw: list[Clause], package: M.DocumentVersion,
           own: bool) -> list[Clause]:
    draft = db.execute(select(M.ContractDraft).where(
        M.ContractDraft.document_version_id == package.id)).scalar_one_or_none()
    tv = db.get(M.TemplateVersion, draft.template_version_id) if draft else None
    recorded = ((package.doc_metadata or {}).get("special_conditions") or {})
    frame = special_conditions.frame_row(db, tv, recorded.get("frame")) \
        if tv is not None else None
    if draft is None or tv is None or frame is None:
        raise _NotApplied("the final contract's template or frame is not on record")
    rows = publish.pinned_clauses(db, tv)
    base = model_.resolve(publish.template_dict(tv),
                          {k: publish.clause_dict(c) for k, c in rows.items()},
                          draft.values)
    targets = special_conditions.targets(base)
    said = special_conditions.roles(frame.body)
    cfg = special_conditions.config(tv) or {}
    title = _pattern(said["title"][0])
    leads = {op: _pattern(said[role][0]) for op, role in special_conditions.OPS.items()
             if role in said}
    openings = [_pattern(t) for t in said.get("opening", [])]
    stops = [_pattern(s["title"]) for s in base["schedules"]]
    stops.append(_pattern(model_.text_of((base["execution"] or {}).get("lead"))
                          or "Execution"))
    at = next((i for i, c in enumerate(raw) if title.fullmatch(_flat(c.content or ""))),
              None)
    if at is None:
        if own:                       # our own final contract always carries them
            raise _NotApplied("the Special Conditions are not in this copy")
        raise _Absent()
    in_frame = cfg.get("precedence") == special_conditions.IN_FRAME
    precedence = [_pattern(t) for t in said.get("precedence", [])] if in_frame else []
    if in_frame:   # S3: Legal's sentence, between the opening and entry 1, exactly
        lines = []
        for c in raw[at + 1:]:
            text = _flat(_LEAD_NUMBER.sub("", c.content or ""))
            if any(p.fullmatch(text) for p in leads.values()):
                break
            lines.append(_flat(c.content or ""))
        if not precedence or not all(any(p.fullmatch(t) for t in lines)
                                     for p in precedence):
            raise _NotApplied("the frame's precedence sentence is absent or different")
    else:          # the precedence clause must still be in the body, word for word
        pin = next((c for c in base["body"] if c["clause_key"] == cfg.get("precedence")),
                   None)
        body_text = _flat(" ".join(c.content or "" for c in raw[:at]))
        if pin is None or not all(_flat(model_.text_of(b.get("runs"))) in body_text
                                  for b in pin["body"] if b.get("runs")):
            raise _NotApplied("the order-of-precedence clause is missing or changed")
    entries: list[dict[str, Any]] = []
    end = len(raw)
    for i in range(at + 1, len(raw)):
        text = _flat(_LEAD_NUMBER.sub("", raw[i].content or ""))
        if any(s.fullmatch(_flat(raw[i].content or "")) for s in stops) or (
                entries and (raw[i].content or "").startswith("|")):  # signature lines
            end = i
            break
        lead = next(((op, m) for op, p in leads.items() if (m := p.fullmatch(text))),
                    None)
        if lead is not None:
            op, m = lead
            entries.append({"op": op, "number": m.groupdict().get("target"),
                            "heading": m.groupdict().get("heading"),
                            "new": m.groupdict().get("new"), "rows": []})
        elif entries:
            entries[-1]["rows"].append(raw[i])
        elif not any(o.fullmatch(text) for o in [*openings, *precedence]):
            raise _NotApplied("the Special Conditions open with words that are not the "
                              "approved frame's")
    if not entries:
        raise _NotApplied("the Special Conditions list no entry")
    for e in entries:
        t = targets.get(e["number"] or "")
        if t is None or _flat(t["heading"] or "") != _flat(e["heading"] or ""):
            raise _NotApplied(f"a Special Condition names clause {e['number']}, which "
                              "the body does not hold under that heading")
        if t["nested"] and e["op"] != "insert_after":
            raise _NotApplied(f"a Special Condition varies clause {e['number']}, which "
                              "has sub-clauses under it")
        if (e["op"] == "delete") == bool(e["rows"]):
            raise _NotApplied(f"the Special Condition on clause {e['number']} has "
                              "text where none belongs, or none where it does")
    if own:
        recorded = ((package.doc_metadata or {}).get("special_conditions") or {}).get(
            "trace", [])
        got = [((targets[e["number"]]["key"]), e["op"],
                special_conditions.text_sha256("\n".join(r.content or ""
                                                         for r in e["rows"])))
               for e in entries]
        want = [(t["target_key"], t["op"], t["text_sha256"]) for t in recorded]
        if got != want:
            raise _NotApplied("the Special Conditions differ from the record of what "
                              "was prepared")
    body = raw[:at]
    halt = {i for i, c in enumerate(body)
            if any(s.fullmatch(_flat(c.content or "")) for s in stops)}
    while end < len(raw) and (raw[end].content or "").startswith("|"):
        end += 1                         # the annexure's own signature lines
    return _rewrite(body, entries, halt, targets) + raw[end:]


def _rewrite(body: list[Clause], entries: list[dict[str, Any]], halt: set[int],
             targets: dict[str, dict[str, Any]]) -> list[Clause]:
    """The body with each entry applied: a unit is its numbered row and the unnumbered
    rows under it (never the signature block or a schedule after it); the entry's rows
    take its number, the first row the target row's title and heading flag."""
    starts = {c.section_number: i for i, c in reversed(list(enumerate(body)))
              if c.section_number}
    spans: dict[str, tuple[int, int]] = {}
    for number, i in starts.items():
        j = i + 1
        while j < len(body) and not body[j].section_number and j not in halt:
            j += 1
        spans[number] = (i, j)
    # each entry's clause is the one the body holds at that number AND reads as the
    # template's: a renumbered body (a clause added or removed before it) never lends
    # its number to another clause (H-1)
    for e in entries:
        span = spans.get(e["number"])
        t = targets[e["number"]]
        if span is None or special_conditions._norm(body[span[0]].content or "") \
                != special_conditions._norm(t["lead"]):
            raise _NotApplied(f"clause {e['number']} of this copy is not the clause the "
                              "Special Condition names (the body was renumbered or "
                              "changed)")
    out = list(body)
    # from the end, so earlier spans keep their indices; on one clause the insertions
    # after it first — the last one first, so they read in order (M-1) — then the
    # change to it
    order = {id(e): n for n, e in enumerate(entries)}
    for e in sorted(entries, key=lambda e: (-spans[e["number"]][0],
                                            e["op"] != "insert_after", -order[id(e)])):
        i, j = spans[e["number"]]
        head = body[i]
        if e["op"] == "insert_after":
            first = {"section_number": e["new"], "section_title": None,
                     "is_heading": False}
        elif (e["op"] == "replace" and head.is_heading
              and _flat(head.content or "") == _flat(e["heading"] or "")):
            i += 1                     # a whole clause keeps its heading row
            first = {"section_number": None, "section_title": None, "is_heading": False}
        else:
            first = {"section_number": e["number"], "section_title": head.section_title,
                     "is_heading": head.is_heading}
        made = [replace(r, **first) if not k
                else replace(r, section_number=None, is_heading=False)
                for k, r in enumerate(e["rows"])]
        if e["op"] == "insert_after":
            out[j:j] = made
        else:
            out[i:j] = made
    return out
