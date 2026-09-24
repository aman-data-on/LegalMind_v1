"""Broad, plan-driven candidate retrieval — roadmap §7, PHASE 7 (`AM-86`).

    pool = retrieval.candidates(db, plan, route, permissions=..., document_version_id=...)
    evidence = retrieval.select(pool, plan)

From the PHASE 6 plan to a candidate pool, then a diverse evidence set:

  1. DOMAINS come from the router (`routing.plan`: permissions first, `AM-45` r1) — the
     Constitution rides on the positions permission (`AM-79` r2). A lane asks for a
     domain; it is searched only if the router authorized it.
  2. Each sub-question's query, and the whole question, is searched in every domain its
     lanes name, at DEPTH, in CANDIDATE mode: lexical and dense fused, dense ungated —
     similarity produces candidates and decides nothing (`AM-84` r4).
  3. An EXACT-REFERENCE lane: a Constitution section the reader names ("§14",
     "section 31.2 of the Constitution") is fetched by its own number.
  4. Per domain, the lists are fused by reciprocal rank and deduplicated by SOURCE
     (a Constitution section, a standard, an Act section, a document chunk) — one
     parent never takes two places. Domains are never merged into one list (`AM-32` r1).
  5. `select` takes the evidence set diversity-first: every (sub-question, lane) gets its
     best candidate before any gets a second, so five similar standards cannot displace
     the statute or the historical record a part of the question needs (roadmap §7).

Nothing here decides whether the evidence suffices — that is PHASES 8–9.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from legalmind.assist import (
    calibration,
    constitution,
    positions,
    query_plan,
    routing,
    store,
)
from legalmind.assist import statutes as statute_corpus

DEPTH = 50
CONSTITUTION = "CONSTITUTION"
LANE_DOMAINS: dict[str, tuple[str, ...]] = {
    query_plan.COMPANY_POSITION: (CONSTITUTION, routing.Domain.POSITIONS.value),
    query_plan.HISTORICAL_EXCEPTION: (CONSTITUTION,),
    query_plan.LAW: (routing.Domain.STATUTES.value, CONSTITUTION),
    query_plan.CONTRACT: (routing.Domain.DOCUMENT.value,),
}
# The router's domains, in pool terms — the Constitution rides with the positions.
ROUTE_DOMAINS: dict[str, tuple[str, ...]] = {
    routing.Domain.POSITIONS.value: (CONSTITUTION, routing.Domain.POSITIONS.value),
    routing.Domain.STATUTES.value: (routing.Domain.STATUTES.value,),
    routing.Domain.DOCUMENT.value: (routing.Domain.DOCUMENT.value,),
}
DOMAIN_LANE = {CONSTITUTION: query_plan.COMPANY_POSITION,
               routing.Domain.POSITIONS.value: query_plan.COMPANY_POSITION,
               routing.Domain.STATUTES.value: query_plan.LAW,
               routing.Domain.DOCUMENT.value: query_plan.CONTRACT}
_CONST_REF = re.compile(r"(?:§\s*|section\s+)(\d+(?:\.\d+)*[a-z]?)\b[^?.]{0,40}?"
                        r"\bconstitution\b|\bconstitution\b[^?.]{0,40}?"
                        r"(?:§\s*|section\s+)(\d+(?:\.\d+)*[a-z]?)", re.I)


@dataclass(frozen=True)
class Candidate:
    domain: str
    ref: str
    item_id: UUID
    text: str
    score: float
    authority: str = ""
    status: str = "CURRENT"
    lanes: tuple[str, ...] = ()


@dataclass
class Pool:
    by_domain: dict[str, list[Candidate]] = field(default_factory=dict)
    searched: set[str] = field(default_factory=set)
    #: The router's PRIMARY domains in pool terms — where an unplaced question's
    #: evidence may come from, exactly as today's path answers it.
    primary: set[str] = field(default_factory=set)

    def refs(self) -> list[str]:
        return [c.ref for cs in self.by_domain.values() for c in cs]


def _authorized(route: routing.RoutePlan, permissions: frozenset[str]) -> set[str]:
    domains = {d.value for d in (*route.domains, *route.fallback)}
    if positions.can_read(permissions):
        domains.add(CONSTITUTION)
    return domains


def _search(db, domain: str, query: str, *, permissions, route, document_version_id,
            embed_query) -> list[Candidate]:
    if domain == CONSTITUTION:
        return [Candidate(domain, f"CONST:{h.section_path}", h.item_id, h.content,
                          h.score, h.authority, h.status)
                for h in constitution.search(db, query=query, permissions=permissions,
                                             limit=DEPTH, embed_query=embed_query)]
    if domain == routing.Domain.POSITIONS.value:
        return [Candidate(domain, f"POS:{h.standard_code}", h.position_chunk_id,
                          h.content, h.score, "COMPANY_STANDARD")
                for h in positions.search_positions(
                    db, query=query, permissions=permissions, limit=DEPTH,
                    embed_query=embed_query, candidates=True)]
    if domain == routing.Domain.STATUTES.value:
        return [Candidate(domain, f"STAT:{h.official_title.removeprefix('The ')}:"
                                  f"{h.section_number}", h.statute_chunk_id, h.content,
                          h.score, "PRIMARY_LAW")
                for h in statute_corpus.search_statutes(
                    db, query=query, permissions=permissions, limit=DEPTH,
                    embed_query=embed_query, candidates=True,
                    include_superseded=route.include_superseded)]
    if domain == routing.Domain.DOCUMENT.value and document_version_id is not None:
        outcome = store.search_hybrid(db, document_version_id=document_version_id,
                                      query=query, limit=DEPTH, candidates=True,
                                      embed_query=embed_query)
        return [Candidate(domain, f"DOC:{h.chunk_id}", h.chunk_id, h.content,
                          h.retrieval_score, "DOCUMENT") for h in outcome.hits]
    return []


def candidates(db, plan: query_plan.QueryPlan, route: routing.RoutePlan, *,
               permissions: frozenset[str], document_version_id: UUID | None = None,
               embed_query=None) -> Pool:
    from legalmind.assist import embedding_runtime

    embed_query = embed_query or embedding_runtime.embed_query
    allowed = _authorized(route, permissions)
    pool = Pool(primary={d for routed in route.domains
                         for d in ROUTE_DOMAINS.get(routed.value, ())})
    fused: dict[str, dict[str, float]] = {}
    best: dict[str, dict[str, Candidate]] = {}
    jobs: list[tuple[str, str, tuple[str, ...]]] = []
    for sub in plan.sub_questions:
        for lane in sub.lanes:
            for domain in LANE_DOMAINS.get(lane, ()):
                jobs.append((domain, sub.query, (lane,)))
    # The whole question is searched too, in every authorized domain its lanes reach —
    # a decomposition must be able to add recall, never remove it — and always in the
    # router's own primary domains, so a question the plan cannot place (no lane:
    # "How many years must KYC records be kept?") is searched exactly where today's
    # path searches it.
    for domain in {d for lane in plan.lanes for d in LANE_DOMAINS.get(lane, ())}:
        jobs.append((domain, plan.question, tuple(sorted(plan.lanes))))
    # The fallback domains too: the pool is RECALL, and today's path consults them
    # when the primary route is silent (`service._consult_fallbacks`). What reaches
    # the reader is still chosen by `select` from the plan's lanes, then by PHASE 8.
    for routed in (*route.domains, *route.fallback):
        for domain in ROUTE_DOMAINS.get(routed.value, ()):
            jobs.append((domain, plan.question, (DOMAIN_LANE[domain],)))
    seen: set[tuple[str, str]] = set()
    for domain, query, lanes in jobs:
        if domain not in allowed or (domain, query) in seen:
            continue
        seen.add((domain, query))
        pool.searched.add(domain)
        for rank, c in enumerate(_search(db, domain, query, permissions=permissions,
                                         route=route,
                                         document_version_id=document_version_id,
                                         embed_query=embed_query), 1):
            scores = fused.setdefault(domain, {})
            scores[c.ref] = scores.get(c.ref, 0.0) + 1 / (calibration.RRF_K + rank)
            kept = best.setdefault(domain, {})
            prior = kept.get(c.ref)
            merged = tuple(sorted({*lanes, *(prior.lanes if prior else ())}))
            kept[c.ref] = Candidate(c.domain, c.ref, c.item_id, c.text, c.score,
                                    c.authority, c.status, merged)
    # 3 — exact reference: a Constitution section named by number goes first.
    named = [a or b for a, b in _CONST_REF.findall(plan.question)]
    if named and CONSTITUTION in allowed:
        for section in named:
            ref = f"CONST:{section}"
            hit = constitution.item_for_section(db, section)
            if hit is not None:
                fused.setdefault(CONSTITUTION, {})[ref] = 1.0
                best.setdefault(CONSTITUTION, {}).setdefault(
                    ref, Candidate(CONSTITUTION, ref, hit[0], hit[1] or "", 1.0,
                                   "COMPANY_CONSTITUTION", "CURRENT",
                                   (query_plan.COMPANY_POSITION,)))
        pool.searched.add(CONSTITUTION)
    for domain, scores in fused.items():
        pool.by_domain[domain] = [best[domain][r] for r in
                                  sorted(scores, key=lambda r: -scores[r])][:DEPTH]
    return pool


def evidence_size(plan: query_plan.QueryPlan) -> int:
    """5–12 units, growing with the number of things asked (roadmap §7)."""
    return max(5, min(12, 3 * len(plan.sub_questions)))


def select(pool: Pool, plan: query_plan.QueryPlan,
           k: int | None = None) -> list[Candidate]:
    """Diversity first: one round per (sub-question, lane, domain) before any second."""
    k = k or evidence_size(plan)
    wanted: list[tuple[str | None, str]] = [
        (lane, d) for sub in plan.sub_questions for lane in sub.lanes
              for d in LANE_DOMAINS.get(lane, ()) if d in pool.by_domain]
    # An unplaced question (no lane) takes evidence only from the router's primary
    # domains; the fallback domains stay in the pool as recall, not as an answer.
    wanted = list(dict.fromkeys(wanted)) or [(None, d) for d in pool.by_domain
                                             if d in pool.primary]
    taken: list[Candidate] = []
    refs: set[str] = set()
    depth = 0
    while len(taken) < k and depth < DEPTH:
        progressed = False
        for lane, domain in wanted:
            ranked = [c for c in pool.by_domain[domain]
                      if c.ref not in refs and (lane is None or lane in c.lanes
                                                or not c.lanes)]
            if not ranked:
                continue
            taken.append(ranked[0])
            refs.add(ranked[0].ref)
            progressed = True
            if len(taken) == k:
                break
        depth += 1
        if not progressed:
            break
    return taken
