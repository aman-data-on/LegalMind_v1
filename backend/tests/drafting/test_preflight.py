"""Preflight blocks a download or send: each refusal fires on the file that earns it."""

import copy
import io
import zipfile

import pymupdf
import pytest

from legalmind.drafting import preflight
from legalmind.drafting.preflight import PreflightRefused
from tests.drafting.test_clean import _tracked_docx


def _patch(data: bytes, name: str, old: bytes, new: bytes) -> bytes:
    src, out = zipfile.ZipFile(io.BytesIO(data)), io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n in src.namelist():
            body = src.read(n)
            if n == name:
                assert old in body, f"{old!r} not in {name}"
                body = body.replace(old, new, 1)
            z.writestr(n, body)
    return out.getvalue()


def _codes(data, **kw):
    return {p.code for p in preflight.check(data, **kw)}


def _append(data: bytes, text: str) -> bytes:
    """A body paragraph added at the end, before the body's closing w:sectPr."""
    doc = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml")
    head, tail = doc.rsplit(b"<w:sectPr", 1)
    para = f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'.encode()
    return _patch(data, "word/document.xml", doc, head + para + b"<w:sectPr" + tail)


def test_numbering_mismatch(rendered):
    model, _, data = rendered
    wrong = copy.deepcopy(model)
    wrong["body"][1]["number"] = "7"
    assert "NUMBERING" in _codes(data, model=wrong)


def test_ref_without_bookmark(rendered):
    data = _patch(rendered[2], "word/document.xml", b'w:name="_LM_CLAUSE_A_1"',
                  b'w:name="_LM_SOMETHING_ELSE"')
    assert "REF_NO_BOOKMARK" in _codes(data)


@pytest.mark.parametrize("text", ["Left {party_two_name} here.", "Fee of [ ] days."])
def test_slot_or_blank_left(rendered, text):
    assert "BLANK" in _codes(_append(rendered[2], text))


def test_revisions_or_comments_in_a_clean_copy():
    assert "MARKUP" in _codes(_tracked_docx())
    assert "MARKUP" not in _codes(_tracked_docx(), clean_copy=False)


def test_external_relationship(rendered):
    data = _patch(rendered[2], "word/_rels/document.xml.rels", b"</Relationships>",
                  b'<Relationship Id="rIdX" Type="http://schemas.openxmlformats.org/'
                  b'officeDocument/2006/relationships/hyperlink" Target="https://example.test"'
                  b' TargetMode="External"/></Relationships>')
    assert "EXTERNAL_RELATIONSHIP" in _codes(data)


def test_image_without_alt_text_or_resolution(rendered):
    data = _patch(rendered[2], "word/document.xml",
                  b'descr="Placeholder figure: three boxes joined by lines"', b'descr=""')
    assert "IMAGE_ALT" in _codes(data)
    doc = zipfile.ZipFile(io.BytesIO(rendered[2])).read("word/document.xml")
    cx = doc.split(b'<wp:extent cx="')[1].split(b'"')[0]
    huge = _patch(rendered[2], "word/document.xml", b'<wp:extent cx="' + cx,
                  b'<wp:extent cx="' + str(int(cx) * 10).encode())
    assert "IMAGE_RESOLUTION" in _codes(huge)


def test_undefined_quoted_term(rendered):
    data = _append(rendered[2], "As the “Unknown Placeholder” provides.")
    assert "UNDEFINED_TERM" in _codes(data)
    assert "UNDEFINED_TERM" not in _codes(rendered[2])
    for defined in ("Here “Alpha Term” or “Beta Term” shall mean a placeholder.",
                    "A placeholder (together, the “Gamma Term”).",
                    "In it, \"Delta Term\" means a placeholder.",
                    # 1.1.2 of our MSA: derived forms of “Control” (2026-11-04)
                    "“Control” means a placeholder, and the words “Epsilon Term” or "
                    "“Zeta Term” shall be construed accordingly."):
        term = defined.split("“")[-1].split("”")[0] if "“" in defined else "Delta Term"
        assert "UNDEFINED_TERM" not in _codes(_append(rendered[2], defined + f" Use “{term}”."))


def test_cross_reference_to_no_clause(rendered):
    data = _append(rendered[2], "Placeholder text, subject to Clause 4.9.")
    assert "CROSS_REFERENCE" in _codes(data)


