"""A chat file with a scanned page (F7, critic #26, 2026-10-15). Before: one image-only
page failed the WHOLE file as OCR_REQUIRED — both text pages lost, the model never told.
A partial parse was stored READY with no trace of its unread pages. Synthetic text only
(rule 21)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist.agent import attachments, tools
from legalmind.ingestion import parsing
from tests.assist.agent.test_assist_attachments import _add, _chunks, _conversation

PDF = "application/pdf"
PAGE_ONE = "1. Fees. The Customer shall pay the monthly fee within thirty days of invoice."
PAGE_TWO = "2. Term. This agreement runs for twelve months from the effective date."
SCANNED = "Annex 3. Service credits are fifteen percent of the monthly fee."


def _pdf(native: list[str], scanned: list[str]) -> bytes:
    """Native-text pages, then image-only pages whose words exist only as pixels."""
    import pymupdf

    doc = pymupdf.open()
    for words in native:
        doc.new_page().insert_textbox(pymupdf.Rect(56, 56, 556, 736), words, fontsize=11)
    for words in scanned:
        src = pymupdf.open()
        src.new_page().insert_textbox(pymupdf.Rect(56, 56, 556, 736), words, fontsize=16)
        png = src[0].get_pixmap(dpi=200, colorspace="gray").tobytes("png")
        page = doc.new_page()
        page.insert_image(page.rect, stream=png)
    return doc.tobytes(deflate=True)


def _listed(db, conv) -> dict:
    ctx = tools.ToolContext(db=db, user_id=uuid4(), permissions=frozenset({"assist.ask"}),
                            conversation_id=conv, contract_id=None)
    (row,) = tools.list_attachments(ctx, tools.ListAttachmentsArgs()).attachments
    return row


@pytest.mark.skipif(not parsing.ocr_available(), reason="needs the OCR toolchain")
def test_a_short_file_with_a_scanned_page_is_read_whole_and_the_ocr_is_marked(db, user):
    conv = _conversation(db, user)
    att = _add(db, conversation_id=conv, data=_pdf([PAGE_ONE, PAGE_TWO], [SCANNED]),
               kind=attachments.FILE, filename="deal.pdf", mime=PDF)
    assert (att.status, att.failure_code, att.pages_unread) == ("READY", None, [])
    chunks = _chunks(db, att.id)
    joined = " ".join(c for c, _ in chunks)
    assert "monthly fee within thirty days" in joined and "twelve months" in joined
    ocr = [a for c, a in chunks if "fifteen percent" in c.lower()]
    assert ocr and ocr[0].get("read_by") == "OCR"
    assert not any(a.get("read_by") for c, a in chunks if "twelve months" in c)
    assert "pages_not_read" not in _listed(db, conv)
    # the reader's Sources say so too, not only the model (review 2026-10-16)
    from legalmind.assist import service
    ocr_id, native_id = (db.execute(text(
        f'SELECT id FROM "{config.assist_schema()}".attachment_chunks WHERE '
        "attachment_id = :a AND content ILIKE :w"), {"a": att.id, "w": w}).scalar()
        for w in ("%fifteen percent%", "%twelve months%"))
    views = service.source_views(db, [("U1", "t", None, f"ATT:{ocr_id}", None, "current"),
                                      ("U2", "t", None, f"ATT:{native_id}", None, "current")])
    assert views[0].get("read_by") == "OCR" and "read_by" not in views[1]


def test_above_the_bound_the_native_pages_stay_and_the_scan_is_disclosed(
        db, user, monkeypatch):
    # the toolchain is "present" so the file needs OCR; the bound says not here
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(attachments, "ATTACHMENT_OCR_MAX_PAGES", 0)
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = _conversation(db, user)
    att = _add(db, conversation_id=conv, data=_pdf([PAGE_ONE, PAGE_TWO], [SCANNED]),
               kind=attachments.FILE, filename="deal.pdf", mime=PDF)
    # was ("FAILED", "OCR_REQUIRED") with no chunks: both text pages lost
    assert (att.status, att.failure_code, att.pages_unread) == ("READY", None, [3])
    joined = " ".join(c for c, _ in _chunks(db, att.id))
    assert "thirty days" in joined and "twelve months" in joined
    assert _listed(db, conv)["pages_not_read"] == [3]       # the model is told
    found = attachments.file_segments(db, conv)
    assert found is not None
    _, parse = found
    # unread pages kept; no reviewable segments: a partial parse is never reviewed (AM-143 r5)
    assert parse["pages_failed"] == [3] and "segments" not in parse
    assert any("OCR not run" in d for d in parse["diagnostics"])


def test_a_long_scan_with_no_text_still_fails_as_ocr_required(db, user, monkeypatch):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(attachments, "ATTACHMENT_OCR_MAX_PAGES", 0)
    att = _add(db, conversation_id=_conversation(db, user), data=_pdf([], [SCANNED]),
               kind=attachments.FILE, filename="scan.pdf", mime=PDF)
    assert (att.status, att.failure_code) == ("FAILED", "OCR_REQUIRED")


def test_a_search_hit_carries_how_its_chunk_was_read(db, user):
    from legalmind.domain import enums as E
    conv = _conversation(db, user)
    seg = parsing.Segment(content=SCANNED, original_content=SCANNED,
                          source_type=E.EvidenceSourceType.OCR, page_number=1)
    att = attachments.add(db, conversation_id=conv, data=b"scan", kind=attachments.FILE,
                          mime=PDF, filename="scan.pdf", extracted=[seg])
    out = attachments.search(db, conversation_id=conv, query="service credits",
                             embed_query=None, attachment_id=att.id)
    assert [h.read_by for h in out.hits] == ["OCR"]
    stored = db.execute(text(
        f'SELECT annotations FROM "{config.assist_schema()}".attachment_chunks '
        "WHERE attachment_id = :a"), {"a": att.id}).scalar_one()
    assert stored["read_by"] == "OCR"


def test_the_same_bytes_or_one_file_too_many_are_settled_before_any_parse(
        db, user, monkeypatch):
    """Review 2026-10-16: a re-upload of a scan was OCR'd again every time, and an 11th
    file was OCR'd in full before being refused. Both are settled first now."""
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = _conversation(db, user)
    data = _pdf([PAGE_ONE], [])
    first = _add(db, conversation_id=conv, data=data, kind=attachments.FILE,
                 filename="a.pdf", mime=PDF)
    assert attachments.already_attached(db, conv, data, attachments.FILE) == first
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENT_MAX_FILES", "1")
    with pytest.raises(attachments.AttachmentRejected, match="TOO_MANY"):
        attachments.already_attached(db, conv, _pdf([PAGE_TWO], []), attachments.FILE)


def test_inline_ocr_past_its_time_bound_reads_the_text_layer_alone(monkeypatch):
    """Review 2026-10-16: 20 pages are not a time bound — a page job may take tesseract's
    120 s. Past ATTACHMENT_OCR_MAX_SECONDS the text layer is read and the request
    answers inside nginx's limit."""
    import time

    from legalmind.api.routers import assist as router
    real = parsing.parse
    monkeypatch.setattr(attachments, "ATTACHMENT_OCR_MAX_SECONDS", 0.2)

    def slow(data, mime, **kw):
        if kw.get("ocr", True):
            time.sleep(2)
        return real(data, mime, **kw)
    monkeypatch.setattr(parsing, "parse", slow)
    started = time.monotonic()
    result = router._ocr_within_bound(parsing, _pdf([PAGE_ONE], []), PDF)
    assert time.monotonic() - started < 1.5
    assert "thirty days" in " ".join(s.content for s in result.segments)
