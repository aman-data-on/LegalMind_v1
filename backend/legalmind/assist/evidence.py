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

from dataclasses import dataclass, field

from legalmind.assist import guardrails, query_plan, retrieval, routing
from legalmind.assist import presentation as presentation_mod
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
    #: The reader named this very section — a Constitution section by number, or a
    #: section of a named Act. It leads its kind in the answer (`AM-107`).
    named: bool = False

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
    #: `AM-108`: the reader's presentation instruction, carried to the claims and the
    #: answer so they can be shaped to it; never a source of evidence.
    presentation: presentation_mod.Presentation = field(
        default_factory=lambda: presentation_mod.Presentation())

    @property
    def answerable(self) -> bool:
        return any(p.state in (SUPPORTED, PARTIALLY_SUPPORTED, CONFLICTING)
                   for p in self.parts)

    def shown(self) -> list[Source]:
        """Every supporting source, in evidence order — what generation may see.
        Nothing when no part is answerable: a refusal shows no evidence."""
        return [s for s in self.sources if s.supports] if self.answerable else []


def _judge(c: Candidate, context: str, relevance: float | None, *,
           plan: query_plan.QueryPlan, pool: Pool, named: set[str],
           absent: bool = False) -> str | None:
    """None when the unit supports; otherwise the first check it fails."""
    if c.status == "UNRATIFIED":
        return "UNRATIFIED"
    kind = kind_of(c)
    if (c.status != "CURRENT" and kind != query_plan.HISTORICAL_EXCEPTION
            and not plan.understood.temporal.wants_past):
        return "NOT_CURRENT"
    if c.domain == CONSTITUTION and c.ref.removeprefix("CONST:") in named:
        return None
    if c.domain == routing.Domain.STATUTES.value and retrieval.names_other_act(c, plan):
        return "WRONG_ACT"
    if c.domain == routing.Domain.STATUTES.value and absent:
        return "NAMED_SECTION_ABSENT"
    if retrieval.exact_reference(c, plan):
        return None                 # the reader named this section of this Act
    if c.domain == routing.Domain.POSITIONS.value and off_topic(c, plan.question):
        return "OFF_TOPIC"
    if relevance is None:
        return "RELEVANCE_UNAVAILABLE"        # fail closed: no reranker, no support
    if c.domain == routing.Domain.DOCUMENT.value:
        # The reader's own document is admitted by ITS gate — calibrated on these
        # clauses, or reopened by the rescue judge — exactly as the previous path
        # admits it; the claim contracts and the verifier still decide every
        # sentence. The web-trained cross-encoder scores lay questions against
        # contract drafting at -5 to -11, so its floor rejected gold clauses the
        # gate had opened for (2026-09-28, `AM-106`); it still ORDERS them.
        if c.ref.startswith("ATT:"):
            return None if pool.material_gate else "MATERIAL_GATE_CLOSED"
        return None if pool.document_gate else "DOCUMENT_GATE_CLOSED"
    if relevance < RELEVANCE_FLOOR.get(c.domain, float("inf")):
        return "NOT_RELEVANT"
    return None


def build(db, plan: query_plan.QueryPlan, pool: Pool,
          selected: list[Candidate]) -> Bundle:
    from legalmind.assist import rerank as cross_encoder

    evidence = retrieval.with_context(db, selected)
    absent = retrieval.named_section_absent(pool, plan)
    # Scored against the whole question AND each sub-question's query, keeping the
    # best: a sub-query carries the planner's English topic subject, which is what a
    # Hinglish question or a follow-up turn ("what if they say 6 months?") lacks.
    contexts = [e.context for e in evidence]
    from legalmind.assist.statutes import with_agency_names
    runs = [cross_encoder.scores(with_agency_names(q), contexts) for q in
            dict.fromkeys([plan.question, *(s.query for s in plan.sub_questions)])]
    scores = [max(r[i] for r in runs if r) for i in range(len(contexts))] \
        if all(runs) else []
    if scores and plan.language != "en":
        # … but the sub-query is subject + the reader's own Roman-Hindi words, and the
        # English cross-encoder scores those as noise: K-02 ("hamara liability cap
        # kitna hai?") had §9 and LIABILITY-MSA-001 ranked first and rejected both
        # (PHASE 13). The subject ALONE — the planner's topic phrase, read
        # deterministically from the reader's words — is scored too, and counts only
        # for a source of a KIND the plan asked for: scored for every kind it admitted
        # the Copyright Act's licence-termination section to a data-retention question.
        subjects = list(dict.fromkeys(s.subject for s in plan.sub_questions if s.subject))
        for run in (cross_encoder.scores(q, contexts) for q in subjects):
            if run:
                scores = [max(x, run[i]) if kind_of(evidence[i].candidate) in plan.lanes
                          else x for i, x in enumerate(scores)]
    named = set(retrieval.named_sections(plan.question))
    sources = [Source(kind_of(e.candidate), e.candidate, e.context,
                      scores[i] if scores else None,
                      (reason := _judge(e.candidate, e.context,
                                        scores[i] if scores else None,
                                        plan=plan, pool=pool, named=named,
                                        absent=absent)) is None,
                      reason,
                      (e.candidate.domain == CONSTITUTION
                       and e.candidate.ref.removeprefix("CONST:") in named)
                      or retrieval.exact_reference(e.candidate, plan))
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
    return Bundle(tuple(parts), tuple(sources), tuple(assertions), no_document,
                  plan.presentation)


def off_topic(c: Candidate, question: str) -> bool:
    """A ratified standard whose Constitution topic is none of the topics the
    question's own words place is not evidence for it, however alike the wording: the
    §9 12-month LIABILITY cap passed the relevance floor for "do we charge 12 months
    of fees on early exit?" (golden GT-03's trap) once more evidence was selected
    (PHASE 13). A question the vocabulary places nowhere is never filtered, and a
    standard whose OWN text addresses an asked topic stays: the suspension-cure
    standard is filed under Payment Terms yet answers "can we suspend without the
    cure period?" (golden G-03)."""
    from legalmind.assist import planner
    asked = planner.topics_in(question)
    topic = planner.STANDARD_TOPICS.get(c.ref.removeprefix("POS:"))
    return (bool(asked) and topic is not None and topic not in asked
            and not planner.topics_in(c.text) & asked)


def _state(needed: list[str], sources: tuple[Source, ...], no_document: bool) -> str:
    if not needed:
        return SUPPORTED if any(s.supports for s in sources) else INSUFFICIENT
    unavailable = {query_plan.CONTRACT} if no_document else set()
    covered = {lane for lane in needed
               if any(s.supports and lane in retrieval.kinds_of(s.candidate)
                      for s in sources)}
    open_lanes = [lane for lane in needed if lane not in unavailable]
    if open_lanes and all(lane in covered for lane in open_lanes):
        return SUPPORTED
    if covered:
        return PARTIALLY_SUPPORTED
    return UNAVAILABLE if not open_lanes else INSUFFICIENT
