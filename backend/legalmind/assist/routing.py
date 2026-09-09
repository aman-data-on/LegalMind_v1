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

from legalmind.assist import intent
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
    #: FALLBACK candidates (2026-09-09) — every OTHER source the caller is authorized
    #: to read, in `_ORDER`. Consulted whenever the primary sources do not answer,
    #: before any refusal. The uploaded document is context, not the boundary of
    #: what may be answered: "what is the termination notice period?" names no
    #: organization and no statute, so its primary route is the document alone —
    #: but when the document is silent, the organization's ratified position and the
    #: statute corpus are still authorized knowledge and are searched. The document
    #: itself is never a fallback: without one attached it cannot be searched at all.
    fallback: tuple[Domain, ...] = ()

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
         statutes_available: bool = False) -> RoutePlan:
    question = question or ""
    comparison = has_document and intent.is_comparison_question(question)
    statute_shaped = intent.is_statute_question(question)
    candidates: set[Domain] = set()
    if has_document and P.ASSIST_ASK in permissions:
        candidates.add(Domain.DOCUMENT)
    # A comparison question is also a position question: the approved position is
    # half of what it asks for, and quoting it beside the Findings is exactly the
    # "cite both sides separately" the requirement names.
    if (intent.mentions_organization(question) or comparison) \
            and positions_permitted(permissions):
        candidates.add(Domain.POSITIONS)
    if statute_shaped and statutes_available and P.ASSIST_ASK in permissions:
        candidates.add(Domain.STATUTES)
    # Fallbacks: what else the caller may read. Authorization is the same test the
    # primary route applies — a domain the caller may not read is not a fallback
    # either, so its absence stays indistinguishable from an empty corpus.
    fallback: set[Domain] = set()
    if positions_permitted(permissions):
        fallback.add(Domain.POSITIONS)
    if statutes_available and P.ASSIST_ASK in permissions:
        fallback.add(Domain.STATUTES)
    fallback -= candidates
    return RoutePlan(comparison=comparison,
                     domains=tuple(d for d in _ORDER if d in candidates),
                     statute_shaped=statute_shaped,
                     fallback=tuple(d for d in _ORDER if d in fallback))


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


def refusal_text(route: RoutePlan, *, statute_holdings: tuple[str, ...] = ()) -> str:
    """`statute_holdings` — the Acts the corpus holds, named when a statute-shaped
    question missed inside an available corpus (AM-46 r3: a public, global fact).

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
    if route.statute_shaped and Domain.STATUTES not in consulted:
        text += _STATUTES_UNAVAILABLE
    elif route.statute_shaped and statute_holdings:
        text += (" The approved statute corpus currently holds: "
                 + "; ".join(statute_holdings) + ".")
    return text
