"""Analysis orchestrator — locked 44.2/44.40, Steps 28, 30, 34, 35, 45B–45D, 43.28.

These are end-to-end tests over the real pipeline: a real DOCX is ingested through
`ingest_document`, a real configuration snapshot is assembled, and `run_analysis`
produces real Findings.

**Every configured value here is STRUCTURAL and carries no legal meaning.** The
phrases, units, thresholds and outcomes exist to exercise the algorithm. None is the
organization's Company Standard, and no assertion in this file is a legal conclusion
(rule 21, Step 45E provenance).
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy import select

from legalmind.analysis.service import AnalysisNotPermitted, run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from tests.conftest import make_user

DOCX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document")

# --------------------------------------------------------------- structural
# Mapping rules that find a liability clause, with an explicitly stated threshold
# (D-1: there is no default).
# NOTE: each DOCX paragraph becomes its own evidence row, so the heading and the
# substantive clause are separate candidates. The rules below match BOTH — a
# configuration that only matched the heading would confirm a clause containing no
# cap, and extraction would correctly find nothing. That is the mapping layer
# working, not a bug, and it is why real rules must target the substantive text.
MAPPING = {
    "exact_phrases": ["limitation of liability", "shall not exceed",
                      "shall not be limited"],
    "keyword_groups": [["liability", "shall not exceed"]],
    "section_heading_terms": ["liability"],
    "confirm_threshold": 5,
}

# Extraction terminology plus a structural Company Standard.
STANDARD = {
    "applicability": "REQUIRED",
    "preferred": 6,
    "unit": "months",
    "basis": "BASIS_FEES",
    "scope_key": "GENERAL",
    "extraction": {
        "cap_phrases": ["shall not exceed"],
        "unlimited_phrases": ["shall not be limited"],
        "units": ["months"],
        "bases": {"BASIS_FEES": ["fees paid"]},
        "exceptions": [
            {"scope": "SCOPE_X", "terms": ["term x"], "scope_label": "Term X"},
        ],
    },
}

# A structural Legal Rule: at most 12 units acceptable, above that needs approval,
# unlimited unacceptable. Illustrative of *shape*, not of any legal position.
LEGAL_RULE = {
    "acceptable_max": 12,
    "approval_required_above": 12,
    "unlimited_outcome": "UNACCEPTABLE",
    "rule_configuration": {
        "scope_required": True,
        "comparable_scopes": ["GENERAL", "SCOPE_X"],
        "comparable_bases": ["BASIS_FEES"],
    },
}

PRESENCE_MAPPING = {
    "exact_phrases": ["governing law"],
    "section_heading_terms": ["governing law"],
    "confirm_threshold": 5,
}


def build_docx(paragraphs: list[str]) -> bytes:
    import docx
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


class Builder:
    """Assembles a Review with a real document and a real snapshot."""

    def __init__(self, db, storage, owner):
        self.db, self.storage, self.owner = db, storage, owner
        self.items: list[M.ConfigurationSnapshotItem] = []
        self.snapshot = M.ConfigurationSnapshot(
            snapshot_hash=uuid.uuid4().hex, created_by=owner.id)
        db.add(self.snapshot); db.flush()

    def requirement(self, code, evaluator_type, *, mapping, standard,
                    legal_rule=None, evaluation_rules=None):
        db = self.db
        # Step 28 scoping: every standard declares its Document Type, which
        # publish enforces in production. The builder mirrors that guarantee so
        # each test states only what it is about; a test exercising the UNTYPED
        # refusal passes `document_type` explicitly (None or an unknown value).
        if "document_type" not in standard:
            standard = {"document_type": "MSA", **standard}
        req = M.Requirement(code=code, status=E.ConfigStatus.ACTIVE)
        db.add(req); db.flush()
        rv = M.RequirementVersion(
            requirement_id=req.id, version_number=1, name=code,
            evaluator_type=evaluator_type, created_by=self.owner.id)
        db.add(rv); db.flush()

        cs = M.CompanyStandardVersion(
            requirement_version_id=rv.id, version_number=1,
            configuration=standard, created_by=self.owner.id)
        mr = M.MappingRuleVersion(
            requirement_version_id=rv.id, version_number=1,
            rules=mapping, created_by=self.owner.id)
        er = M.EvaluationRuleVersion(
            requirement_version_id=rv.id, version_number=1,
            evaluator_type=evaluator_type,
            rules=evaluation_rules or {}, created_by=self.owner.id)
        db.add_all([cs, mr, er]); db.flush()

        lr = None
        if legal_rule is not None:
            lr = M.LegalRuleVersion(
                requirement_version_id=rv.id, version_number=1,
                rule_type=E.RuleType.THRESHOLD, configuration=legal_rule,
                created_by=self.owner.id)
            db.add(lr); db.flush()

        db.add(M.ConfigurationSnapshotItem(
            snapshot_id=self.snapshot.id, requirement_version_id=rv.id,
            company_standard_version_id=cs.id,
            legal_rule_version_id=lr.id if lr else None,
            mapping_rule_version_id=mr.id,
            evaluation_rule_version_id=er.id))
        db.flush()
        return rv

    def review(self, paragraphs):
        db = self.db
        contract = M.Contract(owner_id=self.owner.id, name="Structural MSA",
                              contract_type="MSA",     # declared, per Step 6 / Q9
                              status=E.ContractStatus.ACTIVE)
        db.add(contract); db.flush()
        result = ingest_document(
            db, self.storage, contract_id=contract.id,
            uploaded_by=self.owner.id, data=build_docx(paragraphs),
            filename="msa.docx", declared_mime=DOCX_MIME)
        review = M.Review(
            contract_id=contract.id,
            document_version_id=result.document_version.id,
            configuration_snapshot_id=self.snapshot.id,
            status=E.ReviewStatus.DRAFT, created_by=self.owner.id)
        db.add(review); db.flush()
        return review


@pytest.fixture
def build(db, storage):
    return Builder(db, storage, make_user(db))


# =====================================================================
# The pipeline end to end
# =====================================================================
def test_a_document_produces_findings_with_traceable_evidence(build, db):
    """44.2 / 44.40 — the whole locked pipeline, joined.

    Rule 11 / 45B.3: every Evaluation traces back to the `document_evidence` rows
    the fact came from.
    """
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])

    run = run_analysis(db, review)

    assert run.findings_created == 1
    assert run.failures == []
    outcome = run.outcomes[0]
    assert outcome.mapping_state == "CONFIRMED"

    finding = db.get(M.Finding, outcome.finding_id)
    evaluations = db.execute(
        select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)
    ).scalars().all()
    assert evaluations

    # Evidence survives the evaluator and points at real extracted text.
    links = db.execute(
        select(M.EvaluationEvidence.evidence_id)
        .where(M.EvaluationEvidence.evaluation_id == evaluations[0].id)
    ).scalars().all()
    assert links
    evidence = db.get(M.DocumentEvidence, links[0])
    assert "shall not exceed" in evidence.content.lower()


def test_mapping_state_is_recorded_for_both_evaluator_types(build, db):
    """Owner decision D-2 — `REC-03` calls the three states the canonical
    *persisted* vocabulary, and a replay must be able to show what mapping
    concluded. PRESENCE always did; the numeric side does now."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    build.requirement("GOVERNING-LAW-001", E.EvaluatorType.PRESENCE,
                      mapping=PRESENCE_MAPPING, standard={"applicability": "REQUIRED",
                                "expected_presence": "PRESENT"})
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
        "2. Governing Law",
        "This Agreement is governed by the laws of Ruritania.",
    ])

    run_analysis(db, review)

    evaluations = db.execute(select(M.Evaluation)).scalars().all()
    assert len(evaluations) >= 2
    for evaluation in evaluations:
        facts = (evaluation.result or {}).get("evaluated_facts") or {}
        assert "mapping_state" in facts, evaluation.evaluator_type
        assert facts["mapping_state"] in {"CONFIRMED", "AMBIGUOUS", "UNRESOLVED",
                                         "NONE"}


