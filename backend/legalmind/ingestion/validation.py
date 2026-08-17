"""Upload validation — locked Step 34.2, 34.14; Step 39 security checklist.

Locked 34.16: uploaded files are treated as **untrusted input** and processed
safely. Validation happens before any parser touches the bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

# Locked 34.2 — V1 primarily supports PDF and DOCX.
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SUPPORTED_MIME_TYPES = frozenset({PDF_MIME, DOCX_MIME})

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024        # deployment-tunable (Step 55)

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
                             "Only PDF and DOCX documents are supported.")

    actual = sniff_mime(data)
    if actual is None:
        raise UploadRejected("UNRECOGNISED_CONTENT",
                             "File content does not match a supported format.")
    if actual != declared_mime:
        raise UploadRejected("CONTENT_TYPE_MISMATCH",
                             "File content does not match its declared type.")

    return ValidatedUpload(data=data, filename=filename, mime_type=actual,
                           size_bytes=len(data))


def sniff_mime(data: bytes) -> str | None:
    """Determine format from content, never from filename or client claim."""
    if data.startswith(_PDF_MAGIC):
        return PDF_MIME
    if data.startswith(_ZIP_MAGIC):
        # A DOCX is a ZIP containing word/document.xml. Checked without
        # extracting to disk (34.16).
        import io
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names:
            return DOCX_MIME
        return None
    return None
