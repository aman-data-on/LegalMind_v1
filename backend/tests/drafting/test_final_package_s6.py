"""S6 (`FINAL-PACKAGE-SPEC` c4): the final copy's footer names its own version, and the
Final card's note (`GET /document-versions/{id}/signing-note`) carries only what the app
holds. The template is the S4 TEST-ONLY placeholder — no Legal text."""

from __future__ import annotations

import hashlib
import io
import os
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest

from legalmind.api.routers import negotiation as N
from legalmind.db import models as M
from legalmind.drafting import library
from legalmind.drafting import render_contract as R
from tests.conftest import sign_in
from tests.drafting.conftest import build
from tests.drafting.test_final_package_s4 import _with_annexure_1
from tests.drafting.test_special_conditions import _imported, lawyer  # noqa: F401

V1 = "/api/v1"


def _part(docx: bytes, name: str) -> bytes:
    return zipfile.ZipFile(io.BytesIO(docx)).read(name)


def test_restamp_changes_the_footer_version_only(placeholder, answers):
    _, digest, docx = build(*placeholder, answers)
    made = R.restamp(docx, 3)
    footers = [n for n in zipfile.ZipFile(io.BytesIO(docx)).namelist()
               if n.startswith("word/footer")]
    assert footers
    old, new = f"LM-TEST-v1-{digest[:8]}".encode(), f"LM-TEST-v3-{digest[:8]}".encode()
    assert any(old in _part(docx, f) for f in footers)
    for f in footers:
        assert old not in _part(made, f)
    assert any(new in _part(made, f) for f in footers)
    assert _part(made, "word/document.xml") == _part(docx, "word/document.xml")


@pytest.mark.skipif(not os.environ.get("LEGALMIND_SOFFICE"),
                    reason="LEGALMIND_SOFFICE is not set: no LibreOffice here")
def test_signing_note_of_a_final_copy(db, api, user, seeded, placeholder, lawyer,
                                      monkeypatch):
    t, c = _with_annexure_1(placeholder)
    tv = _imported(db, user, (t, c))
    tv.layout = {**tv.layout, "execution": {**tv.layout["execution"], "last": True}}
    library._rehash(db, tv)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id,
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve")
    tid = api.post(f"{V1}/templates/{tv.id}/publish").json()["data"]["id"]
    values = dict(t["layout"]["check_values"])
    draft = api.post(f"{V1}/drafts", json={"template_version_id": tid,
                                           "answers": values}).json()["data"]
    made = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
    assert made.status_code == 201, made.text
    contract_id = made.json()["data"]["contract_id"]
    v1 = made.json()["data"]["document_version_id"]
    # v1's own review is not this test's: its gates are passed by hand
    monkeypatch.setattr(N.negotiation, "review_open_points", lambda db, v: None)
    monkeypatch.setattr(N, "_require_decided", lambda guard, v: None)
    final = api.post(f"{V1}/contracts/{contract_id}/final-copy")
    assert final.status_code == 201, final.text
    v2 = db.get(M.DocumentVersion,
                uuid.UUID(final.json()["data"]["document_version"]["id"]))
    rec = v2.doc_metadata["pdf"]
    assert rec["status"] == "READY", rec
    note = api.get(f"{V1}/document-versions/{v2.id}/signing-note")
    assert note.status_code == 200, note.text
    n = note.json()["data"]
    assert n["doc_id"] is not None and f"-v{v2.version_number}-" in n["doc_id"]
    assert n["pdf_sha256"] == rec["pdf_sha256"]
    assert n["pages"] >= 1 and n["signature_page"] == n["pages"]   # signatures last
    assert n["pdf_name"].endswith("(final).pdf") and n["word_name"].endswith(".docx")
    assert n["signers"] and all(s["email"] for s in n["signers"])
    assert hashlib.sha256(api.get(f"{V1}/document-versions/{v2.id}/pdf").content
                          ).hexdigest() == n["pdf_sha256"]
    # v1 is not a final contract: nothing to say (byte-identical 404)
    assert api.get(f"{V1}/document-versions/{v1}/signing-note").status_code == 404
