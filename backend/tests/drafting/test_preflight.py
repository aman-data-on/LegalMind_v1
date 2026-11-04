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


def _pdf(*pages: str) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_textbox(pymupdf.Rect(40, 40, 560, 800), text, fontsize=9)
    return doc.tobytes()


def test_pdf_checks_fire(rendered):
    model, _, data = rendered
    codes = _codes(data, model=model, pdf=_pdf(
        "Clause B text, subject to clause 9.9 and clause 2.1.1.1.1. LM-T-v1-0123abcd 1",
        "Signatory Details By LM-T-v1-0123abcd 3"))
    assert {"EXECUTION_SPLIT", "XREF_PDF", "PAGE_NUMBERS"} <= codes
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


def test_require_raises_with_every_problem(rendered):
    data = _append(rendered[2], "{x} [ ]")
    with pytest.raises(PreflightRefused) as exc:
        preflight.require(data)
    assert [p.code for p in exc.value.problems] == ["BLANK"]
