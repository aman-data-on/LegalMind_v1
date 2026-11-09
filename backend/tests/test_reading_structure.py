"""How faithfully a client's paper is read — CLM batch C (legalmind-ingest-v10, 2026-11-09).

The all-features specimen (MANIFEST §4) scored 3/13 as Word, 3/13 as PDF and 2/13 as a
scan. Each class of failure is rebuilt here on a synthetic file (54.6 keeps real
documents out of the repository), with the case that must NOT change beside it:

* a PDF's repeated page header and footer kept apart from the clauses (34.10) — a line
  repeated once in the body is not furniture;
* a table of contents is no clause; three short headings in a row are not a contents;
* "5." printed above "TERM AND TERMINATION" numbers the heading; a "5." mid-text does not;
* a struck letter beside an inserted one in one PDF span splits ("ixty (60)");
* an image strip is read only as prose, placed where it stands, else flagged;
* a numbered Word paragraph that is only a picture is that clause, or is flagged;
* ligature glyphs read as letters; a DOCX without Word's pagination is paginated by the
  renderer when one is configured, and keeps its own breaks when none is.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from legalmind.domain.enums import EvidenceSourceType
from legalmind.ingestion import parsing
from legalmind.ingestion.parsing import normalize_text, parse_docx, parse_pdf

pymupdf = pytest.importorskip("pymupdf")
docx = pytest.importorskip("docx")

ORANGE = (0.776, 0.573, 0.0)


def _pdf(pages: list[list[str]], header: str | None = None,
         footer: str | None = None) -> bytes:
    doc = pymupdf.open()
    for number, lines in enumerate(pages, start=1):
        page = doc.new_page()
        if header:
            page.insert_text((72, 40), header, fontsize=8)
        y = 90.0
        for line in lines:
            page.insert_text((72, y), line, fontsize=10)
            y += 14
        if footer:
            page.insert_text((72, 800), footer.format(n=number, of=len(pages)), fontsize=8)
    return doc.tobytes()


def _read(data: bytes):
    return parse_pdf(data, ocr=False, docling=False)


BODY = [["1.1 The Customer shall pay the fees stated in the order form.",
         "1.2 Either Party may terminate on thirty (30) days notice."],
        ["2.1 LeapSwitch shall provide the Services with reasonable care.",
         "2.2 The Customer shall keep its credentials confidential."],
        ["3.1 This Agreement is governed by the laws of India.",
         "3.2 Notices shall be given in writing to the addresses above."]]


# --- headers and footers -------------------------------------------------------------
def test_a_pdfs_running_header_and_page_footer_are_kept_apart_from_the_clauses():
    result = _read(_pdf(BODY, header="Demo Client | Master Services Agreement | Draft 2",
                        footer="Document Ref: DC/14 Page {n} of {of}"))
    body = [s for s in result.segments if s.metadata.get("part") is None]
    assert not any("Document Ref" in s.content or "Draft 2" in s.content for s in body)
    parts = {s.metadata["part"]: s.content for s in result.segments
             if s.metadata.get("part")}
    assert set(parts) == {"header", "footer"}
    assert all(s.source_type is EvidenceSourceType.OTHER and s.page_number is None
               for s in result.segments if s.metadata.get("part"))
    assert [s.section_number for s in body] == ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2"]


def test_a_line_on_only_two_pages_and_a_clause_on_every_page_stay_text():
    pages = [["1. The Customer shall pay the fees stated in the order form."],
             ["2. The Customer shall pay the fees stated in the order form."],
             ["3. The Customer shall pay the fees stated in the order form.",
              "Signed for the Customer"],
             ["Signed for the Customer", "4. Notices shall be in writing."]]
    result = _read(_pdf(pages))
    assert not any(s.metadata.get("part") for s in result.segments)
    assert sum("Signed for the Customer" in s.content for s in result.segments) == 2


# --- table of contents -----------------------------------------------------------------
HEADED = [["1. DEFINITIONS", "1.1 The Customer shall pay the fees stated in the order."],
          ["2. SCOPE OF SERVICES", "2.1 LeapSwitch shall provide the Services."],
          ["3. TERM AND TERMINATION", "3.1 Either Party may terminate on notice."]]


def test_a_table_of_contents_is_kept_as_contents_never_as_clauses():
    toc = ["CONTENTS", "1. DEFINITIONS ........................ 3",
           "2. SCOPE OF SERVICES .................. 5",
           "3. TERM AND TERMINATION ............... 8"]
    result = _read(_pdf([toc, *HEADED]))
    contents = [s for s in result.segments if s.metadata.get("part") == "contents"]
    assert contents and all(s.section_number is None for s in contents)
    assert not any(s.metadata.get("heading") for s in contents)
    assert [s.section_number for s in result.segments if s.section_number][:2] == [
        "1", "1.1"]


def _segment(text: str) -> parsing.Segment:
    return parsing.Segment(content=normalize_text(text), original_content=text,
                           source_type=EvidenceSourceType.NATIVE_TEXT, page_number=1,
                           section_number=None, section_title=None, start_offset=0,
                           end_offset=len(text), metadata={})


def test_an_order_forms_terms_ending_in_numbers_are_never_contents():
    terms = ["Initial Term in months 12", "Notice of non-renewal in days 90",
             "Payment due within days 30", "Liability cap in months of fees 3"]
    segments = [_segment(t) for t in ["ORDER FORM", *terms, "Signed for the Customer"]]
    parsing._mark_contents(segments)
    assert not any(s.metadata.get("part") for s in segments)
    # the same lines as typed contents with dots, under a title, are still not contents
    # when no heading of the document carries those titles
    dotted = [_segment("CONTENTS"), *(_segment(f"{t} .... {n}") for t, n in
                                      (("Initial Term", 2), ("Notice", 3), ("Payment", 4)))]
    parsing._mark_contents(dotted)
    assert not any(s.metadata.get("part") for s in dotted)


def test_a_word_contents_with_tab_leaders_is_caught():
    segments = [_segment(t) for t in [
        "CONTENTS", "1. DEFINITIONS\t3", "2. SCOPE OF SERVICES\t5",
        "3. TERM AND TERMINATION\t8", "1. DEFINITIONS", "2. SCOPE OF SERVICES",
        "3. TERM AND TERMINATION"]]
    parsing._mark_contents(segments)
    assert [bool(s.metadata.get("part")) for s in segments] == [True] * 4 + [False] * 3


def test_three_one_line_headings_in_a_row_are_not_a_contents():
    segments = [parsing.Segment(content=text, original_content=text,
                                source_type=EvidenceSourceType.NATIVE_TEXT, page_number=1,
                                section_number=None, section_title=text,
                                start_offset=0, end_offset=len(text),
                                metadata={"heading": True})
                for text in ("RECITALS", "DEFINITIONS", "SCOPE OF SERVICES")]
    parsing._mark_contents(segments)
    assert not any(s.metadata.get("part") for s in segments)


# --- a top-level number above its heading ---------------------------------------------
def test_a_number_printed_above_its_heading_numbers_the_heading():
    result = _read(_pdf([["4.6 The Customer shall not unreasonably withhold consent.",
                          "5.", "TERM AND TERMINATION",
                          "5.1 This Agreement commences on the Effective Date."]]))
    heading = next(s for s in result.segments if s.section_number == "5")
    assert heading.section_title == "TERM AND TERMINATION"
    assert heading.metadata.get("heading") is True
    assert not any(s.content.endswith("5.") for s in result.segments)


def test_a_bare_number_above_prose_is_not_a_heading():
    assert parsing._bare_heading("5.", "The Customer shall pay within thirty days.") is None
    assert parsing._bare_heading("5", "TERM AND TERMINATION") is None
    assert parsing._bare_heading("5.", "TERM AND TERMINATION") == ("5", "TERM AND TERMINATION")


# --- tracked changes printed in a PDF --------------------------------------------------
def _redline(before: str, deleted: str, inserted: str, after: str) -> bytes:
    """The N7 shape exactly: the deletion and the insertion printed as ONE coloured run,
    the strike reaching a hair past the deletion's last letter and the underline
    starting a hair before the insertion's first — so PyMuPDF flags ")s" both struck
    and underlined, and the parent read "ixty (60)"."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), before, fontsize=10)
    x = 72 + pymupdf.get_text_length(before, fontsize=10)
    page.insert_text((x, 100), deleted + inserted, fontsize=10, color=ORANGE)
    cut = x + pymupdf.get_text_length(deleted, fontsize=10)
    end = cut + pymupdf.get_text_length(inserted, fontsize=10)
    page.draw_line((x, 96.5), (cut + 0.6, 96.5), color=ORANGE, width=0.5)
    page.draw_line((cut - 0.6, 102), (end, 102), color=ORANGE, width=0.5)
    page.insert_text((end, 100), after, fontsize=10)
    return doc.tobytes()


