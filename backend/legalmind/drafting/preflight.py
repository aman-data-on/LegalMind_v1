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
embedded file, encryption or optional content · at most `MAX_PDF_BYTES`. And
against the DOCX (`_pdf`): the execution block sits on one page — and, where the
template puts it last, opens the last page (`SIGNATURE_PAGE`) · each paragraph holding a
cross-reference reads in the PDF exactly as its cached DOCX text · the whole body reads as
the DOCX does (`TEXT_EQUAL`) · and on OUR layout only: no glyph runs past the right margin
· the footers read "Page 1 of N" … "Page N of N" once each (a pre-S1 file: 1, 2 … per
section).
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
from legalmind.drafting.model import EMAIL, defined_terms
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
#: where a line may break with no space in the text: after a hyphen, dash or slash and
#: before an em dash ("quasi-" | "governmental" reads "quasi- governmental" in a PDF)
_BREAK = re.compile(r"(?<=[-\u2010\u2013\u2014/])\s+|\s+(?=\u2014)")
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
#: the pre-S1 footer (renderer 2): the document ID, then a bare page number, restarting
#: in each schedule — a version made before S1 keeps its file, so its rule (H1)
_OLD_PAGE = re.compile(_DOC_ID + r"\s+(\d+)\b")
#: a name no signing input may carry — as a dictionary key or a type, in any object of
#: the PDF; matched on the object's source with its string literals taken out, so a
#: link's URI ".../JS/..." is not JavaScript
_FORBIDDEN = {"ACROFORM": re.compile(r"/AcroForm\b"),
              "JAVASCRIPT": re.compile(r"/(?:JavaScript|JS)\b"),
              "EMBEDDED_FILE": re.compile(r"/(?:EmbeddedFiles?|EF)\b"),
              "OPTIONAL_CONTENT": re.compile(r"/OCProperties\b|/Type\s*/OCG\b"),
              "LAUNCH": re.compile(r"/Launch\b")}
#: what of `pdf_file` a client's own PDF may not carry into a final copy (`M2`): what
#: a signing tool refuses or a signer cannot see. Not PDF/A or fonts: we do not convert
#: the client's PDF, and nearly none is PDF/A.
CLIENT_PDF = {"ANNOTATION": "contains comments or other annotations",
              "ACROFORM": "contains form fields", "JAVASCRIPT": "contains JavaScript",
              "EMBEDDED_FILE": "contains attached files",
              "ENCRYPTED": "is password-protected or restricted",
              "OPTIONAL_CONTENT": "contains hidden layers",
              "PDF_TOO_LARGE": "is larger than 10 MB",
              "LAUNCH": "contains an action that opens another file or program",
              "OPEN_ACTION": "does something when it is opened, beyond showing a page",
              "PDF_UNREADABLE": "cannot be opened"}
#: the check sets the worker records it ran (`pdf.render_version`)
FILE, TEXT, HOUSE = "pdf_file", "text_equal", "house_layout"
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


def _names(source: str) -> str:
    """A PDF object's source without its string literals — ``(…)`` with escapes and
    nesting, and ``<hex>`` — so what is left are its names, numbers and structure."""
    out, depth, i = [], 0, 0
    while i < len(source):
        c = source[i]
        if depth:
            depth += {"(": 1, ")": -1}.get(c, 0)
            i += 2 if c == "\\" else 1
            continue
        if c == "(":
            depth = 1
        else:
            out.append(c)
        i += 1
    return re.sub(r"(?<!<)<[0-9A-Fa-f\s]*>(?!>)", "", "".join(out))


