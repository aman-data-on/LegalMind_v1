"""Illegible native text is detected, never passed off as content — locked 34.3/34.9.

The defect (2026-09-03, found on a real upload). `MIN_USABLE_CHARS_PER_PAGE` asked
only whether text was PRESENT. A PDF whose embedded fonts carry an incorrect
`/ToUnicode` CMap yields plenty of characters that are the wrong ones — glyph
codes reinterpreted as text. The observed upload extracted its title as
"MaVWeU SeUYLceV AgUeePeQW" for "Master Services Agreement", with every character
at or above 0x6D shifted by −29. Nearly 2,000 characters on page 1 cleared the
presence check, so OCR was never attempted and the mojibake reached the document
viewer, the clause list, the retrieval index and — the part that matters — a
Review reporting MATCH findings against text nobody could read.

Locked 34.3 already requires detecting when extraction is *insufficient*, not
merely absent. These tests pin that reading, and pin the two properties that make
the fix safe rather than merely clever:

  * it CANNOT make a working document worse — the judgement is document-level and
    conservative, and OCR output is adopted only when measurably better;
  * when no legible text can be produced, the result is NO text and a FAILED
    status (45B.7 routes that to UNABLE_TO_EVALUATE), never unreadable text
    dressed as content.

The garbled specimen is synthesised here, not committed: locked 54.6 keeps real
documents out of this repository.
"""

from __future__ import annotations

import pytest

from legalmind.domain.enums import EvidenceSourceType, ExtractionStatus
from legalmind.ingestion import parsing
from legalmind.ingestion.parsing import (
    ILLEGIBLE_STOPWORD_SHARE,
    parse_pdf,
    stopword_share,
    text_is_legible,
)


def build_pdf(pages: list[str]) -> bytes:
    """A PDF carrying enough text per page to be judged.

    `test_ingestion.build_pdf` places one unwrapped `insert_text` run, which
    clips to a single line — fine for its own assertions, but under
    `MIN_WORDS_TO_JUDGE_LEGIBILITY` here, so legibility would report
    "unjudgeable" and nothing under test would run. This wraps into a text box
    so a page holds a realistic amount of prose.
    """
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(56, 56, 556, 736), text, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


# Ordinary legal prose, long enough to judge (>= MIN_WORDS_TO_JUDGE_LEGIBILITY).
LEGAL_PROSE = (
    "This Master Services Agreement is entered into on this day of April 2025 "
    "by and between the Company and the Customer. The Parties agree that the "
    "provision of the Services by the Company to the Customer shall be governed "
    "by the terms and conditions of this Agreement. Neither party shall be "
    "liable to the other for any indirect or consequential loss arising out of "
    "or in connection with this Agreement, and the aggregate liability of the "
    "Company shall not exceed the total fees paid by the Customer in the twelve "
    "months immediately preceding the event giving rise to the claim. "
) * 4


def mangle(text: str) -> str:
    """Reproduce the observed producer bug: shift every code point at or above
    0x6D down by 29, exactly as the broken CMap did."""
    return "".join(chr(ord(c) - 29) if 0x6D <= ord(c) <= 0x7A else c for c in text)


# =====================================================================
# The signal itself
# =====================================================================
def test_legal_prose_reads_as_legible():
    share = stopword_share(LEGAL_PROSE)
    assert share is not None and share >= ILLEGIBLE_STOPWORD_SHARE
    assert text_is_legible(LEGAL_PROSE) is True


def test_the_observed_mangling_reads_as_illegible():
    mangled = mangle(LEGAL_PROSE)
    assert "MaVWeU" in mangle("Master")  # the fixture reproduces the real bug
    share = stopword_share(mangled)
    assert share is not None and share < ILLEGIBLE_STOPWORD_SHARE
    assert text_is_legible(mangled) is False


@pytest.mark.parametrize("text", [
    "",
    "   \n  ",
    # A cover page or website footer: real text, but too little of it to judge.
    # Measured on the supplied corpus at 0.055-0.086 — which is why the parser
    # judges whole documents and never single pages.
    "Products Virtual Machines VPS Kubernetes Storage Networking GPU Cloud",
])
def test_too_little_text_is_unjudgeable_never_illegible(text):
    """`None`, not `False`. Only `False` may change what the parser does, so an
    unjudgeable page can never trigger a re-extraction."""
    assert stopword_share(text) is None
    assert text_is_legible(text) is None


def test_a_non_latin_document_is_unjudgeable_rather_than_illegible():
    """An English function-word list says nothing about Devanagari. Reporting it
    as illegible would send a correctly-extracted document to OCR and lose it."""
    hindi = "यह अनुबंध पक्षों के बीच किया गया है और इसकी शर्तें लागू होंगी। " * 30
    assert stopword_share(hindi) is None
    assert text_is_legible(hindi) is None


def test_the_threshold_separates_the_two_populations_it_was_measured_from():
    """Measured, not guessed: 0.210-0.422 across the 21 real corpus PDFs, 0.092
    for the garbled upload. The constant must stay between them."""
    assert 0.092 < ILLEGIBLE_STOPWORD_SHARE < 0.210


