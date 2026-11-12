"""Our recorded answers as paragraph edits on the client's own DOCX (R6, `AM-251` r2).

Only the answers decide what is written, and only in wording that already exists:

* keep ours on a MODIFIED clause — the client's paragraphs read our previous wording;
* keep ours on an ADDED clause (or annexure) — their paragraphs are deleted;
* keep ours on a DELETED clause — ours re-inserted after the clause before it;
* keep ours on a MOVED clause — deleted where they put it, re-inserted where we had it;
* accept theirs — nothing;
* write our wording (`AM-284`) — the client's paragraphs of that clause read the stored
  wording, as our tracked change, only when its SHA-256 is the one recorded (r4; the
  router has already required the Legal Decision carrying it, r2);
* use our standard (`AM-284` r5) — the same, with the published clause's own words.

A "note to the client" becomes a Word comment at that change (`AM-284` r6); the internal
note is never passed here (`AM-285` r3).

The rows are `negotiation`'s own (the same units, alignment, kind and row key), so a row
key answered on the Changes tab is the row written here. Nothing is composed: every text
written is an evidence row of our previous version, a published clause's text, or
wording a holder typed and approved (rule 7, `AM-251` r3 as amended by `AM-284` r3/r4).
Client paper first (`AM-290`): ``before`` None, the rows the THEIRS rows passed in.

A row that cannot be written exactly is returned with its reason, never dropped: the
reply is refused, or — when the caller names those rows — prepared without them, each
marked by a fixed Word comment where a person restores our wording by hand (AB-151).
"""

from __future__ import annotations

import dataclasses
import difflib
import functools
import hashlib
import io
from collections.abc import Callable, Mapping
from typing import NamedTuple
from uuid import UUID

import docx
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis import negotiation as N
from legalmind.analysis.negotiation import THEIRS_KIND as THEIRS
from legalmind.db import models as M
from legalmind.drafting.model import SLOT
from legalmind.drafting.reply_docx import ReplyEdit, ReplyError, ReplyNote
from legalmind.ingestion.parsing import (
    _W,
    _docx_cell,
    _docx_children,
    _docx_text,
    normalize_text,
    table_row,
)
from legalmind.mapping.service import load_clauses


class Answer(NamedTuple):
    """One recorded answer as the builder needs it: its kind, the text it writes (the
    stored wording or the published clause's words), the hash that wording was approved
    under, and the note to the client — never the internal note."""

    kind: str
    text: str | None = None
    sha256: str | None = None
    client_note: str | None = None


class RowPlan(NamedTuple):
    """One answer to write: its edits, or why they cannot be written (``error``), where
    a comment would mark it (``spot``, None when no paragraph of theirs is near), and
    the note to the client at that place (``note``)."""

    row_key: str
    clause: str
    edits: list[ReplyEdit]
    error: ReplyError | None
    spot: ReplyNote | None
    note: ReplyNote | None = None


#: the fixed comment at a change left to a person (AB-151) — never composed text
MANUAL_NOTE = "LeapSwitch: restore our wording here by hand — {clause}"
_WRITES = ("keep_ours", "write_wording", "use_standard")


def sha256(text: str) -> str:
    """The wording's SHA-256 — what its Legal Decision carries (`AM-284` r2)."""
    return hashlib.sha256(text.encode()).hexdigest()


def clause_text(cv: M.ClauseVersion) -> str | None:
    """A published clause's own words, one paragraph per line — or None where they are
    not fixed text: a ``{var}`` or ``{xref}`` slot, a table or an image needs the
    contract's own model (slices S5/S6), and is never guessed into a reply (rule 15)."""
    lines: list[str] = []

    def walk(blocks: list[dict]) -> bool:
        for b in blocks:
            kind = b.get("kind")
            texts = ([b.get("text", "")] if kind in ("p", "heading", "sub", "definition")
                     else list(b.get("items", ())) if kind == "list" else None)
            if texts is None or any(m.group(1) != "term" for t in texts
                                    for m in SLOT.finditer(t)):
                return False
            lines.extend(SLOT.sub(lambda m: m.group(2), t) for t in texts if t.strip())
            if not walk(b.get("body", [])):
                return False
        return True
    return "\n".join(lines) if walk(cv.body or []) and lines else None