def _pdf(*pages: str, furniture: str = "", unicode: bool = False) -> bytes:
    """Each text in the page body (inside the house margins); ``furniture`` in the
    header and footer of every page (``{n}``/``{total}``: the page and the page count).
    ``unicode``: in an embedded font that has “ ” — (the base font has not)."""
    doc = pymupdf.open()
    for n, text in enumerate(pages, 1):
        page = doc.new_page()
        font = "helv"
        if unicode:
            font = "U"
            page.insert_font(fontname=font, fontbuffer=pymupdf.Font("tiro").buffer)
        assert page.insert_textbox(pymupdf.Rect(40, 110, 560, 760), text, fontsize=6,
                                   fontname=font) >= 0, "the text does not fit"
        if furniture:
            shown = furniture.format(n=n, total=len(pages))
            page.insert_text((72, 45), shown, fontsize=9)
            page.insert_text((72, 800), shown, fontsize=9)
    doc.subset_fonts()
    return doc.tobytes()


def _body_text(data: bytes) -> str:
    """The DOCX body as the PDF prints it: each paragraph after its list label."""
    import docx
    document = docx.Document(io.BytesIO(data))
    paras = document.element.body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    labels = preflight._docx_list_numbers(document, paras, labels=True)
    return " ".join(f"{labels.get(p, '')} {preflight._docx_text(p)}" for p in paras)


def test_pdf_checks_fire(rendered):
    model, _, data = rendered
    codes = _codes(data, model=model, pdf=_pdf(
        "Clause B text, subject to clause 9.9 and clause 2.1.1.1.1.",
        "Signatory Details By", furniture="LM-T-v1-0123abcd Page {n} of 3"))
    assert {"EXECUTION_SPLIT", "XREF_PDF", "PAGE_NUMBERS", "TEXT_EQUAL", "PDFA",
            "FONT_NOT_EMBEDDED"} <= codes
    past = pymupdf.open()
    past.new_page().insert_text((560, 100), "past the margin", fontsize=9)
    assert "MARGIN" in _codes(data, model=model, pdf=past.tobytes())


def test_xref_pdf_ignores_a_space_before_punctuation(rendered):
    """MSA 8.2, 2026-11-04: the PDF text layer read “Payment : All” for the
    run-in title's “Payment: All” — the same words and number, not a stale field."""
    model, _, data = rendered
    body = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml")
    paras = [p for p in preflight.parse_xml(body).iter(preflight._W + "p")
             if any(preflight._REF.search(f.get(preflight._W + "instr", ""))
                    for f in p.iter(preflight._W + "fldSimple"))]
    texts = [preflight._norm(preflight._docx_text(p)) for p in paras]
    texts = [t for t in texts if t.isascii()]     # the test PDF's base font has no “ ”
    assert texts
    loose = [t.replace(",", " ,").replace(".", " .") for t in texts]
    flagged = [p.detail for p in preflight.check(data, model=model, pdf=_pdf(" ".join(loose)))
               if p.code == "XREF_PDF"]
    assert not [t for t in texts if any(t[:40] in d for d in flagged)], flagged


def test_xref_pdf_reads_a_paragraph_across_a_page_break(rendered):
    """MSA 17.7, 2026-11-05: the data-loss paragraph ran from page 16 onto page 17,
    the header and footer between its halves — the same words, not a stale field."""
    model, _, data = rendered
    body = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml")
    texts = [preflight._norm(preflight._docx_text(p))
             for p in preflight.parse_xml(body).iter(preflight._W + "p")
             if any(preflight._REF.search(f.get(preflight._W + "instr", ""))
                    for f in p.iter(preflight._W + "fldSimple"))]
    texts = [t for t in texts if t.isascii() and len(t.split()) > 3]
    assert texts
    words = " ".join(texts).split()
    half = len(words) // 2
    pages = (" ".join(words[:half]), " ".join(words[half:]))
    flagged = [p.detail for p in preflight.check(
        data, model=model, pdf=_pdf(*pages, furniture="DRAFT LM-T-v1-0123abcd Page {n} "
                                    "of {total}"))
        if p.code == "XREF_PDF"]
    assert not [t for t in texts if any(t[:40] in d for d in flagged)], flagged