def test_a_struck_figure_and_the_inserted_one_beside_it_keep_their_own_letters():
    data = _redline("5.4 Cured within ", "thirty (30)", "sixty (60)", " days.")
    spans = [s for b in pymupdf.open(stream=data)[0].get_text(
        "dict", flags=pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_COLLECT_STYLES)["blocks"]
        for line in b["lines"] for s in line["spans"]]
    assert any(s["char_flags"] & 3 == 3 for s in spans)      # the shape is reproduced
    segment = _read(data).segments[0]
    assert "Cured within sixty (60) days." in segment.content
    assert segment.metadata["revision"]["changes"] == [
        {"deleted": "thirty (30)", "inserted": "sixty (60)"}]


def test_a_mixed_span_is_split_at_the_letter_its_rule_changes():
    chars = [{"c": c, "bbox": (100 + 5 * i, 90, 105 + 5 * i, 102)}
             for i, c in enumerate(")s")]
    span = {"text": ")s", "char_flags": 16 | 3, "bbox": (100, 90, 110, 102)}
    rules = [(90, 96, 104, 96), (105, 101, 140, 101)]      # strike, then underline
    split = parsing._split_by_rules(span, chars, rules)
    assert [(s["text"], s["char_flags"] & 3) for s in split] == [(")", 1), ("s", 2)]