def test_mapping_state_is_recorded_on_the_fail_closed_paths_too(build, db):
    """D-2 on the paths that matter most.

    The numeric evaluator has four return paths and three are fail-closed. A stamp
    applied per construction site would miss exactly those — and an
    `UNABLE_TO_EVALUATE` whose replay cannot show *why* mapping delivered no facts
    is the least useful record of all.

    Reaches the fail-closed path via **UNRESOLVED** rather than AMBIGUOUS: under
    owner decision M-2 a tie is CONFIRMED, so the only mapping outcome that
    withholds facts is one where nothing reaches the threshold.
    """
    # A high threshold no clause can reach, while still producing a positive signal
    # — which is UNRESOLVED rather than NONE (a signal existed but fell short).
    unreachable = {
        "exact_phrases": ["limitation of liability"],
        "confirm_threshold": 99,
    }
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=unreachable, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Aggregate liability shall not exceed 24 months of fees paid.",
    ])

    run = run_analysis(db, review)
    outcome = run.outcomes[0]
    assert outcome.mapping_state == "UNRESOLVED"
    assert outcome.classification == "UNABLE_TO_EVALUATE"

    evaluation = db.execute(
        select(M.Evaluation)
        .where(M.Evaluation.finding_id == outcome.finding_id)
    ).scalars().one()
    facts = (evaluation.result or {}).get("evaluated_facts") or {}
    assert facts.get("mapping_state") == "UNRESOLVED"
    # Step 28 r6 — UNABLE_TO_EVALUATE rather than a guessed classification, with the
    # reason recorded rather than inferred.
    assert any("Step 28 r6" in d for d in outcome.diagnostics)


