"""The evidence bundle — roadmap §9 and §14, PHASE 9 (`AM-88`).

    bundle = evidence.build(db, plan, pool, evidence_set)

Retrieval proposes; this decides. Each selected unit is judged on its own, and each
part of the question gets a state:

  SUPPORTED            every source kind the part needs has a supporting source
  PARTIALLY_SUPPORTED  some do, some do not
  CONFLICTING          (vocabulary only — no deterministic detector yet; PHASE 12)
  INSUFFICIENT         nothing supports it
  UNAVAILABLE          the source it needs does not exist here (no document attached,
                       or the reader says the signed copy is missing)

A unit SUPPORTS when all three checks pass, in this order:

  1. AUTHORITY / VERSION / TIME (roadmap §14). An UNRATIFIED passage never supports
     (the Constitution disclaims it itself). A non-CURRENT one — repealed, superseded,
     historical — supports only a HISTORICAL_EXCEPTION part or a question about the
     past. CURRENT is not the same as applicable, but a non-current source is never
     the answer to a current-law question.
  2. RELEVANCE — the cross-encoder's score of the reader's WHOLE question against the
     unit's PARENT CONTEXT (`AM-87` r4), at or above its domain's floor. On the bare
     paragraph the Constitution scores near the model's floor whatever it says; on
     its section it separates (measured, PHASE 9). A Constitution section the reader
     named by number passes on that alone.
  3. DOCUMENTS also need the calibrated document gate on the reader's own question:
     on the held-out Tier-2 set the cross-encoder alone kept 31 of 64 answerable where
     the gate keeps 44, and both together keep 43 while refusing 12 of 13.

Embedding similarity therefore never decides answerability on its own (`AM-84` r4).
A reader's assertion is never evidence (`AM-78`): it is recorded apart, with whether
any supporting source states its figure. No model is called here beyond the local
cross-encoder; no Gemini.
"""
from __future__ import annotations

from dataclasses import dataclass

from legalmind.assist import guardrails, query_plan, retrieval, routing
from legalmind.assist.retrieval import CONSTITUTION, Candidate, Pool, kind_of

SUPPORTED, PARTIALLY_SUPPORTED, CONFLICTING = ("SUPPORTED", "PARTIALLY_SUPPORTED",
                                               "CONFLICTING")
INSUFFICIENT, UNAVAILABLE = "INSUFFICIENT", "UNAVAILABLE"
STATES = (SUPPORTED, PARTIALLY_SUPPORTED, CONFLICTING, INSUFFICIENT, UNAVAILABLE)

#: Cross-encoder floors on (question, parent context), per domain. Calibrated on the
#: PHASE 0 benchmark (`tests/assist_eval/sufficiency_calibration_2026-09-25.json`); the
#: document floor on the held-out Tier-2 77. Round numbers, not fitted to a case.
RELEVANCE_FLOOR = {
    CONSTITUTION: -4.0,
    routing.Domain.POSITIONS.value: -4.0,
    routing.Domain.STATUTES.value: -2.0,
    routing.Domain.DOCUMENT.value: -6.0,
}

_EVIDENCE_LANES = (query_plan.COMPANY_POSITION, query_plan.CONTRACT, query_plan.LAW,
                   query_plan.HISTORICAL_EXCEPTION)


@dataclass(frozen=True)
class Source:
    kind: str
    candidate: Candidate
    context: str
    relevance: float | None
    supports: bool
    #: Why a unit does NOT support — None when it does.
    reason: str | None

    @property
    def ref(self) -> str:
        return self.candidate.ref


@dataclass(frozen=True)
class Part:
    question: str
    lanes: tuple[str, ...]
    state: str
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class Assertion:
    """Something the reader or a third party ASSERTS — context, never evidence."""
    text: str
    figures: tuple[str, ...]
    #: The asserted figures no supporting COMPANY POSITION states — "is 6 months our
    #: policy?" (`guardrails.unstated_figures`, `AM-78`).
    unstated: tuple[str, ...]
    #: The source kinds whose supporting sources DO state one of them — "6 months"
    #: found only in a historical exception is history, never policy.
    stated_by: tuple[str, ...]


