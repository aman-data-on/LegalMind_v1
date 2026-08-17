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
              Requirement"           -> one or more clauses reach the threshold
  UNRESOLVED  "The system cannot establish the mapping reliably"
                                     -> nothing reaches the threshold
  NONE        mapping completed, no provision mapped (45D)
                                     -> no clause produced any positive signal

No `CANDIDATE`, `CANDIDATE-REVIEW`, `NOT MAPPED` or `NO_CONFIDENT_MAPPING` value
is produced or persisted. When the band mapping is decided it can be layered on
without revisiting these semantics.

--------------------------------------------------------------------------
Owner decision M-2 — several supporting clauses are CONFIRMED, not AMBIGUOUS
--------------------------------------------------------------------------
An earlier revision treated several qualifying clauses whose scores tied as
`AMBIGUOUS`, reasoning that choosing a single governing clause would be arbitrary.
Two locked rules stand against that:

    Step 28 r2   "One Requirement may be supported by multiple clauses."
    35.12        the same, restated.

If multiple supporting clauses are normal, no single governing clause has to be
chosen — and this function already retains *every* qualifying candidate rather
than picking one, so the arbitrary choice the tie rule guarded against was never
actually made. In practice the rule also mis-fired constantly: a real
three-paragraph liability clause scored 5/5/5 because each paragraph matched one
configured phrase, and the whole Requirement came out `UNABLE_TO_EVALUATE`.

**`CONFIRMED` here means "this Requirement is mapped to these provisions". It
never means the provisions are compliant, consistent with each other, or legally
acceptable.** Those are later questions and this layer does not answer them.

**Contradiction is not assessed here, and must not be.** Locked Step 28 r8 keeps
Requirement mapping separate from Company Standard evaluation, and locked 44.18
places conflict detection at layer 7 — after fact extraction. Contradiction is a
property of *facts*, not of scores or text, so detecting it here would require
facts this layer must not have. Two clauses stating incompatible caps are mapped
as `CONFIRMED`, both retained as evidence, and the evaluator resolves them: same
scope, materially different, no configured precedence -> `CONFLICT`, which is
Tier 1 and requires a Legal Decision (45C.2, 45C.22, 45C.27, D-3.5(b)).

M-2 therefore makes conflict detection *reachable* rather than weaker. Under the
old rule, tied contradictory clauses produced `AMBIGUOUS` -> no facts -> "we could
not tell"; 45C.2's design of retaining every conflicting provision as
`CONFLICTING` evidence was unreachable because the tie fired first.

**Consequence, recorded rather than worked around:** nothing in V1 produces
`MappingState.AMBIGUOUS`. Cross-Requirement ambiguity — one clause plausibly
mapping to two different Requirements — is the case Step 28's wording most
naturally describes, and it is **not implemented**: `map_document` scores each
Requirement independently. The enum value remains because locked Step 28 defines
it and locked 45D's `PRESENCE` table has a row for it; no producer is invented
here.
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

    # M-2 — every qualifying clause supports the Requirement, and all are
    # retained (Step 28 r2, 35.12). Tied scores are not ambiguity: no single
    # governing clause has to be chosen, so nothing arbitrary is being decided.
    #
    # The explanation states explicitly that contradiction was not assessed, so
    # the record cannot be read as a claim this layer did not make.
    supporting = (
        f"{len(qualifying)} clause(s) reached the confirm threshold "
        f"({rules.confirm_threshold}); all are retained as supporting evidence "
        "(Step 28 r2, 35.12)",
        "mapping establishes only that these provisions govern this Requirement "
        "— not that they are consistent with one another or acceptable; "
        "contradiction is assessed by the evaluator (Step 28 r8, 44.18)",
    )
    return MappingResult(
        requirement_version_id=requirement_version_id,
        state=MappingState.CONFIRMED,
        candidates=tuple(qualifying),
        evidence_ids=tuple(c.clause.evidence_id for c in qualifying),
        explanation=supporting + tuple(
            f"clause {c.clause.section_number or c.clause.evidence_id} "
            f"score {c.value}: " + "; ".join(c.score.explanation)
            for c in qualifying
        ),
    )


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
