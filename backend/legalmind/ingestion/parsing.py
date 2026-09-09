"""Document parsing and normalization — locked Step 34.

The governing rule is locked 34.9: **extraction failures never result in
invented text or legal conclusions.** Every branch here either produces text
that genuinely came from the document, or reports failure.

Locked rules implemented:
  34.6   native PDF/DOCX text extraction preferred
  34.7   OCR used when a supported PDF has no usable text
  34.8   OCR-derived content explicitly identified
  34.9   failures never invent text
  34.10  partial extraction explicitly represented
  34.11  pages, sections, paragraphs, tables preserved where available
  34.12  existing clause numbering preserved
  34.13  source locations retained for Evidence
  34.14  original extracted text preserved alongside normalized text
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field

from legalmind.domain.enums import EvidenceSourceType, ExtractionStatus
from legalmind.ingestion.validation import DOCX_MIME, PDF_MIME

# A page yielding fewer than this many characters of native text is treated as
# having no usable text (34.7). Deliberately low: the threshold decides whether
# to attempt OCR, never what the text says.
MIN_USABLE_CHARS_PER_PAGE = 20

# --------------------------------------------------------------------------
# Legibility — locked 34.3, "detect when normal extraction is INSUFFICIENT"
# --------------------------------------------------------------------------
# The defect this closes (2026-09-03). `MIN_USABLE_CHARS_PER_PAGE` asks only
# whether text is PRESENT. A PDF whose embedded fonts carry a wrong `/ToUnicode`
# CMap yields plenty of characters that are simply the wrong ones — the glyph
# codes reinterpreted as text. Observed on a real upload: an MSA extracted as
#
#     "MaVWeU SeUYLceV AgUeePeQW ... a cRmSan\ incRUSRUaWed XndeU Whe"
#
# for "Master Services Agreement ... a company incorporated under the". Every
# character at or above 0x6D had been shifted by −29 by the producer's broken
# CMap. That passed the presence check with ~1,960 characters on page 1, so OCR
# was never attempted, and the mojibake flowed into evidence, the clause list,
# the chunk index and — worst — a Review that reported MATCH findings against
# text nobody could read.
#
# A `/ToUnicode` CMap that is present and syntactically valid but semantically
# wrong is indistinguishable from a correct one by inspecting the PDF, so the
# signal has to come from the extracted text itself.
#
# WHY A REPAIR IS NOT ATTEMPTED. Inverting the observed shift was tried as a
# diagnostic and does recover the body text — while corrupting every capital,
# because the shifted range collides with the upper-case block ("Strad" became
# "ptrad"). A remap that silently damages some characters to fix others is
# exactly the invented text 34.9 forbids. OCR reads the RENDERED glyphs, which
# are correct, so it is the only honest route — and it is the route 34.3 already
# prescribes for insufficient extraction.
#
# THE SIGNAL. The share of alphabetic tokens that are common English function
# words. Legal prose is saturated with them; a glyph-code stream is not,
# because the mapping destroys them ("the" → "Whe", "of" → "Rf", "to" → "WR").
# It is a fixed 24-word list, not a dictionary and not a model: deterministic,
# offline, and cheap.
#
# THE THRESHOLD, measured rather than guessed. Across the 21 real PDFs in the
# supplied corpus and the statute set, document-level shares ran 0.210 (a
# policy page dense with product nouns) to 0.422 (Companies Act). The garbled
# upload measured 0.092, and 0.345 once the shift was undone — i.e. inside the
# healthy band, confirming both the signal and the gap. 0.15 sits between the
# two populations: 29% below the lowest legitimate document, 63% above the
# garbled one.
LEGIBILITY_STOPWORDS = frozenset({
    "the", "of", "to", "and", "in", "a", "is", "that", "for", "it", "as",
    "with", "be", "on", "by", "or", "this", "are", "from", "at", "not",
    "which", "shall", "any",
})

#: Below this share of function words, a Latin-script document's extracted text
#: is treated as illegible rather than as content.
ILLEGIBLE_STOPWORD_SHARE = 0.15

#: Judged at DOCUMENT level and never per page. Measured on the same corpus: a
#: cover page, a signature page and a website footer legitimately score 0.055 to
#: 0.086 because they are noun lists with almost no prose. Deciding per page
#: would send correctly-extracted pages to OCR and make good text worse.
MIN_WORDS_TO_JUDGE_LEGIBILITY = 200

#: The share of a text's characters that must be plain ASCII before an English
#: function-word test means anything. A document in another script scores near
#: zero on that list for reasons that have nothing to do with extraction
#: quality, so it is reported as unjudgeable and left exactly as extracted.
MIN_ASCII_SHARE_TO_JUDGE = 0.85

#: Longest single line still read as a HEADING rather than a clause with a body.
#: A heading is a label; past this it is prose that happens to start with a
#: number, and calling it a heading would put body text in a table of contents.
#: 80 rather than 120 since 2026-09-05: every genuine heading in the owner's MSA
#: is under 40 characters, and the one false positive was 104.
HEADING_MAX_CHARS = 80

#: A heading is a few words. Sixteen words is a sentence.
HEADING_MAX_WORDS = 10

#: How long the NEXT line must be for a short title-like line to count as an
#: unnumbered heading — i.e. for prose to be following it rather than another
#: list item. Separates "Cancellations" above a paragraph from "Kubernetes" in a
#: navigation menu.
HEADING_PROSE_CHARS = 60


@dataclass
class Segment:
    """One unit of extracted content, destined for document_evidence.

    ``content`` is the normalized text; ``original_content`` is what the parser
    actually returned (34.14 — both are preserved). ``section_number`` is
    captured only when the document states it (34.12 — numbering is preserved,
    never generated).
    """

    content: str
    original_content: str
    source_type: EvidenceSourceType
    page_number: int | None = None
    section_number: str | None = None
    section_title: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    segments: list[Segment]
    status: ExtractionStatus
    pages_total: int = 0
    pages_extracted: int = 0
    pages_failed: list[int] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    #: True when the caller asked for OCR to be deferred (``defer_ocr``) and this
    #: document needs it. The result then carries NO segments and its ``status``
    #: is provisional — the caller must not persist it as the document's
    #: extraction outcome; the outcome belongs to the later OCR run (42.5 gives
    #: OCR its own ProcessingRunType for exactly this attempt-history shape).
    needs_ocr: bool = False
    #: Where page numbers came from, recorded on the processing run (34.13's
    #: spirit — a location is only as good as its provenance). ``None`` when the
    #: document yielded no page model. PDF pages are physical; DOCX pages come
    #: from the file's OWN pagination record (see _docx_paragraph_pages).
    pagination_source: str | None = None


class ParseError(Exception):
    """Raised only for conditions that make the document unreadable."""


# --------------------------------------------------------------------------
# Normalization — locked 34.12
# --------------------------------------------------------------------------
def normalize_text(raw: str) -> str:
    """Whitespace normalization only.

    Deliberately conservative: it collapses runs of whitespace and normalizes
    line endings. It does NOT correct spelling, expand abbreviations, repair
    OCR errors or alter numbers — locked 45C.18 permits normalizing an OCR
    error only when deterministic, and this layer cannot establish that.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    # The third character in this class is U+00A0 NO-BREAK SPACE, deliberately: PDF
    # extraction emits them freely, and a clause whose spacing differs only by an
    # nbsp must normalize to the same text, or `ENG-11` determinism would depend on
    # which producer wrote the file. Not an error to "fix" to an ASCII space.
    text = re.sub(r"[ \t ]+", " ", text)  # noqa: RUF001
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Clause numbering as documents actually write it: "8.", "8.2", "12.3.4",
# "Section 8", "ARTICLE IV", "(a)". Recognition only — never invention.
_CLAUSE_PATTERNS = (
    # A clause number ALONE on its line, with its text on the next — a common
    # PDF layout artifact, and 4 clauses of the owner's own MSA (17.1, 17.2,
    # 14.3) were lost to it. At least one sub-level is REQUIRED: that is what
    # keeps a bare year ("1999.") and a bare page number ("12") out, because
    # neither carries an interior dot. A top-level "17." alone stays unmatched
    # for the same reason — conservative in the direction that cannot invent.
    re.compile(r"^(?P<num>\d+(?:\.\d+)+)\.?$(?P<title>)"),
    re.compile(r"^(?P<num>\d+(?:\.\d+)*)\.?\s+(?P<title>[A-Z][^\n]{0,120})?"),
    re.compile(r"^(?:Section|SECTION|Clause|CLAUSE)\s+(?P<num>\d+(?:\.\d+)*)"
               r"\.?\s*(?P<title>[^\n]{0,120})?"),
    re.compile(r"^(?:Article|ARTICLE)\s+(?P<num>[IVXLC]+|\d+)"
               r"\.?\s*(?P<title>[^\n]{0,120})?"),
)


