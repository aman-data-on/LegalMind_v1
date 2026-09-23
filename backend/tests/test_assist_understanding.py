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


def test_a_comparison_is_recorded_before_anything_is_known_about_the_document():
    """The question "does this comply?" is the same question with or without a
    document attached. What changes is whether it can be SERVED, and that is policy's
    to decide — so understanding records the operation ungated."""
    u = understanding.understand("Does our NDA comply with the DPDP Act?")
    assert u.operation.is_comparison
    assert u.operation.subject == understanding.CURRENT_DOCUMENT


def test_a_compliance_question_against_a_statute_is_not_answered_from_the_standards():
    """The defect this step removes. There is no ratified standard derived from an
    Act — "the DPDP Act does not create a Requirement" (rule 7) — so there is nothing
    to measure the document against, and none may be derived.

    Before, this handed off to the evaluator and showed Findings computed against the
    organization's Company Standards: a yardstick the reader never named, presented as
    an answer to the question they did ask. It is now reported as what it is.
    """
    route = routing.plan("Does our NDA comply with the DPDP Act?", has_document=True,
                         permissions=PERMS, statutes_available=True,
                         statute_jurisdictions=frozenset({"IN"}))
    assert not route.comparison, "must not hand a statute question to the position evaluator"
    assert "NEEDS_AUTHORITY" in route.unmet


def test_a_compliance_question_against_our_own_position_still_reaches_the_evaluator():
    """The path that works is untouched: the deterministic evaluator remains the only
    thing that compares a document to the organization's approved position
    (`AM-25` r4), and Ask still only hands off to it."""
    route = routing.plan("Is this agreement compliant with our Constitution?",
                         has_document=True, permissions=PERMS, statutes_available=True,
                         statute_jurisdictions=frozenset({"IN"}))
    assert route.comparison and not route.unmet


def test_a_comparison_with_no_document_asks_for_one():
    """Rather than answering an easier question in its place."""
    route = routing.plan("Is this agreement compliant with our Constitution?",
                         has_document=False, permissions=PERMS, statutes_available=True,
                         statute_jurisdictions=frozenset({"IN"}))
    assert "NEEDS_DOCUMENT" in route.unmet
    assert not route.comparison


def test_a_plain_lookup_never_acquires_prerequisites():
    """`unmet` is empty for every question that is not a compliance assessment — the
    new branch must not intercept ordinary questions."""
    for question in ("What is the liability cap in this agreement?",
                     "What is our position on MSA auto-renewal?",
                     "What does Indian law say about indemnity?"):
        route = routing.plan(question, has_document=True, permissions=PERMS,
                             statutes_available=True,
                             statute_jurisdictions=frozenset({"IN"}))
        assert not route.unmet, question


def test_the_frozen_matrix_keeps_its_shape():
    """19 classes, four questions each, with the controls that stop the matrix being
    tuned into a pass: six must-refuse, four ambiguous, eight chained follow-ups."""
    classes: dict[str, int] = {}
    for case in CASES:
        classes[case["class"]] = classes.get(case["class"], 0) + 1
    assert len(CASES) == 76
    assert len(classes) == 19 and set(classes.values()) == {4}
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


# --------------------------------------------------------------------------
# Step 3 — which TIME the question is about
# --------------------------------------------------------------------------
@pytest.mark.parametrize("question,kind", [
    ("What does current Indian law say about indemnity?", understanding.CURRENT),
    ("What is the law on winding up as it stands?", understanding.CURRENT),
    ("What did the law say about share allotment?", understanding.HISTORICAL),
    ("What was the rule before the amendment?", understanding.HISTORICAL),
    ("What was applicable on 1 January 2024?", understanding.AS_OF_DATE),
    ("What did the law require in 1956?", understanding.AS_OF_DATE),
    ("What is the liability cap in this agreement?", understanding.UNSPECIFIED),
])
def test_temporal_is_read_from_grammar_not_subject_matter(question, kind):
    """Tense and an explicit date. No Act is named in any rule, no year is special —
    change the statute and every one of these still holds, which is the test for
    whether a temporal rule is principled or just a keyword."""
    assert understanding.understand(question).temporal.kind == kind


def test_a_year_in_an_acts_name_is_not_a_date_the_reader_asked_about():
    """"The Companies Act, 1956" NAMES a statute; it does not ask about 1956. Without
    this every question naming an older Act would read as AS_OF_DATE and quietly
    admit superseded law."""
    named = understanding.understand(
        "What does the Companies Act, 1956 say about allotment of shares?")
    assert named.temporal.kind == understanding.UNSPECIFIED
    asked = understanding.understand("What did the Companies Act say in 1956?")
    assert asked.temporal.kind == understanding.AS_OF_DATE
    assert asked.temporal.date == "1956"


def test_unspecified_time_is_not_the_past():
    """The fail-closed default, asserted directly. A question that says nothing about
    time is asking what is true NOW, and answering it from repealed law is the failure
    the in-force filter exists to prevent."""
    assert not understanding.TemporalScope().wants_past
    assert not understanding.TemporalScope(understanding.CURRENT).wants_past
    assert understanding.TemporalScope(understanding.HISTORICAL).wants_past
    assert understanding.TemporalScope(understanding.AS_OF_DATE, "1956").wants_past