@dataclass(frozen=True)
class Bundle:
    parts: tuple[Part, ...]
    #: Every judged unit, in evidence order — a source found by the whole question
    #: counts even when no single part's lanes name it.
    sources: tuple[Source, ...]
    assertions: tuple[Assertion, ...]
    #: The controlling paper the reader says is missing, or that is not attached.
    missing_document: bool

    @property
    def answerable(self) -> bool:
        return any(p.state in (SUPPORTED, PARTIALLY_SUPPORTED, CONFLICTING)
                   for p in self.parts)

    def shown(self) -> list[Source]:
        """Every supporting source, in evidence order — what generation may see.
        Nothing when no part is answerable: a refusal shows no evidence."""
        return [s for s in self.sources if s.supports] if self.answerable else []


def _judge(c: Candidate, context: str, relevance: float | None, *,
           plan: query_plan.QueryPlan, pool: Pool, named: set[str]) -> str | None:
    """None when the unit supports; otherwise the first check it fails."""
    if c.status == "UNRATIFIED":
        return "UNRATIFIED"
    kind = kind_of(c)
    if (c.status != "CURRENT" and kind != query_plan.HISTORICAL_EXCEPTION
            and not plan.understood.temporal.wants_past):
        return "NOT_CURRENT"
    if c.domain == CONSTITUTION and c.ref.removeprefix("CONST:") in named:
        return None
    if relevance is None:
        return "RELEVANCE_UNAVAILABLE"        # fail closed: no reranker, no support
    if relevance < RELEVANCE_FLOOR.get(c.domain, float("inf")):
        return "NOT_RELEVANT"
    if c.domain == routing.Domain.DOCUMENT.value and not pool.document_gate:
        return "DOCUMENT_GATE_CLOSED"
    return None


def build(db, plan: query_plan.QueryPlan, pool: Pool,
          selected: list[Candidate]) -> Bundle:
    from legalmind.assist import rerank as cross_encoder

    evidence = retrieval.with_context(db, selected)
    # Scored against the whole question AND each sub-question's query, keeping the
    # best: a sub-query carries the planner's English topic subject, which is what a
    # Hinglish question or a follow-up turn ("what if they say 6 months?") lacks.
    contexts = [e.context for e in evidence]
    runs = [cross_encoder.scores(q, contexts) for q in
            dict.fromkeys([plan.question, *(s.query for s in plan.sub_questions)])]
    scores = [max(r[i] for r in runs if r) for i in range(len(contexts))] \
        if all(runs) else []
    named = set(retrieval.named_sections(plan.question))
    sources = [Source(kind_of(e.candidate), e.candidate, e.context,
                      scores[i] if scores else None,
                      (reason := _judge(e.candidate, e.context,
                                        scores[i] if scores else None,
                                        plan=plan, pool=pool, named=named)) is None,
                      reason)
               for i, e in enumerate(evidence)]
    no_document = plan.document_state == "UNAVAILABLE"
    parts = []
    for sub in plan.sub_questions:
        needed = [lane for lane in sub.lanes if lane in _EVIDENCE_LANES]
        mine = tuple(s for s in sources
                     if not needed or not s.candidate.lanes
                     or any(lane in s.candidate.lanes for lane in needed))
        parts.append(Part(sub.text, sub.lanes, _state(needed, mine, no_document), mine))
    def unstated(claim: str, kind: str) -> list[str]:
        return guardrails.unstated_figures(claim, [
            s.candidate.text for s in sources if s.supports and s.kind == kind])
    assertions = []
    for claim in plan.claims:
        figs = tuple(f for f in plan.figures if f in claim.lower())
        stated_by = tuple(k for k in _EVIDENCE_LANES
                          if figs and len(unstated(claim, k)) < len(figs))
        assertions.append(Assertion(claim, figs, tuple(
            unstated(claim, query_plan.COMPANY_POSITION)), stated_by))
    return Bundle(tuple(parts), tuple(sources), tuple(assertions), no_document)


def _state(needed: list[str], sources: tuple[Source, ...], no_document: bool) -> str:
    if not needed:
        return SUPPORTED if any(s.supports for s in sources) else INSUFFICIENT
    unavailable = {query_plan.CONTRACT} if no_document else set()
    covered = {lane for lane in needed
               if any(s.supports and s.kind == lane for s in sources)}
    open_lanes = [lane for lane in needed if lane not in unavailable]
    if open_lanes and all(lane in covered for lane in open_lanes):
        return SUPPORTED
    if covered:
        return PARTIALLY_SUPPORTED
    return UNAVAILABLE if not open_lanes else INSUFFICIENT
