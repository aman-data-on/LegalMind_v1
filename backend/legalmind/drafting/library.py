"""A lawyer approves a template clause by clause (`AM-282`, `AM-283`).

Reference text is imported as DRAFT (`tools/import_template.py`) and is labelled
"Reference text — not approved by Legal" until a holder of
``legal.approve_customization`` acts on each pinned clause:

* **approve** — the text as it stands;
* **replace** — the lawyer's own wording, word for word, read into the importer's block
  tree by its markers (`parse_wording`); the text as typed is kept in ``source.text``;
* **no position** — the clause states no company position; its text is kept.

Every action writes a NEW ``clause_versions`` row, APPROVED on insert — an approved row
is frozen by trigger, so nothing is ever edited — whose ``source`` is the recorded
lawyer source of `AM-282` r1: supplier ``lawyer:<user id>``, approval reference = the
audit event's id, SHA-256 = the approved content hash. The DRAFT template is re-pinned
to that row; the template itself leaves DRAFT only when it is published
(`drafting.publish`), because an APPROVED template is frozen too.
"""

from __future__ import annotations

import re
import string
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.drafting import model, special_conditions
from legalmind.drafting.model import SLOT, clause_hash, content_hash
from legalmind.drafting.publish import pin_list, pinned_clauses
from legalmind.security import audit as A

DRAFT_LABEL = "Reference text — not approved by Legal"
SUGGESTED_LABEL = "Suggested — not approved"      # a DRAFT pre-filled from our standard


def label(row: Any) -> str | None:
    """What a clause reads as until it is approved (None once it is)."""
    if row.status == "APPROVED":
        return None
    kind = (row.source or {}).get("kind")
    if kind == "model":                 # `AM-307`: reference text for management
        return f"{special_conditions.FOR_APPROVAL} — {DRAFT_LABEL}"
    return SUGGESTED_LABEL if kind == "prefill" else DRAFT_LABEL
TEMPLATE_FIELDS = ("doc_type", "brand", "layout", "clauses", "variables", "annexures",
                   "assets", "source")
DECISIONS = {"APPROVE": "template.clause_approved", "REPLACE": "template.clause_replaced",
             "NO_POSITION": "template.clause_no_position"}


class LibraryRefused(ValueError):
    """A clause action that cannot be taken — the reason is the message."""


pins = pin_list          # main body, each annexure, then the Special Conditions frame


