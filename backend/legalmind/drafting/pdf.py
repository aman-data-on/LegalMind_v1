"""The client-facing PDF — LibreOffice headless, run by the WORKER (`AM-277`).

LibreOffice prints tracked changes and comments as markup, so it only ever converts the
CLEAN copy: `convert` runs `clean.clean` first, whatever it is handed. The binary is the
operator's (``LEGALMIND_SOFFICE``), run with an argv list (no shell), a throwaway user
profile and a timeout; its version string is returned so it is recorded with each
output (`contract_drafts.libreoffice_version`).

Entry point for the worker: `render_version` (`AM-293` r2), dispatched by
`worker.dispatch.dispatch_pdf` after a reply or a created contract version is ingested.
It records ``{status, kind, libreoffice_version, pdf_sha256, storage_key, rendered_at}``
(or ``error``) under ``pdf`` in the version's 42.4 ``metadata`` JSONB — not on
``contract_drafts``, which is append-only, and no new column. There is no PyMuPDF
fallback for a client copy (`AM-293` r3): no LibreOffice is a recorded failure.

Fonts: the house font (``config/templates/house/house.json``) must be installed on the
worker host, or LibreOffice substitutes one and the pagination moves.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from legalmind.drafting import clean

#: ponytail: one minute per conversion; a pool of warm LibreOffice processes if the
#: worker ever converts in volume
TIMEOUT_S = 60


class PdfError(RuntimeError):
    pass


@dataclass(frozen=True)
class PdfResult:
    pdf: bytes
    libreoffice_version: str


def soffice() -> str:
    path = os.environ.get("LEGALMIND_SOFFICE")
    if not path:
        raise PdfError("LEGALMIND_SOFFICE is not set: no PDF renderer on this host")
    return path


@lru_cache(maxsize=4)
def version(binary: str) -> str:
    """``LibreOffice 26.2.6.3 <build>`` — as the binary reports itself."""
    with tempfile.TemporaryDirectory() as tmp:
        done = subprocess.run(  # noqa: S603 — argv list, the operator's binary
            [binary, f"-env:UserInstallation=file://{tmp}/profile", "--version"],
            check=True, timeout=TIMEOUT_S, capture_output=True, text=True)
    return done.stdout.strip()


def convert(docx_bytes: bytes, *, timeout: int = TIMEOUT_S) -> PdfResult:
    """The PDF of the CLEAN copy of ``docx_bytes``, or `PdfError`."""
    binary = soffice()
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp, "contract.docx")
        source.write_bytes(clean.clean(docx_bytes))
        try:
            subprocess.run(  # noqa: S603 — argv list, the operator's binary
                [binary, f"-env:UserInstallation=file://{tmp}/profile", "--headless",
                 "--norestore", "--convert-to", "pdf", "--outdir", tmp, str(source)],
                check=True, timeout=timeout, capture_output=True)
            pdf = Path(tmp, "contract.pdf").read_bytes()
        except (OSError, subprocess.SubprocessError) as exc:
            raise PdfError("LibreOffice could not convert the file "
                           f"({type(exc).__name__})") from exc
    return PdfResult(pdf, version(binary))


def convert_contract(docx_bytes: bytes) -> tuple[bytes, PdfResult]:
    """A generated contract's clean DOCX and the PDF of exactly that file."""
    fixed = clean.clean(docx_bytes)
    return fixed, convert(fixed)


# --------------------------------------------------------------------------
# The worker job (`AM-293` r2) — the record on the version, and the render itself
# --------------------------------------------------------------------------
RENDERING, READY, FAILED = "RENDERING", "READY", "FAILED"
#: a render still RENDERING (a lost message) or FAILED this long ago is dispatched
#: again by the next download — well past `TIMEOUT_S` × the two contract conversions
STALE_S = 10 * TIMEOUT_S


def record(version: Any) -> dict | None:
    """The version's PDF record, or None (never dispatched)."""
    return (version.doc_metadata or {}).get("pdf")


def stale(rec: dict | None) -> bool:
    """Nothing recorded, or a RENDERING/FAILED record older than `STALE_S`."""
    if rec is None:
        return True
    if rec["status"] == READY:
        return False
    at = datetime.fromisoformat(rec.get("rendered_at") or rec["queued_at"])
    return (datetime.now(UTC) - at).total_seconds() > STALE_S


def _now() -> str:
    return datetime.now(UTC).isoformat()


