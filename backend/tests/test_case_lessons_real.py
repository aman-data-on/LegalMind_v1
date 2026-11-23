"""Batch 8 sub-batch A (AB-222, `AM-461`–`AM-463`) on the real case that taught it — a
client MoU returned by its lawyer (owner Q9: the two files sit in the gitignored
source-material folder, locked 54.6). Structural only: counts, kinds and states, never a
word of the documents; every test skips when the files are absent (CI has none).
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from legalmind.analysis import consistency as K
from legalmind.analysis import lawyer_rows
from legalmind.analysis import negotiation as N
from legalmind.analysis import service as S
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion import parsing
from legalmind.mapping.engine import Clause
from legalmind.mapping.service import load_clauses
from tests.legal_regression.test_legal_regression import _findings
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified
from tests.test_negotiation import _ingest

_CASE = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "/nonexistent")) \
    / "cases" / "2026-11-client-mou"
OURS, THEIRS = _CASE / "earlier-signed-mou.docx", _CASE / "client-final-mou.docx"
pytestmark = pytest.mark.skipif(not (OURS.is_file() and THEIRS.is_file()),
                                reason="source material not provisioned")


def _read(path: Path) -> parsing.ParseResult:
    return parsing.parse_docx(path.read_bytes())


def _clauses(path: Path) -> list[Clause]:
    """The body rows as `load_clauses` reads them (marks and highlights included)."""
    out = []
    for k, s in enumerate(_read(path).segments):
        meta = s.metadata
        if meta.get("part") in ("header", "footer", "contents"):
            continue
        rev = meta.get("revision") or {}
        marks = ({"changes": rev.get("changes") or [], "comments": meta.get("comments") or [],
                  "original": rev.get("original")}
                 if rev.get("changes") or meta.get("comments") else None)
        out.append(Clause(uuid.uuid5(uuid.NAMESPACE_URL, f"{path.name}#{k}"), s.content,
                          s.section_number, s.section_title, s.page_number,
                          bool(meta.get("heading")), marks,
                          tuple(meta.get("highlighted") or ())))
    return out


def test_case_mou_final_reads_fifteen_highlight_runs():
    """R2.1: the client's 15 highlighted runs land on their rows (consecutive runs as
    one string), the signature table's included; our signed copy has none."""
    segments = _read(THEIRS).segments
    lit = [s for s in segments if s.metadata.get("highlighted")]
    assert len(lit) >= 8
    tables = [s for s in segments if s.source_type is E.EvidenceSourceType.TABLE]
    assert tables[-1].metadata.get("highlighted")               # the signature table
    assert not any(s.metadata.get("highlighted") for s in _read(OURS).segments)


def test_case_mou_final_keeps_one_of_one_comment():
    """R3a: the client lawyer's one comment, made in a signature-table cell, is kept."""
    result = _read(THEIRS)
    assert any(d.startswith("1 of 1 comment(s) kept") for d in result.diagnostics)
    [noted] = [s for s in result.segments if s.metadata.get("comments")]
    assert noted.source_type is E.EvidenceSourceType.TABLE


def test_case_pair_has_no_phantom_heading_rows_and_labels_punctuation():
    """R3d: no heading shown DELETED while it is still in the file (two on the case);
    the dash-and-full-stop row is the one row labelled punctuation only."""
    ours, theirs = _clauses(OURS), _clauses(THEIRS)
    old, new = N._units(ours), N._units(theirs)
    bare = N._align(old, new)
    assert sum(i is not None and j is None and old[i]["heading_only"]
               for i, j, _ in bare) == 2                         # before the fold
    rows = N.fold_headings(old, new, bare)
    assert not any(i is not None and j is None and old[i]["heading_only"]
                   for i, j, _ in rows)
    punctuation = [1 for i, j, m in rows if i is not None and j is not None
                   and N._kind(old[i], new[j], m) == "MODIFIED"
                   and N.same_words(old[i]["text"], new[j]["text"], old[i]["number"],
                                    new[j]["number"])]
    assert len(punctuation) == 1


def test_case_mou_final_commercial_observations():
    """R6: two quantities stated two ways, one blank field, our CIN with a stray
    character — and the totals, which add up, say nothing."""
    kinds = [o["kind"] for o in K.observe(_clauses(THEIRS))["structural"]]
    assert kinds.count(K.QUANTITY_TWO_WAYS) == 2
    assert kinds.count(K.BLANK_FIELD) == 1
    assert kinds.count(K.OUR_CIN) == 1
    assert K.TOTALS_DIFFER not in kinds


CONVENIENCE, VENUE = "CONVENIENCE-NOTICE-MSA-001", "DISPUTE-VENUE-MSA-001"


def test_case_mou_convenience_notice_and_venue_origin(build, db, tmp_path):
    """R3b: CONVENIENCE-NOTICE reads its 30 days on both versions (the client's file
    breaks the sentence before "(30)"). R3c: the venue paragraph is ours word for word,
    so DISPUTE-VENUE is ALREADY_OURS although the price table read with it changed."""
    for code in (CONVENIENCE, VENUE):
        _ratified(build, code)
    contract = M.Contract(owner_id=build.owner.id, name="Case", status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    reviews = []
    for path, name in ((OURS, "ours.docx"), (THEIRS, "theirs.docx")):
        version = _ingest(db, tmp_path, contract, path.read_bytes(), name)
        review = M.Review(contract_id=contract.id, document_version_id=version.id,
                          configuration_snapshot_id=build.snapshot.id,
                          status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
        db.add(review)
        db.flush()
        S.run_analysis(db, review)
        reviews.append(review)
    found = [_findings(db, r) for r in reviews]
    assert [f[CONVENIENCE]["classification"] for f in found] == ["MATCH", "MATCH"]
    ours_v, theirs_v = (db.get(M.DocumentVersion, r.document_version_id) for r in reviews)
    changed = lawyer_rows.changed_evidence(load_clauses(db, ours_v.id),
                                           load_clauses(db, theirs_v.id))
    cited = db.scalars(select(M.EvaluationEvidence.evidence_id).join(
        M.Evaluation, M.Evaluation.id == M.EvaluationEvidence.evaluation_id).join(
        M.Finding, M.Finding.id == M.Evaluation.finding_id).join(
        M.RequirementVersion, M.RequirementVersion.id == M.Finding.requirement_version_id
    ).join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id).where(
        M.Finding.review_id == reviews[1].id, M.Requirement.code == VENUE)).all()
    assert cited
    assert lawyer_rows.origin([str(e) for e in cited], VENUE,
                              found[1][VENUE]["classification"], changed,
                              {VENUE: found[0][VENUE]["classification"]}) \
        == lawyer_rows.ALREADY_OURS
