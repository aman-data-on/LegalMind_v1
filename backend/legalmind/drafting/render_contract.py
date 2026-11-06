"""The canonical contract model (`drafting.model`) → a DOCX on the house shell.

Word-native, so the file behaves in Word as the lawyer expects (ECMA-376 / MS-OI29500):

* **Numbering** — one multilevel ``w:abstractNum`` whose levels are linked to the styles
  ``LM Heading 1``–``5`` (``w:pStyle``); every numbered paragraph also carries its
  ``w:numPr``. Each schedule and each (a)/(b) list restarts through its OWN ``w:num`` with
  ``w:lvlOverride/w:startOverride`` — never by retyping numbers.
* **Cross-references** — the target paragraph is bookmarked and the reference is a
  ``REF _LM_<key> \\w \\h`` field whose cached result is the number we computed, so the
  file reads right before Word ever updates a field. No ``w:updateFields`` is set.
* **Sections** — each schedule is its own ``w:sectPr``: a new page, page numbers
  restarting at 1, its own header and footer. Footers read the document ID, small at
  the left (a signed copy traces back to its record), and the page number at the right,
  as the approved format sets it.
* **Content controls** — each clause sits in a ``w:sdt`` (unique ``w:id``, ``w:tag``
  ``lm:<key>@<version>``, ``w:lock sdtContentLocked``). The lock is ADVISORY: Word
  honours it, any editor can remove it. The real protection is server-side — a contract
  is always rebuilt from the template model, never from an edited file.
* Tables repeat their header row (``w:tblHeader``) and never split a row
  (``w:cantSplit``); images and the logo are EMBEDDED with alt text (``wp:docPr/@descr``),
  never linked; ``compatibilityMode`` 14 (`house_shell`); neutral ``core.xml``; the zip is
  written with fixed timestamps, so the same model gives the same bytes.

No text is composed here: every word comes from the model (rule 21, `AM-251` r1).
"""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import re
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import docx
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Mm, Pt, RGBColor, Twips

from legalmind.api.export_render import _field
from legalmind.drafting.model import text_of

RENDERER_VERSION = "lm-render-contract-2"
HOUSE_PATH = (Path(__file__).resolve().parents[2] / "config" / "templates" / "house"
              / "house.json")
#: numbering ids: the clause list, the recitals, and the first restart instance
_CLAUSES, _RECITALS, _LISTS = 10, 11, 12
#: the Special Conditions entries 1., 2. … (`AM-307`) — defined only where used, so a
#: contract without them keeps its bytes
_ENTRIES = 13
_TAG_MAX = 64
_BOOKMARK_MAX = 40
_FIXED = datetime(2001, 1, 1, tzinfo=UTC)          # neutral core.xml timestamps
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class RenderError(ValueError):
    pass


@lru_cache(maxsize=1)
def house() -> dict[str, Any]:
    return json.loads(HOUSE_PATH.read_text(encoding="utf-8"))


def bookmark(key: str) -> str:
    """Word's bookmark name for a clause key: ≤ 40 characters, letters/digits/_ only,
    hidden (leading underscore)."""
    name = "_LM_" + re.sub(r"\W", "_", key)
    return name if len(name) <= _BOOKMARK_MAX else "_LM_" + hashlib.sha256(
        key.encode()).hexdigest()[:20]


def doc_id(contract_ref: str, version_number: int, model_hash: str) -> str:
    return f"LM-{contract_ref}-v{version_number}-{model_hash[:8]}"


#: a quoted term — double or single curly quotes — and the defining term(s) a numbered
#: definition opens on
_Q_OPEN, _Q_CLOSE = "\u201c\u2018", "\u201d\u2019"
_QUOTED = re.compile(rf"[{_Q_OPEN}]([^{_Q_CLOSE}]{{1,80}})[{_Q_CLOSE}]")
_TERM = rf"[{_Q_OPEN}][^{_Q_CLOSE}]{{1,80}}[{_Q_CLOSE}]"
#: a term may carry its short form: “Service Level Agreement” (“SLA”) shall mean
_DEFINING = re.compile(rf"^((?:{_TERM}\s*(?:\(\s*{_TERM}\s*\)\s*)?(?:,|or|and)?\s*)+)"
                       r"(?=shall mean|means\b|shall have the meaning|has the meaning)")
#: a capitalised run-in opening a front paragraph ("NOW THEREFORE,", "IN WITNESS WHEREOF")
_LEAD_IN = re.compile(r"^[A-Z][A-Z ]*[A-Z],?(?=\s)")