def detect_clause_number(line: str) -> tuple[str | None, str | None]:
    """Return (section_number, section_title) if the line states one.

    Locked 34.12 — existing clause numbering is *preserved*. If the document
    does not state a number, this returns ``None``; a number is never generated,
    because a fabricated section reference would corrupt evidence traceability.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return None, None
    for pattern in _CLAUSE_PATTERNS:
        m = pattern.match(stripped)
        if m:
            title = (m.group("title") or "").strip(" .:-") or None
            return m.group("num"), title
    return None, None


def _split_at_clause_lines(block: str) -> list[tuple[int, str]]:
    """Cut one blank-line block at the lines that state a clause number.

    WHY THIS EXISTS. Blank lines are a property of whoever produced the PDF, not
    of the document. A DOCX exported through one converter separates paragraphs
    with a blank line and segments perfectly; the same contract exported through
    another emits one newline per visual line and no blank line at all, so an
    entire page arrives as a single block. Measured on the real corpus: the same
    MSA gave 356 segments as .docx and 32 as .docx.pdf — 28 pages, one segment
    per page, 3,000+ characters each. Clause numbering was still there in the
    text; it simply never began a block, and only a block's FIRST line was read.

    So the document's own numbering is used as a second boundary. This invents
    nothing (34.12): a line is a boundary only when `detect_clause_number` — the
    same detector that already labels segments — recognises it. Deterministic,
    text in / offsets out, so ENG-11 holds.

    Returns (offset within the block, text) so the caller can keep every
    segment's absolute offsets exact (34.13 traceability).
    """
    lines = block.split("\n")
    cuts: list[tuple[int, str]] = []
    current: list[str] = []
    start = 0
    offset = 0
    after_number = False
    for index, line in enumerate(lines):
        number, _ = detect_clause_number(line)
        following = lines[index + 1] if index + 1 < len(lines) else None
        boundary = bool(number) or _is_unnumbered_heading(line, following,
                                                          after_number)
        after_number = bool(number)
        if boundary and current:
            cuts.append((start, "\n".join(current)))
            start = offset
            current = [line]
        else:
            current.append(line)
        offset += len(line) + 1          # +1 for the newline that split removed
    if current:
        cuts.append((start, "\n".join(current)))
    return cuts


def _looks_like_a_heading(line: str) -> bool:
    """Whether one line reads as a section HEADING rather than prose.

    Three tests, each closing a real failure seen on the owner's documents:

    * **Length and word count.** A heading is a label. "3.1 Customers shall
      raise purchase orders on Leapswitch for the provision of Services. Subject
      to Clause" is 16 words of a sentence the PDF broke mid-line, and it was
      being promoted to a heading because the truncated title it produced
      happened not to end in a full stop.
    * **No sentence punctuation, at the end OR inside.** The interior test is
      what catches that same line: it contains ". " long before it ends.
    * **Starts like a title.** A letter, not a bullet, a date or a page number.

    Deliberately conservative in one direction: a heading that breaks one of
    these is missed rather than prose being promoted. An outline short one entry
    is a smaller failure than an outline full of body text — which is the defect
    this whole change exists to fix.
    """
    stripped = line.strip()
    if not (2 < len(stripped) <= HEADING_MAX_CHARS):
        return False
    if len(stripped.split()) > HEADING_MAX_WORDS:
        return False
    if stripped.rstrip().endswith((".", ";", ":", ",")):
        return False
    # A trailing hyphen is a WORD the PDF broke across lines — "…by self-" /
    # "registration via…". It is the middle of a sentence, never a label, and it
    # was the reason a clause body was promoted to a heading and left the
    # clause's own number orphaned above it (measured on MSA.pdf, 61 segments).
    if stripped.rstrip().endswith(("-", "\u2010", "\u2011", "\u2013")):
        return False
    if ". " in stripped or "," in stripped:
        return False
    return stripped[0].isalpha() or stripped[0].isdigit()


def _second_line(normalized: str) -> str | None:
    parts = normalized.split("\n", 1)
    return parts[1].split("\n", 1)[0] if len(parts) > 1 else None


def _is_title_line(line: str) -> bool:
    """A short, capitalised, punctuation-free line — heading SHAPE, no context."""
    return _looks_like_a_heading(line) and line.strip()[:1].isupper()


def _is_unnumbered_heading(line: str, following: str | None,
                           after_number: bool = False) -> bool:
    """A heading that carries no clause number — and the reason CloudPe blocked.

    Measured 2026-09-05: the CloudPe terms of service and privacy policy carry
    NO clause numbering anywhere, but they are not unstructured. They are
    organised by prose headings — "Copyright", "Cancellations", "Late Fees",
    "Governing Law and Jurisdiction" — and because only numbered headings were
    recognised, the entire document arrived as one block per page and the
    structural gate refused it. The structure was there; we could not see it.

    The `following` line is what separates a heading from a LIST. A printed web
    page ends in navigation chrome — "VPS", "Kubernetes", "Storage", "Careers" —
    every line of which is short and title-like. A heading is followed by the
    prose it introduces; a navigation item is followed by another short line.
    """
    if after_number:
        # The previous line stated a clause number, so THIS line is that
        # clause's text by definition — however label-like it looks. Without
        # this, a layout that puts the number on its own line ("5.1.1." then
        # "The Customer may initiate…") cut twice and left the number stranded
        # as a segment containing nothing but "5.1.1.".
        return False
    if not _is_title_line(line):
        return False
    if following is None or len(following.strip()) < HEADING_PROSE_CHARS:
        return False
    # A heading INTRODUCES a sentence; a wrapped line is continued by its own
    # lowercase remainder. That single test separates the two, and it is what
    # the earlier length/punctuation rules could not: "Government organisations
    # shall mandatorily enable logs of all their ICT" is 10 words, 70 characters,
    # capitalised and unpunctuated — indistinguishable from a heading until you
    # notice the next line begins "systems and maintain them securely".
    #
    # Deliberately "not lowercase" rather than "is uppercase": a real heading is
    # often followed by a bullet list, and requiring a capital would have dropped
    # "Hardware SLA" and "SLA Credit" from the annexure of the owner's own MSA,
    # both of which open with "•".
    return not following.strip()[:1].islower()


def _is_heading(normalized: str, number: str | None, title: str | None) -> bool:
    """Whether a finished segment is a heading rather than a clause with a body.

    A numbered heading labels the clause beneath it — "13. LIMITATION ON
    DAMAGES" — where "13.1 The total liability shall not exceed the fees paid."
    IS the clause. `detect_clause_number` reports a "title" for both, because it
    reads whatever follows the number, so the discrimination happens here.

    ponytail: punctuation, length and word-count heuristics, no case analysis
    and no style information. Upgrade to the document's own heading styles
    (DOCX) if the outline measurably misses headings on real files.
    """
    if "\n" in normalized:
        return False
    if number:
        # Judge the TITLE, not the whole line: the clause number carries its own
        # full stop ("13. LIMITATION ON DAMAGES"), which would trip the interior
        # sentence-punctuation test on every properly numbered heading.
        # A number with no title is a bare "17.1" boundary line, not a heading.
        # The terminal-punctuation test must read the CONTENT, not the title:
        # `detect_clause_number` strips trailing ".:-" from the title, so a
        # one-line clause body would otherwise look unpunctuated and pass.
        return (title is not None and _looks_like_a_heading(title)
                and not normalized.rstrip().endswith((".", ";", ":", ",")))
    return False


# 44.4 — "annexures/schedules where detectable" (2026-09-06). Detectable means the
# document SAYS so: a title line that is the word and the label the document gives
# it ("Annexure-1", "Appendix-3B", "Schedule 2 – Fees", "Exhibit A"), optionally a
# short title, never a sentence. The label is the document's own text, kept
# verbatim (34.12 — numbering is preserved, never generated). A bare "Schedule"
# is not claimed: without a label the word may be a heading about timetables.
_ANNEXURE_TITLE = re.compile(
    r"^(?:annexure|annex|schedule|exhibit|appendix|attachment)"
    r"\s*[-\u2013:.]?\s*(?:no\.?\s*)?"
    r"(?:[0-9]{1,3}[a-z]?|[a-z]|[ivxl]{1,5})"
    r"(?:\s*[-\u2013:]\s*[^.\n]{1,60})?\s*$",
    re.IGNORECASE,
)


def annexure_title(line: str) -> str | None:
    """The line itself when it is an annexure/schedule/appendix title; else None."""
    stripped = line.strip()
    if not stripped or len(stripped) > HEADING_MAX_CHARS:
        return None
    return stripped if _ANNEXURE_TITLE.match(stripped) else None


def _structure_markers(normalized: str, first_line: str, number: str | None,
                       title: str | None,
                       following: str | None) -> tuple[str | None, dict]:
    """The ONE place a segment's structural markers are decided (2026-09-06).

    Used by both the paragraph segmenter (PDF text) and `parse_docx`. Until
    today the DOCX path built its Segments directly and so carried NEITHER the
    heading marker P1 added (2026-09-05) nor the annexure marker of 44.4 — a
    Word upload got only the outline's numbered-row fallback, while the same
    text as a PDF got the real outline. Found by the post-deploy smoke test on
    the live site, not by the corpus proof: all 13 corpus documents are PDFs.

    Returns the (possibly promoted) section title and the marker metadata.
    Boundaries and content are never touched here — markers only.
    """
    annexure = annexure_title(first_line) if number is None else None
    if number is None and (annexure or _is_title_line(first_line)):
        title = first_line.strip()
    if annexure:
        return title, {"heading": True, "annexure": annexure}
    if _is_heading(normalized, number, title) or (
            number is None and _is_unnumbered_heading(first_line, following)):
        return title, {"heading": True}
    return title, {}


def segment_paragraphs(text: str, *, page_number: int | None,
                       source_type: EvidenceSourceType,
                       base_offset: int = 0) -> list[Segment]:
    """Split into paragraph segments, carrying source locations (34.13)."""
    segments: list[Segment] = []
    cursor = 0
    for block in re.split(r"\n\s*\n", text):
        raw_block = block
        block_start = text.find(raw_block, cursor)
        if block_start < 0:                    # pragma: no cover - defensive
            block_start = cursor
        cursor = block_start + len(raw_block)
        if not normalize_text(raw_block):
            continue
        for inner_offset, raw in _split_at_clause_lines(raw_block):
            normalized = normalize_text(raw)
            if not normalized:
                continue
            start = block_start + inner_offset
            first_line = normalized.split("\n", 1)[0]
            number, title = detect_clause_number(first_line)
            title, markers = _structure_markers(
                normalized, first_line, number, title, _second_line(normalized))
            # An UNNUMBERED heading keeps the prose it introduces in the same
            # segment — unlike a numbered one, whose following sub-clause starts
            # its own boundary. So the heading line becomes this segment's
            # title rather than a row of its own. That is the better outcome
            # anyway: the outline entry then points AT the text it labels
            # instead of at an empty label above it.
            segments.append(Segment(
                content=normalized,
                original_content=raw,
                source_type=source_type,
                page_number=page_number,
                section_number=number,
                section_title=title,
                start_offset=base_offset + start,
                end_offset=base_offset + start + len(raw),
                # A heading is a numbered line that carries a title and no body
                # of its own — "13. LIMITATION ON DAMAGES" as against "13.1 The
                # total liability...". Recorded at segmentation because evidence
                # rows are effectively immutable: a row cited by an Evaluation
                # can never be rewritten (rule 17), so a marker not written here
                # can never be added to it later.
                # A segment is a heading when it is a single line that reads as
                # one — numbered ("13. LIMITATION ON DAMAGES") or not
                # ("Cancellations"). The "prose follows" test belongs to the
                # BOUNDARY decision above, not here: by this point the split has
                # already happened, and a navigation list never reaches this
                # branch because it was never cut into single-line segments.
                # "This row BEGINS a section" — a numbered heading standing
                # alone, or any row whose first line reads as a heading. It is
                # not a claim that the row contains nothing else.
                # The unnumbered case reuses the BOUNDARY test, against this
                # segment's own second line: a heading is followed by the prose
                # it introduces. Without that, a printed web page's navigation
                # footer — "VPS", "Kubernetes", "Storage" — reads as a heading
                # because its first line is short and capitalised.
                # An annexure title is a heading the document declares outright
                # (44.4); the boundary decision above is untouched by it.
                metadata=markers,
            ))
    return segments


# --------------------------------------------------------------------------
# OCR availability — locked 34.7, 34.9
# --------------------------------------------------------------------------
def ocr_available() -> bool:
    """Whether the locked OCR toolchain (OCRmyPDF + Tesseract) is present."""
    return shutil.which("ocrmypdf") is not None and shutil.which("tesseract") is not None


def stopword_share(text: str) -> float | None:
    """Share of alphabetic tokens that are common English function words.

    ``None`` means "not judgeable", for one of two honest reasons: too little
    text to measure, or a text that is not predominantly ASCII (see
    ``MIN_ASCII_SHARE_TO_JUDGE``). A caller must treat ``None`` as "leave the
    extraction alone", never as a failure.
    """
    if not text:
        return None
    printable = [c for c in text if not c.isspace()]
    if not printable:
        return None
    ascii_share = sum(c.isascii() for c in printable) / len(printable)
    if ascii_share < MIN_ASCII_SHARE_TO_JUDGE:
        return None

    words = re.findall(r"[A-Za-z]{1,12}", text.lower())
    if len(words) < MIN_WORDS_TO_JUDGE_LEGIBILITY:
        return None
    return sum(word in LEGIBILITY_STOPWORDS for word in words) / len(words)


def text_is_legible(text: str) -> bool | None:
    """Whether extracted text reads as language rather than as glyph codes.

    ``None`` when the question cannot be answered (see ``stopword_share``), which
    is deliberately distinct from ``False``: only ``False`` is evidence of a
    broken extraction, and only ``False`` may change what the parser does.
    """
    share = stopword_share(text)
    if share is None:
        return None
    return share >= ILLEGIBLE_STOPWORD_SHARE


# --------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------
def parse_pdf(data: bytes, *, defer_ocr: bool = False) -> ParseResult:
    """Native PDF text extraction, with OCR only where a page has none.

    Locked 34.7: OCR is used when a supported PDF does not contain usable text.
    Locked 34.9: if a page has no native text and OCR is unavailable or fails,
    that page is reported as failed — its text is never guessed.

    ``defer_ocr`` (2026-09-03, the ~63s-upload fix): when True and this document
    turns out to need OCR — a page with no usable native text, or a native layer
    that is not legible — and the toolchain is present, the OCR is NOT run here.
    The result comes back with ``needs_ocr=True`` and no segments, so the caller
    can finish the upload quickly and run the OCR as its own background
    processing run (``ProcessingRunType.OCR``, locked 42.5). When the toolchain
    is absent there is nothing to defer to, and the fail-closed behaviour is
    exactly as before.
    """
    import pymupdf

    diagnostics: list[str] = []
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError(f"PDF could not be opened: {type(exc).__name__}") from exc

    if doc.needs_pass:
        # 34.4 lists password-protected among the failure conditions.
        raise ParseError("PDF is password protected")

    segments: list[Segment] = []
    failed_pages: list[int] = []
    deferred_pages: list[int] = []
    extracted_pages = 0
    offset = 0

    # `doc` is a PyMuPDF Document; the library ships no type information, so the
    # page objects are untyped here rather than wrongly typed.
    for index, page in enumerate(doc, start=1):    # type: ignore[arg-type,var-annotated]
        try:
            raw = page.get_text("text") or ""
        except Exception as exc:                # pragma: no cover - defensive
            raw = ""
            diagnostics.append(f"page {index}: extraction error {type(exc).__name__}")

        if len(raw.strip()) >= MIN_USABLE_CHARS_PER_PAGE:
            page_segments = segment_paragraphs(
                raw, page_number=index,
                source_type=EvidenceSourceType.NATIVE_TEXT, base_offset=offset)
            segments.extend(page_segments)
            extracted_pages += 1
            offset += len(raw)
            continue

        # No usable native text on this page (34.7).
        if not ocr_available():
            failed_pages.append(index)
            diagnostics.append(
                f"page {index}: no usable native text and OCR toolchain "
                "unavailable; page not extracted")
            continue

        if defer_ocr:
            # The page needs OCR and the caller asked for that to happen in a
            # later run instead of inline. Recorded, not attempted.
            deferred_pages.append(index)
            continue

        try:
            ocr_text = _ocr_page(page)
        except Exception as exc:
            failed_pages.append(index)
            diagnostics.append(f"page {index}: OCR failed ({type(exc).__name__})")
            continue

        if len(ocr_text.strip()) < MIN_USABLE_CHARS_PER_PAGE:
            failed_pages.append(index)
            diagnostics.append(f"page {index}: OCR produced no usable text")
            continue

        segments.extend(segment_paragraphs(
            ocr_text, page_number=index,
            source_type=EvidenceSourceType.OCR,     # 34.8 — explicitly identified
            base_offset=offset))
        extracted_pages += 1
        offset += len(ocr_text)

    pages_total = doc.page_count

    # Locked 34.3 — "detect when normal extraction is INSUFFICIENT and use OCR
    # where supported". Presence was checked per page above; legibility is
    # checked here, once, over the whole document (see the notes on
    # MIN_WORDS_TO_JUDGE_LEGIBILITY for why never per page).
    native_legible = text_is_legible(
        "\n".join(s.content for s in segments
                  if s.source_type is EvidenceSourceType.NATIVE_TEXT))

    if defer_ocr and ocr_available() and (deferred_pages or native_legible is False):
        # OCR is needed and the toolchain is present — hand the decision back to
        # the caller. Without the toolchain there is nothing to defer to, and the
        # existing fail-closed path below concludes now rather than later.
        if deferred_pages:
            diagnostics.append(
                f"{len(deferred_pages)} page(s) have no usable native text; "
                "OCR deferred to a background run")
        if native_legible is False:
            share = stopword_share("\n".join(
                s.content for s in segments
                if s.source_type is EvidenceSourceType.NATIVE_TEXT))
            diagnostics.append(
                "native text is not legible (function-word share "
                f"{share:.3f} < {ILLEGIBLE_STOPWORD_SHARE}); OCR deferred to a "
                "background run")
        pages_total = doc.page_count
        doc.close()
        return ParseResult(
            segments=[], status=ExtractionStatus.FAILED,  # provisional — see needs_ocr
            pages_total=pages_total, pages_extracted=0, pages_failed=[],
            diagnostics=diagnostics, needs_ocr=True)

    if native_legible is False:
        segments, extracted_pages, failed_pages, offset = _reextract_illegible(
            doc, data, segments, diagnostics)

    doc.close()

    status = _status_for(pages_total, extracted_pages)
    return ParseResult(segments=segments, status=status, pages_total=pages_total,
                       pages_extracted=extracted_pages, pages_failed=failed_pages,
                       diagnostics=diagnostics,
                       pagination_source=PDF_PHYSICAL_PAGES if extracted_pages else None)


def _reextract_illegible(
    doc, data: bytes, native_segments: list[Segment], diagnostics: list[str],
) -> tuple[list[Segment], int, list[int], int]:
    """Second pass for a document whose native text is not language.

    Two outcomes, and never a third:

    * **OCR available and measurably better** — the OCR pass replaces the native
      segments wholesale and is marked ``EvidenceSourceType.OCR`` (34.8, and
      34.3's "never silently treat OCR output as equivalent to clean native
      text"). "Measurably better" is required, not assumed: OCR output that is
      itself illegible is discarded, so this can never trade working text for
      worse text.

    * **Otherwise** — every page is reported FAILED and no text is returned.
      That is 34.9 read strictly: the alternative is passing a glyph-code stream
      into evidence, the clause list, the retrieval index and the evaluator,
      where it becomes MATCH findings against text nobody can read. An empty
      extraction is honest; that is not. ``_status_for`` turns it into
      ``FAILED``, which 45B.7 already routes to ``UNABLE_TO_EVALUATE``.

    Returns ``(segments, pages_extracted, pages_failed, offset)``.
    """
    share = stopword_share("\n".join(s.content for s in native_segments))
    diagnostics.append(
        "native text is not legible (function-word share "
        f"{share:.3f} < {ILLEGIBLE_STOPWORD_SHARE}); the embedded fonts most "
        "likely carry an incorrect ToUnicode mapping")

    all_pages = list(range(1, doc.page_count + 1))
    if not ocr_available():
        diagnostics.append(
            "OCR toolchain unavailable, so no legible text can be produced; "
            "no text is returned rather than returning unreadable text")
        return [], 0, all_pages, 0

    ocr_segments: list[Segment] = []
    ocr_failed: list[int] = []
    ocr_pages = 0
    offset = 0
    # Pages OCR independently, so they run in parallel and are reassembled in
    # page order — same input, same output, same order as the sequential loop
    # this replaces (measured byte-identical on the real 30-page document;
    # 65.6s -> 16.2s on 4 cores). Each worker opens its own document handle from
    # `data` because PyMuPDF objects are not safe to share across threads.
    for index, outcome in _ocr_pages_parallel(data, doc.page_count):
        if isinstance(outcome, Exception):
            ocr_failed.append(index)
            diagnostics.append(f"page {index}: OCR failed ({type(outcome).__name__})")
            continue
        ocr_text = outcome
        if len(ocr_text.strip()) < MIN_USABLE_CHARS_PER_PAGE:
            ocr_failed.append(index)
            diagnostics.append(f"page {index}: OCR produced no usable text")
            continue
        ocr_segments.extend(segment_paragraphs(
            ocr_text, page_number=index,
            source_type=EvidenceSourceType.OCR, base_offset=offset))
        ocr_pages += 1
        offset += len(ocr_text)

    ocr_legible = text_is_legible("\n".join(s.content for s in ocr_segments))
    if ocr_legible is not True:
        # OCR ran and is no better. Keeping the native mojibake would be the
        # worse of two bad options: it looks like content.
        diagnostics.append(
            "OCR did not produce legible text either; no text is returned")
        return [], 0, all_pages, 0

    diagnostics.append(
        f"re-extracted {ocr_pages} of {doc.page_count} page(s) by OCR "
        "(marked OCR-derived); the native text was discarded as unreadable")
    return ocr_segments, ocr_pages, ocr_failed, offset


#: Page-level OCR parallelism. Bounded by the machine, never unbounded: each
#: worker is one tesseract process pinned to one thread (OMP_THREAD_LIMIT=1),
#: so the pool as a whole uses about the same CPU a single unpinned tesseract
#: (~2.5 threads) already did — it just keeps all cores busy for the whole run.
OCR_MAX_WORKERS = 4

#: The render resolution for OCR input. 300dpi is tesseract's recommended
#: input density; measured on the real 30-page document, 150dpi is ~35% faster
#: but produces slightly different output, so the density stays at 300 and the
#: speed comes from parallelism, which changes nothing about the output.
OCR_RENDER_DPI = 300


def _ocr_page(page) -> str:                     # pragma: no cover - needs toolchain
    """OCR a single page via the locked toolchain.

    Only reached when the toolchain is present; absence is handled by the caller
    as a failure, never as empty text.
    """
    pix = page.get_pixmap(dpi=OCR_RENDER_DPI)
    return _tesseract_pixmap(pix)


def _tesseract_pixmap(pix) -> str:              # pragma: no cover - needs toolchain
    import os
    import subprocess
    import tempfile

    # One thread per tesseract process: the parallelism lives at the page level,
    # and an unpinned tesseract would oversubscribe the cores it shares with the
    # other pages' workers.
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        image_path = f"{tmp}/page.png"
        pix.save(image_path)
        proc = subprocess.run(
            ["tesseract", image_path, "stdout"],
            capture_output=True, text=True, timeout=120, check=False, env=env)
        if proc.returncode != 0:
            raise ParseError(f"tesseract exited {proc.returncode}")
        return proc.stdout


def _ocr_pages_parallel(
    data: bytes, page_count: int,
) -> list[tuple[int, str | Exception]]:
    """OCR every page of ``data``, up to ``OCR_MAX_WORKERS`` at a time.

    Returns ``[(page_number, text-or-exception), ...]`` in page order regardless
    of completion order, so the caller's output is identical to a sequential
    pass. A page's failure is returned as its exception, never raised — one bad
    page must not cost the other twenty-nine (34.10).
    """
    import os
    from concurrent.futures import ThreadPoolExecutor

    import pymupdf

    def one(index: int) -> str | Exception:     # pragma: no cover - needs toolchain
        try:
            # A thread-local document handle: PyMuPDF documents are not
            # thread-safe, and opening from bytes costs well under a millisecond.
            doc = pymupdf.open(stream=data, filetype="pdf")
            try:
                return _ocr_page(doc[index - 1])
            finally:
                doc.close()
        except Exception as exc:
            return exc

    # A pool of 1 worker already runs `map` sequentially in submission order,
    # so there is no separate single-threaded path to maintain.
    workers = max(1, min(OCR_MAX_WORKERS, os.cpu_count() or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(zip(range(1, page_count + 1),
                        pool.map(one, range(1, page_count + 1)), strict=True))


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# The values written to the processing run's `pagination_source`.
DOCX_RENDERED_PAGE_BREAKS = "DOCX_RENDERED_PAGE_BREAKS"
DOCX_EXPLICIT_PAGE_BREAKS = "DOCX_EXPLICIT_PAGE_BREAKS"
PDF_PHYSICAL_PAGES = "PDF_PHYSICAL_PAGES"


def _docx_paragraph_pages(paragraphs) -> tuple[list[int] | None, int, str | None]:
    """The starting page of each paragraph, from the document's OWN record.

    A DOCX has no physical pages — pagination happens at render time — so this
    never computes one. It reads two things the file itself carries:

    * ``w:lastRenderedPageBreak`` — where the authoring application (Word)
      recorded that a page boundary fell when the file was last saved. This is
      the same pagination the author saw, including the effect of fonts,
      margins and hard breaks.
    * ``w:br w:type="page"`` — a page break the author explicitly inserted.

    Word records a rendered marker at the boundary a hard break causes, so when
    rendered markers exist, a hard break paired with one (no text between them)
    is ONE boundary, not two — measured on the live MSA: 26 rendered + 6
    explicit − 5 such pairs = 27 boundaries = 28 pages, matching Word. The pair
    can appear in EITHER order — Word records the rendered marker at the point
    the previous page's content ended, which is not always after the break run
    — so pairing is order-independent: whichever of the two comes first opens
    the boundary, and the other (if it follows before any real text) closes the
    same one rather than opening a second.

    A file carrying NEITHER kind of break yields ``(None, 0, None)``: a
    one-page document and a converter that strips pagination metadata (Google
    Docs exports do) are indistinguishable, and locked 34.9/34.12 forbid
    guessing — the viewer then says "Not paginated", which stays true.

    A paragraph is assigned the page it STARTS on: a boundary marker that
    precedes the paragraph's first text means the paragraph begins the new
    page; a boundary after text means it began on the earlier page.
    """
    rendered = explicit = 0
    for para in paragraphs:
        for el in para._p.iter():
            if el.tag == _W + "lastRenderedPageBreak":
                rendered += 1
            elif el.tag == _W + "br" and el.get(_W + "type") == "page":
                explicit += 1
    if rendered == 0 and explicit == 0:
        return None, 0, None

    use_rendered = rendered > 0
    page = 1
    # Which kind of break is "open" — awaiting either real text (which closes
    # it) or the OTHER kind of break (which pairs with it as the same
    # boundary, in whichever order the two appear). Two breaks of the SAME
    # kind in a row, with no text between, are two distinct boundaries — a
    # deliberately blank page — so only cross-kind pairing collapses.
    pending_explicit = False
    pending_rendered = False
    pages: list[int] = []
    for para in paragraphs:
        start_page: int | None = None
        for el in para._p.iter():
            if el.tag == _W + "t":
                if (el.text or "").strip():
                    if start_page is None:
                        start_page = page
                    pending_explicit = False
                    pending_rendered = False
            elif el.tag == _W + "br" and el.get(_W + "type") == "page":
                if pending_rendered:
                    pending_rendered = False  # the same boundary, already counted
                else:
                    page += 1
                pending_explicit = True
            elif use_rendered and el.tag == _W + "lastRenderedPageBreak":
                if pending_explicit:
                    pending_explicit = False  # the same boundary, already counted
                else:
                    page += 1
                pending_rendered = True
        pages.append(start_page if start_page is not None else page)

    source = DOCX_RENDERED_PAGE_BREAKS if use_rendered else DOCX_EXPLICIT_PAGE_BREAKS
    return pages, page, source


def parse_docx(data: bytes) -> ParseResult:
    """DOCX extraction preserving paragraphs and tables (34.11).

    Page numbers (2026-09-02): read from the document's own pagination record —
    see ``_docx_paragraph_pages``. Never computed, never guessed; absent record
    means absent pages. Table segments carry no page: python-docx surfaces
    tables outside the paragraph stream, so a table's position in that record
    is not stated by the file.
    """
    import io

    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError(f"DOCX could not be opened: {type(exc).__name__}") from exc

    paragraphs = list(document.paragraphs)
    paragraph_pages, total_pages, pagination_source = _docx_paragraph_pages(paragraphs)

    segments: list[Segment] = []
    offset = 0

    for index, para in enumerate(paragraphs):
        raw = para.text or ""
        normalized = normalize_text(raw)
        if not normalized:
            offset += len(raw)
            continue
        first_line = normalized.split("\n", 1)[0]
        number, title = detect_clause_number(first_line)
        # The same markers the PDF path gets (see _structure_markers). Word puts
        # each paragraph in its own segment, so "the prose that follows" is the
        # next non-empty paragraph rather than the segment's own second line.
        following = next((normalize_text(q.text or "") for q in paragraphs[index + 1:]
                          if normalize_text(q.text or "")), None)
        title, markers = _structure_markers(
            normalized, first_line, number, title, following)
        segments.append(Segment(
            content=normalized, original_content=raw,
            source_type=EvidenceSourceType.NATIVE_TEXT,
            page_number=paragraph_pages[index] if paragraph_pages else None,
            section_number=number, section_title=title,
            start_offset=offset, end_offset=offset + len(raw),
            metadata={"style": para.style.name if para.style else None, **markers},
        ))
        offset += len(raw)

    # Tables are preserved as TABLE-sourced segments (34.11).
    for table_index, table in enumerate(document.tables, start=1):
        rows = ["\t".join(cell.text.strip() for cell in row.cells)
                for row in table.rows]
        raw = "\n".join(rows)
        normalized = normalize_text(raw)
        if not normalized:
            continue
        segments.append(Segment(
            content=normalized, original_content=raw,
            source_type=EvidenceSourceType.TABLE,
            start_offset=offset, end_offset=offset + len(raw),
            metadata={"table_index": table_index, "rows": len(table.rows)},
        ))
        offset += len(raw)

    status = (ExtractionStatus.COMPLETE if segments else ExtractionStatus.FAILED)
    diagnostics = [] if segments else ["DOCX contained no extractable text"]
    if segments and pagination_source:
        diagnostics = [*diagnostics,
                       "pages from the document's own pagination record "
                       f"({pagination_source})"]
    pages_extracted = (total_pages if pagination_source else 1) if segments else 0
    return ParseResult(segments=segments, status=status,
                       pages_total=total_pages if pagination_source else 0,
                       pages_extracted=pages_extracted,
                       diagnostics=diagnostics,
                       pagination_source=pagination_source if segments else None)


def parse(data: bytes, mime_type: str, *, defer_ocr: bool = False) -> ParseResult:
    if mime_type == PDF_MIME:
        return parse_pdf(data, defer_ocr=defer_ocr)
    if mime_type == DOCX_MIME:
        return parse_docx(data)  # a DOCX is text-native; OCR never applies
    raise ParseError(f"unsupported mime type: {mime_type}")


def _status_for(pages_total: int, pages_extracted: int) -> ExtractionStatus:
    """Locked 34.10 — partial extraction is explicitly represented."""
    if pages_total == 0 or pages_extracted == 0:
        return ExtractionStatus.FAILED
    if pages_extracted < pages_total:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.COMPLETE
