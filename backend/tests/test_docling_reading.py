"""Docling reads TABLES only (owner "use docling", 2026-10-15; reworked the same day).

Prose is always the standard parser's: a Docling table replaces a page's blocks only when
they are consecutive, the words and characters are the same multisets, and every cell is
exactly the page's own words inside the cell's box, so it can regroup a page's own words
into `| a | b |` rows and do nothing else. Pinned on synthetic runner JSON (what docling_runner.py
writes), so it runs on CI with no Docling; the integration tests run only where
LEGALMIND_DOCLING_PYTHON/LEGALMIND_DOCLING_MODELS point at a provisioned Docling, and the
corpus ones only where the source material is present too (never on CI).
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import select

from legalmind import config
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.enums import EvidenceSourceType
from legalmind.ingestion import parsing
from legalmind.ingestion.parsing import parse_pdf, table_row
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import PDF_MIME
from tests.conftest import make_user
from tests.test_pdf_reading import CREDIT_ROWS, _ruled_table_pdf

pymupdf = pytest.importorskip("pymupdf")

LINES = ["1. Service Credits", "Credits are paid on the monthly fee as below.",
         "Less than 99.9%", "15%", "Less than 99.0%", "40%",
         "2. Exclusions", "Scheduled maintenance is excluded."]
ROWS = [["Less than 99.9%", "15%"], ["Less than 99.0%", "40%"]]


def _pdf(lines: list[str] = LINES, *, rules: int = 3, at: dict | None = None) -> bytes:
    """``lines`` at y = 72 + 18 i (or at ``at[line]``), with ``rules`` thin horizontal
    rules of one width under them."""
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((at or {}).get(line, (72, 72 + 18 * i)), line, fontsize=10)
    for i in range(rules):
        page.draw_line((72, 240 + 10 * i), (300, 240 + 10 * i), width=0.5)
    return doc.tobytes()


def _box(text: str, data: bytes | None = None) -> list[float]:
    """Where ``text`` is on page 1 of ``data`` (default `_pdf()`): a cell's box."""
    hits = pymupdf.open(stream=data or _pdf(), filetype="pdf")[0].search_for(text)
    return list(hits[0]) if hits else [0, 0, 0, 0]


def _table(rows: list[list[str]], bbox=(60, 100, 400, 170), data: bytes | None = None,
           boxes: dict | None = None) -> dict:
    """What the runner writes: each cell at its own text's place on the page (or at
    ``boxes[text]``'s); the default bbox is around LINES[2:6]."""
    return {"bbox": list(bbox), "rows": rows,
            "cells": [{"text": c, "bbox": (boxes or {}).get(c) or _box(c, data)}
                      for row in rows for c in row]}


TABLE = _table(ROWS)


@pytest.fixture
def docling(monkeypatch):
    """Docling 'configured', its reading replaced by the JSON the test sets; the page
    count of each subset it was sent is recorded under "sent"."""
    reading: dict = {"docling_version": "9.9.9", "pages": {}}
    sent: list[int] = []

    def read(data, n):
        sent.append(pymupdf.open(stream=data, filetype="pdf").page_count)
        return reading, None
    monkeypatch.setattr(parsing, "docling_available", lambda: True)
    monkeypatch.setattr(parsing, "_docling_read", read)
    reading["sent"] = sent
    return reading


def test_a_docling_table_is_inlined_inside_its_clause(docling):
    docling["pages"]["1"] = [TABLE]
    result = parse_pdf(_pdf())

    clause = next(s for s in result.segments if s.section_number == "1")
    assert clause.content.split("\n") == [LINES[0], LINES[1], table_row(ROWS[0]),
                                          table_row(ROWS[1])]
    assert clause.metadata["tables"] == 1
    assert clause.source_type is EvidenceSourceType.NATIVE_TEXT
    assert [s.section_number for s in result.segments] == ["1", "2"]
    assert result.reader == {"docling_version": "9.9.9", "docling_pages": [1],
                             "docling_tables": [1], "fallback_reasons": {}}
    assert "Docling 9.9.9 read tables on 1 page(s): inlined on pages 1" \
        in result.diagnostics


