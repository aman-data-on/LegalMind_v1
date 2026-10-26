"""A blank page is read, never failed (AM-187, 2026-10-26): a contract with one blank
page — only its page number, as a tiny picture — was PARTIAL, and its review refused."""
import pymupdf

from legalmind.domain.enums import ExtractionStatus
from legalmind.ingestion.parsing import parse

CLAUSE = ("1. Liability. The total liability of either party shall not exceed the fees "
          "paid in the twelve months before the claim. ") * 3


def _pdf(second_page) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 400), CLAUSE)
    second_page(doc.new_page())
    doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 400), CLAUSE)
    return doc.tobytes()


def _png(w: int, h: int) -> bytes:
    return pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), 0).tobytes("png")


def test_a_blank_page_with_only_a_page_number_is_read():
    def page(p):
        p.draw_rect(p.rect, color=None, fill=(1, 1, 1))              # white background
        p.insert_image(pymupdf.Rect(290, 800, 305, 810), stream=_png(29, 17))
        p.insert_text((297, 790), "2")
    result = parse(_pdf(page), "application/pdf")
    assert result.status is ExtractionStatus.COMPLETE and result.pages_failed == []


def test_an_empty_page_is_read():
    result = parse(_pdf(lambda p: None), "application/pdf")
    assert result.status is ExtractionStatus.COMPLETE


def test_a_page_holding_a_picture_is_never_called_blank():
    """A scan the size of the page may be a whole clause: OCR decides, never us."""
    result = parse(_pdf(lambda p: p.insert_image(p.rect, stream=_png(600, 800))),
                   "application/pdf")
    assert not any("blank" in d for d in result.diagnostics)


def test_a_page_with_drawn_lines_is_never_called_blank():
    """Text drawn as outlines has no text layer: a black drawing is not blank."""
    result = parse(_pdf(lambda p: p.draw_line((50, 100), (500, 100))), "application/pdf")
    assert not any("blank" in d for d in result.diagnostics)
