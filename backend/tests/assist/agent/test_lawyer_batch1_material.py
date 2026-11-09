"""Lawyer batch 1 (owner, 2026-11-09), chat material: a photo or screenshot read by OCR
(B1.1, P1), the pictures in a file said in fixed words and never read as a signature
(B1.2, P2), and each chat file labelled read WHOLE or IN PART, the absence rule applying
only to a file read whole (B1.3, P3). Synthetic text only (rule 21); no model call."""
import pymupdf
import pytest

from legalmind.assist.agent import attachments
from legalmind.assist.agent.tools import _stems
from legalmind.assist.verification import agent_verify as av
from legalmind.ingestion import parsing
from legalmind.ingestion.validation import PDF_MIME, UploadRejected, validate_upload
from tests.assist.agent.test_assist_attachments import _add, _chunks, _conversation
from tests.assist.integration.test_assist_ask import storage  # noqa: F401  (fixture)

needs_tesseract = pytest.mark.skipif(not parsing.ocr_available(),
                                     reason="tesseract is not installed here")

CLAUSE = ("17.2 Limitation of Liability. The aggregate liability of the Provider shall "
          "not exceed the fees paid by the Customer in the six (6) months preceding the "
          "claim.")


def _screenshot(text=CLAUSE, fmt="png") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=300)
    page.insert_textbox(pymupdf.Rect(20, 20, 580, 280), text, fontsize=13)
    return page.get_pixmap(dpi=150).tobytes(fmt)


def _words(s: str) -> str:
    return " ".join(s.split())


# ------------------------------------------------------------------------- B1.1 images
@needs_tesseract
def test_image_attachment_a_screenshot_is_read_by_ocr(db, user):
    c = _conversation(db, user)
    a = _add(db, conversation_id=c, data=_screenshot(), kind=attachments.FILE,
             filename="clause.png", mime="image/png")
    assert (a.status, a.mime_type) == ("READY", "image/png")
    rows = _chunks(db, a.id)
    assert len(rows) == 1 and _words(rows[0].content) == _words(CLAUSE)
    assert rows[0].annotations["read_by"] == "OCR"
    # the photo is one picture covering its page, and its text was read
    assert attachments.picture_lines(a.pictures) == [
        "Page 1: a picture covering the whole page; its text was read by OCR."]


@needs_tesseract
def test_image_attachment_a_jpeg_photo_is_read_too(db, user):
    c = _conversation(db, user)
    a = _add(db, conversation_id=c, data=_screenshot(fmt="jpg"), kind=attachments.FILE,
             filename="photo.jpg", mime="image/jpeg")
    assert a.status == "READY" and "Limitation of Liability" in _chunks(db, a.id)[0].content


@pytest.mark.parametrize("data, declared, code", [
    (_screenshot(), PDF_MIME, "CONTENT_TYPE_MISMATCH"),          # a PNG renamed .pdf
    (b"%PDF-1.7 not an image", "image/png", "CONTENT_TYPE_MISMATCH"),
    (b"plain bytes that are no image", "image/png", "UNRECOGNISED_CONTENT"),
])
def test_image_attachment_a_mismatch_is_refused_as_any_mismatch(db, user, data, declared,
                                                                code):
    c = _conversation(db, user)
    with pytest.raises(attachments.AttachmentRejected) as e:
        _add(db, conversation_id=c, data=data, kind=attachments.FILE,
             filename="x.png", mime=declared)
    assert e.value.code == code


def test_image_attachment_a_huge_image_is_shrunk_to_one_a4_page_of_ocr():
    big = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 6000, 6000), False)
    big.clear_with(255)
    page = pymupdf.open(stream=parsing.image_to_pdf(big.tobytes("png"))).load_page(0)
    side = max(page.rect.width, page.rect.height) * parsing.OCR_RENDER_DPI / 72
    assert side <= parsing.IMAGE_MAX_SIDE_PX


def test_image_attachment_the_dashboard_still_refuses_a_picture():
    with pytest.raises(UploadRejected) as e:
        validate_upload(_screenshot(), "clause.png", "image/png")
    assert e.value.code == "UNSUPPORTED_TYPE"


# --------------------------------------------------------------------- B1.2 pictures
def _pdf_with_pictures() -> bytes:
    """A logo (~5% of page 1, at the top) and a small picture at the foot of page 3."""
    doc = pymupdf.open()
    tile = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    tile.clear_with(120)
    for n in range(3):
        page = doc.new_page(width=600, height=800)
        page.insert_textbox(pymupdf.Rect(40, 200, 560, 600),
                            f"{n + 1}. Clause {n + 1}. " + "The parties agree. " * 30,
                            fontsize=11)
    doc[0].insert_image(pymupdf.Rect(40, 20, 190, 180), pixmap=tile)      # 5.0%
    doc[2].insert_image(pymupdf.Rect(400, 660, 540, 800), pixmap=tile)    # 4.1%
    return doc.tobytes()


def test_pictures_are_recorded_with_page_and_position():
    data = _pdf_with_pictures()
    parsed = parsing.parse(data, PDF_MIME, docling=False)
    pictures = parsing.pictures(data, PDF_MIME, parsed.segments)
    assert [(p["page"], p["position"], p["read"]) for p in pictures] == [
        (1, "top", False), (3, "bottom", False)]
    assert attachments.picture_lines(pictures) == [
        "Page 1: a small picture near the top (it may be a logo); its content was not "
        "read.",
        "Page 3: a small picture near the foot; its content was not read."]