def emphasis(runs: list[dict], *, terms: str | None = None) -> list[dict]:
    """The approved format's weight, applied to the model's own words: ``terms="all"``
    bolds every quoted term (front matter), ``"defining"`` the term(s) a paragraph opens
    on when it defines them (“Affiliate” shall mean …), ``None`` the capitalised
    run-in."""
    out: list[dict] = []
    for i, r in enumerate(runs):
        text = r.get("t")
        if text is None or (i and terms != "all"):
            out.append(r)
        elif terms is None:
            m = _LEAD_IN.match(text)
            out += [{**r, "t": m.group(0), "b": True}, {**r, "t": text[m.end():]}] \
                if m else [r]
        else:
            m = _DEFINING.match(text) if terms == "defining" else None
            end = len(text) if terms == "all" else m.end(1) if m else 0
            pos = 0
            for q in _QUOTED.finditer(text, 0, end):
                out += [{**r, "t": text[pos:q.start(1)]},
                        {**r, "t": q.group(1), "b": True}]
                pos = q.end(1)
            out.append({**r, "t": text[pos:]})
    return [x for x in out if x.get("t") != ""]


# ---------------------------------------------------------------- the shell
def _numbering_xml(restarts: list[tuple[int, int]]) -> str:
    """The numbering part: the clause list L1–L5 linked to the heading styles, the
    recitals (A), (B) …, the (a), (b) item list, and one ``w:num`` per restart."""
    h = house()
    ladder, suffix = h["clause_ladder_twips"], h["number_suffix"]
    # the number right-aligned at its position and never bold, even on a bold heading
    levels = "".join(
        f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="decimal"/>'
        f'<w:pStyle w:val="LMHeading{i + 1}"/><w:suff w:val="tab"/>'
        f'<w:lvlText w:val="{".".join(f"%{j + 1}" for j in range(i + 1))}{suffix}"/>'
        f'<w:lvlJc w:val="right"/><w:pPr><w:ind w:left="{text}" '
        f'w:hanging="{text - number}"/></w:pPr><w:rPr><w:b w:val="0"/></w:rPr></w:lvl>'
        for i, (number, text) in enumerate(ladder))

    def single(abstract: int, fmt: str, text: str, left: int, hang: int) -> str:
        return (f'<w:abstractNum w:abstractNumId="{abstract}"><w:multiLevelType '
                f'w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/>'
                f'<w:numFmt w:val="{fmt}"/><w:lvlText w:val="{text}"/><w:lvlJc '
                f'w:val="left"/><w:pPr><w:ind w:left="{left}" w:hanging="{hang}"/>'
                f'</w:pPr><w:rPr><w:b w:val="0"/></w:rPr></w:lvl></w:abstractNum>')
    party_left, party_hang = h["party_twips"]
    list_left = ladder[0][1] + sum(h["list_twips"])
    nums = "".join(f'<w:num w:numId="{n}"><w:abstractNumId w:val="{a}"/></w:num>'
                   for n, a in ((1, _CLAUSES), (2, _RECITALS)))
    nums += "".join(f'<w:num w:numId="{n}"><w:abstractNumId w:val="{a}"/><w:lvlOverride '
                    f'w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
                    for n, a in restarts)
    number, text = ladder[0]
    entries = (single(_ENTRIES, "decimal", "%1.", text, text - number)
               if any(a == _ENTRIES for _, a in restarts) else "")
    return (f'<w:numbering {nsdecls("w")}><w:abstractNum w:abstractNumId="{_CLAUSES}">'
            f'<w:multiLevelType w:val="multilevel"/>{levels}</w:abstractNum>'
            f'{single(_RECITALS, "upperLetter", "%1.", party_left, party_hang)}'
            f'{single(_LISTS, "lowerLetter", "(%1)", list_left, h["list_twips"][1])}'
            f'{entries}{nums}</w:numbering>')


def _spacing(fmt: Any, spacing: list[float]) -> None:
    fmt.space_before, fmt.space_after = (Pt(v) for v in spacing)


