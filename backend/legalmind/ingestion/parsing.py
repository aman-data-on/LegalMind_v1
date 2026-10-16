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

import os
import re
import shutil
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from legalmind import config
from legalmind.domain.enums import EvidenceSourceType, ExtractionStatus
from legalmind.ingestion.validation import (
    DOCX_MIME,
    PDF_MIME,
    TEXT_MIME_TYPES,
)

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
    #: Pages whose OCR was kept but read with low confidence — recorded on the run and
    #: disclosed wherever the document is read, never silently treated as clean text.
    pages_low_confidence: list[int] = field(default_factory=list)
    #: Docling's part when it was run (``_docling_tables``): docling_version,
    #: docling_pages (gated), docling_tables (a Docling table inlined), fallback_reasons
    #: ({page: why}). Empty when Docling was not run; {"docling_deferred": True} when a
    #: read deferred only for it (``needs_ocr``).
    reader: dict = field(default_factory=dict)


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
    # A number followed by a lowercase word is a wrapped line ("…paid in the\n12
    # months preceding…", "…clause\n6.3 above"), never a clause (A5) — unless it
    # is written as a full sub-clause number ("1.1.1. if that person…"). A bare
    # number with no dot or sub-level needs a capitalised title.
    re.compile(r"^(?P<num>\d+(?:\.\d+)+)\.\s+(?P<title>[A-Z][^\n]{0,120})?"),
    re.compile(r"^(?P<num>\d+(?:\.\d+)+|\d+(?=\.))\.?\s+(?![a-z])"
               r"(?P<title>[A-Z][^\n]{0,120})?"),
    re.compile(r"^(?P<num>\d+)\s+(?P<title>[A-Z][^\n]{0,120})"),
    re.compile(r"^(?:Section|SECTION|Clause|CLAUSE)\s+(?P<num>\d+(?:\.\d+)*)"
               r"\.?\s*(?P<title>[^\n]{0,120})?"),
    re.compile(r"^(?:Article|ARTICLE)\s+(?P<num>[IVXLC]+|\d+)"
               r"\.?\s*(?P<title>[^\n]{0,120})?"),
    # A markup tool's bracketed label, "[13.] Service Termination" (AM-146): the dot
    # INSIDE the bracket and a capitalised title, so a footnote "[1]" stays prose.
    re.compile(r"^\[(?P<num>\d+(?:\.\d+)*)\.\]\s+(?P<title>[A-Z][^\n]{0,120})"),
)


_LONG_CLAUSE = re.compile(r"^(?P<num>\d+(?:\.\d+)+)\.?\s+[A-Z(\"\u201c]")

#: U+200B ZERO WIDTH SPACE and U+FEFF (a BOM mid-text), read as a space by clause
#: detection — see `detect_clause_number`.
_ZERO_WIDTH = str.maketrans({"\u200b": " ", "\ufeff": " "})


def table_row(cells: list[str | None]) -> str:
    """One table row as one line, `| a | b |`: the ONE serialization, PDF and DOCX.

    A tab would be collapsed by `normalize_text`, and a bare `a | b` can open with a
    clause number and be cut as one. The leading `|` keeps a row out of clause and
    heading detection, so a table stays inside the clause that introduces it. A cell's
    own line breaks become spaces: one row is one line.
    """
    return "| " + " | ".join(" ".join((c or "").split()) for c in cells) + " |"


def detect_clause_number(line: str) -> tuple[str | None, str | None]:
    """Return (section_number, section_title) if the line states one.

    Locked 34.12 — existing clause numbering is *preserved*. If the document
    does not state a number, this returns ``None``; a number is never generated,
    because a fabricated section reference would corrupt evidence traceability.
    """
    # A Google-Docs export writes "6.1.<U+200B>" — a ZERO WIDTH SPACE after the number,
    # which `str.strip` keeps, so MSA-Feb.pdf read 1 numbered clause of ~200 (gap P1).
    # Spaces for DETECTION only: the content keeps the character (34.12/34.14).
    stripped = line.translate(_ZERO_WIDTH).strip()
    if not stripped:
        return None, None
    if len(stripped) > 200:
        # A DOCX clause is one paragraph on one line, so "5.4 MSA clause 7.2 … applies
        # only during…" is long and was left unnumbered: 54 of 74 clauses of a real
        # addendum (2026-10-14), its early-exit clause among them. Long, only a number
        # with a sub-level counts — a long line opening "12 Months" stays prose — and
        # the sentence is not a title.
        m = _LONG_CLAUSE.match(stripped)
        return (m.group("num"), None) if m else (None, None)
    for pattern in _CLAUSE_PATTERNS:
        m = pattern.match(stripped)
        if m:
            title = (m.group("title") or "").strip(" .:-") or None
            return m.group("num"), title
    return None, None


def _bold_heading(line: str, bold_lines: frozenset[str]) -> bool:
    """A line the PDF sets ALL in bold that reads as a title — a heading whatever
    follows it (AM-146). "Confidentiality" above a 55-character bullet failed the
    prose rule of `_is_unnumbered_heading` and was absorbed into the clause above.
    A trailing colon is a bold label's ("Penalty Clause:"), so it is allowed here."""
    stripped = line.strip()
    return stripped in bold_lines and _is_title_line(stripped.rstrip(":").rstrip())


def _split_at_clause_lines(block: str,
                           bold_lines: frozenset[str] = frozenset(),
                           ) -> list[tuple[int, str]]:
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
        boundary = (bool(number)
                    or (not after_number and _bold_heading(line, bold_lines))
                    or _is_unnumbered_heading(line, following, after_number))
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
    #
    # A `| … |` table row is not prose: the line above it is the table's own header
    # ("Monthly Uptime Service Credit Percentage"), and cutting there tore SLA-
    # leapswitch's 15/40/100% rows away from "Issuance of Service Credits" (F1 critic).
    return not following.strip()[:1].islower() and not following.lstrip().startswith("|")


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
                       title: str | None, following: str | None,
                       bold: bool = False) -> tuple[str | None, dict]:
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
    if number is None and bold:
        title = first_line.strip().rstrip(":").rstrip()   # a bold label (`_bold_heading`)
    if annexure:
        return title, {"heading": True, "annexure": annexure}
    if _is_heading(normalized, number, title) or (number is None and bold) or (
            number is None and _is_unnumbered_heading(first_line, following)):
        return title, {"heading": True}
    return title, {}


def segment_paragraphs(text: str, *, page_number: int | None,
                       source_type: EvidenceSourceType,
                       base_offset: int = 0,
                       bold_lines: frozenset[str] = frozenset()) -> list[Segment]:
    """Split into paragraph segments, carrying source locations (34.13).

    ``bold_lines``: the page's all-bold lines, given only for a marked-up PDF
    (AM-146, `_bold_heading`) — every other document segments exactly as before."""
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
        for inner_offset, raw in _split_at_clause_lines(raw_block, bold_lines):
            normalized = normalize_text(raw)
            if not normalized:
                continue
            start = block_start + inner_offset
            first_line = normalized.split("\n", 1)[0]
            number, title = detect_clause_number(first_line)
            if bold_lines and number and title and ": " in title:
                # A marked-up page (AM-146): "[13.] Service Termination: The" once its
                # struck sentence is gone — the label is what precedes the colon.
                title = title.split(": ", 1)[0]
            title, markers = _structure_markers(
                normalized, first_line, number, title, _second_line(normalized),
                bold=_bold_heading(first_line, bold_lines))
            # A PDF table stays NATIVE_TEXT inside its clause as `table_row` lines (F1),
            # so source_type cannot say "from a table": this count of tables (runs of
            # `| ` rows) is how a reader knows (BR-1).
            rows = [line.startswith("| ") for line in normalized.split("\n")]
            tables = sum(row and not (i and rows[i - 1]) for i, row in enumerate(rows))
            if tables:
                markers = {**markers, "tables": tables}
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
def _reads_in_columns(blocks: list, page_height: float) -> bool:
    """Does this page's content stream jump back up to start another column?

    Re-ordering EVERY page was measured and is wrong. On the 77-question set it lifted
    the statute lane (gate-open hit@1 0.538 -> 0.786) and pushed the contract lane
    down (gate-open 30/44 -> 27/44, recall@10 0.659 -> 0.568): single-column pages are
    already in reading order, so sorting them only churns the text that embeddings
    were built from. The fix is to reorder the pages that need it and leave the rest
    byte-identical.

    A single column runs down the page, so the content stream's y only grows. A second
    column begins by jumping back to the top — a large negative step. That jump IS the
    condition, so it is what is tested, rather than counting columns by clustering x.
    A third of the page height is well clear of the small negative steps a footnote or
    a hanging indent produces.
    """
    previous_top = None
    for block in blocks:
        top = block[1]
        if previous_top is not None and previous_top - top > page_height / 3:
            return True
        previous_top = top
    return False


def _is_ruled(page) -> bool:
    """At least one thin horizontal AND one thin vertical rule — a ruled grid can be
    here. ~3 ms a page against find_tables' 70-150 ms, and it missed no table page
    across 17 PDFs (Companies Act: 53 of 370 pages pass). Fill-only boxes — MSA.pdf's
    white page fill and 13.8-pt highlight bars — are not thin, so never pass (F1b).
    Read per path ITEM, not per drawing: one path may hold a whole grid, and a STROKED
    box (cells drawn as `re`) is four rules however large it is."""
    import pymupdf

    horizontal = vertical = False
    for drawing in page.get_cdrawings():
        stroked = "s" in (drawing.get("type") or "")
        rects = [pymupdf.Rect(drawing["rect"])]
        for item in drawing["items"]:
            if item[0] == "re" and stroked:
                r = pymupdf.Rect(item[1])
                horizontal |= r.width >= 20
                vertical |= r.height >= 10
            elif item[0] == "l":
                rects.append(pymupdf.Rect(item[1], item[2]).normalize())
        for r in rects:
            horizontal |= r.height <= 2 and r.width >= 20
            vertical |= r.width <= 2 and r.height >= 10
        if horizontal and vertical:
            return True
    return False


