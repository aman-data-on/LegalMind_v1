"""The Special Conditions annexure — accepted client changes, listed once, the template
body untouched (`AM-307`, design `11-ANNEXURE-SYSTEM-DESIGN.md`).

A template opts in with ``layout.special_conditions``::

    {"frame": {"clause_key", "version"}, "precedence": "<body clause key>",
     "position": "after_execution" | "before_execution", "pages": "continue",
     "initials": bool}        # both parties sign or initial the annexure

The FRAME is a clause version (pinned, approved like any clause, never rendered as
body) whose ``p`` blocks carry a ``role``: ``title``, ``opening`` (one or more),
``op.replace``, ``op.delete``, ``op.insert_after`` and ``op.add``. Its
slots are ``{sc:target}`` (a cross-reference to the varied clause), ``{sc:heading}``,
``{sc:new_number}``, ``{sc:agreement}``, ``{sc:date}`` and ``{sc:parties}`` beside the
template's own ``{variables}``. The
PRECEDENCE clause is a pinned body clause the lawyer approves. Neither is ever seeded
APPROVED (rules 7/21): `tools.import_template --special-conditions` loads the DRAFT
reference text labelled "For management approval".

`derive` turns the answered changes of one round into entries — one per varied clause,
``op`` replace | delete | insert_after and the agreed text verbatim (the client's,
our wording, or our standard) — or names why it cannot (fail closed, rule 15). No word
is composed here: an entry's text is the client's, the lawyer's or the clause library's,
and the lead sentence is the approved frame's (`AM-251` r1).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M

ROLES_REQUIRED = ("title", "opening", "op.replace", "op.delete", "op.insert_after")
OPS = {"replace": "op.replace", "delete": "op.delete", "insert_after": "op.insert_after",
       "add": "op.add"}
#: `{sc:target}` · `{sc:heading}` · `{sc:new_number}` · `{sc:agreement}` (its name) ·
#: `{sc:date}` (its effective date) · `{sc:parties}` (the parties' names)
SC_SLOT = re.compile(r"\{sc:(target|heading|new_number|agreement|date|parties)\}")
#: a quoted heading slot, dropped whole where the varied clause has no heading of its own
NO_HEADING = re.compile(r"\s*[“\"]\{sc:heading\}[”\"]")
FOR_APPROVAL = "For management approval"
POSITIONS = ("after_execution", "before_execution")
_LEADING_NUMBER = re.compile(r"^\W*\d+(?:\.\d+)*[A-Z]?\.?\s+")


def config(template: Any) -> dict[str, Any] | None:
    layout = (template.get("layout") if isinstance(template, dict)
              else template.layout) or {}
    return layout.get("special_conditions") or None


def text_sha256(text: str) -> str:
    """Spacing ignored, nothing else — the same rule as a carried decision's."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def roles(frame_body: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for b in frame_body or []:
        if b.get("kind") == "p" and b.get("role"):
            out.setdefault(b["role"], []).append(b.get("text", ""))
    return out


# ---------------------------------------------------------------- B1 readiness
def readiness(db: DBSession, tv: M.TemplateVersion) -> dict[str, Any]:
    """``{"ready", "missing": [{"code", "detail"}]}`` — whether this template version can
    carry a Special Conditions annexure: configured, its frame pinned, APPROVED and
    complete, its precedence clause a pinned body clause and APPROVED (`AM-307`, R-3).
    Whether the template is published is the package gate's own check."""
    cfg = config(tv)
    if cfg is None:
        return {"ready": False, "missing": [{"code": "NOT_CONFIGURED", "detail":
                "this template has no Special Conditions frame or precedence clause"}]}
    missing: list[dict[str, str]] = []

    def row(pin: Mapping[str, Any] | None) -> M.ClauseVersion | None:
        if not pin:
            return None
        return db.execute(select(M.ClauseVersion).where(
            M.ClauseVersion.clause_key == pin["clause_key"],
            M.ClauseVersion.version == pin["version"])).scalar_one_or_none()

    frame = row(cfg.get("frame"))
    if frame is None:
        missing.append({"code": "FRAME_MISSING", "detail": "no frame clause is pinned"})
    else:
        if frame.status != "APPROVED":
            missing.append({"code": "FRAME_NOT_APPROVED", "detail":
                            "the Special Conditions wording is not approved by Legal"})
        gaps = [r for r in ROLES_REQUIRED if r not in roles(frame.body)]
        if gaps:
            missing.append({"code": "FRAME_INCOMPLETE",
                            "detail": f"the frame has no {', '.join(gaps)} wording"})
    pin = next((p for p in tv.clauses if p["clause_key"] == cfg.get("precedence")), None)
    precedence = row(pin)
    if precedence is None:
        missing.append({"code": "PRECEDENCE_NOT_PINNED", "detail":
                        "no order-of-precedence clause in the body names the annexure"})
    elif precedence.status != "APPROVED":
        missing.append({"code": "PRECEDENCE_NOT_APPROVED", "detail":
                        "the order-of-precedence clause is not approved by Legal"})
    if cfg.get("position", "after_execution") not in POSITIONS:
        missing.append({"code": "POSITION", "detail": "position is not one of "
                        f"{', '.join(POSITIONS)}"})
    return {"ready": not missing, "missing": missing}


