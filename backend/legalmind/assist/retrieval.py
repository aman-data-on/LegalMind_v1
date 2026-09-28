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

import dataclasses
import re
from dataclasses import dataclass, field
from uuid import UUID

from legalmind.assist import (
    authority,
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


def named_sections(question: str) -> list[str]:
    """Constitution sections the reader names by number ("§14", "section 31.2 of the
    Constitution") — the exact-reference lane."""
    return [a or b for a, b in _CONST_REF.findall(question)]


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
    #: The cross-encoder's relevance to the reader's whole question (PHASE 8);
    #: None when not reranked. Orders evidence; never shown, never a verdict.
    relevance: float | None = None
    #: Every authority among the source's matching records (a Constitution section's
    #: children), when the search reports them; empty otherwise. `kinds_of`.
    authorities: tuple[str, ...] = ()
    #: A statute section's marginal note (its title), scored with the chunk by the
    #: cross-encoder: s. 73's best-matching chunk is an illustration about cargo, and
    #: without its title the Contract Act's damages section ranked below unrelated Acts
    #: (golden E-01, GT-11). Never shown; the evidence text is unchanged.
    note: str = ""


@dataclass
class Pool:
    by_domain: dict[str, list[Candidate]] = field(default_factory=dict)
    searched: set[str] = field(default_factory=set)
    #: The router's PRIMARY domains in pool terms — where an unplaced question's
    #: evidence may come from, exactly as today's path answers it.
    primary: set[str] = field(default_factory=set)
    #: The calibrated document gate on the reader's OWN question (never a sub-question
    #: or a rephrasing) — one of the signals PHASE 9's sufficiency combines (`AM-88`).
    document_gate: bool | None = None

    def refs(self) -> list[str]:
        return [c.ref for cs in self.by_domain.values() for c in cs]


def _authorized(route: routing.RoutePlan, permissions: frozenset[str]) -> set[str]:
    domains = {d.value for d in (*route.domains, *route.fallback)}
    if positions.can_read(permissions):
        domains.add(CONSTITUTION)
    return domains


def _search(db, domain: str, query: str, *, permissions, route, document_version_id,
            embed_query, pool: Pool | None = None, question: str = "",
            pinned_evidence: tuple[UUID, ...] = (), outline: bool = False
            ) -> list[Candidate]:
    if domain == CONSTITUTION:
        return [Candidate(domain, f"CONST:{h.section_path}", h.item_id, h.content,
                          h.score, h.authority, h.status, authorities=h.authorities)
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
                          h.score, *authority.of_statute(h.official_title),
                          note=h.marginal_note or "")
                for h in statute_corpus.search_statutes(
                    db, query=query, permissions=permissions, limit=DEPTH,
                    embed_query=embed_query, candidates=True,
                    include_superseded=route.include_superseded)]
    if domain == routing.Domain.DOCUMENT.value and document_version_id is not None:
        if outline:
            # A whole-document task names nothing to search for: the document's
            # outline IS the subject, and the gate is open for it — the claim
            # contracts and the verifier still decide every sentence (`AM-108`).
            from legalmind.assist import planner
            if pool is not None:
                pool.document_gate = True
            sections = store.outline_chunks(db, document_version_id=document_version_id,
                                            limit=DEPTH)
            # Sections on a topic the organization holds a position on first (its own
            # vocabulary, `planner.topics_in`), then the rest in document order — so
            # a 21-section agreement's summary is its terms, not its definitions.
            sections.sort(key=lambda h: not planner.topics_in(h.content))
            return [Candidate(domain, f"DOC:{h.chunk_id}", h.chunk_id, h.content,
                              h.retrieval_score, "DOCUMENT") for h in sections]
        outcome = store.search_hybrid(db, document_version_id=document_version_id,
                                      query=query, limit=DEPTH, candidates=True,
                                      embed_query=embed_query)
        hits = outcome.hits
        if pool is not None and query == question:
            # The gate decides on the reader's own question, and gets the same two
            # openings today's path gives it (`service.retrieve_document`): a
            # Finding's cited clauses, already recorded against this version, and the
            # rescue judge's second look at a SHUT gate, over the question's own top-K
            # as it was calibrated. Neither admits anything past the judge, the claim
            # contracts or the verifier. Without them 14 of 44 ratified document
            # questions lost their clause at the gate (2026-09-28).
            gate = outcome.gate_open
            pinned = store.chunks_for_evidence(
                db, document_version_id=document_version_id,
                evidence_ids=list(pinned_evidence),
                limit=len(pinned_evidence)) if pinned_evidence else []
            if not gate and not pinned:
                from legalmind.assist import rescue
                refused = dataclasses.replace(
                    outcome, hits=[], candidates=hits[:calibration.RETRIEVAL_TOP_K])
                second = rescue.reconsider(refused, question)
                if second.gate_open:
                    gate, pinned = True, list(second.hits)
            if pinned:
                seen = {h.chunk_id for h in pinned}
                gate, hits = True, [*pinned, *[h for h in hits if h.chunk_id not in seen]]
            pool.document_gate = gate
        return [Candidate(domain, f"DOC:{h.chunk_id}", h.chunk_id, h.content,
                          h.retrieval_score, "DOCUMENT") for h in hits]
    return []