def _table_rows(table) -> str:
    """A table as `table_row` lines from `extract()` alone — never `to_markdown()`
    (drops ligature glyphs: "Cloudfare") nor `header.external` (takes a clause heading
    or a print header as the header) — F1c. A cell a vertical merge left empty takes
    the text of the cell above when that cell's box spans this row, so a merged
    "Dedicated Servers" labels every row it covers; any other empty cell is ''."""
    rows = table.extract()
    lines = []
    for i, row in enumerate(rows):
        cells = list(row)
        for j, cell in enumerate(cells):
            above = next((k for k in range(i - 1, -1, -1)
                          if table.rows[k].cells[j] is not None), None)
            if cell is None and above is not None and \
                    table.rows[above].cells[j][3] >= table.rows[i].bbox[3] - 1:
                cells[j] = rows[above][j]
        lines.append(table_row(cells))
    return "\n".join(lines)


def _table_rules(page) -> int:
    """The most thin horizontal rules on the page that share ONE horizontal extent (x0
    and x1 each within 3 pt of a rule's): line items and filled bars <= 2 pt high and
    >= 20 pt wide, and a stroked box's top and bottom edges. A table's row separators
    span the table; an underline or a section rule does not line up with two others
    (MSA.pdf sent 13 pages and held no table). The Docling gate (>= 3): it admits
    SLA-cloudpe's horizontal-rule tables, which `_is_ruled` cannot (no vertical rule)."""
    import pymupdf

    spans: list[tuple[float, float]] = []
    for drawing in page.get_cdrawings():
        stroked = "s" in (drawing.get("type") or "")
        for item in drawing["items"]:
            if item[0] not in ("l", "re"):
                continue
            r = (pymupdf.Rect(item[1], item[2]).normalize() if item[0] == "l"
                 else pymupdf.Rect(item[1]))
            if r.width < 20:
                continue
            if item[0] == "re" and stroked:
                spans += [(r.x0, r.x1)] * (1 if r.height <= 2 else 2)
            elif r.height <= 2:
                spans.append((r.x0, r.x1))
    # ponytail: O(n^2) in a page's rules; bucket by x0 if a page ever carries thousands.
    return max((sum(abs(a - x0) <= 3 and abs(b - x1) <= 3 for a, b in spans)
                for x0, x1 in spans), default=0)


def _inline_tables(page, blocks: list, docling_tables: list[dict] | None = None) -> list:
    """Tables as ONE pseudo-block of `| a | b |` rows, in content-stream place.

    Without this every cell is its own block, one per line, and rows and columns are
    lost: SLA-leapswitch's "Less than 99.0% / 40%" pairs, PRIVACY-leapswitch's
    sub-processor columns interleaved (F1). The table that was built before (dc6d41d)
    was withdrawn by 26014d8 for three reasons this avoids: its tables sat AFTER the
    page's prose, cut off from their clause (here the pseudo-block takes the place of
    the first block it replaces, so a table stays in its clause's segment); its cells
    were tab-joined, which `normalize_text` collapses (here `table_row`); and the
    'lines' strategy took MSA.pdf's highlighted clause text for tables (here
    'lines_strict' behind `_is_ruled`: 12 of 12 detections real on the corpus).

    Candidates: PyMuPDF's 'lines_strict' tables on an `_is_ruled` page first — a drawn
    grid's geometry is exact, and it carries a merged label down every row it spans,
    which Docling's TableFormer missed (test_a_vertically_merged_label_...) — then
    Docling's tables for the page (``docling_tables``, `_docling_tables`; pseudo-block
    number `_DOCLING_BLOCK`) that do not overlap one: SLA-cloudpe's horizontal-rule
    credit tables, which PyMuPDF cannot read.

    FAIL-SAFE: a table replaces its blocks only when (a) the blocks it replaces are
    consecutive in stream order — no other block between them, which the splice would
    move; (b) the blocks' \\w+ words AND their non-space characters other than '|' equal,
    as multisets, its cells' — no word or character lost, doubled, rewritten or run
    together ('>=' for '<=', a dropped '%', "Section5" for "Section 5"); and,
    for a Docling table, (c) every non-empty cell's text is exactly the page's own words
    whose centre lies in that cell's box, in stream order — so two rows' values swapped,
    or two rows joined, are never accepted, though the characters are the same. A header
    sharing a block with the heading above it, a Devanagari table whose glyphs extract
    differently, or a Docling cell it de-hyphenated keeps the original lines. So a table
    only regroups the page's own words into rows.

    ponytail: a table continued across pages is two tables; the continuation has no
    header row.
    """
    import pymupdf

    page_words: list = []

    def centred(box, b) -> bool:
        return (box[0] <= (b[0] + b[2]) / 2 <= box[2]
                and box[1] <= (b[1] + b[3]) / 2 <= box[3])

    def tokens(text: str) -> tuple[Counter[str], Counter[str]]:
        return (Counter(re.findall(r"\w+", text)),
                Counter(ch for ch in text if not ch.isspace() and ch != "|"))

    def read(box) -> str:
        """The page's own words in ``box``, in stream order, one space apart."""
        if not page_words:
            page_words.extend(page.get_text("words"))
        return " ".join(w[4] for w in page_words if centred(box, w))

    def splice(bbox, grid: list[list], cells: list, rows, boxes=()):
        """``blocks`` with the table in place, or None when it fails the check above.
        ``cells`` holds each cell's text once (a merged label carried down ``rows`` is
        one); ``boxes`` its (text, bbox) pairs, for the geometric check (c)."""
        if len(grid) < 2 or len(grid[0]) < 2:
            return None
        inside = [i for i, b in enumerate(blocks) if centred(bbox, b)]
        if not inside or inside != list(range(inside[0], inside[-1] + 1)) or \
                tokens(" ".join(c or "" for c in cells)) != \
                tokens(" ".join(blocks[i][4] for i in inside)) or \
                any(text.strip() and read(box) != " ".join(text.split())
                    for text, box in boxes):
            return None
        x0, y0, x1, y1 = bbox
        replaced = set(inside[1:])
        return [(x0, y0, x1, y1, *rows()) if i == inside[0] else b
                for i, b in enumerate(blocks) if i not in replaced]

    inlined = []
    if _is_ruled(page):
        # A stdout hint once per process, not a diagnostic (newer than 1.24).
        getattr(pymupdf, "no_recommend_layout", lambda: None)()
        for found in page.find_tables(strategy="lines_strict").tables:
            grid = found.extract()
            kept = splice(found.bbox, grid, [c for row in grid for c in row],
                          lambda t=found: (_table_rows(t), -1, 0))
            if kept is not None:
                blocks = kept
                inlined.append(pymupdf.Rect(found.bbox))
    try:
        for table in docling_tables or ():
            if any(pymupdf.Rect(table["bbox"]).intersects(r) for r in inlined):
                continue
            kept = splice(table["bbox"], table["rows"],
                          [c["text"] for c in table["cells"]], lambda t=table: (
                              "\n".join(table_row(row) for row in t["rows"]),
                              _DOCLING_BLOCK, 0),
                          [(c["text"], c["bbox"]) for c in table["cells"]])
            blocks = blocks if kept is None else kept
    except Exception:                       # pragma: no cover - defensive
        pass            # a Docling table must never cost the page its own tables
    return blocks


def _mostly_vertical(page) -> bool:
    """More of the page's characters sit on non-horizontal lines than on horizontal."""
    import pymupdf

    chars: Counter[bool] = Counter()
    # TEXTFLAGS_TEXT: without it "dict" carries every image's bytes — 230 scanned
    # Income-tax pages took ~50 s just to be asked their text direction.
    for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
        for line in block.get("lines", ()):
            chars[bool(line["dir"][1])] += sum(len(s["text"]) for s in line["spans"])
    return chars[True] > chars[False]


# --------------------------------------------------------------------------
# Revision marks — AM-146 (2026-10-16)
# --------------------------------------------------------------------------
# A redlined PDF (Word / LibreOffice "show changes" export) draws its tracked changes:
# inserted text coloured and underlined, deleted text coloured and struck through. Read
# as plain text the two merge — a struck "3" beside an inserted "5" read "53 years"
# on a real MOU. They are two versions of the contract and are kept apart: the PROPOSED
# text (insertions kept, deletions dropped — the accepted view `_VISIBLE_RUN` already
# reads from a DOCX) is the evidence, and the ORIGINAL plus each change is recorded on
# the segment's metadata. Nothing is invented: every character is the document's own.
#
# Recognition: PyMuPDF's span `char_flags` (strike 1, underline 2, TEXT_COLLECT_STYLES).
# A document is marked up only when it carries STRUCK text in a colour (not black or
# grey); that colour is its revision colour, and its text in that colour is a change —
# struck = deleted, otherwise inserted (an inserted word's spaces and ligature glyphs
# often carry no underline of their own). A blue underlined e-mail link is not struck,
# so a document with links and no strikes is not marked up and reads as before.

#: Around a revision run inside a page's text, so it survives the block sort and join;
#: `_resolve_revisions` removes them before any segment is cut. Never in evidence.
_DEL_OPEN, _DEL_CLOSE, _INS_OPEN, _INS_CLOSE = "", "", "", ""
_MARKERS = str.maketrans("", "", _DEL_OPEN + _DEL_CLOSE + _INS_OPEN + _INS_CLOSE)
#: A line left holding only these once its deleted text is gone is dropped with it.
_BULLETS = " \t\u25cf\u2022\u25aa\u25e6-\u2013*"


def _neutral(rgb: int) -> bool:
    """Black, white or grey: the channels within ~10% of each other."""
    r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
    return max(r, g, b) - min(r, g, b) < 26


def _styled_text(page) -> dict:
    import pymupdf
    return page.get_text("dict",
                         flags=pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_COLLECT_STYLES)