# --- an image in the text ---------------------------------------------------------------
def _image_strip_pdf(words: str | None) -> bytes:
    """Typed clauses with a paragraph-shaped picture under "16.3" (a pasted scan)."""
    src = pymupdf.open()
    shot = src.new_page(width=500, height=60)
    if words:
        shot.insert_textbox(pymupdf.Rect(5, 5, 495, 55), words, fontsize=11)
    png = shot.get_pixmap(dpi=150).tobytes("png")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "16.2 Consequences of Force Majeure: the obligations "
                     "are suspended.", fontsize=10)
    page.insert_text((60, 160), "16.3", fontsize=10)
    page.insert_image(pymupdf.Rect(90, 115, 520, 165), stream=png)
    page.insert_text((72, 200), "16.4 No Relief for Customer Defaults: payment is "
                     "never excused.", fontsize=10)
    return doc.tobytes()


SCANNED = ("Extended Force Majeure: if the event continues for a period exceeding sixty "
           "(60) consecutive days, either Party may terminate this Agreement.")


def test_an_image_strip_unread_is_flagged_on_its_clause_and_the_reading_is_partial():
    result = _read(_image_strip_pdf(SCANNED))
    flagged = [s for s in result.segments if s.metadata.get("unread_image")]
    assert [s.section_number for s in flagged] == ["16.3"]
    assert flagged[0].metadata["unread_image"] == {"page": 1, "number": None}
    assert result.pages_failed == [1]


def test_an_image_strip_read_as_prose_stands_after_its_number(monkeypatch):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel", lambda data, pages, clips=None: [
        (i, (SCANNED, 92.0)) for i in pages])
    segments = parse_pdf(_image_strip_pdf(SCANNED), docling=False).segments
    order = [s.section_number or s.source_type.value for s in segments]
    assert order == ["16.2", "16.3", "OCR", "16.4"]


def test_an_image_strip_holding_labels_not_sentences_adds_no_text(monkeypatch):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel", lambda data, pages, clips=None: [
        (i, ("Order placed  KYC  Provisioned  Live service", 92.0)) for i in pages])
    result = parse_pdf(_image_strip_pdf(None), docling=False)
    assert not any(s.source_type is EvidenceSourceType.OCR for s in result.segments)
    assert not any(s.metadata.get("unread_image") for s in result.segments)