def reply_rows(db: DBSession, before: M.DocumentVersion | None, after: M.DocumentVersion,
               answers: Mapping[str, Answer], docx_bytes: bytes,
               theirs_rows: list[dict] | None = None,
               template: dict | None = None) -> list[RowPlan]:
    """Each answer in ``answers`` (row key -> `Answer`) that writes text or carries a
    note to the client, as the edits that write it into the client's file
    ``docx_bytes`` (the stored bytes of ``after``), in the document's order. ``before``
    None: client paper first, the rows being ``theirs_rows`` (`AM-290`) — unless
    ``template`` is the blank it was made from (`drafting.blank.link`, `AM-302`),
    compared as ours exactly as `negotiation.changes` compares it."""
    paper_first = before is None and template is None
    ours = load_clauses(db, before.id) if before is not None else (
        template["clauses"] if template else [])
    theirs = load_clauses(db, after.id)
    if template:
        theirs = [c for c in theirs if not c.content.startswith(template["note_open"])]
    text = {c.evidence_id: c.content for c in (*ours, *theirs)}
    old, new = N._units(ours), N._units(theirs)
    if template:
        N.as_filled(old, new, template)
    rows = N._align(old, new)
    paired = {i: j for i, j, moved in rows
              if i is not None and j is not None and not moved}

    # which paragraph each of the client's rows is, when its text occurs more than once:
    # its rank among the parser's NON-TABLE rows of that text, over the body's non-table
    # paragraphs — a table cell reading the same words is never counted (a table row is
    # located cell by cell, below)
    body = docx.Document(io.BytesIO(docx_bytes)).element.body
    elements = body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    paragraphs = [normalize_text(_docx_text(p)) for p in elements]
    plain = [k for k, p in enumerate(elements) if not p.xpath("ancestor::w:tbl")]
    tables = _tables(body, {p: k for k, p in enumerate(elements)})
    rank: dict[UUID, int] = {}
    seen: dict[str, int] = {}
    for c in theirs:
        if c.content in tables or c.content.startswith("| "):
            continue
        rank[c.evidence_id] = seen.get(c.content, 0)
        seen[c.content] = rank[c.evidence_id] + 1

    def anchor(evidence_id: str) -> tuple[str, int | None]:
        content = text[UUID(evidence_id)]
        hits = [k for k in plain if paragraphs[k] == content]
        k = rank.get(UUID(evidence_id))
        if k is None or (len(hits) > 1 and len(hits) > seen[content]):
            # more paragraphs read it than rows the parser gave: the rank says nothing
            # about which one, so `_locate` refuses ANCHOR_AMBIGUOUS (rule 15)
            return content, None
        return content, hits[k] if k < len(hits) else None

    def edit(evidence_id: str, new_text: str | None,
             insert: bool = False) -> list[ReplyEdit]:
        content, hint = anchor(evidence_id)
        if content in tables or (new_text or "").startswith("| "):
            return _table_edits(tables.get(content, []), new_text, insert, paragraphs)
        return [ReplyEdit(content, new_text, insert_after_anchor=insert, index_hint=hint)]

    def spot(n: dict | None, i: int | None, label: str) -> ReplyNote | None:
        """Their paragraph nearest the change: its first row, else where we had it."""
        try:
            evidence = n["evidence_ids"][0] if n else where_we_had(i or 0)
        except ReplyError:
            return None
        content, hint = anchor(evidence)
        if content in tables:
            rows = tables[content] or []
            first = next((k for r in rows for c in r for k in c.paragraphs
                          if paragraphs[k]), None)
            return None if first is None else ReplyNote(
                paragraphs[first], MANUAL_NOTE.format(clause=label), first)
        return ReplyNote(content, MANUAL_NOTE.format(clause=label), hint)

    def where_we_had(i: int) -> str:
        """The client's last row of the nearest clause before ours that kept its place."""
        for k in range(i - 1, -1, -1):
            if k in paired:
                return new[paired[k]]["evidence_ids"][-1]
        raise ReplyError("our clause stood first in the document; restore it by hand",
                         "UNSUPPORTED")

    def one(kind: str, i: int | None, o: dict | None, n: dict | None) -> list[ReplyEdit]:
        """One answered change's edits."""
        edits: list[ReplyEdit] = []
        if kind in ("ADDED", "NEW_ANNEXURE", "MOVED"):
            assert n is not None
            edits += [x for e in n["evidence_ids"] for x in edit(e, None)]
        if kind in ("DELETED", "MOVED"):
            assert o is not None and i is not None
            at = where_we_had(i)
            edits += [x for e in o["evidence_ids"] for x in edit(at, text[UUID(e)], True)]
        if kind == "MODIFIED":
            assert o is not None and n is not None and i is not None
            edits += _rewrite(o["evidence_ids"], n["evidence_ids"], text, edit,
                              functools.partial(where_we_had, i))
        return edits

    def ours_now(i: int | None, n: dict | None, answer: Answer) -> list[ReplyEdit]:
        """`AM-284`: the clause reads ``answer.text`` — their first paragraph rewritten,
        their others deleted, our further paragraphs inserted after it; a clause they
        deleted is re-inserted where we had it."""
        if answer.text is None or (answer.kind == "write_wording"
                                   and sha256(answer.text) != answer.sha256):
            raise ReplyError("the wording is not the wording that was approved",
                             "INVALID_EDIT")
        lines = answer.text.split("\n")
        if n is None:
            if i is None:
                raise ReplyError("the client's paper has no place for this point; "
                                 "add it by hand", "UNSUPPORTED")
            at = where_we_had(i)
            return [x for line in lines for x in edit(at, line, True)]
        first, *rest = n["evidence_ids"]
        return [*edit(first, lines[0]), *(x for line in lines[1:]
                                         for x in edit(first, line, True)),
                *(x for e in rest for x in edit(e, None))]

    def plan(key: str, kind: str, i: int | None, o: dict | None, n: dict | None,
             label: str) -> RowPlan:
        answer = answers[key]
        place = spot(n, i, label)
        note = None if answer.client_note is None or place is None else \
            dataclasses.replace(place, text=answer.client_note)
        try:
            if answer.client_note is not None and note is None:
                raise ReplyError("the note to the client has no paragraph to sit on",
                                 "ANCHOR_NOT_FOUND")
            edits = (one(kind, i, o, n) if answer.kind == "keep_ours"
                     else ours_now(i, n, answer) if answer.kind in _WRITES else [])
            return RowPlan(key, label, edits, None, place, note)
        except ReplyError as exc:
            return RowPlan(key, label, [], exc, place, note)

    def wanted(key: str) -> bool:
        a = answers.get(key)
        return a is not None and (a.kind in _WRITES or a.client_note is not None)

    out: list[RowPlan] = []
    if paper_first:                                     # `AM-290`: client paper first
        for row in theirs_rows or ():
            if not wanted(row["row_key"]):
                continue
            ids = (row["after"] or {}).get("evidence_ids") or []
            n = {"evidence_ids": ids} if ids else None
            c = row["clause"]
            label = (f"clause {N.clause_label(c, heading=False)}" if c["number"]
                     else c["heading"] or row["review"]["after"][0]["requirement_code"])
            if answers[row["row_key"]].kind == "keep_ours":
                out.append(RowPlan(row["row_key"], label, [], ReplyError(
                    "there is no wording of ours to keep on the client's paper",
                    "UNSUPPORTED"), None))
                continue
            held = row.get("clauses") or []
            if len(held) > 1 and answers[row["row_key"]].kind in _WRITES:
                # one wording over several clauses would rewrite the first and delete
                # the rest of the client's text — a person places it (rule 15)
                said = list(dict.fromkeys(N.clause_label(c) or "?" for c in held))
                named = (", ".join(said[:-1]) + " and " + said[-1]) if len(said) > 1 \
                    else said[0]
                out.append(RowPlan(row["row_key"], label, [], ReplyError(
                    f"this point covers clauses {named}; write it in by hand",
                    "UNSUPPORTED"), spot(n, None, label)))
                continue
            out.append(plan(row["row_key"], THEIRS, None, None, n, label))
        return out
    for i, j, moved in rows:
        o = old[i] if i is not None else None
        n = new[j] if j is not None else None
        kind = N._kind(o, n, moved)
        key = N._row_key(kind, o, n) if kind else ""
        if kind is None or not wanted(key):
            continue
        here = n or o
        assert here is not None
        label = (f"clause {N.clause_label(here, heading=False)}" if here["number"]
                 else here["heading"] or "the opening text")
        out.append(plan(key, kind, i, o, n, label))
    return out