@pytest.mark.parametrize("rows", [
    [["Less than 99.9%", "15%"], ["Less than", "40%"]],            # a word lost
    [["Less than 99.9%", "15%"], ["Less than 99.0%", "4O%"]],      # a word rewritten
    [["Less than 99.9%", "15%"], ["Not less than 99.0%", "40%"]],  # a word added
])
def test_a_table_whose_words_differ_keeps_the_standard_lines(docling, rows):
    docling["pages"]["1"] = [_table(rows)]
    standard = parse_pdf(_pdf(), docling=False)
    result = parse_pdf(_pdf())

    assert result.segments == standard.segments
    assert result.reader["docling_tables"] == []
    assert result.reader["fallback_reasons"] == {1: "words differ or a ruled grid stands"}


def test_a_one_row_docling_table_is_not_a_table(docling):
    """TOS-cloudpe's navigation footer came back as a one-row 'table'."""
    docling["pages"]["1"] = [{"bbox": TABLE["bbox"], "rows": [[" ".join(LINES[2:6])]],
                              "cells": [{"text": " ".join(LINES[2:6]),
                                         "bbox": TABLE["bbox"]}]}]
    assert parse_pdf(_pdf()).segments == parse_pdf(_pdf(), docling=False).segments


def test_a_ruled_grid_pymupdf_reads_is_not_doubled_or_replaced(docling):
    """A ruled grid both readers find: the standard parser's rows, once — its geometry
    carries a merged label down, which Docling's TableFormer missed."""
    data = _ruled_table_pdf()
    page = pymupdf.open(stream=data, filetype="pdf")[0]
    (found,) = page.find_tables(strategy="lines_strict").tables
    docling["pages"]["1"] = [_table(CREDIT_ROWS, found.bbox, data)]
    result = parse_pdf(data)

    assert result.segments == parse_pdf(data, docling=False).segments
    assert result.reader["docling_tables"] == []
    text = "\n".join(s.content for s in result.segments)
    assert text.count(table_row(CREDIT_ROWS[1])) == 1


def test_a_docling_label_carried_down_its_span_is_counted_once(docling):
    """rows carry a vertically merged label down; the word check counts it once."""
    lines = ["1. Caps", "Dedicated Servers", "12 months fees", "Service credits",
             "2. Exclusions apply."]
    rows = [["Dedicated Servers", "12 months fees"],
            ["Dedicated Servers", "Service credits"]]
    data = _pdf(lines)
    docling["pages"]["1"] = [{"bbox": [60, 82, 400, 140], "rows": rows,
                              "cells": [{"text": t, "bbox": _box(t, data)} for t in (
                                  "Dedicated Servers", "12 months fees",
                                  "Service credits")]}]
    clause = parse_pdf(_pdf(lines)).segments[0]
    assert clause.content.split("\n") == ["1. Caps", *map(table_row, rows)]


@pytest.mark.parametrize("reading", [
    ["not", "a", "dict"],
    {"pages": []},
    {"pages": {"1": [{"bbox": [1, 2, 3], "rows": [["a", "b"]], "cells": ["a", "b"]}]}},
    {"pages": {"1": [{"bbox": [1, 2, 3, True], "rows": [["a", "b"]], "cells": ["a", "b"]}]}},
    {"pages": {"1": [{"bbox": [1, 2, 3, 4], "rows": [["a", 5]], "cells": ["a", "b"]}]}},
    {"pages": {"1": [{"bbox": [1, 2, 3, 4], "rows": "a | b", "cells": []}]}},
    {"pages": {"1": [{"bbox": [1, 2, 3, 4], "rows": [["a", "b"]]}]}},   # no cells
    {"pages": {"1": [{"bbox": [1, 2, 3, 4], "rows": [["a", "b"]], "cells": ["a", "b"]}]}},
    {"pages": {"1": [{"bbox": [1, 2, 3, 4], "rows": [["a", "b"]],
                      "cells": [{"text": "a", "bbox": [1, 2, 3]}]}]}},
    {"pages": {"2": []}},                       # a page that was never sent
    {"pages": {"one": []}},
])
def test_malformed_docling_output_falls_back_to_the_standard_result(
        monkeypatch, reading):
    monkeypatch.setattr(parsing, "docling_available", lambda: True)
    monkeypatch.setattr(parsing, "_docling_read", lambda data, n: (reading, None))
    standard = parse_pdf(_pdf(), docling=False)
    result = parse_pdf(_pdf())
    assert result.segments == standard.segments and result.status == standard.status
    assert result.reader["fallback_reasons"] == {1: "Docling output malformed"}
    assert result.diagnostics[-1].endswith(
        "standard tables on page(s) 1 (Docling output malformed)")


