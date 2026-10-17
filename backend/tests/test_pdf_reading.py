"""PDF reading — tables, rotation, clause numbers, OCR quality and image regions.

The document-reading audit (2026-10-15) found these on real files; each test here
reproduces one on a synthetic PDF built in the test (locked 54.6 keeps real
documents out of the repository), and the last block pins the approved corpus
itself when it is present (it never is on CI):

  F1    a ruled table came out one cell per line, rows and columns lost
  R2    a 270-degree page whose footer was drawn first read its clauses backwards
  P1    "6.1.<ZERO WIDTH SPACE>" was not a clause number (MSA-Feb.pdf: 1 of ~200)
  R3    a sideways scan was OCR'd into gibberish and stored COMPLETE
  F5    text inside a large image on a typed page was never read
  OCR-QUALITY / OCR-SEQUENTIAL / F6   confidence, one parallel pass, -l and --psm 1
  BR-10 no test parsed the real contracts, so a segmentation regression passed CI
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import pytest

from legalmind import config
from legalmind.domain.enums import EvidenceSourceType, ExtractionStatus
from legalmind.ingestion import parsing
from legalmind.ingestion.parsing import detect_clause_number, parse_pdf

pymupdf = pytest.importorskip("pymupdf")

needs_tesseract = pytest.mark.skipif(not parsing.ocr_available(),
                                     reason="OCR toolchain not installed")

CREDIT_ROWS = [["Monthly Uptime", "Service Credit"],
               ["< 99.95% but >= 99.0%", "5% of monthly fee"],
               ["< 99.0% but >= 95.0%", "10% of monthly fee"],
               ["< 95.0%", "25% of monthly fee"]]


def _ruled_table_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "7. Service Credits", fontsize=11)
    page.insert_text((72, 90), "7.1 If Monthly Uptime falls below the commitment, "
                               "Customer receives the credit below.", fontsize=9)
    for r, row in enumerate(CREDIT_ROWS):
        for c, cell in enumerate(row):
            rect = pymupdf.Rect(72 + c * 200, 110 + r * 20, 272 + c * 200, 130 + r * 20)
            page.draw_rect(rect, color=(0, 0, 0), width=0.8)
            page.insert_text((rect.x0 + 4, rect.y0 + 14), cell, fontsize=9)
    page.insert_text((72, 210), "7.2 Credits are the sole remedy for downtime.", fontsize=9)
    return doc.tobytes()


def _words(text: str) -> Counter:
    return Counter(re.findall(r"\w+", text))


# =====================================================================
# F1 — ruled tables inline, in their clause
# =====================================================================
def test_a_ruled_table_stays_inside_its_clause_as_rows():
    result = parse_pdf(_ruled_table_pdf())
    by_number = {s.section_number: s for s in result.segments}

    clause = by_number["7.1"]
    assert "| Monthly Uptime | Service Credit |" in clause.content
    assert "| < 99.95% but >= 99.0% | 5% of monthly fee |" in clause.content
    assert clause.metadata["tables"] == 1
    assert clause.source_type is EvidenceSourceType.NATIVE_TEXT     # BR-7: still judged
    assert by_number["7.2"].content == "7.2 Credits are the sole remedy for downtime."
    # No word lost or doubled, and offsets still run forward.
    page = pymupdf.open(stream=_ruled_table_pdf(), filetype="pdf")[0]
    assert _words(" ".join(s.content for s in result.segments)) == _words(page.get_text())
    starts = [s.start_offset for s in result.segments]
    assert starts == sorted(starts)


def test_a_table_header_line_is_not_cut_off_as_its_own_heading():
    """Critic recheck: SLA-leapswitch's header "Monthly Uptime Service Credit
    Percentage" became a heading segment and took the 15/40/100% rows from
    "Issuance of Service Credits"."""
    header = "Monthly Uptime Service Credit Percentage"
    row = "| Less than 99.9%* but equal to or greater than 99.0% | 15% |"
    assert not parsing._is_unnumbered_heading(header, row)
    text = f"Issuance of Service Credits\nCredits follow the scale below.\n{header}\n{row}"
    segments = parsing.segment_paragraphs(text, page_number=1,
                                          source_type=EvidenceSourceType.NATIVE_TEXT)
    assert len(segments) == 1 and row in segments[0].content


def test_a_fill_only_grid_is_not_a_table_and_its_text_is_untouched():
    """MSA.pdf's shape: a white full-page fill and 13.8-pt black bars under each
    line, no strokes. strategy='lines' read its clauses as tables (F1b)."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(page.rect, color=None, fill=(1, 1, 1))
    lines = ["8.4 The Customer shall pay every invoice within thirty days.",
             "8.5 Late payment accrues interest at the statutory rate.",
             "8.6 Disputed amounts are notified in writing within ten days."]
    for i, line in enumerate(lines):
        y = 100 + i * 20
        page.draw_rect(pymupdf.Rect(72, y - 11, 520, y + 2.8), color=None, fill=(0, 0, 0))
        page.insert_text((72, y), line, fontsize=9, color=(1, 1, 1))
    page = pymupdf.open(stream=doc.tobytes(), filetype="pdf")[0]

    text, _ = parsing._page_blocks_in_reading_order(page)
    assert "|" not in text
    assert text == "\n".join(b[4].strip() for b in page.get_text("blocks")
                             if b[6] == 0 and b[4].strip())