# =====================================================================
# End to end through parse_pdf
# =====================================================================
def test_a_legible_pdf_is_untouched_and_stays_native(monkeypatch):
    """The guard against making working documents worse: OCR must not even be
    considered for a document whose native text reads as language."""
    def fail(*a, **k):                       # pragma: no cover - must not run
        raise AssertionError("OCR was attempted on a legible document")
    monkeypatch.setattr(parsing, "_ocr_page", fail)

    result = parse_pdf(build_pdf([LEGAL_PROSE[:1200], LEGAL_PROSE[1200:2400]]))
    assert result.status is ExtractionStatus.COMPLETE
    assert result.segments
    assert all(s.source_type is EvidenceSourceType.NATIVE_TEXT
               for s in result.segments)
    assert not any("not legible" in d for d in result.diagnostics)


def test_illegible_native_text_is_not_returned_when_ocr_is_unavailable(monkeypatch):
    """The state this machine is actually in — no OCR toolchain installed.

    The honest outcome is NO text and FAILED, which 45B.7 turns into
    UNABLE_TO_EVALUATE. Returning the glyph stream would put unreadable text in
    front of a reviewer and into the evaluator, which is what produced MATCH
    findings against unreadable text on the live instance.
    """
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)
    result = parse_pdf(build_pdf([mangle(LEGAL_PROSE[:1200]),
                                  mangle(LEGAL_PROSE[1200:2400])]))

    assert result.segments == []
    assert result.status is ExtractionStatus.FAILED
    assert result.pages_failed == [1, 2]
    assert any("not legible" in d for d in result.diagnostics)
    assert any("OCR toolchain unavailable" in d for d in result.diagnostics)


def test_ocr_replaces_illegible_native_text_and_is_marked_as_ocr(monkeypatch):
    """34.3 and 34.8: OCR reads the rendered glyphs, which are correct, and the
    result is explicitly identified as OCR-derived rather than passed off as
    clean native text."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_page", lambda page: LEGAL_PROSE[:1400])

    result = parse_pdf(build_pdf([mangle(LEGAL_PROSE[:1200]),
                                  mangle(LEGAL_PROSE[1200:2400])]))

    assert result.status is ExtractionStatus.COMPLETE
    assert result.segments
    assert all(s.source_type is EvidenceSourceType.OCR for s in result.segments)
    # The unreadable native text is gone, not merged alongside.
    assert not any("SeUYLceV" in s.content or "AgUeePeQW" in s.content
                   for s in result.segments)
    assert any("re-extracted" in d and "OCR-derived" in d
               for d in result.diagnostics)


def test_ocr_that_is_no_better_is_discarded_rather_than_adopted(monkeypatch):
    """"Measurably better" is required, not assumed. A scanner that returns its
    own noise must not replace one unreadable extraction with another — and must
    not leave the native mojibake in place either, because that looks like
    content."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_page", lambda page: mangle(LEGAL_PROSE[:1400]))

    result = parse_pdf(build_pdf([mangle(LEGAL_PROSE[:1200])]))

    assert result.segments == []
    assert result.status is ExtractionStatus.FAILED
    assert any("OCR did not produce legible text either" in d
               for d in result.diagnostics)


def test_a_failing_ocr_toolchain_still_yields_no_invented_text(monkeypatch):
    """34.9 on the error path: an OCR crash is reported, never papered over."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)

    def boom(page):
        raise RuntimeError("tesseract died")
    monkeypatch.setattr(parsing, "_ocr_page", boom)

    result = parse_pdf(build_pdf([mangle(LEGAL_PROSE[:1200])]))
    assert result.segments == []
    assert result.status is ExtractionStatus.FAILED
    assert any("OCR failed" in d for d in result.diagnostics)


# =====================================================================
# The toolchain is now installed (2026-09-03) — so this path is live
# =====================================================================
def test_the_real_toolchain_recovers_an_illegible_document():
    """End to end through the REAL tesseract, not a stub.

    Skipped where the toolchain is absent, so the suite stays portable — but on
    a machine that has it, this is the only test that proves the whole chain:
    detect that native text is not language, rasterise, recognise, and come back
    with prose. Measured on the document that prompted the fix: a function-word
    share of 0.080 natively, 0.359 after OCR, against a legible band of
    0.210-0.422 across the real corpus.
    """
    if not parsing.ocr_available():
        pytest.skip("OCR toolchain not installed on this machine")

    # Reproducing the real bug takes care, and the first attempt here got it
    # WRONG in an instructive way. Rendering `mangle(source)` puts the mangled
    # characters on the page as actual glyphs, so OCR reads back exactly the
    # mangled text and correctly reports it as still illegible — a faithful
    # result for a fixture that does not resemble the defect.
    #
    # The real PDF is the other way round: the printed SHAPES are correct
    # English and only the character CODES behind them are wrong. So the page is
    # rendered from clean prose, and native extraction alone is made to lie —
    # which is precisely what a broken `/ToUnicode` CMap does. OCR then has
    # correct glyphs to recognise, exactly as it did on the real document.
    import pymupdf

    source = LEGAL_PROSE[:1600]
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(pymupdf.Page, "get_text",
                        lambda self, *a, **k: mangle(source))
    try:
        result = parse_pdf(build_pdf([source]))
    finally:
        monkeypatch.undo()

    assert result.status is ExtractionStatus.COMPLETE
    assert result.segments
    assert all(s.source_type is EvidenceSourceType.OCR for s in result.segments)

    recovered = "\n".join(s.content for s in result.segments)
    assert text_is_legible(recovered) is True
    # Real words, not glyph codes — and specific ones from the source.
    lowered = recovered.lower()
    assert "agreement" in lowered
    assert "liability" in lowered
    assert "aggreepeqw" not in lowered and "seuylcev" not in lowered
