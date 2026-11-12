"""Prepare our reply — the client's own DOCX with OUR answers as Word tracked changes
(R6, `AM-251` r2).

Every change is a w:ins / w:del authored by ``author`` at ``when``; nothing else in the
file moves. A paragraph no edit names is never touched, the client's own tracked changes
stay where they are, and an anchor that does not locate exactly one paragraph is refused,
never guessed (rule 15). What an edit SAYS is the caller's: this module writes only the
wording it is handed — answers recorded in LegalMind (`AM-251` r2, `AM-252` r2) — and
decides nothing. No model is in this path (`AM-251` r1/r3).

A paragraph's text is the parser's own accepted view (`_docx_text`), so the anchor a
caller takes from an evidence row is the text located here, and the reply reads back
through `parse_docx` as exactly these changes (AM-146/157).

Same inputs and ``when`` → the same document.xml: change ids count up from the file's
highest id in edit order, and nothing else varies.
"""

from __future__ import annotations

import copy
import difflib
import io
import itertools
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from legalmind.ingestion.parsing import _VISIBLE_RUN, _docx_text, normalize_text

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
#: run children read as one character, as the parser's `_docx_text` reads them
_ONE_CHAR = {"tab": "\t", "br": "\n", "cr": "\n", "noBreakHyphen": "-", "ptab": "\t"}
#: run children with no text that may travel with a split run (Word's layout cache)
_ZERO_WIDTH = {"lastRenderedPageBreak"}
#: a tracked-change container already in the client's file
_TRACKED = {_W + "ins", _W + "moveTo", _W + "del", _W + "moveFrom"}
#: word-level diff tokens: a word, a run of white space, one punctuation mark
_TOKEN = re.compile(r"\w+|\s+|[^\w\s]")


@dataclass(frozen=True)
class ReplyEdit:
    """One paragraph-level answer.

    ``anchor_text``: the paragraph's current text as the client's file shows it (the
    accepted view, compared normalized). ``index_hint``: its position among the body's
    paragraphs — table cells included, text boxes not, the parser's order — used ONLY to
    choose among several exact matches, never to locate a paragraph the text does not
    match. ``new_text``: our wording; ``None`` deletes the paragraph. With
    ``insert_after_anchor`` the wording becomes a new paragraph after the anchor (a
    paragraph the client deleted, re-inserted)."""

    anchor_text: str
    new_text: str | None
    insert_after_anchor: bool = False
    index_hint: int | None = None


@dataclass(frozen=True)
class ReplyNote:
    """A Word comment by ``author`` on the paragraph ``anchor_text`` names (located as an
    edit's anchor is) — where an answer could not be written and a person restores our
    wording by hand (AB-151). The text is the caller's fixed sentence, never composed."""

    anchor_text: str
    text: str
    index_hint: int | None = None