# =====================================================================
# M-2 safeguard — supporting clauses vs CONTRADICTORY clauses
#
# Mapping CONFIRMED means "these provisions govern this Requirement". It never
# means they agree, and never means compliance. Contradiction is caught one layer
# down by the locked conflict evaluator (Step 28 r8, 44.18, 45C.2, 45C.22).
# =====================================================================
def _tied_rules():
    """A flat rule set: each clause matches one phrase, so scores tie."""
    return {
        "exact_phrases": ["limitation of liability", "shall not exceed",
                          "shall not be limited"],
        "confirm_threshold": 5,
    }


def test_tied_conflicting_provisions_produce_conflict_not_a_match(build, db):
    """The safeguard, end to end.

    Two clauses tie, both govern the general scope, and they state incompatible
    caps. Mapping cannot tell — it has no facts (Step 28 r8) — so it reports
    CONFIRMED and retains both. The evaluator then finds two materially different
    caps in one scope with no configured precedence and returns **CONFLICT**
    (45C.2, 45C.22). Nothing silently becomes MATCH.
    """
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=_tied_rules(), standard=STANDARD,
                      legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Aggregate liability shall not exceed 6 months of fees paid.",
        "Aggregate liability shall not exceed 24 months of fees paid.",
    ])

    run = run_analysis(db, review)
    outcome = run.outcomes[0]

    # Mapping said CONFIRMED — and that is not a legal statement.
    assert outcome.mapping_state == "CONFIRMED"
    # The Finding is CONFLICT, not MATCH and not DEVIATION.
    assert outcome.classification == "CONFLICT"

    evaluations = db.execute(
        select(M.Evaluation).where(M.Evaluation.finding_id == outcome.finding_id)
    ).scalars().all()
    general = [e for e in evaluations if e.scope_key == "GENERAL"]
    assert len(general) == 1
    assert general[0].classification is E.FindingClassification.CONFLICT
    # 45B.26 — never NULL; a conflict is not an outcome about acceptability.
    assert general[0].rule_outcome is E.RuleOutcome.NOT_APPLICABLE


