"""The query planner — advisory, fail-closed, and unable to reach anything it must not.

What is asserted hardest is the BOUNDARY, not the feature: the plan steers where
retrieval looks and nothing else. It cannot open the gate, cannot add a domain, cannot
touch the comparison decision, is never cited, and on every failure path the pipeline
runs exactly as it did before the planner existed.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from legalmind.assist import generation, planner


def _fake(text: str):
    return generation.GenerationResult(text=text, model="fake", prompt_version="test",
                                       payload_sha256="0" * 64, latency_ms=1)


GOOD = json.dumps({"intent": "fact", "topic": "liability", "subject": "the cure period",
                   "party": "ORGANIZATION", "source_preference": "DOCUMENT",
                   "queries": ["cure period breach", "remedy breach within days",
                               "cure period breach", "", "x", "material breach not cured",
                               "a fourth query"],
                   "section_hint": "7.2."})


# --------------------------------------------------------------------------
# Parsing — a closed vocabulary, clipped, never trusted
# --------------------------------------------------------------------------
def test_a_good_reply_parses_into_a_validated_plan():
    p = planner.parse_plan(GOOD, "how much time do we get to fix a breach?")
    assert p is not None
    assert p.intent == "FACT"                       # upper-cased into the vocabulary
    assert p.topic == "Liability"                   # case-insensitive match to TOPICS
    assert p.party == "ORGANIZATION" and p.source_preference == "DOCUMENT"
    # duplicates, empties and one-character junk dropped; capped at MAX_QUERIES
    assert p.queries == ("cure period breach", "remedy breach within days",
                         "material breach not cured")
    assert p.section_hint == "7.2"                  # trailing full stop removed


@pytest.mark.parametrize("reply", ["", "nonsense", "[1, 2, 3]", '{"intent": ', "null"])
def test_an_unparseable_reply_is_no_plan(reply):
    assert planner.parse_plan(reply, "q") is None


def test_unknown_values_fall_to_neutral_and_unknown_topics_to_none():
    p = planner.parse_plan(json.dumps({"intent": "GUESS", "topic": "Something Else",
                                       "party": "ALIENS", "source_preference": "GOOGLE",
                                       "queries": "not a list", "section_hint": "seven"}),
                           "q")
    assert (p.intent, p.topic, p.party, p.source_preference) == ("FACT", None, "NONE", "ANY")
    assert p.queries == () and p.section_hint is None


def test_a_query_that_merely_repeats_the_question_is_dropped():
    q = "What is the termination notice period?"
    p = planner.parse_plan(json.dumps({"queries": [q, q.lower(), "notice to terminate"]}), q)
    assert p.queries == ("notice to terminate",)


def test_prose_around_the_json_is_tolerated():
    p = planner.parse_plan("Here is the plan:\n" + GOOD + "\nHope this helps.", "q")
    assert p is not None and p.topic == "Liability"


# --------------------------------------------------------------------------
# The topic vocabulary is the Constitution's, read off the ratified standards
# --------------------------------------------------------------------------
def test_topics_are_exactly_the_ratified_standards_appendix_b_topics():
    from legalmind.assist.positions import RATIFIED_STANDARDS_DIR

    expected = {json.loads(p.read_text())["configuration"]["constitution"]["topic"]
                for p in RATIFIED_STANDARDS_DIR.glob("*.json")}
    assert set(planner.TOPICS) == expected
    assert len(planner.TOPICS) >= 10
    assert "Liability" in planner.TOPICS and "Termination & Suspension" in planner.TOPICS


# --------------------------------------------------------------------------
#: The ONLY shape that now reaches the provider: the lexical table cannot place
#: it (no cue, no canonical term, no section number) AND it reads ambiguous
#: (conditional + referential). Every test below that asserts a provider call
#: must use a question of this shape, or it is testing the cheap path.
UNPLACED = "if that happens, what else applies?"


# plan() — fail-closed on every path, and exactly the permitted payload
# --------------------------------------------------------------------------
def test_off_means_no_plan_and_no_provider_call(monkeypatch):
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "off")

    def boom(*a, **k):
        raise AssertionError("no provider call may be made while disabled")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert planner.plan("what is the cure period?") is None


def test_off_by_default_after_measurement(monkeypatch):
    """Measured 2026-09-17: +4.6 s p50 per ask for no demonstrated ranking gain on the ratified set.
    The mechanism ships built, tested and fail-closed; the default does not pay for it."""
    monkeypatch.delenv("LEGALMIND_QUERY_PLANNER", raising=False)

    def boom(*a, **k):
        raise AssertionError("no provider call may be made while disabled")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert planner.plan("what is the cure period?") is None


def test_on_when_asked(monkeypatch):
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake(GOOD))
    assert planner.plan("what is the cure period?") is not None


@pytest.mark.parametrize("failure", [generation.GenerationRefused("gate"),
                                     generation.GenerationUnavailable("timeout")])
def test_a_provider_failure_is_no_plan(monkeypatch, failure):
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")

    def fail(*a, **k):
        raise failure

    monkeypatch.setattr(generation, "generate_raw", fail)
    assert planner.plan(UNPLACED) is None


def test_an_unparseable_reply_is_no_plan_at_the_seam(monkeypatch):
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake("I think..."))
    assert planner.plan(UNPLACED) is None


def test_an_empty_question_is_no_plan_and_no_call(monkeypatch):
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")

    def boom(*a, **k):
        raise AssertionError("no call for an empty question")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert planner.plan("   ") is None


def test_the_call_is_bounded_and_carries_only_the_permitted_payload(monkeypatch):
    """`AM-30` t2 as amended by `AM-58` r1: the question, the prior USER questions, the
    template. Nothing else — no chunk, no position, no statute text. And a hard
    timeout: a late plan is worth less than no plan."""
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")
    seen: dict = {}

    def capture(prompt, **kwargs):
        seen["prompt"] = prompt
        seen.update(kwargs)
        return _fake(GOOD)

    monkeypatch.setattr(generation, "generate_raw", capture)
    planner.plan(UNPLACED,
                 ["what is the termination notice period?"], request_id="r-1")
    assert seen["prompt_version"] == planner.PLAN_PROMPT_VERSION == "query-plan-1"
    assert seen["timeout_s"] == planner.PLAN_TIMEOUT_S <= 10
    assert seen["max_output_tokens"] <= 256
    assert UNPLACED in seen["prompt"]
    assert "what is the termination notice period?" in seen["prompt"]
    assert planner.CONTEXT_HEADER in seen["prompt"]
    for topic in planner.TOPICS:
        assert topic in seen["prompt"]
    # The template refuses to answer or advise — the plan is a search plan, not a reply.
    assert "Do NOT answer the question" in seen["prompt"]
    assert "Do NOT give legal advice" in seen["prompt"]


def test_no_prior_questions_means_no_context_block(monkeypatch):
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")
    seen: dict = {}

    def capture(prompt, **kwargs):
        seen["prompt"] = prompt
        return _fake(GOOD)

    monkeypatch.setattr(generation, "generate_raw", capture)
    planner.plan(UNPLACED)
    assert planner.CONTEXT_HEADER not in seen["prompt"]


def test_as_filters_carries_enums_and_phrases_only():
    p = planner.parse_plan(GOOD, "q")
    record = p.as_filters()
    assert set(record) == {"prompt_version", "intent", "topic", "subject", "party",
                           "source_preference", "queries", "section_hint"}
    assert record["prompt_version"] == "query-plan-1"
    json.dumps(record)   # must be JSONB-safe


# --------------------------------------------------------------------------
# The boundary, asserted on the AST
# --------------------------------------------------------------------------
def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            out.add(node.module or "")
            out |= {a.name for a in node.names}
    return out


def test_the_planner_reaches_no_retrieval_and_no_persistence():
    """It reads a plan out of the model and returns it. If it could retrieve or
    persist, a later edit could give it authority it must never have."""
    imported = _imports(pathlib.Path(planner.__file__))
    assert not (imported & {"store", "positions", "statutes", "sqlalchemy", "routing",
                            "intent", "guardrails", "rescue"}), imported


def test_routing_and_the_safety_screens_cannot_see_the_plan():
    """`AM-25` r4 / `AM-45` r3 / `AM-68` r1: which route a question takes is decided by
    code the plan cannot influence — the planner is not importable from there."""
    from legalmind.assist import intent, routing

    for module in (routing, intent):
        assert "planner" not in _imports(pathlib.Path(module.__file__)), module.__name__


# ==========================================================================
# The cheap path (Phase 1, 2026-09-18) — a plan for nothing, or no plan
# ==========================================================================
def test_the_cheap_path_makes_no_provider_call_at_all(monkeypatch):
    """The whole point of Phase 1: the common question costs no call and no
    latency. Phase 1's first attempt spent 4,788 ms p50 asking about every
    question; the table answers this one for free."""
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")

    def boom(*a, **k):
        raise AssertionError("the cheap path reached the provider")

    monkeypatch.setattr(generation, "generate_raw", boom)
    made = planner.plan("how much time do we get to fix a breach?")
    assert made is not None
    assert made.topic == "Termination & Suspension"
    assert "cure period" in made.queries


def test_a_plain_question_the_table_cannot_place_costs_no_call_either(monkeypatch):
    """Rung two: nothing to add, and nothing ambiguous to resolve. Retrieval
    runs exactly as it does today — a simple question does not pay for a
    planner."""
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")

    def boom(*a, **k):
        raise AssertionError("a plain question reached the provider")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert planner.plan("are we allowed to recruit their staff?") is None


def test_only_an_unplaced_ambiguous_question_reaches_the_provider(monkeypatch):
    monkeypatch.setenv("LEGALMIND_QUERY_PLANNER", "on")
    calls: list[str] = []

    def capture(prompt, **kwargs):
        calls.append(prompt)
        return _fake(GOOD)

    monkeypatch.setattr(generation, "generate_raw", capture)
    assert planner.plan(UNPLACED) is not None
    assert len(calls) == 1


# -- the precision rule: contribute a term, never a paraphrase --------------
def test_a_term_the_reader_already_used_is_never_added_as_a_query():
    """The measured precision loss (0.390 -> 0.358) was extra queries adding
    their own rank-fused lists. A reader who typed "cure period" already has
    that lexical pass; repeating it only dilutes the gold share."""
    made = planner.plan_lexical("what is the cure period?")
    assert made is not None
    assert made.queries == ()          # nothing to contribute
    assert made.topic == "Termination & Suspension"   # but still aimed


def test_a_term_the_reader_lacks_is_contributed_once():
    made = planner.plan_lexical("how much time do we get to fix a breach?")
    assert made is not None and made.queries == ("cure period",)


@pytest.mark.parametrize("question", [
    "what is the liability cap?",
    "what are the payment terms?",
    "what is the force majeure clause?",
    "what is the governing law?",
])
def test_a_question_already_in_legal_terms_contributes_nothing(question):
    made = planner.plan_lexical(question)
    assert made is not None and made.queries == ()


def test_the_cheap_path_never_exceeds_three_queries():
    #  A question touching many cues at once still obeys MAX_QUERIES.
    made = planner.plan_lexical(
        "if they get acquired or discontinue the service, who pays, which court "
        "hears it, and can we walk away and stop paying?")
    assert made is not None and len(made.queries) <= planner.MAX_QUERIES


def test_a_section_number_in_the_sentence_becomes_the_hint():
    made = planner.plan_lexical("what does section 17.2 say about the cap?")
    assert made is not None and made.section_hint == "17.2"


# -- the table is vocabulary, not law --------------------------------------
def test_every_cue_names_a_topic_the_ratified_standards_carry():
    """The guard that keeps the table vocabulary: a topic cannot be invented
    here, only named. Rules 7 and 21."""
    for _, _, topic in planner._TERMS:
        assert topic in planner.TOPICS


def test_the_table_states_no_threshold_and_no_position():
    """No number, no duration, no acceptance word — a search thesaurus cannot
    smuggle in what a standard requires."""
    forbidden = ("month", "days", "year", "acceptab", "unacceptab", "%",
                 "shall", "must not", "deviat")
    for cue, term, _ in planner._TERMS:
        assert not any(ch.isdigit() for ch in term), term
        assert not any(w in term.casefold() for w in forbidden), term
        assert not any(ch.isdigit() for ch in cue), cue


def test_the_cheap_path_leaves_the_recorded_fields_neutral():
    """`party` and `source_preference` narrow nothing, so the lexical path does
    not guess at them — routing decides domains from permissions (`AM-45` r1)."""
    made = planner.plan_lexical("how much time do we get to fix a breach?")
    assert made is not None
    assert made.party == "NONE" and made.source_preference == "ANY"


def test_the_cheap_path_still_returns_nothing_when_the_flag_is_off(monkeypatch):
    monkeypatch.delenv("LEGALMIND_QUERY_PLANNER", raising=False)
    assert planner.plan("how much time do we get to fix a breach?") is None
