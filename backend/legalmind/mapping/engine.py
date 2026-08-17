"""Mapping engine — locked Steps 28 and 35.

Produces, for each Requirement, a persisted **Mapping State** (axis 1):
``CONFIRMED`` / ``AMBIGUOUS`` / ``UNRESOLVED``, plus ``NONE`` for established
absence (45D).

--------------------------------------------------------------------------
On the deliberately deferred band mapping (B-11)
--------------------------------------------------------------------------
Locked Step 35.9 sketches bands — "High -> CONFIRMED, Medium -> CANDIDATE /
REVIEW, Low -> NOT MAPPED" — and explicitly declines to lock thresholds. The
owner further deferred how Step 35's band vocabulary maps onto Step 28's three
persisted states, instructing that it must not be inferred.

This engine therefore **does not implement Step 35's band vocabulary at all.**
It derives state directly from locked Step 28's own definitions:

  CONFIRMED   "sufficient deterministic evidence to map the clause to the
              Requirement"                          -> exactly one clear winner
  AMBIGUOUS   "More than one plausible mapping exists and LegalMind must not
              silently choose one"                  -> tied plausible candidates
  UNRESOLVED  "The system cannot establish the mapping reliably"
                                                    -> nothing reaches threshold

No `CANDIDATE`, `CANDIDATE-REVIEW`, `NOT MAPPED` or `NO_CONFIDENT_MAPPING` value
is produced or persisted. When the band mapping is decided it can be layered on
without revisiting these semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from legalmind.domain.enums import MappingState
from legalmind.mapping.rules import MappingRules
from legalmind.mapping.scoring import CandidateScore, score_clause


@dataclass(frozen=True)
class Clause:
    """A candidate clause — one `document_evidence` row (42.6)."""

    evidence_id: UUID
    content: str
    section_number: str | None = None
    section_title: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class Candidate:
    clause: Clause
    score: CandidateScore

    @property
    def value(self) -> int:
        return self.score.score


@dataclass(frozen=True)
class MappingResult:
    """The mapping outcome for ONE Requirement over a document.

    ``evidence_ids`` is the mapping evidence required by locked 35.18 and
    Step 28 r7 ("Every mapping retains evidence showing the relevant customer
    clause and Requirement").
    """

    requirement_version_id: UUID
    state: MappingState
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)
    evidence_ids: tuple[UUID, ...] = field(default_factory=tuple)
    explanation: tuple[str, ...] = field(default_factory=tuple)

    @property
    def confirmed_clauses(self) -> tuple[Clause, ...]:
        return tuple(c.clause for c in self.candidates)


def map_requirement(
    requirement_version_id: UUID,
    rules: MappingRules,
    clauses: list[Clause],
) -> MappingResult:
    """Map one Requirement against a document's clauses.

    Locked 35.6: operates at clause/section level, never on the document as one
    text block. Locked 35.12: one Requirement may map to multiple clauses — all
    qualifying clauses are retained rather than reduced to a single best match.
    Locked 35.17: a clause may remain unmapped when evidence is insufficient;
    nothing is forced.
    """
    scored = [
        Candidate(clause=c, score=score_clause(
            rules, content=c.content, section_title=c.section_title))
        for c in clauses
    ]
    # Deterministic ordering: score descending, then evidence id, so equal
    # scores never depend on input order (ENG-11).
    scored.sort(key=lambda c: (-c.value, str(c.clause.evidence_id)))

    qualifying = [c for c in scored if c.value >= rules.confirm_threshold]

    if not qualifying:
        # Distinguish "nothing plausible at all" from "something looked
        # relevant but fell short". Both are non-mappings, but the second is
        # not established absence and must not be reported as NONE (45D).
        any_positive = any(c.value > 0 for c in scored)
        state = MappingState.UNRESOLVED if any_positive else MappingState.NONE
        best = scored[0] if scored else None
        explanation = (
            (f"no candidate reached the confirm threshold "
             f"({rules.confirm_threshold}); best score "
             f"{best.value if best else 0}",)
            if any_positive else
            ("no clause produced any positive mapping signal",)
        )
        return MappingResult(
            requirement_version_id=requirement_version_id,
            state=state,
            candidates=(),
            evidence_ids=tuple(c.clause.evidence_id for c in scored
                               if c.value > 0),
            explanation=explanation,
        )

    # AMBIGUOUS when two candidates are equally plausible for the SAME
    # Requirement and differ in substance. Locked Step 28: "LegalMind must not
    # silently choose one."
    ambiguous = _is_ambiguous(qualifying, rules)

    if ambiguous:
        return MappingResult(
            requirement_version_id=requirement_version_id,
            state=MappingState.AMBIGUOUS,
            candidates=tuple(qualifying),
            evidence_ids=tuple(c.clause.evidence_id for c in qualifying),
            explanation=(
                f"{len(qualifying)} candidates within the tie margin "
                f"({rules.tie_margin}); the engine must not choose between them",
            ) + tuple(
                f"candidate {c.clause.section_number or c.clause.evidence_id}: "
                f"score {c.value}" for c in qualifying
            ),
        )

    return MappingResult(
        requirement_version_id=requirement_version_id,
        state=MappingState.CONFIRMED,
        candidates=tuple(qualifying),
        evidence_ids=tuple(c.clause.evidence_id for c in qualifying),
        explanation=tuple(
            f"clause {c.clause.section_number or c.clause.evidence_id} "
            f"score {c.value}: " + "; ".join(c.score.explanation)
            for c in qualifying
        ),
    )


def _is_ambiguous(qualifying: list[Candidate], rules: MappingRules) -> bool:
    """Whether the engine faces a choice it is forbidden to make.

    Multiple qualifying clauses are NOT automatically ambiguous — locked 35.12
    and Step 28 r2 permit one Requirement to be supported by several clauses.
    Ambiguity arises when candidates are tied closely enough that selecting a
    single governing clause would be arbitrary, AND they are not simply
    restatements of one another.
    """
    if len(qualifying) < 2:
        return False
    best = qualifying[0].value
    tied = [c for c in qualifying if best - c.value <= rules.tie_margin]
    if len(tied) < 2:
        return False
    # Materially identical clauses are one position stated twice, not a
    # conflict of candidates (45C.17 for the evaluation layer; the same
    # reasoning applies here).
    distinct = {_fingerprint_clause(c.clause) for c in tied}
    return len(distinct) > 1


def _fingerprint_clause(clause: Clause) -> str:
    import hashlib
    import re
    normalized = re.sub(r"\s+", " ", (clause.content or "").strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()


def map_document(
    requirement_rules: dict[UUID, MappingRules],
    clauses: list[Clause],
) -> dict[UUID, MappingResult]:
    """Map every configured Requirement over one document.

    Locked 35.13: one clause may map to multiple Requirements — each Requirement
    is scored independently over the full clause set, so a clause serving two
    Requirements is claimed by both.
    """
    return {
        rv_id: map_requirement(rv_id, rules, clauses)
        for rv_id, rules in requirement_rules.items()
    }