def test_conflicting_provisions_are_all_retained_as_conflicting_evidence(build, db):
    """45C.2 / 45C.27 — every conflicting provision is retained, none discarded."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=_tied_rules(), standard=STANDARD,
                      legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Aggregate liability shall not exceed 6 months of fees paid.",
        "Aggregate liability shall not exceed 24 months of fees paid.",
    ])

    run = run_analysis(db, review)
    evaluation = db.execute(
        select(M.Evaluation).where(
            M.Evaluation.finding_id == run.outcomes[0].finding_id,
            M.Evaluation.scope_key == "GENERAL")
    ).scalars().one()

    links = db.execute(
        select(M.EvaluationEvidence)
        .where(M.EvaluationEvidence.evaluation_id == evaluation.id)
    ).scalars().all()
    assert len(links) == 2
    assert all(link.relationship_type is E.EvidenceRelationshipType.CONFLICTING
               for link in links)
    # Both figures survive in the record; neither was chosen or dropped.
    caps = (evaluation.actual_value or {}).get("caps") or []
    assert sorted(c["cap_value"] for c in caps) == [6.0, 24.0]


def test_conflict_requires_a_legal_decision(build, db):
    """CONFLICT is Tier 1, so D-3.5(b) requires a decision and Step 30 r6 sends the
    Review to LEGAL_REVIEW. The fail-closed guarantee stated as an outcome."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=_tied_rules(), standard=STANDARD,
                      legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Aggregate liability shall not exceed 6 months of fees paid.",
        "Aggregate liability shall not exceed 24 months of fees paid.",
    ])

    run = run_analysis(db, review)
    finding = db.get(M.Finding, run.outcomes[0].finding_id)
    assert finding.status is E.FindingStatus.DECISION_REQUIRED
    assert run.review_status == E.ReviewStatus.LEGAL_REVIEW.value


def test_no_configured_precedence_never_picks_a_winner(build, db):
    """45C.22 / F-6 — only CONFIGURED precedence may resolve a conflict.

    With no `precedence_rules`, neither cap is adopted: there is no single
    `cap_value` on the evaluation and no `operator`, because no comparison was
    performed. In-document precedence language is never applied.
    """
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=_tied_rules(), standard=STANDARD,
                      legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Aggregate liability shall not exceed 6 months of fees paid.",
        "Notwithstanding the foregoing, aggregate liability shall not exceed "
        "24 months of fees paid.",
    ])

    run = run_analysis(db, review)
    evaluation = db.execute(
        select(M.Evaluation).where(
            M.Evaluation.finding_id == run.outcomes[0].finding_id,
            M.Evaluation.scope_key == "GENERAL")
    ).scalars().one()

    assert evaluation.classification is E.FindingClassification.CONFLICT
    assert "cap_value" not in (evaluation.actual_value or {})
    assert evaluation.operator is None
    assert evaluation.expected_value is None
    assert any("no configured precedence" in d
               for d in (evaluation.result or {}).get("diagnostics", []))


def test_tied_provisions_in_different_scopes_are_not_a_conflict(build, db):
    """A tie alone never implies conflict.

    A general cap and a carve-out tie on score but govern different scopes, so 45C
    evaluates each separately — two Evaluations, no CONFLICT.
    """
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=_tied_rules(), standard=STANDARD,
                      legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Aggregate liability shall not exceed 6 months of fees paid.",
        "Liability for term x shall not be limited.",
    ])

    run = run_analysis(db, review)
    evaluations = db.execute(
        select(M.Evaluation).where(
            M.Evaluation.finding_id == run.outcomes[0].finding_id)
    ).scalars().all()

    assert {e.scope_key for e in evaluations} == {"GENERAL", "SCOPE_X"}
    assert all(e.classification is not E.FindingClassification.CONFLICT
               for e in evaluations)