# ---------------------------------------------------------------- targets
def targets(model: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """The main body's clauses and sub-clauses by number: ``{key, number, heading,
    lead, nested, order}`` — ``key`` the clause or keyed sub-clause's own, else the
    synthetic ``<clause_key>~<number>``; ``lead`` the text its first row reads; ``nested``
    whether sub-clauses sit under it. Schedules are never a target."""
    from legalmind.drafting.model import text_of
    out: dict[str, dict[str, Any]] = {}

    def subs(blocks: list[dict], clause: Mapping[str, Any]) -> None:
        for b in blocks:
            if b["kind"] != "sub":
                continue
            out[b["number"]] = {
                "key": b.get("key") or f"{clause['clause_key']}~{b['number']}",
                "number": b["number"],
                # its own run-in title, or none — never its clause's heading
                "heading": (b.get("title") or "").rstrip(": \t") or None,
                "title": b.get("title"), "title_style": b.get("title_style"),
                "lead": (b.get("title") or "") + text_of(b["runs"]),
                "nested": any(x["kind"] == "sub" for x in b["body"]),
                "plain": _plain(b["body"]), "order": len(out)}
            subs(b["body"], clause)

    for c in model["body"]:
        out[c["number"]] = {"key": c["clause_key"], "number": c["number"],
                            "heading": c["title"], "lead": c["title"], "title": None,
                            "nested": any(b["kind"] == "sub" for b in c["body"]),
                            "plain": _plain(c["body"]), "order": len(out)}
        subs(c["body"], c)
    return out


def _plain(body: list[dict]) -> bool:
    """Only paragraphs under it — a list's lettering, a table or an image would not
    survive as the annexure's plain paragraphs."""
    return all(b["kind"] in ("p", "heading", "definition", "sub") for b in body)


# ---------------------------------------------------------------- B2 derive
def _norm(text: str) -> str:
    from legalmind.analysis import document_comparison as dc
    from legalmind.analysis.negotiation import _typography
    return _typography(dc._norm(text))


def _strip_number(texts: list[str], number: str | None) -> str:
    out = list(texts)
    if out and number:
        m = _LEADING_NUMBER.match(out[0])
        if m and m.group(0).strip().rstrip(".") == number:
            out[0] = out[0][m.end():]
    return "\n".join(t for t in out if t.strip())


def _insert_number(anchor: str, taken: set[str]) -> str:
    """17.2 → 17.2A, then 17.2B … (Q-5: the lawyer may rule another style)."""
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if anchor + letter not in taken:
            taken.add(anchor + letter)
            return anchor + letter
    raise ValueError("too many inserted clauses after one clause")


def derive(changes: list[dict], old: list[dict], new: list[dict],
           alignment: list[tuple[int | None, int | None, bool]],
           model: Mapping[str, Any], standard_text: Any) -> dict[str, Any]:
    """The answered changes of one round → ``{"entries", "blockers"}``.

    ``old``/``new`` are `negotiation._units` of our version and the client's,
    ``alignment`` their `negotiation._align`; ``model`` our version's base model (body =
    the template); ``standard_text(clause_version_id) -> str | None`` our standard's
    words. An entry: ``{target {key, number, heading}, op, text, new_number?, row_key,
    choice, effect}``; a blocker: ``{code, message, row_key}``. Keep ours, and an agreed
    text equal to the template's (spacing and typography aside), give no entry."""
    by_number = targets(model)
    ours_eid = {u["evidence_ids"][0]: i for i, u in enumerate(old) if u["evidence_ids"]}
    theirs_eid = {u["evidence_ids"][0]: j for j, u in enumerate(new) if u["evidence_ids"]}
    anchor_of: dict[int, int | None] = {}
    last: int | None = None
    for i, j, _ in alignment:
        if j is not None and i is None:
            anchor_of[j] = last
        if i is not None:
            last = i
    entries: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    inserted: set[str] = set(by_number)

    def block(change: dict, code: str, message: str) -> None:
        blockers.append({"code": code, "message": message, "row_key": change["row_key"]})

    for change in changes:
        answer = (change.get("answer") or {}).get("answer")
        if answer is None or answer == "keep_ours":
            continue                     # unanswered: the reply gate names it
        kind = change["kind"]
        _, _, ours_key, theirs_key = change["row_key"].split("|")
        if kind in ("MOVED", "NEW_ANNEXURE", "THEIRS"):
            block(change, "CANNOT_EXPRESS", "A moved clause or a new annexure cannot be "
                  "written as a Special Condition — keep ours, or reply with tracked "
                  "changes.")
            continue
        i = ours_eid.get(ours_key) if ours_key else None
        j = theirs_eid.get(theirs_key) if theirs_key else None
        if kind == "ADDED":
            assert j is not None
            a = anchor_of.get(j)
            unit = old[a] if a is not None else None
        else:
            unit = old[i] if i is not None else None
        target = by_number.get(unit["number"]) if unit and unit["number"] else None
        if unit is not None and (target is None or _norm(unit["texts"][0])
                                 != _norm(target["lead"])):
            target = None                # front matter, execution or a schedule
        if target is None:
            block(change, "CANNOT_EXPRESS", "This change is outside the numbered "
                  "clauses (front matter, the signature block or a schedule) — keep "
                  "ours, or reply with tracked changes.")
            continue
        if kind != "ADDED" and target["nested"]:
            block(change, "CANNOT_EXPRESS", f"Clause {target['number']} has sub-clauses "
                  "under it; replacing it in the annexure would read as replacing them "
                  "too — keep ours, or reply with tracked changes.")
            continue
        if kind == "MODIFIED" and not target["plain"]:
            block(change, "CANNOT_EXPRESS", f"Clause {target['number']} holds a list, a "
                  "table or an image, which the annexure cannot restate exactly — keep "
                  "ours, or reply with tracked changes.")
            continue
        if answer == "accept_theirs":
            if kind != "DELETED" and j is None:
                block(change, "CANNOT_EXPRESS", "The client's text could not be found.")
                continue
            text = None if j is None else _strip_number(new[j]["texts"],
                                                        new[j]["number"])
        elif answer == "write_wording":
            text = change["answer"].get("wording") or ""
        else:                                                    # use_standard
            text = standard_text(change["answer"].get("clause_version_id"))
            if text is None:
                block(change, "CANNOT_EXPRESS", "Our standard clause needs this "
                      "contract's own values — keep ours.")
                continue
        # a whole clause keeps its heading: the entry is what stands under it
        clause_level = target is not None and "." not in target["number"]
        if clause_level and text is not None and kind != "ADDED":
            first, _, rest = text.partition("\n")
            if _norm(first) == _norm(target["lead"]):
                text = rest
        template_text = "\n".join(unit["texts"][1 if clause_level else 0:]) \
            if unit and kind != "ADDED" else ""
        if text is not None and kind != "ADDED" and _norm(text) == _norm(template_text):
            continue                                       # agreed = template: none
        entry: dict[str, Any] = {
            "row_key": change["row_key"], "answer": answer,
            "effect": change.get("effect_for_us"), "text": text}
        if kind == "ADDED":
            if not (text or "").strip():
                continue
            entry.update(op="insert_after", target=_public(target),
                         new_number=_insert_number(target["number"], inserted),
                         order=(target["order"], 1))
        else:
            entry.update(op="delete" if text is None else "replace",
                         target=_public(target), order=(target["order"], 0))
        entries.append(entry)
    seen: set[tuple[str, str]] = set()
    for e in entries:
        if e["op"] in ("replace", "delete"):
            k = (e["op"], e["target"]["key"])
            if k in seen or ("replace", k[1]) in seen or ("delete", k[1]) in seen:
                blockers.append({"code": "CANNOT_EXPRESS", "row_key": e["row_key"],
                                 "message": f"Two answers vary clause "
                                            f"{e['target']['number']} — answer it once."})
            seen.add(k)
    entries.sort(key=lambda e: e.pop("order"))
    for n, e in enumerate(entries, 1):
        e["n"] = n
    return {"entries": entries, "blockers": blockers}


def _public(target: Mapping[str, Any]) -> dict[str, Any]:
    return {k: target[k] for k in ("key", "number", "heading")}


def entries_sha256(entries: list[dict], pins: Sequence[str] = ()) -> str:
    """What the dry run showed — the POST names it (409 STALE_PREVIEW otherwise): each
    entry, the answer and effect behind it, and the frame and precedence versions its
    words come from (L-5)."""
    import json
    return hashlib.sha256(json.dumps([
        list(pins),
        *([e["n"], e["op"], (e["target"] or {}).get("key"), e.get("new_number"),
           text_sha256(e["text"] or ""), e.get("answer"), e.get("effect")]
          for e in entries)]).encode()).hexdigest()


# ---------------------------------------------------------------- B3 model section
def section(r: Any, frame: Mapping[str, Any], cfg: Mapping[str, Any],
            entries: list[dict], layout: Mapping[str, Any], model: Mapping[str, Any]
            ) -> tuple[dict[str, Any], dict[str, str]]:
    """The client-facing section and its synthetic anchors (key → number) — built with
    the model's own resolver, so a ``{variable}`` in the frame reads its value. Entry
    text is never parsed for slots: it is put in verbatim, one paragraph per line."""
    from legalmind.drafting.model import role as var_role
    from legalmind.drafting.model import text_of
    said = roles(frame.get("body", []))
    where = f"{frame.get('clause_key')}@{frame.get('version')}"
    anchors: dict[str, str] = {}
    dated = next((k for k, v in r.vars.items() if var_role(v) == "effective_date"), None)
    agreement = {
        "agreement": layout.get("short_title") or layout.get("title"),
        "date": r.runs(f"{{{dated}}}", where) if dated else None,
        "parties": " and ".join(text_of(p["name"]) for p in model["parties"]) or None}
    named = targets(model)

    def runs(text: str, slots: Mapping[str, Any]) -> list[dict]:
        out: list[dict] = []
        pos = 0
        for m in SC_SLOT.finditer(text):
            if m.start() > pos:
                out += r.runs(text[pos:m.start()], where) or []
            value = slots.get(m.group(1))
            if value is None:
                r.problems.append({"field": where, "problem":
                                   f"{{sc:{m.group(1)}}} has nothing to say here"})
            elif isinstance(value, dict):
                out.append(value)
            elif isinstance(value, list):                     # a variable's own runs
                out += value
            else:
                out.append({"t": str(value)})
            pos = m.end()
        if pos < len(text):
            out += r.runs(text[pos:], where) or []
        from legalmind.drafting.model import _merge
        return _merge(out)

    out_entries = []
    for e in entries:
        role = OPS[e["op"]]
        if role not in said:
            r.problems.append({"field": where, "problem": f"has no {role} wording"})
            continue
        t = e.get("target") or {}
        if t and "~" in t["key"]:
            anchors[t["key"]] = t["number"]
        slots = {"target": {"ref": t["key"], "num": t["number"]} if t else None,
                 "heading": t.get("heading"), "new_number": e.get("new_number"),
                 **agreement}
        lead = said[OPS[e["op"]]][0]
        if not t.get("heading"):
            lead = NO_HEADING.sub("", lead)
        lines = [line for line in (e.get("text") or "").split("\n") if line.strip()]
        out_entries.append({
            "n": str(e["n"]), "op": e["op"], "target": t.get("key"),
            "lead": runs(lead, slots),
            "blocks": [_titled(line, named.get(t.get("number", ""))) if not i
                       else [{"t": line}] for i, line in enumerate(lines)]})
    title = said.get("title", [""])[0]
    return {
        "title": runs(title, agreement),
        "label": title,
        "opening": [runs(t, agreement) for t in said.get("opening", [])],
        "entries": out_entries,
        # R-5/R-6, Q-5: both parties sign or initial the annexure (a template setting)
        **({"signature": True} if cfg.get("initials") else {}),
        "position": cfg.get("position", "after_execution"),
        "precedence": cfg.get("precedence"),
        "anchors": dict(sorted(anchors.items())),
        "headings": sorted({(e.get("target") or {}).get("heading") for e in entries}
                           - {None}),
    }, anchors


def _titled(line: str, target: Mapping[str, Any] | None) -> list[dict]:
    """The first line of an entry: where it opens on the varied clause's run-in title,
    the title's words carry its mark (underlined, or bold) as in the body."""
    title = (target or {}).get("title")
    if not title or not line.startswith(title):
        return [{"t": line}]
    words = title.rstrip(": \t")
    mark = "b" if target.get("title_style") == "bold" else "u"   # type: ignore[union-attr]
    return [x for x in ({"t": words, mark: True}, {"t": line[len(words):]}) if x["t"]]


def walk_entries(model: Mapping[str, Any]) -> Iterator[dict]:
    yield from (model.get("special_conditions") or {}).get("entries", [])


def frame_row(db: DBSession, tv: M.TemplateVersion) -> M.ClauseVersion | None:
    pin = (config(tv) or {}).get("frame")
    return None if not pin else db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == pin["clause_key"],
        M.ClauseVersion.version == pin["version"])).scalar_one_or_none()
