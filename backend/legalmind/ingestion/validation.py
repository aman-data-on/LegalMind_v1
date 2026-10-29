"""Upload validation — locked Step 34.2, 34.14; Step 39 security checklist.

Locked 34.16: uploaded files are treated as **untrusted input** and processed
safely. Validation happens before any parser touches the bytes.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

# Locked 34.2 — V1 primarily supports PDF and DOCX.
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT_MIME = "text/plain"
MARKDOWN_MIME = "text/markdown"
# Text formats carry no magic bytes, so they are verified differently — see
# `looks_like_text`. They are kept in their own set because that difference is real
# and a reader of this module should not have to infer it.
TEXT_MIME_TYPES = frozenset({TEXT_MIME, MARKDOWN_MIME})
SUPPORTED_MIME_TYPES = frozenset({PDF_MIME, DOCX_MIME}) | TEXT_MIME_TYPES

# A text upload must decode and must read as text. Neither is a formality: a PDF
# renamed .txt fails the first (NUL bytes), and a binary blob that happens to decode
# fails the second.
_PRINTABLE_SHARE = 0.95

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024        # deployment-tunable (Step 55)

#: QA-008/009 (2026-10-29): a DOCX is a ZIP, so its size on upload says nothing about
#: what the parser holds — 444 KB unpacked to 400 MB, and 191 KB to a million
#: paragraphs that held a request for minutes. The largest real upload unpacks to
#: 1.9 MB (0.66 MB of XML, 472 paragraphs); each bound is about 40x that. Sizes are
#: the ZIP's own records, which `zipfile` enforces on read, so nothing is decompressed
#: to check them; only a document.xml already within the XML bound is read to count.
MAX_DOCX_UNPACKED_BYTES = 2 * MAX_FILE_SIZE_BYTES
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
MAX_DOCX_PARAGRAPHS = 20_000
_PARAGRAPH = re.compile(rb"<(?:\w+:)?p[\s/>]")

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"                     # DOCX is a ZIP container


class UploadRejected(Exception):
    """Validation failure. Rejected before storage and before parsing."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidatedUpload:
    data: bytes
    filename: str
    mime_type: str
    size_bytes: int


def validate_upload(data: bytes, filename: str, declared_mime: str) -> ValidatedUpload:
    """Validate an upload without trusting anything the client said.

    The declared MIME type is checked against the file's actual magic bytes: a
    client claiming PDF while supplying something else is rejected rather than
    handed to a parser (34.16).
    """
    if not data:
        raise UploadRejected("EMPTY_FILE", "File is empty.")
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise UploadRejected("FILE_TOO_LARGE", "File exceeds the maximum size.")
    if declared_mime not in SUPPORTED_MIME_TYPES:
        raise UploadRejected("UNSUPPORTED_TYPE",
                             "Only PDF, DOCX, plain text and Markdown documents "
                             "are supported.")

    if declared_mime in TEXT_MIME_TYPES:
        # Magic bytes cannot answer this: text has none, and inventing a signature
        # for it would mean `sniff_mime` returning a type for arbitrary bytes — which
        # `deploy/preflight.py` asserts it must never do. So the claim "this is text"
        # is checked as what it is, and a file that IS a known binary format is
        # refused whatever it was declared as.
        if sniff_mime(data) is not None:
            raise UploadRejected("CONTENT_TYPE_MISMATCH",
                                 "File content does not match its declared type.")
        if not looks_like_text(data):
            raise UploadRejected("UNRECOGNISED_CONTENT",
                                 "File content does not match a supported format.")
        return ValidatedUpload(data=data, filename=filename, mime_type=declared_mime,
                               size_bytes=len(data))

    actual = sniff_mime(data)
    if actual is None:
        raise UploadRejected("UNRECOGNISED_CONTENT",
                             "File content does not match a supported format.")
    if actual != declared_mime:
        raise UploadRejected("CONTENT_TYPE_MISMATCH",
                             "File content does not match its declared type.")
    if actual == DOCX_MIME:
        _check_docx_bounds(data)

    return ValidatedUpload(data=data, filename=filename, mime_type=actual,
                           size_bytes=len(data))


def _check_docx_bounds(data: bytes) -> None:
    """Refuse a DOCX that unpacks far beyond any real contract, before parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            members = z.infolist()
            xml = sum(m.file_size for m in members
                      if m.filename.endswith((".xml", ".rels")))
            too_large = (xml > MAX_DOCX_XML_BYTES
                         or sum(m.file_size for m in members) > MAX_DOCX_UNPACKED_BYTES)
            body = b"" if too_large else z.read("word/document.xml")
    except (zipfile.BadZipFile, ValueError, OSError):   # a size record that lies
        raise UploadRejected("UNRECOGNISED_CONTENT",
                             "File content does not match a supported format.") from None
    if too_large or len(_PARAGRAPH.findall(body)) > MAX_DOCX_PARAGRAPHS:
        raise UploadRejected("DOCUMENT_TOO_LARGE",
                             "This Word file is far larger than a contract once opened, "
                             "so it was not read.")


def sniff_mime(data: bytes) -> str | None:
    """Determine format from content, never from filename or client claim."""
    if data.startswith(_PDF_MAGIC):
        return PDF_MIME
    if data.startswith(_ZIP_MAGIC):
        # A DOCX is a ZIP containing word/document.xml. Checked without
        # extracting to disk (34.16).
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names:
            return DOCX_MIME
        return None
    return None


def looks_like_text(data: bytes) -> bool:
    """Is this actually text? Decodable as UTF-8, and predominantly printable.

    Deliberately NOT part of `sniff_mime`: that function answers "which format is
    this" from a signature, and text has none. A sniffer that returned a type for any
    decodable bytes would accept arbitrary input, which is the posture locked 34.16
    rules out and `deploy/preflight.py` asserts against.
    """
    if b"\x00" in data:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if not text.strip():
        return False
    printable = sum(ch.isprintable() or ch.isspace() for ch in text)
    return printable / len(text) >= _PRINTABLE_SHARE