def test_materially_identical_restatements_are_one_position(build, db):
    """45C.17 — the same cap stated twice is one position, not a conflict.

    Both provisions are still retained as evidence; only the *position* is merged.
    """
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=_tied_rules(), standard=STANDARD,
                      legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Aggregate liability shall not exceed 6 months of fees paid.",
        "Aggregate liability shall not exceed 6 months of fees paid.",
    ])

    run = run_analysis(db, review)
    evaluation = db.execute(
        select(M.Evaluation).where(
            M.Evaluation.finding_id == run.outcomes[0].finding_id,
            M.Evaluation.scope_key == "GENERAL")
    ).scalars().one()

    assert evaluation.classification is not E.FindingClassification.CONFLICT
    links = db.execute(
        select(M.EvaluationEvidence)
        .where(M.EvaluationEvidence.evaluation_id == evaluation.id)
    ).scalars().all()
    assert len(links) == 2          # merged position, both provisions retained


def test_the_general_cap_and_its_carveout_are_evaluated_separately(build, db):
    """44.17 + 45C — the hidden-carve-out case, end to end.

    A conforming general cap and a non-conforming carve-out must produce TWO
    Evaluations under ONE Finding, so the exception cannot be masked by the
    aggregate figure.
    """
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
        "Liability for term x shall not be limited.",
    ])

    run = run_analysis(db, review)
    finding = db.get(M.Finding, run.outcomes[0].finding_id)
    evaluations = db.execute(
        select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)
    ).scalars().all()

    scopes = {e.scope_key for e in evaluations}
    assert scopes == {"GENERAL", "SCOPE_X"}
    exception = next(e for e in evaluations if e.scope_key == "SCOPE_X")
    assert exception.evaluation_kind is E.EvaluationKind.EXCEPTION
    # 45C.4 — the unlimited carve-out applies only to its own scope.
    general = next(e for e in evaluations if e.scope_key == "GENERAL")
    assert general.evaluation_kind is E.EvaluationKind.PRIMARY
    # The Finding summary is a roll-up over both, never the general cap alone.
    assert finding.classification is not E.FindingClassification.MATCH


# =====================================================================
# D-3 — applicability
# =====================================================================
def test_an_optional_requirement_with_no_provision_produces_no_finding(build, db):
    """Locked F-1 — nothing was required, nothing was found, nothing is asserted.

    `MISSING` is excluded by 36.4 ("the Requirement is *expected*") and `MATCH` by
    36.2 ("customer *provision* conforms"), so no Finding is the only correct answer.
    """
    build.requirement("GOVERNING-LAW-001", E.EvaluatorType.PRESENCE,
                      mapping=PRESENCE_MAPPING,
                      standard={"applicability": "OPTIONAL",
                                "expected_presence": "PRESENT"})
    review = build.review(["1. Payment", "Fees are payable within 30 days."])

    run = run_analysis(db, review)

    assert run.findings_created == 0
    assert run.skipped_as_optional == 1
    assert db.execute(select(M.Finding)).first() is None


def test_a_required_requirement_with_no_provision_produces_missing(build, db):
    build.requirement("GOVERNING-LAW-001", E.EvaluatorType.PRESENCE,
                      mapping=PRESENCE_MAPPING,
                      standard={"applicability": "REQUIRED",
                                "expected_presence": "PRESENT"})
    review = build.review(["1. Payment", "Fees are payable within 30 days."])

    run = run_analysis(db, review)
    finding = db.get(M.Finding, run.outcomes[0].finding_id)
    assert finding.classification is E.FindingClassification.MISSING


def test_absent_applicability_fails_closed_to_required(build, db):
    """D-3 — a configuration typo must not silently suppress a Finding, so the
    unstated case produces one for authorized review and says why."""
    build.requirement("GOVERNING-LAW-001", E.EvaluatorType.PRESENCE,
                      mapping=PRESENCE_MAPPING,
                      standard={"expected_presence": "PRESENT"})
    review = build.review(["1. Payment", "Fees are payable within 30 days."])

    run = run_analysis(db, review)
    assert run.findings_created == 1
    assert run.skipped_as_optional == 0
    finding = db.get(M.Finding, run.outcomes[0].finding_id)
    assert finding.classification is E.FindingClassification.MISSING
    assert any("fail closed" in d for d in run.outcomes[0].diagnostics)


