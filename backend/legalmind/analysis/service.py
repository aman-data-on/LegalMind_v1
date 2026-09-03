"""Analysis orchestrator — locked 44.2 / 44.40, Steps 28, 30, 34, 35, 36, 44, 45B–45D.

The locked pipeline, joined end to end:

```text
Document Version
     -> clauses            (latest COMPLETED processing run)      34.x
     -> Mapping State      per Requirement, from the SNAPSHOT     28, 35
     -> structured facts   per Requirement, requirement-specific  44.10, 44.11
     -> Evaluation(s)      one per governed scope                 45B, 45C, 45D
     -> Finding            derived summary + scoped Evaluations   AB-1
     -> Review lifecycle   LEGAL_REVIEW or RESOLVED, derived      Step 30
```

**This module decides nothing.** It contains no classification, no threshold, no
rule and no roll-up: each of those lives in the layer that owns it, and the
orchestrator only routes data between them. That is deliberate — locked 44.29 keeps
evaluation semantics in tested code per evaluator, and a coordinator that "helped" by
resolving an ambiguity would be exactly the silent guess `ENG-09` and Step 28 r6
forbid.

Three fail-closed paths are worth naming because they look like errors and are not:

* an **optional** Requirement with no mapped provision produces **no Finding at
  all** (locked `F-1`) — recorded as coverage, not as a gap;
* a Requirement whose configuration cannot be used produces **no Finding** and a
  recorded failure, never a guessed one;
* a document that cannot be read produces `ANALYSIS_FAILED` on the Review, which is
  a *processing* state and is never confused with a Finding of
  `UNABLE_TO_EVALUATE` (Step 30 r13, 34.15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis.unmatched import record_unmatched_provisions
from legalmind.db import models as M
from legalmind.db.lookup import must_exist
from legalmind.domain.document_types import is_document_type
from legalmind.domain.enums import (
    EvaluatorType,
    FindingClassification,
    MappingState,
    ProcessingStatus,
    ReviewStatus,
)
from legalmind.evaluation.contracts import (
    CompanyStandard,
    EvaluatorInput,
    EvidenceRef,
    LegalRule,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.presence import OptionalRequirementAbsent, PresenceMisconfigured
from legalmind.evaluation.registry import evaluate, version_for
from legalmind.evaluation.service import (
    EvidenceCardinalityViolation,
    persist_evaluation,
    requirement_applicability,
)
from legalmind.extraction.liability import (
    LiabilityExtractionConfig,
    extract_liability_facts,
)
from legalmind.mapping.engine import Clause, MappingResult, map_requirement
from legalmind.mapping.rules import MappingMisconfigured, MappingRules
from legalmind.mapping.service import load_clauses
from legalmind.observability import log_event
from legalmind.observability.logs import timed
from legalmind.observability.metrics import (
    classification_signal,
    fail_closed_rate,
    is_operational_failure,
)
from legalmind.security import audit as A
from legalmind.workflow.review_lifecycle import advance_after_analysis, transition


class AnalysisNotPermitted(Exception):
    """The Review is not in a state where analysis may run.

    Not a permission error — the API layer authorizes separately. This is the
    business-rule refusal 43.28 requires: a Review that already has Findings must
    not be silently re-analysed, because that would duplicate legal output.
    """


@dataclass
class RequirementOutcome:
    """What happened for one Requirement. Reported, never interpreted."""

    requirement_code: str
    requirement_version_id: UUID
    mapping_state: str | None = None
    finding_id: UUID | None = None
    classification: str | None = None
    evaluation_count: int = 0
    #: True when locked F-1 suppressed the Finding (optional + no provision).
    skipped_as_optional: bool = False
    failure: str | None = None
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class AnalysisRun:
    review_id: UUID
    review_status: str
    requirements_in_snapshot: int
    #: Declared Document Type of the paper under review (locked Step 6), and how
    #: many of the pinned Requirements apply to it (locked Step 28 scoping).
    #: None / equal-to-snapshot until the scoping stage has run.
    document_type: str | None = None
    requirements_applicable: int = 0
    outcomes: list[RequirementOutcome] = field(default_factory=list)
    #: REC-02 / D-4 (owner, 2026-09-01) — evidence rows this Review's Findings
    #: never cited. A document-level observation, never a Finding classification.
    unmatched_provisions: int = 0

    @property
    def findings_created(self) -> int:
        return sum(1 for o in self.outcomes if o.finding_id is not None)

    @property
    def skipped_as_optional(self) -> int:
        return sum(1 for o in self.outcomes if o.skipped_as_optional)

    @property
    def failures(self) -> list[RequirementOutcome]:
        return [o for o in self.outcomes if o.failure is not None]


# ==========================================================================
# Entry point
# ==========================================================================
def run_analysis(db: DBSession, review: M.Review, *,
                 actor_id: UUID | None = None,
                 request_id: str | None = None) -> AnalysisRun:
    """Analyse one Review against its pinned configuration snapshot.

    Reproducible from the Document Version plus the configuration versions alone
    (Step 28 r15, AUD-04) — nothing is read from *current* configuration, and no
    wall-clock value affects an outcome.
    """
    assert_analysable(db, review)

    _to_processing(db, review, actor_id=actor_id, request_id=request_id)

    # 53.5 — stage durations, to locate bottlenecks across Step 44's layers. The
    # log line carries counts and ids only, never clause text (53.3).
    with timed("analysis.stage.load", request_id=request_id,
               review_id=str(review.id)) as stage:
        clauses = load_clauses(db, review.document_version_id)
        items = _snapshot_items(db, review.configuration_snapshot_id)
        stage["clause_count"] = len(clauses)
        stage["requirement_count"] = len(items)

    run = AnalysisRun(
        review_id=review.id,
        review_status=review.status.value,
        requirements_in_snapshot=len(items),
    )

    def _refuse(reason: str, reason_code: str) -> AnalysisRun:
        """ANALYSIS_FAILED, uniformly — Step 30 r13, 53.4/53.5.

        One shape for every pre-evaluation refusal so the audit record and the
        alertable log line cannot drift apart between failure causes.
        """
        transition(db, review, ReviewStatus.ANALYSIS_FAILED,
                   actor_id=actor_id, request_id=request_id)
        run.review_status = review.status.value
        A.record(db, action=A.ANALYSIS_RUN_FAILED, entity_type="review",
                 entity_id=review.id, actor_id=actor_id, request_id=request_id,
                 after={"reason": reason})
        # 53.5 — ANALYSIS_FAILED is a genuine operational failure and IS alertable,
        # unlike any fail-closed classification. `reason_code` is a code, not
        # user text, so 53.3 permits it.
        log_event("analysis.failed", request_id=request_id,
                  review_id=str(review.id),
                  review_status=run.review_status,
                  reason_code=reason_code,
                  operational_failure=True)
        return run

    if not clauses:
        # 34.9 / Step 30 r13 — a document with no usable text is a PROCESSING
        # failure, not a set of legal conclusions. Nothing is evaluated and no
        # Finding is invented.
        return _refuse("no extracted clauses available", "no_extracted_clauses")

    # ---- Document Type scoping — locked Step 6 + Step 28 ---------------------
    # A Requirement applies only to the kind of paper its standard declares.
    # Undeclared type on the Contract: REFUSE (owner decision Q9 — the type is
    # declared by the uploader, never inferred), because the alternative is
    # evaluating every Requirement against every document, which is precisely
    # the defect this filter exists to close (an NDA flagged for having no
    # liability cap). Untyped standard in the snapshot: REFUSE, because the
    # snapshot predates the publish-time check and neither skipping nor
    # evaluating it can be justified silently (ENG-09).
    document_type = _review_document_type(db, review)
    if document_type is None or not is_document_type(document_type):
        return _refuse("contract declares no valid document type",
                       "document_type_undeclared")
    if untyped := _untyped_items(items):
        return _refuse(
            "snapshot predates document-type validation; untyped standard for: "
            + ", ".join(sorted(untyped)),
            "snapshot_standard_untyped")

    items = _applicable_items(items, document_type)
    # `requirements_in_snapshot` keeps the SNAPSHOT count — the audit record must
    # state what was pinned, not what applied. The applicable count is its own
    # field, so "2 pinned, 1 applicable to an MSA" reads as exactly that.
    run.requirements_applicable = len(items)
    run.document_type = document_type

    with timed("analysis.stage.evaluate", request_id=request_id,
               review_id=str(review.id)) as stage:
        for item in items:
            run.outcomes.append(
                _analyse_requirement(db, review, item, clauses))
        stage["findings_created"] = run.findings_created

    # Step 30 r6 / r16 — the workflow chooses LEGAL_REVIEW or RESOLVED from the
    # DERIVED Finding states. The orchestrator does not decide it.
    advance_after_analysis(db, review, actor_id=actor_id, request_id=request_id)
    run.review_status = review.status.value

    # REC-02 / D-4 (owner, 2026-09-01) — after every Finding and Evaluation of
    # this Review exists, whatever evidence none of them cited is a
    # document-level UNMATCHED_PROVISION observation. Never a Finding, never a
    # classification, never a lifecycle input (rules 1-3 of REC-02 stand).
    run.unmatched_provisions = record_unmatched_provisions(
        db, review, review.document_version_id)

    A.record(db, action=A.ANALYSIS_RUN_RECORDED, entity_type="review",
             entity_id=review.id, actor_id=actor_id, request_id=request_id,
             after={"requirements_in_snapshot": run.requirements_in_snapshot,
                    "document_type": run.document_type,
                    "requirements_applicable": run.requirements_applicable,
                    "findings_created": run.findings_created,
                    "skipped_as_optional": run.skipped_as_optional,
                    "failures": len(run.failures),
                    "review_status": run.review_status,
                    "unmatched_provisions": run.unmatched_provisions})

    _log_signals(run, request_id=request_id)
    return run


def _log_signals(run: AnalysisRun, *, request_id: str | None) -> None:
    """Locked 53.5's signals, and the one rule that matters most about them.

    "Do not alert on `UNABLE_TO_EVALUATE` — it is the system working as locked." So
    the fail-closed rate is reported as its own signal, explicitly flagged as not an
    error rate, and never folded into a failure count. Locked 53.5 names the trap: a
    *falling* fail-closed rate may mean the engine has started guessing.

    Counts and classifications only — no clause text, no thresholds, no rule
    outcomes (53.3).
    """
    from collections import Counter

    counts = Counter(o.classification for o in run.outcomes
                     if o.classification is not None)
    as_enum = {}
    for value, n in counts.items():
        try:
            as_enum[FindingClassification(value)] = n
        except ValueError:                                   # pragma: no cover
            continue

    log_event(
        "analysis.completed",
        request_id=request_id,
        review_id=str(run.review_id),
        review_status=run.review_status,
        requirements_in_snapshot=run.requirements_in_snapshot,
        findings_created=run.findings_created,
        skipped_as_optional=run.skipped_as_optional,
        classification_counts=dict(counts),
        # The honesty metric — reported, never targeted.
        fail_closed_rate=fail_closed_rate(as_enum),
        # Configuration failures, which ARE operational. Kept separate from the
        # fail-closed rate so the two can never be confused (53.4).
        configuration_failures=len(run.failures),
        signals=sorted({classification_signal(c) for c in as_enum}),
        # 53.4 / Step 30 r13 — ANALYSIS_FAILED is a genuine failure; a Finding of
        # UNABLE_TO_EVALUATE is not, and this is the only place that decides.
        operational_failure=is_operational_failure(
            review_status=ReviewStatus(run.review_status)),
    )


# ==========================================================================
# Per-Requirement
# ==========================================================================
@dataclass(frozen=True)
class _SnapshotItem:
    """One pinned Requirement version plus the configuration versions it uses."""

    requirement: M.Requirement
    requirement_version: M.RequirementVersion
    company_standard: M.CompanyStandardVersion
    mapping_rules: M.MappingRuleVersion
    evaluation_rules: M.EvaluationRuleVersion
    legal_rule: M.LegalRuleVersion | None


def _analyse_requirement(db: DBSession, review: M.Review, item: _SnapshotItem,
                         clauses: list[Clause]) -> RequirementOutcome:
    rv = item.requirement_version
    outcome = RequirementOutcome(
        requirement_code=item.requirement.code,
        requirement_version_id=rv.id,
    )

    standard_configuration = item.company_standard.configuration or {}
    required, applicability_note = requirement_applicability(standard_configuration)
    if applicability_note:
        outcome.diagnostics.append(applicability_note)

    # ---- mapping (Steps 28, 35) -----------------------------------------
    try:
        rules = MappingRules.from_config(item.mapping_rules.rules)
    except MappingMisconfigured as exc:
        # D-1 defence in depth: publish already refuses this, so reaching here means
        # a snapshot predates the check. Still a failure, never a guess.
        outcome.failure = f"mapping configuration unusable: {exc}"
        return outcome

    mapping: MappingResult = map_requirement(rv.id, rules, clauses)
    outcome.mapping_state = mapping.state.value

    evidence = tuple(EvidenceRef(evidence_id=eid) for eid in mapping.evidence_ids)

    # ---- evaluator input (45B.11) ---------------------------------------
    requirement = RequirementContext(
        requirement_version_id=rv.id,
        code=item.requirement.code,
        evaluator_type=rv.evaluator_type,
        required=required,
    )
    legal_rule = None
    if item.legal_rule is not None:
        legal_rule = LegalRule(
            version_id=item.legal_rule.id,
            configuration=item.legal_rule.configuration or {},
            # 45B.9 — `rule_configuration` shape is NOT YET SPECIFIED; it is read
            # from where the Legal Rule stores it and never invented here.
            rule_configuration=(item.legal_rule.configuration or {}).get(
                "rule_configuration") or {},
        )

    evaluator_input = EvaluatorInput(
        requirement=requirement,
        company_standard=CompanyStandard(
            version_id=item.company_standard.id,
            configuration=standard_configuration),
        evaluator_version=version_for(rv.evaluator_type),
        evidence=evidence,
        # D-2 — supplied for BOTH evaluator types so the Mapping State is recorded
        # on every Evaluation, not only on presence ones.
        mapping=MappingInput(mapping_state=mapping.state, evidence_refs=evidence),
        facts=_facts_for(rv, standard_configuration, mapping, clauses, outcome),
        legal_rule=legal_rule,
    )

    # ---- evaluate + persist ---------------------------------------------
    try:
        output = evaluate(evaluator_input)
    except OptionalRequirementAbsent:
        # Locked F-1 — nothing was required, nothing was found, nothing is
        # asserted. Coverage, not a gap.
        outcome.skipped_as_optional = True
        return outcome
    except PresenceMisconfigured as exc:
        outcome.failure = f"presence configuration unusable: {exc}"
        return outcome

    try:
        persisted = persist_evaluation(
            db,
            review=review,
            requirement_version_id=rv.id,
            output=output,
            legal_rule_version_id=item.legal_rule.id if item.legal_rule else None,
            evaluation_rule_version_id=item.evaluation_rules.id,
            requirement_required=required,
        )
    except EvidenceCardinalityViolation as exc:
        # N-34 / 45C.25 — refusing is correct: the alternative is fabricating
        # evidence to satisfy a constraint.
        outcome.failure = f"evidence cardinality: {exc}"
        return outcome

    outcome.finding_id = persisted.finding.id
    outcome.classification = persisted.finding.classification.value
    outcome.evaluation_count = len(persisted.evaluations)
    return outcome


def _facts_for(rv: M.RequirementVersion, standard_configuration: dict,
               mapping: MappingResult, clauses: list[Clause],
               outcome: RequirementOutcome):
    """Requirement-specific fact extraction — locked 44.11.

    `PRESENCE` takes no facts at all: presence is established by the mapping layer
    and the evaluator reads no clause text (45D, N-30). Only the numeric evaluator
    consumes facts.

    **Facts are extracted only from a CONFIRMED mapping.** Locked Step 28 r6: "An
    ambiguous or unresolved mapping may produce UNABLE_TO_EVALUATE rather than a
    guessed classification." Extracting from candidates the mapping layer refused to
    choose between would do exactly the choosing Step 28's `AMBIGUOUS` state exists
    to prevent — and would let a genuinely ambiguous provision surface as a clean
    `MATCH`. Supplying no facts instead makes `evaluate_numeric` fail closed to
    `UNABLE_TO_EVALUATE` (45B.7), which is the locked outcome.
    """
    if rv.evaluator_type is not EvaluatorType.NUMERIC_COMPARISON:
        return None

    if mapping.state is not MappingState.CONFIRMED:
        outcome.diagnostics.append(
            f"mapping state {mapping.state.value}: no facts extracted, so the "
            "evaluation fails closed rather than choosing between candidates "
            "(Step 28 r6)")
        return None

    mapped = list(mapping.confirmed_clauses)
    if not mapped:
        return None

    facts = extract_liability_facts(
        mapped, LiabilityExtractionConfig.from_config(standard_configuration))
    # REC-07 — extraction diagnostics travel with the evaluation for auditability.
    # They are diagnostic metadata only and cannot alter a legal finding.
    outcome.diagnostics.extend(facts.extraction_diagnostics)
    return facts


# ==========================================================================
# Preconditions and lifecycle
# ==========================================================================
def assert_analysable(db: DBSession, review: M.Review) -> None:
    """43.28 — a retry must not duplicate Findings.

    `UNIQUE(review_id, requirement_version_id)` would collide anyway, but colliding
    mid-run would leave a partially analysed Review. Refusing up front is cleaner and
    says what happened. Re-analysis of an already-analysed Review is a separate
    concern and is deliberately not implemented.

    Public because the queue dispatcher runs the same check *before* enqueueing
    (`worker.dispatch`): a refusal the caller can see is worth more than a job the
    worker would silently discard. Both paths must refuse on identical grounds, which
    is why there is one function rather than two.
    """
    existing = db.execute(
        select(func.count()).select_from(M.Finding)
        .where(M.Finding.review_id == review.id)
    ).scalar_one()
    if existing:
        raise AnalysisNotPermitted(
            f"this Review already has {existing} Finding(s); re-analysis would "
            "duplicate legal output")

    if review.status in {ReviewStatus.RESOLVED, ReviewStatus.CLOSED,
                         ReviewStatus.CANCELLED}:
        raise AnalysisNotPermitted(
            f"a Review in {review.status.value} cannot be analysed")

    # A document whose processing has not concluded has no evidence to analyse
    # yet (the deferred-OCR path, 2026-09-03). Analysing it now would evaluate
    # over zero rows and mint MISSING findings against text that is still being
    # recovered — refused here so both the inline and the queued path refuse on
    # identical grounds, per this function's contract.
    version = db.get(M.DocumentVersion, review.document_version_id)
    if version is not None and version.processing_status in {
            ProcessingStatus.PENDING, ProcessingStatus.PROCESSING}:
        raise AnalysisNotPermitted(
            "the document is still being processed; analysis can start when "
            "text extraction completes")


def _to_processing(db: DBSession, review: M.Review, *, actor_id: UUID | None,
                   request_id: str | None) -> None:
    """Walk the locked Step 30 path to PROCESSING.

    Every intermediate transition is made explicitly rather than assigning the
    status, so r2's state machine and r17's audit event both apply to each step.
    """
    if review.status is ReviewStatus.DRAFT:
        transition(db, review, ReviewStatus.UPLOADED,
                   actor_id=actor_id, request_id=request_id)
    if review.status is ReviewStatus.UPLOADED:
        transition(db, review, ReviewStatus.PROCESSING,
                   actor_id=actor_id, request_id=request_id)
    if review.status is not ReviewStatus.PROCESSING:
        raise AnalysisNotPermitted(
            f"a Review in {review.status.value} cannot enter PROCESSING")


def _review_document_type(db: DBSession, review: M.Review) -> str | None:
    """The declared Document Type of the paper under review — locked Step 6.

    Resolved Review → DocumentVersion → Contract.contract_type, the field the
    uploader declares (owner decision Q9, 2026-08-19: declared, never inferred
    from content — a wrong guess would silently load the wrong baseline).
    Returns None when undeclared; the caller refuses, it does not default.
    """
    dv = db.get(M.DocumentVersion, review.document_version_id)
    if dv is None:
        return None
    contract = db.get(M.Contract, dv.contract_id)
    return contract.contract_type if contract is not None else None


def _applicable_items(items: list[_SnapshotItem],
                      document_type: str) -> list[_SnapshotItem]:
    """Keep the Requirements whose standard declares this Document Type.

    Locked Step 28's Requirement Model scopes every Requirement to a Document
    Type; per owner decision Q2 (2026-08-19) the value lives in the Company
    Standard configuration, the same JSONB route D-3 used for Required/Optional.

    A plain equality test is sufficient — and safe — because publish refuses any
    standard that omits the type or names one outside Step 6's vocabulary, so an
    untyped item here means a snapshot that predates the check. Fail-closed
    reading (ENG-09): such an item is REFUSED by the caller rather than either
    silently skipped or silently evaluated; skipping could hide a Requirement
    that should have run, evaluating could flag an NDA for having no liability
    cap, and neither mistake should be possible to make quietly.

    Input order (Requirement code) is preserved — ENG-11 determinism.
    """
    return [
        item for item in items
        if (item.company_standard.configuration or {}).get("document_type")
        == document_type
    ]


def _untyped_items(items: list[_SnapshotItem]) -> list[str]:
    """Requirement codes whose pinned standard declares no valid Document Type."""
    return [
        item.requirement.code for item in items
        if not is_document_type(
            (item.company_standard.configuration or {}).get("document_type"))
    ]


def _snapshot_items(db: DBSession, snapshot_id: UUID) -> list[_SnapshotItem]:
    """Load the pinned configuration — locked 42.12, Step 30, AUD-04.

    Read entirely through `configuration_snapshot_items`, never from current
    configuration: that is what makes a historical Review reproducible and what
    keeps a published draft from changing an existing Review (rule 16).

    Ordered by Requirement code so the analysis sequence — and therefore the audit
    trail — is deterministic (`ENG-11`).
    """
    rows = db.execute(
        select(M.ConfigurationSnapshotItem, M.RequirementVersion, M.Requirement)
        .join(M.RequirementVersion,
              M.RequirementVersion.id
              == M.ConfigurationSnapshotItem.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.ConfigurationSnapshotItem.snapshot_id == snapshot_id)
        .order_by(M.Requirement.code)
    ).all()

    items: list[_SnapshotItem] = []
    for snapshot_item, rv, requirement in rows:
        # 42.12 makes all three NOT NULL on a snapshot item, so a missing row here is
        # a corrupt snapshot rather than a Requirement the analysis may skip. Refusing
        # loudly is the fail-closed reading: skipping one would silently produce a
        # Review that analysed fewer Requirements than its snapshot pinned.
        items.append(_SnapshotItem(
            requirement=requirement,
            requirement_version=rv,
            company_standard=must_exist(
                db.get(M.CompanyStandardVersion,
                       snapshot_item.company_standard_version_id),
                "company_standard_version", snapshot_item.requirement_version_id),
            mapping_rules=must_exist(
                db.get(M.MappingRuleVersion,
                       snapshot_item.mapping_rule_version_id),
                "mapping_rule_version", snapshot_item.requirement_version_id),
            evaluation_rules=must_exist(
                db.get(M.EvaluationRuleVersion,
                       snapshot_item.evaluation_rule_version_id),
                "evaluation_rule_version", snapshot_item.requirement_version_id),
            # Genuinely optional — locked Step 20 r4.
            legal_rule=(db.get(M.LegalRuleVersion,
                               snapshot_item.legal_rule_version_id)
                        if snapshot_item.legal_rule_version_id else None),
        ))
    return items

