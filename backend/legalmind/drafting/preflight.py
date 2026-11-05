"""Preflight — the checks that BLOCK a generated contract's download and send.

`check` returns every problem found (``code`` + a plain ``detail``), never only the
first; `require` raises `PreflightRefused` with that list. A problem is a reason to stop,
not a warning: the file is rebuilt from the model, never patched by hand.

On the DOCX: the numbering Word displays (the parser's own `_docx_list_numbers`) equals
the model's, clause by clause · every ``REF`` names a bookmark · no ``{`` slot or ``[ ]``
blank is left · a clean copy carries no revision or comment (`clean.has_markup`) · no
relationship is external · every image is embedded with alt text at the house minimum
resolution · a quoted defined term is defined · the document's own cross-reference
observations (`analysis.consistency`) are empty · it parses (`parse_docx`).
With the PDF too: the execution block sits on one page · each paragraph holding a
cross-reference reads in the PDF exactly as its cached DOCX text · no glyph runs past the
right margin · every footer's
page number runs 1, 2, 3 … in its own section.
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Any

from docx.oxml import parse_xml
from docx.oxml.ns import qn
from lxml import etree  # type: ignore[import-untyped]

from legalmind.analysis import consistency
from legalmind.drafting import clean, render_contract
from legalmind.drafting.model import defined_terms
from legalmind.ingestion.parsing import (
    ParseError,
    _docx_list_numbers,
    _docx_text,
    parse_docx,
)
from legalmind.mapping.engine import Clause

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_STORY = re.compile(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$")
_BLANK = re.compile(r"\{|\[\s*\]")
_REF = re.compile(r"\bREF\s+(\S+)")
_TIGHT = re.compile(r"\s+(?=[,.;:)])")          # a space before punctuation
_QUOTED = re.compile(r"[“\"]([A-Z][\w &/-]{1,60}?)[”\"]")
#: the house footer: the document ID, then the page number (`render_contract.furniture`)
#: how far a glyph may sit past the right margin (PDF points) before the page fails
MARGIN_TOLERANCE_PT = 0.5
_PAGE = re.compile(r"\bLM-\S+-v\d+-[0-9a-f]{8}\s+(\d+)\b")
SPECIAL = "lm:special-conditions"


@dataclass(frozen=True)
class Problem:
    code: str
    detail: str


class PreflightRefused(Exception):
    def __init__(self, problems: list[Problem]) -> None:
        super().__init__("; ".join(f"{p.code}: {p.detail}" for p in problems))
        self.problems = problems


def _norm(text: str) -> str:
    return " ".join(text.split())


def _parts(z: zipfile.ZipFile) -> dict[str, etree._Element]:
    return {n: parse_xml(z.read(n)) for n in z.namelist()
            if n.startswith("word/") and n.endswith(".xml")}


def _expected(model: Mapping[str, Any]) -> dict[str, list[str]]:
    """Tag → the numbers its content control should display, in order."""
    def subs(blocks: list[dict]) -> list[str]:
        out = []
        for b in blocks:
            if b["kind"] == "sub":
                out += [b["number"], *subs(b["body"])]
        return out
    out = {f"lm:{c['clause_key']}@{c['version']}": [c["number"], *subs(c["body"])]
           for c in [*model["body"],
                     *(c for s in model["schedules"] for c in s["clauses"])]}
    if model.get("special_conditions"):            # `AM-307`: entries 1, 2, …
        out[SPECIAL] = [e["n"] for e in model["special_conditions"]["entries"]]
    return out


def _numbering(docx_bytes: bytes, model: Mapping[str, Any]) -> list[Problem]:
    import docx
    document = docx.Document(io.BytesIO(docx_bytes))
    paragraphs = document.element.body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    shown = _docx_list_numbers(document, paragraphs)
    out = []
    expected = _expected(model)
    for sdt in document.element.body.iter(_W + "sdt"):
        tag = sdt.find(f"{_W}sdtPr/{_W}tag")
        tag = tag.get(_W + "val") if tag is not None else None
        if tag not in expected:
            continue
        got = [shown[p] for p in sdt.iter(_W + "p") if p in shown]
        want = expected.pop(tag)
        if got != want:
            out.append(Problem("NUMBERING",
                               f"{tag} displays {got}, the model says {want}"))
    out += [Problem("NUMBERING", f"{tag} is not in the file") for tag in expected]
    return out


def _images(z: zipfile.ZipFile, parts: Mapping[str, etree._Element],
            min_dpi: int) -> list[Problem]:
    from docx.image.image import Image
    out = []
    for name, root in parts.items():
        rels_name = f"{name.rsplit('/', 1)[0]}/_rels/{name.rsplit('/', 1)[1]}.rels"
        rels = (etree.fromstring(z.read(rels_name))
                if rels_name in z.namelist() else None)
        targets = {r.get("Id"): r.get("Target") for r in rels} if rels is not None else {}
        for inline in [*root.iter(qn("wp:inline")), *root.iter(qn("wp:anchor"))]:
            pr = inline.find(qn("wp:docPr"))
            label = pr.get("name", "an image") if pr is not None else "an image"
            if pr is None or not (pr.get("descr") or "").strip():
                out.append(Problem("IMAGE_ALT", f"{label} in {name} has no alt text"))
            blip = next(inline.iter(qn("a:blip")), None)
            rid = blip.get(qn("r:embed")) if blip is not None else None
            target = targets.get(rid or "")
            if not target:
                out.append(Problem("IMAGE_NOT_EMBEDDED",
                                   f"{label} in {name} is not embedded"))
                continue
            path = "word/" + target.lstrip("/").removeprefix("word/")
            extent = inline.find(qn("wp:extent"))
            if path in z.namelist() and extent is not None:
                px = Image.from_blob(z.read(path)).px_width
                inches = int(extent.get("cx")) / 914400
                if inches and px / inches < min_dpi:
                    out.append(Problem("IMAGE_RESOLUTION", f"{label} prints at "
                                       f"{px / inches:.0f} dpi, under {min_dpi}"))
    return out


def _defined_terms(body: etree._Element, roles: set[str],
                   headings: AbstractSet[str] = frozenset()) -> list[Problem]:
    """A quoted term must be defined somewhere — except the heading a Special Condition
    quotes for the clause it varies, and only inside the annexure (`AM-307`, L-4)."""
    paragraphs = list(body.iter(_W + "p"))
    special = {p for sdt in body.iter(_W + "sdt")
               if (tag := sdt.find(f"{_W}sdtPr/{_W}tag")) is not None
               and tag.get(_W + "val") == SPECIAL for p in sdt.iter(_W + "p")}
    texts = [(_norm(_docx_text(p)), p in special) for p in paragraphs]
    defined = set(roles)
    for t, _ in texts:
        defined |= defined_terms(t)
    used = {m.group(1) for t, inside in texts for m in _QUOTED.finditer(t)
            if not (inside and m.group(1) in headings)}
    return [Problem("UNDEFINED_TERM", f"“{term}” is used in quotes and never defined")
            for term in sorted(used - defined)]


def _consistency(docx_bytes: bytes) -> list[Problem]:
    try:
        parsed = parse_docx(docx_bytes)
    except ParseError as exc:
        return [Problem("PARSE", f"the parser cannot read the file ({exc.code})")]
    clauses = [Clause(evidence_id=uuid.uuid4(), content=s.content,
                      section_number=s.section_number, section_title=s.section_title,
                      is_heading=bool((s.metadata or {}).get("heading")))
               for s in parsed.segments if (s.metadata or {}).get("part") is None]
    return [Problem("CROSS_REFERENCE", o["text"])
            for o in consistency.observe(clauses)["additional"]]


def _pdf(docx_body: etree._Element, pdf: bytes) -> list[Problem]:
    import pymupdf
    margins = render_contract.house()["page"]["margin_mm"]
    margin = margins["right"] * 72 / 25.4
    out = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pages = [_norm(page.get_text()) for page in doc]
        # the body between the top and bottom margins (header and footer sit outside,
        # with a line's allowance), read as one text: a paragraph may cross a page
        body = _norm(" ".join(page.get_text(clip=pymupdf.Rect(
            0, margins["top"] * 72 / 25.4 - 6, page.rect.width,
            page.rect.height - margins["bottom"] * 72 / 25.4 + 6)) for page in doc))
        for n, page in enumerate(doc, 1):        # no printed glyph past the right margin
            edge = page.rect.width - margin + MARGIN_TOLERANCE_PT
            over = [line for block in page.get_text("rawdict")["blocks"]
                    for line in block.get("lines", [])
                    if any(c["bbox"][2] > edge and c["c"].strip()
                           for span in line["spans"] for c in span["chars"])]
            if over:
                out.append(Problem("MARGIN", f"page {n}: {len(over)} line(s) run past "
                                   "the right margin"))
    for sdt in docx_body.iter(_W + "sdt"):
        tag = sdt.find(f"{_W}sdtPr/{_W}tag")
        if tag is not None and tag.get(_W + "val") == "lm:execution":
            block = _norm(" ".join(_docx_text(p) for p in sdt.iter(_W + "p")))
            if not any(block in page for page in pages):
                out.append(Problem("EXECUTION_SPLIT", "the execution block does not sit "
                                   "on one page"))
        if tag is not None and tag.get(_W + "val") == SPECIAL:
            out += _new_page(sdt, pages)
    # the PDF's text layer puts a space between a run-in title's run and the “:” after
    # it ("Payment : All"); only the words and numbers are compared, not that spacing
    whole = _TIGHT.sub("", body)
    for p in docx_body.iter(_W + "p"):
        refs = [f for f in p.iter(_W + "fldSimple")
                if _REF.search(f.get(_W + "instr", ""))]
        text = _norm(_docx_text(p))
        if refs and _TIGHT.sub("", text) not in whole:
            out.append(Problem("XREF_PDF", f"“{text[:80]}” reads differently in the PDF"))
    section: list[int] = []
    for page in pages:
        m = _PAGE.search(page)
        if not m:
            continue
        if int(m.group(1)) == 1 and section:
            out += _page_run(section)
            section = []
        section.append(int(m.group(1)))
    return out + _page_run(section)


def _new_page(sdt: etree._Element, pages: list[str]) -> list[Problem]:
    """`AM-307` R-5: the Special Conditions begin on a page of their own — the page
    holding their opening holds nothing of the text just before them."""
    texts = [_norm(_docx_text(p)) for p in sdt.iter(_W + "p")]
    first = next((t[:60] for t in texts[1:] if t), "")      # the opening, not the title
    before = sdt.xpath("preceding::w:p", namespaces={"w": _W[1:-1]})
    prior = next((t for t in (_norm(_docx_text(p)) for p in reversed(before)) if t), "")
    at = next((i for i, page in enumerate(pages) if first and first in page), None)
    if at is None or (prior and prior[-40:] in pages[at].split(first)[0]):
        return [Problem("SC_NEW_PAGE", "the Special Conditions do not start on a new "
                        "page")]
    return []


def _page_run(section: list[int]) -> list[Problem]:
    if section != list(range(1, len(section) + 1)):
        return [Problem("PAGE_NUMBERS", f"pages read {section}, a section of "
                        f"{len(section)} pages")]
    return []


def check(docx_bytes: bytes, *, model: Mapping[str, Any] | None = None,
          pdf: bytes | None = None, clean_copy: bool = True) -> list[Problem]:
    """Every problem with this file, or ``[]``."""
    out: list[Problem] = []
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        parts = _parts(z)
        body = parts["word/document.xml"]
        stories = {n: r for n, r in parts.items()
                   if _STORY.match(n)}
        bookmarks = {b.get(_W + "name") for r in stories.values()
                     for b in r.iter(_W + "bookmarkStart")}
        codes = [f.get(_W + "instr", "") for r in stories.values()
                 for f in r.iter(_W + "fldSimple")]
        codes += ["".join(t.text or "" for t in r.iter(_W + "instrText"))
                  for r in stories.values()]
        for code in codes:
            for m in _REF.finditer(code):
                if m.group(1) not in bookmarks:
                    out.append(Problem("REF_NO_BOOKMARK", f"a cross-reference names "
                                       f"{m.group(1)}, which no bookmark carries"))
        for name, root in stories.items():
            for p in root.iter(_W + "p"):
                text = _docx_text(p)
                if _BLANK.search(text):
                    out.append(Problem("BLANK", f"{name}: “{_norm(text)[:80]}” has a "
                                       "slot or blank left"))
        for rels in (n for n in z.namelist() if n.endswith(".rels")):
            for rel in etree.fromstring(z.read(rels)):
                if rel.get("TargetMode") == "External":
                    out.append(Problem("EXTERNAL_RELATIONSHIP",
                                       f"{rels} links {rel.get('Target')}"))
        out += _images(z, stories, render_contract.house()["min_image_dpi"])
    if clean_copy:
        out += [Problem("MARKUP", m) for m in clean.has_markup(docx_bytes)]
    roles = {p["role"] for p in (model or {}).get("parties", [])}
    out += _defined_terms(body, roles, set(((model or {}).get("special_conditions")
                                            or {}).get("headings", [])))
    out += _consistency(docx_bytes)
    if model is not None:
        out += _numbering(docx_bytes, model)
    if pdf is not None:
        out += _pdf(body, pdf)
    return out


def pdf_problems(docx_bytes: bytes, pdf: bytes) -> list[Problem]:
    """Only the PDF checks of `check` — for the worker's client PDF (`AM-293` r2), whose
    DOCX already passed every other check when it was created."""
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        return _pdf(parse_xml(z.read("word/document.xml")), pdf)


def require(docx_bytes: bytes, **kwargs: Any) -> None:
    problems = check(docx_bytes, **kwargs)
    if problems:
        raise PreflightRefused(problems)