def _has_coloured_rule(page) -> bool:
    """A thin coloured line — a strike, an underline or a link. ~0.5 ms a page; it
    keeps the styled read off every page that cannot hold a revision."""
    for drawing in page.get_cdrawings():
        rect, colour = drawing.get("rect"), drawing.get("color")
        if rect and rect[3] - rect[1] <= 2 and colour and \
                max(colour) - min(colour) >= 0.1:
            return True
    return False


def _revision_colours(doc) -> frozenset[int]:
    """The colours of the document's struck, coloured text — empty when it has none,
    which is every document that is not marked up (see the note above)."""
    colours: set[int] = set()
    for page in doc:
        if not _has_coloured_rule(page):
            continue
        for block in _styled_text(page)["blocks"]:
            for line in block.get("lines", ()):
                colours |= {s["color"] for s in line["spans"]
                            if s.get("char_flags", 0) & 1 and not _neutral(s["color"])
                            and s["text"].strip()}
    return frozenset(colours)


def _revision_blocks(styled: dict, colours: frozenset[int]) -> list[tuple]:
    """The page's text blocks, `get_text("blocks")`-shaped, with each change marked."""
    blocks = []
    for block in styled["blocks"]:
        if block.get("type", 0) != 0:
            continue
        lines = []
        for line in block.get("lines", ()):
            text = ""
            for span in line["spans"]:
                if span["color"] not in colours:
                    text += span["text"]
                elif span.get("char_flags", 0) & 1:
                    text += _DEL_OPEN + span["text"] + _DEL_CLOSE
                else:
                    text += _INS_OPEN + span["text"] + _INS_CLOSE
            lines.append(text)
        blocks.append((*block["bbox"], "\n".join(lines) + "\n", block["number"], 0))
    return blocks


def _bold_lines(styled: dict, colours: frozenset[int]) -> frozenset[str]:
    """Lines set all in bold, as their proposed text reads (`_bold_heading`)."""
    bold = set()
    for block in styled["blocks"]:
        for line in block.get("lines", ()):
            spans = [s for s in line["spans"] if s["text"].strip() and not (
                s["color"] in colours and s.get("char_flags", 0) & 1)]
            if spans and all(s["flags"] & 16 or "bold" in s["font"].lower()
                             for s in spans):
                bold.add("".join(s["text"] for s in spans).strip())
    return frozenset(bold)


@dataclass
class _Change:
    """One tracked change, at ``start``..``end`` of the PROPOSED page text (the
    inserted run; equal when the change only deleted)."""
    start: int
    end: int
    deleted: str = ""
    inserted: str = ""


def _resolve_revisions(marked: str) -> tuple[str, list[_Change]]:
    """A page's marked text as its proposed text and its changes. A deletion followed
    at once by an insertion is ONE change ("3" -> "5"); a line that held only deleted
    text (and its bullet) is dropped whole rather than left as an empty bullet."""
    out: list[str] = []
    changes: list[_Change] = []
    pos = 0
    for line in marked.split("\n"):
        kept, i, deleted_any = "", 0, False
        line_changes: list[_Change] = []
        for m in re.finditer(f"{_DEL_OPEN}(.*?){_DEL_CLOSE}|{_INS_OPEN}(.*?){_INS_CLOSE}",
                             line, re.S):
            kept += line[i:m.start()]
            at = pos + len(kept)
            deleted, inserted = m.group(1) or "", m.group(2) or ""
            deleted_any |= bool(deleted)
            kept += inserted
            last = line_changes[-1] if line_changes else None
            if last and last.end == at:           # adjacent runs are one change
                last.end += len(inserted)
                last.deleted += deleted
                last.inserted += inserted
            else:
                line_changes.append(_Change(at, at + len(inserted), deleted, inserted))
            i = m.end()
        kept += line[i:]
        if deleted_any and not kept.strip(_BULLETS) and out:
            gone = "\n" + line.translate(_MARKERS)  # the line as it stood, bullet and all
            at = pos - 1                          # the end of the previous kept line
            last = changes[-1] if changes else None
            if last and last.start == last.end == at:   # deleted lines run on, in order
                last.deleted += gone
            else:
                changes.append(_Change(at, at, deleted=gone))
            continue
        out.append(kept)
        changes += line_changes
        pos += len(kept) + 1
    proposed = "\n".join(out)
    # One change wrapped over several printed lines is ONE change: runs whose gap in
    # the proposed text is only a line break or spaces are joined, each side with a space.
    merged: list[_Change] = []
    for change in changes:
        last = merged[-1] if merged else None
        if last and change.start >= last.end and not proposed[last.end:change.start].strip():
            gap = " " if last.end < change.start else ""
            last.deleted = " ".join(p for p in (last.deleted, change.deleted) if p)
            last.inserted = (last.inserted + gap + change.inserted) if change.inserted \
                else last.inserted
            last.end = max(last.end, change.end)
        else:
            merged.append(change)
    return proposed, merged


def _record_revisions(segments: list[Segment], changes: list[_Change], base: int) -> int:
    """Each change onto the segment that holds it: metadata `revision` = the original
    text and the changes, in the document's words. Returns the changes placed."""
    placed = 0
    for segment in segments:
        start = (segment.start_offset or 0) - base
        end = (segment.end_offset or 0) - base
        own = [c for c in changes if start <= c.start and c.end <= end]
        if not own:
            continue
        original = segment.original_content
        for c in sorted(own, key=lambda c: c.start, reverse=True):
            original = original[:c.start - start] + c.deleted + original[c.end - start:]
        # A wholly inserted line is an empty one in the original; a PDF page has no
        # blank lines of its own (its blocks are joined by one newline), so none is kept.
        original = "\n".join(line for line in original.split("\n") if line.strip())
        segment.metadata = {**segment.metadata, "revision": {
            "original": normalize_text(original),
            "changes": [{"deleted": normalize_text(c.deleted),
                         "inserted": normalize_text(c.inserted)} for c in own]}}
        placed += len(own)
        changes = [c for c in changes if c not in own]
    return placed


def _continues(previous: Segment, segment: Segment, furniture: set[str]) -> bool:
    """Whether a page's first segment carries on the previous page's last clause: no
    number, no heading of its own, and a sentence visibly running on — this one starts
    lower-case, or the one above breaks on a comma or a hyphen. A capital after a line
    with no full stop is NOT enough: a signature block above "IN WITNESS WHEREOF" ends
    unpunctuated too. A page footer repeated across pages is never continued."""
    return (segment.page_number != previous.page_number
            and segment.source_type is EvidenceSourceType.NATIVE_TEXT
            and previous.source_type is EvidenceSourceType.NATIVE_TEXT
            and not segment.section_number and not segment.metadata.get("heading")
            and previous.content not in furniture
            and (segment.content[:1].islower()
                 or previous.content.rstrip().endswith((",", "-", "\u2013"))))


def _stitch_pages(segments: list[Segment]) -> list[Segment]:
    """One clause across a page break is one segment (AM-146): its page is where it
    starts, `end_page` where it ends, its offsets span both."""
    seen = Counter(s.content for s in segments)
    furniture = {text for text, n in seen.items() if n > 1}
    out: list[Segment] = []
    for segment in segments:
        previous = out[-1] if out else None
        if previous is None or not _continues(previous, segment, furniture):
            out.append(segment)
            continue
        joined = previous.original_content + "\n" + segment.original_content
        halves = (previous, segment)
        metadata = {**previous.metadata, "end_page": segment.page_number}
        if any(s.metadata.get("revision") for s in halves):
            metadata["revision"] = {
                "original": "\n".join((s.metadata.get("revision") or {}).get(
                    "original", s.content) for s in halves),
                "changes": [c for s in halves for c in
                            (s.metadata.get("revision") or {}).get("changes", ())]}
        out[-1] = Segment(content=normalize_text(joined), original_content=joined,
                          source_type=previous.source_type,
                          page_number=previous.page_number,
                          section_number=previous.section_number,
                          section_title=previous.section_title,
                          start_offset=previous.start_offset,
                          end_offset=segment.end_offset,
                          metadata=metadata)
    return out


def _page_blocks_in_reading_order(page, docling_tables: list[dict] | None = None,
                                  revision: tuple[dict, frozenset[int]] | None = None,
                                  ) -> tuple[str, bool]:
    """The page's prose in READING order, tables inline as `| a | b |` rows — and
    whether one of them is Docling's (``docling_tables``, `_inline_tables`).

    `get_text("text")` walks the PDF content stream, which on a two-column layout
    emits an entire column before the next: measured on the DPDP Act's penalty
    Schedule, a breach label and its penalty landed 699 characters apart. Sorting
    blocks into row-bands (y, then x) puts them 113 apart.

    `get_text(sort=True)` reorders too but joins spans with no separator — on
    SLA-leapswitch.pdf it produced `*99.95%forPower(Dual-poweredservers)`, which no
    lexical search matches — so whole blocks are sorted and each block's own text is
    left exactly as it was. The 6-point band absorbs the baseline jitter of a
    justified line.

    Only pages that need it are reordered; see `_reads_in_columns` for why, and for
    what happened when every page was.

    Rotation (R2): block coordinates are UNROTATED, so the column test takes the
    cropbox height, not the rotation-adjusted `page.rect`; and the (y, x) sort assumes
    horizontal text — on a 270-degree page whose footer was drawn first it reversed
    the clauses — so a page whose text is MOSTLY non-horizontal keeps stream order.
    Mostly, not any: the CloudPe web prints carry one vertical "Brochure" tab, and
    "any" moved their whole page-1 navigation (AUP, SLA, PRIVACY, TOS) — the R1
    baseline this change must not touch.

    ponytail (R1): page furniture drawn out of order (a footer first, a print header
    last) still fires the column test on most single-column pages. Ignoring the top
    and bottom ~8% would fix it, but it moves the text embeddings were built from, so
    it waits for a zero-Gemini retrieval re-measure on a scratch DB.
    """
    # ``revision`` (a marked-up document's page, AM-146): its styled read and revision
    # colours — the same blocks, each change marked for `_resolve_revisions`.
    kept = (_revision_blocks(*revision) if revision else
            [b for b in page.get_text("blocks") if b[6] == 0])   # 0 = text, 1 = image
    try:
        kept = _inline_tables(page, kept, docling_tables)
    except Exception:                       # pragma: no cover - defensive
        pass        # the table is an improvement; its failure must not cost the page
    if _reads_in_columns(kept, page.cropbox.height) and not _mostly_vertical(page):
        kept.sort(key=lambda b: (round(b[1] / 6), b[0]))
    return ("\n".join(b[4].strip() for b in kept if b[4].strip()),
            any(b[5] == _DOCLING_BLOCK for b in kept))