def candidates(db, plan: query_plan.QueryPlan, route: routing.RoutePlan, *,
               permissions: frozenset[str], document_version_id: UUID | None = None,
               embed_query=None, pinned_evidence: tuple[UUID, ...] = ()) -> Pool:
    from legalmind.assist import embedding_runtime

    lexical_only = embed_query is None and not embedding_runtime.available()
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
                # With no vectors, its topic phrase alone as well: lexical-only, "early
                # exit fixed-term commitment What if the customer says they were
                # promised 6 months?" ranked §27 and §31.15 above §14 on "customer" and
                # "months", and a follow-up lost its topic (roadmap §15; CI has no
                # model). With vectors the extra list costs recall — measured 0.952 →
                # 0.893 (PR #121) — so it runs only in the degraded mode it repairs.
                if lexical_only and sub.subject:
                    jobs.append((domain, sub.subject, (lane,)))
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
        listed: set[str] = set()
        for rank, c in enumerate(_search(db, domain, query, permissions=permissions,
                                         route=route,
                                         document_version_id=document_version_id,
                                         embed_query=embed_query, pool=pool,
                                         question=plan.question,
                                         pinned_evidence=pinned_evidence,
                                         outline=plan.presentation.document_wide), 1):
            # A source counts once per list, at its best rank: §18's four sub-headings
            # share one section number, and summing them put four long sections above
            # §4.1 for "under which Companies Act was Leapswitch incorporated?" (H-01).
            if c.ref in listed:
                continue
            listed.add(c.ref)
            scores = fused.setdefault(domain, {})
            scores[c.ref] = scores.get(c.ref, 0.0) + 1 / (calibration.RRF_K + rank)
            kept = best.setdefault(domain, {})
            prior = kept.get(c.ref)
            merged = tuple(sorted({*lanes, *(prior.lanes if prior else ())}))
            kept[c.ref] = dataclasses.replace(c, lanes=merged)
    # 3 — exact reference: a Constitution section named by number goes first.
    named = named_sections(plan.question)
    if named and CONSTITUTION in allowed:
        for section in named:
            ref = f"CONST:{section}"
            hit = constitution.item_for_section(db, section, permissions=permissions)
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


RERANK_DEPTH = 30
#: Where the cross-encoder earns its place, measured (PHASE 8, `AM-87`): statutes and
#: documents — prose it reads well. NOT the Constitution or the positions: on short
#: company positions it promoted the 12-month liability cap for a 12-month early-exit
#: question, raising the golden wrong-source rate 0 → 0.143 in every variant tried.
RERANK_DOMAINS = frozenset({routing.Domain.STATUTES.value, routing.Domain.DOCUMENT.value})


def rerank(pool: Pool, plan: query_plan.QueryPlan) -> Pool:
    """PHASE 8 (`AM-87`): the cross-encoder reorders the top RERANK_DEPTH of each
    RERANK_DOMAINS pool by relevance to the reader's WHOLE question (scoring each
    sub-question and keeping the best was measured worse — it rewards a passage for
    matching any fragment). Then version before relevance: a non-current source sorts
    behind every current one unless the question asks about the past (roadmap §14).
    Membership never changes; the tail keeps its fused order; with no reranker the pool
    is returned as it is."""
    from legalmind.assist import rerank as cross_encoder

    reranked: dict[str, list[Candidate]] = {}
    for domain, cands in pool.by_domain.items():
        head, tail = cands[:RERANK_DEPTH], cands[RERANK_DEPTH:]
        scores = (cross_encoder.scores(statute_corpus.with_agency_names(plan.question),
                                       [f"{c.note}. {c.text}" if c.note
                                                        else c.text for c in head])
                  if domain in RERANK_DOMAINS else None)
        if scores is None:
            reranked[domain] = cands
            continue
        order = sorted(range(len(head)), key=lambda i: -scores[i])
        # Version before relevance: a cross-encoder cannot see that s. 291 of the
        # REPEALED Companies Act, 1956 is not the law on board powers today.
        if not plan.understood.temporal.wants_past:
            order.sort(key=lambda i: head[i].status != "CURRENT")
        order.sort(key=lambda i: not exact_reference(head[i], plan))
        reranked[domain] = [dataclasses.replace(head[i], relevance=scores[i])
                            for i in order] + tail
    return Pool(by_domain=reranked, searched=pool.searched, primary=pool.primary,
                document_gate=pool.document_gate)