def test_a_docling_step_that_raises_falls_back(monkeypatch):
    def boom(data, n):
        raise MemoryError
    monkeypatch.setattr(parsing, "docling_available", lambda: True)
    monkeypatch.setattr(parsing, "_docling_read", boom)
    result = parse_pdf(_pdf())
    assert result.segments == parse_pdf(_pdf(), docling=False).segments
    assert result.reader["fallback_reasons"] == {1: "Docling failed (MemoryError)"}


def test_only_pages_that_can_hold_a_table_are_sent(docling):
    doc = pymupdf.open()
    for rules in (0, 3, 2, 5):          # pages 1-4: pages 2 and 4 pass the gate
        doc.insert_pdf(pymupdf.open(stream=_pdf(rules=rules), filetype="pdf"))
    docling["pages"]["2"] = [TABLE]     # the subset's page 2 is the document's page 4
    result = parse_pdf(doc.tobytes())

    assert docling["sent"] == [2]
    assert result.reader["docling_pages"] == [2, 4]
    assert result.reader["docling_tables"] == [4]
    assert {s.page_number for s in result.segments if table_row(ROWS[0]) in s.content} \
        == {4}


def test_a_document_with_no_ruled_page_never_runs_docling(monkeypatch):
    monkeypatch.setattr(parsing, "docling_available", lambda: True)
    monkeypatch.setattr(parsing, "_docling_read",
                        lambda *a: pytest.fail("Docling ran with no gated page"))
    data = _pdf(rules=2)
    result = parse_pdf(data, defer_ocr=True)
    assert not result.needs_ocr
    assert result == parse_pdf(data, docling=False)
    assert result.reader == {}


def test_a_deferred_read_defers_only_with_a_gated_page(docling):
    result = parse_pdf(_pdf(), defer_ocr=True)
    assert result.needs_ocr and result.segments == [] and result.pages_total == 1
    assert result.diagnostics == ["table reading of 1 page(s) deferred to a background run"]
    # A read that cannot wait (a chat attachment) never runs Docling and never defers.
    assert not parse_pdf(_pdf(), defer_ocr=True, ocr=False).needs_ocr
    assert not parse_pdf(_pdf(), defer_ocr=True, docling=False).needs_ocr
    assert docling["sent"] == []


def test_unavailable_docling_is_the_standard_result_exactly(monkeypatch):
    monkeypatch.setattr(parsing, "docling_available", lambda: False)
    monkeypatch.setattr(parsing, "_docling_read",
                        lambda *a: pytest.fail("Docling ran while unavailable"))
    assert parse_pdf(_pdf()) == parse_pdf(_pdf(), docling=False)
    assert parse_pdf(_pdf()).reader == {}


def test_docling_available_needs_both_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("LEGALMIND_DOCLING_PYTHON", sys.executable)
    monkeypatch.delenv("LEGALMIND_DOCLING_MODELS", raising=False)
    assert not parsing.docling_available()
    monkeypatch.setenv("LEGALMIND_DOCLING_MODELS", str(tmp_path / "absent"))
    assert not parsing.docling_available()
    monkeypatch.setenv("LEGALMIND_DOCLING_MODELS", str(tmp_path))
    assert parsing.docling_available()