def test_a_vertically_merged_label_is_carried_to_every_row_it_spans():
    doc = pymupdf.open()
    page = doc.new_page()
    x, y = [72, 200, 330, 470], [80, 100, 130, 160, 190]

    def rule(a, b):
        page.draw_line(a, b, color=(0, 0, 0), width=0.8)
    for yy in (y[0], y[1], y[4]):
        rule((x[0], yy), (x[3], yy))
    for yy in (y[2], y[3]):                 # column 0 merged across rows 1-3
        rule((x[1], yy), (x[3], yy))
    for xx in x:
        rule((xx, y[0]), (xx, y[4]))
    cells = {(0, 0): "Service", (0, 1): "Cap", (0, 2): "Exclusions",
             (1, 0): "Dedicated Servers", (1, 1): "12 months fees", (1, 2): "fraud",
             (2, 1): "Service credits", (2, 2): "gross negligence",
             (3, 1): "Uncapped for", (3, 2): "data breach"}
    for (r, c), text in cells.items():
        page.insert_text((x[c] + 4, y[r] + 14), text, fontsize=9)

    text = parse_pdf(doc.tobytes()).segments[0].content
    assert "| Dedicated Servers | 12 months fees | fraud |" in text
    assert "| Dedicated Servers | Service credits | gross negligence |" in text
    assert "| Dedicated Servers | Uncapped for | data breach |" in text


# =====================================================================
# R2 — rotated text keeps its order
# =====================================================================
def test_a_270_degree_page_with_its_footer_drawn_first_keeps_clause_order():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 800), "Page 1 of 3 - Annexure printed sideways", fontsize=9)
    for k in range(6):
        page.insert_text((500 - k * 40, 80),
                         f"{k + 1}. Clause number {k + 1} says the Customer shall pay "
                         f"fee {k + 1} within thirty days of the invoice date.",
                         fontsize=9, rotate=270)
    numbers = [s.section_number for s in parse_pdf(doc.tobytes()).segments
               if s.section_number]
    assert numbers == ["1", "2", "3", "4", "5", "6"]


