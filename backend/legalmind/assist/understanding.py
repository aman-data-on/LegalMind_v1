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

from dataclasses import dataclass

from legalmind.assist import intent


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

    @property
    def statute_shaped(self) -> bool:
        """The question asks about the law itself — the Domain C candidate signal."""
        return self.signals.general_law

    @property
    def because(self) -> tuple[str, ...]:
        """Which signals produced the statute decision. For the routing log only."""
        return self.signals.because


def understand(question: str) -> QuestionUnderstanding:
    """Derive everything today's code knows about a question, in one pass.

    Pure, deterministic and free — no database, no model, no network. Call it once per
    turn and pass the result down; that is the whole point of it existing.
    """
    text = question or ""
    return QuestionUnderstanding(
        question=text,
        capability=intent.is_capability_question(text),
        general_knowledge=intent.is_general_knowledge_question(text),
        comparison_requested=intent.is_comparison_question(text),
        exact_text=intent.is_exact_text_request(text),
        follow_up=intent.is_follow_up(text),
        mentions_organization=intent.mentions_organization(text),
        signals=intent.legal_question_signals(text),
    )