def test_pictures_never_change_what_the_parser_reads():
    """B1.2 check 4: pictures are read beside the parse — every OCR decision and every
    segment is byte-identical with or without them."""
    data = _pdf_with_pictures()
    before = parsing.parse(data, PDF_MIME, docling=False)
    parsing.pictures(data, PDF_MIME, before.segments)
    after = parsing.parse(data, PDF_MIME, docling=False)
    assert [(s.content, s.source_type, s.page_number) for s in before.segments] == \
        [(s.content, s.source_type, s.page_number) for s in after.segments]


def test_pictures_and_how_a_file_was_read_reach_the_model(db, user):
    """B1.2 check 2 and B1.3: the model's context names each picture, and whether the
    file was read WHOLE or IN PART."""
    from legalmind.assist.agent import agent, tools
    c = _conversation(db, user)
    a = _add(db, conversation_id=c, data=_pdf_with_pictures(), kind=attachments.FILE,
             filename="msa.pdf", mime=PDF_MIME)
    assert a.status == "READY" and len(a.pictures) == 2
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=frozenset(
        {"assist.ask"}), conversation_id=c)
    whole = agent._inline_material(ctx, agent.EvidenceRegistry(db, c))
    text = " ".join(whole.blocks)
    assert "read WHOLE" in text and whole.whole == [a.id] and whole.all_whole
    assert "Page 1: a small picture near the top (it may be a logo)" in text
    assert "Page 3: a small picture near the foot" in text
    assert "never evidence that it is signed, stamped or executed" in text
    part = agent._inline_material(ctx, agent.EvidenceRegistry(db, c), limit=100)
    joined = " ".join(part.blocks)
    assert "searched IN PART (0 of" in joined and part.whole == [] \
        and not part.all_whole
    assert "<user_material" not in joined          # nothing inlined; search reaches it


# ----------------------------------------------------------------- B1.3 absence rule
NO_CAP = "This file has no liability cap."


def test_an_absence_said_of_a_whole_file_is_its_own_fact():
    """B1.3 check 4 (P3): read WHOLE, a file whose text names no liability is a closed
    world — the sentence is not held to a clause that would have to state it."""
    passages = (frozenset(_stems("The Customer shall pay within 30 days of invoice.")),)
    assert av._checked_part(NO_CAP, frozenset(), passages) == ""


def test_an_absence_said_of_a_file_read_in_part_is_still_checked():
    assert av._checked_part(NO_CAP, frozenset(), ()) == NO_CAP
    # read whole, but the file does speak of liability: the clause must bear it out
    passages = (frozenset(_stems("The Provider's liability is limited to the fees.")),)
    assert av._checked_part(NO_CAP, frozenset(), passages) == NO_CAP


@pytest.mark.parametrize("pages, lean, label", [
    (18, False, "read WHOLE"),          # ~70k characters: inlined whole
    (60, False, "searched IN PART"),    # ~230k: past INLINE_MATERIAL_CHARS
    (18, True, "searched IN PART"),     # the lean model's 24k
])
def test_a_file_is_labelled_whole_or_in_part_by_its_size(db, user, pages, lean, label):
    """B1.3 checks 1-3, on a text file of about 3,900 characters a page."""
    from legalmind.assist.agent import agent, tools
    c = _conversation(db, user)
    body = "\n\n".join(f"{n}. Clause {n}. " + f"The obligations of clause {n} apply. " * 100
                       for n in range(1, pages + 1))
    a = _add(db, conversation_id=c, data=body.encode(), kind=attachments.FILE,
             filename="long.txt", mime="text/plain")
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=frozenset(
        {"assist.ask"}), conversation_id=c)
    got = agent._inline_material(ctx, agent.EvidenceRegistry(db, c),
                                 limit=agent.LEAN_MATERIAL_CHARS if lean else None)
    assert label in got.blocks[0] and (a.id in got.whole) is (label == "read WHOLE")


def test_a_scan_with_a_picture_on_every_page_is_one_line():
    """Recheck D5: twenty identical page pictures are one line with the page range."""
    pictures = [{"page": n, "share": 1.0, "position": "middle", "read": True}
                for n in range(1, 21)]
    assert attachments.picture_lines(pictures) == [
        "Pages 1-20: a picture covering the whole page; its text was read by OCR."]


@needs_tesseract
def test_a_screenshot_or_a_clause_is_never_reviewed_as_a_whole_contract(db, user):
    """Recheck D4 (`AM-143` r5): a screenshot of one clause, or a file of a clause or two,
    is part of a document — the whole-contract review would report every other clause
    missing, so it is never run; a contract with its clauses still is a whole one."""
    c = _conversation(db, user)
    shot = _add(db, conversation_id=c, data=_screenshot(), kind=attachments.FILE,
                filename="clause.png", mime="image/png")
    parse = attachments.files_segments(db, c)[0][1]
    assert attachments.is_fragment(shot, parse)
    clause = _add(db, conversation_id=c, data=CLAUSE.encode(), kind=attachments.FILE,
                  filename="clause.txt", mime="text/plain")
    by_id = {a.id: (a, p) for a, p in attachments.files_segments(db, c)}
    assert attachments.is_fragment(*by_id[clause.id])
    whole = "\n\n".join(f"{n}. Clause {n}. The parties agree to the terms of clause {n}."
                        for n in range(1, 6))
    full = _add(db, conversation_id=c, data=whole.encode(), kind=attachments.FILE,
                filename="contract.txt", mime="text/plain")
    by_id = {a.id: (a, p) for a, p in attachments.files_segments(db, c)}
    assert not attachments.is_fragment(*by_id[full.id])
