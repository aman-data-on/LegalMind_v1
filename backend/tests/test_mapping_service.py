"""Mapping persistence/integration — locked Step 28 r15, 35.20, Step 30.

The property these protect: a mapping is reproducible from the Document Version
plus the configuration versions the Review captured — never from whatever
configuration happens to be current.
"""

from __future__ import annotations

import uuid

import pytest

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.enums import MappingState
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME
from legalmind.mapping.rules import MappingRules
from legalmind.mapping.service import load_clauses, run_mapping
from tests.conftest import make_user
from tests.test_ingestion import build_docx

LIABILITY_CONFIG = MappingRules(
    exact_phrases=("limitation of liability",),
    aliases=("aggregate liability",),
    keyword_groups=(("liability", "shall not exceed"),),
    section_heading_terms=("liability",),
    negative_patterns=("shall not be limited",),
).to_config()


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


def _configured_review(db, storage, user, *, mapping_config, paragraphs):
    """Build a Review whose snapshot pins one Requirement's mapping rules."""
    contract = M.Contract(owner_id=user.id, name="ACME MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()

    ingested = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=user.id,
        data=build_docx(paragraphs), filename="msa.docx",
        declared_mime=DOCX_MIME)

    req = M.Requirement(code=f"LIABILITY-{uuid.uuid4().hex[:4]}",
                        status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(
        requirement_id=req.id, version_number=1, name="Limitation of Liability",
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=user.id)
    db.add(rv); db.flush()

    std = M.CompanyStandardVersion(requirement_version_id=rv.id, version_number=1,
                                   configuration={"preferred": 6, "unit": "months"},
                                   created_by=user.id)
    mapping = M.MappingRuleVersion(requirement_version_id=rv.id, version_number=1,
                                   rules=mapping_config, created_by=user.id)
    evalrule = M.EvaluationRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, rules={},
        created_by=user.id)
    db.add_all([std, mapping, evalrule]); db.flush()

    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id)
    db.add(snap); db.flush()
    db.add(M.ConfigurationSnapshotItem(
        snapshot_id=snap.id, requirement_version_id=rv.id,
        company_standard_version_id=std.id, legal_rule_version_id=None,
        mapping_rule_version_id=mapping.id,
        evaluation_rule_version_id=evalrule.id))
    db.flush()

    review = M.Review(contract_id=contract.id,
                      document_version_id=ingested.document_version.id,
                      configuration_snapshot_id=snap.id,
                      status=E.ReviewStatus.PROCESSING, created_by=user.id)
    db.add(review); db.flush()
    return review, rv, mapping


def test_maps_ingested_document_end_to_end(db, storage):
    """Document -> Evidence -> Mapping, using snapshot configuration."""
    user = make_user(db)
    review, rv, _ = _configured_review(
        db, storage, user, mapping_config=LIABILITY_CONFIG,
        paragraphs=[
            "8.2 Limitation of Liability",
            "The aggregate liability of either party shall not exceed six "
            "months of fees paid under this Agreement.",
            "3.1 Payment Terms",
            "Invoices are payable within thirty days.",
        ])
    run = run_mapping(db, review)
    assert run.state_of(rv.id) is MappingState.CONFIRMED
    assert run.results[rv.id].evidence_ids


def test_mapping_uses_snapshot_rules_not_current_configuration(db, storage):
    """Step 30 / AUD-04 — publishing new configuration must not change a Review.

    A later, stricter mapping rule version is published. The Review's snapshot
    still points at version 1, so its mapping outcome must not move.
    """
    user = make_user(db)
    review, rv, mapping_v1 = _configured_review(
        db, storage, user, mapping_config=LIABILITY_CONFIG,
        paragraphs=["8.2 Limitation of Liability",
                    "Aggregate liability shall not exceed six months of fees."])
    before = run_mapping(db, review).state_of(rv.id)
    assert before is MappingState.CONFIRMED

    # Publish v2 with an unreachable threshold. New Reviews would use it; this
    # one must not.
    strict = dict(LIABILITY_CONFIG, confirm_threshold=999)
    db.add(M.MappingRuleVersion(requirement_version_id=rv.id, version_number=2,
                                rules=strict, created_by=user.id))
    db.flush()

    assert run_mapping(db, review).state_of(rv.id) is before


def test_only_latest_completed_processing_run_supplies_clauses(db, storage):
    """42.5 — failed attempts are retained for history but must not contribute
    clauses, or stale text could resurrect through a retry."""
    from legalmind.ingestion.service import process_document_version

    user = make_user(db)
    review, rv, _ = _configured_review(
        db, storage, user, mapping_config=LIABILITY_CONFIG,
        paragraphs=["8.2 Limitation of Liability",
                    "Aggregate liability shall not exceed six months of fees."])
    dv_id = review.document_version_id
    first_clauses = load_clauses(db, dv_id)
    assert first_clauses

    # A reprocess creates a second COMPLETED run with its own evidence rows.
    dv = db.get(M.DocumentVersion, dv_id)
    second = process_document_version(db, storage, dv,
                                      run_type=E.ProcessingRunType.REPROCESS)
    clauses = load_clauses(db, dv_id)
    ids = {c.evidence_id for c in clauses}
    second_run_ids = {
        e.id for e in db.query(M.DocumentEvidence).filter_by(
            processing_run_id=second.id).all()}
    assert ids == second_run_ids            # only the latest run's evidence
    assert ids.isdisjoint({c.evidence_id for c in first_clauses})


def test_failed_extraction_yields_no_clauses(db, storage):
    """34.9 / Step 28 r6 — no text means no mapping, never a guessed one."""
    user = make_user(db)
    contract = M.Contract(owner_id=user.id, name="Scan",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    from tests.test_ingestion import build_image_only_pdf
    from legalmind.ingestion.validation import PDF_MIME

    ingested = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=user.id,
        data=build_image_only_pdf(), filename="scan.pdf", declared_mime=PDF_MIME)
    assert ingested.document_version.extraction_status is E.ExtractionStatus.FAILED
    assert load_clauses(db, ingested.document_version.id) == []


def test_unconfigured_requirement_is_simply_absent_from_results(db, storage):
    """A Requirement not in the snapshot is not mapped at all — the engine does
    not invent configuration for it."""
    user = make_user(db)
    review, rv, _ = _configured_review(
        db, storage, user, mapping_config=LIABILITY_CONFIG,
        paragraphs=["8.2 Limitation of Liability",
                    "Aggregate liability shall not exceed six months of fees."])
    run = run_mapping(db, review)
    assert set(run.results) == {rv.id}
