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

from dataclasses import dataclass, field, replace
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
from legalmind.mapping.scoring import score_clause
from legalmind.analysis import semantic
from legalmind.assist import generation
from legalmind.extraction.liability import ABSENT, UNKNOWN, prune_absent
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
    #: AM-51 — the Step 6 families the document showed it belongs to (declared
    #: type plus every type at least two of whose standards mapped CONFIRMED).
    detected_types: list[str] = field(default_factory=list)
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

    if _structure_not_extracted(clauses):
        # Owner decision 2026-09-05: structurally-failed extraction BLOCKS
        # analysis rather than warning. The sibling of the 34.9 refusal above,
        # and of the 2026-09-03 incident where a document whose text was
        # unreadable still produced three MATCH findings: there, characters
        # arrived but were not language; here, text arrives but is not
        # SEGMENTED, so a "clause" is a whole page. Evaluating that yields
        # findings whose evidence is a page and whose citations cannot point at
        # a provision — a legal conclusion drawn from a unit nobody can check.
        return _refuse("document structure could not be extracted — no clause "
                       "numbering, no headings and no paragraph breaks were "
                       "recovered; re-upload in a format that preserves structure",
                       "structure_not_extracted")

    # ---- Applicability by CONTENT — AM-51 (owner, 2026-09-09) -----------------
    # The document decides what applies: every pinned Requirement is MAPPED
    # first (deterministic, Steps 28/35), and a Requirement applies when the
    # document actually contains its clause (mapping CONFIRMED) or when it
    # belongs to a family the document is evidently a member of — the declared
    # type, if any, or a Step 6 type at least two of whose standards the
    # document confirms. Only a family's standards may be MISSING: absence is
    # asserted only where the document has shown it belongs to that family.
    # The declared type is one optional signal, never a gate; a document with no
    # type — or one that spans several families — is analysed across all of
    # them. An untyped standard in the snapshot still refuses (ENG-09).
    document_type = _review_document_type(db, review)
    if document_type is not None and not is_document_type(document_type):
        document_type = None
    if untyped := _untyped_items(items):
        return _refuse(
            "snapshot predates document-type validation; untyped standard for: "
            + ", ".join(sorted(untyped)),
            "snapshot_standard_untyped")

    # ---- Grounded semantic recognition — AM-54 (owner, 2026-09-09) --------------
    # One embedding pass over the clauses and the requirements' approved wording;
    # the generative model is consulted only where configured terminology
    # confirmed nothing, through the single egress seam, with every call hashed
    # into the audit trail (AM-30 t5). Absent model → lexical only, recorded.
    index = semantic.build_index(clauses, {
        item.requirement_version.id: semantic.anchor_text(
            item.requirement_version.description, item.mapping_rules.rules)
        for item in items})
    egress = _egress_for(db, review, actor_id=actor_id, request_id=request_id)
    if index is None:
        log_event("analysis.semantic.unavailable", request_id=request_id,
                  review_id=str(review.id))

    mappings = {item.requirement.code: _map_item(item, clauses, index, egress,
                                                 declared_type=document_type)
                for item in items}
    items, families = applicable_by_content(items, mappings, document_type)
    # `requirements_in_snapshot` keeps the SNAPSHOT count — the audit record must
    # state what was pinned, not what applied.
    run.requirements_applicable = len(items)
    run.document_type = document_type
    run.detected_types = sorted(families)

    with timed("analysis.stage.evaluate", request_id=request_id,
               review_id=str(review.id)) as stage:
        for item in items:
            run.outcomes.append(
                _analyse_requirement(db, review, item, clauses,
                                     mapping=mappings[item.requirement.code],
                                     egress=egress))
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
                    "detected_types": run.detected_types,
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


def _egress_for(db: DBSession, review: M.Review, *, actor_id: UUID | None,
                request_id: str | None) -> semantic.Egress:
    """The analysis run's one door to the generative model: the single seam
    (AM-30 t1), the environment gate, and a hash-only audit row per call."""
    from legalmind import config

    def egress(prompt: str, prompt_version: str):
        try:
            result = generation.generate_raw(
                prompt, prompt_version=prompt_version,
                environment=config.environment(), request_id=request_id,
                max_output_tokens=400)
        except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
            log_event("analysis.semantic.no_model", request_id=request_id,
                      review_id=str(review.id), cause=type(exc).__name__)
            return None
        A.record(db, action=A.ASSIST_GENERATION_CALLED, entity_type="review",
                 entity_id=review.id, actor_id=actor_id, request_id=request_id,
                 after={"purpose": prompt_version, "model": result.model,
                        "payload_sha256": result.payload_sha256})
        return result
    return egress