# =====================================================================
# P1 — a zero-width space after the clause number
# =====================================================================
def test_a_zero_width_space_after_a_clause_number_is_still_a_clause_number():
    assert detect_clause_number("6.1.\u200b") == ("6.1", None)
    assert detect_clause_number("\ufeff7. Term") == ("7", "Term")
    segments = parsing.segment_paragraphs(
        "6.1.\u200b\nChange Requests shall be raised in writing by either party.",
        page_number=1, source_type=EvidenceSourceType.NATIVE_TEXT)
    assert segments[0].section_number == "6.1"
    assert "\u200b" in segments[0].content        # content untouched (34.14)


# =====================================================================
# F5 — an image region on a text page
# =====================================================================
def _mixed_pdf(token: str = "QUOKKA") -> bytes:
    src = pymupdf.open()
    page = src.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 400),
                        "ANNEXURE B - SERVICE CREDITS\nUptime below 99.5 percent: "
                        "credit of 10 percent of the monthly fee.\nThe Provider's "
                        f"aggregate liability shall not exceed {token} fees.", fontsize=12)
    png = page.get_pixmap(dpi=200, clip=pymupdf.Rect(40, 40, 560, 300)).tobytes("png")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), "Schedule 3 is attached below as signed by both parties.",
                     fontsize=11)
    page.insert_image(pymupdf.Rect(50, 100, 560, 400), stream=png)
    return doc.tobytes()


def test_an_image_the_text_layer_does_not_cover_is_found_and_a_scan_with_one_is_not():
    page = pymupdf.open(stream=_mixed_pdf(), filetype="pdf")[0]
    assert len(parsing._unread_images(page)) == 1

    # A full-page scan WITH a text layer over it (the Income-tax Act's shape).
    doc = pymupdf.open()
    page = doc.new_page()
    png = pymupdf.open(stream=_mixed_pdf(), filetype="pdf")[0].get_pixmap(dpi=72)
    page.insert_image(page.rect, stream=png.tobytes("png"))
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 400), "The Provider's aggregate "
                        "liability shall not exceed the fees paid in twelve months.")
    assert parsing._unread_images(page) == []


def test_an_image_region_defers_ocr_and_is_reported_when_ocr_is_off(monkeypatch):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    assert parse_pdf(_mixed_pdf(), defer_ocr=True).needs_ocr

    result = parse_pdf(_mixed_pdf(), defer_ocr=True, ocr=False)
    assert not result.needs_ocr
    # read in part, never COMPLETE: the region may hold the clause asked about (34.10)
    assert result.status is ExtractionStatus.FAILED      # its only page, so 0 of 1 whole
    assert result.pages_failed == [1]
    assert {s.source_type for s in result.segments} == {EvidenceSourceType.NATIVE_TEXT}
    assert "page 1: image region not read (OCR not run for this read)" in result.diagnostics