def parse_pdf(data: bytes, *, defer_ocr: bool = False, ocr: bool = True,
              docling: bool | None = None) -> ParseResult:
    """Native PDF text extraction, with OCR only where a page has none.

    Locked 34.7: OCR is used when a supported PDF does not contain usable text.
    Locked 34.9: if a page has no native text and OCR is unavailable or fails,
    that page is reported as failed — its text is never guessed.

    ``defer_ocr`` (2026-09-03, the ~63s-upload fix): when True and this document
    turns out to need OCR — a page with no usable native text, an image the text
    layer does not cover, or a native layer that is not legible — and the toolchain
    is present, the OCR is NOT run here.
    The result comes back with ``needs_ocr=True`` and no segments, so the caller
    can finish the upload quickly and run the OCR as its own background
    processing run (``ProcessingRunType.OCR``, locked 42.5). When the toolchain
    is absent there is nothing to defer to, and the fail-closed behaviour is
    exactly as before.

    ``ocr=False`` (2026-10-15) reads the text layer only, exactly as if the toolchain
    were absent: a page needing OCR fails, the native pages are kept, an unread image
    region is reported — and nothing is ever deferred. For a caller that cannot wait
    for OCR and has nowhere to defer it to.

    Every page needing OCR is read in ONE parallel pass (OCR-SEQUENTIAL: 12 scanned
    pages 23.3 s one at a time, 6.6 s in parallel), and reassembled in page order, so
    offsets stay sequential exactly as the page-by-page loop left them.

    ``docling`` (owner decision 2026-10-15, "use docling"): ``None`` reads TABLES with
    Docling when it is configured (`docling_available`), ``False`` never. Prose is
    always this parser's: Docling only regroups a page's own words into table rows
    (`_inline_tables`), on the pages that can hold a table (`_table_rules`). A read
    that cannot wait (``ocr=False``) never runs it; a deferred one with such a page
    defers, because Docling takes seconds a page.
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

    docling_pages: list[int] = []
    if docling is not False and ocr and docling_available():
        try:
            docling_pages = [index for index, page in enumerate(doc, start=1)  # type: ignore[arg-type,var-annotated]
                             if _table_rules(page) >= DOCLING_MIN_RULES]
        except Exception:                   # pragma: no cover - defensive
            pass                            # no gate, no Docling: the standard read
    if defer_ocr and 0 < len(docling_pages) <= DOCLING_MAX_PAGES_TOTAL:
        pages_total = doc.page_count
        doc.close()
        return ParseResult(
            segments=[], status=ExtractionStatus.FAILED,  # provisional — see needs_ocr
            pages_total=pages_total, diagnostics=[
                f"table reading of {len(docling_pages)} page(s) deferred to a "
                "background run"], needs_ocr=True, reader={"docling_deferred": True})
    tables, reader = _docling_tables(doc, docling_pages) if docling_pages else ({}, {})

    can_ocr = ocr and ocr_available()
    no_ocr = ("OCR not run for this read" if ocr_available()
              else "OCR toolchain unavailable")
    native: dict[int, str] = {}
    ocr_pages: list[int] = []                       # no usable native text (34.7)
    regions: list[tuple[int, tuple]] = []           # an image the text layer misses (F5)
    # A marked-up document only (AM-146): its revision colours, each page's tracked
    # changes and its bold lines. Empty for every other document, which reads as before.
    try:
        colours = _revision_colours(doc)
    except Exception:                       # pragma: no cover - defensive
        colours = frozenset()               # unread marks: the plain read, as before
    changes: dict[int, list[_Change]] = {}
    bold: dict[int, frozenset[str]] = {}

    # `doc` is a PyMuPDF Document; the library ships no type information, so the
    # page objects are untyped here rather than wrongly typed.
    for index, page in enumerate(doc, start=1):    # type: ignore[arg-type,var-annotated]
        try:
            revision = None
            if colours:
                styled = _styled_text(page)
                bold[index] = _bold_lines(styled, colours)
                if any(s["color"] in colours for b in styled["blocks"]
                       for line in b.get("lines", ()) for s in line["spans"]):
                    revision = (styled, colours)
            raw, by_docling = _page_blocks_in_reading_order(page, tables.get(index),
                                                            revision)
            if revision:
                raw, changes[index] = _resolve_revisions(raw)
            if by_docling:
                reader["docling_tables"].append(index)
        except Exception as exc:                # pragma: no cover - defensive
            raw = ""
            diagnostics.append(f"page {index}: extraction error {type(exc).__name__}")
        if len(raw.strip()) >= MIN_USABLE_CHARS_PER_PAGE:
            native[index] = raw
            regions += [(index, rect) for rect in _unread_images(page)]
        else:
            ocr_pages.append(index)

    pages_total = doc.page_count
    failed_pages: list[int] = []
    #: Pages whose native text was read but an image region on them was not: reported
    #: PARTIAL (34.10), never COMPLETE — the region may hold the clause asked about.
    partly_read: set[int] = set()
    if not can_ocr:
        partly_read |= {index for index, _ in regions}
        for index in ocr_pages:
            failed_pages.append(index)
            diagnostics.append(
                f"page {index}: no usable native text and {no_ocr}; page not extracted")
        diagnostics += [f"page {index}: image region not read ({no_ocr})"
                        for index in sorted({index for index, _ in regions})]

    # Locked 34.3 — "detect when normal extraction is INSUFFICIENT and use OCR
    # where supported". Presence was checked per page above; legibility is
    # checked here, once, over the whole document (see the notes on
    # MIN_WORDS_TO_JUDGE_LEGIBILITY for why never per page). The pages' raw text
    # and their segments carry the same words, so either may be judged.
    native_text = "\n".join(native.values())
    native_legible = text_is_legible(native_text)

    if defer_ocr and can_ocr and (ocr_pages or regions or native_legible is False):
        # OCR is needed and the toolchain is present — hand the decision back to
        # the caller. Without the toolchain there is nothing to defer to, and the
        # existing fail-closed path below concludes now rather than later.
        if ocr_pages:
            diagnostics.append(
                f"{len(ocr_pages)} page(s) have no usable native text; "
                "OCR deferred to a background run")
        if regions:
            diagnostics.append(
                f"{len({index for index, _ in regions})} page(s) carry an image the "
                "text layer does not cover; OCR deferred to a background run")
        if native_legible is False:
            diagnostics.append(
                "native text is not legible (function-word share "
                f"{stopword_share(native_text):.3f} < {ILLEGIBLE_STOPWORD_SHARE}); "
                "OCR deferred to a background run")
        doc.close()
        return ParseResult(
            segments=[], status=ExtractionStatus.FAILED,  # provisional — see needs_ocr
            pages_total=pages_total, pages_extracted=0, pages_failed=[],
            diagnostics=diagnostics, needs_ocr=True)

    if native_legible is False:
        ocr_segments, ocr_extracted, failed_pages, ocr_low = _reextract_illegible(
            data, pages_total, native_text, diagnostics, can_ocr, no_ocr)
        doc.close()
        return ParseResult(
            segments=ocr_segments, status=_status_for(pages_total, ocr_extracted),
            pages_total=pages_total, pages_extracted=ocr_extracted,
            pages_failed=failed_pages, diagnostics=diagnostics,
            pagination_source=PDF_PHYSICAL_PAGES if ocr_extracted else None,
            pages_low_confidence=ocr_low)
    doc.close()

    reads: dict[int, list[tuple[tuple | None, _OcrOutcome]]] = {}
    if can_ocr and (ocr_pages or regions):
        jobs = [(index, None) for index in ocr_pages] + regions
        outcomes = _ocr_pages_parallel(data, [index for index, _ in jobs],
                                       [clip for _, clip in jobs])
        for (index, clip), (_, outcome) in zip(jobs, outcomes, strict=True):
            reads.setdefault(index, []).append((clip, outcome))
        diagnostics.append(f"OCR languages: {config.ocr_languages()}")

    # Each page's reading as (text, source, metadata) parts, in order: segmented
    # below by ONE loop, native text and OCR alike.
    parts: dict[int, list[tuple[str, EvidenceSourceType, dict]]] = {}
    low_confidence: list[int] = []
    extracted_pages = 0
    for index in range(1, pages_total + 1):
        if index in native:
            parts[index] = [(native[index], EvidenceSourceType.NATIVE_TEXT, {})]
            extracted_pages += 1
        for clip, outcome in reads.get(index, ()):
            if clip is not None and not isinstance(outcome, Exception) and \
                    len(outcome[0].strip()) < MIN_USABLE_CHARS_PER_PAGE:
                # Read, and blank: a photograph or a signature, not unread text. Said,
                # so a region that should have held text never vanishes silently.
                diagnostics.append(f"page {index}: image region has no readable text")
                continue
            kept = _read_ocr(index, outcome, diagnostics, low_confidence)
            if kept is None:
                if clip is None:
                    failed_pages.append(index)
                else:
                    partly_read.add(index)
                continue
            text, metadata = kept
            if clip is not None:
                metadata["ocr_region"] = [round(v, 1) for v in clip]
                diagnostics.append(f"page {index}: image region read by OCR")
            # 34.8 — OCR text explicitly identified.
            parts.setdefault(index, []).append((text, EvidenceSourceType.OCR, metadata))
            extracted_pages += clip is None

    partly_read -= set(failed_pages)
    failed_pages = sorted(failed_pages + list(partly_read))
    extracted_pages -= len(partly_read & set(native))

    if reader:
        for index in sorted(set(tables) & set(native) - set(reader["docling_tables"])):
            reader["fallback_reasons"][index] = "words differ or a ruled grid stands"
        diagnostics.append(_reader_diagnostic(reader))

    segments: list[Segment] = []
    offset = 0
    placed = 0
    for index, page_parts in sorted(parts.items()):
        for text, source, metadata in page_parts:
            page_segments = segment_paragraphs(text, page_number=index,
                                               source_type=source, base_offset=offset,
                                               bold_lines=bold.get(index, frozenset()))
            for segment in page_segments:
                segment.metadata = {**segment.metadata, **metadata}
            if source is EvidenceSourceType.NATIVE_TEXT and changes.get(index):
                placed += _record_revisions(page_segments, changes[index], offset)
            segments += page_segments
            offset += len(text)
    if colours:
        segments = _stitch_pages(segments)
        diagnostics.append(
            f"revision marks read (AM-146): {placed} tracked change(s) on page(s) "
            f"{sorted(p for p, c in changes.items() if c)}; evidence is the proposed "
            "text, the original is kept on each changed segment")

    # The document-level backstop over OCR text too (34.9). Per-page confidence above
    # is the page-level signal; this backs up the pages it could not vouch for (no
    # score, or under OCR_WARN_CONFIDENCE). A confidently read scan is never judged by
    # function words: a scanned price list or credit table has almost none, and the
    # backstop threw such pages away (review, 2026-10-16).
    def doubtful(segment: Segment) -> bool:
        return segment.source_type is EvidenceSourceType.OCR and (
            segment.metadata.get("ocr_confidence") or 0) < OCR_WARN_CONFIDENCE
    ocr_text = "\n".join(s.content for s in segments if doubtful(s))
    if text_is_legible(ocr_text) is False:
        dropped = {s.page_number or 0 for s in segments if doubtful(s)}
        lost = sorted(dropped - set(native))          # pages left with no text at all
        segments = [s for s in segments if not doubtful(s)]
        # a native page that lost its region's text is read in part, as above
        regions_lost = (dropped & set(native)) - set(failed_pages)
        failed_pages = sorted(set(failed_pages) | dropped)
        extracted_pages -= len(lost) + len(regions_lost)
        low_confidence = [p for p in low_confidence if p not in dropped]
        diagnostics.append(
            f"OCR output is not legible; {len(lost)} page(s) not extracted and "
            "image-region text dropped")

    return ParseResult(segments=segments,
                       status=_status_for(pages_total, extracted_pages),
                       pages_total=pages_total,
                       pages_extracted=extracted_pages, pages_failed=failed_pages,
                       diagnostics=diagnostics,
                       pagination_source=PDF_PHYSICAL_PAGES if extracted_pages else None,
                       pages_low_confidence=sorted(set(low_confidence)), reader=reader)


# --------------------------------------------------------------------------
# Docling — owner decision 2026-10-15, "use docling": TABLES only
# --------------------------------------------------------------------------
# Measured on the supplied corpus (bench, 2026-10-15): table cells 89.2% against 3.7%,
# and it reads SLA-cloudpe's horizontal-rule credit tables, which PyMuPDF cannot. Its
# prose was no better than this parser's and, as a page-text replacement, duplicated a
# paragraph across a page break, moved a notice address between clauses and could flip
# a clause by one word (adversarial review). So prose is never Docling's: its tables
# regroup a page's own words into rows (`_inline_tables`), and nothing else.

#: A page goes to Docling only with at least this many thin horizontal rules of one
#: horizontal extent (`_table_rules`). Calibrated 2026-10-15 on the 13 approved PDFs:
#: 18 of 137 pages pass (MSA.pdf 13 -> 2), SLA-cloudpe pp. 1-2 and SLA-leapswitch p. 1
#: (the real tables) among them; Companies Act 2013 60 of 370 (was 70 of 370).
DOCLING_MIN_RULES = 3

#: Pages per child run: the child's memory grows with the pages it is sent, inside the
#: API's cgroup, so a document is read in runs of at most this many (one at a time, each
#: with its own lock wait and deadline) and the results merged. A document with more
#: gated pages than DOCLING_MAX_PAGES_TOTAL is not sent at all — its standard tables
#: stand (reason "too many table pages for Docling").
DOCLING_MAX_PAGES_PER_RUN = 12
DOCLING_MAX_PAGES_TOTAL = 60

#: Each child run's wall-clock budget: 60 s to load the models, 20 s a page, never past
#: 30 minutes. Waiting for the locks is bounded by the same figure.
DOCLING_TIMEOUT_BASE_S = 60
DOCLING_TIMEOUT_PER_PAGE_S = 20
DOCLING_TIMEOUT_MAX_S = 1800

#: One conversion at a time — in this process (the lock) and across this service's
#: processes (the flock on a file in its tempdir; each systemd service has a private
#: /tmp, so the API and the worker each run one, never one for the whole host): each
#: child holds over a gigabyte. ponytail: a queue of one per service; a single worker
#: service when uploads outrun it.
_DOCLING_LOCK = threading.Lock()
_DOCLING_LOCK_FILE = "legalmind-docling.lock"
_DOCLING_RUNNER = Path(__file__).with_name("docling_runner.py")

#: The pseudo-block number `_inline_tables` gives a Docling table (PyMuPDF's is -1).
_DOCLING_BLOCK = -2


def docling_available() -> bool:
    """Whether Docling is configured: its python executable and its models exist."""
    python, models = config.docling_python(), config.docling_models()
    return bool(python and models and os.access(python, os.X_OK)
                and os.path.isdir(models))


def _oom_first(command: list[str]) -> list[str]:
    """``command`` run first in line for the kernel's OOM killer (no privilege is needed
    to RAISE a score), so a large document costs the Docling child, never the API.
    Through util-linux `choom`, which sets the score and execs: a `preexec_fn` would run
    Python between fork and exec in this multithreaded process, which can deadlock the
    child while it holds the Docling lock (review, 2026-10-16). No `choom`, no change."""
    choom = shutil.which("choom")
    return [choom, "-n", "1000", "--", *command] if choom else command


def _docling_read(data: bytes, page_count: int) -> tuple[dict | None, str | None]:
    """Docling's neutral JSON for ``data`` (see docling_runner.py), or None and why.

    A separate process from a separate environment, offline, one at a time, with a
    timeout, first in line for the OOM killer. Its output is never logged — stderr
    would carry document text."""
    import fcntl
    import json
    import subprocess
    import tempfile
    import time

    python, models = config.docling_python(), config.docling_models()
    timeout = min(DOCLING_TIMEOUT_MAX_S,
                  DOCLING_TIMEOUT_BASE_S + DOCLING_TIMEOUT_PER_PAGE_S * page_count)
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryDirectory() as tmp:
        Path(f"{tmp}/in.pdf").write_bytes(data)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp,
               "TMPDIR": tmp, "LANG": "C.UTF-8", "OMP_NUM_THREADS": "2",
               "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
               "HF_HUB_DISABLE_TELEMETRY": "1"}
        if "TESSDATA_PREFIX" in os.environ:
            env["TESSDATA_PREFIX"] = os.environ["TESSDATA_PREFIX"]
        command = [str(python), "-I", str(_DOCLING_RUNNER),
                   f"{tmp}/in.pdf", f"{tmp}/out.json", str(models),
                   config.ocr_languages()]
        if not _DOCLING_LOCK.acquire(timeout=timeout):
            return None, "Docling busy"
        try:
            with open(Path(tempfile.gettempdir(), _DOCLING_LOCK_FILE), "w") as lock:
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            return None, "Docling busy"
                        time.sleep(0.5)
                proc = subprocess.run(_oom_first(command), capture_output=True,
                                      timeout=timeout, check=False, env=env, cwd=tmp)
        except subprocess.TimeoutExpired:
            return None, f"Docling timed out after {timeout} s"
        except OSError as exc:
            return None, f"Docling could not start ({type(exc).__name__})"
        finally:
            _DOCLING_LOCK.release()
        if proc.returncode < 0:
            return None, f"Docling was killed (signal {-proc.returncode})"
        if proc.returncode:
            return None, f"Docling exited {proc.returncode}"
        try:
            return json.loads(Path(f"{tmp}/out.json").read_text(encoding="utf-8")), None
        except (OSError, ValueError):
            return None, "Docling wrote no readable output"


def _docling_shape(reading: object, sent: int) -> dict[int, list[dict]] | None:
    """The runner's pages as {subset page: tables}, or None when the JSON is not the
    shape docling_runner.py writes — never trusted past this check."""
    def number(v: object) -> bool:
        return isinstance(v, int | float) and not isinstance(v, bool)

    def box(b: object) -> bool:
        return isinstance(b, list) and len(b) == 4 and all(map(number, b))

    def table(t: object) -> bool:
        return (isinstance(t, dict) and box(t.get("bbox"))
                and isinstance(t.get("rows"), list)
                and all(isinstance(r, list) and all(isinstance(c, str) for c in r)
                        for r in t["rows"])
                and isinstance(t.get("cells"), list)
                and all(isinstance(c, dict) and isinstance(c.get("text"), str)
                        and box(c.get("bbox")) for c in t["cells"]))

    if not isinstance(reading, dict) or not isinstance(reading.get("pages"), dict):
        return None
    pages = reading["pages"]
    if not all(isinstance(k, str) and k.isdigit() and 1 <= int(k) <= sent
               and isinstance(v, list) and all(map(table, v)) for k, v in pages.items()):
        return None
    return {int(k): v for k, v in pages.items()}


def _docling_tables(doc, pages: list[int]) -> tuple[dict[int, list[dict]], dict]:
    """Docling's tables for ``pages`` (1-based) of ``doc``, by original page number, and
    the reader record. Only those pages are sent, as subset PDFs of at most
    DOCLING_MAX_PAGES_PER_RUN pages, one run after another. Never raises: any Docling
    problem is a fallback reason for the pages not yet read, no further run is made,
    and the standard tables stand."""
    import pymupdf

    reader: dict = {"docling_version": None, "docling_pages": pages,
                    "docling_tables": [], "fallback_reasons": {}}
    if len(pages) > DOCLING_MAX_PAGES_TOTAL:
        reader["fallback_reasons"] = dict.fromkeys(
            pages, "too many table pages for Docling")
        return {}, reader
    tables: dict[int, list[dict]] = {}
    for start in range(0, len(pages), DOCLING_MAX_PAGES_PER_RUN):
        run = pages[start:start + DOCLING_MAX_PAGES_PER_RUN]
        try:
            subset = pymupdf.open()
            for index in run:
                subset.insert_pdf(doc, from_page=index - 1, to_page=index - 1)
            data = subset.tobytes()
            subset.close()
            reading, reason = _docling_read(data, len(run))
            shaped = None if reading is None else _docling_shape(reading, len(run))
            if reading is not None and shaped is None:
                reason = "Docling output malformed"
        except Exception as exc:            # the fallback IS the handling
            shaped, reason = None, f"Docling failed ({type(exc).__name__})"
        if shaped is None:
            reader["fallback_reasons"] = dict.fromkeys(pages[start:], reason)
            break
        version = reading.get("docling_version") if isinstance(reading, dict) else None
        if isinstance(version, str):
            reader["docling_version"] = version
        tables.update({run[k - 1]: found for k, found in shaped.items()})
    return tables, reader


def _reader_diagnostic(reader: dict) -> str:
    """'Docling 2.139.0 read tables on 3 page(s): inlined on pages 1, 2; standard
    tables on page(s) 3 (words differ or a ruled grid stands)'."""
    line = (f"Docling {reader['docling_version'] or ''} read tables on "
            f"{len(reader['docling_pages'])} page(s)").replace("  ", " ")
    if reader["docling_tables"]:
        line += ": inlined on pages " + ", ".join(map(str, reader["docling_tables"]))
    by_reason: dict[str, list[str]] = {}
    for page, reason in reader["fallback_reasons"].items():
        by_reason.setdefault(reason, []).append(str(page))
    if by_reason:
        line += "; standard tables on " + "; ".join(
            f"page(s) {', '.join(pages)} ({why})" for why, pages in by_reason.items())
    return line


