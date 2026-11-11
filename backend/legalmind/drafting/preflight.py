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
With the PDF too (`pdf_file`, any file the worker makes): PDF/A-2b identified, with an
OutputIntent · every font embedded · no annotation but a link · no form, JavaScript,
embedded file, encryption or optional content · at most `MAX_PDF_BYTES`. And on our house
layout (`_pdf`): the execution block sits on one page · each paragraph holding a
cross-reference reads in the PDF exactly as its cached DOCX text · the whole body reads as
the DOCX does (`TEXT_EQUAL`) · no glyph runs past the right margin · the footers read
"Page 1 of N" … "Page N of N", once each, N the page count.
"""

from __future__ import annotations

import io
import re
import unicodedata
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
#: how far a glyph may sit past the right margin (PDF points) before the page fails
MARGIN_TOLERANCE_PT = 0.5
#: the e-signing tools' lowest per-file limit (Adobe, 10 MB), read as decimal: stricter
MAX_PDF_BYTES = 10_000_000
#: the house footer: the document ID, then "Page x of y" (`render_contract.furniture`)
_DOC_ID = r"\bLM-\S+-v\d+-[0-9a-f]{8}"
_PAGE = re.compile(_DOC_ID + r"\s+" + re.sub(r"(\\ )+", r"\\s*", re.escape(
    render_contract.house()["footer"]["page_format"])).replace(
    r"\{PAGE\}", r"(\d+)").replace(r"\{NUMPAGES\}", r"(\d+)"))
#: a dictionary key no signing input may carry, in any object of the PDF
_FORBIDDEN = {"ACROFORM": re.compile(r"/AcroForm\b"),
              "JAVASCRIPT": re.compile(r"/(?:JavaScript|JS)\b"),
              "EMBEDDED_FILE": re.compile(r"/EmbeddedFiles?\b"),
              "OPTIONAL_CONTENT": re.compile(r"/OCProperties\b|/Type\s*/OCG\b")}
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


def pdf_file(pdf: bytes) -> list[Problem]:
    """The checks on the PDF alone, for ANY file LibreOffice made (`FINAL-PACKAGE-SPEC`
    c1, e): what a signing tool or an archive must be able to trust."""
    import pymupdf
    out = []
    if len(pdf) > MAX_PDF_BYTES:
        out.append(Problem("PDF_TOO_LARGE", f"the PDF is {len(pdf) / 1e6:.1f} MB, over "
                           f"the {MAX_PDF_BYTES / 1e6:.0f} MB a signing tool accepts"))
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        if doc.needs_pass or doc.metadata.get("encryption"):
            out.append(Problem("ENCRYPTED", "the PDF is encrypted or restricted"))
        xmp = doc.get_xml_metadata()
        part = re.search(r"pdfaid:part(?:>|=\")\s*(\d)", xmp)
        conformance = re.search(r"pdfaid:conformance(?:>|=\")\s*(\w)", xmp)
        intents = doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")
        if (part and part[1], conformance and conformance[1].upper()) != ("2", "B"):
            out.append(Problem("PDFA", "the PDF does not identify itself as PDF/A-2b"))
        if intents[0] != "array" or not intents[1].strip("[] "):
            out.append(Problem("PDFA", "the PDF has no output intent (PDF/A colour)"))
        found = {code for x in range(1, doc.xref_length())
                 for code, key in _FORBIDDEN.items() if key.search(doc.xref_object(x))}
        out += [Problem(code, f"the PDF carries {code.lower().replace('_', ' ')}")
                for code in sorted(found)]
        loose: set[str] = set()
        for n, page in enumerate(doc, 1):
            kinds = sorted({t[1] for t in page.annot_xrefs()
                            if t[1] != pymupdf.mupdf.PDF_ANNOT_LINK})
            if kinds:
                out.append(Problem("ANNOTATION", f"page {n} has an annotation that is "
                                   f"not a link ({', '.join(map(str, kinds))})"))
            loose |= {f[3] for f in page.get_fonts(full=True)
                      if f[1] == "n/a" and f[2] != "Type3"}
        if loose:
            out.append(Problem("FONT_NOT_EMBEDDED", "fonts not embedded: "
                               + ", ".join(sorted(loose))))
    return out


def _flat(text: str) -> tuple[str, list[int], str]:
    """``text`` compared as words, not as layout: NFKC (a ligature is its letters),
    casefolded (a heading's capitals are its style), every space dropped (a justified
    line, a tab after a number, a space before a colon). With the index of each kept
    character in the readable text, to quote a mismatch."""
    readable = _norm(unicodedata.normalize("NFKC", text).casefold())
    keep = [i for i, c in enumerate(readable) if not c.isspace()]
    return "".join(readable[i] for i in keep), keep, readable


def _text_equal(document: Any, pdf_body: str) -> list[Problem]:
    """`TEXT_EQUAL`: the DOCX body — every paragraph in order, tables included, each
    after the list label Word prints — reads as the PDF body does; the first place it
    does not is quoted from both."""
    paragraphs = document.element.body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    labels = _docx_list_numbers(document, paragraphs, labels=True)
    want = _flat(" ".join(f"{labels.get(p, '')} {_docx_text(p)}" for p in paragraphs))
    got = _flat(pdf_body)
    if want[0] == got[0]:
        return []
    k = next((i for i, (a, b) in enumerate(zip(want[0], got[0], strict=False))
              if a != b), min(len(want[0]), len(got[0])))

    def at(side: tuple[str, list[int], str]) -> str:
        i = side[1][k] if k < len(side[1]) else len(side[2])
        return side[2][max(0, i - 40):i + 40] or "(nothing)"
    return [Problem("TEXT_EQUAL", f"the PDF reads “…{at(got)}…” where the Word file "
                    f"reads “…{at(want)}…”")]


def _pdf(docx_bytes: bytes, pdf: bytes) -> list[Problem]:
    """The checks of the PDF against its DOCX, on the house layout (its margins and
    footer)."""
    import docx
    import pymupdf
    document = docx.Document(io.BytesIO(docx_bytes))
    docx_body = document.element.body
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
    out += _text_equal(document, body)
    # the PDF's text layer puts a space between a run-in title's run and the “:” after
    # it ("Payment : All"); only the words and numbers are compared, not that spacing
    whole = _TIGHT.sub("", body)
    for p in docx_body.iter(_W + "p"):
        refs = [f for f in p.iter(_W + "fldSimple")
                if _REF.search(f.get(_W + "instr", ""))]
        text = _norm(_docx_text(p))
        if refs and _TIGHT.sub("", text) not in whole:
            out.append(Problem("XREF_PDF", f"“{text[:80]}” reads differently in the PDF"))
    read = [(int(m[1]), int(m[2])) if (m := _PAGE.search(page)) else None
            for page in pages]
    if read != [(n, len(pages)) for n in range(1, len(pages) + 1)]:
        shown = [f"{r[0]} of {r[1]}" if r else "no number" for r in read]
        out.append(Problem("PAGE_NUMBERS", f"pages read {shown}, a file of "
                           f"{len(pages)} pages"))
    return out


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
        out += pdf_file(pdf) + _pdf(docx_bytes, pdf)
    return out


def pdf_problems(docx_bytes: bytes, pdf: bytes) -> list[Problem]:
    """Only the PDF checks of `check` — for the worker's client PDF (`AM-293` r2), whose
    DOCX already passed every other check when it was created. Every file gets
    `pdf_file`; the layout checks need OUR layout, so they run where a footer carries our
    document ID — a final copy of the client's own paper has neither our margins nor our
    footer."""
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        ours = any(re.search(_DOC_ID, z.read(n).decode("utf-8", "replace"))
                   for n in z.namelist() if re.fullmatch(r"word/footer\d*\.xml", n))
    return pdf_file(pdf) + (_pdf(docx_bytes, pdf) if ours else [])


def require(docx_bytes: bytes, **kwargs: Any) -> None:
    problems = check(docx_bytes, **kwargs)
    if problems:
        raise PreflightRefused(problems)