def texts(node: Any) -> Iterator[str]:
    """Every string of a JSON tree."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list | dict):
        for x in node.values() if isinstance(node, dict) else node:
            yield from texts(x)


def slots(node: Any) -> list[str]:
    """The ``{variable}`` slots a clause body uses."""
    return sorted({m.group(2) for t in texts(node) for m in SLOT.finditer(t)
                   if m.group(1) is None})


def template_hash(template: dict[str, Any], clauses: dict[tuple[str, int], dict]) -> str:
    return content_hash({
        **{k: template.get(k) for k in ("template_key", "version", *TEMPLATE_FIELDS)},
        "pins": [clauses[(p["clause_key"], p["version"])]["content_hash"]
                 for p in pins(template) if (p["clause_key"], p["version"]) in clauses]})


def progress(db: DBSession, tv: M.TemplateVersion) -> tuple[int, int]:
    rows = pinned_clauses(db, tv)
    every = pins(tv)
    done = sum(1 for p in every if (r := rows.get((p["clause_key"], p["version"])))
               and r.status == "APPROVED")
    return done, len(every)


def _rehash(db: DBSession, tv: M.TemplateVersion) -> None:
    rows = pinned_clauses(db, tv)
    tv.content_hash = template_hash(
        {"template_key": tv.template_key, "version": tv.version,
         **{k: getattr(tv, k) for k in TEMPLATE_FIELDS}},
        {k: {"content_hash": r.content_hash} for k, r in rows.items()})


# ------------------------------------------------- the lawyer's wording → blocks
_NUMBERED = re.compile(r"(\d+(?:\.\d+)+)\.?\s+(\S.*)")      # 4.1 · 4.1.2. · …
_ITEM = re.compile(r"\(?([a-z]{1,5})\)\s+(\S.*)")           # (a) · b) · (iv)
_OPENS_ON_TERM = re.compile(r"[“\"]([^”\"]+)[”\"]\s+(\S.*)")
_IMAGE = re.compile(r"\[Image: (.*)\]")
_LABEL = re.compile(r"\[([^\[\]{}]+)\]")
_ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",
          "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"]


def _letter(i: int) -> str:
    """Word's lowerLetter: a … z, aa … zz."""
    return string.ascii_lowercase[i % 26] * (i // 26 + 1)


def _subs(body: list[dict], path: tuple[int, ...] = ()) -> Iterator[tuple[tuple, dict]]:
    n = 0
    for b in body:
        if b.get("kind") == "sub":
            n += 1
            yield (*path, n), b
            yield from _subs(b.get("body", []), (*path, n))


def _blocks(body: list[dict]) -> Iterator[dict]:
    for b in body:
        yield b
        yield from _blocks(b.get("body", []))


def outline(body: list[dict], number: str) -> list[dict[str, Any]]:
    """The clause line by line as the renderer will number it — ``number`` is the clause's
    own (`number_of`): ``{"number": "4.1" | "(a)" | None, "level", "kind", "text"}``."""
    out: list[dict[str, Any]] = []

    def walk(blocks: list[dict], prefix: str, level: int) -> None:
        sub = 0
        for b in blocks:
            kind = b.get("kind")
            line = {"number": None, "level": level, "kind": kind}
            if kind == "sub":
                sub += 1
                out.append(line | {"number": f"{prefix}.{sub}", "level": level + 1,
                                   "text": b.get("title", "") + b.get("text", "")})
                walk(b.get("body", []), f"{prefix}.{sub}", level + 1)
            elif kind == "list":
                out.extend(line | {"number": f"({_letter(i)})", "text": t}
                           for i, t in enumerate(b["items"]))
            elif kind == "definition":
                out.append(line | {"text": f"“{b['term']}” {b['text']}"})
            elif kind == "table":
                out.extend(line | {"text": "| " + " | ".join(r) + " |"}
                           for r in [b["header"], *b.get("rows", [])])
            elif kind == "image":
                out.append(line | {"text": f"[Image: {b.get('alt', '')}]"})
            else:
                out.append(line | {"text": b.get("text", "")})

    walk(body, number, 1)
    return out


def wording(body: list[dict], number: str) -> str:
    """The clause as a lawyer types it — numbers and list markers included — which
    `parse_wording` reads back into the same blocks."""
    return "\n\n".join(f"{x['number']} {x['text']}" if x["number"] else x["text"]
                       for x in outline(body, number))


def number_of(tv: Any, clause_key: str) -> str:
    """The clause's number in its part (main body or annexure), every clause included."""
    for group in [tv.clauses, *(a.get("clauses", []) for a in tv.annexures)]:
        for i, p in enumerate(group, 1):
            if p["clause_key"] == clause_key:
                return str(i)
    return "1"


def _words(text: str) -> list[str]:
    return text.translate(str.maketrans("“”\u2018\u2019|", "\"\"'' ")).split()


def parse_wording(text: str, old_body: list[dict]) -> list[dict[str, Any]]:
    """The lawyer's wording → the block tree the importer builds. Markers become
    structure: ``4.1`` / ``4.1.2`` nest as sub-clauses (a skipped level nests under the
    one above, as the importer does), ``(a)`` / ``(i)`` runs are a list, a line opening
    on a quoted term is a definition, ``|`` rows a table; every other line a paragraph.
    What the clause had is kept where the lawyer kept it: a ``[Field name]`` chip of one
    of its fields is that ``{field}`` slot again, a keyed sub-clause keeps its key at the
    same number (so a cross-reference to it still resolves), a heading line stays a
    heading, an ``[Image: alt]`` line its image and a table its column widths. No word
    is added or dropped — the blocks read back, markers aside, as the wording typed, or
    the wording is refused."""
    labels = {" ".join(k.replace("_", " ").lower().split()): k for k in slots(old_body)}
    keys = {path: b["key"] for path, b in _subs(old_body) if b.get("key")}
    titles = {path: b for path, b in _subs(old_body) if b.get("title")}
    headings = {b["text"] for b in _blocks(old_body) if b.get("kind") == "heading"}
    images = {b.get("alt", ""): b for b in _blocks(old_body) if b.get("kind") == "image"}
    widths = [b.get("widths") for b in _blocks(old_body) if b.get("kind") == "table"]

    def chip(m: re.Match[str]) -> str:
        key = labels.get(" ".join(m.group(1).replace("_", " ").lower().split()))
        return f"{{{key}}}" if key else m.group(0)

    body: list[dict[str, Any]] = []
    stack: list[tuple[list[dict], tuple[int, ...]]] = [(body, ())]
    typed: list[str] = []
    items: dict[str, Any] | None = None           # the list now running: block, scheme
    rows: list[list[str]] = []

    def put(block: dict[str, Any]) -> None:
        stack[-1][0].append(block)

    def end_table() -> None:
        if rows:
            if len({len(r) for r in rows}) != 1:
                raise LibraryRefused("a table row has the wrong cell count")
            table = {"kind": "table", "header": rows[0], "rows": rows[1:]}
            if widths and (w := widths.pop(0)) and len(w) == len(rows[0]):
                table["widths"] = w                     # the column widths it had
            put(table)
            rows.clear()

    for raw in text.replace("\r\n", "\n").split("\n"):
        line = _LABEL.sub(chip, raw.strip())
        if not line:
            continue                               # a blank line ends nothing
        if line.startswith("|"):
            items = None
            typed.append(line)
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        end_table()
        numbered, item = _NUMBERED.fullmatch(line), _ITEM.fullmatch(line)
        marker, said = item.groups() if item else ("", "")
        scheme = ("roman" if marker in _ROMAN and (marker == "i" or len(marker) > 1)
                  else "alpha" if len(marker) == 1 else None)
        if scheme and items is not None:
            seq = _ROMAN if items["scheme"] == "roman" else list(string.ascii_lowercase)
            at = seq.index(items["last"]) if items["last"] in seq else len(seq)
            follows = seq[at + 1] if at + 1 < len(seq) else None
            if marker in ("a", "i") and marker != follows and scheme != items["scheme"]:
                # ponytail: one list level, as the model and the renderer hold; a nested
                # (i) run needs list items with bodies in model, renderer and preflight
                raise LibraryRefused(f"“{line[:60]}” starts a list inside a list item, "
                                     "which a template cannot number — make the outer "
                                     "items numbered sub-clauses (4.1, 4.2) instead")
            if marker not in ("a", "i") or marker == follows:
                items["block"]["items"].append(said)          # renumbered as shown
                items["last"] = marker
                typed.append(said)
                continue
        if scheme:
            block = {"kind": "list", "items": [said]}
            put(block)
            items = {"block": block, "scheme": scheme, "last": marker}
            typed.append(said)
            continue
        items = None
        if numbered:
            depth = len(numbered.group(1).split("."))
            if depth > model.MAX_LEVEL:
                raise LibraryRefused(f"“{line[:60]}” nests deeper than "
                                     f"{model.MAX_LEVEL} levels")
            while len(stack) < depth - 1:
                stack.append(stack[-1])
            container, path = stack[depth - 2]
            path = (*path, sum(b["kind"] == "sub" for b in container) + 1)
            sub: dict[str, Any] = {"kind": "sub", "text": numbered.group(2), "body": []}
            if path in keys:
                sub["key"] = keys[path]
            old = titles.get(path)          # the run-in title it had, if still typed
            if old and sub["text"].startswith(old["title"]):
                sub["text"] = sub["text"][len(old["title"]):]
                sub.update({k: old[k] for k in ("title", "title_style") if k in old})
            container.append(sub)
            stack = [*stack[:depth - 1], (sub["body"], path)]
            typed.append(numbered.group(2))
            continue
        typed.append(line)
        term = _OPENS_ON_TERM.fullmatch(line)
        if line in headings:
            put({"kind": "heading", "text": line})
        elif (image := _IMAGE.fullmatch(line)) and image.group(1) in images:
            put(dict(images[image.group(1)]))
        elif term:
            put({"kind": "definition", "term": term.group(1), "text": term.group(2)})
        else:
            put({"kind": "p", "text": line})
    end_table()
    if not body:
        raise LibraryRefused("the wording is empty")
    stored = [x["text"] for x in outline(body, "1")]
    if _words(" ".join(stored)) != _words(" ".join(typed)):  # a parser fault: refuse
        raise LibraryRefused("the wording could not be read into clauses word for word")
    return body


def _pinned(db: DBSession, tv: M.TemplateVersion, clause_key: str
            ) -> tuple[dict[str, Any], M.ClauseVersion]:
    if tv.status != "DRAFT":
        raise LibraryRefused(f"this template is {tv.status}; its clauses are fixed — "
                             "a new template version is needed")
    pin = next((p for p in pins(tv) if p["clause_key"] == clause_key), None)
    if pin is None:
        raise LibraryRefused("not a clause of this template")
    return pin, db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == clause_key,
        M.ClauseVersion.version == pin["version"])).scalar_one()