def _unread_images(page) -> list[tuple[float, float, float, float]]:
    """Placed images big enough to carry text the text layer does not have (F5).

    A page with 20 native characters was taken as read whole, so a scanned annex
    pasted onto a typed page was lost and the page still reported COMPLETE. The rule:
    an image covering >= IMAGE_REGION_MIN_SHARE of the page with fewer than
    MIN_USABLE_CHARS_PER_PAGE text-layer characters centred inside it. Calibrated on
    35 approved PDFs (3,333 pages): it flags no page the old rule did not already
    OCR — logos are under 10% of a page, TOS-leapswitch p1's 25% banner has 1,000+
    native characters over it, and the Income-tax Act's scans carry a text layer.

    Image boxes and words are in UNROTATED page space, so area and words are judged
    against the cropbox; the clip returned is for `get_pixmap`, which takes ROTATED
    coordinates — on a /Rotate 90 page the unrotated box rendered blank and the annex
    was lost silently (review, 2026-10-16).
    """
    import pymupdf

    large = [rect for rect in (pymupdf.Rect(info["bbox"]) & page.cropbox
                               for info in page.get_image_info())
             if abs(rect) >= IMAGE_REGION_MIN_SHARE * abs(page.cropbox)]
    words = page.get_text("words") if large else []
    rects = []
    for rect in large:
        inside = sum(len(w[4]) for w in words
                     if pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2) in rect)
        if inside < MIN_USABLE_CHARS_PER_PAGE:
            rects.append(tuple(rect * page.rotation_matrix))
    return rects