def _asked(plan: query_plan.QueryPlan) -> str:
    return f" {statute_corpus.expand_aliases(plan.question)} "


def _is_named_act(c: Candidate, asked: str) -> bool:
    title = c.ref.split(":", 1)[1].rsplit(":", 1)[0].lower()
    # Drop the registry's provenance suffixes ("(REPEALED …)", "— as enacted").
    title = title.split(" (")[0].split(" \u2014 ")[0]
    words = [w for w in title.replace(",", "").split()
             if w not in {"the", "act", "rules", "of", "and", "code", "directions"}
             and not w.isdigit()]
    return bool(words) and all(w in asked for w in words)


def _names_an_act(asked: str) -> bool:
    return any(a in asked for a in ("act", "rules", "adhiniyam", "code", "directions"))


def names_other_act(c: Candidate, plan: query_plan.QueryPlan) -> bool:
    """Roadmap §7/§14 (PHASE 13, `AM-94`): a question naming a section OF a named Act
    is answered only by that Act — "section 194J of the Income-tax Act, 1961" (a
    section the supplied text predates) was answered by the CGST Act."""
    if not plan.section_hint or c.domain != routing.Domain.STATUTES.value:
        return False
    asked = _asked(plan)
    return _names_an_act(asked) and not _is_named_act(c, asked)


def exact_reference(c: Candidate, plan: query_plan.QueryPlan) -> bool:
    """The reader named this very section of this very Act (roadmap §7's exact-
    reference retrieval). Search ranks it first; the cross-encoder, reading "section
    74" in the question but not in the section's text, demoted s. 74 of the Contract
    Act to tenth (golden A-04, PHASE 13) — so it sorts first after the rerank and the
    evidence judge takes it as named, as it does a named Constitution section."""
    if not plan.section_hint or c.domain != routing.Domain.STATUTES.value:
        return False
    asked = _asked(plan)
    return (c.ref.rsplit(":", 1)[-1].lower() == plan.section_hint.lower()
            and _names_an_act(asked) and _is_named_act(c, asked))


def named_section_absent(pool: Pool, plan: query_plan.QueryPlan) -> bool:
    """The reader named a section of a named Act and no candidate IS that section:
    "section 194J of the Income-tax Act, 1961" against a text that predates s. 194J.
    Another section of the Act cannot say what the named one said (PHASE 13, H-02)."""
    if not plan.section_hint or not _names_an_act(_asked(plan)):
        return False
    return not any(exact_reference(c, plan)
                   for c in pool.by_domain.get(routing.Domain.STATUTES.value, []))


def kind_of(c: Candidate) -> str:
    """Which of roadmap §9's distinctions a source IS — from its domain and its own
    authority label, never from the lane that found it (PHASE 9, `AM-88`)."""
    if c.domain == routing.Domain.DOCUMENT.value:
        return query_plan.CONTRACT
    if c.domain == routing.Domain.STATUTES.value or c.authority == "SECONDARY_REFERENCE":
        return query_plan.LAW
    if c.authority == "HISTORICAL_EXCEPTION":
        return query_plan.HISTORICAL_EXCEPTION
    return query_plan.COMPANY_POSITION


def kinds_of(c: Candidate) -> set[str]:
    """Every kind the source can serve: its own (`kind_of`) and one per further
    authority its matching records hold. PHASE 13 (`AM-94`): before this, §31.2 —
    the golden question's historical-exception source — was a COMPANY_POSITION
    candidate because its best-matching child was the position paragraph, so the
    history lane could never take it and §31.15's renewal deals were shown as the
    early-termination history instead. Labelling (`kind_of`) is unchanged."""
    return {kind_of(c)} | {kind_of(dataclasses.replace(c, authority=a))
                           for a in c.authorities}


def evidence_size(plan: query_plan.QueryPlan) -> int:
    """8–12 units selected, growing with the number of things asked (roadmap §7) — the
    evidence judge then decides what is shown. Measured 2026-09-27 (79 golden cases,
    zero Gemini): a floor of 5 lost gold ranked 3rd–5th in its domain (recall@3
    0.815); 8 reaches 0.864 with wrong-source and false admission at 0 once off-topic
    standards are judged out (`evidence.off_topic`), the median shown unchanged at
    3, +~250 ms in the evidence layer and +~20% prompt tokens; 10 gained nothing more."""
    if plan.presentation.document_wide:
        return 12                     # the document's sections, as many as fit
    return max(8, min(12, 3 * len(plan.sub_questions)))