def pdf_file(pdf: bytes) -> list[Problem]:
    """The checks on the PDF alone, for ANY file LibreOffice made (`FINAL-PACKAGE-SPEC`
    c1, e), and the client's own PDF a final copy is (`CLIENT_PDF`): what a signing
    tool or an archive must be able to trust."""
    import pymupdf
    out = []
    if len(pdf) > MAX_PDF_BYTES:
        out.append(Problem("PDF_TOO_LARGE", f"the PDF is {len(pdf) / 1e6:.1f} MB, over "
                           f"the {MAX_PDF_BYTES / 1e6:.0f} MB a signing tool accepts"))
    try:
        doc = pymupdf.open(stream=pdf, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError):
        return [*out, Problem("PDF_UNREADABLE", "the file is not a PDF that opens")]
    try:
        with doc:
            return out + _inspect(doc)
    except (ValueError, RuntimeError):           # a damaged xref, an object that breaks
        return [*out, Problem("PDF_UNREADABLE", "the file is not a PDF that opens")]


#: an open action that only shows a page: a GoTo to a destination array, either order
_GOTO = re.compile(r"<<\s*/S\s*/GoTo\s*/D\s*\[[^\]]*\]\s*>>"
                   r"|<<\s*/D\s*\[[^\]]*\]\s*/S\s*/GoTo\s*>>")


def _open_action(doc: Any) -> str | None:
    """The catalog's /OpenAction may only show a page: none, a destination array (as
    LibreOffice 24.2 writes, "[page /XYZ …]"), or a GoTo action to one. Anything else
    (URI, Launch, JavaScript, SubmitForm, GoToR …) runs on opening — refused. JavaScript
    and Launch anywhere are also caught by `_FORBIDDEN`."""
    kind, value = doc.xref_get_key(doc.pdf_catalog(), "OpenAction")
    if kind in ("null", "array"):
        return None
    source = doc.xref_object(int(value.split()[0])) if kind == "xref" else value
    if kind in ("xref", "dict") and _GOTO.fullmatch(" ".join(source.split())):
        return None
    return "the PDF runs an action when it is opened, beyond showing a page"


def _inspect(doc: Any) -> list[Problem]:
    """`pdf_file` on an opened document."""
    import pymupdf
    out = []
    if doc.needs_pass:                       # nothing else can be read
        return [Problem("ENCRYPTED", "the PDF needs a password to open")]
    if doc.metadata.get("encryption"):
        out.append(Problem("ENCRYPTED", "the PDF is encrypted or restricted"))
    xmp = doc.get_xml_metadata()
    part = re.search(r"pdfaid:part(?:>|=\")\s*(\d)", xmp)
    conformance = re.search(r"pdfaid:conformance(?:>|=\")\s*(\w)", xmp)
    intents = doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")
    if (part and part[1], conformance and conformance[1].upper()) != ("2", "B"):
        out.append(Problem("PDFA", "the PDF does not identify itself as PDF/A-2b"))
    if intents[0] != "array" or not intents[1].strip("[] "):
        out.append(Problem("PDFA", "the PDF has no output intent (PDF/A colour)"))
    names = [_names(doc.xref_object(x)) for x in range(1, doc.xref_length())]
    found = {code for source in names for code, key in _FORBIDDEN.items()
             if key.search(source)}
    out += [Problem(code, f"the PDF carries {code.lower().replace('_', ' ')}")
            for code in sorted(found)]
    if (why := _open_action(doc)) is not None:
        out.append(Problem("OPEN_ACTION", why))
    loose: set[str] = set()
    for n, page in enumerate(doc.pages(), 1):
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


def _label(n: int, fmt: str) -> str:
    """One list level's counter as Word prints it (the template library's letters and
    numerals): none prints nothing; a bullet has no counter, its glyph is its text."""
    from legalmind.drafting.library import _ROMAN, _letter  # it imports publish → us
    if fmt in ("lowerLetter", "upperLetter"):
        return _letter(n - 1).upper() if fmt == "upperLetter" else _letter(n - 1)
    if fmt in ("lowerRoman", "upperRoman") and n <= len(_ROMAN):
        return _ROMAN[n - 1].upper() if fmt == "upperRoman" else _ROMAN[n - 1]
    return "" if fmt == "none" else str(n)  # ponytail: roman past xx prints its number