def _rewrite(ours: list[str], theirs: list[str], text: dict,
             edit: Callable[..., list[ReplyEdit]],
             before_unit: Callable[[], str]) -> list[ReplyEdit]:
    """One clause's rows back to ours: a changed row rewritten, a row they added deleted,
    a row they removed re-inserted after the row before it."""
    a = [text[UUID(e)] for e in ours]
    b = [text[UUID(e)] for e in theirs]
    out: list[ReplyEdit] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False) \
            .get_opcodes():
        if tag == "equal":
            continue
        both = min(i2 - i1, j2 - j1)
        out += [x for k in range(both) for x in edit(theirs[j1 + k], a[i1 + k])]
        out += [x for e in theirs[j1 + both:j2] for x in edit(e, None)]
        if i2 - i1 > both:
            at = theirs[j1 + both - 1] if j1 + both else before_unit()
            out += [x for k in range(i1 + both, i2) for x in edit(at, a[k], True)]
    return out


class _Cell(NamedTuple):
    """One shown table cell: its parsed text, its paragraphs' indices, and whether it
    only shows the merged cell above it (as the parser reads it)."""

    text: str
    paragraphs: list[int]
    merged: bool
    nested: bool


def _tables(body, index: dict) -> dict[str, list[list[_Cell]] | None]:
    """Each body table by the text the parser gives it (its `table_row` lines), with
    each shown row's cells — ``None`` where two tables read the same, so neither is
    guessed."""
    out: dict[str, list[list[_Cell]] | None] = {}
    for tbl in body.xpath(".//w:tbl[not(ancestor::w:tbl)]"):
        rows: list[list[_Cell]] = []
        above: dict[int, str] = {}
        for tr in _docx_children(tbl, _W + "tr"):
            cells = []
            here: dict[int, str] = {}
            col = tr.grid_before
            for tc in _docx_children(tr, _W + "tc"):
                merged = tc.vMerge == "continue"      # shows the cell above, as parsed
                here[col] = above.get(col, "") if merged else _docx_cell(tc)
                own = [index[p] for p in _docx_children(tc, _W + "p") if p in index]
                cells.append(_Cell(here[col], own, merged, bool(tc.xpath(".//w:tbl"))))
                col += tc.grid_span
            above = here
            if any(c.text for c in cells):
                rows.append(cells)
        key = normalize_text("\n".join(table_row([c.text for c in r]) for r in rows))
        out[key] = None if key in out else rows
    return out