def test_an_image_region_ocr_cannot_vouch_for_leaves_its_page_partly_read(monkeypatch):
    """Review 2026-10-16: an unreliable region read was dropped and the page stayed
    COMPLETE. The native page is kept; the page is reported, so the reading is PARTIAL."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel", lambda data, pages, clips=None:
                        [(i, ("garbled annex text that could not be read well", 40.0))
                         for i in pages])
    doc = pymupdf.open(stream=_mixed_pdf(), filetype="pdf")
    doc.new_page().insert_text((72, 96), "2. The Customer shall pay every invoice.")
    result = parse_pdf(doc.tobytes())
    assert result.status is ExtractionStatus.PARTIAL and result.pages_failed == [1]
    assert {s.source_type for s in result.segments} == {EvidenceSourceType.NATIVE_TEXT}


def test_ocr_off_fails_a_page_needing_ocr_and_keeps_the_native_ones(monkeypatch):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel",
                        lambda *a, **k: pytest.fail("OCR ran with ocr=False"))
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 96), "1. The Customer shall pay every invoice.")
    doc.new_page()                                   # no text: needs OCR
    result = parse_pdf(doc.tobytes(), defer_ocr=True, ocr=False)
    assert not result.needs_ocr
    assert result.status is ExtractionStatus.PARTIAL
    assert result.pages_failed == [2]


# =====================================================================
# OCR — one parallel pass, per-page confidence
# =====================================================================
def _blank_pages(n: int) -> bytes:
    doc = pymupdf.open()
    for _ in range(n):
        doc.new_page()
    return doc.tobytes()


PROSE = "The Customer shall pay the fees stated in the order form within thirty days."


def test_every_page_needing_ocr_is_read_in_one_parallel_pass_in_page_order(monkeypatch):
    calls = []

    def fake(data, pages, clips=None):
        calls.append(list(pages))
        return [(i, (f"{i}. {PROSE}", 95.0)) for i in pages]
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel", fake)

    result = parse_pdf(_blank_pages(3))
    assert calls == [[1, 2, 3]]
    assert [s.page_number for s in result.segments] == [1, 2, 3]
    starts = [s.start_offset for s in result.segments]
    assert starts == sorted(set(starts))
    assert all(s.source_type is EvidenceSourceType.OCR
               and s.metadata["ocr_confidence"] == 95.0 for s in result.segments)
    assert "OCR languages: eng" in result.diagnostics


@pytest.mark.parametrize(("confidence", "kept"), [(40.0, False), (70.0, True)])
def test_ocr_confidence_fails_a_page_closed_or_flags_it(monkeypatch, confidence, kept):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel",
                        lambda data, pages, clips=None:
                        [(i, ("Zl dydj uawa easbe jana ad1A as wor ydu msdeay", confidence))
                         for i in pages])
    result = parse_pdf(_blank_pages(1))
    if kept:
        assert result.status is ExtractionStatus.COMPLETE
        assert result.pages_low_confidence == [1]
        assert result.segments[0].metadata["ocr_confidence"] == 70.0
        assert "page 1: low OCR confidence (70.0)" in result.diagnostics
    else:
        assert result.status is ExtractionStatus.FAILED
        assert result.segments == [] and result.pages_failed == [1]
        assert "page 1: OCR text not reliable (mean confidence 40.0)" in result.diagnostics


def test_doubtful_nonsense_still_fails_the_document_level_legibility_backstop(
        monkeypatch):
    """Kept where the page score cannot vouch for the text (under OCR_WARN_CONFIDENCE);
    a confident read is not judged by function words — see the table-scan test."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel",
                        lambda data, pages, clips=None:
                        [(i, ("Whe Rf WR cRmSan XndeU " * 60, 70.0)) for i in pages])
    result = parse_pdf(_blank_pages(2))
    assert result.status is ExtractionStatus.FAILED
    assert result.segments == [] and result.pages_failed == [1, 2]
    assert any(d.startswith("OCR output is not legible") for d in result.diagnostics)


