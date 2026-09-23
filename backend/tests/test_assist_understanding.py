"""`QuestionUnderstanding` — one reading of a question, and it must not drift.

Step 1 of the query-understanding migration is a PURE REFACTOR: the object exists and
the router reads it, but every value is one of today's predicates called once. These
tests pin that equivalence, so the day a field stops matching its predicate is the day
a test fails rather than the day a route quietly changes.

The matrix in `tests/assist_eval/understanding_matrix.json` is the frozen baseline the
parity run compares against; its shape is pinned here so a case cannot be dropped to
make a number look better.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib

import pytest

from legalmind.assist import intent, routing, understanding
from legalmind.security import permissions as P

MATRIX = pathlib.Path(__file__).parent / "assist_eval/understanding_matrix.json"
CASES = json.loads(MATRIX.read_text())["cases"]
PERMS = frozenset({P.ASSIST_ASK, P.CONTRACT_VIEW, P.FINDING_VIEW,
                   P.LEGAL_POSITION_VIEW, P.CONFIGURATION_VIEW})


@pytest.mark.parametrize("question", [c["q"] for c in CASES])
def test_every_field_equals_the_predicate_it_replaced(question):
    """The refactor's whole claim, asserted on all 64 matrix questions."""
    u = understanding.understand(question)
    assert u.capability == intent.is_capability_question(question)
    assert u.general_knowledge == intent.is_general_knowledge_question(question)
    assert u.comparison_requested == intent.is_comparison_question(question)
    assert u.exact_text == intent.is_exact_text_request(question)
    assert u.follow_up == intent.is_follow_up(question)
    assert u.mentions_organization == intent.mentions_organization(question)
    assert u.statute_shaped == intent.is_statute_question(question)


@pytest.mark.parametrize("question", [c["q"] for c in CASES])
def test_routing_is_identical_whether_it_reads_the_object_or_derives_it(question):
    """`plan` accepts a pre-read understanding so the predicates run once per turn.
    Passing one must not change a single routing decision."""
    for has_document in (False, True):
        derived = routing.plan(question, has_document=has_document,
                               permissions=PERMS, statutes_available=True)
        passed = routing.plan(question, has_document=has_document, permissions=PERMS,
                              statutes_available=True,
                              understood=understanding.understand(question))
        assert derived == passed


def test_comparison_is_recorded_ungated_and_the_router_applies_the_gate():
    """The question "does this comply?" is the same question with or without a
    document attached. What changes is whether the evaluator can run (`AM-25` r4), and
    that is the ROUTER's decision — so the understanding records the request ungated.

    This is the distinction that makes a document-plus-statute comparison expressible
    at all; today the router still gates it, and that is deliberate for a pure refactor.
    """
    u = understanding.understand("Does our NDA comply with the DPDP Act?")
    assert u.comparison_requested
    assert not routing.plan(u.question, has_document=False,
                            permissions=PERMS, statutes_available=True).comparison
    assert routing.plan(u.question, has_document=True,
                        permissions=PERMS, statutes_available=True).comparison


def test_the_frozen_matrix_keeps_its_shape():
    """16 classes, four questions each, with the controls that stop the matrix being
    tuned into a pass: six must-refuse, four ambiguous, eight chained follow-ups."""
    classes: dict[str, int] = {}
    for case in CASES:
        classes[case["class"]] = classes.get(case["class"], 0) + 1
    assert len(CASES) == 64
    assert len(classes) == 16 and set(classes.values()) == {4}
    assert sum(1 for c in CASES if c.get("must_refuse")) == 6
    assert sum(1 for c in CASES if c.get("ambiguous")) == 4
    assert sum(1 for c in CASES if c.get("after")) == 8


def test_understanding_is_frozen():
    """A caller reads it; nobody edits it halfway down the pipeline."""
    u = understanding.understand("What is the liability cap?")
    with pytest.raises(dataclasses.FrozenInstanceError):
        u.exact_text = True          # type: ignore[misc]