class ReplyError(Exception):
    """An edit that cannot be applied exactly. ``code``: ANCHOR_NOT_FOUND ·
    ANCHOR_AMBIGUOUS · CONFLICTING_EDITS · INVALID_EDIT · UNSUPPORTED."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def _body(docx_bytes: bytes) -> tuple[Any, list[Any], list[str]]:
    document = docx.Document(io.BytesIO(docx_bytes))
    paragraphs = document.element.body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    return document, paragraphs, [normalize_text(_docx_text(p)) for p in paragraphs]


def _marker(document: Any, author: str, when: datetime) -> Callable[[str], Any]:
    stamp = (when if when.tzinfo else when.replace(tzinfo=UTC)).astimezone(UTC)
    ids = itertools.count(1 + max((int(v) for v in document.element.xpath("//@w:id")
                                   if v.isdigit()), default=0))
    # ponytail: ids are unique within document.xml; footnote/header parts keep their own

    def mark(tag: str) -> Any:
        return OxmlElement(tag, {qn("w:id"): str(next(ids)), qn("w:author"): author,
                                 qn("w:date"): stamp.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return mark


def unplaceable(docx_bytes: bytes,
                groups: Mapping[str, Sequence[ReplyEdit]]) -> dict[str, ReplyError]:
    """Which groups (one answered change each) cannot be written exactly, and why —
    every group tried, not just the first: each edit located, and each rewrite dry-run
    on a copy of its paragraph, so `apply_reply` on the rest cannot refuse. A paragraph
    two groups rewrite refuses the later one."""
    document, paragraphs, texts = _body(docx_bytes)
    mark = _marker(document, "", datetime.now(UTC))
    claimed: set[int] = set()
    failed: dict[str, ReplyError] = {}
    for key, edits in groups.items():
        mine: set[int] = set()
        try:
            for edit in edits:
                k = _locate(texts, edit)
                if edit.insert_after_anchor:
                    _new_paragraph(paragraphs[k], edit.new_text or "", mark)
                    continue
                if k in claimed or k in mine:
                    raise ReplyError("two edits rewrite the same paragraph",
                                     "CONFLICTING_EDITS")
                mine.add(k)
                _rewrite(copy.deepcopy(paragraphs[k]), edit.new_text or "", mark)
        except ReplyError as exc:
            failed[key] = exc
            continue
        claimed |= mine
    return failed


def placeable(docx_bytes: bytes, notes: Sequence[ReplyNote]) -> list[ReplyNote]:
    """The notes whose paragraph can be located exactly — a comment is never guessed
    onto another paragraph (rule 15); the caller lists the rest without one."""
    _, _, texts = _body(docx_bytes)
    out = []
    for note in notes:
        try:
            _locate(texts, ReplyEdit(note.anchor_text, "", index_hint=note.index_hint))
        except ReplyError:
            continue
        out.append(note)
    return out


def apply_reply(docx_bytes: bytes, edits: Sequence[ReplyEdit], *,
                author: str = "LeapSwitch Legal", when: datetime,
                notes: Sequence[ReplyNote] = ()) -> bytes:
    """The client's DOCX with ``edits`` applied as tracked changes, and ``notes`` as
    Word comments. Every anchor is located before anything is written, so a refused
    edit leaves no half-made reply."""
    document, paragraphs, texts = _body(docx_bytes)
    located = [(edit, paragraphs[_locate(texts, edit)]) for edit in edits]
    rewritten = [p for edit, p in located if not edit.insert_after_anchor]
    if len(set(rewritten)) != len(rewritten):
        raise ReplyError("two edits rewrite the same paragraph", "CONFLICTING_EDITS")
    noted = [(note, paragraphs[_locate(texts, ReplyEdit(
        note.anchor_text, "", index_hint=note.index_hint))]) for note in notes]
    mark = _marker(document, author, when)

    last: dict[Any, Any] = {}       # several paragraphs after one anchor keep their order
    for edit, p in located:
        if edit.insert_after_anchor:
            new = _new_paragraph(p, edit.new_text or "", mark)
            last.get(p, p).addnext(new)
            last[p] = new
        else:
            _rewrite(p, edit.new_text or "", mark)
            if edit.new_text is None:
                _mark_paragraph(p, "w:del", mark)
    for note, p in noted:
        runs = _visible_runs(p) or [p.add_r()]
        paragraph = Paragraph(p, document)
        document.add_comment([Run(runs[0], paragraph), Run(runs[-1], paragraph)],
                             text=note.text, author=author, initials="LS")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def _locate(texts: list[str], edit: ReplyEdit) -> int:
    if edit.insert_after_anchor and edit.new_text is None:
        raise ReplyError("an inserted paragraph needs text", "INVALID_EDIT")
    want = normalize_text(edit.anchor_text)
    hits = [i for i, text in enumerate(texts) if text == want]
    if len(hits) > 1 and edit.index_hint in hits:
        hits = [edit.index_hint]
    if not hits:
        raise ReplyError(f"no paragraph reads {want[:60]!r}", "ANCHOR_NOT_FOUND")
    if len(hits) > 1:
        raise ReplyError(f"{len(hits)} paragraphs read {want[:60]!r} and no hint chooses",
                         "ANCHOR_AMBIGUOUS")
    return hits[0]


def _visible_runs(p: Any) -> list[Any]:
    """The runs the parser reads as ``p``'s accepted text, in order."""
    depth = len(p.xpath("ancestor-or-self::w:p"))
    return list(p.xpath(f".//w:r[count(ancestor::w:p) = {depth} and {_VISIBLE_RUN}]"))


