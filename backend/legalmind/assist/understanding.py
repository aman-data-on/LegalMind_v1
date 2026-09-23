"""What a question IS — assembled once, read everywhere.

Until now the assist lane had no representation of a question. Seventeen call sites
across five modules each re-derived one aspect from the raw string: `routing.plan`
asked five predicates, `service._ask` asked nine more, and none of them could see what
the others had concluded. Three consequences, all measured:

  * The decisions cannot be jointly consistent, because nothing holds them together.
  * They cannot be explained after the fact — a route could be reconstructed only by
    re-running the predicates on the same string.
  * A question needing two sources cannot be expressed at all, because the router
    emits domain MEMBERSHIP rather than a plan.

This module introduces the missing object and nothing else. Every field is one of
today's predicates, called once, with the same arguments and the same meaning, so the
routing decision is byte-identical — verified against the frozen 64-case matrix in
`tests/assist_eval/understanding_matrix.json` and the 91-case routing matrix.

It deliberately does NOT yet carry `requested_fact`, `authority`, `jurisdiction` or
`temporal`. Those are new semantics, they change behaviour, and they belong to the step
that measures them. A field that no caller reads is a field nobody can be wrong about.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from legalmind.assist import intent

# --------------------------------------------------------------------------
# What KIND of fact is being asked for, and what KIND of source can state it.
#
# Reading which fact a question wants means reading its words; there is no way
# round that. The discipline is what the words are allowed to be:
#
#   * INTERROGATIVE SHAPE, never subject matter. "penalty" and "within what time"
#     are here; "cyber incident" and "personal data" are not, and must never be —
#     a topic list is how a router stops generalising and starts memorising the
#     benchmark.
#   * A CLOSED set of six, each carrying a relation to the authority that can
#     answer it. The relation is the content; the pattern is only how it is
#     recognised.
# --------------------------------------------------------------------------
PENALTY = "PENALTY"
DEADLINE = "DEADLINE"
PERIOD = "PERIOD"
VALUE = "VALUE"
PROCEDURE = "PROCEDURE"
DEFINITION = "DEFINITION"
NO_FACT = "NONE"

DOCUMENT = "DOCUMENT"
POSITION = "POSITION"
GENERAL_LAW = "GENERAL_LAW"

UNSPECIFIED = "UNSPECIFIED"

# First match wins, so the specific shapes precede the general ones.
_FACTS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE)) for name, pattern in (
        (PENALTY, r"\b(penalt(?:y|ies)|punishment|punishable|fine|imprisonment)\b"),
        (DEADLINE, r"(within what time|by when|how soon|how long do i have|deadline)"),
        (PERIOD, r"\b(how long|period|duration|survives? for|notice period)\b"),
        (VALUE, r"\b(how much|cap|amount|rate|limit|threshold)\b"),
        (PROCEDURE, r"(how (?:do|does|can|is|are)\b|what is the process|procedure)"),
        (DEFINITION, r"(what (?:is|are|does)\b|when is\b|is a\b)"),
    ))

# The one semantic claim in this module, and the reason `requested_fact` exists at
# all: a ratified Company Standard records what the organization WILL ACCEPT. It
# never imposes a penalty on anyone — only law does that, or a contract the parties
# signed. So a question asking for a penalty cannot be answered by the position
# corpus, whatever words it shares with one.
#
# Every other fact type is genuinely answerable by any source: a period, a value, a
# deadline or a procedure can each be stated by a contract, by a ratified position or
# by a statute, and claiming otherwise would be routing by guess.
_FACT_CANNOT_ANSWER: dict[str, frozenset[str]] = {PENALTY: frozenset({POSITION})}

# Jurisdictions the question may NAME. Not a list of what the system holds — that
# comes from the corpus itself (`statutes.jurisdictions`), so adding an Act in a new
# jurisdiction changes what may be answered without touching this table.
_JURISDICTIONS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), code) for pattern, code in (
        (r"\bindian?\b", "IN"),
        (r"\bdelaware\b", "US-DE"),
        (r"\b(gdpr|european union|\beu\b)\b", "EU"),
        (r"\bsingapore\b", "SG"),
        (r"\b(united kingdom|england|wales)\b", "UK"),
        (r"\b(united states|u\.s\.a?\.?)\b", "US"),
    ))


@dataclass(frozen=True)
class QuestionUnderstanding:
    """One question, understood once. Frozen: a caller may read it, never edit it."""

    question: str
    #: `AM-68` — answered from the rendered manifest, with zero retrieval.
    capability: bool
    #: Nothing authorised can answer it, so nothing is searched.
    general_knowledge: bool
    #: The reader asked how a document stands against the approved position. Recorded
    #: UNGATED — whether a document is attached is the router's decision to apply
    #: (`AM-25` r4), not a property of the question.
    comparison_requested: bool
    #: `AM-76` r2 — the reader asked for the source's own words.
    exact_text: bool
    #: The question refers back rather than standing alone.
    follow_up: bool
    #: It asks about the organization's own position.
    mentions_organization: bool
    #: The seven deterministic GENERAL LAW signals, and which fired.
    signals: intent.LegalQuestionSignals
    #: WHAT kind of fact the reader wants — one of the six, or NONE.
    requested_fact: str = NO_FACT
    #: WHAT KIND OF AUTHORITY the question is ABOUT. This is the reader's side of the
    #: question and nothing else: it is not permission, not availability, and not a
    #: decision to search anything. `routing.plan` intersects it with what the caller
    #: may read and what the corpus holds, and that intersection is the only thing
    #: that reaches retrieval (`AM-45` r1 — permissions decide first, always).
    authority: frozenset[str] = frozenset()
    #: The jurisdiction the question NAMES, or UNSPECIFIED. A value, not a boolean —
    #: "Delaware law" and "Indian law" were the same signal before this existed.
    jurisdiction: str = UNSPECIFIED

    @property
    def statute_shaped(self) -> bool:
        """The question asks about the law itself — the Domain C candidate signal."""
        return self.signals.general_law

    @property
    def because(self) -> tuple[str, ...]:
        """Which signals produced the statute decision. For the routing log only."""
        return self.signals.because


def _requested_fact(text: str) -> str:
    for name, pattern in _FACTS:
        if pattern.search(text):
            return name
    return NO_FACT


def _jurisdiction(text: str) -> str:
    for pattern, code in _JURISDICTIONS:
        if pattern.search(text):
            return code
    return UNSPECIFIED


def _authority(text: str, fact: str, signals: intent.LegalQuestionSignals,
               organization: bool) -> frozenset[str]:
    """Which KINDS of source the question is asking about.

    Additive and generous on purpose: this is the reader's side of the question, so
    saying "a statute could answer this" costs nothing on its own. What it may not do
    is widen what gets SEARCHED — `routing.plan` intersects it with permissions and
    with the corpus, and a source the caller cannot read stays unreadable.
    """
    asked: set[str] = set()
    if signals.general_law:
        asked.add(GENERAL_LAW)
    if organization:
        asked.add(POSITION)
    if signals.document_target:
        asked.add(DOCUMENT)
    # A fact only some sources can state narrows the ask. See `_FACT_CANNOT_ANSWER`:
    # today that is the penalty rule and nothing else.
    cannot = _FACT_CANNOT_ANSWER.get(fact, frozenset())
    if cannot:
        asked -= cannot
        # A penalty with nothing else named is a question about the law, because the
        # only remaining source that states one is a statute or the document itself.
        if not asked:
            asked.add(GENERAL_LAW)
    return frozenset(asked)


def understand(question: str) -> QuestionUnderstanding:
    """Derive everything today's code knows about a question, in one pass.

    Pure, deterministic and free — no database, no model, no network. Call it once per
    turn and pass the result down; that is the whole point of it existing.
    """
    text = question or ""
    signals = intent.legal_question_signals(text)
    organization = intent.mentions_organization(text)
    fact = _requested_fact(text)
    return QuestionUnderstanding(
        question=text,
        capability=intent.is_capability_question(text),
        general_knowledge=intent.is_general_knowledge_question(text),
        comparison_requested=intent.is_comparison_question(text),
        exact_text=intent.is_exact_text_request(text),
        follow_up=intent.is_follow_up(text),
        mentions_organization=organization,
        signals=signals,
        requested_fact=fact,
        authority=_authority(text, fact, signals, organization),
        jurisdiction=_jurisdiction(text),
    )
