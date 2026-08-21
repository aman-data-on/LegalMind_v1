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


def segment_paragraphs(text: str, *, page_number: int | None,
                       source_type: EvidenceSourceType,
                       base_offset: int = 0) -> list[Segment]:
    """Split into paragraph segments, carrying source locations (34.13)."""
    segments: list[Segment] = []
    cursor = 0
    for block in re.split(r"\n\s*\n", text):
        raw = block
        start = text.find(raw, cursor)
        if start < 0:                          # pragma: no cover - defensive
            start = cursor
        cursor = start + len(raw)
        normalized = normalize_text(raw)
        if not normalized:
            continue
        first_line = normalized.split("\n", 1)[0]
        number, title = detect_clause_number(first_line)
        segments.append(Segment(
            content=normalized,
            original_content=raw,
            source_type=source_type,
            page_number=page_number,
            section_number=number,
            section_title=title,
            start_offset=base_offset + start,
            end_offset=base_offset + cursor,
        ))
    return segments


# --------------------------------------------------------------------------
# OCR availability — locked 34.7, 34.9
# --------------------------------------------------------------------------
def ocr_available() -> bool:
    """Whether the locked OCR toolchain (OCRmyPDF + Tesseract) is present."""
    return shutil.which("ocrmypdf") is not None and shutil.which("tesseract") is not None


# --------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------
def parse_pdf(data: bytes) -> ParseResult:
    """Native PDF text extraction, with OCR only where a page has none.

    Locked 34.7: OCR is used when a supported PDF does not contain usable text.
    Locked 34.9: if a page has no native text and OCR is unavailable or fails,
    that page is reported as failed — its text is never guessed.
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
    doc.close()

    status = _status_for(pages_total, extracted_pages)
    return ParseResult(segments=segments, status=status, pages_total=pages_total,
                       pages_extracted=extracted_pages, pages_failed=failed_pages,
                       diagnostics=diagnostics)


def _ocr_page(page) -> str:                     # pragma: no cover - needs toolchain
    """OCR a single page via the locked toolchain.

    Only reached when the toolchain is present; absence is handled by the caller
    as a failure, never as empty text.
    """
    import subprocess
    import tempfile

    pix = page.get_pixmap(dpi=300)
    with tempfile.TemporaryDirectory() as tmp:
        image_path = f"{tmp}/page.png"
        pix.save(image_path)
        proc = subprocess.run(
            ["tesseract", image_path, "stdout"],
            capture_output=True, text=True, timeout=120, check=False)
        if proc.returncode != 0:
            raise ParseError(f"tesseract exited {proc.returncode}")
        return proc.stdout


def parse_docx(data: bytes) -> ParseResult:
    """DOCX extraction preserving paragraphs and tables (34.11)."""
    import io

    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError(f"DOCX could not be opened: {type(exc).__name__}") from exc

    segments: list[Segment] = []
    offset = 0

    for para in document.paragraphs:
        raw = para.text or ""
        normalized = normalize_text(raw)
        if not normalized:
            offset += len(raw)
            continue
        number, title = detect_clause_number(normalized.split("\n", 1)[0])
        segments.append(Segment(
            content=normalized, original_content=raw,
            source_type=EvidenceSourceType.NATIVE_TEXT,
            page_number=None,                   # DOCX has no reliable page model
            section_number=number, section_title=title,
            start_offset=offset, end_offset=offset + len(raw),
            metadata={"style": para.style.name if para.style else None},
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
    return ParseResult(segments=segments, status=status, pages_total=0,
                       pages_extracted=1 if segments else 0,
                       diagnostics=diagnostics)


def parse(data: bytes, mime_type: str) -> ParseResult:
    if mime_type == PDF_MIME:
        return parse_pdf(data)
    if mime_type == DOCX_MIME:
        return parse_docx(data)
    raise ParseError(f"unsupported mime type: {mime_type}")


def _status_for(pages_total: int, pages_extracted: int) -> ExtractionStatus:
    """Locked 34.10 — partial extraction is explicitly represented."""
    if pages_total == 0 or pages_extracted == 0:
        return ExtractionStatus.FAILED
    if pages_extracted < pages_total:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.COMPLETE