# =====================================================================
# Step 30 — lifecycle
# =====================================================================
def test_review_reaches_legal_review_when_a_decision_is_needed(build, db):
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 24 months of fees paid.",   # above the max
    ])

    run = run_analysis(db, review)
    assert run.review_status == E.ReviewStatus.LEGAL_REVIEW.value


def test_review_reaches_resolved_when_nothing_needs_a_decision(build, db):
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",    # within the max
    ])

    run = run_analysis(db, review)
    assert run.review_status == E.ReviewStatus.RESOLVED.value
    # Rule 14 / Step 30 r8 — RESOLVED is a workflow state, never a classification.
    finding = db.get(M.Finding, run.outcomes[0].finding_id)
    assert finding.status is E.FindingStatus.OPEN


def test_an_unreadable_document_is_analysis_failed_not_a_finding(build, db, storage):
    """Step 30 r13 / 34.15 — `ANALYSIS_FAILED` is a processing state and is never
    the same thing as a Finding of `UNABLE_TO_EVALUATE`."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review(["1. Limitation of Liability", "Capped at 6 months."])

    # Remove the extracted evidence, simulating a document that yielded no text.
    db.execute(M.DocumentEvidence.__table__.delete())
    db.flush()

    run = run_analysis(db, review)
    assert run.review_status == E.ReviewStatus.ANALYSIS_FAILED.value
    assert run.findings_created == 0
    assert db.execute(select(M.Finding)).first() is None


def test_every_lifecycle_transition_is_audited(build, db):
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])
    actor = make_user(db)

    run_analysis(db, review, actor_id=actor.id, request_id="analysis-trace-1")

    events = db.execute(
        select(M.AuditEvent).where(M.AuditEvent.entity_id == review.id)
        .order_by(M.AuditEvent.id)
    ).scalars().all()
    actions = [e.action for e in events]
    # Step 30 r17 — every transition, plus the run itself.
    assert actions.count("review.status_changed") >= 3      # UPLOADED, PROCESSING, …
    assert "analysis.run_recorded" in actions
    assert all(e.event_metadata["request_id"] == "analysis-trace-1"
               for e in events if e.event_metadata)


# =====================================================================
# 43.28 — idempotency
# =====================================================================
def test_re_running_analysis_is_refused(build, db):
    """43.28 — a retry must not duplicate Findings. Refusing up front says what
    happened instead of colliding mid-run and leaving a partial Review."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])

    run_analysis(db, review)
    with pytest.raises(AnalysisNotPermitted, match="already has"):
        run_analysis(db, review)

    assert db.execute(
        select(M.Finding).where(M.Finding.review_id == review.id)
    ).scalars().all().__len__() == 1


# =====================================================================
# D-1 defence in depth · D-4 · ENG-11
# =====================================================================
def test_unusable_mapping_configuration_is_a_failure_never_a_finding(build, db):
    """D-1 — publish refuses this, so reaching it means a snapshot predates the
    check. It must still never produce a Finding from an assumed threshold."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping={"exact_phrases": ["limitation of liability"]},
                      standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])

    run = run_analysis(db, review)
    assert run.findings_created == 0
    assert len(run.failures) == 1
    assert "confirm_threshold" in run.failures[0].failure
    assert db.execute(select(M.Finding)).first() is None


def test_no_unmatched_provision_rows_are_written(build, db):
    """Owner decision D-4 — `REC-02` defers the persistence and surfacing of
    `UNMATCHED_PROVISION`, so the orchestrator writes none."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
        "2. Payment",                        # matches no Requirement
        "Fees are payable within 30 days.",
    ])

    run_analysis(db, review)
    assert db.execute(select(M.UnmatchedProvision)).first() is None


