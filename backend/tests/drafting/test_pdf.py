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
    assert [p.split(ident)[1].split()[0] for p in pages] == ["1", "2", "1", "1"]
    assert any("subject to clause 2.1 and clause 2.1.1.1.1." in p for p in pages)


def test_the_pdf_never_prints_tracked_changes():
    pages = " ".join(_text(pdf.convert(_tracked_docx()).pdf))
    assert "run inserted" in pages and "run deleted" not in pages
    assert "moved away" not in pages and "Placeholder comment" not in pages
    assert clean.has_markup(clean.clean(_tracked_docx())) == []


def test_no_soffice_is_a_refusal(monkeypatch, rendered):
    monkeypatch.delenv("LEGALMIND_SOFFICE")
    with pytest.raises(pdf.PdfError):
        pdf.convert(rendered[2])