def _numbered_picture_docx() -> bytes:
    """Clause 1.1 typed, clause 1.2 a numbered paragraph holding only a picture."""
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    document = docx.Document()
    numbering = document.part.numbering_part.element
    numbering.append(parse_xml(
        f'<w:abstractNum {nsdecls("w")} w:abstractNumId="90"><w:lvl w:ilvl="0">'
        '<w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/>'
        '<w:lvlText w:val="%1.%2"/></w:lvl></w:abstractNum>'))
    numbering.append(parse_xml(f'<w:num {nsdecls("w")} w:numId="7">'
                               '<w:abstractNumId w:val="90"/></w:num>'))

    def numbered(text: str, level: int):
        p = document.add_paragraph(text)
        p._p.get_or_add_pPr().append(parse_xml(
            f'<w:numPr {nsdecls("w")}><w:ilvl w:val="{level}"/><w:numId w:val="7"/>'
            '</w:numPr>'))
        return p
    numbered("FORCE MAJEURE", 0)
    numbered("Consequences: the obligations are suspended for the duration.", 1)
    png = pymupdf.open()
    shot = png.new_page(width=400, height=40)
    shot.insert_text((5, 25), "Extended Force Majeure: sixty (60) days", fontsize=11)
    numbered("", 1).add_run().add_picture(io.BytesIO(shot.get_pixmap(dpi=150).tobytes(
        "png")), width=docx.shared.Inches(1.5))
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_a_numbered_word_paragraph_that_is_only_a_picture_is_that_clause(monkeypatch):
    monkeypatch.setattr(parsing, "_tesseract_pixmap",
                        lambda pix: (SCANNED, 91.0))
    segments = parse_docx(_numbered_picture_docx()).segments
    ocr = [s for s in segments if s.source_type is EvidenceSourceType.OCR]
    assert [(s.section_number, s.content) for s in ocr] == [("1.2", SCANNED)]


def test_a_numbered_word_picture_that_cannot_be_read_is_flagged(monkeypatch):
    def fail(pix):
        raise parsing.ParseError("no OCR here")
    monkeypatch.setattr(parsing, "_tesseract_pixmap", fail)
    result = parse_docx(_numbered_picture_docx())
    flagged = [s for s in result.segments if s.metadata.get("unread_image")]
    assert [s.metadata["unread_image"]["number"] for s in flagged] == ["1.2"]
    assert result.status.value == "PARTIAL"


# --- text normalisation and DOCX pages --------------------------------------------------
def test_ligature_glyphs_read_as_their_letters_and_the_original_keeps_them():
    assert normalize_text("Conﬁdential conﬂicts eﬀect") == \
        "Confidential conflicts effect"