def test_analysis_is_deterministic_across_reviews(build, db):
    """ENG-11 / rule 9 — same document + same snapshot => same result.

    Run against two separate Reviews of the same document version and snapshot,
    since re-running one is refused by 43.28.
    """
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    first = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 24 months of fees paid.",
        "Liability for term x shall not be limited.",
    ])
    second = M.Review(
        contract_id=first.contract_id,
        document_version_id=first.document_version_id,
        configuration_snapshot_id=first.configuration_snapshot_id,
        status=E.ReviewStatus.DRAFT, created_by=first.created_by)
    db.add(second); db.flush()

    run_one = run_analysis(db, first)
    run_two = run_analysis(db, second)

    def shape(run):
        findings = db.execute(
            select(M.Finding).where(M.Finding.review_id == run.review_id)
        ).scalars().all()
        out = []
        for finding in sorted(findings, key=lambda f: str(f.requirement_version_id)):
            evaluations = db.execute(
                select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)
                .order_by(M.Evaluation.scope_key)
            ).scalars().all()
            out.append((finding.classification,
                        tuple((e.scope_key, e.classification, e.rule_outcome)
                              for e in evaluations)))
        return out

    assert shape(run_one) == shape(run_two)
    assert run_one.review_status == run_two.review_status


# =====================================================================
# The API surface — locked 49.3 (interpretation), 49.8, 49.10, 47.7
# =====================================================================
def _api_case(api, db, storage):
    """A signed-in owner with an analysable Review, reachable over HTTP."""
    from tests.conftest import grant_role, sign_in

    owner = make_user(db)
    grant_role(db, owner, "USER")
    builder = Builder(db, storage, owner)
    builder.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                        mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = builder.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 24 months of fees paid.",
    ])
    sign_in(api, db, owner)
    return owner, review


def test_analyze_endpoint_runs_the_pipeline(api, db, storage, seeded):
    _, review = _api_case(api, db, storage)

    response = api.post(f"/api/v1/reviews/{review.id}/analyze")
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["findings_created"] == 1
    # Step 30 / 52.7 — lifecycle status is the single source of progress. There is
    # no separate job state that could disagree with it.
    assert body["review_status"] == "LEGAL_REVIEW"
    assert body["requirements"][0]["mapping_state"] == "CONFIRMED"
    assert body["requirements"][0]["failure"] is None


