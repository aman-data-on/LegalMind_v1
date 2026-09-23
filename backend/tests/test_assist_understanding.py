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
