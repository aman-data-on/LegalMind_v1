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
    #: Authorized candidate domains, in `_ORDER`. Empty means nothing can be searched.
    domains: tuple[Domain, ...]
    #: The question asked about the law itself. Recorded even when STATUTES is not a
    #: candidate, so the refusal can name the real limitation.
    statute_shaped: bool

    def has(self, domain: Domain) -> bool:
        return domain in self.domains


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
    return RoutePlan(comparison=comparison,
                     domains=tuple(d for d in _ORDER if d in candidates),
                     statute_shaped=statute_shaped)


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
    question missed inside an available corpus (AM-46 r3: a public, global fact)."""
    searched = []
    if route.has(Domain.DOCUMENT):
        searched.append("the selected document")
    if route.has(Domain.POSITIONS):
        searched.append("the organization's approved positions")
    if route.has(Domain.STATUTES):
        searched.append("the approved statute corpus")
    if searched:
        text = "Information not found in " + " or in ".join(searched) + "." + _TAIL
    else:
        text = _NO_DOCUMENT + (_TAIL if route.statute_shaped else
                               " Attach a document to ask about it.")
    if route.statute_shaped and not route.has(Domain.STATUTES):
        text += _STATUTES_UNAVAILABLE
    elif route.statute_shaped and statute_holdings:
        text += (" The approved statute corpus currently holds: "
                 + "; ".join(statute_holdings) + ".")
    return text
