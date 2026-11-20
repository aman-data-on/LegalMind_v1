"""Batch 3+4 (AB-218), check 2: what Legal told the client never reaches the
final contract — its body, Annexure 2 or its PDF. The structural placeholder template and
synthetic text only; the recorded words are TEST text, never a position (rule 21)."""

from __future__ import annotations

import io
import uuid
import zipfile

from legalmind.db import models as M
from tests.drafting.test_final_package_s3 import (  # noqa: F401 — fixtures
    lawyer,
    negotiated,
    sc_template,
)

V1 = "/api/v1"
TOLD = "Test note: we told the client a mutual cap qq7z"


def test_what_we_told_them_never_reaches_the_final_contract(db, api, negotiated):
    contract, v1, v2, storage = negotiated
    rows = api.get(f"{V1}/contracts/{contract.id}/changes").json()["data"]["changes"]
    tie = {c["row_key"]: "AS_TOLD" for c in rows if c["route"] == "holder"}
    # the deal is the lawyer's own (never sent to Legal: round 3 D4 refuses a write), so
    # the record is placed directly — this test is about where the words never go
    lawyer_id = contract.owner_id
    db.add(M.DealPosition(contract_id=contract.id, position_key="t", version_number=1,
                          text=TOLD, ties=tie, recorded_by=lawyer_id))
    db.flush()
    assert api.post(f"{V1}/contracts/{contract.id}/positions",
                    json={"text": TOLD}).status_code == 403          # D4, by the way
    url = f"{V1}/contracts/{contract.id}/package"
    dry = api.get(url).json()["data"]
    assert dry["available"] is True, dry["blockers"]
    assert "qq7z" not in str(dry)
    done = api.post(url, json={"expected_entries_sha256": dry["entries_sha256"]})
    assert done.status_code == 201, done.text
    v3 = db.get(M.DocumentVersion,
                uuid.UUID(done.json()["data"]["document_version"]["id"]))
    with zipfile.ZipFile(io.BytesIO(storage.get(v3.storage_key))) as z:
        every_part = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())
    assert "Annexure 2" in every_part                    # the control: the annexure is read
    assert "qq7z" not in every_part