def test_understanding_says_when_policy_says_whether():
    """The boundary. `temporal` never selects a source — it sets one policy input,
    and the router decides admissibility. A superseded Act is admissible only when the
    reader asked about the past."""
    for question, expected in (
            ("What did the law on winding up say in 1956?", True),
            ("What was the rule before the amendment?", True),
            ("What is the current law on winding up?", False),
            ("What are the duties of a director?", False)):
        route = routing.plan(question, has_document=False, permissions=PERMS,
                             statutes_available=True,
                             statute_jurisdictions=frozenset({"IN"}))
        assert route.include_superseded is expected, question


def test_naming_a_repealed_act_still_reaches_it_without_any_temporal_claim():
    """Two separate rules, and this pins that they stay separate. A reader who NAMES
    an Act gets that Act — a source rule, matched per row inside the query — and it
    holds whether or not the question says anything about time. Conflating the two is
    what the Income-tax case in the matrix originally got wrong."""
    u = understanding.understand(
        "What does the Income-tax Act, 1961 say about TDS on professional fees?")
    assert u.temporal.kind == understanding.UNSPECIFIED
    route = routing.plan(u.question, has_document=False, permissions=PERMS,
                         statutes_available=True, statute_jurisdictions=frozenset({"IN"}))
    assert route.include_superseded is False


# --------------------------------------------------------------------------
# Step 5 — a legal source referred to by CATEGORY rather than by name
# --------------------------------------------------------------------------
@pytest.mark.parametrize("question", [
    "Which Act governs company incorporation today?",
    "What statute covers electronic signatures?",
    "What does the law say about indemnity?",
    "What did the law on allotment of shares say in 1956?",
    "Under the law, when is an agreement void?",
])
def test_a_source_named_by_category_is_still_a_source_reference(question):
    """`names_instrument` only ever matched a source by NAME, so a question asking
    for the law in the abstract carried no source signal at all and was answered from
    whatever else happened to be authorized. Measured 2026-09-23: five wrong-source
    answers in 76 — the only tier of failure where a reader is shown a source that
    cannot answer their question."""
    assert intent.legal_question_signals(question).generic_instrument
    assert intent.is_statute_question(question)


@pytest.mark.parametrize("question", [
    "What is the rule in this contract?",
    "What does the law say in our standard?",
    "What rules do we apply to vendors?",
])
def test_a_generic_reference_still_loses_to_something_of_our_own(question):
    """It is a TIER-B positive, not an override. A question that refers to a document
    or to the organization's own position is answered from those — the same relation
    every other positive signal obeys."""
    signals = intent.legal_question_signals(question)
    assert signals.generic_instrument
    assert not signals.general_law


def test_this_is_not_the_impersonal_modal_signal_that_was_rejected():
    """An earlier attempt made "must + impersonal" a statute signal and was REJECTED
    for breaking a must-refuse case. The distinction is real and worth pinning: a
    modal is a phrasing that contractual obligations share, whereas "the statute"
    names a kind of source and nothing else. These carry a modal and no source, and
    must NOT route to the law on that basis alone."""
    for question in ("Notice must be given within thirty days.",
                     "The fee must be paid before renewal."):
        assert not intent.legal_question_signals(question).generic_instrument


# --------------------------------------------------------------------------
# Step 6 — a lexical coincidence must not decide which source is consulted
# --------------------------------------------------------------------------
def test_the_route_carries_what_the_question_asked_about():
    """`asked_authority` is understanding's answer travelling with policy's plan, so
    a later stage can tell "the reader wants our position" from "nothing indicated
    which kind of source this is". It is not a permission and not a plan."""
    route = routing.plan("What is our position on auto-renewal?", has_document=False,
                         permissions=PERMS, statutes_available=True,
                         statute_jurisdictions=frozenset({"IN"}))
    assert understanding.POSITION in route.asked_authority
    neutral = routing.plan("Within what time must a cyber incident be reported?",
                           has_document=False, permissions=PERMS, statutes_available=True,
                           statute_jurisdictions=frozenset({"IN"}))
    assert understanding.POSITION not in neutral.asked_authority


def test_a_position_hit_suppresses_the_statutes_only_when_positions_were_asked_for():
    """The defect, stated as a rule. Position retrieval is lexical-first and ungated —
    "a lexical hit is trusted on its own" — so two shared lexemes returns rows.
    Measured 2026-09-23: "within what time must a cyber incident be reported?" matched
    CLAIM-WINDOW-SLA-001 and "how long do I have to file an appeal?" matched
    CONF-SURVIVAL-NDA-001, and on the strength of those coincidences the statute
    corpus was never searched — though it holds the CERT-In Directions and IT Act
    s.57 that answer them.

    The original intent is kept: a question the organization's own position genuinely
    answers is not also put to 5,000 statute sections. What changed is the test —
    whether the READER asked about the organization's material, not whether a lexical
    query happened to return something.
    """
    from legalmind.assist import service

    source = pathlib.Path(service.__file__).read_text()
    assert "own_material = (understanding.POSITION in route.asked_authority" in source
    assert "if position_hits and not route.statute_shaped and own_material:" in source