@pytest.fixture
def configured(monkeypatch, tmp_path):
    """Docling 'configured' on this python (which has none); returns the OCR languages,
    asked of tesseract before a test fakes subprocess.run."""
    monkeypatch.setenv("LEGALMIND_DOCLING_PYTHON", sys.executable)
    monkeypatch.setenv("LEGALMIND_DOCLING_MODELS", str(tmp_path))
    return config.ocr_languages()


@pytest.mark.parametrize("outcome, reason", [
    (subprocess.TimeoutExpired("docling", 80), "Docling timed out after 80 s"),
    (subprocess.CompletedProcess([], -9, b"", b""), "Docling was killed (signal 9)"),
    (subprocess.CompletedProcess([], 1, b"", b""), "Docling exited 1"),
    (subprocess.CompletedProcess([], 0, b"", b""), "Docling wrote no readable output"),
])
def test_a_failed_docling_run_leaves_the_standard_result(monkeypatch, configured,
                                                         outcome, reason):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(subprocess, "run", run)

    standard = parse_pdf(_pdf(), docling=False)
    result = parse_pdf(_pdf())
    assert result.segments == standard.segments and result.status == standard.status
    assert result.reader["fallback_reasons"] == {1: reason}
    (command, kwargs), = calls
    at = command.index("-I")
    assert command[at + 1].endswith("docling_runner.py")
    # first in line for the OOM killer through `choom`, never a preexec_fn (review
    # 2026-10-16: Python between fork and exec in a threaded process can deadlock)
    import shutil
    assert "preexec_fn" not in kwargs
    if shutil.which("choom"):
        assert command[1:4] == ["-n", "1000", "--"]
    assert kwargs["timeout"] == 80                          # 60 s + 20 s x 1 page
    env = kwargs["env"]
    assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["TMPDIR"] == env["HOME"] == kwargs["cwd"]
    assert command[-1] == configured


def test_a_busy_docling_falls_back_within_the_deadline(monkeypatch, configured):
    """Another conversion holds a lock: wait no longer than the run's own budget."""
    import fcntl
    import tempfile

    monkeypatch.setattr(parsing, "DOCLING_TIMEOUT_BASE_S", 0)
    monkeypatch.setattr(parsing, "DOCLING_TIMEOUT_PER_PAGE_S", 0.2)
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: pytest.fail("Docling ran while busy"))
    standard = parse_pdf(_pdf(), docling=False)
    with parsing._DOCLING_LOCK:                 # another thread of this process
        result = parse_pdf(_pdf())
    assert result.segments == standard.segments
    assert result.reader["fallback_reasons"] == {1: "Docling busy"}

    with open(Path(tempfile.gettempdir(), parsing._DOCLING_LOCK_FILE), "w") as other:
        fcntl.flock(other, fcntl.LOCK_EX)       # another process on the host
        assert parse_pdf(_pdf()).reader["fallback_reasons"] == {1: "Docling busy"}
    assert parsing._DOCLING_LOCK.acquire(blocking=False)    # released on the way out
    parsing._DOCLING_LOCK.release()


def test_a_real_child_that_cannot_import_docling_falls_back(configured):
    """No monkeypatched subprocess: this python has no Docling, so the runner exits 1."""
    if subprocess.run([sys.executable, "-I", "-c", "import docling"],
                      capture_output=True, check=False).returncode == 0:
        pytest.skip("this python has Docling")
    result = parse_pdf(_pdf())
    assert result.segments == parse_pdf(_pdf(), docling=False).segments
    assert result.reader["fallback_reasons"] == {1: "Docling exited 1"}