def mark(version: Any, kind: str, status: str, **fields: Any) -> dict:
    """Write the record (a new dict: the JSONB column is not a MutableDict)."""
    rec = {"status": status, "kind": kind, "queued_at": _now(), **fields}
    version.doc_metadata = {**(version.doc_metadata or {}), "pdf": rec}
    return rec


def render_version(db: Any, storage: Any, document_version_id: UUID,
                   kind: str) -> dict | None:
    """Make the client PDF of one stored version, store it and record it; the caller
    commits. A contract (`kind="contract"`) gets its page totals filled and the PDF
    checks of the preflight (a problem fails closed, nothing stored); a reply is its
    CLEAN copy as converted. `PdfError` is a recorded FAILED, never a fallback."""
    from legalmind.db import models as M
    from legalmind.db.session import on_rollback
    from legalmind.drafting import preflight

    version = db.get(M.DocumentVersion, document_version_id)
    if version is None:
        return None
    if (record(version) or {}).get("status") == READY:
        return record(version)
    failed = None
    try:
        source = storage.get(version.storage_key)
        if kind == "contract":
            fixed, result = convert_contract(source)
            problems = preflight.pdf_problems(fixed, result.pdf)
            if problems:
                raise PdfError("the PDF did not pass its check: "
                               + "; ".join(p.detail for p in problems))
        else:
            result = convert(source)
    except PdfError as exc:
        failed = str(exc)
    db.refresh(version, with_for_update=True)  # the lock only around the write
    if (record(version) or {}).get("status") == READY:
        return record(version)                 # another render finished first
    if failed is not None:
        return mark(version, kind, FAILED, error=failed, rendered_at=_now())
    key = storage.put(result.pdf, suggested_name=f"{kind}.pdf")
    on_rollback(db, lambda: storage.discard(key))    # no record, no orphan file
    return mark(version, kind, READY, storage_key=key,
                libreoffice_version=result.libreoffice_version,
                pdf_sha256=hashlib.sha256(result.pdf).hexdigest(), rendered_at=_now())


# --------------------------------------------------------------------------
# The blank template's PDF (`AM-302`) — a PUBLISHED template version is frozen by its
# trigger, so the record is an audit event per state (`template.blank_pdf`), keyed by
# the blank model's hash: a later render of other text is a different record.
# --------------------------------------------------------------------------
def blank_record(db: Any, template_version_id: UUID, model_hash: str,
                 kind: str = "blank") -> dict | None:
    """The latest ``template.blank_pdf`` state for this blank, or None."""
    from sqlalchemy import select

    from legalmind.db import models as M
    from legalmind.security import audit as A

    said = [s for s in db.execute(select(M.AuditEvent.after_state).where(
        M.AuditEvent.action == A.TEMPLATE_BLANK_PDF,
        M.AuditEvent.entity_id == template_version_id)).scalars()
        if (s or {}).get("model_hash") == model_hash and s.get("kind") == kind]
    # by its own clock: two states in one transaction share the row's timestamp
    return max(said, key=lambda s: s["queued_at"], default=None)


def mark_blank(db: Any, template_version_id: UUID, model_hash: str, kind: str,
               status: str, **fields: Any) -> dict:
    from legalmind.security import audit as A

    rec = {"status": status, "kind": kind, "model_hash": model_hash,
           "queued_at": _now(), **fields}
    A.record(db, action=A.TEMPLATE_BLANK_PDF, entity_type="template_version",
             entity_id=template_version_id, after=rec)
    return rec


def render_blank(db: Any, storage: Any, template_version_id: UUID,
                 kind: str = "blank") -> dict | None:
    """Make, store and record the blank template's (or its review copy's) PDF; the
    caller commits."""
    from legalmind.db import models as M
    from legalmind.drafting import blank

    tv = db.get(M.TemplateVersion, template_version_id)
    if tv is None:
        return None
    docx, model = blank.render(db, tv, kind)
    digest = blank.model_.model_hash(model)
    done = blank_record(db, tv.id, digest, kind)
    if (done or {}).get("status") == READY:
        return done
    try:
        result = convert(docx)
    except PdfError as exc:
        return mark_blank(db, tv.id, digest, kind, FAILED, error=str(exc),
                          rendered_at=_now())
    key = storage.put(result.pdf, suggested_name=f"{kind}.pdf")
    return mark_blank(db, tv.id, digest, kind, READY, storage_key=key,
                      libreoffice_version=result.libreoffice_version,
                      pdf_sha256=hashlib.sha256(result.pdf).hexdigest(),
                      rendered_at=_now())
