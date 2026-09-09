"""Clause-level version comparison — locked 33.15, 33.16, PROD-04, Step 33 r18/r19.

Locked 33.15 asks for deterministic section comparison and rules it out of the
AI lane explicitly ("This is **not LLM/RAG**"). PROD-04 gives an ordinary User
`compare`. The line these tests defend is 33.16 / r19: a comparison MAY say
"clause 17.2 changed: Unlimited -> 12 months" and may never become, or imply, a
Legal Decision.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from legalmind.analysis.version_comparison import (
    ComparisonNotPossible,
    compare_versions,
)
from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.conftest import grant_role, make_user, sign_in

V1 = "/api/v1"


def _version(db, contract, number: int, clauses: list[tuple[str | None, str, str]]):
    """A version whose evidence is `(section_number, title, content)` rows."""
    version = M.DocumentVersion(
        contract_id=contract.id, version_number=number,
        original_filename=f"v{number}.pdf", mime_type="application/pdf",
        file_size_bytes=10, file_hash=f"h{number}" * 10, storage_key=f"k{number}",
        processing_status=E.ProcessingStatus.COMPLETED,
        extraction_status=E.ExtractionStatus.COMPLETE,
        uploaded_by=contract.owner_id)
    db.add(version)
    db.flush()
    run = M.DocumentProcessingRun(
        document_version_id=version.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED, processor_version="test")
    db.add(run)
    db.flush()
    for index, (section, title, content) in enumerate(clauses):
        db.add(M.DocumentEvidence(
            document_version_id=version.id, processing_run_id=run.id,
            page_number=1, section_number=section, section_title=title,
            content=content, source_type=E.EvidenceSourceType.NATIVE_TEXT,
            start_offset=index * 100, end_offset=index * 100 + len(content)))
    db.flush()
    return version


@pytest.fixture
def contract(db):
    owner = make_user(db)
    c = M.Contract(owner_id=owner.id, name="Negotiated MSA",
                   contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    return c


def test_it_reports_the_four_states_locked_33_15_asks_for(db, contract):
    """33.15's worked example, exactly: a clause whose text moved from one
    position to another, reported as CHANGED with both sides quoted."""
    v1 = _version(db, contract, 1, [
        ("1", "Definitions", "Capitalized terms have the meanings given."),
        ("17.2", "Limitation of Liability", "Liability shall be unlimited."),
        ("20", "Governing Law", "This Agreement is governed by Indian law."),
    ])
    v2 = _version(db, contract, 2, [
        ("1", "Definitions", "Capitalized terms have the meanings given."),
        ("17.2", "Limitation of Liability",
         "Liability shall not exceed 12 months of fees."),
        ("21", "Notices", "Notices shall be sent to the addresses below."),
    ])

    result = compare_versions(db, v1, v2)

    assert result["summary"] == {"ADDED": 1, "REMOVED": 1, "CHANGED": 1, "UNCHANGED": 1}
    by_section = {c["section_number"]: c for c in result["clauses"]}
    assert by_section["1"]["status"] == "UNCHANGED"
    assert by_section["17.2"]["status"] == "CHANGED"
    assert "unlimited" in by_section["17.2"]["before"]["excerpt"].lower()
    assert "12 months" in by_section["17.2"]["after"]["excerpt"]
    assert by_section["21"]["status"] == "ADDED" and by_section["21"]["before"] is None
    assert by_section["20"]["status"] == "REMOVED" and by_section["20"]["after"] is None


def test_reflowed_whitespace_is_not_a_change(db, contract):
    """A re-exported document rewraps paragraphs; that is not an amendment, and
    reporting it as one would bury the real changes in noise."""
    v1 = _version(db, contract, 1, [("5", "Term", "This Agreement runs for\n  twelve   months.")])
    v2 = _version(db, contract, 2, [("5", "Term", "This Agreement runs for twelve months.")])

    result = compare_versions(db, v1, v2)
    assert result["summary"]["CHANGED"] == 0
    assert result["summary"]["UNCHANGED"] == 1


def test_case_and_wording_changes_are_never_folded_away(db, contract):
    """The opposite guard. Only whitespace is normalized: case and punctuation
    are what a reader is comparing, so folding them would hide a real edit."""
    v1 = _version(db, contract, 1, [("9", "Indemnity", "The Supplier shall indemnify the Customer.")])
    v2 = _version(db, contract, 2, [("9", "Indemnity", "The Customer shall indemnify the Supplier.")])

    assert compare_versions(db, v1, v2)["summary"]["CHANGED"] == 1


def test_clauses_are_ordered_the_way_the_document_numbers_them(db, contract):
    """2 before 10, and 2.2 before 2.10 — a lexical sort would put clause 10
    between 1 and 2 and make the comparison unreadable."""
    rows = [("2", "B", "b"), ("10", "J", "j"), ("2.10", "BJ", "bj"), ("2.2", "BB", "bb")]
    v1 = _version(db, contract, 1, rows)
    v2 = _version(db, contract, 2, rows)

    order = [c["section_number"] for c in compare_versions(db, v1, v2)["clauses"]]
    assert order == ["2", "2.2", "2.10", "10"]


def test_unnumbered_text_is_counted_never_paired_by_guesswork(db, contract):
    """A recital or signature block has no number to match on. Exact text pairs
    stay quiet; the rest is COUNTED, because inventing a pairing would put two
    unrelated passages side by side under a heading that says "changed"."""
    v1 = _version(db, contract, 1, [
        (None, None, "WHEREAS the parties wish to record their agreement."),
        (None, None, "Signed for and on behalf of the Supplier."),
    ])
    v2 = _version(db, contract, 2, [
        (None, None, "WHEREAS the parties wish to record their agreement."),
        (None, None, "Signed in two counterparts by authorized signatories."),
    ])

    result = compare_versions(db, v1, v2)
    assert result["unnumbered"] == {"unchanged": 1, "added": 1, "removed": 1}
    assert result["clauses"] == [], "nothing unnumbered is reported as a clause"
    assert result["matched_on"] == "section_number"


def test_it_reports_existing_findings_and_produces_none_locked_33_16(
        db, contract, requirement_version):
    """The 33.16 boundary, which is the whole point of the module.

    A changed clause that the engine already has a Finding on shows that Finding
    beside it — the reader should see that the engine has something to say there.
    But the comparison creates NOTHING: no Finding, no Classification, no Rule
    Outcome, and no field anywhere in the payload that could read as a verdict on
    the change itself (Step 33 r19: comparison is not a Legal Decision).
    """
    from tests.test_api_authz import make_evaluation, make_finding

    v1 = _version(db, contract, 1, [("17.2", "Liability", "Liability shall be unlimited.")])
    v2 = _version(db, contract, 2, [("17.2", "Liability", "Liability shall not exceed 12 months.")])
    import uuid as _uuid
    snapshot = M.ConfigurationSnapshot(snapshot_hash=_uuid.uuid4().hex,
                                       created_by=contract.owner_id)
    db.add(snapshot)
    db.flush()
    review = M.Review(contract_id=contract.id, document_version_id=v2.id,
                      configuration_snapshot_id=snapshot.id,
                      status=E.ReviewStatus.LEGAL_REVIEW, created_by=contract.owner_id)
    db.add(review)
    db.flush()
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding)
    evidence = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == v2.id)).scalars().one()
    db.add(M.EvaluationEvidence(evaluation_id=evaluation.id, evidence_id=evidence.id,
                                relationship_type=E.EvidenceRelationshipType.PRIMARY))
    db.flush()

    findings_before = db.execute(select(M.Finding)).scalars().all()
    result = compare_versions(db, v1, v2)
    findings_after = db.execute(select(M.Finding)).scalars().all()

    assert len(findings_after) == len(findings_before), "comparison writes no Finding"
    clause = result["clauses"][0]
    assert clause["status"] == "CHANGED"
    assert clause["findings"] and clause["findings"][0]["finding_id"] == str(finding.id)
    # The classification is QUOTED from the engine, never invented here.
    assert clause["findings"][0]["classification"] == finding.classification.value
    # And nothing in the payload passes judgment on the CHANGE itself.
    for forbidden in ("rule_outcome", "acceptable", "approved", "verdict", "decision"):
        assert forbidden not in str(result).lower().replace("decision_", "")


def test_two_versions_of_different_contracts_are_refused(db, contract):
    """Not an empty diff — a caller error. Silently answering "no changes" for
    two unrelated documents would be the most misleading reply available."""
    other_owner = make_user(db)
    other = M.Contract(owner_id=other_owner.id, name="Someone else's",
                       contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(other)
    db.flush()
    mine = _version(db, contract, 1, [("1", "A", "a")])
    theirs = _version(db, other, 1, [("1", "A", "a")])

    with pytest.raises(ComparisonNotPossible, match="different contracts"):
        compare_versions(db, mine, theirs)
    with pytest.raises(ComparisonNotPossible, match="itself"):
        compare_versions(db, mine, mine)


def test_an_unreadable_version_is_refused_rather_than_reported_as_empty(db, contract):
    """A document with no extracted text (34.9's refusal, or one still being
    OCR'd) has nothing to compare. Saying so beats reporting every clause of the
    other version as REMOVED, which is what an empty side would produce."""
    readable = _version(db, contract, 1, [("1", "A", "The parties agree as follows.")])
    empty = _version(db, contract, 2, [])

    with pytest.raises(ComparisonNotPossible, match="no extracted text"):
        compare_versions(db, readable, empty)


def test_the_endpoint_is_available_to_an_ordinary_user_and_scoped(
        api, db, seeded, user):
    """PROD-04 — an ordinary User may compare. And 47.6/SEC-07 still hold: a
    version of a contract the caller cannot see is a 404, not a diff."""
    grant_role(db, user, "USER")
    sign_in(api, db, user)
    mine = M.Contract(owner_id=user.id, name="Mine", contract_type="MSA",
                      status=E.ContractStatus.ACTIVE)
    db.add(mine)
    db.flush()
    v1 = _version(db, mine, 1, [("17.2", "Liability", "Unlimited liability.")])
    v2 = _version(db, mine, 2, [("17.2", "Liability", "Liability capped at 12 months.")])

    ok = api.get(f"{V1}/contracts/{mine.id}/version-comparison",
                 params={"before": str(v1.id), "after": str(v2.id)})
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["summary"]["CHANGED"] == 1
    assert body["before"]["version_number"] == 1 and body["after"]["version_number"] == 2

    # Someone else's contract: 404, and identical to a nonexistent one.
    stranger = make_user(db)
    theirs = M.Contract(owner_id=stranger.id, name="Theirs", contract_type="MSA",
                        status=E.ContractStatus.ACTIVE)
    db.add(theirs)
    db.flush()
    tv1 = _version(db, theirs, 1, [("1", "A", "a")])
    tv2 = _version(db, theirs, 2, [("1", "A", "b")])
    assert api.get(f"{V1}/contracts/{theirs.id}/version-comparison",
                   params={"before": str(tv1.id), "after": str(tv2.id)}
                   ).status_code == 404
    # And a version from ANOTHER contract cannot be smuggled in as one side.
    assert api.get(f"{V1}/contracts/{mine.id}/version-comparison",
                   params={"before": str(v1.id), "after": str(tv2.id)}
                   ).status_code == 404


def test_a_late_change_is_shown_rather_than_truncated_away(db, contract):
    """The excerpt is centred on the divergence, not taken from the top.

    The defect this pins: a clause whose wording differs 900 characters in used
    to render as two identical-looking excerpts under a heading that says
    "wording changed". That is worse than showing nothing — it invites the
    reader to conclude the difference is cosmetic. The window must contain the
    change, and must admit that it cut text off the front.
    """
    lead = "The parties acknowledge and agree that " * 25   # ~975 characters
    v1 = _version(db, contract, 1, [("17.2", "Liability", lead + "six (6) months of fees.")])
    v2 = _version(db, contract, 2, [("17.2", "Liability", lead + "twelve (12) months of fees.")])

    clause = compare_versions(db, v1, v2)["clauses"][0]
    assert clause["status"] == "CHANGED"
    assert "six (6) months" in clause["before"]["excerpt"]
    assert "twelve (12) months" in clause["after"]["excerpt"]
    # And it says so, rather than presenting a mid-clause window as the clause.
    assert clause["before"]["truncated_start"] is True
    assert clause["after"]["truncated_start"] is True


def test_a_short_clause_still_reads_from_its_beginning(db, contract):
    """The window only moves when it has to. A clause that fits is shown whole,
    from its first word, and claims no truncation at either end."""
    v1 = _version(db, contract, 1, [("3", "Term", "Twelve months from the Effective Date.")])
    v2 = _version(db, contract, 2, [("3", "Term", "Twenty-four months from the Effective Date.")])

    clause = compare_versions(db, v1, v2)["clauses"][0]
    assert clause["after"]["excerpt"].startswith("Twenty-four months")
    assert clause["after"]["truncated_start"] is False
    assert clause["after"]["truncated_end"] is False


def test_a_source_that_differs_between_versions_does_not_touch_the_comparison(db, contract):
    """Declared source lives in `document_versions.metadata` (2026-09-06) and is
    version-level precisely because it can change: v1 our template, v2 the
    counterparty's redline. The comparison keys on `section_number` alone, so
    that change must be invisible here — identical clauses stay UNCHANGED and
    the response carries no source, counterparty or date."""
    clauses = [("1", "Definitions", "Capitalized terms have the meanings given."),
               ("17.2", "Limitation of Liability", "Liability shall be unlimited.")]
    v1 = _version(db, contract, 1, clauses)
    v2 = _version(db, contract, 2, clauses)
    v1.doc_metadata = {"source": "ORGANIZATION"}
    v2.doc_metadata = {"source": "COUNTERPARTY", "counterparty": "Placeholder Ltd",
                       "effective_date": "2026-07-28"}
    db.flush()

    result = compare_versions(db, v1, v2)

    assert result["summary"] == {"ADDED": 0, "REMOVED": 0, "CHANGED": 0, "UNCHANGED": 2}
    assert not any(key in str(result) for key in ("ORGANIZATION", "COUNTERPARTY",
                                                  "Placeholder", "effective_date"))


def test_each_side_of_a_comparison_is_one_runs_reading(db, contract):
    """P-8 (2026-09-06): a second COMPLETED run on a version replaces its reading
    for the comparison — the old rows are history, not a second set of clauses."""
    from datetime import UTC, datetime, timedelta

    same = [("1", "Definitions", "Capitalized terms have the meanings given.")]
    v1 = _version(db, contract, 1, same)
    v2 = _version(db, contract, 2, same)
    rerun = M.DocumentProcessingRun(
        document_version_id=v2.id, run_type=E.ProcessingRunType.REPROCESS,
        status=E.ProcessingRunStatus.COMPLETED, processor_version="test",
        started_at=datetime.now(UTC) + timedelta(minutes=5))
    db.add(rerun); db.flush()
    db.add(M.DocumentEvidence(
        document_version_id=v2.id, processing_run_id=rerun.id, page_number=1,
        section_number="1", section_title="Definitions",
        content="Capitalized terms have the meanings set out in Schedule 1.",
        source_type=E.EvidenceSourceType.NATIVE_TEXT, start_offset=0, end_offset=60))
    db.flush()

    result = compare_versions(db, v1, v2)

    assert result["summary"] == {"ADDED": 0, "REMOVED": 0, "CHANGED": 1, "UNCHANGED": 0}
    assert "Schedule 1" in result["clauses"][0]["after"]["excerpt"]