def _map_item(item: _SnapshotItem, clauses: list[Clause],
              index: semantic.SemanticIndex | None = None,
              egress: semantic.Egress | None = None,
              declared_type: str | None = None) -> MappingResult | str:
    """Map one Requirement (Steps 28, 35), or return the misconfiguration message.

    D-1 defence in depth: publish already refuses unusable rules, so a message
    here means a snapshot predates the check — still a failure, never a guess.

    AM-54: when configured terminology confirms nothing, the semantic stage
    shortlists the clauses closest in meaning to the approved wording and has
    each adjudicated on a verbatim span. Its signals then go through the SAME
    threshold as a configured phrase. Lexical confirmation is never widened
    semantically — the stage only speaks where the words were silent — and it
    speaks only INSIDE the document's declared family: that is where an absent
    clause would otherwise be asserted MISSING (the false-MISSING this exists to
    prevent), and live R&D showed every cross-family semantic confirmation to
    be a topically adjacent clause of a different family (a confidentiality
    return clause read as data export). Applicability across families stays
    lexical (AM-51).
    """
    try:
        rules = MappingRules.from_config(item.mapping_rules.rules)
    except MappingMisconfigured as exc:
        return f"mapping configuration unusable: {exc}"
    lexical = map_requirement(item.requirement_version.id, rules, clauses)
    if (index is None or egress is None or lexical.state is MappingState.CONFIRMED
            or declared_type is None or _standard_type(item) != declared_type):
        return lexical
    # 35.5 still vetoes: a clause carrying a configured negative pattern (a
    # negative lexical score) is never offered for semantic confirmation.
    shortlist = [(c, sim) for c, sim in index.shortlist(item.requirement_version.id, clauses)
                 if score_clause(rules, content=c.content, section_title=c.section_title).score >= 0]
    if not shortlist:
        return lexical
    terms = ", ".join([*rules.aliases, *rules.exact_phrases, *rules.section_heading_terms])
    signals, diagnostics = semantic.adjudicate(
        item.requirement_version.description or "", terms, shortlist,
        rules.confirm_threshold, egress)
    result = map_requirement(item.requirement_version.id, rules, clauses,
                             extra_signals=signals)
    return replace(result, explanation=result.explanation + tuple(diagnostics))


def _standard_type(item: _SnapshotItem) -> str | None:
    return (item.company_standard.configuration or {}).get("document_type")


def applicable_by_content(items: list[_SnapshotItem],
                          mappings: dict[str, MappingResult | str],
                          declared_type: str | None,
                          ) -> tuple[list[_SnapshotItem], set[str]]:
    """Which pinned Requirements this document is measured against — AM-51
    (r2 corrected same-day, 2026-09-09, after live verification before
    deployment — see the AM-51 correction appended to all_lock.md).

    A family (Step 6 type) is DETECTED only when it is the DECLARED type — the
    one fact a human or a confident suggestion actually asserted about this
    document (AM-50). An earlier draft of this rule also detected a family from
    ANY two of its standards mapping CONFIRMED; live testing on a real mixed
    document showed that fails exactly the guarantee this record exists to
    keep: boilerplate clauses common to nearly every commercial contract
    (Governing Law, a liability cap) confirmed against MSA, TOS and NDA
    standards alike, "detecting" every family from one ordinary document and
    flooding it with MISSING findings for clauses it was never shown to lack —
    the false-positive flood rule 15 and the owner's instruction both forbid.
    Detection now requires the one signal that is actually evidence of KIND:
    a declared type. Content still wins independently of any family: a
    Requirement whose own clause the document confirms applies regardless of
    which family its standard belongs to or whether any type is declared — an
    NDA with a liability clause is still measured against the liability
    standard — but an absent clause is MISSING only inside the declared
    family, never inferred from other clauses' presence. A standard listing
    the declared type under `not_applicable_to` is excluded even when
    confirmed: how the owner's SLA ruling (2026-08-20) stays in force. Order
    preserved (ENG-11).
    """
    confirmed = {code: (not isinstance(m, str) and m.state is MappingState.CONFIRMED)
                 for code, m in mappings.items()}
    detected = {declared_type} if declared_type else set()

    def excluded(item: _SnapshotItem) -> bool:
        cfg = item.company_standard.configuration or {}
        blocked = cfg.get("not_applicable_to") or []
        return declared_type is not None and declared_type in blocked

    applicable = [
        item for item in items
        if not excluded(item)
        and (_standard_type(item) in detected or confirmed[item.requirement.code])
    ]
    return applicable, detected