def _docx_with_hard_break() -> bytes:
    document = docx.Document()
    document.add_paragraph("1. The Customer shall pay the fees.")
    document.add_page_break()
    document.add_paragraph("2. Notices shall be in writing.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_a_docx_without_words_record_takes_the_renderers_pages(monkeypatch):
    monkeypatch.setattr(parsing, "_docx_rendered_pages",
                        lambda data, paragraphs: ([1, 1, 3], 3, "LibreOffice 26.2"))
    result = parse_docx(_docx_with_hard_break(), render_pages=True)
    assert result.pagination_source == parsing.DOCX_LIBREOFFICE_RENDER
    assert result.pages_total == 3
    assert [s.page_number for s in result.segments] == [1, 3]
    assert result.reader == {"libreoffice_version": "LibreOffice 26.2"}


def test_a_docx_is_never_printed_unless_it_is_an_upload(monkeypatch):
    calls = []
    monkeypatch.setattr(parsing, "_docx_rendered_pages",
                        lambda data, paragraphs: calls.append(1))
    parse_docx(_docx_with_hard_break())                  # generated, preflight, Ask …
    parsing.parse(_docx_with_hard_break(), parsing.DOCX_MIME)
    assert calls == []


def test_a_hanging_renderer_is_killed_with_its_children(monkeypatch, tmp_path):
    import time
    marker = tmp_path / "child.pid"
    fake = tmp_path / "soffice"
    fake.write_text(f"#!/bin/sh\nsleep 300 &\necho $! > {marker}\nwait\n")
    fake.chmod(0o755)
    monkeypatch.setenv("LEGALMIND_SOFFICE", str(fake))
    monkeypatch.setattr(parsing, "RENDER_TIMEOUT_S", 1)
    started = time.monotonic()
    assert parsing._render_docx(_docx_with_hard_break()) is None
    assert time.monotonic() - started < 10
    child = int(marker.read_text())
    time.sleep(0.2)
    stat = Path(f"/proc/{child}/stat")
    # gone, or a zombie waiting for init to reap it: either way no longer running
    assert not stat.exists() or stat.read_text().split()[2] == "Z"


def test_without_a_renderer_a_docx_keeps_its_own_breaks(monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    result = parse_docx(_docx_with_hard_break())
    assert result.pagination_source == parsing.DOCX_EXPLICIT_PAGE_BREAKS
    assert [s.page_number for s in result.segments] == [1, 2]


# --- a blurred grey scan is not a redline ------------------------------------------------
def test_a_blurred_grey_page_is_not_read_as_revision_ink():
    np = pytest.importorskip("numpy")
    grey = np.full((200, 600), 255, np.uint8)
    for row in range(40, 160, 20):                      # blurred black "type": grey edges
        grey[row:row + 3, 40:560] = 0
        grey[row - 3:row, 40:560] = 150
        grey[row + 3:row + 6, 40:560] = 150
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.Pixmap(
        pymupdf.csGRAY, 600, 200, grey.tobytes(), False))
    assert parsing._revision_rules(pix) is None


def test_a_gutter_number_tesseract_read_as_its_own_column_rejoins_its_clause():
    def word(block, line, x, y, text):
        return ["5", "1", str(block), "1", str(line), "1", str(x), str(y), "40", "20",
                "90", text]
    rows = [word(1, 1, 100, 300, "5.4"),
            word(2, 1, 200, 298, "Termination"), word(2, 1, 320, 298, "for"),
            word(2, 2, 200, 330, "breach"), word(2, 2, 260, 330, "applies.")]
    assert parsing._hang_numbers(rows) == "5.4 Termination for\nbreach applies.\n"
    # a real second column carries text, not bare numbers: left as tesseract read it
    assert parsing._hang_numbers([word(1, 1, 100, 300, "Fees"),
                                  word(2, 1, 400, 300, "Term")]) is None


# --- a PDF's footnote and its reference mark ---------------------------------------------
def test_a_pdf_footnote_is_a_note_never_a_clause_one():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "1.1 Territory means the territory of India.",
                     fontsize=10)
    page.insert_text((72, 114), "1.2 Notices shall be in writing.", fontsize=10)
    page.insert_text((72, 760), "1 Reference to the word include is without limitation.",
                     fontsize=7)
    segments = _read(doc.tobytes()).segments
    note = next(s for s in segments if "Reference to the word" in s.content)
    assert note.metadata.get("part") == "footnote" and note.section_number is None
    assert [s.section_number for s in segments if s.section_number] == ["1.1", "1.2"]


class _Page:
    """A page as `_note_marks` reads it: one body line ending in a superscript mark."""
    rect = pymupdf.Rect(0, 0, 600, 800)

    def get_text(self, kind, flags=0):
        span = {"size": 10.0, "flags": 4}
        return {"blocks": [{"lines": [{"bbox": (72, 100, 400, 112), "spans": [
            {**span, "text": "Territory means the territory of India."},
            {"text": "1", "size": 6.4, "flags": 5}]}]}]}


def test_a_superscript_note_mark_after_a_word_leaves_the_clause_text():
    raw, small = parsing._note_marks(_Page(),
                                     "Territory means the territory of India.1\n")
    assert raw == "Territory means the territory of India.\n" and small == frozenset()


def test_a_line_opening_with_a_cross_reference_is_not_that_clause():
    assert parsing.detect_clause_number("Clause 16 of this Agreement.") == (None, None)
    assert parsing.detect_clause_number("Clause 16 Force Majeure")[0] == "16"


# --- bounded work: past the limit the page is said, its text never dropped ----------------
def test_past_the_split_limit_the_page_is_flagged_and_keeps_its_text(monkeypatch):
    monkeypatch.setattr(parsing, "SPLIT_MAX_WORK", 0)
    result = _read(_redline("5.4 Cured within ", "thirty (30)", "sixty (60)", " days."))
    assert any("too dense" in d for d in result.diagnostics)
    assert "(60) days." in result.segments[0].content


def test_past_the_line_limit_gutter_numbers_are_left_as_read(monkeypatch):
    monkeypatch.setattr(parsing, "HANG_MAX_LINES", 1)
    rows = [["5", "1", "1", "1", "1", "1", "100", "300", "40", "20", "90", "5.4"],
            ["5", "1", "2", "1", "1", "1", "200", "298", "40", "20", "90", "Text"]]
    assert parsing._hang_numbers(rows) is None
