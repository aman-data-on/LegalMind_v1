"""What a contract lawyer reads off a client's markup before answering it — computed,
never decided (owner, 2026-11-16; design `LAWYER-AGENT-R2` slices S1–S3, step 0).

* **Origin** (step 0): is a point the client's change, or already in our own paper? A
  point that fires on our unchanged text is not something the client asked for.
* **Lettered points** (D1): one changed clause as the lawyer splits it, (a), (b), (c)…,
  each with who it binds and who it benefits (D6), and the standard it touches (D2).
* **Notes for Legal** (D4/D5): the same figure stated two ways, a reference to a clause
  the client deleted, a defined term whose definition was deleted, a duplicated sentence.

Every output is its own display field. None is a Finding, Classification, Rule Outcome,
Mapping State or Legal Decision (rules 10/13, `AM-29`), and none is ever applied: a person
reads it and decides. Pure functions over clauses the review already read; no model.
"""
from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from typing import Any

from legalmind.analysis import change_triage as T
from legalmind.analysis import negotiation as N
from legalmind.mapping.engine import Clause

CLIENT_CHANGED, ALREADY_OURS = "CLIENT_CHANGED", "ALREADY_OURS"
LEGAL_DECIDES = "LEGAL_DECIDES"
OURS, THEIRS, BOTH = "LEAPSWITCH", "CLIENT", "BOTH"
MADE_MUTUAL, ONTO_US, ONTO_THEM, MIXED = ("MADE_MUTUAL", "ONE_SIDED_ONTO_LEAPSWITCH",
                                          "ONE_SIDED_ONTO_CLIENT", "MIXED")


# ------------------------------------------------------------------ step 0: origin
def changed_evidence(ours: list[Clause] | None, theirs: list[Clause]) -> set[str] | None:
    """The client's rows that differ from what we sent: by version diff against our
    version when there is one, else by the redline's own tracked changes. None when
    neither can tell (a clean paper with no version of ours): nothing is labelled."""
    if ours:
        old, new = N._units(ours), N._units(theirs)
        out: set[str] = set()
        for i, j, moved in N._align(old, new):
            if j is None:
                continue
            o = old[i] if i is not None else None
            if N._kind(o, new[j], moved) not in (None, "MOVED"):
                out.update(new[j]["evidence_ids"])
        return out
    if any((c.marks or {}).get("changes") for c in theirs):
        return {str(c.evidence_id) for c in theirs if (c.marks or {}).get("changes")}
    return None


def origin(evidence_ids: Iterable[str], code: str, classification: str,
           changed: set[str] | None, ours_result: dict[str, str] | None) -> str | None:
    """`CLIENT_CHANGED` when the point reads a row the client changed, or our own version
    gave a different result; `ALREADY_OURS` when it reads only rows we sent unchanged and
    our version gave the same result (or, with no review of ours, it reads unchanged rows
    at all); None when nothing can tell — never guessed (rule 15)."""
    if changed is None:
        return None
    ids = set(evidence_ids)
    if ids & changed:
        return CLIENT_CHANGED
    if ours_result is not None:
        return ALREADY_OURS if ours_result.get(code) == classification else CLIENT_CHANGED
    return ALREADY_OURS if ids else None


# ------------------------------------------------------------------ D1 / D2 / D6
_PARTY = {"OUR": OURS, "THEIR": THEIRS}


def _bound_benefits(who: str | None) -> tuple[str | None, str | None]:
    """Whom a sentence binds and whom it benefits, from `change_triage._who`'s reading."""
    if who is None:
        return None, None
    if who == "MUTUAL":
        return BOTH, BOTH
    side, what = who.split("_", 1)
    me, other = _PARTY[side], _PARTY["THEIR" if side == "OUR" else "OUR"]
    return (me, other) if what == "DUTY" else (other, me)


def _flat(text: str | None) -> list[str]:
    return T._sentences(" ".join((text or "").split()))


def _letter(n: int) -> str:
    return chr(ord("a") + n) if n < 26 else f"a{n - 25}"