def test_analyze_is_idempotent_rather_than_duplicating(api, db, storage, seeded):
    """49.8 — "a repeat with the same key returns the original result rather than
    re-running". A duplicate is not an error; duplicated legal output would be."""
    _, review = _api_case(api, db, storage)

    first = api.post(f"/api/v1/reviews/{review.id}/analyze",
                     headers={"Idempotency-Key": "run-1"})
    second = api.post(f"/api/v1/reviews/{review.id}/analyze",
                      headers={"Idempotency-Key": "run-1"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["data"]["already_analysed"] is True
    assert db.execute(
        select(M.Finding).where(M.Finding.review_id == review.id)
    ).scalars().all().__len__() == 1


def test_analyze_requires_the_permission(api, db, storage, seeded):
    """The permission mapping is an interpretation (49.3 has no analysis row), but
    it is still enforced server-side rather than merely declared."""
    from tests.conftest import bespoke_role, grant, sign_in

    _, review = _api_case(api, db, storage)
    narrow = make_user(db)
    grant(db, narrow, bespoke_role(db, "VIEW_ONLY_REVIEWS", ["review.view"]))
    # Visible via ownership transfer of the Review to this user, so the refusal is a
    # 403 about the operation rather than a 404 about the object (47.7).
    review.created_by = narrow.id
    db.flush()
    sign_in(api, db, narrow)

    assert api.post(f"/api/v1/reviews/{review.id}/analyze").status_code == 403


def test_analyze_on_someone_elses_review_is_404(api, db, storage, seeded):
    """41.24 / 47.7 — existence is not disclosed."""
    from tests.conftest import grant_role, sign_in

    _, review = _api_case(api, db, storage)
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    sign_in(api, db, stranger)

    assert api.post(f"/api/v1/reviews/{review.id}/analyze").status_code == 404


def test_analyze_is_rate_limited(api, db, storage, seeded):
    """49.10 — rate limiting applies to analysis submission. The limit is deployment
    configuration, so the test drives the configured value."""
    from legalmind.api import ratelimit

    _, review = _api_case(api, db, storage)
    for _ in range(ratelimit.ANALYSIS.max_requests):
        api.post(f"/api/v1/reviews/{review.id}/analyze")

    limited = api.post(f"/api/v1/reviews/{review.id}/analyze")
    assert limited.status_code == 429
    # 49.10 — no detail about the limit's shape.
    assert "Retry-After" not in limited.headers


# =====================================================================
# Document Type scoping — locked Step 6 + Step 28, owner Q3=B/Q9 (2026-08-19)
# =====================================================================
def test_an_nda_is_never_measured_against_an_msa_requirement(build, db):
    """THE headline fix. A Requirement applies only to the kind of paper its
    standard declares (Step 28's Requirement Model), so an NDA produces **no
    liability Finding at all** — not MISSING, not a Legal Decision.

    Before this filter existed, exactly this scenario produced
    `MISSING liability cap → DECISION_REQUIRED` against a real NDA, which is
    technically defensible and practically misleading: an NDA normally has no
    liability cap, and the organization's own NDA has none either.
    """
    build.requirement("LIABILITY-MSA-STRUCT", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Confidential Information",
        "Each party shall hold Confidential Information in strict confidence.",
    ])
    # The uploader declared this paper an NDA.
    contract = db.get(M.Contract, review.contract_id)
    contract.contract_type = "NDA"
    db.flush()

    run = run_analysis(db, review)

    assert run.document_type == "NDA"
    assert run.requirements_in_snapshot == 1      # pinned — honestly reported
    assert run.requirements_applicable == 0       # none applies to an NDA
    assert run.findings_created == 0
    assert run.failures == []
    assert db.execute(select(M.Finding)).first() is None
    # No Finding means nothing to review: the lifecycle resolves rather than
    # parking the Review in front of Legal with nothing to decide.
    assert run.review_status != "ANALYSIS_FAILED"


def test_a_matching_document_type_still_produces_the_finding(build, db):
    """The other half: scoping must not suppress a Requirement that applies."""
    build.requirement("LIABILITY-MSA-STRUCT", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])
    run = run_analysis(db, review)   # builder declares MSA on the contract

    assert run.document_type == "MSA"
    assert run.requirements_applicable == 1
    assert run.findings_created == 1


def test_an_undeclared_document_type_refuses_rather_than_evaluating(build, db):
    """Owner Q9 — the type is declared by the uploader, never inferred, and its
    absence is a refusal (ENG-09): the alternative is evaluating every
    Requirement against every document, which is the defect the filter closes.
    """
    build.requirement("LIABILITY-MSA-STRUCT", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])
    contract = db.get(M.Contract, review.contract_id)
    contract.contract_type = None
    db.flush()

    run = run_analysis(db, review)

    assert run.review_status == "ANALYSIS_FAILED"
    assert run.findings_created == 0
    assert db.execute(select(M.Finding)).first() is None


def test_a_snapshot_with_an_untyped_standard_refuses(build, db):
    """A snapshot that predates the publish-time check must refuse, not guess.

    Neither silently skipping the untyped Requirement (could hide one that
    should have run) nor evaluating it (could flag an NDA for a missing cap) is
    acceptable; both would be quiet. The refusal names the Requirement.
    """
    build.requirement("UNTYPED-STRUCT", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING,
                      standard={**STANDARD, "document_type": None},
                      legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])
    run = run_analysis(db, review)

    assert run.review_status == "ANALYSIS_FAILED"
    assert run.findings_created == 0


def test_scoping_preserves_requirement_code_order(build, db):
    """ENG-11 — the filter must not disturb the deterministic analysis order."""
    for code in ("A-STRUCT", "C-STRUCT", "B-STRUCT"):
        build.requirement(code, E.EvaluatorType.NUMERIC_COMPARISON,
                          mapping=MAPPING, standard=STANDARD,
                          legal_rule=LEGAL_RULE)
    review = build.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 6 months of fees paid.",
    ])
    run = run_analysis(db, review)
    codes = [o.requirement_code for o in run.outcomes]
    assert codes == sorted(codes)
