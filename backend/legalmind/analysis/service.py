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

import logging
import re
from dataclasses import dataclass, field, replace
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis import reading as _reading
from legalmind.analysis import semantic
from legalmind.analysis.opposition import opposing_signals
from legalmind.analysis.unmatched import record_unmatched_provisions
from legalmind.assist.llm import generation
from legalmind.db import models as M
from legalmind.db.lookup import must_exist
from legalmind.domain.document_types import is_document_type, title_type
from legalmind.domain.enums import (
    EvaluationKind,
    EvaluatorType,
    ExtractionStatus,
    FindingClassification,
    MappingState,
    ProcessingStatus,
    ReviewStatus,
)
from legalmind.evaluation.categorical import CategoricalMisconfigured
from legalmind.evaluation.contracts import (
    Cap,
    CompanyStandard,
    EvaluatorInput,
    EvidenceRef,
    LegalRule,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.numeric import MUTUAL
from legalmind.evaluation.presence import OptionalRequirementAbsent, PresenceMisconfigured
from legalmind.evaluation.registry import evaluate, version_for
from legalmind.evaluation.service import (
    EvidenceCardinalityViolation,
    persist_evaluation,
    requirement_applicability,
)
from legalmind.extraction import commercial, parties
from legalmind.extraction.categorical import read_values
from legalmind.extraction.liability import (
    ABSENT,
    APPLICABILITY_UNCERTAIN,
    FIGURE_NOT_READ,
    FINITE,
    NO_FIGURE_STATED,
    PAID_IN_ADVANCE,
    UNKNOWN,
    UNLIMITED,
    LiabilityExtractionConfig,
    LiabilityFacts,
    blank_in,
    cap_carved_out,
    cap_disapplied,
    extract_liability_facts,
    has_magnitude,
    one_position,
    prune_absent,
    stated_figures,
)
from legalmind.mapping.engine import (
    Candidate,
    Clause,
    MappingResult,
    map_requirement,
    under_headings,
)
from legalmind.mapping.rules import MappingMisconfigured, MappingRules
from legalmind.mapping.scoring import (
    CandidateScore,
    Signal,
    contains_phrase,
    normalize,
    phrase_pattern,
    score_clause,
)
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
    #: Where ``document_type`` came from (AM-192): "declared", "title" or "content".
    document_type_source: str | None = None
    #: AM-51 — the Step 6 families the document showed it belongs to (declared
    #: type plus every type at least two of whose standards mapped CONFIRMED).
    detected_types: list[str] = field(default_factory=list)
    #: AM-61 — one record per pinned Requirement: APPLIED, NOT_APPLICABLE or
    #: SAME_POSITION, each with the reason. What was NOT measured, and why, is
    #: part of the run's record — never silently dropped.
    applicability: list[dict] = field(default_factory=list)
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
                 request_id: str | None = None,
                 deal_fixed_term: bool = False) -> AnalysisRun:
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

    # ---- Applicability by CONTENT — AM-51 (2026-09-09), AM-61 (2026-09-13) -----
    # The document decides what applies: every pinned Requirement is MAPPED
    # first (lexical, then grounded semantic — AM-54/AM-60), and a Requirement
    # applies when the document CONFIRMS its clause (any family), belongs to the
    # DECLARED family, or is EXPECTED because the document confirms a Constitution
    # sibling the standard itself names (`constitution.expected_when`). Absence is
    # asserted only for an applied Requirement; one that applies by none of these
    # is NOT_APPLICABLE — recorded with its reason, never dropped. Two standards
    # stating the SAME Constitution position are evaluated once (SAME_POSITION).
    # The declared type is one signal, never a gate. An untyped standard in the
    # snapshot still refuses (ENG-09).
    document_type = _review_document_type(db, review)
    if document_type is not None and not is_document_type(document_type):
        document_type = None
    # undeclared: the paper's own title names its kind ("PURCHASE ORDER"), so the
    # guards keyed on the type still hold — a vendor position never measures a
    # customer's order (2026-10-23; recorded as the run's type, from the title)
    source = "declared" if document_type else None
    if document_type is None and (titled := title_type(clauses)):
        document_type, source = titled, "title"
    # AM-192 (owner, 2026-10-26: "no matter what the file name is — what it includes"):
    # paper whose title names no kind, on which we serve a customer for a fee or a term,
    # is an Other Agreement — §31.13's general positions, never a partner's or vendor's.
    if document_type is None and customer_service_paper(clauses):
        document_type, source = OTHER_TYPE, "content"
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

    if index is not None and egress is not None:
        # a first pass that only COLLECTS the prompts (it asks nothing), then all of them
        # are asked together; the real pass below reads the answers in its own order
        wanted: list[tuple[str, str]] = []
        for item in items:
            _map_item(item, clauses, index, lambda p, v: wanted.append((p, v)),
                      declared_type=document_type)
        egress.prefetch(wanted)  # type: ignore[attr-defined]
    mappings = {item.requirement.code: _map_item(item, clauses, index, egress,
                                                 declared_type=document_type)
                for item in items}
    bases = _position_bases(items)
    # `AM-229` r6: a fixed term another document of the SAME deal states (the signed
    # MOU's "Contract Term: 1 Year") is a fact of the deal, so §14 applies to its MSA
    # too — the term's length may sit in another paper (AM-161).
    items, families, run.applicability = applicable_by_content(
        items, mappings, document_type,
        fixed_term=commercial.states_fixed_term(clauses) or deal_fixed_term)
    # A4 — part of the document was not read (e.g. a page that failed OCR):
    # a clause mapped nowhere may sit in the unread part, so absence cannot be
    # asserted (rule 15). UNABLE_TO_EVALUATE needs evidence (N-34) and there is
    # none, so the analysis is refused rather than minting a MISSING.
    version = db.get(M.DocumentVersion, review.document_version_id)
    unread = sorted(i.requirement.code for i in items
                    if not isinstance(m := mappings[i.requirement.code], str)
                    and m.state is MappingState.NONE)
    if (unread and version is not None
            and version.extraction_status is ExtractionStatus.PARTIAL):
        return _refuse("part of the document could not be read (e.g. a page "
                       "that failed OCR), so the absence of "
                       f"{', '.join(unread)} cannot be established; re-upload a "
                       "complete, clean copy", "extraction_partial")
    # `requirements_in_snapshot` keeps the SNAPSHOT count — the audit record must
    # state what was pinned, not what applied.
    run.requirements_applicable = len(items)
    run.document_type = document_type
    run.document_type_source = source
    run.detected_types = sorted(families)

    with timed("analysis.stage.evaluate", request_id=request_id,
               review_id=str(review.id)) as stage:
        for item in items:
            run.outcomes.append(
                _analyse_requirement(db, review, item, clauses,
                                     mapping=mappings[item.requirement.code],
                                     egress=egress, document_type=document_type,
                                     bases=bases.get(_position_signature(item) or ())))
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
    _second_read(db, review, clauses, document_type, request_id)

    A.record(db, action=A.ANALYSIS_RUN_RECORDED, entity_type="review",
             entity_id=review.id, actor_id=actor_id, request_id=request_id,
             after={"requirements_in_snapshot": run.requirements_in_snapshot,
                    "document_type": run.document_type,
                    "document_type_source": run.document_type_source,
                    "detected_types": run.detected_types,
                    "requirements_applicable": run.requirements_applicable,
                    "applicability": run.applicability,
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


def _cached_recognition(db: DBSession, snapshot_id: UUID, prompt_version: str,
                        prompt_sha256: str,
                        model: str) -> M.SemanticRecognitionCache | None:
    return db.execute(
        select(M.SemanticRecognitionCache).where(
            M.SemanticRecognitionCache.configuration_snapshot_id == snapshot_id,
            M.SemanticRecognitionCache.prompt_version == prompt_version,
            M.SemanticRecognitionCache.prompt_sha256 == prompt_sha256,
            M.SemanticRecognitionCache.model == model)
    ).scalar_one_or_none()


#: How many recognition calls are in flight at once (the provider's limit is far above).
PREFETCH_WORKERS = 8


def _egress_for(db: DBSession, review: M.Review, *, actor_id: UUID | None,
                request_id: str | None) -> semantic.Egress:
    """The analysis run's one door to the generative model: the single seam
    (AM-30 t1), the environment gate, and a hash-only audit row per call.

    Also the RECOGNITION memoization seam (bug fix, 2026-09-29): a hosted
    model at `temperature: 0.0` is not guaranteed bit-reproducible, so the
    same clause re-adjudicated under the same configuration snapshot could
    get a different verdict — a real rule-9 violation, confirmed against a
    live incident where the byte-identical document, re-analyzed under the
    same snapshot, produced a different Finding count. A cache hit here
    means the exact same prompt was already adjudicated under this exact
    snapshot by this exact pinned model; reusing that verdict is what makes a
    repeat analysis deterministic, not a second, independent roll of the same
    die. The model is part of the cache key, not just stored, because
    `MAPPING_PROMPT_VERSION` never changes with `LEGALMIND_GENERATION_MODEL`
    — pinning a new model must get fresh verdicts, never this cache silently
    replaying the old model's.
    """
    import hashlib


    #: Answers asked for ahead of time, by (prompt hash, prompt version) — see `prefetch`.
    ready: dict[tuple[str, str], generation.GenerationResult | Exception] = {}

    # `AM-152` — the owner-selected review model, resolved ONCE per run. A choice that
    # is unknown or not configured leaves the lexical result, exactly as no model does
    # (AM-54); it never aborts the analysis (review, 2026-10-16).
    try:
        chosen = _review_model()
    except ValueError as exc:                    # UnknownModel / ModelNotConfigured
        log_event("analysis.semantic.no_model", level=logging.WARNING,
                  request_id=request_id, review_id=str(review.id),
                  cause=f"{type(exc).__name__}: {exc}")

        def unavailable(prompt: str, prompt_version: str) -> None:
            return None
        unavailable.prefetch = lambda prompts: None  # type: ignore[attr-defined]
        return unavailable
    #: the cache key — the model that answers, so egress and prefetch agree
    model = chosen.api_model if chosen else generation._model()

    def _ask(prompt: str, prompt_version: str):
        return ask_review_model(chosen, prompt, prompt_version, request_id)

    def egress(prompt: str, prompt_version: str):
        import time

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        cached = _cached_recognition(db, review.configuration_snapshot_id,
                                     prompt_version, prompt_sha256, model)
        if cached is not None:
            A.record(db, action=A.ASSIST_GENERATION_CALLED, entity_type="review",
                     entity_id=review.id, actor_id=actor_id, request_id=request_id,
                     after={"purpose": prompt_version, "model": cached.model,
                            "payload_sha256": cached.payload_sha256, "cache_hit": True})
            return generation.GenerationResult(
                text=cached.response_text, model=cached.model,
                prompt_version=prompt_version, payload_sha256=cached.payload_sha256,
                latency_ms=0)
        got = ready.pop((prompt_sha256, prompt_version), None)
        # a call `prefetch` already made and lost counts as the first attempt: a refusal
        # is final, an unavailable provider gets the one retry, exactly as before
        try:
            if isinstance(got, generation.GenerationRefused):
                raise got
            if isinstance(got, generation.GenerationResult):
                result = got
            else:
                try:
                    if got is not None:
                        raise got
                    result = _ask(prompt, prompt_version)
                except generation.GenerationUnavailable:
                    # One retry after a short pause: a transient provider error (a
                    # 503 seen live, 2026-09-09) must not silently degrade a whole
                    # requirement to "no model reached". A refusal is never retried.
                    time.sleep(1.5)
                    result = _ask(prompt, prompt_version)
        except (generation.GenerationRefused,
                generation.GenerationUnavailable) as exc:
            log_event("analysis.semantic.no_model", request_id=request_id,
                      review_id=str(review.id), cause=type(exc).__name__)
            return None
        db.execute(pg_insert(M.SemanticRecognitionCache).values(
            configuration_snapshot_id=review.configuration_snapshot_id,
            prompt_version=prompt_version, prompt_sha256=prompt_sha256,
            model=result.model, response_text=result.text,
            payload_sha256=result.payload_sha256,
        ).on_conflict_do_nothing(
            index_elements=["configuration_snapshot_id", "prompt_version",
                            "prompt_sha256", "model"]))
        A.record(db, action=A.ASSIST_GENERATION_CALLED, entity_type="review",
                 entity_id=review.id, actor_id=actor_id, request_id=request_id,
                 after={"purpose": prompt_version, "model": result.model,
                        "payload_sha256": result.payload_sha256})
        return result

    def prefetch(prompts: list[tuple[str, str]]) -> None:
        """Ask the model for these prompts AT ONCE. One call per Requirement, one after
        the other, was 54 calls x 2.3 s = 126 s of a 129 s analysis (a real upload,
        2026-10-08). Only the network call runs in threads — the cache, the audit row
        and the database session stay on this thread, in the same order as before, so
        what is asked, what is cached and what is audited are unchanged. A call that
        fails here is simply asked again, with its retry, by `egress`."""
        from concurrent.futures import ThreadPoolExecutor

        todo: dict[tuple[str, str], str] = {}
        for prompt, version in prompts:
            key = (hashlib.sha256(prompt.encode("utf-8")).hexdigest(), version)
            if key not in todo and key not in ready and _cached_recognition(
                    db, review.configuration_snapshot_id, version, key[0],
                    model) is None:
                todo[key] = prompt

        def ask(item: tuple[tuple[str, str], str]):
            (_, version), prompt = item
            try:
                return _ask(prompt, version)
            except (generation.GenerationRefused,
                    generation.GenerationUnavailable) as exc:
                return exc

        with ThreadPoolExecutor(max_workers=PREFETCH_WORKERS) as pool:
            for key, result in zip(todo, pool.map(ask, todo.items()), strict=True):
                ready[key] = result

    egress.prefetch = prefetch  # type: ignore[attr-defined]
    return egress


def _second_read(db: DBSession, review: M.Review, clauses: list[Clause],
                 document_type: str | None, request_id: str | None) -> None:
    """AM-162 — the lawyer's second read, and AM-224's reading of the client's changes,
    after every Finding exists and each in its own savepoint: they write only their own
    assist table, so Findings are byte-identical with them on or off (rule 9), and a
    failure here never fails the analysis."""
    from legalmind.analysis import change_triage, reading
    steps = [(name, step, tokens) for name, step, tokens, on in (
        ("reading", reading.run, 4096, reading.enabled()),
        # ~60 output tokens a changed clause; a heavily marked-up MSA has ~90 of them
        ("triage", change_triage.run, 8192, change_triage.enabled())) if on]
    if not steps:
        return
    try:
        chosen = _review_model()
    except ValueError:
        return
    model = chosen.api_model if chosen else generation._model()
    for name, step, tokens in steps:
        def ask(prompt: str, version: str, tokens: int = tokens):
            try:
                # one long answer a document: a self-hosted model writing ~25 tokens a
                # second needs minutes, never the 30 s a short recognition call gets
                return ask_review_model(chosen, prompt, version, request_id,
                                        max_output_tokens=tokens,
                                        timeout_s=LONG_READ_TIMEOUT_S)
            except (generation.GenerationRefused, generation.GenerationUnavailable):
                return None
        try:
            with db.begin_nested():
                items = step(db, review.document_version_id, clauses, document_type,
                             ask, model)
            log_event(f"analysis.{name}.done", request_id=request_id,
                      review_id=str(review.id),
                      items="none" if items is None else str(len(items)))
        except Exception as exc:            # the assist lane never fails the analysis
            log_event(f"analysis.{name}.failed", level=logging.WARNING,
                      request_id=request_id, review_id=str(review.id),
                      cause=type(exc).__name__)


LONG_READ_TIMEOUT_S = 600.0


def ask_review_model(chosen, prompt: str, prompt_version: str, request_id: str | None,
                     max_output_tokens: int = 400,
                     timeout_s: float | None = None) -> generation.GenerationResult:
    """Gemini through its own call as always, any other router model through its
    OpenAI-compatible endpoint. Both go through the single egress seam (`_send`),
    audited and counted alike. ``timeout_s`` None keeps each transport's own default
    (60 s, 30 s)."""
    from legalmind import config
    if chosen is None:
        return generation.generate_raw(
            prompt, prompt_version=prompt_version, environment=config.environment(),
            request_id=request_id, max_output_tokens=max_output_tokens,
            timeout_s=timeout_s or 60.0)
    from legalmind.assist.agent import model_router
    turn = generation.generate_openai_turn(
        "", [{"role": "user", "parts": [{"text": prompt}]}],
        endpoint=model_router.endpoint(chosen), prompt_version=prompt_version,
        environment=config.environment(), request_id=request_id,
        max_output_tokens=max_output_tokens, thinking="MINIMAL",
        timeout_s=timeout_s or 30.0)
    return generation.GenerationResult(
        text=turn.text, model=turn.model, prompt_version=prompt_version,
        payload_sha256=turn.payload_sha256, latency_ms=turn.latency_ms)


def _review_model():
    """The router model the review asks (`config.review_model`), or None for Gemini's
    own call. An unknown or unconfigured choice raises, and is never substituted. Not
    `model_router.resolve`: that also requires Ask's agent mode, and the review does
    not depend on how Ask is configured — only on the model's own key and endpoint."""
    import os

    from legalmind import config
    from legalmind.assist.agent import model_router
    chosen = model_router.MODELS.get(config.review_model() or model_router.DEFAULT)
    if chosen is None:
        raise model_router.UnknownModel(config.review_model())
    if chosen.id == model_router.DEFAULT:
        return None
    if not (os.environ.get(chosen.key_env, "").strip() and (
            not chosen.base_url_env or os.environ.get(chosen.base_url_env, "").strip())):
        raise model_router.ModelNotConfigured(chosen.label)
    return chosen


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
    semantically — the stage only speaks where the words were silent. It runs
    for EVERY pinned Requirement since AM-60 (2026-09-13) removed AM-54 r4's
    in-family gate on a live four-mode measurement; ``declared_type`` is kept for
    the callers and no longer narrows it.
    """
    try:
        rules = MappingRules.from_config(item.mapping_rules.rules)
    except MappingMisconfigured as exc:
        return f"mapping configuration unusable: {exc}"
    standard = item.company_standard.configuration or {}
    if standard.get("form") in (NAMES_DOCUMENT, BY_REFERENCE):
        return _shaped_mapping(item.requirement_version.id, clauses, standard)
    waived = waiver_signals(clauses, standard.get("waiver_patterns") or (),
                            rules.confirm_threshold,
                            conditions=standard.get("waiver_conditions") or ())
    if "INVOICE_PAYMENT_PERIOD" in ((standard.get("extraction") or {}).get("bases")
                                    or {}):
        for clause in paid_in_advance(clauses):
            waived = {**waived, clause.evidence_id: (
                *waived.get(clause.evidence_id, ()),
                Signal("structure", "payment is taken in advance",
                       rules.confirm_threshold))}
    if standard.get("scope_key") == "CONF_DEFINITION" and (span := marking_only(clauses)):
        bound = next(c for c in clauses if span in " ".join((c.content or "").split()))
        waived = {**waived, bound.evidence_id: (
            *waived.get(bound.evidence_id, ()),
            Signal("waiver_pattern", f"marked information only; span: {span}",
                   rules.confirm_threshold))}
    if standard.get("scope_key") == "CONF_MUTUAL" and (span := fixed_roles(clauses)):
        bound = next(c for c in clauses if span in " ".join((c.content or "").split()))
        waived = {**waived, bound.evidence_id: (
            *waived.get(bound.evidence_id, ()),
            Signal("waiver_pattern", f"a role bound to one party; span: {span}",
                   rules.confirm_threshold))}
    if standard.get("scope_key") == "ORDER_PRECEDENCE_PO_MSA":
        for evidence_id, extra in precedence_signals(clauses,
                                                     rules.confirm_threshold).items():
            waived = {**waived, evidence_id: (*waived.get(evidence_id, ()), *extra)}
    if standard.get("scope_key") == "EARLY_TERMINATION_RESTRICTION":
        for evidence_id, extra in exit_right_signals(
                clauses, rules.confirm_threshold,
                standard.get("waiver_conditions") or ()).items():
            waived = {**waived, evidence_id: (*waived.get(evidence_id, ()), *extra)}
    for evidence_id, extra in opposing_signals(clauses, standard.get("scope_key"),
                                               rules.confirm_threshold,
                                               _sentences).items():
        waived = {**waived, evidence_id: (*waived.get(evidence_id, ()), *extra)}
    for evidence_id, signal in _structural_signals(
            clauses, rules, standard, item.mapping_rules.rules).items():
        waived = {**waived, evidence_id: (*waived.get(evidence_id, ()), signal)}
    lexical = map_requirement(item.requirement_version.id, rules, clauses,
                              extra_signals=waived)
    if index is None or egress is None or lexical.state is MappingState.CONFIRMED:
        return lexical
    # 35.5 still vetoes: a clause carrying a configured negative pattern (a
    # negative lexical score) is never offered for semantic confirmation.
    shortlist = [(c, sim)
                 for c, sim in index.shortlist(item.requirement_version.id, clauses)
                 if score_clause(rules, content=c.content,
                                 section_title=c.section_title).score >= 0]
    if not shortlist:
        return lexical
    terms = ", ".join([*rules.aliases, *rules.exact_phrases,
                       *rules.section_heading_terms])
    signals, diagnostics = semantic.adjudicate(
        item.requirement_version.description or "", terms, shortlist,
        rules.confirm_threshold, egress,
        position_statement=(standard.get("nli_hypothesis")
                            or standard.get("position_statement")),
        # AM-152 r1: only a presence standard that requires the clause can be waived
        opposable=(item.requirement_version.evaluator_type is EvaluatorType.PRESENCE
                   and standard.get("expected_presence") == "PRESENT"),
        conditions=standard.get("waiver_conditions") or ())
    for evidence_id, extra in waived.items():
        signals[evidence_id] = (*signals.get(evidence_id, ()), *extra)
    result = map_requirement(item.requirement_version.id, rules, clauses,
                             extra_signals=signals)
    return replace(result, explanation=result.explanation + tuple(diagnostics))


#: `AM-152` — the signals that say a clause WAIVES or OPPOSES the position rather than
#: stating it: a configured waiver phrase (deterministic) or the selected model's
#: OPPOSED verdict on a verbatim span (`semantic.adjudicate`).
OPPOSING_SIGNALS = frozenset({"waiver_pattern", "semantic_opposed"})


#: Words whose stop never ends a sentence before a figure ("Rs. 5,00,000", "Sec. 7",
#: "Clause No. 7"), and "i.e."/"e.g.", which never end one (review r29/r30). A real
#: sentence end before a figure ("… shall apply. 3 months' notice …") still splits.
_BEFORE_A_FIGURE = re.compile(r"\b(?:rs|inr|no|nos|sec|cl|art|para)\.$", re.I)
_NEVER_AN_END = re.compile(r"\b(?:i\.e|e\.g|viz)\.$", re.I)


#: What a customer's paper calls the customer (the counterparty on MSA/TOS/order paper).
_CUSTOMER_NAMES = ("buyer", "client", "purchaser")


#: §31.11 shapes (2026-10-23, generated per position by tools/generate_section31_
#: standards.py from the Constitution's own words): NAMES_DOCUMENT — the paper names the
#: governing agreement anywhere; BY_REFERENCE — its own section on the topic points to
#: the agreement rather than restating terms ("not restated independently").
NAMES_DOCUMENT = "NAMES_DOCUMENT"
BY_REFERENCE = "BY_REFERENCE"


#: "… is not subject to any MSA", "without an MSA": a mention that denies the reference.
_DENIES = re.compile(r"\b(?:not|no|never|without)\b(?:\W+\w+){0,4}\W*$")
#: "Non-payment and suspension" is not the payment-terms section.
_NON = re.compile(r"\bnon[\s-]*$")


def _names(clause: Clause, terms) -> bool:
    """Whether the clause names one of ``terms`` without denying it."""
    body = normalize(clause.content or "")
    for term in terms:
        for m in re.finditer(phrase_pattern(normalize(term)), body):
            start = max(body.rfind(".", 0, m.start()), body.rfind(";", 0, m.start())) + 1
            if not _DENIES.search(body[start:m.start()]):
                return True
    return False


def _heads(title: str, topic) -> bool:
    """Whether a heading names the topic — "Payment", never "Non-payment"."""
    return any(not _NON.search(title[:m.start()])
               for t in topic for m in re.finditer(phrase_pattern(normalize(t)), title))


def _topic_section(clauses: list[Clause], topic) -> list[Clause]:
    """The document's OWN section on a topic: the first numbered heading naming it
    ("7. Payment") and what is numbered under it, in document order — never a later
    schedule's heading that also says "payment" (the real PO's SLA annexure)."""
    titles = under_headings(clauses)
    out: list[Clause] = []
    head: str | None = None
    for c in clauses:
        number = (c.section_number or "").rstrip(".")
        top = number.split(".")[0] if number else None
        if head is None:
            if top and "." not in number and _heads(
                    normalize(titles.get(c.evidence_id) or ""), topic):
                head = top
                out.append(c)
        elif top == head:
            out.append(c)
        elif top and "." not in number:
            break                      # the next numbered section ends this one
    return out


def _shaped_mapping(rv_id: UUID, clauses: list[Clause],
                    standard: dict) -> MappingResult:
    """The clauses a shaped position is about. NAMES_DOCUMENT: every clause naming the
    agreement (none → NONE, so MISSING with no evidence). BY_REFERENCE: the document's
    own section on the topic — each clause under a heading naming it; a paper silent on
    the topic follows the agreement it names (none named → NONE, MISSING)."""
    refers = standard.get("refers_to") or ()
    if standard.get("form") == NAMES_DOCUMENT:
        hits = [c for c in clauses if _names(c, refers)]
        why = "names the governing agreement" if hits else "no clause names it"
    else:
        hits = _topic_section(clauses, standard.get("topic_headings") or ())
        why = "the document's own section on this topic"
        if not hits:
            hits = [c for c in clauses if _names(c, refers)]
            why = ("no section of its own; the paper names the governing agreement"
                   if hits else "no section on this topic and no governing agreement")
    return MappingResult(
        requirement_version_id=rv_id,
        state=MappingState.CONFIRMED if hits else MappingState.NONE,
        candidates=tuple(Candidate(c, CandidateScore(0, (Signal("shape", why, 0),)))
                         for c in hits),
        evidence_ids=tuple(c.evidence_id for c in hits),
        explanation=(f"{standard.get('form')}: {why}",))


def restated(mapping: MappingResult | str, standard: dict) -> bool:
    """BY_REFERENCE: the section found states its own terms and never points to the
    governing agreement — "not restated independently" (Constitution §31.11)."""
    return (standard.get("form") == BY_REFERENCE and not isinstance(mapping, str)
            and mapping.state is MappingState.CONFIRMED
            and not any(_names(c, standard.get("refers_to") or ())
                        for c in mapping.confirmed_clauses))


#: A clause under the standard's own heading that also uses its subject words and states
#: a figure in its units (or leaves one blank) is about that term — scored like an alias.
STRUCTURE_WEIGHT = 3


def topic_terms(rules: dict | None) -> tuple[str, ...]:
    """A standard's topic words — its own mapping vocabulary: exact phrases, aliases and
    every keyword-group word (35.4: terminology is configuration, nothing invented)."""
    rules = rules or {}
    words = [*(rules.get("exact_phrases") or ()), *(rules.get("aliases") or ()),
             *(w for group in rules.get("keyword_groups") or () for w in group)]
    return tuple(dict.fromkeys(words))


def _structural_signals(clauses: list[Clause], rules: MappingRules,
                        standard: dict, standard_rules: dict | None = None,
                        ) -> dict[UUID, Signal]:
    """Structural evidence for a PERIOD standard (2026-10-23): "7.1 … invoice … at least
    [7] days" under "7. Payment" is the payment-period clause even when no configured
    phrase names it and a model shortlist skipped it. Three facts the standard itself
    configures, all required: its heading term on the clause or its parent heading, a
    basis word in the clause, and a figure in its units or a blank. Never for a cap
    that can be unlimited or is context-guarded (liability) — those keep their words."""
    extraction = standard.get("extraction") or {}
    config = LiabilityExtractionConfig.from_config(standard)
    if (not rules.section_heading_terms or not extraction.get("bases")
            or config.unlimited_phrases or config.cap_context_terms):
        return {}
    basis_terms = tuple(t for terms in config.bases.values() for t in terms)
    titles = under_headings(clauses)

    def same_word(a: str, b: str) -> bool:      # "terminate" / "termination"
        a, b = normalize(a), normalize(b)
        return a[:6] == b[:6] if min(len(a), len(b)) >= 6 else a == b
    out: dict[UUID, Signal] = {}
    for clause in clauses:
        heading = normalize(titles.get(clause.evidence_id) or "")
        body = normalize(clause.content or "")
        term = next((t for t in rules.section_heading_terms
                     if contains_phrase(heading, t)), None)
        # the basis word must be evidence of its own: "termination" under a
        # "Termination" heading is one fact counted twice — "13.3 prepaid fees refunded
        # within 15 days of termination" is no notice clause
        topic = topic_terms(standard_rules)
        own = term and any(
            contains_phrase(sentence, b) and not same_word(b, term)
            and (not topic or any(contains_phrase(sentence, t) for t in topic))
            and (has_magnitude(sentence, config.units) or blank_in(sentence))
            for sentence in re.split(r"(?<=[.;])\s+", body) for b in basis_terms)
        if own:
            out[clause.evidence_id] = Signal(
                "structure", f"under '{term}', its basis words and a figure",
                STRUCTURE_WEIGHT)
    return out


def _sentences(text: str) -> list[str]:
    out: list[list[str]] = []
    prev = ""
    for piece in re.split(r"(?<=[.;])\s+", text or ""):
        # the abbreviation is always in the previous PIECE: linear, however long the run
        if out and (_NEVER_AN_END.search(prev)
                    or (_BEFORE_A_FIGURE.search(prev) and piece[:1].isdigit())):
            out[-1].append(piece)
        else:
            out.append([piece])
        prev = piece
    return [normalize(" ".join(s)) for s in out if "".join(s).strip()]


def waiver_signals(clauses: list[Clause], patterns, threshold: int,
                   conditions=()) -> dict[UUID, tuple[Signal, ...]]:
    """A clause stating one of the standard's configured waiver phrases ("no lock-in",
    "no early termination charges") addresses the requirement — by negating it. It
    is confirmed at the threshold, exactly as one exact phrase is, and the signal says
    so; `opposed_span` then reads it as the clause's polarity. Terminology, so
    configuration (35.4) — nothing inferred. A waiver in a sentence that also states
    one of the configured ``conditions`` ("material breach", "for cause") is a
    carve-out from the position, not a waiver of it, and is not counted (`AM-155`)."""
    out: dict[UUID, tuple[Signal, ...]] = {}
    for clause in clauses:
        hits = [p for sentence in _sentences(clause.content)
                if not any(contains_phrase(sentence, c) for c in conditions)
                for p in patterns if contains_phrase(sentence, p)]
        if hits:
            out[clause.evidence_id] = (Signal(
                "waiver_pattern", f"the clause waives the position; span: {hits[0]}",
                threshold),)
    return out


#: §14 by what the clause DOES (AM-188, owner 2026-10-26): the customer — or either party
#: — may leave the term on notice, for convenience or at any time. Grammar, never a party
#: name; LeapSwitch's own right to leave is not the customer's.
_EXIT_RIGHT = re.compile(
    r"\b(?:the\s+)?(?:customer|client|buyer|purchaser|either\s+party)\s+(?:may|can|"
    r"(?:shall|will)\s+(?:be\s+entitled|have\s+the\s+right)\s+to|is\s+entitled\s+to|"
    r"has\s+the\s+right\s+to)\s+terminate\b[^.;]{0,200}?(?:\bnotice\b|\bfor\s+"
    r"convenience\b|\bat\s+any\s+time\b|\bwithout\s+(?:any\s+)?cause\b|\bfor\s+any\s+"
    r"reason\b)", re.I)
#: An exit an EVENT triggers — force majeure, the other side's failure — is a carve-out
#: like an exit for breach, never a waiver of the term (replay of our own MSA §18.3).
_TRIGGERED = re.compile(r"\b(?:if|unless|in\s+the\s+event|(?:up)?on\s+the\s+occurrence|"
                        r"should|force\s+majeure)\b", re.I)
#: The consequence §14 asks for, stated in the same limb: the exit keeps the position.
_REST_OF_TERM = re.compile(r"\b(?:remainder|rest|balance|unexpired\s+(?:portion|part))\s+"
                           r"of\s+the\s+(?:term|contract|commitment)|\bremaining\s+"
                           r"(?:term|months|period)|\bunexpired\s+(?:term|period)", re.I)


def exit_right_signals(clauses: list[Clause], threshold: int,
                       conditions=()) -> dict[UUID, tuple[Signal, ...]]:
    """A limb giving the customer an exit from the term — not for breach or insolvency
    (the standard's ``conditions``: a carve-out, not a waiver) and not paying the rest of
    the term — waives §14, however it names its fee ("an early termination fee may
    apply" states no amount). Read limb by limb, as `waiver_signals` reads sentences."""
    out: dict[UUID, tuple[Signal, ...]] = {}
    for clause in clauses:
        for limb in _sentences(clause.content):
            m = _EXIT_RIGHT.search(limb)
            if m and not _REST_OF_TERM.search(limb) and not _TRIGGERED.search(limb) \
                    and not any(
                    contains_phrase(limb, c) for c in conditions):
                out[clause.evidence_id] = (Signal(
                    "waiver_pattern",
                    f"the clause lets the customer leave the term; span: {m.group(0)}",
                    threshold),)
                break
    return out


#: §31.11 precedence by which document WINS (AM-190, owner 2026-10-26): "Where a PO and
#: the governing MSA conflict, the MSA prevails". A paper that ranks itself first — "this
#: MOU shall prevail, followed by the MSA", "(i) this MoU; (ii) the MSA" — waives it,
#: whatever the paper is called; one that ranks the MSA first states it. Grammar only.
_THIS_PAPER = (r"this\s+(?:po|purchase\s+order|order(?:\s+form)?|mou|memorandum"
               r"(?:\s+of\s+understanding)?|proposal|quotation|addendum|schedule|annexure|"
               r"sow)\b")
_THE_MSA = r"(?:the\s+)?(?:msa|master\s+services?\s+agreement)\b"
_WINS = r"(?:shall|will|should)\s+(?:prevail|govern|take\s+precedence|override|control)"
_PAPER_WINS = re.compile(rf"{_THIS_PAPER}[^.;,]{{0,20}}?\s{_WINS}|"
                         rf"\(i\)\s*{_THIS_PAPER}", re.I)
_MSA_WINS = re.compile(rf"{_THE_MSA}\s*(?:\([^)]*\)\s*)?{_WINS}|\(i\)\s*{_THE_MSA}", re.I)


def precedence_signals(clauses: list[Clause],
                       threshold: int) -> dict[UUID, tuple[Signal, ...]]:
    """Whole sentences that rank this paper against the MSA ("(i) …; (ii) …" kept
    together): the paper first waives the position, the MSA first states it."""
    out: dict[UUID, tuple[Signal, ...]] = {}
    for clause in clauses:
        for sentence in re.split(r"(?<=\.)\s+", " ".join((clause.content or "").split())):
            if not re.search(_THE_MSA, sentence, re.I):
                continue
            if m := _PAPER_WINS.search(sentence):
                out[clause.evidence_id] = (Signal(
                    "waiver_pattern", f"the paper ranks itself above the MSA; span: "
                    f"{m.group(0)}", threshold),)
                break
            if m := _MSA_WINS.search(sentence):
                out[clause.evidence_id] = (Signal(
                    "precedence", f"the MSA prevails: {m.group(0)}", threshold),)
                break
    return out


#: Payment taken BEFORE the service (AM-191, 2026-10-26): "[PREPAID]", "billed in
#: advance", "received before service activation". A payment term — never a missing one
#: — with no invoice period to compare: a person decides. Only beside a payment word, so
#: "prepaid credits are non-refundable" is no payment term. Grammar only.
_IN_ADVANCE = re.compile(r"\bpre-?paid\b|\bin\s+advance\b|\bupfront\b|\bup-front\b|"
                         r"\bbefore\s+(?:the\s+)?(?:service\s+)?activation\b", re.I)
_PAYMENT_WORD = re.compile(r"\b(?:pay\w*|billed|billing|invoic\w*)\b", re.I)


def paid_in_advance(clauses: list[Clause]) -> list[Clause]:
    return [c for c in clauses
            if any(_IN_ADVANCE.search(s) and _PAYMENT_WORD.search(s)
                   # "in advance or arrears as may be agreed": a choice left open
                   and not re.search(r"\barrears\b", s, re.I)
                   for s in _sentences(c.content))]


#: §15 by the ROLES, never the title (AM-199, owner 2026-10-26): a Disclosing or Receiving
#: Party role bound to a named party or a blank — "(“Disclosing Party (ACME)”)",
#: "ACME Private Limited (the “Disclosing Party”)" — protects one side only. "one party
#: (“Disclosing Party”) … the other", "Each party (the “Receiving Party”)" stay mutual.
_ROLE = r"(?:disclosing|receiving)\s+party"
_ROLE_NAMED_INSIDE = re.compile(
    rf"[\"\u201c\u2018']\s*{_ROLE}\s*\(\s*[^)\"\u201d]{{2,80}}", re.I)
#: the NAME is case-sensitive — a company is capitalised; only the role words are not
_ROLE_AFTER_NAME = re.compile(
    rf"(?P<who>[A-Z][\w&.,'\u2019\- ]{{2,80}}?)\s*\(\s*(?i:(?:hereinafter\s+)?"
    rf"(?:referred\s+to\s+as\s+)?(?:the\s+)?)[\"\u201c\u2018']\s*(?i:{_ROLE})\s*"
    rf"[\"\u201d\u2019']")
_ANY_PARTY = re.compile(
    r"\b(?:one|each|either|a|the\s+other|any|both)(?:\s+(?:party|parties))?\s*$", re.I)


def fixed_roles(clauses: list[Clause]) -> str | None:
    """The span binding a confidentiality role to one named party, or None (AM-199)."""
    for clause in clauses:
        text = " ".join((clause.content or "").split())
        if m := _ROLE_NAMED_INSIDE.search(text):
            return m.group(0)
        for m in _ROLE_AFTER_NAME.finditer(text):
            # read with the words before it: "the other Party (“Disclosing Party”)"
            if not _ANY_PARTY.search(text[max(0, m.start("who") - 20):m.end("who")]):
                return m.group(0)
    return None


#: §15's two-part test (AM-206, 2026-10-26): "information marked confidential, or
#: information a reasonable person would understand to be confidential". Protection only
#: for MARKED information — "shall not be subject to the restrictions … unless … marked"
#: — is one part; the reasonable-person limb anywhere in the document is the second.
_MARKING_ONLY = re.compile(r"\b(?:unless|only\s+if|only\s+where|provided\s+that)\b"
                           r"[^.]{0,160}?\bmarked\b", re.I)
_REASONABLE_LIMB = re.compile(r"\breasonabl[ey]\b[^.]{0,80}?\b(?:understood|understand|"
                              r"regarded|considered|know)\b|\bby\s+(?:its|their)\s+nature\b",
                              re.I)


def marking_only(clauses: list[Clause]) -> str | None:
    """The span that protects marked information only, when no reasonable-person limb is
    stated anywhere in the document — or None (AM-206)."""
    texts = [" ".join((c.content or "").split()) for c in clauses]
    if any(_REASONABLE_LIMB.search(t) for t in texts):
        return None
    return next((m.group(0) for t in texts if (m := _MARKING_ONLY.search(t))), None)


#: A clause's start where the parser recorded no number: a short title line with no
#: closing stop ("Confidentiality", "Miscellaneous Provisions") or a "Title Case:" label
#: ("Partner Indemnification of Company: …") — never "The Company will: (i) …".
_TITLE_WORDS = (r"[A-Z][\w\u2019'-]*(?:\s+(?:[A-Z][\w\u2019'-]*|&|of|and|for|to|the|in|"
                r"on|by|or|with)){0,7}")
#: Every word capitalised (small words aside) and no punctuation: a list item Word left
#: unnumbered ("Third-party software installed by the Customer,") is never a title.
_CLAUSE_START = re.compile(rf"^(?:{_TITLE_WORDS}$|{_TITLE_WORDS}\s*:)")
#: A breadth phrase the same sentence then excludes ("indirect damages are excluded",
#: "lost profits shall not be recoverable"): an exclusion, never breadth.
#: Only the losses themselves may stand between the phrase and the exclusion, and an
#: exclusion FROM the cap is not one ("indemnity obligations are excluded from the
#: limitation of liability" makes them broader, not narrower).
_EXCLUDED_AFTER = re.compile(
    r"\W*(?:(?:damages?|losses?|loss|lost|profits?|revenue|data|indirect|consequential|"
    r"special|incidental|punitive|exemplary|of|and|or|any|all|such)\W+){0,8}"
    r"(?:(?:is|are|shall\s+be|will\s+be)\s+(?:(?:expressly|specifically)\s+)?"
    r"(?:excluded|disclaimed|not\s+recoverable|not\s+covered|not\s+included)"
    r"|(?:shall|will)\s+not\s+be\s+(?:recoverable|covered|included))\b"
    r"(?!\s+from\s+(?:the\s+|any\s+|such\s+)?(?:limitation|cap|aggregate)\b)", re.I)


_EXECUTION = re.compile(r"(?:in\s+witness\s+where(?:of|as)|signed\s+(?:by|for)|"
                        r"for\s+and\s+on\s+behalf\s+of)\b", re.I)


def _starts_clause(clause: Clause) -> bool:
    """A short title line, a "Title Case:" label or an execution block on the paragraph's
    first line — a heading with a short body ("Governing Law\nIndian law applies.")
    still starts a clause."""
    first = (clause.content or "").strip().split("\n", 1)[0].strip()
    return bool(_CLAUSE_START.match(first) or _EXECUTION.match(first))


def _with_continuations(clauses: list[Clause], mapping: MappingResult) -> list[Clause]:
    """The confirmed clauses, each with the paragraphs that continue it — "The Company
    will: … give Partner sole control of the defense" under an indemnity, or Word's
    auto-numbered (a)–(e) items under 14.1, are part of that clause. A continuation ends
    at the next number, heading, short title line, "Title Case:" label or execution
    block (each read on the paragraph's first line); an unnumbered run that nothing
    closes is the document's remainder, of which only what the mapping
    confirmed is read (/code-review and its re-review, 2026-10-17)."""
    confirmed = {c.evidence_id for c in mapping.confirmed_clauses}
    out: list[Clause] = []
    run: list[Clause] = []
    for clause in clauses:
        # a confirmed clause's own sub-clauses (10 → 10.1, 10.2) are its body: a confirmed
        # "10. INDEMNIFICATION" heading is read with what is numbered under it (r34)
        child = bool(run and run[0].section_number and clause.section_number
                     and clause.section_number.startswith(
                         run[0].section_number.rstrip(".") + "."))
        numbered = bool(clause.section_number or clause.is_heading) and not child
        # a numbered clause runs to the next number or heading (a Title-Case list item
        # inside it never ends it); a title line or label ends only an unnumbered run
        unnumbered_run = bool(run) and not (run[0].section_number or run[0].is_heading)
        if numbered or ((unnumbered_run or not run) and _starts_clause(clause)):
            out, run = out + run, []
        if run or clause.evidence_id in confirmed:
            run.append(clause)
    if run and not (run[0].section_number or run[0].is_heading
                    or _starts_clause(run[0])):
        run = [c for c in run if c.evidence_id in confirmed]
    return out + run


#: AM-207 — a page number stranded at a clause's end by a page break ("…notice\n7").
_TRAILING_PAGE_NUMBER = re.compile(r"\n\s*\d{1,3}\s*$")


def _page_breaks_joined(clauses: list[Clause]) -> list[Clause]:
    """For reading a figure only: a piece with no number and no heading that opens in
    lowercase is the rest of the previous clause's sentence, broken by a page ("…written
    notice" | 7 | "from Leapswitch specifying the breach, or (b) …"). Read alone, its
    figure contradicted the clause it belongs to (our own MSA 7.4, a false CONFLICT).
    The evidence rows are untouched; the joined clause cites the clause it continues."""
    out: list[Clause] = []
    for clause in clauses:
        text = (clause.content or "").lstrip()
        if not clause.section_number and re.fullmatch(r"\d{1,3}", text.strip()):
            continue                        # a page number alone: nothing to read
        if (out and not clause.section_number and not clause.is_heading
                and text[:1].islower()):
            head = out[-1]
            out[-1] = replace(head, content=_TRAILING_PAGE_NUMBER.sub(
                "", (head.content or "").rstrip()) + " " + text)
            continue
        out.append(clause)
    return out


_LIABILITY_TITLE = re.compile(r"\b(?:limitation|liabilit\w*|damages)\b", re.I)


def _titled_for(clauses: list[Clause], cfg: dict) -> list[Clause]:
    """Clauses whose own title or label names the indemnity ("Indemnification
    Procedure: …") — read for breadth even when the mapping did not confirm them, so a
    procedure that cedes the defence is never missed for want of its own score."""
    scope = cfg.get("breadth_scope") or ()
    out = []
    for clause in clauses:
        # only a real title or label: a parser's "title" that is the clause's first line
        # ("In no event, whether in contract, indemnity, warranty …") never counts
        title = (clause.section_title or "").strip()
        label = title if _CLAUSE_START.match(title) else ""
        head = _CLAUSE_START.match((clause.content or "").strip())
        if head:
            label += " " + head.group(0)
        # a heading that names liability too ("Limitation of Liability and Indemnity") is
        # the cap's, never the indemnity's own
        if (scope and not _LIABILITY_TITLE.search(label)
                and any(contains_phrase(normalize(label), t) for t in scope)):
            out.append(clause)
    return out


#: An exclusion in any indemnity's words ("shall not be liable to the Indemnified Party
#: for any indirect …", "shall have no liability for …") — read beside the configured
#: negatives, up to twelve words before the phrase (r32).
#: "… direct losses, but not (for/against) any indirect …" — never "but not limited to".
_BUT_NOT = re.compile(r"\bbut\s+not\s+(?:for\s+|against\s+)?(?:any\s+)?"
                      r"(?:\w+\s+(?:or|and)\s+){0,3}$")
_NOT_LIABLE = ("not be liable", "not liable", "no liability",
               "neither party shall be liable", "neither party will be liable",
               "not apply to", "not be applicable to", "not be required to indemnify",
               "not be obliged to indemnify", "not be obligated to indemnify",
               "no obligation to indemnify", "not indemnify", "not extend to",
               "not cover", "under no circumstances", "in no case",
               "nothing in this indemnity",
               "neither party shall be required to indemnify", "no party shall be liable",
               "and not for", "with the exception of", "not be responsible",
               "not responsible", "in no circumstances", "nothing in this clause")


#: A sentence that opens "In no event …" / "Under no circumstances …" is an exclusion of
#: liability whatever theories it names, "indemnity" among them (AM-165).
_OPENS_AS_EXCLUSION = re.compile(
    r"\W*(?:\d[\d.]*\W+)?(?:in\s+no\s+event|under\s+no\s+circumstances|"
    r"in\s+no\s+circumstances)\b", re.I)


def narrowing_hit(clauses: list[Clause], cfg: dict) -> str | None:
    """The sentence that limits an exclusion to listed causes (owner, 2026-10-21; G-F):
    it states the exclusion ("not be liable" … a ``narrowing_subject`` word), a
    ``narrowing_lead`` ("arising from", "caused by") followed by a ``narrowing_causes``
    term (the customer's or a third party's doing), and none of ``full_scope_terms``
    ("howsoever", "operational error"). Phrase matching only; None when unconfigured."""
    causes, leads = cfg.get("narrowing_causes") or (), cfg.get("narrowing_lead") or ()
    if not causes or not leads:
        return None
    subject = cfg.get("narrowing_subject") or ()
    full = cfg.get("full_scope_terms") or ()
    for clause in clauses:
        for sentence in _sentences(clause.content):
            if not (any(contains_phrase(sentence, n) for n in _NOT_LIABLE)
                    and any(contains_phrase(sentence, w) for w in subject)):
                continue
            if any(contains_phrase(sentence, f) for f in full):
                continue
            low = normalize(sentence)
            for lead in leads:
                at = low.find(normalize(lead))
                if at >= 0 and any(contains_phrase(low[at:], c) for c in causes):
                    return sentence
    return None


def breadth_hit(clauses: list[Clause], cfg: dict) -> str | None:
    """`AM-154` r1 / `AM-155`: the first configured breadth phrase an indemnity sentence
    COVERS — a sentence stating one of ``breadth_scope`` (the indemnity's own words),
    where no configured ``breadth_negatives`` cue stands within six words before the
    phrase ("shall not be liable for any indirect", "this indemnity shall not extend
    to consequential", "Leapswitch shall retain control of the defence"): an
    exclusion, or a defence kept, is not breadth. Phrase matching only."""
    patterns = cfg.get("breadth_patterns") or ()
    scope = cfg.get("breadth_scope") or ()
    negatives = "|".join(re.escape(normalize(n))
                         for n in (*(cfg.get("breadth_negatives") or ()), *_NOT_LIABLE))
    in_scope = False
    excluding = False
    for clause in clauses:
        for sentence in _sentences(clause.content):
            # a list's items share their lead-in's indemnity until a full stop — "shall
            # indemnify … from and against: (a) …; (b) … indirect losses; …" (r35)
            in_scope = in_scope or not scope or any(contains_phrase(sentence, t)
                                                    for t in scope)
            ends = sentence.rstrip().endswith(".")
            if excluding or _OPENS_AS_EXCLUSION.match(sentence):
                # "In no event, whether in … indemnity …, shall X be liable for: (a) …;
                # (b) …" — the exclusion and every item under it, to the full stop
                excluding = not ends
                in_scope = in_scope and not ends
                continue
            if in_scope:
                for p in patterns:
                    for m in re.finditer(phrase_pattern(normalize(p)), sentence):
                        before = sentence[:m.start()]
                        if (_EXCLUDED_AFTER.match(sentence[m.end():])
                                or _BUT_NOT.search(before)):
                            continue        # "indirect damages are excluded": not covered
                        if not negatives or not re.search(
                                rf"(?:{negatives})\W+(?:\w+\W+){{0,12}}$", before):
                            return p
            in_scope = in_scope and not ends
    return None


#: §10 by what WE promise (AM-189, owner 2026-10-26): our indemnity covers third-party IP
#: infringement, gross negligence and wilful misconduct; any other cause is "materially
#: broader". Our side or a mutual "each party" indemnifies — never the customer's
#: indemnity to us, never a negated one ("shall have no obligation to indemnify").
_WE_INDEMNIFY = re.compile(
    r"\b(?:" + "|".join(_reading._PROVIDER) + r"|each\s+party|either\s+party|both\s+"
    r"parties)\s+(?:shall|will|agrees?\s+to|undertakes?\s+to)\s+(?:(?!no\b|not\b)\w+[\s,]+)"
    r"{0,3}?indemnif\w*(?P<rest>[^.]*)", re.I)
_BEYOND_SECTION_10 = re.compile(
    r"breach\s+of\s+(?:any\s+)?(?:applicable\s+)?laws?|breach\s+of\s+(?:this\s+)?"
    r"(?:agreement|contract)|breach\s+of\s+(?:any\s+|its\s+)?(?:representations?|"
    r"warrant\w*|obligations?)|confidentiality|data\s+protection|privacy|"
    r"(?<!gross\s)negligen\w*|any\s+(?:failure|deficiency|disruption|interruption|outage|"
    r"downtime)|(?:provision|performance)\s+of\s+the\s+services|act\s+or\s+omission",
    re.I)
#: §10's own causes for an indemnity we give. One that names none of them covers every
#: claim, which is broader than §10 too (QA-001, 2026-10-29: "LeapSwitch shall indemnify,
#: defend and hold harmless the Customer from all claims" MATCHED).
_SECTION_10_OURS = re.compile(r"intellectual\s+property|infring\w*|gross\s+negligen\w*|"
                              r"wil+ful\s+misconduct", re.I)


#: AM-211 — in a MUTUAL paper either side may be the Disclosing or Receiving Party, so an
#: indemnity given by a role binds us too ("The Disclosing Party shall indemnify …").
_ROLE_INDEMNIFIES = re.compile(
    r"\bthe\s+(?:disclosing|receiving)\s+party\s+(?:shall|will|agrees?\s+to|undertakes?\s+"
    r"to)\s+(?:(?!no\b|not\b)\w+[\s,]+){0,3}?indemnif\w*(?P<rest>[^.]*)", re.I)


def our_indemnity_beyond(clauses: list[Clause]) -> str | None:
    """The first cause beyond Constitution §10 that an indemnity WE give names, read to
    the sentence's end — or None. Recognition grammar, never a position (35.4)."""
    givers = [_WE_INDEMNIFY] + ([_ROLE_INDEMNIFIES] if not fixed_roles(clauses) else [])
    for clause in clauses:
        text = " ".join((clause.content or "").split())
        for pattern in givers:
            for m in pattern.finditer(text):
                if hit := _BEYOND_SECTION_10.search(m.group("rest")):
                    return hit.group(0)
                if not _SECTION_10_OURS.search(m.group("rest")):
                    return m.group(0).strip()
    return None


#: AM-212 — §10: the customer's indemnity covers its content, unlawful use, customer and
#: end-user conduct, AUP violations and breach of law. One that names neither the AUP nor
#: its end users' conduct is narrower than §10 — read only where the customer indemnifies.
_THEY_INDEMNIFY = re.compile(
    r"\b(?:the\s+)?(?:customer|client|buyer|purchaser)\s+(?:shall|will|agrees?\s+to|"
    r"undertakes?\s+to)\s+(?:(?!no\b|not\b)\w+[\s,]+){0,3}?indemnif\w*(?P<rest>[^.]*)",
    re.I)
#: …or covers them by a wider limb: ANY breach of the agreement (the AUP is part of it),
#: or claims of the customer's own customers (its end users) — the GRP MSA's 11.1, 13.2
_SECTION_10_THEIRS = re.compile(
    r"\b(?:acceptable\s+use|aup|end[\s-]+users?|its\s+users|customers?\s+of\s+(?:the\s+)?"
    r"customer|any\s+breach|breach\s+of\s+(?:this|the)\s+(?:agreement|contract))\b", re.I)


def their_indemnity_short(indemnity: list[Clause]) -> str | None:
    """The customer's indemnity, when it omits both §10 limbs it must carry (the AUP, its
    end users' conduct) — or None. ``indemnity`` is the clauses the indemnity standard
    found WITH their continuations: "arising out of or relating to:" is followed by its
    (a)-(e) list (our own MSA 16.1), and an indemnity inside another topic's clause (an
    MSME notice) is never the indemnity."""
    text = " ".join(" ".join((c.content or "").split()) for c in indemnity)
    found = _THEY_INDEMNIFY.search(text)
    if found and not _SECTION_10_THEIRS.search(text):
        return found.group(0)[:160]
    return None


#: The signals that show a clause STATES the position — its own configured wording or the
#: model's verbatim confirmation; an alias or heading alone is not enough.
STATING_SIGNALS = frozenset({"exact_phrase", "keyword_group", "semantic_confirmed",
                             "precedence"})


#: An exception phrase governing the cue — no clause break between them: "Save where …
#: material breach, … shall pay" states the charge; "Unless otherwise agreed in writing,
#: upon termination for … material breach, …" is a for-cause rule (r33).
_EXCEPTION = re.compile(r"\b(?:save|except|unless|other\s+than|excluding|subject\s+to|"
                        r"without\s+prejudice\s+to|notwithstanding)\b[^,;:]*$")


def _carved_out(sentence: str, cues) -> bool:
    """Whether every for-cause cue in the (normalized) sentence sits inside an exception
    phrase — then the sentence still states the position; a cue anywhere else makes it a
    for-cause rule, never a statement of it (r31: no list of lifting words)."""
    hits = [m.start() for cue in cues
            for m in re.finditer(rf"\b{re.escape(normalize(cue))}\b", sentence)]
    return all(_EXCEPTION.search(sentence[max(0, i - 80):i]) for i in hits)


def contested(mapping: MappingResult, conditions=()) -> bool:
    """Whether a confirmed clause opposes the position AND another confirmed clause
    states it on positive evidence (`STATING_SIGNALS`) — one stray waiver phrase never
    speaks for the whole document, and a clause that merely mentions the subject never
    contests a waiver (review, 2026-10-17). A stating sentence with a for-cause cue
    states the position only when the cue is an exception to it (r31)."""
    opposing = stating = False
    for c in mapping.candidates:
        kinds = {s.kind for s in c.score.signals}
        if kinds & OPPOSING_SIGNALS:
            opposing = True
        elif kinds & STATING_SIGNALS:
            # sentence by sentence, as `waiver_signals` reads conditions: a clause stating
            # the position in one sentence and a for-cause carve-out in the next states it
            terms = [s.matched.split(" + ") for s in c.score.signals
                     if s.kind in ("exact_phrase", "keyword_group")]
            stating = stating or any(
                _carved_out(sentence, conditions)
                and (not terms or any(all(contains_phrase(sentence, w) for w in group)
                                      for group in terms))
                for sentence in _sentences(c.clause.content))
    return opposing and stating


def opposed_span(mapping: MappingResult) -> str | None:
    """The sentence of a confirmed clause that waives or opposes the position, or None
    when no confirmed clause carries an opposing signal (`OPPOSING_SIGNALS`)."""
    for candidate in mapping.candidates:
        kinds = [s for s in candidate.score.signals if s.kind in OPPOSING_SIGNALS]
        if kinds:
            # both opposing signals end "span: <text>", the raw text (never a repr)
            needle = kinds[0].matched.rpartition("span: ")[2].strip()
            for sentence in re.split(r"(?<=[.;])\s+", candidate.clause.content):
                if needle and normalize(needle) in normalize(sentence):
                    return " ".join(sentence.split())
            return " ".join(needle.split()) or " ".join(
                candidate.clause.content.split())[:300]
    return None


def _standard_type(item: _SnapshotItem) -> str | None:
    return (item.company_standard.configuration or {}).get("document_type")


def _cross_family(item: _SnapshotItem, declared_type: str | None) -> bool:
    """Another document type's standard on a typed document (2026-10-21, AM-51 r2 as
    amended): its clause may be confirmed by content, but a figure it does not state is
    never read as an established absence there — whether the position applies at all is
    for Legal to confirm. Not on OTHER: the catch-all type has no family of its own and is
    measured against the customer-service positions (Constitution §31.13, AM-152)."""
    family = _standard_type(item)
    return bool(declared_type and declared_type != "OTHER" and family
                and family != declared_type)


APPLIED = "APPLIED"
NOT_APPLICABLE = "NOT_APPLICABLE"
SAME_POSITION = "SAME_POSITION"
SAME_TOPIC = "SAME_TOPIC"

#: Constitution §31.13 (AM-147): documents that "do not fit MSA, NDA, SLA, PO, Partner
#: Agreement, Vendor Agreement, or Distribution Agreement" are "evaluated against the
#: general positions already set out in Sections 9-22". So the positions §31 states
#: for a counterparty RELATIONSHIP alone — a partner, a vendor, a distributor — never
#: measure a document declared OTHER: a customer MOU read "Acceptable" against a vendor
#: agreement's deliverables clause. The general (MSA, TOS, NDA, SLA) copies still
#: apply by content (AM-51), and so do the Purchase Order and Amendment positions,
#: which a customer's order or side letter genuinely states.
OTHER_TYPE = "OTHER"
#: The parties of paper on which WE serve a CUSTOMER — and of paper on which we buy.
_CUSTOMER_PARTY = re.compile(r"\b(?:customer|client|buyer|purchaser|subscriber)\b", re.I)
_WE_BUY = re.compile(r"\b(?:vendor|supplier|contractor|distributor|reseller|partner)\b",
                     re.I)


def customer_service_paper(clauses: list[Clause]) -> bool:
    """Content, not a name (AM-192): a fee or a committed term is stated and the other
    side is a customer, never a vendor, supplier, partner or distributor — that paper is
    a relationship §31 states positions for, and is never typed by this guess."""
    text = " ".join(c.content or "" for c in clauses)
    facts = commercial.read(clauses)
    return bool((facts.fee_per_month or facts.term_stated)
                and _CUSTOMER_PARTY.search(text) and not _WE_BUY.search(text))
_TYPE_SPECIFIC = frozenset({"PARTNER_AGREEMENT", "VENDOR_AGREEMENT",
                            "DISTRIBUTION_AGREEMENT"})
#: AM-153 — positions §31 states for an order or an amendment as a document of its own.
_PAPER_SPECIFIC = frozenset({"ORDER_FORM", "AMENDMENT"})

#: When one topic is stated per family (CONF-SURVIVAL-MSA-001 / -NDA-001), the copy
#: kept for a document of none of them: the Constitution's general commercial positions
#: are written for the MSA (§§9-22), then the published terms. Engineering order, never
#: a legal ranking — the dropped copy is recorded SAME_TOPIC with the one measured.
_FAMILY_ORDER = ("MSA", "TOS", "NDA", "SLA")


def _topic(item: _SnapshotItem) -> tuple[str, str | None]:
    """A Requirement's topic across families: its code without the family and serial
    (``CONF-SURVIVAL-MSA-001`` -> ``CONF-SURVIVAL``), with its Constitution section."""
    code, family = item.requirement.code, _standard_type(item)
    stem = code.rsplit(f"-{family}-", 1)[0] if family and f"-{family}-" in code else code
    return stem, _section(item)


def _constitution(item: _SnapshotItem) -> dict:
    return (item.company_standard.configuration or {}).get("constitution") or {}


def _section(item: _SnapshotItem) -> str | None:
    return _constitution(item).get("section")


def _position_signature(item: _SnapshotItem) -> tuple | None:
    """What the standard asks for, as a comparable key — or None when the
    Constitution states no section for it (then nothing can be 'the same')."""
    cfg = item.company_standard.configuration or {}
    section = _section(item)
    if section is None:
        return None
    if "preferred" in cfg:
        return (section, "NUMERIC", cfg.get("preferred"), cfg.get("unit"),
                cfg.get("basis"), cfg.get("scope_key"))
    if "expected_presence" in cfg:
        return (section, "PRESENCE", cfg.get("expected_presence"), cfg.get("scope_key"))
    if "allowed_values" in cfg:
        return (section, "CATEGORICAL", tuple(cfg["allowed_values"]),
                cfg.get("scope_key"))
    return None


def _position_bases(
        items: list[_SnapshotItem]) -> dict[tuple, dict[str, tuple[str, ...]]]:
    """The basis terminology of every pinned copy of one Constitution position,
    merged (A1). One position measured once must recognise what EITHER copy's
    ratified terminology names: the TOS copy alone has no affected-services
    terms, so an affected-services cap read through it was total fees — a false
    MATCH. Merged, the clause names two bases and fails closed (`_find_basis`).
    Terms only; no value, unit or comparable basis changes. Sorted (ENG-11)."""
    merged: dict[tuple, dict[str, set[str]]] = {}
    for item in items:
        key = _position_signature(item)
        if key is None:
            continue
        block = ((item.company_standard.configuration or {}).get("extraction") or {})
        for basis, terms in (block.get("bases") or {}).items():
            merged.setdefault(key, {}).setdefault(basis, set()).update(terms)
    return {key: {b: tuple(sorted(t)) for b, t in sorted(by.items())}
            for key, by in merged.items()}


#: `AM-152` — the document types a customer's service contract is declared as: the
#: five commercial pillars (`commercial_pillar`) are always measured on them.
CUSTOMER_SERVICE_TYPES = frozenset({"MSA", "TOS", "ORDER_FORM", OTHER_TYPE})


def _states_commitment(mapping: MappingResult | str, cfg: dict | None) -> bool:
    """AM-161: a confirmed clause with a sentence that STATES the customer's commitment in
    one of the standard's `commitment_phrases` ("The Customer shall have no right to
    terminate this Agreement before the expiry of the Term") and no waiver pattern in that
    same sentence. Never an alias alone, never LeapSwitch's own restriction, and a stray
    waiver elsewhere is `contested`'s to weigh, not a cancellation (r4)."""
    if isinstance(mapping, str):
        return False
    phrases = (cfg or {}).get("commitment_phrases") or ()
    waivers = (cfg or {}).get("waiver_patterns") or ()
    return any(any(contains_phrase(sentence, p) for p in phrases)
               and not any(contains_phrase(sentence, w) for w in waivers)
               for c in mapping.confirmed_clauses for sentence in _sentences(c.content))


def applicable_by_content(items: list[_SnapshotItem],
                          mappings: dict[str, MappingResult | str],
                          declared_type: str | None, *, fixed_term: bool = False,
                          ) -> tuple[list[_SnapshotItem], set[str], list[dict]]:
    """Which pinned Requirements this document is measured against, and WHY each
    one was or was not — AM-51 (2026-09-09, r2 corrected same day) as amended by
    AM-61 (2026-09-13).

    Three signals make a Requirement apply, each deterministic and each recorded:

    * CONFIRMED — the document contains its clause (content wins, whatever family
      the standard belongs to; one document may span several legal domains).
    * DECLARED — the standard's family is the type a human or a confident
      suggestion declared (AM-50): the one fact actually asserted about the KIND
      of paper. Absence inside it is measured.
    * EXPECTED — the standard's own `constitution.expected_when.confirmed_any`
      names a sibling position the document confirms: a liability cap makes the
      §9 exclusion of consequential damages expected; a confidentiality clause
      makes the §15 survival period expected. The trigger is DECLARED per
      standard from the Constitution's structure, never inferred across topics —
      the boilerplate flood that killed AM-51 r1 (a governing-law clause
      "detecting" the whole MSA family) cannot recur, because no standard names
      a governing-law clause as evidence for anything but dispute resolution.

    A Requirement none of these reaches is NOT_APPLICABLE and is RECORDED with its
    reason (rule 15: not a guess, not a silence). A standard listing the declared
    type under `not_applicable_to` never applies, even when confirmed — how the
    owner's SLA ruling (2026-08-20) stays in force. Two applied standards stating
    the SAME Constitution position (same section, same value/unit/basis/scope or
    same presence expectation) are evaluated ONCE: a confirmed copy before an
    unconfirmed one, then the declared family's copy, else the first by code
    (ENG-11); the others are SAME_POSITION.
    The standards stay per family (Q3=B); only the measurement is de-duplicated.
    Order preserved (ENG-11).
    """
    confirmed = {code: (not isinstance(m, str) and m.state is MappingState.CONFIRMED)
                 for code, m in mappings.items()}
    # AM-161 (owner, 2026-10-17): a lock-in clause the document confirms, with no waiver
    # opposing it ("The Customer shall have no right to terminate this Agreement before
    # the expiry of the Term"), is itself a fixed-term commitment (§14 Scope), even where
    # the term's length sits in another document — no ₹ figure follows from it (AM-156).
    committed = fixed_term or any(
        _states_commitment(mappings[i.requirement.code], i.company_standard.configuration)
        for i in items if confirmed.get(i.requirement.code)
        and (i.company_standard.configuration or {}).get("requires_fixed_term"))
    detected = {declared_type} if declared_type else set()
    coverage: list[dict] = []
    applied: list[_SnapshotItem] = []

    def record(item: _SnapshotItem, outcome: str, reason: str) -> None:
        coverage.append({"code": item.requirement.code, "section": _section(item),
                         "outcome": outcome, "reason": reason})

    for item in items:
        code = item.requirement.code
        cfg = item.company_standard.configuration or {}
        blocked = cfg.get("not_applicable_to") or []
        if declared_type is not None and declared_type in blocked:
            record(item, NOT_APPLICABLE,
                   f"the standard lists the declared type {declared_type} under "
                   "not_applicable_to (owner ruling 2026-08-20)")
            continue
        family = _standard_type(item)
        # An Order Form's or an Amendment's own §31.11/§31.12 position measures that
        # paper; on an Other Agreement it stays (a customer's order genuinely states it).
        specific = _TYPE_SPECIFIC | (_PAPER_SPECIFIC if declared_type != OTHER_TYPE
                                     else frozenset())
        if declared_type and family in specific and family != declared_type:
            # AM-147 for OTHER (Constitution §31.13); AM-153 for any declared type: a
            # partner, vendor or distributor position measures that relationship only —
            # an MSA's "Effect of Termination" heading once matched a partner position.
            lead = ("Constitution §31.13: an Other Agreement is evaluated against the "
                    "general positions of Sections 9-22, not"
                    if declared_type == OTHER_TYPE
                    else f"a {declared_type} is not measured against")
            record(item, NOT_APPLICABLE,
                   f"{lead} the §{_section(item)} {family} position (AM-147/AM-153)")
            continue
        if cfg.get("requires_fixed_term") and not committed:
            # Constitution §14 — "services supplied against a fixed-term commercial
            # commitment". A monthly, cancel-anytime service saying "no lock-in" is not
            # a waiver of anything (AM-152).
            record(item, NOT_APPLICABLE,
                   f"Constitution §{_section(item)} applies to a fixed-term commitment; "
                   "the document states no committed term (AM-152)")
            continue
        if cfg.get("non_fixed_term_only") and committed and not confirmed[code]:
            # §13 subordinated to §14 on a fixed-term commitment: not measured as an
            # absence, still measured where the document has the clause (§31.2:
            # "checked on a document-by-document basis") (AM-161)
            record(item, NOT_APPLICABLE,
                   f"Constitution §{_section(item)}: \"This section governs ongoing, "
                   "non-fixed-term arrangements; see Section 14 for early exit from a "
                   "fixed-term commitment.\" — the document states a fixed-term "
                   "commitment and no such clause (AM-161)")
            continue
        triggers = sorted(c for c in (_constitution(item).get("expected_when") or {})
                          .get("confirmed_any", []) if confirmed.get(c))
        pillar = (cfg.get("commercial_pillar")
                  and declared_type in CUSTOMER_SERVICE_TYPES)
        if confirmed[code]:
            reason = "the document confirms this clause" + (
                f"; another document type's standard ({_standard_type(item)}): a figure "
                "it does not state is not read as absent — Legal to confirm it applies"
                if _cross_family(item, declared_type) and item.requirement_version
                .evaluator_type is EvaluatorType.NUMERIC_COMPARISON else "")
        elif _standard_type(item) in detected:
            reason = (f"declared type {declared_type} is this standard's family; "
                      "absence is measured")
        elif pillar:
            reason = ("a commercial pillar, measured on every customer service "
                      f"contract (Constitution §31.13; {declared_type}); absence is "
                      "measured (AM-152)")
        elif triggers and _cross_family(item, declared_type):
            # owner, 2026-10-21 ("how a lawyer behaves"): another document type's
            # position, expected beside a confirmed sibling but absent, is not raised as
            # a missing clause on this paper — the report's coverage says so, and Legal
            # may add it. No clause exists to show, so no Finding is minted (N-34).
            record(item, NOT_APPLICABLE,
                   f"another document type's position ({_standard_type(item)}), "
                   f"expected beside Constitution §{_section(item)} through "
                   f"{', '.join(triggers)}; not raised as missing on a {declared_type} "
                   "— Legal may add it")
            continue
        elif triggers:
            section = _section(item)
            reason = (f"expected: the document confirms Constitution §{section} "
                      f"through {', '.join(triggers)}")
        else:
            record(item, NOT_APPLICABLE,
                   "not confirmed in the document; "
                   + (f"not the declared family ({declared_type}); "
                      if declared_type else "no type declared; ")
                   + "no Constitution sibling it names is confirmed")
            continue
        applied.append(item)
        record(item, APPLIED, reason)

    # SAME_POSITION — one Constitution position, measured once.
    # The copy kept is one whose clause the document CONFIRMS, then the declared
    # family's — never a copy whose mapping failed beside one that confirmed (A7).
    def rank(i: _SnapshotItem) -> tuple[bool, bool]:
        return confirmed[i.requirement.code], _standard_type(i) == declared_type

    kept: dict[tuple, _SnapshotItem] = {}
    for item in applied:
        key = _position_signature(item)
        if key is not None and (key not in kept or rank(item) > rank(kept[key])):
            kept[key] = item
    duplicates = {i.requirement.code: kept[k].requirement.code for i in applied
                  if (k := _position_signature(i)) is not None and kept[k] is not i}
    if duplicates:
        for entry in coverage:
            if entry["code"] in duplicates:
                entry["outcome"] = SAME_POSITION
                entry["reason"] = (f"states the same Constitution §{entry['section']} "
                                   f"position as {duplicates[entry['code']]}, which is "
                                   "measured for both")
        applied = [i for i in applied if i.requirement.code not in duplicates]

    # SAME_TOPIC (AM-147) — one topic, one result for one document. Two families'
    # copies of a topic that state DIFFERENT positions (the MSA and NDA confidentiality
    # survival bases) both measured one clause and disagreed: "Deviates" beside
    # "Unclear" on the same sentence. The copy kept: a confirmed one, then the declared
    # family's, then `_FAMILY_ORDER`, then by code (ENG-11).
    def topic_rank(i: _SnapshotItem) -> tuple:
        family = _standard_type(i)
        order = (_FAMILY_ORDER.index(family) if family in _FAMILY_ORDER
                 else len(_FAMILY_ORDER))
        return (not confirmed[i.requirement.code], family != declared_type, order,
                i.requirement.code)

    by_topic: dict[tuple, _SnapshotItem] = {}
    for item in applied:
        key = _topic(item)
        if key not in by_topic or topic_rank(item) < topic_rank(by_topic[key]):
            by_topic[key] = item
    other_copies = {i.requirement.code: by_topic[_topic(i)].requirement.code
                    for i in applied if by_topic[_topic(i)] is not i}
    for entry in coverage:
        if entry["code"] in other_copies:
            entry["outcome"] = SAME_TOPIC
            entry["reason"] = (f"another family's copy of the topic measured once, as "
                               f"{other_copies[entry['code']]} (AM-147)")
    applied = [i for i in applied if i.requirement.code not in other_copies]
    return applied, detected, coverage


def _analyse_requirement(db: DBSession, review: M.Review, item: _SnapshotItem,
                         clauses: list[Clause], *,
                         mapping: MappingResult | str,
                         egress: semantic.Egress | None = None,
                         bases: dict[str, tuple[str, ...]] | None = None,
                         document_type: str | None = None,
                         ) -> RequirementOutcome:
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
    # `AM-152` — the sentence that waives the position, kept with the analysis record
    # (REC-07); the evaluator receives only the fact (45D).
    waiving = opposed_span(mapping)
    disputed = contested(mapping, standard_configuration.get("waiver_conditions") or ())
    if waiving:
        outcome.diagnostics.append(
            f"polarity {'CONTESTED' if disputed else 'OPPOSED'}: {waiving}")
    # `AM-154` — a configured breadth phrase in a clause the mapping CONFIRMED.
    broad = (breadth_hit(_with_continuations(clauses, mapping)
                         + _titled_for(clauses, standard_configuration),
                         standard_configuration)
             if mapping.state is MappingState.CONFIRMED else None)
    if broad is None and standard_configuration.get("scope_key") == "INDEMNIFICATION" \
            and mapping.state is MappingState.CONFIRMED:
        broad = our_indemnity_beyond(clauses)
    if broad:
        outcome.diagnostics.append(f"breadth: {broad!r} (AM-154)")
    narrow = (narrowing_hit(list(mapping.confirmed_clauses), standard_configuration)
              if mapping.state is MappingState.CONFIRMED else None)
    if narrow is None and standard_configuration.get("scope_key") == "INDEMNIFICATION" \
            and mapping.state is MappingState.CONFIRMED:
        narrow = their_indemnity_short(_with_continuations(clauses, mapping))
    if narrow:
        outcome.diagnostics.append(f"narrowing: {narrow!r} (G-F, 2026-10-21)")

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
        # on every Evaluation, not only on presence ones. `AM-152`: and whether the
        # clause found WAIVES the position rather than stating it.
        mapping=MappingInput(mapping_state=mapping.state, evidence_refs=evidence,
                             opposed=waiving is not None,
                             contested=disputed,
                             too_broad=broad is not None,
                             too_narrow=narrow is not None,
                             restated=restated(mapping, standard_configuration)),
        facts=_facts_for(rv, standard_configuration, mapping, clauses, outcome,
                         egress=egress, bases=bases,
                         topic=topic_terms(item.mapping_rules.rules),
                         roles=(document_type or "") in parties.CUSTOMER_TYPES,
                         uncertain=_cross_family(item, document_type)),
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
    except CategoricalMisconfigured as exc:
        outcome.failure = f"categorical configuration unusable: {exc}"
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
               outcome: RequirementOutcome, egress: semantic.Egress | None = None,
               bases: dict[str, tuple[str, ...]] | None = None,
               topic: tuple[str, ...] = (), roles: bool = False,
               uncertain: bool = False):
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
    if rv.evaluator_type is EvaluatorType.CATEGORICAL:
        # AM-148 — the values the CONFIRMED clauses name; nothing from candidates the
        # mapping refused to choose between (Step 28 r6, as below).
        if mapping.state is not MappingState.CONFIRMED or not mapping.confirmed_clauses:
            return None
        try:
            return read_values(list(mapping.confirmed_clauses), standard_configuration)
        except CategoricalMisconfigured:
            return None                     # the evaluator refuses it, with the reason
    if rv.evaluator_type is not EvaluatorType.NUMERIC_COMPARISON:
        return None

    if mapping.state is MappingState.NONE:
        # Established absence: the mapping layer completed and no clause scored
        # at all. For a Requirement that APPLIES (declared family, or expected
        # through a confirmed Constitution sibling — AM-61) that is the numeric
        # evaluator's MISSING with zero evidence (45C.15), exactly as PRESENCE
        # reports it — not "unable", and never a cardinality failure that drops
        # the Finding (found 2026-09-13 on the real mixed document).
        outcome.diagnostics.append(
            "mapping NONE: no provision to extract from; absence established by "
            "the mapping layer, not by evaluator inspection")
        return LiabilityFacts(caps=(), extraction_status=ExtractionStatus.COMPLETE,
                              extraction_diagnostics=())

    if mapping.state is not MappingState.CONFIRMED:
        outcome.diagnostics.append(
            f"mapping state {mapping.state.value}: no facts extracted, so the "
            "evaluation fails closed rather than choosing between candidates "
            "(Step 28 r6)")
        return None

    # a confirmed heading ("10. Liability") is read with what is numbered under it
    # ("10.1 … 6 months"): the figure is in the body, never in the heading (2026-10-23)
    mapped = _page_breaks_joined(_with_continuations(clauses, mapping))
    if not mapped:
        return None

    config = replace(LiabilityExtractionConfig.from_config(standard_configuration),
                     topic_terms=topic)
    if bases:
        config = replace(config, bases=bases)
    if roles:
        # On a customer's paper (MSA, TOS, order) the counterparty IS the customer, so
        # "the amount paid by the Buyer" is the configured "amount paid by the customer"
        # (2026-10-23). Never on a vendor's or partner's paper, where LeapSwitch buys.
        config = replace(config, bases={
            code: tuple(dict.fromkeys(
                [*terms, *(t.replace("customer", party) for t in terms
                           if "customer" in t for party in _CUSTOMER_NAMES)]))
            for code, terms in config.bases.items()})
    facts = extract_liability_facts(mapped, config)
    # REC-07 — extraction diagnostics travel with the evaluation for auditability.
    # They are diagnostic metadata only and cannot alter a legal finding.
    outcome.diagnostics.extend(facts.extraction_diagnostics)

    # AM-54 stage 2 — a mapped clause the configured phrases could not read is
    # offered to the model ONCE, and only a magnitude written in the clause is
    # accepted (semantic.extract_cap verifies it); the comparison that follows
    # is the same deterministic one. No model → the configured reading stands.
    # A figure the configured words could not read (FIGURE_NOT_READ) is offered too:
    # that is the second reader's whole case (2026-10-23).
    def unread(cap) -> bool:
        return cap.cap_status == ABSENT or (cap.cap_status == UNKNOWN
                                            and cap.reason == FIGURE_NOT_READ)

    if egress is not None and any(unread(c) for c in facts.caps):
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
            if unread(cap) and clause is not None:
                read = semantic.extract_cap(clause, config, egress, diagnostics,
                                            description=rv.description or "")
                if read is None and semantic_only:
                    diagnostics.append(
                        "semantic extraction: no quantity read from a semantically "
                        "mapped clause; recorded UNKNOWN rather than absence (AM-54)")
                    read = replace(cap, cap_status=UNKNOWN, reason=(
                        FIGURE_NOT_READ if stated_figures(clause.content)
                        else NO_FIGURE_STATED),
                        candidates=stated_figures(clause.content))
                caps.append(read if read is not None else cap)
            else:
                caps.append(cap)
        outcome.diagnostics.extend(diagnostics)
        facts = replace(facts, caps=prune_absent(caps))
    # AM-164 — a sentence that takes any breach (or every claim) out of the limitation
    # leaves no cap for the claims it exists for: an unlimited position beside the stated
    # figure, which the evaluator reads as the conflict it is, for a person.
    if config.cap_context_terms:
        # AM-195 — a §9-named class (confidentiality, data, IP, indemnities) taken out of
        # the cap is uncapped for those claims, as AM-164 reads a breach-wide class.
        for clause, named in cap_carved_out(clauses):
            outcome.diagnostics.append(
                f"clause {clause.section_number or '?'} takes {named!r} claims out of "
                "the limitation: Constitution §9 approves no carve-out for them; read "
                "as unlimited for those claims")
            facts = replace(facts, caps=(*facts.caps, Cap(
                cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope,
                scope_label=None, cap_status=UNLIMITED,
                evidence_refs=(clause.evidence_id,))))
        for clause in cap_disapplied(clauses):
            outcome.diagnostics.append(
                "clause %s takes a breach-wide class of claims out of the limitation: "
                "read as unlimited for those claims" % (clause.section_number or "?"))
            facts = replace(facts, caps=(*facts.caps, Cap(
                cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope,
                scope_label=None, cap_status=UNLIMITED,
                evidence_refs=(clause.evidence_id,))))
    # AM-191 — prepaid: nothing read as an invoice period, but the paper takes payment in
    # advance. A payment term found, with no period to compare — never MISSING.
    advance = (paid_in_advance(mapped) if "INVOICE_PAYMENT_PERIOD" in config.bases
               else [])
    if advance and all(c.cap_status == ABSENT for c in facts.caps):
        outcome.diagnostics.append("payment is taken in advance: no invoice period to "
                                   "compare (AM-191)")
        facts = replace(facts, caps=(Cap(
            cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope, scope_label=None,
            cap_status=UNKNOWN, reason=PAID_IN_ADVANCE,
            evidence_refs=tuple(c.evidence_id for c in advance)),))
    # Another type's standard (`_cross_family`): no stated figure is UNKNOWN, never an
    # established absence — a person confirms whether the position applies at all.
    if uncertain:
        refs = tuple(c.evidence_id for c in mapped[:1])
        caps = [replace(c, cap_status=UNKNOWN, reason=APPLICABILITY_UNCERTAIN)
                if c.cap_status == ABSENT else c for c in facts.caps]
        facts = replace(facts, caps=tuple(caps) or (Cap(
            cap_kind=EvaluationKind.PRIMARY, scope=config.general_scope, scope_label=None,
            cap_status=UNKNOWN, reason=APPLICABILITY_UNCERTAIN, evidence_refs=refs),))
    facts = replace(facts, caps=one_position(facts.caps))
    # Constitution §9 — a mutual cap: whose liability each stated cap limits, from its
    # own sentence; None when the words do not say (never guessed).
    if standard_configuration.get(MUTUAL):
        content = {c.evidence_id: c.content for c in clauses}
        facts = replace(facts, caps=tuple(
            replace(cap, cap_party=parties.cap_party(
                [s for ref in cap.evidence_refs
                 for s in parties.sentences(content.get(ref, ""))],
                {"cap_value": cap.cap_value, "cap_unit": cap.cap_unit}, roles))
            if cap.cap_status == FINITE else cap for cap in facts.caps))
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

