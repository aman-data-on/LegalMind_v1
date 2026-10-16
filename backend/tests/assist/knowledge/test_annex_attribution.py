"""`store.annexes` reads the annexure label on a chunk's FIRST line (critic P2,
2026-10-15). A label row that carries its annexure's opening text in the same chunk
("Annexure-3A\\nService Offered…") was not recognised, so 3A's and 3B's chunks —
payment terms included — were cited as inside Annexure-2. Synthetic text only."""

from __future__ import annotations

from sqlalchemy import text

from legalmind import config
from legalmind.assist.ingestion.indexing import index_document_version
from legalmind.assist.knowledge import store
from legalmind.db import models as M
from legalmind.domain import enums as E

ROWS = [
    "1. The Provider shall supply the Services described in the annexures below.",
    "Annexure-2",
    "Dedicated hosting in the Provider's primary facility, monitored at all hours.",
    "Annexure-3A\nService Offered: managed backup of the Customer's servers, daily.",
    "1. Backups are retained for thirty days and restored on written request only.",
    "Appendix-3B\nPAYMENT TERMS\nThe Customer shall pay all fees quarterly in advance.",
    "1. Invoices are payable within thirty days of the date of the invoice issued.",
    "Clause 3B of this agreement explains how the fees are calculated and invoiced.",
]


def test_a_label_with_content_on_its_first_line_opens_its_annexure(db, user):
    contract = M.Contract(owner_id=user.id, name="Annex MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    version = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="a.pdf",
        mime_type="application/pdf", file_size_bytes=1, file_hash="h", storage_key="k",
        processing_status=E.ProcessingStatus.COMPLETED,
        extraction_status=E.ExtractionStatus.COMPLETE, uploaded_by=user.id)
    db.add(version)
    db.flush()
    run = M.DocumentProcessingRun(
        document_version_id=version.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED, processor_version="t")
    db.add(run)
    db.flush()
    offset = 0
    for content in ROWS:
        db.add(M.DocumentEvidence(
            document_version_id=version.id, processing_run_id=run.id, page_number=1,
            content=content, source_type=E.EvidenceSourceType.NATIVE_TEXT,
            start_offset=offset, end_offset=offset + len(content)))
        offset += len(content) + 1
    db.flush()
    index_document_version(db, version.id, reindex=True)

    chunks = db.execute(text(
        f'SELECT id, content FROM "{config.assist_schema()}".chunks '
        "WHERE document_version_id = :v ORDER BY ordinal"), {"v": version.id}).all()
    label = store.annexes(db, [c[0] for c in chunks])
    by_text = {c[1].split("\n")[0][:20]: label.get(c[0]) for c in chunks}
    assert by_text["1. The Provider shal"] is None
    assert by_text["Dedicated hosting in"] == "Annexure-2"
    assert by_text["Annexure-3A"] == "Annexure-3A"
    assert by_text["1. Backups are retai"] == "Annexure-3A"
    assert by_text["Appendix-3B"] == "Appendix-3B"
    assert by_text["1. Invoices are paya"] == "Appendix-3B"
    # A clause that merely names an annexure on its first line opens nothing.
    assert by_text["Clause 3B of this ag"] == "Appendix-3B"