@pytest.fixture
def store(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


def _ingest(db, store, data, *, defer_ocr):
    owner = make_user(db)
    contract = M.Contract(owner_id=owner.id, name="Docling", contract_type="SLA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    return ingest_document(db, store, contract_id=contract.id, uploaded_by=owner.id,
                           data=data, filename="doc.pdf", declared_mime=PDF_MIME,
                           defer_ocr=defer_ocr)


def test_an_upload_with_a_gated_page_defers_to_the_background_run(db, store, docling):
    result = _ingest(db, store, _pdf(), defer_ocr=True)
    assert result.document_version.processing_status is E.ProcessingStatus.PROCESSING
    assert result.evidence_count == 0
    assert result.processing_run.run_metadata["ocr_required"] is True


def test_the_reader_is_recorded_on_the_processing_run(db, store, docling):
    docling["pages"]["1"] = [TABLE]
    run = _ingest(db, store, _pdf(), defer_ocr=False).processing_run
    assert run.run_metadata["reader"]["docling_tables"] == [1]
    rows = db.execute(select(M.DocumentEvidence)
                      .where(M.DocumentEvidence.processing_run_id == run.id)).scalars()
    assert any(table_row(ROWS[1]) in r.content for r in rows)


def test_a_deferral_for_tables_alone_is_recorded_as_such(db, store, docling):
    run = _ingest(db, store, _pdf(), defer_ocr=True).processing_run
    assert run.run_metadata["docling_deferred"] is True


# =====================================================================
# Hardening (verifier, 2026-10-15)
# =====================================================================
def test_two_rows_values_swapped_are_rejected_by_the_cells_place(docling):
    """The same characters and words, the same rows' labels — but each value where the
    other one is printed: only the cell geometry tells, and it keeps the standard lines."""
    swapped = [["Less than 99.9%", "40%"], ["Less than 99.0%", "15%"]]
    docling["pages"]["1"] = [_table(swapped, boxes={"40%": _box("15%"),
                                                    "15%": _box("40%")})]
    result = parse_pdf(_pdf())
    assert result.segments == parse_pdf(_pdf(), docling=False).segments
    assert result.reader["docling_tables"] == []


def test_two_rows_joined_are_rejected(docling):
    joined = [["Less than 99.9% Less than 99.0%", "15% 40%"], ["", ""]]
    docling["pages"]["1"] = [{"bbox": TABLE["bbox"], "rows": joined, "cells": [
        {"text": "Less than 99.9% Less than 99.0%", "bbox": [60, 95, 400, 150]},
        {"text": "15% 40%", "bbox": [60, 112, 400, 168]}]}]
    assert parse_pdf(_pdf()).reader["docling_tables"] == []


@pytest.mark.parametrize("cell", ["Less than 99.9% but <= 99.0%",   # '>=' flipped
                                  "Less than 99.9 but >= 99.0%"])   # a '%' dropped
def test_a_flipped_operator_or_a_dropped_sign_is_rejected(docling, cell):
    """Both have the page's \\w+ words exactly; the characters differ."""
    lines = ["1. Credits", "Less than 99.9% but >= 99.0%", "15%",
             "Less than 99.0%", "40%", "2. Exclusions apply."]
    data = _pdf(lines)
    rows = [[cell, "15%"], ["Less than 99.0%", "40%"]]
    boxes = {cell: _box("Less than 99.9% but >= 99.0%", data)}
    docling["pages"]["1"] = [_table(rows, (60, 80, 400, 155), data, boxes)]
    assert parse_pdf(data).reader["docling_tables"] == []
    docling["pages"]["1"] = [_table([["Less than 99.9% but >= 99.0%", "15%"], rows[1]],
                                    (60, 80, 400, 155), data)]
    assert parse_pdf(data).reader["docling_tables"] == [1]       # the control


def test_a_table_is_rejected_when_another_block_sits_between_its_blocks(docling):
    """In stream order a block outside the table lies between two it would replace:
    splicing would move it, so the standard lines stand."""
    data = _pdf([*LINES[:4], "Footnote outside", *LINES[4:]],
                at={"Footnote outside": (72, 400), **{
                    line: (72, 72 + 18 * i) for i, line in enumerate(LINES)}})
    docling["pages"]["1"] = [_table(ROWS, data=data)]
    result = parse_pdf(data)
    assert result.reader["docling_tables"] == []
    assert result.segments == parse_pdf(data, docling=False).segments


def test_the_gate_counts_rules_of_one_extent_only():
    def page(*spans):
        doc = pymupdf.open()
        p = doc.new_page()
        for i, (x0, x1) in enumerate(spans):
            p.draw_line((x0, 100 + 20 * i), (x1, 100 + 20 * i), width=0.5)
        return pymupdf.open(stream=doc.tobytes(), filetype="pdf")[0]

    assert parsing._table_rules(page((72, 300), (73, 299), (72, 302))) == 3   # a table
    assert parsing._table_rules(page((72, 150), (72, 220), (100, 300))) == 1  # underlines
    assert parsing._table_rules(page()) == 0


def test_pages_are_read_in_runs_and_merged(monkeypatch):
    monkeypatch.setattr(parsing, "DOCLING_MAX_PAGES_PER_RUN", 2)
    monkeypatch.setattr(parsing, "docling_available", lambda: True)
    readings = iter([{"docling_version": "9.9.9", "pages": {"2": [TABLE]}},
                     {"docling_version": "9.9.9", "pages": {}},
                     {"docling_version": "9.9.9", "pages": {"1": [TABLE]}}])
    sent: list[int] = []

    def read(data, n):
        sent.append(pymupdf.open(stream=data, filetype="pdf").page_count)
        assert n == sent[-1]                    # each run's own deadline
        return next(readings), None
    monkeypatch.setattr(parsing, "_docling_read", read)
    doc = pymupdf.open()
    for _ in range(5):
        doc.insert_pdf(pymupdf.open(stream=_pdf(), filetype="pdf"))
    result = parse_pdf(doc.tobytes())
    assert sent == [2, 2, 1]
    assert result.reader["docling_tables"] == [2, 5]
    assert result.reader["fallback_reasons"] == {}


def test_a_failed_run_ends_the_reading_and_keeps_earlier_runs(monkeypatch):
    monkeypatch.setattr(parsing, "DOCLING_MAX_PAGES_PER_RUN", 1)
    monkeypatch.setattr(parsing, "docling_available", lambda: True)
    replies = iter([({"docling_version": "9.9.9", "pages": {"1": [TABLE]}}, None),
                    (None, "Docling busy")])
    monkeypatch.setattr(parsing, "_docling_read", lambda data, n: next(replies))
    doc = pymupdf.open()
    for _ in range(3):
        doc.insert_pdf(pymupdf.open(stream=_pdf(), filetype="pdf"))
    result = parse_pdf(doc.tobytes())                # a third run would raise
    assert result.reader["docling_tables"] == [1]
    assert result.reader["fallback_reasons"] == {2: "Docling busy", 3: "Docling busy"}


def test_too_many_table_pages_skip_docling_and_never_defer(monkeypatch):
    monkeypatch.setattr(parsing, "DOCLING_MAX_PAGES_TOTAL", 1)
    monkeypatch.setattr(parsing, "docling_available", lambda: True)
    monkeypatch.setattr(parsing, "_docling_read",
                        lambda *a: pytest.fail("Docling ran past the page cap"))
    doc = pymupdf.open()
    for _ in range(2):
        doc.insert_pdf(pymupdf.open(stream=_pdf(), filetype="pdf"))
    data = doc.tobytes()
    assert not parse_pdf(data, defer_ocr=True).needs_ocr
    result = parse_pdf(data)
    assert result.segments == parse_pdf(data, docling=False).segments
    assert result.reader["fallback_reasons"] == {
        1: "too many table pages for Docling", 2: "too many table pages for Docling"}


@pytest.mark.skipif(not Path("/proc/self/oom_score_adj").exists(), reason="not Linux")
def test_the_child_is_first_in_line_for_the_oom_killer(monkeypatch, configured, tmp_path):
    """A fake runner reports its own oom_score_adj as the version it read with."""
    fake = tmp_path / "fake_runner.py"
    fake.write_text('import json, sys\n'
                    'json.dump({"docling_version": open("/proc/self/oom_score_adj")'
                    '.read().strip(), "pages": {}}, open(sys.argv[2], "w"))\n')
    monkeypatch.setattr(parsing, "_DOCLING_RUNNER", fake)
    assert parse_pdf(_pdf()).reader["docling_version"] == "1000"

# =====================================================================
# Integration — a provisioned Docling (never on CI)
# =====================================================================
needs_docling = pytest.mark.skipif(not parsing.docling_available(),
                                   reason="Docling not configured")
CORPUS = Path(config.source_material_dir())
APPROVED = ["AUP-cloudpe.pdf", "AUP-leapswitch.pdf", "MSA-Feb.pdf",
            "MSA-GRP-2026-07-30.pdf", "MSA-original.pdf", "MSA.pdf", "NDA.pdf",
            "PRIVACY-cloudpe.pdf", "PRIVACY-leapswitch.pdf", "SLA-cloudpe.pdf",
            "SLA-leapswitch.pdf", "TOS-cloudpe.pdf", "TOS-leapswitch.pdf"]


def _corpus(name: str, **kwargs):
    path = CORPUS / name
    if not path.is_file():
        pytest.skip(f"source material absent ({name})")
    return parse_pdf(path.read_bytes(), **kwargs)


def _page_lines(result) -> dict[int | None, list[str]]:
    pages: dict[int | None, list[str]] = {}
    for s in result.segments:
        pages.setdefault(s.page_number, []).extend(s.content.split("\n"))
    return pages


@needs_docling
def test_a_real_run_on_a_ruled_grid_leaves_the_standard_rows():
    """The real runner's JSON passes the shape check, and a drawn grid PyMuPDF reads
    stays PyMuPDF's: the reading is the standard one exactly."""
    result = parse_pdf(_ruled_table_pdf())
    assert result.reader["fallback_reasons"] == {
        1: "words differ or a ruled grid stands"}, result.diagnostics
    assert result.segments == parse_pdf(_ruled_table_pdf(), docling=False).segments
    clause = next(s for s in result.segments if s.section_number == "7.1")
    assert "| < 99.0% but >= 95.0% | 10% of monthly fee |" in clause.content


@needs_docling
@pytest.mark.parametrize("name", APPROVED)
def test_docling_only_regroups_a_pages_own_words_into_rows(name):
    """THE invariant: per page the same \\w+ words, and every line that is not a table
    row is the standard read's line, in the standard read's order — Docling never adds,
    drops, moves or rewrites prose (the page-break duplication, the moved notice
    address and the one-word flips the prose design allowed cannot happen here)."""
    standard, read = _page_lines(_corpus(name, docling=False)), _page_lines(_corpus(name))
    assert standard.keys() == read.keys()
    for page, lines in read.items():
        assert Counter(re.findall(r"\w+", "\n".join(lines))) == Counter(
            re.findall(r"\w+", "\n".join(standard[page]))), (name, page)
        prose = iter(standard[page])
        assert all(line in prose for line in lines if not line.startswith("| ")), \
            (name, page)


@needs_docling
def test_the_cloudpe_credit_tiers_come_out_as_rows():
    rows = [line for s in _corpus("SLA-cloudpe.pdf").segments
            for line in s.content.split("\n") if line.startswith("| ")]
    for credit in ("5%", "10%", "20%"):
        assert any(row.endswith(f"| {credit} |") for row in rows), (credit, rows)


@needs_docling
def test_the_leapswitch_sla_keeps_its_credit_rows_and_qualifier():
    result = _corpus("SLA-leapswitch.pdf")
    lines = [line for s in result.segments for line in s.content.split("\n")]
    assert any(line.startswith("*99.95% for Power (Dual-powered servers)")
               for line in lines)
    issuance = next(s for s in result.segments
                    if s.section_title == "Issuance of Service Credits")
    for credit in ("15%", "40%", "100%"):
        assert any(line.startswith("| ") and line.endswith(f"| {credit} |")
                   for line in issuance.content.split("\n")), credit
