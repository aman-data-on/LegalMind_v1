"""Batch 8 item 5 (`AM-467`, C-34 open): which of our standard sets measured the paper.

Round 2 (D1): the source is read at serve time from fields every ratified file already
has — nothing is written to configuration, so no standard is re-versioned, nothing is
re-imported or published, and no carried Legal Decision moves (`AM-317` r7). Source
names and point counts reach Legal only (D5). Nothing here chooses a side of C-34.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from legalmind.api.routers.deal_brief import (
    MSA_TERMS_ON_OTHER_PAPER,
    measured_against,
    standard_sources,
)
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from legalmind.security import audit as A
from tests.conftest import make_finding, make_user
from tests.legal_regression.test_carry_forward_am317 import (
    CAPPED,
    _cap_finding,
    _carried,
    _deal,
)
from tests.legal_regression.test_effect_for_us import _version
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tools.import_ratified_standards import import_standards
from tools.publish_payload import split

MSA, CONSTITUTION = "LIABILITY-MSA-001", "CONVENIENCE-NOTICE-MSA-001"
MSA2 = "ARBITRATION-MSA-001"   # a second standard that quotes our MSA (one point each)


def test_every_published_requirement_maps_to_a_kind():
    active, retired = split(RATIFIED_STANDARDS_DIR)
    known = standard_sources()
    assert set(active) | set(retired) <= set(known)
    assert {known[c]["kind"] for c in active} <= {
        "OUR_MSA", "CONSTITUTION", "PUBLISHED_POLICY", "OTHER_DOCUMENT"}
    assert known[MSA]["kind"] == "OUR_MSA" and known[CONSTITUTION]["kind"] == "CONSTITUTION"
    assert known["LIABILITY-TOS-001"]["kind"] == "PUBLISHED_POLICY"
    assert known["GOVLAW-NDA-001"]["kind"] == "OTHER_DOCUMENT"
    assert all("LEGALMIND_SOURCE_MATERIAL_DIR" not in v["name"] and "docs/" not in v["name"]
               for v in known.values())


def _versions(db) -> tuple[int, int, int]:
    return tuple(db.scalar(select(func.count()).select_from(t)) for t in (
        M.RequirementVersion, M.CompanyStandardVersion, M.ConfigurationSnapshot))


def test_nothing_in_configuration_or_requirement_versions_changes(db):
    """The importer is as on main: a second import writes no version, and no stored
    configuration carries a source key."""
    email = make_user(db).email
    import_standards(db, actor_email=email)
    db.flush()
    once = _versions(db)
    import_standards(db, actor_email=email)
    db.flush()
    assert _versions(db) == once
    assert not db.scalar(select(func.count()).select_from(M.CompanyStandardVersion).where(
        M.CompanyStandardVersion.configuration.has_key("source")))


def test_carry_forward_keeps_decisions_unchanged(build, db, seeded):
    """A decided point carries to the next version exactly as before, with the brief's
    standard sets read in between (nothing is written by reading them)."""
    contract, decision = _deal(build, db, seeded)
    first = db.scalars(select(M.Review).where(M.Review.contract_id == contract.id)).one()
    before = _versions(db)
    assert measured_against(db, first, legal=True)["measured_against"]
    assert _versions(db) == before
    _, review = _version(build, db, contract, CAPPED)
    finding = _cap_finding(db, review)
    assert finding.status is E.FindingStatus.RESOLVED
    [event] = _carried(db, finding)
    assert event.after_state["decision_ids"] == [str(decision.id)]


def _review(db, codes: list[str], analysed_as: str | None):
    """A Review with one point per requirement code, and the analysis run's own record
    of the type it measured the paper as."""
    user = make_user(db)
    contract = M.Contract(owner_id=user.id, name="Paper", status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    version = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="p.pdf",
        mime_type="application/pdf", file_size_bytes=1, file_hash=uuid.uuid4().hex,
        storage_key="k", processing_status=E.ProcessingStatus.COMPLETED,
        extraction_status=E.ExtractionStatus.COMPLETE, uploaded_by=user.id)
    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id)
    db.add_all([version, snap])
    db.flush()
    review = M.Review(contract_id=contract.id, document_version_id=version.id,
                      configuration_snapshot_id=snap.id,
                      status=E.ReviewStatus.ANALYSIS_COMPLETE, created_by=user.id)
    db.add(review)
    db.flush()
    made: dict[str, M.RequirementVersion] = {}
    for code in codes:
        if code not in made:                 # one version per code: its newest
            req = db.scalar(select(M.Requirement).where(M.Requirement.code == code))
            if req is None:
                req = M.Requirement(code=code, status=E.ConfigStatus.ACTIVE)
                db.add(req)
                db.flush()
            newest = db.scalar(select(func.max(M.RequirementVersion.version_number))
                               .where(M.RequirementVersion.requirement_id == req.id)) or 0
            made[code] = M.RequirementVersion(
                requirement_id=req.id, version_number=newest + 1, name="x",
                evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=user.id)
            db.add(made[code])
            db.flush()
        make_finding(db, review, made[code])
    if analysed_as:
        A.record(db, action=A.ANALYSIS_RUN_RECORDED, entity_type="review",
                 entity_id=review.id, actor_id=user.id,
                 after={"document_type": analysed_as})
    db.flush()
    return review


def test_measured_against_groups_applied_standards_by_source(db):
    known = standard_sources()
    review = _review(db, [MSA, MSA2, CONSTITUTION], "MSA")
    assert measured_against(db, review, legal=True) == {"measured_against": sorted([
        {"kind": "CONSTITUTION", "name": known[CONSTITUTION]["name"], "points": 1},
        {"kind": "OUR_MSA", "name": known[MSA]["name"], "points": 2}],
        key=lambda s: (s["kind"], s["name"]))}


def test_sources_and_counts_reach_legal_only(db):
    """D5: a reader without Legal details gets each set's kind only — the name and the
    count keys are omitted, never nulled."""
    review = _review(db, [MSA, MSA2, CONSTITUTION], "OTHER")
    got = measured_against(db, review, legal=False)
    assert got["measured_against"] == [{"kind": "CONSTITUTION"}, {"kind": "OUR_MSA"}]
    assert got["measured_against_note"] == MSA_TERMS_ON_OTHER_PAPER


def test_a_standard_with_no_ratified_file_is_left_out(db):
    assert measured_against(db, _review(db, ["NO-SUCH-STANDARD-001"], "OTHER"), legal=True) == {}
    assert measured_against(db, _review(db, [], "OTHER"), legal=True) == {}
    got = measured_against(db, _review(db, ["NO-SUCH-STANDARD-002", MSA], "MSA"), legal=True)
    assert [s["points"] for s in got["measured_against"]] == [1]


def test_msa_terms_on_an_other_agreement_carry_the_note(db):
    for analysed in ("OTHER", None):
        got = measured_against(db, _review(db, [MSA, CONSTITUTION], analysed), legal=True)
        assert got["measured_against_note"] == MSA_TERMS_ON_OTHER_PAPER


def test_msa_terms_on_an_msa_carry_no_note(db):
    assert "measured_against_note" not in measured_against(
        db, _review(db, [MSA], "MSA"), legal=True)
    assert "measured_against_note" not in measured_against(
        db, _review(db, [CONSTITUTION], "OTHER"), legal=True)


def test_an_older_review_never_takes_todays_source(db):
    """Re-check N1: a point measured by an older version of its standard than the one
    the file now describes is left out — an older Review says nothing rather than take
    today's source (R5.3)."""
    older = _review(db, [MSA, CONSTITUTION], "MSA")
    _review(db, [MSA], "MSA")                 # the MSA standard moves on a version
    got = measured_against(db, older, legal=True)
    assert [s["kind"] for s in got["measured_against"]] == ["CONSTITUTION"]