# --------------------------------------------------------------------------
# Step 2 — what fact is asked for, what authority can state it, which jurisdiction
# --------------------------------------------------------------------------
def test_a_penalty_is_never_asked_of_the_position_corpus():
    """The one semantic claim `requested_fact` exists to make: a ratified Company
    Standard records what the organization WILL ACCEPT. It never imposes a penalty —
    only law does, or a contract the parties signed. So a question asking for a
    penalty is not a question the position corpus can answer, whatever words it
    shares with one.

    This is the relation Q12 turns on, and it is deliberately NOT a rule about
    "personal data" or any other subject: change the subject and it still holds.
    """
    for question in ("What is the penalty for failing to protect personal data?",
                     "What is the punishment for breach of confidentiality?",
                     "What is the penalty for late filing of returns?"):
        u = understanding.understand(question)
        assert u.requested_fact == understanding.PENALTY
        assert understanding.POSITION not in u.authority
        assert understanding.GENERAL_LAW in u.authority


def test_every_other_fact_stays_answerable_by_any_source():
    """Only the penalty relation is claimed. A period, a value or a deadline can each
    be stated by a contract, a ratified position or a statute, and narrowing them
    would be routing by guess."""
    for question in ("What is the notice period?", "What is the liability cap?",
                     "Within what time must it be reported?"):
        u = understanding.understand(question)
        assert understanding.POSITION not in understanding._FACT_CANNOT_ANSWER.get(
            u.requested_fact, frozenset()) or u.requested_fact == understanding.PENALTY


def test_authority_is_what_is_asked_not_what_may_be_read():
    """The boundary the whole step turns on. `authority` is the reader's side of the
    question; it must never widen what the system searches. A caller without the
    position permission gets no POSITIONS domain no matter what the question asks
    about (`AM-45` r1 — permissions decide before question shape)."""
    question = "What is our approved position on auto-renewal?"
    u = understanding.understand(question)
    assert understanding.POSITION in u.authority

    unprivileged = frozenset({P.ASSIST_ASK})
    route = routing.plan(question, has_document=False, permissions=unprivileged,
                         statutes_available=True)
    assert routing.Domain.POSITIONS not in route.domains
    assert routing.Domain.POSITIONS not in route.fallback


@pytest.mark.parametrize("question,expected", [
    ("What does Indian law say about indemnity?", "IN"),
    ("What does Delaware law say about limitation of liability?", "US-DE"),
    ("Under EU GDPR, what is the breach notification deadline?", "EU"),
    ("What is the liability cap in this agreement?", understanding.UNSPECIFIED),
])
def test_jurisdiction_is_a_value_not_a_boolean(question, expected):
    """Before this existed "Delaware law" and "Indian law" were the same signal, which
    is why a Delaware question reached an Indian corpus."""
    assert understanding.understand(question).jurisdiction == expected


def test_law_of_an_uncovered_jurisdiction_is_not_answered_from_any_corpus():
    """Measured 2026-09-23: both of these were ANSWERED from an Indian corpus. Neither
    stated foreign law — both returned a Company Standard quote — but a reader asking
    about Delaware should not be handed the organization's own position instead, and
    the statute corpus holds no Delaware law to give them.

    The covered jurisdiction is read from the corpus, so this is not a list of
    countries in code: ingest an Act under a new jurisdiction and it becomes answerable.
    """
    covered = frozenset({"IN"})
    for question in ("What does Delaware law say about limitation of liability?",
                     "Under EU GDPR, what is the breach notification deadline?"):
        route = routing.plan(question, has_document=False, permissions=PERMS,
                             statutes_available=True, statute_jurisdictions=covered)
        assert not route.domains and not route.fallback, question


def test_a_covered_jurisdiction_is_unaffected():
    route = routing.plan("What does Indian law say about indemnity?", has_document=False,
                         permissions=PERMS, statutes_available=True,
                         statute_jurisdictions=frozenset({"IN"}))
    assert routing.Domain.STATUTES in route.domains


def test_asking_about_our_own_position_survives_a_foreign_jurisdiction():
    """The exclusion is about the LAW of an uncovered jurisdiction. "What is our
    position on Delaware disputes?" asks about the organization, and the organization
    can answer it."""
    route = routing.plan("What is our position on Delaware disputes?", has_document=False,
                         permissions=PERMS, statutes_available=True,
                         statute_jurisdictions=frozenset({"IN"}))
    assert routing.Domain.POSITIONS in (route.domains + route.fallback)