def _capitals(document: Any) -> Any:
    """A test on a ``w:r``: is it printed in capitals by its formatting — ``w:caps`` or
    ``w:smallCaps``, set on the run, its character style or its paragraph's style
    (through ``w:basedOn``)? Capitals typed as capitals need no test."""
    styles = {st.get(_W + "styleId"): st
              for st in document.styles.element.iter(_W + "style")}

    def caps(rpr: Any) -> bool | None:
        for tag in ("caps", "smallCaps"):
            el = rpr.find(_W + tag) if rpr is not None else None
            if el is not None:
                return el.get(_W + "val", "true") not in ("0", "false", "off")
        return None

    def styled(style_id: str | None) -> bool | None:
        seen = set()
        while style_id in styles and style_id not in seen:
            seen.add(style_id)
            if (got := caps(styles[style_id].find(_W + "rPr"))) is not None:
                return got
            based = styles[style_id].find(_W + "basedOn")
            style_id = based.get(_W + "val") if based is not None else None
        return None

    def test(r: Any) -> bool:
        rpr = r.find(_W + "rPr")
        rstyle = rpr.find(_W + "rStyle") if rpr is not None else None
        p = next(r.iterancestors(_W + "p"), None)
        pstyle = p.find(f"{_W}pPr/{_W}pStyle") if p is not None else None
        for got in (caps(rpr), styled(rstyle.get(_W + "val") if rstyle is not None
                                      else None),
                    styled(pstyle.get(_W + "val") if pstyle is not None else None)):
            if got is not None:
                return got
        return False
    return test


def _words(text: str) -> str:
    """``text`` compared as printed words: NFKC (a ligature is its letters), every run
    of spaces one space, no space before punctuation (the PDF's "Payment : All"). Case
    and word boundaries count: "shall not" is not "shallnot" — only where a line may
    break without a space (`_BREAK`) is a space not a word boundary."""
    return _BREAK.sub("", _TIGHT.sub("", _norm(unicodedata.normalize("NFKC", text))))


def _text_equal(document: Any, pdf_body: str) -> list[Problem]:
    """`TEXT_EQUAL`: the DOCX body — every paragraph in order, tables included, each
    after the list label Word prints, in capitals where its formatting prints them —
    reads as the PDF body does; the first place it does not is quoted from both."""
    paragraphs = document.element.body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    labels = _docx_list_numbers(document, paragraphs, labels=_label)
    upper = _capitals(document)
    want = _words(" ".join(f"{labels.get(p, '')} {_docx_text(p, upper=upper)}"
                           for p in paragraphs))
    got = _words(pdf_body)
    if want == got:
        return []
    k = next((i for i, (a, b) in enumerate(zip(want, got, strict=False)) if a != b),
             min(len(want), len(got)))

    def at(text: str) -> str:
        return text[max(0, k - 40):k + 40] or "(nothing)"
    return [Problem("TEXT_EQUAL", f"the PDF reads “…{at(got)}…” where the Word file "
                    f"reads “…{at(want)}…”")]


def _page_numbers(docx_bytes: bytes, pages: list[str]) -> list[Problem]:
    """The footers our renderer wrote. With a ``NUMPAGES`` field (S1 on): "Page 1 of
    N" … "Page N of N", once each, N the page count. Without (a version made before
    S1, H1): the document ID and a bare number, 1, 2, 3 … in each section."""
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        totals = any(b"NUMPAGES" in z.read(n) for n in z.namelist()
                     if re.fullmatch(r"word/footer\d*\.xml", n))
    if totals:
        read = [(int(m[1]), int(m[2])) if (m := _PAGE.search(page)) else None
                for page in pages]
        if read != [(n, len(pages)) for n in range(1, len(pages) + 1)]:
            shown = [f"{r[0]} of {r[1]}" if r else "no number" for r in read]
            return [Problem("PAGE_NUMBERS", f"pages read {shown}, a file of "
                            f"{len(pages)} pages")]
        return []
    runs: list[list[int]] = []
    for page in pages:
        if m := _OLD_PAGE.search(page):
            if int(m[1]) == 1 or not runs:
                runs.append([])
            runs[-1].append(int(m[1]))
    return [Problem("PAGE_NUMBERS", f"pages read {run}, a section of {len(run)} pages")
            for run in runs if run != list(range(1, len(run) + 1))]