def test_text_equal(rendered):
    """`TEXT_EQUAL`: the whole body, list labels included, reads the same in the PDF —
    however its lines break, its spaces fall or its headings are capitalised; one word
    changed, or a paragraph lost, is refused and the place quoted."""
    model, _, data = rendered
    text = _body_text(data)
    # the labels Word prints, computed from the numbering part (not by the code tested)
    assert "A. Party One Placeholder Limited" in text and "(a) Second list item one." \
        in text and "4.1. Clause C.1 text" in text
    page = "LM-T-v1-0123abcd Page {n} of {total}"

    def text_equal(body: str) -> list[str]:
        return [p.detail for p in preflight.check(
            data, model=model, pdf=_pdf(body, furniture=page, unicode=True))
            if p.code == "TEXT_EQUAL"]
    loose = "  ".join(text.upper().split()).replace(":", " :")   # wrapped by the box
    assert text_equal(loose) == []
    changed = text_equal(text.replace("Clause C.1 text", "Clause C.1 test"))
    assert len(changed) == 1 and "c.1 test" in changed[0] and "c.1 text" in changed[0]
    assert text_equal(text.replace("Second list item one.", ""))


def test_page_x_of_y(rendered):
    """Footers read "Page 1 of N" … "Page N of N": once each, in order, N the count."""
    model, _, data = rendered

    def pages(furniture: str, n: int = 3) -> list[str]:
        return [p.detail for p in preflight.check(
            data, model=model, pdf=_pdf(*["Body."] * n, furniture=furniture))
            if p.code == "PAGE_NUMBERS"]
    assert pages("LM-T-v1-0123abcd Page {n} of {total}") == []
    assert pages("LM-T-v1-0123abcd Page {n} of 4")            # Y is not the page count
    assert pages("LM-T-v1-0123abcd Page 1 of {total}")        # a restart
    assert pages("LM-T-v1-0123abcd {n}")                      # the old bare number
    assert pages("") == ["pages read ['no number', 'no number', 'no number'], a file "
                         "of 3 pages"]


def test_signature_split_refused(rendered):
    """The execution table across a page break is refused; on one page it passes."""
    model, _, data = rendered
    body = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml")
    sdt = next(s for s in preflight.parse_xml(body).iter(preflight._W + "sdt")
               if s.find(f"{preflight._W}sdtPr/{preflight._W}tag").get(
                   preflight._W + "val") == "lm:execution")
    words = preflight._norm(" ".join(preflight._docx_text(p)
                                     for p in sdt.iter(preflight._W + "p"))).split()
    half = len(words) // 2

    def split(*pages: str) -> bool:
        return "EXECUTION_SPLIT" in _codes(data, model=model, pdf=_pdf(*pages))
    assert split(" ".join(words[:half]), " ".join(words[half:]))
    assert not split("Clause text.", " ".join(words))


def test_pdf_file_checks_fire():
    """What a signing input must never carry, each refused by its own code."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 120), "Body.", fontsize=9)            # helv: not embedded
    page.add_text_annot((72, 200), "a note")
    widget = pymupdf.Widget()
    widget.field_name, widget.field_type = "f", pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(72, 300, 200, 320)
    page.add_widget(widget)                                      # an AcroForm
    doc.embfile_add("source.docx", b"PK")
    doc.add_ocg("layer")
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction",
                     "<</S/JavaScript/JS(app.alert(1))>>")
    data = doc.tobytes()
    codes = {p.code for p in preflight.pdf_file(data)}
    assert codes == {"PDFA", "FONT_NOT_EMBEDDED", "ANNOTATION", "ACROFORM", "JAVASCRIPT",
                     "EMBEDDED_FILE", "OPTIONAL_CONTENT"}
    locked = pymupdf.open()
    locked.new_page()
    sealed = locked.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o",
                            permissions=0)
    assert "ENCRYPTED" in {p.code for p in preflight.pdf_file(sealed)}
    big = {p.code for p in preflight.pdf_file(sealed + b"%" * preflight.MAX_PDF_BYTES)}
    assert "PDF_TOO_LARGE" in big


def test_require_raises_with_every_problem(rendered):
    data = _append(rendered[2], "{x} [ ]")
    with pytest.raises(PreflightRefused) as exc:
        preflight.require(data)
    assert [p.code for p in exc.value.problems] == ["BLANK"]