def test_a_confidently_read_table_scan_is_not_judged_by_function_words(monkeypatch):
    """Review 2026-10-16: the backstop failed a confident scan of a price list — a table
    has almost no "the"/"of". Only OCR the confidence cannot vouch for is judged."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    rows = "\n".join(f"Tier {i} | {i * 500} INR | {i}% credit | 30 days" for i in range(70))
    monkeypatch.setattr(parsing, "_ocr_pages_parallel",
                        lambda data, pages, clips=None: [(i, (rows, 95.0)) for i in pages])
    result = parse_pdf(_blank_pages(1))
    assert parsing.text_is_legible(rows) is False             # the shape that was failed
    assert result.status is ExtractionStatus.COMPLETE and result.pages_failed == []


def test_tesseract_is_asked_for_a_language_orientation_and_confidence(monkeypatch, tmp_path):
    import subprocess

    seen = []

    def run(argv, **kwargs):
        seen.append(argv)
        Path(f"{argv[2]}.txt").write_text("Total liability is capped.\n")
        Path(f"{argv[2]}.tsv").write_text(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth"
            "\theight\tconf\ttext\n"
            "1\t1\t0\t0\t0\t0\t0\t0\t9\t9\t-1\t\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t9\t9\t90\tTotal\n"
            "5\t1\t1\t1\t1\t2\t0\t0\t9\t9\t70\tliability\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    class Pix:
        n = 1                       # greyscale: no revision ink to look for (AM-157)

        def save(self, path):
            Path(path).write_bytes(b"")
    monkeypatch.delenv("LEGALMIND_OCR_LANGS", raising=False)
    monkeypatch.setattr(config, "_tesseract_languages", lambda: frozenset({"eng", "osd"}))
    monkeypatch.setattr(subprocess, "run", run)

    assert parsing._tesseract_pixmap(Pix()) == ("Total liability is capped.\n", 80.0)
    argv = seen[0]
    assert argv[argv.index("-l") + 1] == "eng"
    assert argv[argv.index("--psm") + 1] == "1"
    assert argv[-2:] == ["txt", "tsv"]


def test_ocr_languages_keep_only_installed_models(monkeypatch):
    monkeypatch.setattr(config, "_tesseract_languages", lambda: frozenset({"eng", "osd"}))
    monkeypatch.setenv("LEGALMIND_OCR_LANGS", "eng+hin")
    assert config.ocr_languages() == "eng"
    monkeypatch.setenv("LEGALMIND_OCR_LANGS", "hin")
    assert config.ocr_languages() == "eng"
    monkeypatch.setattr(config, "_tesseract_languages", lambda: frozenset({"eng", "hin"}))
    monkeypatch.setenv("LEGALMIND_OCR_LANGS", "eng+hin")
    assert config.ocr_languages() == "eng+hin"


# --- the real toolchain ------------------------------------------------
@needs_tesseract
@pytest.mark.parametrize("rotate", [90, 180])
def test_a_sideways_or_upside_down_scan_is_read(rotate):
    src = pymupdf.open()
    page = src.new_page()
    page.insert_textbox(pymupdf.Rect(60, 60, 540, 400),
                        "17.2 The Supplier's total liability shall not exceed the fees "
                        "paid in the twelve months before the claim.\n17.3 Neither party "
                        "is liable for indirect or consequential loss.", fontsize=13)
    png = page.get_pixmap(dpi=200, clip=pymupdf.Rect(40, 40, 560, 420)).tobytes("png")
    doc = pymupdf.open()
    doc.new_page().insert_image(pymupdf.Rect(40, 40, 560, 420), stream=png, rotate=rotate)

    result = parse_pdf(doc.tobytes())
    assert result.status is ExtractionStatus.COMPLETE
    text = " ".join(s.content for s in result.segments)
    assert "total liability" in text
    assert all(s.source_type is EvidenceSourceType.OCR for s in result.segments)


@needs_tesseract
def test_an_image_region_on_a_text_page_is_read_by_ocr_after_the_native_text():
    result = parse_pdf(_mixed_pdf("QUOKKA"))
    assert result.status is ExtractionStatus.COMPLETE
    assert result.segments[0].source_type is EvidenceSourceType.NATIVE_TEXT
    ocr = [s for s in result.segments if s.source_type is EvidenceSourceType.OCR]
    assert any("QUOKKA" in s.content for s in ocr)
    assert all(s.page_number == 1 and "ocr_region" in s.metadata
               and "ocr_confidence" in s.metadata for s in ocr)
    assert "page 1: image region read by OCR" in result.diagnostics


@needs_tesseract
@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_a_scanned_annex_on_a_rotated_page_is_read_or_said(rotation):
    """Review 2026-10-16: on a /Rotate 90 page the region was clipped in the wrong
    coordinates, rendered blank, and the annex vanished from a COMPLETE page. Now it is
    read — or, where tesseract cannot read the render (upside down), the page is
    reported partly read. Never silent."""
    doc = pymupdf.open(stream=_mixed_pdf("QUOKKA"), filetype="pdf")
    doc[0].set_rotation(rotation)
    result = parse_pdf(doc.tobytes())
    text = " ".join(s.content for s in result.segments)
    assert "QUOKKA" in text or result.pages_failed == [1], result.diagnostics


# =====================================================================
# BR-10 — the approved corpus, when present (never on CI)
# =====================================================================
CORPUS = Path(config.source_material_dir())
CORPUS_PDFS = ["AUP-cloudpe.pdf", "AUP-leapswitch.pdf", "MSA-Feb.pdf",
               "MSA-GRP-2026-07-30.pdf", "MSA-original.pdf", "MSA.pdf", "NDA.pdf",
               "PRIVACY-cloudpe.pdf", "PRIVACY-leapswitch.pdf", "SLA-cloudpe.pdf",
               "SLA-leapswitch.pdf", "TOS-cloudpe.pdf", "TOS-leapswitch.pdf"]
# sha256[:16] of the numbered section_number sequence, measured with the parser
# BEFORE the 2026-10-15 changes: tables, rotation and OCR must not move a clause.
NUMBERED_BEFORE = {"MSA.pdf": "7b769554a27a57d7",
                   "MSA-GRP-2026-07-30.pdf": "6586288bb2e4ff83",
                   "TOS-leapswitch.pdf": "20f4febbb893732e"}


def _corpus(name: str):
    path = CORPUS / name
    if not path.is_file():
        pytest.skip(f"source material absent ({name})")
    # The standard parser's own pins; Docling's reading is pinned in test_docling_reading.
    return parse_pdf(path.read_bytes(), docling=False)


@pytest.mark.parametrize("name", CORPUS_PDFS)
def test_every_approved_pdf_still_reads_complete(name):
    result = _corpus(name)
    assert result.status is ExtractionStatus.COMPLETE
    if name in NUMBERED_BEFORE:
        numbers = "\n".join(s.section_number for s in result.segments if s.section_number)
        assert hashlib.sha256(numbers.encode()).hexdigest()[:16] == NUMBERED_BEFORE[name]
    if name == "TOS-leapswitch.pdf":       # its 25% banner image is not a scan (BR-8)
        assert all(s.source_type is EvidenceSourceType.NATIVE_TEXT
                   for s in result.segments)


def test_the_sla_credit_rows_stay_under_issuance_of_service_credits():
    result = _corpus("SLA-leapswitch.pdf")
    assert len(result.segments) == 19
    issuance = next(s for s in result.segments
                    if s.section_title == "Issuance of Service Credits")
    assert "| Less than 99.0% but equal to or greater than 95.0% | 40% |" in issuance.content
    assert "| Less than 95.0% | 100% |" in issuance.content


def test_the_nda_execution_block_reads_as_a_row():
    rows = [line for s in _corpus("NDA.pdf").segments for line in s.content.split("\n")
            if line.startswith("| ")]
    # Never print the row: it names the counterparty.
    assert any(line.startswith("| DISCLOSING PARTY | RECEIVING PARTY |") for line in rows)


def test_msa_feb_clause_numbers_behind_a_zero_width_space_are_read():
    result = _corpus("MSA-Feb.pdf")
    assert sum(bool(s.section_number) for s in result.segments) >= 150


def test_the_corpus_tables_lose_no_word():
    """F1's fail-safe, on the real files: inlining a table rewrites lines, never
    words — the \\w+ multiset of the page is what the text layer holds."""
    for name in ("SLA-leapswitch.pdf", "PRIVACY-leapswitch.pdf", "MSA-GRP-2026-07-30.pdf"):
        path = CORPUS / name
        if not path.is_file():
            pytest.skip(f"source material absent ({name})")
        for page in pymupdf.open(path):
            assert _words(parsing._page_blocks_in_reading_order(page)[0]) == _words(
                " ".join(b[4] for b in page.get_text("blocks") if b[6] == 0))

