"""The assist readers read a version's evidence in reading order, from ONE run.

BR-6 (2026-10-15): type suggestion, Key Obligations, Finding explanations and the
report's unmatched list ordered by (page, id), and `id` is a random uuid4 — so an
unpaginated DOCX (every page NULL) was read in no order at all, and type suggestion
and obligations also read every run's rows, not the latest completed one (P-8).
F3/BR-5: version_groups put page-less rows (DOCX tables) FIRST, every other reader
last. Synthetic text only; generation is faked at the single seam.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from legalmind.assist.ingestion import version_groups
from legalmind.assist.llm import generation
from legalmind.assist.synthesis import obligations, type_suggestion
from legalmind.db import models as M
from legalmind.domain import enums as E

T0 = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


def _version(db, user):
    contract = M.Contract(owner_id=user.id, name="Order MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    version = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="order.docx",
        mime_type="application/msword", file_size_bytes=1, file_hash="h",
        storage_key="k", processing_status=E.ProcessingStatus.COMPLETED,
        extraction_status=E.ExtractionStatus.COMPLETE, uploaded_by=user.id)
    db.add(version)
    db.flush()
    return version


def _run(db, version, minutes, rows):
    """A COMPLETED run whose rows are (content, page, offset), ids DESCENDING in
    offset order so a uuid tiebreak reads them backwards."""
    run = M.DocumentProcessingRun(
        document_version_id=version.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED, processor_version="t",
        started_at=T0 + timedelta(minutes=minutes))
    db.add(run)
    db.flush()
    for n, (content, page, offset) in enumerate(rows):
        db.add(M.DocumentEvidence(
            id=uuid.UUID(int=(minutes + 1) * 1000 - n), document_version_id=version.id,
            processing_run_id=run.id, page_number=page, content=content,
            source_type=E.EvidenceSourceType.NATIVE_TEXT,
            start_offset=offset, end_offset=offset + len(content)))
    db.flush()


def _unpaginated_twice_read(db, user):
    version = _version(db, user)
    _run(db, version, 0, [("STALE reading of the whole agreement.", None, 0)])
    _run(db, version, 5, [(f"Clause {n} of the agreement.", None, n * 100)
                          for n in range(1, 6)])
    return version


def _capture(monkeypatch, module, reply):
    seen = {}

    def fake(prompt, *, prompt_version, environment, request_id=None,
             evidence_count=None, max_output_tokens=1024):
        seen["prompt"] = prompt
        return generation.GenerationResult(
            text=reply, model="fake-model@test", prompt_version=prompt_version,
            payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(module.generation, "generate_raw", fake)
    return seen


def _clause_order(prompt):
    return sorted(range(1, 6), key=lambda n: prompt.index(f"Clause {n} "))


def test_type_suggestion_reads_the_latest_run_in_offset_order(db, user, monkeypatch):
    version = _unpaginated_twice_read(db, user)
    seen = _capture(monkeypatch, type_suggestion, "TYPE: MSA\nREASON: synthetic")
    type_suggestion.suggest_document_type(db, document_version_id=version.id)
    assert "STALE" not in seen["prompt"]
    assert _clause_order(seen["prompt"]) == [1, 2, 3, 4, 5]


def test_obligations_read_the_latest_run_in_offset_order(db, user, monkeypatch):
    version = _unpaginated_twice_read(db, user)
    seen = _capture(monkeypatch, obligations, "NONE")
    obligations.extract_obligations(db, document_version_id=version.id)
    assert "STALE" not in seen["prompt"]
    assert _clause_order(seen["prompt"]) == [1, 2, 3, 4, 5]


def test_version_groups_puts_page_less_rows_last(db, user):
    version = _version(db, user)
    _run(db, version, 0, [("pagelesstable", None, 0), ("firstpage", 1, 0)])
    assert version_groups._text(db, version.id) == "firstpage pagelesstable"