def points(before: str | None, after: str | None, vendor: bool = False,
           aliases: tuple[list[str], list[str]] = ([], [])) -> list[dict[str, Any]]:
    """One changed clause as lettered points, in the document's order: each sentence the
    client rewrote, added or removed, with whom it binds and benefits."""
    # a PDF breaks a sentence at each printed line: read it whole, so a line reflowed by
    # the client's edit is not a change of its own
    old, new = _flat(before), _flat(after)
    out: list[dict[str, Any]] = []

    def add(kind: str, was: str | None, now: str | None) -> None:
        bound, benefits = _bound_benefits(T._who(now or was or "", vendor, aliases))
        out.append({"letter": _letter(len(out)), "kind": kind, "before": was,
                    "after": now, "bound": bound, "benefits": benefits})
    matcher = difflib.SequenceMatcher(None, [T._key(s) for s in old],
                                      [T._key(s) for s in new], autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        pairs = min(i2 - i1, j2 - j1)
        for k in range(pairs):
            add("CHANGED", old[i1 + k], new[j1 + k])
        for s in new[j1 + pairs:j2]:
            add("ADDED", None, s)
        for s in old[i1 + pairs:i2]:
            add("REMOVED", s, None)
    return out


def mutuality(before: str | None, lettered: list[dict[str, Any]],
              vendor: bool = False,
              aliases: tuple[list[str], list[str]] = ([], [])) -> str | None:
    """The clause as changed: made mutual, one-sided onto LeapSwitch or onto the client,
    mixed, or None when no changed sentence names who acts."""
    was_mutual = any(T._who(s, vendor, aliases) == "MUTUAL" for s in _flat(before))
    now = {p["bound"] for p in lettered if p["after"] and p["bound"]}
    if not now:
        return None
    if now == {BOTH}:
        return None if was_mutual else MADE_MUTUAL
    if now <= {OURS, BOTH}:
        return ONTO_US
    if now <= {THEIRS, BOTH}:
        return ONTO_THEM
    return MIXED


def standards(row: dict[str, Any]) -> dict[str, Any]:
    """D2: the standards a change touches — the review's findings on the clause first,
    else the Constitution topic its heading names, else none: Legal decides. Never a
    model's guess alone."""
    codes = sorted({f["requirement_code"] for side in ("before", "after")
                    for f in (row.get("review") or {}).get(side, ())})
    if codes:
        return {"source": "FINDING", "codes": codes}
    topics = [{"section": t["section"], "title": t["title"]}
              for t in (row.get("triage") or {}).get("topics", ())]
    if topics:
        return {"source": "HEADING_TOPIC", "topics": topics}
    return {"source": LEGAL_DECIDES}


def lawyer_view(row: dict[str, Any], vendor: bool = False,
                aliases: tuple[list[str], list[str]] = ([], [])) -> dict[str, Any]:
    before = (row.get("before") or {}).get("text")
    after = (row.get("after") or {}).get("text")
    lettered = points(before, after, vendor, aliases) if row["kind"] != "MOVED" else []
    return {"points": lettered, "standards": standards(row),
            "mutuality": mutuality(before, lettered, vendor, aliases)}


# ------------------------------------------------------------------ D4 / D5
#: the concepts whose figure a lawyer aligns across clauses (fixed list, engineering)
_CONCEPTS = {"dispute window": re.compile(r"\bdisput", re.I),
             "cure period": re.compile(r"\bcure\b|\bremed(?:y|ied|ies)\b", re.I)}
_DAYS = re.compile(r"\b(\d{1,3})\s*(?:\(\w+\)\s*)?(working|business|calendar)?\s*days?\b",
                   re.I)
_XREF = re.compile(r"\b(?:Clauses?|Sections?)\s+(\d{1,2}(?:\.\d{1,2}){0,3})\b")
_DEFINED = re.compile(r"[“\"]([A-Z][\w\- ]{1,40}?)[”\"]\s*(?:shall\s+)?"
                      r"(?:means?|have the meaning|refers? to)")
_WORD = re.compile(r"[a-z0-9]{3,}")
#: a duplicated sentence: share of words in common (Jaccard), engineering threshold
DUPLICATE_OVERLAP = 0.8
_DUP_MIN_WORDS = 8


def _num(n: str | None) -> str:
    return N._num(n)


def _note(kind: str, clauses: list[str], text: str) -> dict[str, Any]:
    return {"kind": kind, "clauses": clauses, "text": text}


def notes_for_legal(ours: list[Clause], theirs: list[Clause]) -> list[dict[str, Any]]:
    """What a lawyer checks across the clauses after a markup — each note cites its
    clauses; a person reads it. A figure or duplicate note starts from a clause the
    client changed; a reference or term note from any clause naming what was deleted."""
    old, new = N._units(ours), N._units(theirs)
    changed: list[dict] = []
    deleted: set[str] = set()       # by alignment, never by number: renumbering moves
    for i, j, moved in N._align(old, new):
        if j is None and i is not None and old[i]["number"]:
            deleted.add(_num(old[i]["number"]))
        elif j is not None and N._kind(old[i] if i is not None else None, new[j],
                                       moved) not in (None, "MOVED"):
            changed.append(new[j])
    numbered = [u for u in new if u["number"]]
    deleted -= {_num(u["number"]) for u in numbered}   # its number still names a clause
    notes: list[dict[str, Any]] = []

    # (i) one concept, two figures
    def figures(unit: dict) -> dict[str, set[str]]:
        found: dict[str, set[str]] = {}
        for s in _flat(unit["text"]):
            for concept, rx in _CONCEPTS.items():
                if rx.search(s):
                    for m in _DAYS.finditer(s):
                        unit_word = (m.group(2) or "").lower()
                        found.setdefault(concept, set()).add(
                            f"{m.group(1)} {unit_word + ' ' if unit_word else ''}days")
        return found
    seen: set[tuple] = set()
    for unit in changed:
        if not unit["number"]:
            continue
        for concept, mine in figures(unit).items():
            for other in numbered:
                if other is unit or _num(other["number"]) == _num(unit["number"]):
                    continue
                theirs_f = figures(other).get(concept, set())
                if theirs_f and not (theirs_f & mine):
                    key = (concept, *sorted((_num(unit["number"]),
                                             _num(other["number"]))))
                    if key in seen:
                        continue
                    seen.add(key)
                    notes.append(_note(
                        "FIGURE_DIFFERS", [unit["number"], other["number"]],
                        f"The {concept} reads {', '.join(sorted(mine))} in clause "
                        f"{unit['number']} but {', '.join(sorted(theirs_f))} in clause "
                        f"{other['number']}."))
    # (ii) a reference to a clause the client deleted
    cited: set[tuple[str, str]] = set()
    for unit in new:
        for m in _XREF.finditer(" ".join(unit["text"].split())):
            target = _num(m.group(1))
            if target in deleted and (unit["number"] or "", target) not in cited:
                cited.add((unit["number"] or "", target))
                notes.append(_note(
                    "REFERS_TO_DELETED", [unit["number"] or "", m.group(1)],
                    f"Clause {unit['number'] or '(unnumbered)'} still refers to clause "
                    f"{m.group(1)}, which the client deleted."))
    # (iii) a defined term used after its definition was deleted
    def defined(units: list[dict]) -> set[str]:
        return {m.group(1).strip() for u in units
                for m in _DEFINED.finditer(" ".join(u["text"].split()))}
    gone = defined(old) - defined(new)
    for term in sorted(gone):
        users = [u["number"] for u in new if u["number"]
                 and re.search(rf"\b{re.escape(term)}\b", " ".join(u["text"].split()))]
        if users:
            notes.append(_note(
                "DEFINITION_DELETED", users[:5],
                f"“{term}” is still used in clause"
                f"{'s' * (len(users) > 1)} {', '.join(users[:5])}, but the client "
                "deleted its definition."))
    # D5: a changed sentence that repeats another clause
    def words(s: str) -> set[str]:
        return set(_WORD.findall(s.lower()))
    others = [(u["number"], words(s)) for u in numbered for s in _flat(u["text"])]
    flagged: set[tuple] = set()
    for unit in changed:
        for s in _flat(unit["text"]):
            mine = words(s)
            if len(mine) < _DUP_MIN_WORDS:
                continue
            for number, theirs_w in others:
                if not number or _num(number) == _num(unit["number"]):
                    continue
                if len(mine & theirs_w) / len(mine | theirs_w) >= DUPLICATE_OVERLAP:
                    key = tuple(sorted((_num(unit["number"]), _num(number))))
                    if key not in flagged:
                        flagged.add(key)
                        notes.append(_note(
                            "DUPLICATE", [unit["number"] or "", number],
                            f"Clause {unit['number'] or '(unnumbered)'} repeats what "
                            f"clause {number} already says."))
    return notes