def replacement(db: DBSession, tv: M.TemplateVersion, clause_key: str,
                text: str) -> list[dict[str, Any]]:
    """The lawyer's wording for this clause as the blocks it would store — nothing
    written (the dry run of `decide`'s REPLACE)."""
    _, current = _pinned(db, tv, clause_key)
    body = parse_wording(text, current.body)
    unknown = sorted(set(slots(body)) - {v["key"] for v in tv.variables})
    if unknown:
        raise LibraryRefused(f"the wording uses {unknown}, which are not fields of "
                             "this template")
    return body


def decide(db: DBSession, tv: M.TemplateVersion, clause_key: str, decision: str, *,
           actor_id: UUID, reason: str | None = None, text: str | None = None,
           request_id: str | None = None) -> M.ClauseVersion:
    """Record one lawyer action on one pinned clause → the new APPROVED row.

    The caller has checked ``legal.approve_customization`` and locked ``tv``."""
    pin, current = _pinned(db, tv, clause_key)
    if decision == "APPROVE" and current.status == "APPROVED":
        raise LibraryRefused("this clause is already approved")
    if decision != "APPROVE" and not (reason or "").strip():
        raise LibraryRefused("a reason is required")
    body = current.body
    if decision == "REPLACE":
        body = replacement(db, tv, clause_key, text or "")
    clause = {"title": current.title, "body": body, "realises": current.realises,
              "stance": current.stance}
    digest = clause_hash(clause)
    latest = db.execute(select(func.max(M.ClauseVersion.version)).where(
        M.ClauseVersion.clause_key == clause_key)).scalar_one()
    row_id = uuid.uuid4()
    event = A.record(db, action=DECISIONS[decision], entity_type="clause_version",
                     entity_id=row_id, actor_id=actor_id, request_id=request_id,
                     after={"template_key": tv.template_key,
                            "template_version": tv.version,
                            "clause_key": clause_key, "version": latest + 1,
                            "based_on": pin["version"], "content_hash": digest,
                            "reason": reason})
    source = {"kind": "LAWYER", "supplier": f"lawyer:{actor_id}",
              "approval_ref": str(event.id), "sha256": digest, "decision": decision,
              "reason": reason,
              **({"text": text} if decision == "REPLACE" else {}),
              "based_on": {"version": current.version,
                           "content_hash": current.content_hash,
                           "supplier": (current.source or {}).get("supplier")}}
    row = M.ClauseVersion(id=row_id, clause_key=clause_key, version=latest + 1,
                          status="APPROVED", title=current.title, body=body,
                          realises=current.realises, stance=current.stance, source=source,
                          content_hash=digest, created_by=actor_id, approved_by=actor_id,
                          approved_at=datetime.now(UTC))
    db.add(row)
    db.flush()
    repinned = [{**p, "version": row.version} if p["clause_key"] == clause_key else p
                for p in tv.clauses]
    tv.clauses = repinned
    tv.annexures = [{**a, "clauses": [{**p, "version": row.version}
                                      if p["clause_key"] == clause_key else p
                                      for p in a.get("clauses", [])]}
                    for a in tv.annexures]
    sc = (tv.layout or {}).get("special_conditions") or {}
    if (sc.get("frame") or {}).get("clause_key") == clause_key:
        tv.layout = {**tv.layout, "special_conditions": {
            **sc, "frame": {**sc["frame"], "version": row.version}}}
    db.flush()
    _rehash(db, tv)
    db.flush()
    return row


def mark_approved(db: DBSession, tv: M.TemplateVersion, *, actor_id: UUID) -> None:
    """DRAFT → APPROVED once every pinned clause is APPROVED (just before the publish
    gate, which re-checks it); otherwise left for the gate to name what is missing."""
    done, total = progress(db, tv)
    if tv.status == "DRAFT" and total and done == total:
        tv.status, tv.approved_by = "APPROVED", actor_id
        tv.approved_at = datetime.now(UTC)
        db.flush()