def _read_ocr(index: int, outcome: _OcrOutcome, diagnostics: list[str],
              low_confidence: list[int]) -> tuple[str, dict] | None:
    """The per-page OCR gate: the text and its segment metadata, or None and why.

    Length alone was the only test (R3), so a sideways scan read as gibberish was
    stored COMPLETE. Mean word confidence separates the two where the function-word
    test cannot — it needs 200 words, and noisy scans still pass it (OCR-QUALITY).
    """
    if isinstance(outcome, Exception):
        diagnostics.append(f"page {index}: OCR failed ({type(outcome).__name__})")
        return None
    text, confidence = outcome
    if len(text.strip()) < MIN_USABLE_CHARS_PER_PAGE:
        diagnostics.append(f"page {index}: OCR produced no usable text")
        return None
    if confidence is None:
        return text, {}
    if confidence < OCR_FAIL_CONFIDENCE:
        diagnostics.append(
            f"page {index}: OCR text not reliable (mean confidence {confidence:.1f})")
        return None
    if confidence < OCR_WARN_CONFIDENCE:
        low_confidence.append(index)
        diagnostics.append(f"page {index}: low OCR confidence ({confidence:.1f})")
    return text, {"ocr_confidence": round(confidence, 1)}


def _reextract_illegible(
    data: bytes, page_count: int, native_text: str, diagnostics: list[str],
    can_ocr: bool, no_ocr: str,
) -> tuple[list[Segment], int, list[int], list[int]]:
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

    Returns ``(segments, pages_extracted, pages_failed, pages_low_confidence)``.
    """
    share = stopword_share(native_text)
    diagnostics.append(
        "native text is not legible (function-word share "
        f"{share:.3f} < {ILLEGIBLE_STOPWORD_SHARE}); the embedded fonts most "
        "likely carry an incorrect ToUnicode mapping")

    all_pages = list(range(1, page_count + 1))
    if not can_ocr:
        diagnostics.append(
            f"{no_ocr}, so no legible text can be produced; "
            "no text is returned rather than returning unreadable text")
        return [], 0, all_pages, []

    ocr_segments: list[Segment] = []
    ocr_failed: list[int] = []
    low_confidence: list[int] = []
    ocr_pages = 0
    offset = 0
    # Pages OCR independently, so they run in parallel and are reassembled in
    # page order — same input, same output, same order as the sequential loop
    # this replaces (measured byte-identical on the real 30-page document;
    # 65.6s -> 16.2s on 4 cores). Each worker opens its own document handle from
    # `data` because PyMuPDF objects are not safe to share across threads.
    for index, outcome in _ocr_pages_parallel(data, all_pages):
        kept = _read_ocr(index, outcome, diagnostics, low_confidence)
        if kept is None:
            ocr_failed.append(index)
            continue
        ocr_text, metadata = kept
        for segment in segment_paragraphs(
                ocr_text, page_number=index,
                source_type=EvidenceSourceType.OCR, base_offset=offset):
            segment.metadata = {**segment.metadata, **metadata}
            ocr_segments.append(segment)
        ocr_pages += 1
        offset += len(ocr_text)
    diagnostics.append(f"OCR languages: {config.ocr_languages()}")

    ocr_legible = text_is_legible("\n".join(s.content for s in ocr_segments))
    if ocr_legible is not True:
        # OCR ran and is no better. Keeping the native mojibake would be the
        # worse of two bad options: it looks like content.
        diagnostics.append(
            "OCR did not produce legible text either; no text is returned")
        return [], 0, all_pages, []

    diagnostics.append(
        f"re-extracted {ocr_pages} of {page_count} page(s) by OCR "
        "(marked OCR-derived); the native text was discarded as unreadable")
    return ocr_segments, ocr_pages, ocr_failed, sorted(set(low_confidence))


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

#: OCR mean word confidence (tesseract's tsv ``conf``, words scoring >= 0). Below
#: OCR_FAIL_CONFIDENCE a page's OCR text is not kept and the page FAILS closed (34.9);
#: below OCR_WARN_CONFIDENCE it is kept, flagged in segment metadata
#: (``ocr_confidence``), ``pages_low_confidence`` and a diagnostic.
#: Calibration knobs, not constants of nature — measured 2026-10-15 on SLA-leapswitch
#: p1 and the Income-tax Act p2/p101 rendered, degraded and rotated, against their own
#: text layer: every readable read (similarity >= 0.91) scored >= 77.8, every
#: unreadable one (<= 0.742) <= 52.2; clean 300 dpi pages score ~94, sideways ~35.
OCR_FAIL_CONFIDENCE = 60.0
OCR_WARN_CONFIDENCE = 80.0

#: The share of a page an image must cover before `_unread_images` reads it (F5).
IMAGE_REGION_MIN_SHARE = 0.15

#: One OCR read: (text, mean word confidence or None when no word was found), or the
#: exception that stopped it.
_OcrOutcome = tuple[str, float | None] | Exception


def _ocr_page(page, clip=None) -> tuple[str, float | None]:  # pragma: no cover
    """OCR a single page, or the ``clip`` region of it, via the locked toolchain.

    Only reached when the toolchain is present; absence is handled by the caller
    as a failure, never as empty text.
    """
    pix = page.get_pixmap(dpi=OCR_RENDER_DPI, clip=clip)
    return _tesseract_pixmap(pix)


def _tesseract_pixmap(pix) -> tuple[str, float | None]:  # pragma: no cover
    """The text and the mean confidence of its words, from ONE tesseract process.

    ``txt tsv`` writes both outputs in one pass — the tsv's per-word ``conf`` is the
    quality signal (OCR-QUALITY) at no second OCR. ``--psm 1`` is automatic
    segmentation WITH orientation detection: a page scanned sideways or upside down
    read 0.076 similar under the default and 0.985 with it, upright output unchanged
    on the pages measured (R3). ``-l`` is the configured language set (F6).
    """
    import os
    import subprocess
    import tempfile
    from pathlib import Path

    # One thread per tesseract process: the parallelism lives at the page level,
    # and an unpinned tesseract would oversubscribe the cores it shares with the
    # other pages' workers.
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        image_path = f"{tmp}/page.png"
        pix.save(image_path)
        proc = subprocess.run(
            ["tesseract", image_path, f"{tmp}/out", "-l", config.ocr_languages(),
             "--psm", "1", "txt", "tsv"],
            capture_output=True, text=True, timeout=120, check=False, env=env)
        if proc.returncode != 0:
            raise ParseError(f"tesseract exited {proc.returncode}")
        text = Path(f"{tmp}/out.txt").read_text(encoding="utf-8")
        rows = [r.split("\t") for r in
                Path(f"{tmp}/out.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    confidences = [float(r[10]) for r in rows
                   if len(r) > 10 and r[0] == "5" and float(r[10]) >= 0]
    return text, (sum(confidences) / len(confidences) if confidences else None)


def _ocr_pages_parallel(
    data: bytes, pages: list[int], clips: list | None = None,
) -> list[tuple[int, _OcrOutcome]]:
    """OCR ``pages`` of ``data`` (each whole, or its ``clips`` entry when one is
    given), up to ``OCR_MAX_WORKERS`` at a time.

    Returns ``[(page_number, (text, confidence)-or-exception), ...]`` in the order
    asked regardless of completion order, so the caller's output is identical to a
    sequential pass. A page's failure is returned as its exception, never raised —
    one bad page must not cost the other twenty-nine (34.10).
    """
    import os
    from concurrent.futures import ThreadPoolExecutor

    import pymupdf

    def one(job: tuple[int, tuple | None]) -> _OcrOutcome:  # pragma: no cover
        index, clip = job
        try:
            # A thread-local document handle: PyMuPDF documents are not
            # thread-safe, and opening from bytes costs well under a millisecond.
            doc = pymupdf.open(stream=data, filetype="pdf")
            try:
                return _ocr_page(doc[index - 1], clip)
            finally:
                doc.close()
        except Exception as exc:
            return exc

    # A pool of 1 worker already runs `map` sequentially in submission order,
    # so there is no separate single-threaded path to maintain.
    workers = max(1, min(OCR_MAX_WORKERS, os.cpu_count() or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = zip(pages, clips or [None] * len(pages), strict=True)
        return list(zip(pages, pool.map(one, jobs), strict=True))


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# The values written to the processing run's `pagination_source`.
DOCX_RENDERED_PAGE_BREAKS = "DOCX_RENDERED_PAGE_BREAKS"
DOCX_EXPLICIT_PAGE_BREAKS = "DOCX_EXPLICIT_PAGE_BREAKS"
PDF_PHYSICAL_PAGES = "PDF_PHYSICAL_PAGES"


def _docx_row_breaks_once(body) -> set:
    """The rendered page breaks to ignore: Word lays each cell of a row out on its own,
    so a row split across a page records one boundary IN EVERY CELL — counted per cell,
    a two-cell row moved every later paragraph two pages on (review 2026-10-16). Only
    the first cell of each row that records one is kept."""
    skip = set()
    for tr in body.iter(_W + "tr"):
        seen_cell = False
        for tc in tr.iterchildren(_W + "tc"):
            breaks = [b for b in tc.iter(_W + "lastRenderedPageBreak")
                      if next(b.iterancestors(_W + "tr")) is tr]
            if breaks and seen_cell:
                skip.update(breaks)
            seen_cell = seen_cell or bool(breaks)
    return skip


def _docx_paragraph_pages(paragraphs, skip: frozenset | set = frozenset()) -> tuple[
        list[int] | None, int, str | None]:
    """The starting page of each ``w:p`` element, from the document's OWN record.

    The caller passes EVERY paragraph in document order, table cells included (PB):
    a break recorded inside a cell moves every later paragraph, and a table's page
    is its first cell paragraph's.

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
        for el in para.iter():
            if el in skip:
                continue
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
        for el in para.iter():
            if el in skip:
                continue
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