def _pdf(docx_bytes: bytes, pdf: bytes, *, ours: bool,
         signature_last: bool = False) -> list[Problem]:
    """The checks of the PDF against its DOCX: its text (`TEXT_EQUAL`, the body between
    the DOCX's own top and bottom margins), its execution block, its cross-references;
    and, on OUR layout only (``ours``), the house right margin and our page footers;
    where the template puts the signatures last (``signature_last``), the execution
    block opens the last page (`SIGNATURE_PAGE`)."""
    import docx
    import pymupdf
    document = docx.Document(io.BytesIO(docx_bytes))
    docx_body = document.element.body
    # ponytail: the body section's margins (the last w:sectPr) clip every page — a file
    # whose sections differ fails closed (TEXT_EQUAL); clip per section if one must pass
    section = document.sections[-1]
    top, bottom = (abs(m.pt) if m is not None else 72.0
                   for m in (section.top_margin, section.bottom_margin))
    margin = render_contract.house()["page"]["margin_mm"]["right"] * 72 / 25.4
    out = []
    # S2: the Word file's email addresses, each read whole where the PDF broke it over
    # two lines (a narrow cell, no space to break at) — only these exact strings
    emails = sorted({e for p in docx_body.iter(_W + "p")
                     for e in EMAIL.findall(_docx_text(p))}, key=len, reverse=True)
    heals = [(re.compile(r"\s*".join(map(re.escape, e))), e) for e in emails]

    def heal(text: str) -> str:
        for pattern, email in heals:
            text = pattern.sub(email, text)
        return _norm(text)
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pages = [heal(page.get_text()) for page in doc]
        # the body between the top and bottom margins (header and footer sit outside,
        # with a line's allowance), read as one text: a paragraph may cross a page
        bodies = [heal(page.get_text(clip=pymupdf.Rect(
            0, top - 6, page.rect.width, page.rect.height - bottom + 6))) for page in doc]
        body = _norm(" ".join(bodies))
        for n, page in enumerate(doc if ours else [], 1):   # no glyph past our margin
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
            if signature_last and not (bodies and _words(bodies[-1]).startswith(
                    _words(block))):
                out.append(Problem("SIGNATURE_PAGE", "the signature page is not the "
                                   "last page, or does not start at the top of it"))
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
    return out + (_page_numbers(docx_bytes, pages) if ours else [])


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
        out += pdf_problems(docx_bytes, pdf, ours=True, signature_last=bool(
            (model or {}).get("execution", {}).get("last")))
    return out


def pdf_checks(ours: bool) -> list[str]:
    """The check sets `pdf_problems` runs, as the worker records them."""
    return [FILE, TEXT, HOUSE] if ours else [FILE, TEXT]


def pdf_problems(docx_bytes: bytes, pdf: bytes, *, ours: bool,
                 signature_last: bool = False) -> list[Problem]:
    """Only the PDF checks of `check` — for the worker's client PDF (`AM-293` r2), whose
    DOCX already passed every other check when it was created. ``ours`` is PROVENANCE,
    never read from the file: we generated it (a ``ContractDraft`` row), so it is on the
    house layout and our footers are checked; else it is paper (the client's, or ours as
    the client returned it), checked as a file and for its text (`pdf_checks`).
    ``signature_last``: the template puts the signature page last (S2), read by the
    caller from the template — `SIGNATURE_PAGE` runs on our layout only."""
    file = pdf_file(pdf)
    if any(p.code in ("ENCRYPTED", "PDF_UNREADABLE") for p in file):  # nothing to read
        return file
    return file + _pdf(docx_bytes, pdf, ours=ours, signature_last=ours and signature_last)


def require(docx_bytes: bytes, **kwargs: Any) -> None:
    problems = check(docx_bytes, **kwargs)
    if problems:
        raise PreflightRefused(problems)