def select(pool: Pool, plan: query_plan.QueryPlan,
           k: int | None = None) -> list[Candidate]:
    """Diversity first: one round per (sub-question, lane, domain) before any second."""
    k = k or evidence_size(plan)
    # Every sub-question's lanes, then the lanes only a CONTEXT sentence opened ("the
    # client says their signed MSA …" opens the historical record) — each gets a round.
    lanes = [lane for sub in plan.sub_questions for lane in sub.lanes]
    lanes += sorted(plan.lanes - set(lanes))
    wanted: list[tuple[str | None, str]] = [
        (lane, d) for lane in lanes
              for d in LANE_DOMAINS.get(lane, ()) if d in pool.by_domain]
    # The lanes' domains first; then every other searched domain's best candidate, so a
    # source the plan did not name (a position for a statute-shaped question) can still
    # reach the evidence set. Whether any of it is SHOWN is the sufficiency decision
    # (PHASE 9, `AM-84` r4), not this one.
    wanted = list(dict.fromkeys(wanted))
    # The reader's own document is the primary source of a document conversation: its
    # lane takes two picks a round, so about half the evidence is the document, and
    # the Constitution, standards and law still get theirs. With one, a clause ranked
    # second to seventh in the document never reached the bundle (2026-09-28).
    wanted = [w for pair in wanted
              for w in ((pair, pair) if pair[1] == routing.Domain.DOCUMENT.value
                        else (pair,))]
    rest = sorted(pool.by_domain, key=lambda d: d not in pool.primary)
    extras: list[tuple[str | None, str]] = [(None, d) for d in rest
                                            if all(w[1] != d for w in wanted)]
    document = routing.Domain.DOCUMENT.value
    if plan.presentation.document_wide and document in pool.by_domain:
        # A whole-document task is answered from the document alone (`AM-108`).
        wanted, extras = [(query_plan.CONTRACT, document)], []
    if not wanted:
        # An unplaced question draws only from the router's PRIMARY domains (`AM-86`
        # r3). Measured (PHASE 8): offering it every domain gained 2 of 78 slots and
        # tripled false admission 0.2 -> 0.6, wrong-source 0.026 -> 0.040.
        wanted, extras = [(None, d) for d in rest if d in pool.primary], []
    from legalmind.assist import planner
    asked = planner.topics_in(plan.question)

    def placed(c: Candidate) -> bool:
        # A Constitution section on a topic the question names answers for the
        # company position whichever of its paragraphs matched: §14's note on ss.
        # 73/74 matched "early termination of a fixed-term deal", its position did
        # not, and §14 never answered the question it is about (2026-09-27, G-03).
        return c.domain == CONSTITUTION and bool(
            planner.SECTION_TOPICS.get(c.ref.removeprefix("CONST:"), frozenset()) & asked)

    taken: list[Candidate] = []
    refs: set[str] = set()
    depth = 0
    while len(taken) < k and depth < DEPTH:
        progressed = False
        # Extra (unrequested) domains offer their best candidate in the FIRST round
        # only, so they widen coverage without crowding out a lane's second source.
        for lane, domain in wanted + (extras if depth == 0 else []):
            # Kind-aware (PHASE 9): a LAW lane in the Constitution takes the company's
            # reading of the law, a historical lane a historical record, and a position
            # lane neither — so one kind never answers for another.
            ranked = [c for c in pool.by_domain[domain]
                      if c.ref not in refs
                      and (lane is None or ((lane in c.lanes or not c.lanes)
                                            and (lane in kinds_of(c) or (
                                                lane == query_plan.COMPANY_POSITION
                                                and placed(c)))))]
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


CONTEXT_CHARS = 4000


@dataclass(frozen=True)
class Evidence:
    """A selected candidate with its restored parent context (roadmap §8). `candidate`
    is the precise, citable span; `context` is what generation reads around it — built
    at read time, never stored, never cited in place of the span."""
    candidate: Candidate
    context: str


def with_context(db, evidence: list[Candidate]) -> list[Evidence]:
    """Parent/context reconstruction per domain (`AM-82` r3's expanders): a
    Constitution paragraph gets its provision's siblings (non-current ones labelled),
    a statute chunk its whole section, a document chunk its neighbours in the same
    evidence row. A position is one ratified quote with no children: its context is
    itself. The span is always inside its context."""
    out = []
    for c in evidence:
        if c.domain == CONSTITUTION:
            context = constitution.expand(db, c.item_id, max_chars=CONTEXT_CHARS)
        elif c.domain == routing.Domain.STATUTES.value:
            context = statute_corpus.expand_section(db, c.item_id,
                                                    max_chars=CONTEXT_CHARS)
        elif c.domain == routing.Domain.DOCUMENT.value:
            context = store.expand_chunk(db, c.item_id, max_chars=CONTEXT_CHARS)
        else:
            context = c.text
        out.append(Evidence(c, context if c.text.strip() and
                            " ".join(c.text.split()) in " ".join(context.split())
                            else f"{context}\n{c.text}".strip()))
    return out
