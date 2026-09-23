"""Source routing for the assist lane — the question picks the sources, never the user.

Owner requirement, 2026-09-08: a user uploads any legal document and asks a
natural-language question; LegalMind determines which authorized knowledge answers
it. No mode selector, no domain picker, no "is this an MSA?" prerequisite. Before
this module, `ask()` searched exactly one corpus — the document's chunks — so a
question about the organization's approved position was refused as "not found in the
selected document", which was true and beside the point.

Three domains, kept distinct (`AM-32` r1: separate tables, provenance, citation
semantics, access control — the router routes, it never merges):

    DOCUMENT    the uploaded document version the conversation is about
    POSITIONS   the organization's ratified Company Standards (Domain A, extractive
                only — `AM-32` r4: never in a generation payload, quoted verbatim)
    STATUTES    the approved statute corpus (Domain C) — a candidate only once the
                corpus is ratified and ingested; until then the plan records that a
                statute-shaped question was asked and the refusal says so

Authorization first (`AM-25` r6/r7). The candidate set is computed from the caller's
resolved permission set BEFORE any retrieval, and a domain the caller may not read
is simply not a candidate — so its absence is indistinguishable from an empty
corpus. The plan is deterministic in (question, has_document, permissions,
statutes_available) and is recorded on the retrieval run so the routing decision is
reconstructable alongside the retrieval it produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from legalmind import config
from legalmind.assist import understanding
from legalmind.domain.document_types import readable as _readable_document_type
from legalmind.security import permissions as P


class Domain(StrEnum):
    DOCUMENT = "DOCUMENT"
    POSITIONS = "POSITIONS"
    STATUTES = "STATUTES"


# Fixed rendering order, so identical inputs always produce identical output.
_ORDER = (Domain.DOCUMENT, Domain.POSITIONS, Domain.STATUTES)


def ordered(domains) -> tuple[str, ...]:
    """Domain names in `_ORDER` — one rendering for a set, however it was built."""
    names = {str(d) for d in domains}
    return tuple(d.value for d in _ORDER if d.value in names)


def positions_permitted(permissions: frozenset[str]) -> bool:
    """Domain A access — `AM-32` r5 as amended by `AM-44` (2026-09-08).

    `assist.ask` AND (`configuration.view` OR `legal_position.view`). The
    Constitution §3.2B lets users ask about "the company's legal position" and §25.1
    lets a normal user compare and view; AB-12 r7 already grants a Department User
    `legal_position.view` so they can see WHY their Finding is a MATCH or DEVIATION —
    the standard. Retrieval over PUBLISHED standards is the same disclosure by another
    door. Drafts are never chunked (`AM-32` r3), so `configuration.draft` stays out.
    """
    return P.ASSIST_ASK in permissions and (
        P.CONFIGURATION_VIEW in permissions or P.LEGAL_POSITION_VIEW in permissions)


@dataclass(frozen=True)
class RoutePlan:
    #: The evaluator's question (`AM-25` r4). Needs a document; handled before retrieval.
    comparison: bool
    #: PRIMARY candidates — the sources the question's own shape points at, in
    #: `_ORDER`. Searched first; an answer here is attributed to them.
    domains: tuple[Domain, ...]
    #: The question asked about the law itself. Recorded even when STATUTES is not a
    #: candidate, so the refusal can name the real limitation.
    statute_shaped: bool
    #: What the question asks ABOUT (`understanding.authority`), carried so later
    #: stages can tell "the reader wants the organization's position" from "nothing
    #: indicated which kind of source this is". Not a permission and not a plan.
    asked_authority: frozenset[str] = frozenset()
    #: POLICY: what a COMPLIANCE ASSESSMENT needs before it can run at all, and does
    #: not have. Empty for every question that is not one, and for one that can run.
    #: Reported to the reader instead of answering an easier question in its place.
    unmet: tuple[str, ...] = ()
    #: POLICY: may a SUPERSEDED source answer this question? Understanding says which
    #: time the reader asked about (`temporal`); this says whether a repealed Act is
    #: therefore admissible. Default False — a question that says nothing about time
    #: is asking what is true now, and answering it from repealed law is the failure
    #: the in-force filter exists to prevent (`AM-71`'s shape). Fail closed.
    include_superseded: bool = False
    #: WHICH deterministic signals produced `statute_shaped` — for the routing log and
    #: for a human reconstructing a decision. Never rendered to a reader.
    statute_signals: tuple[str, ...] = ()
    #: FALLBACK candidates (2026-09-09) — every OTHER source the caller is authorized
    #: to read, in `_ORDER`. Consulted whenever the primary sources do not answer,
    #: before any refusal. The uploaded document is context, not the boundary of
    #: what may be answered: "what is the termination notice period?" names no
    #: organization and no statute, so its primary route is the document alone —
    #: but when the document is silent, the organization's ratified position and the
    #: statute corpus are still authorized knowledge and are searched. The document
    #: itself is never a fallback: without one attached it cannot be searched at all.
    fallback: tuple[Domain, ...] = ()
    #: `AM-68` — the question asks what the PRODUCT does, not what the law says. When
    #: true, `domains` and `fallback` are both empty and no corpus is searched at all.
    capability: bool = False
    #: The question asks what a legal CONCEPT means, in general — not what any document
    #: or standard says. Like `capability`, it searches nothing: no authorised source
    #: holds the definition of "indemnity", and answering it from Company Standards
    #: presents the organization's positions as though they were the definition.
    general_knowledge: bool = False

    def has(self, domain: Domain) -> bool:
        return domain in self.domains

    @property
    def searched(self) -> tuple[Domain, ...]:
        """Every domain consulted before a refusal — primary AND fallback, in
        `_ORDER`. Deterministic in (permissions, has_document, statutes_available),
        which is exactly what `AM-46` requires of the refusal wording: it may depend
        on facts the caller already holds, never on whether a chunk exists."""
        both = set(self.domains) | set(self.fallback)
        return tuple(d for d in _ORDER if d in both)


def plan(question: str, *, has_document: bool, permissions: frozenset[str],
         statutes_available: bool = False,
         statute_jurisdictions: frozenset[str] = frozenset(),
         understood: understanding.QuestionUnderstanding | None = None) -> RoutePlan:
    """The domain plan. `understood` is the question read once (`understanding.
    understand`); it is derived here when a caller has not already done so, so no
    caller is obliged to change and the predicates run exactly once per turn."""
    question = question or ""
    u = understood if understood is not None else understanding.understand(question)
    # `has_document` gates the comparison because it is the ROUTER's decision, not a
    # property of the question (`AM-25` r4): asking whether a document complies is the
    # same question with or without one attached, and what changes is whether the
    # evaluator can run.
    # A COMPLIANCE ASSESSMENT is a request whether or not it can be served. Its
    # prerequisites are resolved here, before retrieval, and reported as themselves.
    #
    # NEEDS_AUTHORITY is not a gap in this code. A statute creates no Requirement —
    # "the DPDP Act does not create a Requirement", rule 7 — so there is no ratified
    # standard derived from an Act to measure a document against, and none may be
    # derived. Answering "does our NDA comply with the DPDP Act?" from the Company
    # Standards would measure it against a yardstick the reader did not name.
    unmet: list[str] = []
    if u.operation.is_comparison:
        if not has_document:
            unmet.append("NEEDS_DOCUMENT")
        if understanding.GENERAL_LAW in u.operation.against:
            unmet.append("NEEDS_AUTHORITY")
    # The evaluator answers a comparison against the organization's own position, and
    # only that. `AM-25` r4 is unchanged: Ask never performs the comparison, it hands
    # off to the Findings the deterministic evaluator already produced.
    comparison = (has_document and u.operation.is_comparison
                  and understanding.POSITION in u.operation.against)
    signals = u.signals
    statute_shaped = u.statute_shaped
    # `AM-68` r2 — ZERO RETRIEVAL, of any kind. A capability question reaches no legal
    # corpus at all: not the document, not the positions, not the statutes, and not as
    # a fallback. Returning here rather than emptying the sets afterwards is the point —
    # there is no later branch that could add one back.
    #
    # `AM-68` locked 2026-09-15, option (b): the manifest is RENDERED, not generated.
    # `config.capability_route_enabled()` defaults to on; setting the env var to "off"
    # is the rollback, restoring the pre-amendment behaviour without a deploy.
    if config.capability_route_enabled() and u.capability:
        return RoutePlan(comparison=False, domains=(), statute_shaped=False,
                         fallback=(), capability=True)
    # Same shape, same reason: nothing authorised answers it, so nothing is searched.
    # Unlike the capability route this needs no flag — NOT searching is always safe,
    # and it is what stops "what is an NDA?" being answered with three Company
    # Standards. What it may SAY is a separate question (see `service`).
    if u.general_knowledge:
        return RoutePlan(comparison=False, domains=(), statute_shaped=False,
                         fallback=(), general_knowledge=True)
    candidates: set[Domain] = set()
    if has_document and P.ASSIST_ASK in permissions:
        candidates.add(Domain.DOCUMENT)
    # A comparison question is also a position question: the approved position is
    # half of what it asks for, and quoting it beside the Findings is exactly the
    # "cite both sides separately" the requirement names.
    if (u.mentions_organization or comparison) \
            and positions_permitted(permissions):
        candidates.add(Domain.POSITIONS)
    # JURISDICTION IS POLICY, not understanding. The question may NAME a jurisdiction;
    # whether this system holds law for it is a fact about the corpus, and where it
    # does not, the corpus is not a substitute. Measured 2026-09-23 before this rule:
    # "what does Delaware law say about limitation of liability" and "under EU GDPR,
    # what is the breach notification deadline" were both ANSWERED, from an Indian
    # corpus. Neither stated foreign law — both returned a Company Standard quote —
    # but a reader asking about Delaware should not be handed one.
    #
    # Unspecified stays permitted: most questions name no jurisdiction and the corpus
    # answers them as it always has.
    jurisdiction_covered = (u.jurisdiction == understanding.UNSPECIFIED
                            or not statute_jurisdictions
                            or u.jurisdiction in statute_jurisdictions)
    # WHAT THE QUESTION ASKS ABOUT (`u.authority`) is not what may be searched. It
    # widens the CANDIDATES only, and every one still passes the same permission test
    # the shape-derived route does (`AM-45` r1). A source the caller may not read is
    # not reachable through this door either.
    asks_law = understanding.GENERAL_LAW in u.authority
    if ((statute_shaped or asks_law) and statutes_available
            and jurisdiction_covered and P.ASSIST_ASK in permissions):
        candidates.add(Domain.STATUTES)
    if (understanding.POSITION in u.authority and positions_permitted(permissions)
            and jurisdiction_covered):
        candidates.add(Domain.POSITIONS)
    # Fallbacks: what else the caller may read. Authorization is the same test the
    # primary route applies — a domain the caller may not read is not a fallback
    # either, so its absence stays indistinguishable from an empty corpus.
    # A named jurisdiction this system holds no law for is not answered from the
    # organization's own positions either. A ratified Company Standard is what THIS
    # organization will accept; it is not a statement of Delaware or EU law, and
    # offering it to someone who asked for one is misleading by juxtaposition even
    # though the quote is honestly labelled — which is exactly what the 2026-09-23
    # baseline measured.
    #
    # Narrow on purpose: it applies only when the reader is asking about the LAW. "What
    # is our position on Delaware disputes?" asks about the organization, and the
    # organization can answer it.
    foreign_law_question = not jurisdiction_covered and not u.mentions_organization
    fallback: set[Domain] = set()
    if positions_permitted(permissions) and not foreign_law_question:
        fallback.add(Domain.POSITIONS)
    if statutes_available and jurisdiction_covered and P.ASSIST_ASK in permissions:
        fallback.add(Domain.STATUTES)
    fallback -= candidates
    return RoutePlan(comparison=comparison,
                     asked_authority=u.authority,
                     unmet=tuple(unmet),
                     include_superseded=u.temporal.wants_past,
                     domains=tuple(d for d in _ORDER if d in candidates),
                     statute_shaped=statute_shaped,
                     statute_signals=signals.because,
                     fallback=tuple(d for d in _ORDER if d in fallback),
                     capability=False, general_knowledge=False)


# --------------------------------------------------------------------------
# Refusal wording — `AM-29` r4 as amended by `AM-46` (2026-09-08)
# --------------------------------------------------------------------------
# One sentence per candidate SET, identical for every cause within that set. The
# wording depends only on facts the caller already holds — their own permissions
# (`/me`) and whether their conversation has a document — never on whether a
# particular chunk, standard or document exists. So a permission exclusion and a
# genuine miss still read identically, and no wording confirms the existence of
# anything outside the caller's scope (`AM-25` r6/r7).
_TAIL = " The available material does not answer this question."
_NO_DOCUMENT = "No document is attached to this conversation."
_STATUTES_UNAVAILABLE = (
    " Statutory text is not yet part of this installation's approved sources, so "
    "questions about the law itself cannot be answered.")


def refusal_text(route: RoutePlan, *, statute_holdings: tuple[str, ...] = (),
                 unheld_document_type: str | None = None,
                 position_coverage: tuple[str, ...] = ()) -> str:
    """`statute_holdings` — the Acts the corpus holds, named when a statute-shaped
    question missed inside an available corpus (AM-46 r3: a public, global fact).

    `unheld_document_type` / `position_coverage` — the same courtesy for Domain A, on
    the same AM-46 r3 reasoning: when the question named a kind of paper the ratified
    corpus holds NO position for, say which kinds it does hold. Without this the reader
    of a Partner Agreement question saw only "Information not found", which reads as a
    broken search rather than as the fact it is — the organization has approved no
    Partner Agreement position yet. Naming the covered types discloses no position,
    only the shape of the corpus.

    Names every domain the service consulted — primary and fallback — because a
    refusal is only honest once all of them have been checked (2026-09-09). The set
    is still a function of the caller's own permissions, the presence of a document
    and the corpus's public availability, so no wording confirms the existence of
    anything outside the caller's scope (`AM-25` r6/r7, `AM-46`)."""
    consulted = route.searched
    searched = []
    if Domain.DOCUMENT in consulted:
        searched.append("the selected document")
    if Domain.POSITIONS in consulted:
        searched.append("the organization's approved positions")
    if Domain.STATUTES in consulted:
        searched.append("the approved statute corpus")
    if searched:
        text = "Information not found in " + " or in ".join(searched) + "." + _TAIL
        if Domain.DOCUMENT not in consulted:
            text += " " + _NO_DOCUMENT
    else:
        text = _NO_DOCUMENT + (_TAIL if route.statute_shaped else
                               " Attach a document to ask about it.")
    if unheld_document_type and position_coverage:
        text += (f" No approved position covers "
                 f"{_readable_document_type(unheld_document_type)}. The organization's "
                 f"ratified standards currently cover: "
                 + ", ".join(_readable_document_type(t) for t in position_coverage)
                 + ".")
    if route.statute_shaped and Domain.STATUTES not in consulted:
        text += _STATUTES_UNAVAILABLE
    elif route.statute_shaped and statute_holdings:
        text += (" The approved statute corpus currently holds: "
                 + "; ".join(statute_holdings) + ".")
    return text
