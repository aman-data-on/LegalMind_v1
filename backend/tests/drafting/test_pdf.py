"""LibreOffice PDF of the CLEAN copy — no markup, page totals and xrefs as the DOCX says.

Skipped where no LibreOffice is configured (CI): set LEGALMIND_SOFFICE to run it."""

import os

import pymupdf
import pytest

from legalmind.drafting import clean, pdf, preflight
from tests.drafting.test_clean import _tracked_docx

pytestmark = pytest.mark.skipif(not os.environ.get("LEGALMIND_SOFFICE"),
                                reason="LEGALMIND_SOFFICE is not set: no LibreOffice here")


def _text(data: bytes) -> list[str]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [" ".join(page.get_text().split()) for page in doc]


def test_contract_pdf_matches_its_docx(rendered):
    model, digest, data = rendered
    fixed, result = pdf.convert_contract(data)
    assert result.libreoffice_version.startswith("LibreOffice ")
    assert preflight.check(fixed, model=model, pdf=result.pdf) == []
    pages = _text(result.pdf)
    ident = f"LM-TEST-v1-{digest[:8]}"
    # one run for the whole file: the schedules continue it (`FINAL-PACKAGE-SPEC` S1)
    assert [" ".join(p.split(ident)[1].split()[:4]) for p in pages] == [
        f"Page {n} of 4" for n in range(1, 5)]
    assert any("subject to clause 2.1 and clause 2.1.1.1.1." in p for p in pages)


def test_pdfa2b_clean(rendered):
    """`FINAL-PACKAGE-SPEC` c1/(g)7: the file a signing tool gets is PDF/A-2b, tagged,
    in en-IN, every font embedded, nothing but links, no form, script, attachment,
    encryption or layer, under 10 MB — and the export options are recorded."""
    fixed, result = pdf.convert_contract(rendered[2])
    data = result.pdf
    assert preflight.pdf_file(data) == []
    assert preflight.pdf_problems(fixed, data, ours=True) == []
    assert len(data) <= 10_000_000
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        xmp = doc.get_xml_metadata()
        assert "<pdfaid:part>2</pdfaid:part>" in xmp
        assert "<pdfaid:conformance>B</pdfaid:conformance>" in xmp
        cat = doc.pdf_catalog()
        assert doc.xref_get_key(cat, "OutputIntents")[0] == "array"
        assert doc.xref_get_key(cat, "Lang") == ("string", "en-IN")
        assert doc.xref_get_key(cat, "StructTreeRoot")[0] == "xref"      # tagged
        for key in ("AcroForm", "Names", "OCProperties", "OpenAction"):
            assert doc.xref_get_key(cat, key)[0] == "null", key
        assert not doc.metadata.get("encryption") and doc.embfile_count() == 0
        for page in doc:
            assert {t[1] for t in page.annot_xrefs()} <= {pymupdf.mupdf.PDF_ANNOT_LINK}
            assert all(f[1] != "n/a" for f in page.get_fonts(full=True))
    assert pdf.EXPORT["SelectPdfVersion"] == 2 and pdf.EXPORT["ExportFormFields"] is False


def test_a_contract_made_before_s1_still_passes(rendered):
    """H1: a version rendered by lm-render-contract-2 (bare page numbers restarting in
    each schedule) converts, with the S1 export, to a PDF its own page rule passes —
    its final copy is a PDF for signature, not a refusal."""
    from tests.drafting.test_preflight import renderer2
    fixed, result = pdf.convert_contract(renderer2(rendered[2]))
    assert preflight.pdf_problems(fixed, result.pdf, ours=True) == []
    ident = f"LM-TEST-v1-{rendered[1][:8]}"
    assert [p.split(ident)[1].split()[0] for p in _text(result.pdf)] == ["1", "2", "1", "1"]


def test_the_signature_page_is_the_last_page(placeholder, answers):
    """S2: with ``execution.last`` LibreOffice puts the whole signature table at the top
    of the file's last page, after both schedules; preflight passes, ``SIGNATURE_PAGE``
    included — and no e-sign tag text is in the file (c3: none by default)."""
    from tests.drafting.conftest import build
    template, clauses = placeholder
    template["layout"]["execution"]["last"] = True
    model, _, data = build(template, clauses, answers)
    fixed, result = pdf.convert_contract(data)
    assert preflight.check(fixed, model=model, pdf=result.pdf) == []
    pages = _text(result.pdf)
    assert [n for n, p in enumerate(pages) if "Signatory Details" in p] == [len(pages) - 1]
    assert "signatory.two@example.test" in pages[-1]
    assert pages[-2].count("Schedule B") >= 1
    assert not any("{{" in p or "\\s1\\" in p for p in pages)


def test_the_pdf_never_prints_tracked_changes():
    pages = " ".join(_text(pdf.convert(_tracked_docx()).pdf))
    assert "run inserted" in pages and "run deleted" not in pages
    assert "moved away" not in pages and "Placeholder comment" not in pages
    assert clean.has_markup(clean.clean(_tracked_docx())) == []


def test_no_soffice_is_a_refusal(monkeypatch, rendered):
    monkeypatch.delenv("LEGALMIND_SOFFICE")
    with pytest.raises(pdf.PdfError):
        pdf.convert(rendered[2])