def _analyse_requirement(db: DBSession, review: M.Review, item: _SnapshotItem,
                         clauses: list[Clause], *,
                         mapping: MappingResult | str,
                         egress: semantic.Egress | None = None) -> RequirementOutcome:
    rv = item.requirement_version
    outcome = RequirementOutcome(
        requirement_code=item.requirement.code,
        requirement_version_id=rv.id,
    )

    standard_configuration = item.company_standard.configuration or {}
    required, applicability_note = requirement_applicability(standard_configuration)
    if applicability_note:
        outcome.diagnostics.append(applicability_note)

    # ---- mapping (Steps 28, 35) — computed once, for applicability and here ----
    if isinstance(mapping, str):
        outcome.failure = mapping
        return outcome
    outcome.mapping_state = mapping.state.value
    # AM-54 — the semantic stage's record travels with the evaluation (REC-07).
    outcome.diagnostics.extend(line for line in mapping.explanation
                               if line.startswith("semantic mapping:"))

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
        facts=_facts_for(rv, standard_configuration, mapping, clauses, outcome,
                         egress=egress),
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
               outcome: RequirementOutcome, egress: semantic.Egress | None = None):
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

    config = LiabilityExtractionConfig.from_config(standard_configuration)
    facts = extract_liability_facts(mapped, config)
    # REC-07 — extraction diagnostics travel with the evaluation for auditability.
    # They are diagnostic metadata only and cannot alter a legal finding.
    outcome.diagnostics.extend(facts.extraction_diagnostics)

    # AM-54 stage 2 — a mapped clause the configured phrases could not read is
    # offered to the model ONCE, and only a magnitude written in the clause is
    # accepted (semantic.extract_cap verifies it); the comparison that follows
    # is the same deterministic one. No model → the configured reading stands.
    if egress is not None and any(c.cap_status == ABSENT for c in facts.caps):
        by_id = {c.evidence_id: c for c in mapped}
        # A mapping the configured words never confirmed (semantic only): the
        # clause was judged to address the requirement, so a quantity the text
        # does not yield is UNCERTAINTY, never established absence — UNKNOWN,
        # and a person looks. Absence is asserted only where configured
        # terminology confirmed the clause (deterministic, as before).
        semantic_only = any("confirmed on a verbatim span" in line
                            for line in mapping.explanation)
        diagnostics: list[str] = []
        caps = []
        for cap in facts.caps:
            clause = by_id.get(cap.evidence_refs[0]) if cap.evidence_refs else None
            if cap.cap_status == ABSENT and clause is not None:
                read = semantic.extract_cap(clause, config, egress, diagnostics,
                                            description=rv.description or "")
                if read is None and semantic_only:
                    diagnostics.append(
                        "semantic extraction: no quantity read from a semantically "
                        "mapped clause; recorded UNKNOWN rather than absence (AM-54)")
                    read = replace(cap, cap_status=UNKNOWN)
                caps.append(read if read is not None else cap)
            else:
                caps.append(cap)
        outcome.diagnostics.extend(diagnostics)
        facts = replace(facts, caps=prune_absent(caps))
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


#: Mean characters per clause above which a document's text is treated as never
#: having been cut into paragraphs at all. This is NOT "the document has no
#: headings" — it is "the segmenter found no boundary of any kind", which on a
#: real contract means the extraction produced blobs.
#:
#: MEASURED, not chosen (rule 7's discipline applied to a product parameter): on
#: 2026-09-05 the segmentation was run over every supplied document. Every one
#: that segmented landed between 158 and 913 mean characters per clause; the two
#: that did not sat at 1,828 and 2,043.
UNSEGMENTED_MEAN_CHARS = 1200

#: Below this total, one block is a plausible WHOLE document (a one-page letter,
#: a short order form), so the ratio says nothing and the check does not run.
UNSEGMENTED_MIN_DOCUMENT_CHARS = 4000


def _structure_not_extracted(clauses: list[Clause]) -> bool:
    """Whether this document's STRUCTURE FAILED TO EXTRACT.

    Owner instruction, 2026-09-05: *"genuinely has no structure"* and *"our
    extraction failed"* must never be treated as the same condition. The first
    is a property of the paper and may be analysed honestly; the second is a
    processing failure and blocks.

    They are separated by two INDEPENDENT signals rather than one ratio:

    ```text
    any clause carries a section number, or any row is a heading
        -> structure was found                     -> analyse
    no structure found, but the text IS cut into
    ordinary paragraphs
        -> the document genuinely has none          -> analyse
    no structure found AND the text arrives in
    page-sized blobs
        -> nothing was recovered, not even a
           paragraph break                          -> REFUSE
    ```

    The middle row is the case this rewrite exists for. The first version of
    this gate had only the ratio, and it refused a terms of service that is
    organised by prose headings — real structure our extractor could not see.
    Now that unnumbered headings are recognised, that document reports structure
    and passes; a document with genuinely nothing passes too, on paragraphs
    alone; and only a document where extraction recovered no boundary at all is
    refused.
    """
    if any(c.section_number for c in clauses) or any(c.is_heading for c in clauses):
        return False
    total = sum(len(clause.content) for clause in clauses)
    if total < UNSEGMENTED_MIN_DOCUMENT_CHARS:
        return False
    return total / len(clauses) > UNSEGMENTED_MEAN_CHARS


def _review_document_type(db: DBSession, review: M.Review) -> str | None:
    """The declared Document Type of the paper under review — locked Step 6.

    Resolved Review → DocumentVersion → Contract.contract_type. Since AM-51
    (2026-09-09) this is ONE signal to applicability, not a gate: None means the
    document's content alone decides which families apply.
    """
    dv = db.get(M.DocumentVersion, review.document_version_id)
    if dv is None:
        return None
    contract = db.get(M.Contract, dv.contract_id)
    return contract.contract_type if contract is not None else None


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