def _atoms(run: Any) -> list[tuple[Any, str | None]]:
    """A run's content as (element, text): one atom per character of a w:t, one per
    tab/break, "" for a layout cache, ``None`` for content a split cannot carry (a
    drawing, a field character) — refused only if that run must be split."""
    out: list[tuple[Any, str | None]] = []
    for child in run:
        name = child.tag.removeprefix(_W)
        if name == "rPr":
            continue
        if name == "t":
            out += [(child, ch) for ch in child.text or ""]
        else:
            out.append((child, _ONE_CHAR.get(name, "" if name in _ZERO_WIDTH else None)))
    return out


def _text(run: Any, text: str, deleted: bool = False) -> None:
    """Append ``text`` to ``run`` as w:t (w:delText when deleted), tabs and breaks."""
    for piece in re.split(r"([\t\n])", text):
        if piece in ("\t", "\n"):
            run.append(OxmlElement("w:tab" if piece == "\t" else "w:br"))
        elif piece:
            t = OxmlElement("w:delText" if deleted else "w:t",
                            {qn("xml:space"): "preserve"})
            t.text = piece
            run.append(t)


def _run(rpr: Any, text: str = "", deleted: bool = False) -> Any:
    """A new run carrying ``rpr`` (copied): the formatting of the text it replaces."""
    run = OxmlElement("w:r")
    if rpr is not None:
        run.append(copy.deepcopy(rpr))
    _text(run, text, deleted)
    return run


def _rewrite(p: Any, new: str, mark: Callable[[str], Any]) -> None:
    """``p``'s accepted text becomes ``new`` by a word-level diff: removed words wrapped
    in w:del where they stand, added words in a w:ins right after the words they follow,
    each run split keeping its own rPr. A run with nothing removed or added after it is
    left exactly as it was."""
    runs = _visible_runs(p)
    atoms = [_atoms(run) for run in runs]
    stream = [(i, k) for i, run_atoms in enumerate(atoms)
              for k, (_, ch) in enumerate(run_atoms) if ch]
    old = "".join(atoms[i][k][1] or "" for i, k in stream)
    if old != _docx_text(p):
        raise ReplyError("the paragraph's text is not all in plain runs", "UNSUPPORTED")
    old_tokens, new_tokens = _TOKEN.findall(old), _TOKEN.findall(new)
    starts = [0, *itertools.accumulate(map(len, old_tokens))]
    deleted: set[tuple[int, int]] = set()
    inserts: dict[tuple[int, int], str] = {}  # (run, atom it follows; -1 = run's start)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, old_tokens, new_tokens, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        deleted.update(stream[starts[i1]:starts[i2]])
        if j2 > j1:
            added, at = "".join(new_tokens[j1:j2]), starts[i2]
            if not stream:                       # an empty paragraph: added at its end
                ins = mark("w:ins")
                ins.append(_run(None, added))
                p.append(ins)
            else:
                inserts[stream[at - 1] if at else (stream[0][0], -1)] = added

    for i, run in enumerate(runs):
        if not any(key[0] == i for key in (*deleted, *inserts)):
            continue
        if any(ch is None for _, ch in atoms[i]):
            raise ReplyError("a run to change holds a drawing or field", "UNSUPPORTED")
        rpr = run.find(_W + "rPr")
        pieces: list[tuple[str, list[tuple[Any, str]] | str]] = []
        if (i, -1) in inserts:
            pieces.append(("ins", inserts[(i, -1)]))
        op = "keep"
        for k, (element, ch) in enumerate(atoms[i]):
            if ch:                     # a layout cache goes with the text before it
                op = "del" if (i, k) in deleted else "keep"
            if pieces and pieces[-1][0] == op:
                pieces[-1][1].append((element, ch or ""))  # type: ignore[union-attr]
            else:
                pieces.append((op, [(element, ch or "")]))
            if (i, k) in inserts:
                pieces.append(("ins", inserts[(i, k)]))
        made = [_piece(op, body, rpr, mark) for op, body in pieces]
        for element in made:
            run.addprevious(element)
        run.getparent().remove(run)
        for element in made:
            if element.tag == _W + "ins":
                _hoist(element, p, mark)