#: A run the accepted, visible document shows: not moved away, not deleted in a tracked
#: change, not hidden (w:vanish). The test a footnote reference and a text box's anchor
#: must pass too — what the reader never sees never reaches evidence (review 2026-10-16).
_VISIBLE_RUN = ("not(ancestor::w:moveFrom) and not(ancestor::w:del) and not(w:rPr/"
                "w:vanish[not(@w:val='0' or @w:val='false' or @w:val='off')])")


def _docx_text(p) -> str:
    """A ``w:p``'s text in the ACCEPTED view of its tracked changes: python-docx's
    run text PLUS the runs it skips — inside a tracked insertion (w:ins) or an
    inline content control. Deleted text is w:delText, which a run's text never
    includes, and moved-from runs are left out (A3).

    Only the runs whose NEAREST paragraph is ``p``: a text box's runs sit in a w:p
    nested inside its anchor and are read as paragraphs of their own (F4). Hidden
    text (w:vanish) is neither displayed nor printed, so it is not the document's
    text (N-HIDDEN). ponytail: hidden set through a character style is not
    resolved — walk the style chain if a real file ever does that.

    A page or column break is a line break here: python-docx reads it as "", which
    fused "…calendar days." and "Issued within…" into "days.Issued" across a break."""
    depth = len(p.xpath("ancestor-or-self::w:p"))
    return "".join("\n" if el.tag == _W + "br" else str(el) for r in p.xpath(
        f".//w:r[count(ancestor::w:p) = {depth} and {_VISIBLE_RUN}]")
        for el in r.xpath("w:br | w:cr | w:noBreakHyphen | w:ptab | w:t | w:tab"))


def _docx_revision(p) -> dict | None:
    """A ``w:p``'s tracked changes as `_record_revisions` records a PDF's (AM-146): the
    ORIGINAL text (deletions kept, insertions dropped) and each change. ``None`` for a
    paragraph with no tracked change — every paragraph of an unmarked document."""
    depth = len(p.xpath("ancestor-or-self::w:p"))
    runs = p.xpath(f".//w:r[count(ancestor::w:p) = {depth}"
                   " and not(ancestor::w:moveFrom)]")
    original, changes, current = "", [], None
    for run in runs:
        kind = ("deleted" if run.xpath("ancestor::w:del") else
                "inserted" if run.xpath("ancestor::w:ins") else None)
        text = "".join(el.text or "" for el in run.xpath("w:t | w:delText"))
        if kind != "inserted":
            original += text
        if kind is None:
            current = None if text else current
            continue
        if current is None:
            current = {"deleted": "", "inserted": ""}
            changes.append(current)
        current[kind] += text
    if not changes:
        return None
    return {"original": normalize_text(original),
            "changes": [{k: normalize_text(v) for k, v in c.items()} for c in changes]}


def _docx_children(el, *tags):
    """``el``'s child elements with one of ``tags``, in document order, looking
    through the wrappers that hold blocks, rows and cells without being them:
    content controls (w:sdt/w:sdtContent, A3) and custom XML (w:customXml, F4)."""
    for child in el.iterchildren():
        if child.tag in tags:
            yield child
        elif child.tag == _W + "sdt":
            for content in child.iterchildren(_W + "sdtContent"):
                yield from _docx_children(content, *tags)
        elif child.tag == _W + "customXml":
            yield from _docx_children(child, *tags)


def _docx_rows(tbl) -> list[list[str]]:
    """A ``w:tbl``'s non-empty rows as cell texts (F2b), rows and cells inside
    content controls included (F4). One entry per ``w:tc``, so a horizontally merged
    cell (gridSpan) is read once; a vertically merged one (vMerge) repeats its top
    cell's text on every row it spans, so each row reads whole on its own
    ("Tier 2 | 40% | Max 20% of monthly fee")."""
    rows: list[list[str]] = []
    above: dict[int, str] = {}
    for tr in _docx_children(tbl, _W + "tr"):
        cells: list[str] = []
        here: dict[int, str] = {}
        col = tr.grid_before
        for tc in _docx_children(tr, _W + "tc"):
            here[col] = above.get(col, "") if tc.vMerge == "continue" else _docx_cell(tc)
            cells.append(here[col])
            col += tc.grid_span
        above = here
        if any(cells):
            rows.append(cells)
    return rows


def _docx_cell(tc) -> str:
    """A cell's paragraphs joined with a space — a newline is the ROW separator, so
    a second paragraph read as a new row (F2d) — and a nested table inline as
    ``[a | b; c | d]`` (F2c), bracketed so its columns are never read as the outer
    row's and the outer row stays one line."""
    parts = []
    for block in _docx_children(tc, _W + "p", _W + "tbl"):
        if block.tag == _W + "p":
            parts.append(_docx_text(block))
        elif nested := _docx_rows(block):
            parts.append("[" + "; ".join(" | ".join(row) for row in nested) + "]")
    return " ".join(" ".join(part.split()) for part in parts if part.strip())


def _docx_part_xml(document, reltype):
    """A part related to the main document (footnotes, endnotes, comments), parsed;
    ``None`` when the document has none."""
    from docx.oxml import parse_xml
    try:
        return parse_xml(document.part.part_related_by(reltype).blob)
    except KeyError:
        return None


def _docx_notes(document, rt) -> dict[tuple[str, str], str]:
    """Footnote and endnote texts by (kind, w:id), Word's separator notes left out
    (F4) — a qualifier such as "fees exclude GST" is often only in a note."""
    notes: dict[tuple[str, str], str] = {}
    for kind, reltype in (("footnote", rt.FOOTNOTES), ("endnote", rt.ENDNOTES)):
        root = _docx_part_xml(document, reltype)
        for note in [] if root is None else root.iterchildren(_W + kind):
            # Word's own separator lines carry a w:type; a real note none or "normal".
            if note.get(_W + "type") in (None, "normal"):
                # (a parsed part is plain lxml: iterated, since `w:` is unbound here)
                notes[(kind, note.get(_W + "id"))] = "\n".join(
                    _docx_text(p) for p in note.iter(_W + "p")
                    if not any(a.tag.endswith("}Fallback") for a in p.iterancestors()))
    return notes