def _table_edits(rows: list[list[_Cell]] | None, ours: str | None, insert: bool,
                 paragraphs: list[str]) -> list[ReplyEdit]:
    """A table back to our wording cell by cell, when its shape is unchanged and each
    changed cell is one plain paragraph; a table the client added has every cell's
    words struck (the grid stays — ponytail: Word's row deletion, w:trPr/w:del, if an
    empty grid ever matters). Anything else is restored by hand (rule 15)."""
    if rows is None:
        raise ReplyError("two tables read the same; restore it by hand",
                         "ANCHOR_AMBIGUOUS")
    if not rows or insert or (ours is not None and not ours.startswith("| ")):
        raise ReplyError("a table was moved, added beside our text or removed; restore "
                         "it by hand", "UNSUPPORTED")
    if ours is None:
        if any(c.nested for r in rows for c in r):
            raise ReplyError("a nested table to remove; restore it by hand",
                             "UNSUPPORTED")
        return [ReplyEdit(paragraphs[k], "", index_hint=k)
                for r in rows for c in r if not c.merged
                for k in c.paragraphs if paragraphs[k]]
    # ponytail: a "|" inside a cell miscounts the row, which then refuses (shape)
    mine = [[c.strip() for c in line.strip()[1:-1].split("|")]
            for line in ours.split("\n")]
    if [len(r) for r in mine] != [len(r) for r in rows]:
        raise ReplyError("a table changed shape; restore it by hand", "UNSUPPORTED")
    out = []
    for row, words in zip(rows, mine, strict=True):
        for cell, want in zip(row, words, strict=True):
            if " ".join(cell.text.split()) == want:
                continue
            if cell.merged or cell.nested or len(cell.paragraphs) != 1:
                raise ReplyError("a merged, nested or multi-paragraph table cell "
                                 "changed; restore it by hand", "UNSUPPORTED")
            k = cell.paragraphs[0]
            out.append(ReplyEdit(paragraphs[k], want, index_hint=k))
    return out