def _piece(op: str, body: list[tuple[Any, str]] | str, rpr: Any,
           mark: Callable[[str], Any]) -> Any:
    """One stretch of a split run: kept as a plain run, or in our w:del / w:ins."""
    if isinstance(body, str):
        ins = mark("w:ins")
        ins.append(_run(rpr, body))
        return ins
    run, buffer = _run(rpr), ""
    for element, ch in body:
        if element.tag == _W + "t":
            buffer += ch
            continue
        _text(run, buffer, op == "del")
        buffer = ""
        run.append(copy.deepcopy(element))
    _text(run, buffer, op == "del")
    if op == "keep":
        return run
    wrapper = mark("w:del")
    wrapper.append(run)
    return wrapper


def _hoist(ins: Any, p: Any, mark: Callable[[str], Any]) -> None:
    """Our w:ins that landed inside the client's tracked insertion (or move) is lifted
    out beside it, splitting it in two (the second half under a fresh id) — a w:ins
    never nests in another. Our w:del inside theirs stays: that IS Word's form for
    deleting another author's insertion."""
    tracked = [a for a in itertools.takewhile(lambda a: a is not p, ins.iterancestors())
               if a.tag in _TRACKED]
    if not tracked:
        return
    parent = ins.getparent()
    if tracked != [parent]:
        raise ReplyError("a change inside a nested tracked change", "UNSUPPORTED")
    if ins.getnext() is None:
        parent.addnext(ins)
    elif ins.getprevious() is None:
        parent.addprevious(ins)
    else:
        rest = parent.makeelement(parent.tag, dict(parent.attrib))
        rest.set(qn("w:id"), mark("w:ins").get(qn("w:id")))
        for sibling in list(ins.itersiblings()):
            rest.append(sibling)
        parent.addnext(ins)
        ins.addnext(rest)


def _mark_paragraph(p: Any, tag: str, mark: Callable[[str], Any]) -> None:
    """Record ``p``'s paragraph mark as inserted or deleted (w:pPr/w:rPr/w:ins|w:del),
    so accepting a deletion removes the paragraph and rejecting an insertion does."""
    ppr = p.get_or_add_pPr()
    rpr = ppr.find(_W + "rPr")
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        tail = next((c for c in ppr if c.tag in (_W + "sectPr", _W + "pPrChange")), None)
        if tail is not None:
            tail.addprevious(rpr)
        else:
            ppr.append(rpr)
    if rpr.find(_W + tag.removeprefix("w:")) is not None:
        return                                   # the client already marked it so
    their_ins = rpr.find(_W + "ins")             # CT_ParaRPr: ins before del
    if tag == "w:del" and their_ins is not None:
        their_ins.addnext(mark(tag))
    else:
        rpr.insert(0, mark(tag))


def _new_paragraph(anchor: Any, text: str, mark: Callable[[str], Any]) -> Any:
    """A tracked new paragraph shaped like ``anchor`` (its paragraph properties, its
    first run's formatting) — the client's paragraph we restore beside it."""
    p = OxmlElement("w:p")
    source = anchor.find(_W + "pPr")
    if source is not None:
        ppr = copy.deepcopy(source)
        for child in [c for c in ppr if c.tag in (_W + "rPr", _W + "sectPr",
                                                   _W + "pPrChange")]:
            ppr.remove(child)            # never a section break, never their change
        p.append(ppr)
    _mark_paragraph(p, "w:ins", mark)
    runs = _visible_runs(anchor)
    ins = mark("w:ins")
    ins.append(_run(runs[0].find(_W + "rPr") if runs else None, text))
    p.append(ins)
    return p
