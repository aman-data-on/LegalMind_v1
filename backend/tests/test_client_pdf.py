"""The client-facing PDF is made by LibreOffice in the worker only (`AM-293` r2/r3).

Recorded on the version (`metadata.pdf`): 202 while rendering, 200 once stored, a
plain 503 when LibreOffice is missing — never a PyMuPDF copy. Synthetic documents."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta

import pytest

from legalmind.api.storage import get_storage
from legalmind.db import models as M
from legalmind.drafting import pdf
from legalmind.worker import dispatch as D
from tests.test_negotiation import _changes, owner  # noqa: F401 — fixture
from tests.test_negotiation_reply import (  # noqa: F401 — `published` is autouse
    REPLY,
    SOFFICE,
    _answer,
    _negotiated,
    published,
)
from tests.test_version_comparison import V1
from tests.test_worker import JoinedSession

needs_lo = pytest.mark.skipif(not os.path.exists(SOFFICE), reason="no LibreOffice here")


def _reply(api, db, owner, tmp_path):
    c, _, _ = _negotiated(api, db, owner, tmp_path)
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "accept_theirs" if change["route"] == "owner"
                else "keep_ours")
    body = api.post(REPLY.format(c.id)).json()["data"]
    return db.get(M.DocumentVersion, body["document_version"]["id"]), \
        f"{V1}/document-versions/{body['document_version']['id']}/pdf"


def test_no_libreoffice_is_a_recorded_failure_never_a_reading_copy(
        api, db, owner, tmp_path, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    version, url = _reply(api, db, owner, tmp_path)      # inline: no broker here
    rec = pdf.record(version)
    assert rec["status"] == "FAILED" and "LEGALMIND_SOFFICE" in rec["error"]
    assert "storage_key" not in rec
    got = api.get(url)
    assert got.status_code == 503 and not got.content.startswith(b"%PDF")
    assert got.json()["error"]["code"] == "PDF_NOT_MADE"
    assert "LEGALMIND_SOFFICE" in got.json()["error"]["message"]


def test_queued_dispatch_records_rendering_and_sends_after_commit(
        api, db, owner, tmp_path, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    version, url = _reply(api, db, owner, tmp_path)
    monkeypatch.setattr(D, "configure_broker", lambda: "memory://")
    sent = []
    monkeypatch.setattr(D, "_off_loop", sent.append)
    assert D.dispatch_pdf(db, version, "reply") == "queued"
    assert pdf.record(version)["status"] == "RENDERING" and sent == []  # not before commit
    monkeypatch.undo()
    got = api.get(url)
    assert got.status_code == 202 and got.json() == {"data": {"status": "rendering"}}


@needs_lo
def test_the_worker_job_renders_and_records_then_the_download_serves_it(
        api, db, owner, tmp_path, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    version, url = _reply(api, db, owner, tmp_path)
    pdf.mark(version, "reply", pdf.RENDERING)
    db.flush()
    assert api.get(url).status_code == 202
    monkeypatch.setenv("LEGALMIND_SOFFICE", SOFFICE)
    monkeypatch.setattr("legalmind.worker.tasks._session", lambda: JoinedSession(db))
    from legalmind.worker.tasks import render_pdf
    assert render_pdf.apply(kwargs={"document_version_id": str(version.id),
                                    "kind": "reply"}).get()["status"] == "READY"
    db.refresh(version)
    rec = pdf.record(version)
    assert rec["libreoffice_version"].startswith("LibreOffice ") and rec["rendered_at"]
    got = api.get(url)
    assert got.status_code == 200 and got.content.startswith(b"%PDF")
    assert hashlib.sha256(got.content).hexdigest() == rec["pdf_sha256"]
    assert get_storage().get(rec["storage_key"]) == got.content


@needs_lo
def test_a_stale_failure_is_dispatched_again_by_the_next_download(
        api, db, owner, tmp_path, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    version, url = _reply(api, db, owner, tmp_path)
    monkeypatch.setenv("LEGALMIND_SOFFICE", SOFFICE)
    assert api.get(url).status_code == 503             # a fresh failure stands
    old = (datetime.now(UTC) - timedelta(seconds=pdf.STALE_S + 1)).isoformat()
    version.doc_metadata = {**version.doc_metadata,
                            "pdf": {**pdf.record(version), "rendered_at": old}}
    db.flush()
    assert api.get(url).status_code == 200             # inline again, now with LO


def test_a_render_finished_meanwhile_is_kept_and_a_rolled_back_one_leaves_no_file(
        api, db, owner, tmp_path, monkeypatch):
    """L4: the READY check is repeated under the row lock — a render that finished
    while this one converted stands, and nothing more is stored; and the file of a
    render whose transaction rolls back is discarded with it."""
    version, _ = _reply(api, db, owner, tmp_path)
    storage = get_storage()
    pdf.mark(version, "reply", pdf.RENDERING)
    db.flush()
    made = pdf.PdfResult(b"%PDF-1.7 synthetic", "LibreOffice test")

    def finished_elsewhere(_docx):
        pdf.mark(version, "reply", pdf.READY, storage_key="theirs")
        db.flush()
        return made
    monkeypatch.setattr(pdf, "convert", finished_elsewhere)
    put = []
    monkeypatch.setattr(storage, "put", lambda data, **_: put.append(data) or "mine")
    assert pdf.render_version(db, storage, version.id, "reply")["storage_key"] == "theirs"
    assert put == []

    monkeypatch.undo()
    monkeypatch.setattr(pdf, "convert", lambda _docx: made)
    pdf.mark(version, "reply", pdf.RENDERING)
    db.flush()
    with pytest.raises(ValueError), db.begin_nested():
        key = pdf.render_version(db, storage, version.id, "reply")["storage_key"]
        assert storage.get(key) == made.pdf
        raise ValueError("the job failed after storing")
    assert not storage.exists(key)