def _style(doc: Any, name: str, *, size: float | None = None, bold: bool = False,
           keep_next: bool = False, numbered: int | None = None,
           align: Any = None, left: int | None = None, caps: bool = False,
           spacing: list[float] | None = None) -> None:
    style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = doc.styles["Normal"]
    style.font.bold = bold
    style.font.all_caps = caps or None
    if size:
        style.font.size = Pt(size)
    fmt = style.paragraph_format
    fmt.keep_with_next = keep_next
    if spacing:
        _spacing(fmt, spacing)
    if align is not None:
        fmt.alignment = align
    if left is not None:
        fmt.left_indent = Twips(left)
    if numbered is not None:                        # style ↔ level link
        ppr = style.element.get_or_add_pPr()
        ppr.insert(0, parse_xml(f'<w:numPr {nsdecls("w")}>'
                                + (f'<w:ilvl w:val="{numbered}"/>' if numbered else "")
                                + '<w:numId w:val="1"/></w:numPr>'))


def text_width_twips() -> int:
    page = house()["page"]
    return round((page["width_mm"] - page["margin_mm"]["left"]
                  - page["margin_mm"]["right"]) * 1440 / 25.4)


def house_shell() -> Any:
    """The house shell, built from ``config/templates/house/house.json`` — styles,
    page, numbering and settings, no text. Built rather than stored, so the shell is
    reviewable as code and its bytes cannot drift from the style values."""
    h = house()
    doc = docx.Document()
    body = doc.element.body
    for p in body.findall(qn("w:p")):
        body.remove(p)
    normal = doc.styles["Normal"]
    normal.font.name = h["font"]
    normal.font.size = Pt(h["font_size_pt"])
    rfonts = normal.element.get_or_add_rPr().get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), h["font"])
    spacing, caps = h["spacing_pt"], h["caps"]
    _spacing(normal.paragraph_format, spacing["normal"])
    normal.paragraph_format.line_spacing = h["line_spacing"]
    normal.paragraph_format.widow_control = True
    if h["justify"]:
        normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    ladder, front = h["clause_ladder_twips"], spacing["front"]
    _style(doc, "LM Title", size=h["title_size_pt"], bold=True, caps=caps["title"],
           align=WD_ALIGN_PARAGRAPH.CENTER, spacing=front)
    _style(doc, "LM Front", spacing=front)
    _style(doc, "LM Connector", bold=True, keep_next=True, left=h["party_twips"][0],
           spacing=front)
    _style(doc, "LM Plain Heading", size=h["heading_size_pt"], bold=True, keep_next=True,
           spacing=front)
    for i in range(5):
        _style(doc, f"LM Heading {i + 1}", bold=i == 0, keep_next=i == 0, numbered=i,
               caps=i == 0 and caps["heading1"],
               spacing=spacing["heading1"] if i == 0 else None)
        _style(doc, f"LM Body {i + 1}", left=ladder[i][1])
    _style(doc, "LM List", left=ladder[0][1] + sum(h["list_twips"]))
    _style(doc, "LM Recital", left=h["party_twips"][0], spacing=front)
    _style(doc, "LM Schedule Title", size=h["title_size_pt"], bold=True,
           caps=caps["title"], align=WD_ALIGN_PARAGRAPH.CENTER, keep_next=True,
           spacing=front)
    page, width = h["page"], text_width_twips()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(page["width_mm"]), Mm(page["height_mm"])
    for side, mm in page["margin_mm"].items():
        setattr(section, f"{side}_margin", Mm(mm))
    section.header_distance = Mm(page["header_mm"])
    section.footer_distance = Mm(page["footer_mm"])
    for name in ("Header", "Footer"):          # the default template's tabs are Letter's
        fmt = doc.styles[name].paragraph_format
        fmt.tab_stops.clear_all()
        fmt.tab_stops.add_tab_stop(Twips(width // 2), WD_TAB_ALIGNMENT.CENTER)
        fmt.tab_stops.add_tab_stop(Twips(width), WD_TAB_ALIGNMENT.RIGHT)
        fmt.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _spacing(fmt, [0, 0])
    footer = doc.styles["Footer"].font
    footer.name, footer.size = h["footer"]["font"], Pt(h["footer"]["size_pt"])
    settings = doc.settings.element
    for el in [*settings.findall(qn("w:updateFields")),
               *settings.findall(qn("w:trackRevisions"))]:
        settings.remove(el)
    for compat in settings.iter(qn("w:compatSetting")):
        if compat.get(qn("w:name")) == "compatibilityMode":
            # 14, not 15: in mode 15 LibreOffice shrinks a justified line's spaces to fit
            # one more word but paints the first line of a numbered paragraph (the one
            # holding the number's tab) unshrunk, so it runs 3-9 pt past the margin; in
            # 14 neither Word nor LibreOffice shrinks, and they break lines alike
            compat.set(qn("w:val"), "14")
    # a justified line ending in a line break is not stretched (Word and LibreOffice)
    settings.find(qn("w:compat")).insert(0, OxmlElement("w:doNotExpandShiftReturn"))
    return doc


# ---------------------------------------------------------------- building blocks
class _Builder:
    def __init__(self, model: Mapping[str, Any], assets: Mapping[str, Any]) -> None:
        self.doc = house_shell()
        self.body = self.doc.element.body
        self.model = model
        self.assets = assets
        self.restarts: list[tuple[int, int]] = []
        self.ids = 0                      # w:id for sdt and bookmarks — one sequence
        self.blank = False
        self.header_note: str | None = None
        #: a sub-clause number → the synthetic key a Special Condition names it by (an
        #: unkeyed sub-clause is bookmarked only when one does — `AM-307`)
        self.anchors: dict[str, str] = {}

    def next_id(self) -> int:
        self.ids += 1
        return self.ids

    def restart(self, abstract: int) -> int:
        num = 3 + len(self.restarts)
        self.restarts.append((num, abstract))
        return num

    def mark(self) -> int:
        """Where the next block lands: before the body's closing ``w:sectPr``."""
        return len(self.body) - 1

    def since(self, start: int) -> list[Any]:
        return [el for el in list(self.body)[start:] if el.tag != qn("w:sectPr")]

    def para(self, style: str, runs: list[dict] | None = None, *,
             num: tuple[int, int] | None = None, keep_next: bool = False,
             bookmark_key: str | None = None) -> Any:
        p = self.doc.add_paragraph(style=style)
        ppr = p._p.get_or_add_pPr()
        if num:
            ppr.append(parse_xml(f'<w:numPr {nsdecls("w")}><w:ilvl w:val="{num[1]}"/>'
                                 f'<w:numId w:val="{num[0]}"/></w:numPr>'))
        if keep_next:
            p.paragraph_format.keep_with_next = True
        if bookmark_key:
            bid = str(self.next_id())
            p._p.append(OxmlElement("w:bookmarkStart", {
                qn("w:id"): bid, qn("w:name"): bookmark(bookmark_key)}))
        self.runs(p, runs or [])
        if bookmark_key:
            p._p.append(OxmlElement("w:bookmarkEnd", {qn("w:id"): bid}))
        return p

    def runs(self, p: Any, runs: list[dict], *, bold: bool = False) -> None:
        for r in runs:
            if "t" in r:
                run = p.add_run(r["t"])
                run.bold = bold or r.get("b") or None
                run.underline = r.get("u") or None
                if r.get("ph"):        # a blank template's field: highlighted, so it
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW   # survives Docs
            else:
                _field(p, f" REF {bookmark(r['ref'])} \\w \\h ", cached=str(r["num"]))

    def sdt(self, start: int, tag: str) -> None:
        """Wrap everything added since ``start`` in one block content control — never on
        a blank template, which is filled outside LegalMind (a locked control would
        stop Word filling it)."""
        if self.blank:
            return
        if len(tag) > _TAG_MAX:
            raise RenderError(f"content-control tag over {_TAG_MAX} characters: {tag}")
        content = self.since(start)
        sdt = parse_xml(
            f'<w:sdt {nsdecls("w")}><w:sdtPr><w:alias w:val="{tag}"/>'
            f'<w:tag w:val="{tag}"/>'
            f'<w:id w:val="{self.next_id()}"/><w:lock w:val="sdtContentLocked"/>'
            f'</w:sdtPr><w:sdtContent/></w:sdt>')
        content[0].addprevious(sdt)
        holder = sdt.find(qn("w:sdtContent"))
        for el in content:
            holder.append(el)

    def picture(self, p: Any, name: str, width_cm: float, alt: str) -> None:
        asset = self.assets[name]
        data = base64.b64decode(asset["data_b64"])
        p.add_run().add_picture(io.BytesIO(data), width=Cm(width_cm))
        for pr in p._p.iter(qn("wp:docPr")):
            pr.set("descr", alt or asset.get("alt", ""))
            pr.set("name", name)

    # -- blocks
    def blocks(self, blocks: list[dict], level: int, num: int) -> None:
        for b in blocks:
            kind = b["kind"]
            if kind == "sub":
                runs = emphasis(b["runs"], terms="defining")
                if b.get("title"):              # the run-in title, as the file set it
                    mark = "b" if b.get("title_style") == "bold" else "u"
                    # the title's words carry the mark, never its colon or spacing
                    words = b["title"].rstrip(": \t")
                    runs = [{"t": words, mark: True},
                            *([{"t": b["title"][len(words):]}]
                              if b["title"] != words else []), *b["runs"]]
                self.para(f"LM Heading {b['level']}", runs,
                          num=(num, b["level"] - 1),
                          bookmark_key=b.get("key") or self.anchors.get(b["number"]),
                          # a title alone, or a lead-in to its own sub-clauses
                          keep_next=(bool(b.get("title")) and not b["runs"]) or (
                              bool(b["body"]) and text_of(b["runs"]).rstrip()
                              .endswith(":")))
                self.blocks(b["body"], b["level"], num)
            elif kind == "p":
                self.para(f"LM Body {level}", b["runs"])
            elif kind == "heading":
                self.para("LM Plain Heading", b["runs"], keep_next=True)
            elif kind == "definition":
                p = self.para(f"LM Body {level}")
                _spacing(p.paragraph_format, house()["spacing_pt"]["definition"])
                p.add_run("“")
                p.add_run(b["term"]).bold = True
                p.add_run("” ")
                self.runs(p, b["runs"])
            elif kind == "list":
                items = self.restart(_LISTS)
                at, gutter = house()["list_twips"]
                left = house()["clause_ladder_twips"][level - 1][1] + at + gutter
                for runs in b["items"]:
                    p = self.para("LM List", runs, num=(items, 0))
                    p.paragraph_format.left_indent = Twips(left)
                    p.paragraph_format.first_line_indent = Twips(-gutter)
            elif kind == "table":
                self.table(b["rows"], b.get("widths"))
            elif kind == "image":
                p = self.para(f"LM Body {level}")
                self.picture(p, b["asset"], b["width_cm"], b["alt"])

    def table(self, rows: list[list[list[dict]]], widths: list[int] | None,
              keep_together: bool = False, header: bool = True) -> Any:
        t = house()["table"]
        table = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        table.autofit = False
        line = (f'w:val="single" w:sz="{t["border_eighths_pt"]}" w:space="0" '
                f'w:color="{t["border"]}"')
        vert, side = t["cell_margin_twips"]
        tblpr = table._tbl.tblPr
        tblpr.append(parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            + "".join(f"<w:{e} {line}/>" for e in
                      ("top", "left", "bottom", "right", "insideH", "insideV"))
            + "</w:tblBorders>"))
        tblpr.append(parse_xml(
            f'<w:tblCellMar {nsdecls("w")}>'
            + "".join(f'<w:{e} w:w="{w}" w:type="dxa"/>' for e, w in
                      (("top", vert), ("left", side), ("bottom", vert), ("right", side)))
            + "</w:tblCellMar>"))
        if widths:
            grid = table._tbl.tblGrid
            for col, w in zip(grid.findall(qn("w:gridCol")), widths, strict=True):
                col.set(qn("w:w"), str(w))
        for r, row in enumerate(rows):
            tr = table.rows[r]._tr
            trpr = tr.get_or_add_trPr()
            trpr.append(OxmlElement("w:cantSplit"))
            if r == 0 and header:
                trpr.append(OxmlElement("w:tblHeader"))
            for c, runs in enumerate(row):
                cell = table.rows[r].cells[c]
                if widths:
                    cell.width = Twips(widths[c])
                p = cell.paragraphs[0]
                p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
                _spacing(p.paragraph_format, [0, 0])
                if r == 0 and header:
                    cell._tc.get_or_add_tcPr().append(parse_xml(
                        f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" '
                        f'w:fill="{t["header_fill"]}"/>'))
                if keep_together and r < len(rows) - 1:
                    p.paragraph_format.keep_with_next = True
                self.runs(p, runs, bold=r == 0 and header)
        return table

    # -- sections
    def furniture(self, section: Any, label: str, doc_identifier: str,
                  front: bool = False) -> None:
        """Every page: the demo/review note, the label (if the house shows one), the
        document ID and page number. The logo is letterhead — the FRONT page only, top
        right, as an executed agreement carries it; later pages and schedules never."""
        h = house()
        logo = self.model.get("logo") if front else None
        section.different_first_page_header_footer = bool(logo)
        pairs = [(section.header, section.footer)]
        if logo:
            pairs.append((section.first_page_header, section.first_page_footer))
        for header, footer in pairs:
            header.is_linked_to_previous = False
            footer.is_linked_to_previous = False
            head = header.paragraphs[0]
            if self.header_note:      # a demo or review copy says so on every page
                note = head.add_run(self.header_note + "  ")
                note.bold = True
                note.font.color.rgb = RGBColor.from_string("B42318")
            if h["header_label"] and header is section.header:
                head.add_run(label).font.color.rgb = RGBColor.from_string(h["colour"])
            foot = footer.paragraphs[0]
            foot.add_run(doc_identifier).font.size = Pt(h["footer"]["id_size_pt"])
            foot.add_run("\t\t")
            _field(foot, " PAGE ")
        if logo:
            first = section.first_page_header
            mark = first.paragraphs[0]
            if mark.runs:                       # the demo note keeps its own line
                mark = first.add_paragraph()
            mark.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            self.picture(mark, f"logo:{self.model['brand']}", h["logo_width_cm"],
                         logo["alt"])

    def new_section(self) -> Any:
        return restart_pages(self.doc.add_section(WD_SECTION.NEW_PAGE))


def render(model: Mapping[str, Any], assets: Mapping[str, Any], *, contract_ref: str,
           version_number: int, model_hash: str, blank: bool = False,
           header_note: str | None = None) -> bytes:
    """The DOCX for one model. ``assets`` are the template's (name → {data_b64, alt}).
    ``blank``: the blank template's model (`model.resolve(blank=True)`) — no content
    controls, placeholders highlighted, each conditional part's note under its title;
    ``header_note`` printed first in every header (a DEMO template's label)."""
    b = _Builder(model, assets)
    b.blank, b.header_note = blank, header_note
    identifier = doc_id(contract_ref, version_number, model_hash)
    b.furniture(b.doc.sections[0], model["short_title"], identifier, front=True)
    gap = house()["front_gap_pt"]

    def gap_before(p: Any) -> None:     # the file's blank line, as spacing (Round 6)
        p.paragraph_format.space_before = Pt(gap)

    b.para("LM Title", [{"t": model["title"]}])
    if model["preamble"]:
        b.para("LM Front", emphasis(model["preamble"], terms="all"))
    if model["parties"]:
        start = b.mark()
        parties = b.restart(_RECITALS)
        for i, party in enumerate(model["parties"]):
            if i and model.get("connector"):
                b.para("LM Connector", model["connector"])
            p = b.para("LM Recital", num=(parties, 0), keep_next=True)
            if not i:
                gap_before(p)
            b.runs(p, party["name"], bold=True)
            if party.get("incorporation"):
                p.add_run(", ")
                b.runs(p, emphasis(party["incorporation"], terms="all"))
                continue
            p.add_run(f" (“{party['role']}”)")
            for label, key in (("Registered office", "office"), ("CIN", "cin")):
                if party[key]:
                    b.para("LM Recital", [{"t": f"{label}: "}, *party[key]])
        if model.get("parties_close"):
            b.para("LM Front", emphasis(model["parties_close"], terms="all"))
        b.sdt(start, "lm:parties")
    if model["recitals"]:
        gap_before(b.para("LM Plain Heading", model.get("recitals_label")
                          or [{"t": "Recitals"}], keep_next=True))
        recitals = b.restart(_RECITALS)          # A., B. again after the parties
        for runs in model["recitals"]:
            b.para("LM Recital", runs, num=(recitals, 0))
    if model.get("operative"):
        gap_before(b.para("LM Front", emphasis(model["operative"]), keep_next=True))
    def clauses(items: list[dict], num: int, main: bool = False) -> None:
        for i, clause in enumerate(items):
            start = b.mark()
            p = b.para("LM Heading 1", [{"t": clause["title"]}], num=(num, 0),
                       bookmark_key=clause["clause_key"])
            if main and not i and (model["preamble"] or model["parties"]):
                gap_before(p)
            if clause.get("note"):
                b.para("LM Body 1", [{"t": clause["note"], "ph": True}])
            b.blocks(clause["body"], 1, num)
            b.sdt(start, f"lm:{clause['clause_key']}@{clause['version']}")

    special = model.get("special_conditions")
    b.anchors = {n: k for k, n in (special or {}).get("anchors", {}).items()}
    clauses(model["body"], 1, main=True)
    b.anchors = {}
    if special and special["position"] == "before_execution":
        _special_conditions(b, special, model, identifier)
    _execution(b, model["execution"])
    if special and special["position"] != "before_execution":
        _special_conditions(b, special, model, identifier)
    for schedule in model["schedules"]:
        section = b.new_section()
        b.furniture(section, f"{model['short_title']} — {schedule['title']}", identifier)
        b.para("LM Schedule Title", [{"t": schedule["title"]}])
        if schedule.get("note"):
            b.para("LM Body 1", [{"t": schedule["note"], "ph": True}])
        clauses(schedule["clauses"], b.restart(_CLAUSES))
    _unique_drawing_ids(b.doc)
    _replace_numbering(b.doc, _numbering_xml(b.restarts))
    _neutral_core(b.doc, model["title"])
    return deterministic_zip(_save(b.doc))


def _execution(b: _Builder, execution: Mapping[str, Any]) -> None:
    """The approved format's signature table: one "By / Sign" column pair per party,
    the party's name bold beside "By", a spanning shaded header, room to sign."""
    parties = execution["rows"]
    if not parties:
        return
    t = house()["table"]
    start = b.mark()
    if execution.get("lead"):
        p = b.para("LM Front", emphasis(execution["lead"]), keep_next=True)
        p.paragraph_format.space_before = Pt(house()["front_gap_pt"])
    else:
        b.para("LM Plain Heading", [{"t": "Execution"}], keep_next=True)
    shows = {"Authority": any(r.get("authority") for r in parties),
             "Common seal": execution["seal"], "Witness": execution["witness"]}
    value = {"By": "party", "Name": "signatory", "Designation": "designation",
             "Authority": "authority", "Signatory Email": "email", "Date of sign": "date"}
    lines = [(label, height) for label, height in t["signature_rows"]
             if shows.get(label, True)]
    rows = [[[{"t": "Signatory Details"}], *[[] for _ in range(2 * len(parties) - 1)]]]
    for label, _ in lines:
        rows.append([cell for r in parties for cell in (
            [{"t": label}],
            [{**x, "b": label == "By"} for x in r.get(value.get(label, "")) or []])])
    pair = text_width_twips() // len(parties)
    widths = ([w for p in t["pair_twips"] for w in p] if len(parties) == 2 else
              [t["label_twips"], pair - t["label_twips"]] * len(parties))
    table = b.table(rows, widths, keep_together=True)
    head = table.cell(0, 0).merge(table.cell(0, len(rows[0]) - 1))
    head.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for tr, (_, height) in zip(table.rows[1:], lines, strict=True):
        tr.height = Twips(height)
    b.sdt(start, "lm:execution")


def _special_conditions(b: _Builder, sc: Mapping[str, Any], model: Mapping[str, Any],
                        identifier: str) -> None:
    """The Special Conditions part (`AM-307`, R-5): a new page, page numbers running on
    from the body (never restarted), its own label in the header, the frame's title,
    its opening, then each entry — numbered 1, 2 … with the frame's lead sentence (a
    ``REF`` to the varied clause) and the agreed text verbatim — in one locked content
    control; where the template asks, both parties' signature lines (R-6, Q-5), kept on
    the page of the last entry."""
    section = b.doc.add_section(WD_SECTION.NEW_PAGE)
    b.furniture(section, f"{model['short_title']} — {sc['label']}", identifier)
    if not house()["header_label"]:            # the body has none; the annexure says so
        head = section.header.paragraphs[0]
        head.add_run(("\t" if head.text else "") + sc["label"]).font.color.rgb = \
            RGBColor.from_string(house()["colour"])
    start = b.mark()
    b.para("LM Schedule Title", sc["title"])
    for runs in sc["opening"]:
        b.para("LM Front", runs)
    num = b.restart(_ENTRIES)
    tail = bool(sc.get("signature"))
    for i, e in enumerate(sc["entries"]):
        last = i == len(sc["entries"]) - 1
        b.para("LM Body 1", e["lead"], num=(num, 0),
               keep_next=bool(e["blocks"]) or (last and tail))
        for k, runs in enumerate(e["blocks"]):
            b.para("LM Body 2", runs,
                   keep_next=k < len(e["blocks"]) - 1 or (last and tail))
    if tail:
        _signature_lines(b, model["execution"]["rows"])
    b.sdt(start, "lm:special-conditions")


def _signature_lines(b: _Builder, parties: list[dict]) -> None:
    """Both parties' lines under the annexure, in the signature table's style — the
    house's own labels (``annexure_signature_rows``), the party's name bold by "By"."""
    t = house()["table"]
    value = {"By": "party", "Name": "signatory"}
    rows = []
    for label, _ in t["annexure_signature_rows"]:
        rows.append([cell for r in parties for cell in (
            [{"t": label}],
            [{**x, "b": label == "By"} for x in r.get(value.get(label, "")) or []])])
    pair = text_width_twips() // len(parties)
    widths = ([w for p in t["pair_twips"] for w in p] if len(parties) == 2 else
              [t["label_twips"], pair - t["label_twips"]] * len(parties))
    gap = b.para("LM Body 1", [], keep_next=True)
    gap.paragraph_format.space_before = Pt(house()["front_gap_pt"])
    table = b.table(rows, widths, keep_together=True, header=False)
    for tr, (_, height) in zip(table.rows, t["annexure_signature_rows"], strict=True):
        tr.height = Twips(height)


def restart_pages(section: Any) -> Any:
    """Page numbers restart at 1 in this section (``w:pgNumType`` in schema order,
    before ``w:cols``)."""
    sect = section._sectPr
    if sect.find(qn("w:pgNumType")) is None:
        el = OxmlElement("w:pgNumType", {qn("w:start"): "1"})
        cols = sect.find(qn("w:cols"))
        if cols is not None:
            cols.addprevious(el)
        else:
            sect.append(el)
    return section


def _unique_drawing_ids(doc: Any) -> None:
    """``wp:docPr/@id`` unique across the whole package (python-docx counts per part,
    so a header logo and a body figure would both be 1)."""
    n = 0
    for part in doc.part.package.iter_parts():
        element = getattr(part, "_element", None)
        if element is None:
            continue
        for pr in element.iter(qn("wp:docPr")):
            n += 1
            pr.set("id", str(n))


def _replace_numbering(doc: Any, xml: str) -> None:
    numbering = doc.part.numbering_part.element
    for child in list(numbering):
        numbering.remove(child)
    for child in parse_xml(xml):
        numbering.append(copy.deepcopy(child))


def _neutral_core(doc: Any, title: str) -> None:
    core = doc.core_properties
    core.author = core.last_modified_by = "LegalMind"
    core.title, core.subject, core.keywords, core.comments = title, "", "", ""
    core.created = core.modified = core.last_printed = _FIXED
    core.revision = 1


def _save(doc: Any) -> bytes:
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def deterministic_zip(data: bytes) -> bytes:
    """The same package with fixed entry timestamps and no preview thumbnail, so equal
    parts give equal bytes."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename == "docProps/thumbnail.jpeg":
                continue
            body = src.read(info.filename)
            if info.filename == "_rels/.rels":
                body = re.sub(rb'<Relationship [^>]*thumbnail\.jpeg"/>', b"", body)
            entry = zipfile.ZipInfo(info.filename, date_time=_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            dst.writestr(entry, body)
    return out.getvalue()


def append_annexure(main: bytes, annexure: bytes, title: str) -> bytes:
    """A lawyer-supplied annexure appended UNCHANGED after a new page with its title.

    ponytail: minimal lxml append — text, tables and paragraph formatting only. An
    annexure with its own images, numbering, styles or comments is refused (its
    relationships and definitions would not travel); `docxcompose.Composer` with
    preserve-styles replaces this body once installed (`AM-278`)."""
    annex = docx.Document(io.BytesIO(annexure))
    body = annex.element.body
    refused = [what for what, xpath in (
        ("images or linked objects", ".//*[@r:embed or @r:id or @r:link]"),
        ("list numbering", ".//w:numPr"), ("comments", ".//w:commentReference"))
        if body.xpath(xpath)]
    custom_styles = set(body.xpath(".//w:pStyle/@w:val | .//w:rStyle/@w:val"))
    doc = docx.Document(io.BytesIO(main))
    known = {s.style_id for s in doc.styles}
    if custom_styles - known:
        refused.append("styles " + ", ".join(sorted(custom_styles - known)))
    if refused:
        raise RenderError("annexure needs docxcompose to be appended: it carries "
                          + "; ".join(refused))
    section = restart_pages(doc.add_section(WD_SECTION.NEW_PAGE))
    section.header.is_linked_to_previous = False
    section.header.paragraphs[0].text = title
    doc.add_paragraph(title, style="LM Schedule Title")
    anchor = doc.element.body.find(qn("w:sectPr"))
    for el in body:
        if el.tag != qn("w:sectPr"):
            anchor.addprevious(copy.deepcopy(el))
    return deterministic_zip(_save(doc))