def _docx_furniture(document) -> list[tuple[str, str]]:
    """Each DISTINCT header and footer text ONCE, as (part, text) — locked 34.10
    identifies them separately (F4). Deduplicated by text across sections and the
    first-page/even-page variants: a header repeated per section would trip the
    index's REPEATED_TEXT gate and silently stop the document being indexed (BR-4)."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for section in document.sections:
        for part in ("header", "footer"):
            for variant in (part, f"first_page_{part}", f"even_page_{part}"):
                story = getattr(section, variant)
                if story.is_linked_to_previous:      # no definition of its own
                    continue
                text = "\n".join(_docx_text(p) for p in story._element.xpath(
                    ".//w:p[not(ancestor::*[local-name()='Fallback'])]"))
                if (key := normalize_text(text)) and key not in seen:
                    seen.add(key)
                    out.append((part, text))
    return out


def parse_docx(data: bytes) -> ParseResult:
    """DOCX extraction preserving paragraphs and tables (34.11), in document order.

    The body is read block by block as Word lays it out (F2e): paragraphs and
    tables where they stand, content controls and custom XML looked through, a
    text box's paragraphs right after its anchor, and a footnote or endnote right
    after the first block that references it (``part`` in metadata). Headers and
    footers come last, once each, as OTHER with ``part`` header/footer and no page
    — page furniture, never a clause (BR-4). Comments are reviewer notes, not the
    document's text, and are counted in diagnostics, never read (N-SILENT).

    Page numbers (2026-09-02): read from the document's own pagination record —
    see ``_docx_paragraph_pages``. Never computed, never guessed; absent record
    means absent pages. A table takes the page of its first cell paragraph, with
    breaks inside cells counted (PB). Word's automatic list numbering is not
    rendered (N-AUTONUM, awaiting an owner ruling on locked 34.12).
    """
    import io

    import docx
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError(f"DOCX could not be opened: {type(exc).__name__}") from exc

    body = document.element.body
    # Every paragraph in document order, table cells included, text boxes not (their
    # anchor already carries their breaks) — PB. Keyed by the elements held in this
    # list, so the lxml proxies stay the same objects for the lookups below.
    every = body.xpath(".//w:p[not(ancestor::w:txbxContent)]")
    paragraph_pages, total_pages, pagination_source = _docx_paragraph_pages(
        every, _docx_row_breaks_once(body))
    page_of = dict(zip(every, paragraph_pages, strict=True)) if paragraph_pages else {}

    blocks = list(_docx_children(body, _W + "p", _W + "tbl"))
    # The same markers the PDF path gets (see _structure_markers). Word puts each
    # paragraph in its own segment, so "the prose that follows" is the next
    # non-empty body paragraph rather than the segment's own second line.
    following: dict = {}
    after = None
    for block in reversed(blocks):
        if block.tag == _W + "p":
            following[block] = after
            after = normalize_text(_docx_text(block)) or after

    unread: list[str] = []

    def aux(name: str, read, default):
        """A footnote/endnote, header/footer or comments part that cannot be read is a
        diagnostic, never a failed document (review 2026-10-16): the body still is."""
        try:
            return read()
        except Exception as exc:
            unread.append(f"{name} could not be read ({type(exc).__name__})")
            return default

    notes = aux("footnotes and endnotes", lambda: _docx_notes(document, RT), {})
    segments: list[Segment] = []
    offset = 0

    def emit(raw: str, source: EvidenceSourceType, page: int | None,
             number: str | None = None, title: str | None = None,
             metadata: dict | None = None) -> None:
        nonlocal offset
        if normalized := normalize_text(raw):
            segments.append(Segment(
                content=normalized, original_content=raw, source_type=source,
                page_number=page, section_number=number, section_title=title,
                start_offset=offset, end_offset=offset + len(raw),
                metadata=metadata or {}))
        offset += len(raw)

    def paragraph(p, page: int | None, next_text: str | None) -> None:
        raw = _docx_text(p)
        normalized = normalize_text(raw)
        if not normalized:
            return emit(raw, EvidenceSourceType.NATIVE_TEXT, page)
        first_line = normalized.split("\n", 1)[0]
        number, title = detect_clause_number(first_line)
        title, markers = _structure_markers(
            normalized, first_line, number, title, next_text)
        style = Paragraph(p, document._body).style
        revision = _docx_revision(p)
        emit(raw, EvidenceSourceType.NATIVE_TEXT, page, number, title,
             {"style": style.name if style else None, **markers,
              **({"revision": revision} if revision else {})})

    table_index = 0
    for block in blocks:
        if block.tag == _W + "tbl":
            # Tables are TABLE-sourced segments (34.11), one row per line (F2a). No
            # section number: a table states none, and numbering is never inherited.
            first = block.xpath(".//w:p[not(ancestor::w:txbxContent)]")
            page = page_of.get(first[0]) if first else None
            rows = _docx_rows(block)
            table_index += 1
            emit("\n".join(table_row(list(row)) for row in rows),
                 EvidenceSourceType.TABLE, page,
                 metadata={"table_index": table_index, "rows": len(rows)})
        else:
            page = page_of.get(block)
            paragraph(block, page, following[block])
            # Word writes a DrawingML text box twice — the VML copy in mc:Fallback.
            # ponytail: a text box anchored in a table cell, and a table inside a text
            # box, are not read — add them to _docx_cell / here if a real file has one.
            for box in block.xpath(f".//w:r[{_VISIBLE_RUN}]//w:txbxContent[not("
                                   "ancestor::*[local-name()='Fallback'])]/w:p"):
                paragraph(box, page, None)
        for ref in block.xpath(f".//w:r[{_VISIBLE_RUN}]/w:footnoteReference | "
                               f".//w:r[{_VISIBLE_RUN}]/w:endnoteReference"):
            key = ("footnote" if ref.tag == _W + "footnoteReference" else "endnote",
                   ref.get(_W + "id"))
            if key in notes:
                emit(notes.pop(key), EvidenceSourceType.NATIVE_TEXT, page,
                     metadata={"part": key[0], "note_id": key[1]})
    # A note no visible reference points at — its reference deleted, hidden or moved
    # away — is not text the document shows, so it is not read (review 2026-10-16).
    # ponytail: a note referenced only from a header or footer is not read either.
    for part, text in aux("headers and footers", lambda: _docx_furniture(document), []):
        emit(text, EvidenceSourceType.OTHER, None, metadata={"part": part})

    status = (ExtractionStatus.COMPLETE if segments else ExtractionStatus.FAILED)
    diagnostics = [] if segments else ["DOCX contained no extractable text"]
    if segments and pagination_source:
        diagnostics = [*diagnostics,
                       "pages from the document's own pagination record "
                       f"({pagination_source})"]
    diagnostics += unread
    comments = aux("comments", lambda: _docx_part_xml(document, RT.COMMENTS), None)
    if comments is not None and (count := len(comments.findall(_W + "comment"))):
        diagnostics.append(
            f"{count} comment(s) not read (reviewer notes, not document text)")
    embedded = len(body.xpath(".//w:object | .//w:altChunk"))
    if embedded:
        diagnostics.append(f"{embedded} embedded object(s) not read")
    # A part this read knows it did not read — a damaged footnote/header part, an
    # imported (altChunk) or embedded document — may hold the clause asked about, so the
    # reading is PARTIAL, never COMPLETE (rule 15, 34.10; review 2026-10-16), as a PDF
    # page with an unread image region is.
    if segments and (unread or embedded):
        status = ExtractionStatus.PARTIAL
    pages_extracted = (total_pages if pagination_source else 1) if segments else 0
    return ParseResult(segments=segments, status=status,
                       pages_total=total_pages if pagination_source else 0,
                       pages_extracted=pages_extracted,
                       diagnostics=diagnostics,
                       pagination_source=pagination_source if segments else None)


_MARKDOWN_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.MULTILINE)
_MARKDOWN_RULE = re.compile(r"^[ \t]{0,3}(?:[-*_][ \t]*){3,}$", re.MULTILINE)


def parse_text(data: bytes) -> ParseResult:
    """Plain text and Markdown, through the same segmenter as everything else.

    `segment_paragraphs` was already source-agnostic — it takes text, a page and a
    source type — so this adds a reader, not a second parser. There is no page model:
    a .md file states no pagination, so `page_number` is None and `pages_total` is 0,
    exactly as `parse_docx` already reports for a DOCX whose own record is absent.
    Status is decided the same way it is there: text or no text.

    Markdown's heading marks are removed before segmentation. They are presentation,
    and left in place `## 5. Liability` is not a clause number to `detect_clause_number`
    — the numbering the document itself states is what locked 34.12 preserves, and a
    `#` is not part of it. Nothing else about the text is altered: no list
    renumbering, no emphasis stripping, no link rewriting.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError("text could not be decoded as UTF-8") from exc
    text = _MARKDOWN_RULE.sub("", _MARKDOWN_HEADING.sub("", text))
    segments = segment_paragraphs(text, page_number=None,
                                  source_type=EvidenceSourceType.NATIVE_TEXT,
                                  base_offset=0)
    status = ExtractionStatus.COMPLETE if segments else ExtractionStatus.FAILED
    return ParseResult(
        segments=segments, status=status, pages_total=0,
        pages_extracted=1 if segments else 0,
        diagnostics=[] if segments else ["file contained no extractable text"])


def parse(data: bytes, mime_type: str, *, defer_ocr: bool = False,
          ocr: bool = True, docling: bool | None = None) -> ParseResult:
    if mime_type == PDF_MIME:
        return parse_pdf(data, defer_ocr=defer_ocr, ocr=ocr, docling=docling)
    if mime_type == DOCX_MIME:
        return parse_docx(data)  # a DOCX is text-native; OCR never applies
    if mime_type in TEXT_MIME_TYPES:
        return parse_text(data)  # no pages, no OCR, no embedded objects
    raise ParseError(f"unsupported mime type: {mime_type}")


def _status_for(pages_total: int, pages_extracted: int) -> ExtractionStatus:
    """Locked 34.10 — partial extraction is explicitly represented."""
    if pages_total == 0 or pages_extracted == 0:
        return ExtractionStatus.FAILED
    if pages_extracted < pages_total:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.COMPLETE
