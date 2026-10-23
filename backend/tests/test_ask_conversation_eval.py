"""The conversation eval's scoring (enterprise-readiness plan P0) — pure, no database,
no model. The replay itself is a measurement run and is not part of the suite."""
import json
from datetime import UTC, datetime
from pathlib import Path

from tools import ask_conversation_eval as ev
from tools import ask_turn_trace as trace


def _turn(reply="An answer.", cited=()):
    t = trace.Turn(0, "q", reply, "ANSWERED", "m", datetime(2026, 10, 22, tzinfo=UTC))
    t.cited = [trace.Cited(k, "src", b, "current") for k, b in cited]
    return t


def test_each_expectation_fails_only_on_what_it_names():
    assert ev.score(_turn(), {"outcome": "answered"}, {"route": "model"}) == []
    assert ev.score(_turn(), {"outcome": "prerouted"}, {"route": "model"}) == [
        "ROUTE: a fixed reply where the model should answer"]
    brand = ev.score(_turn(cited=[("C7", "Leapswitch")]), {}, {"forbid_brand": "Leapswitch"})
    assert brand == ["BRAND: cites a published Leapswitch policy ['C7']"]
    assert ev.score(_turn(), {"flags": ["points:14/16"]}, {"all_points": True}) == [
        "POINTS: 14 of 16 answered"]
    assert ev.score(_turn(), {}, {"all_points": True}) == [
        "POINTS: the list was not read as points"]
    verdict = ev.score(_turn("Yes, this is acceptable."), {},
                       {"forbid": [r"\bis acceptable\b"], "require": ["Sales team"]})
    assert verdict == ["FORBID: /\\bis acceptable\\b/", "REQUIRE: /Sales team/"]


def test_the_cases_are_well_formed_and_name_no_client():
    data = json.loads((Path(ev.__file__).resolve().parents[1] / "tests" / "assist_eval"
                       / "ask_conversations.json").read_text())
    ids = [c["id"] for c in data["cases"]]
    assert len(ids) == len(set(ids)) and ids
    allowed = {"route", "forbid_brand", "all_points", "forbid", "require"}
    for case in data["cases"]:
        assert case["turns"] and case["severity"] in {"Critical", "High", "Medium", "Low"}
        for step in case["turns"]:
            assert set(step.get("expect", {})) <= allowed, case["id"]


def test_without_a_turn_log_the_reply_itself_says_fixed_reply_and_points():
    from legalmind.assist.query import capability
    brief = capability.brief(capability.load())
    assert ev.observed(brief, None)["outcome"] == "prerouted"
    partial = ev.observed("Your message lists 16 points; 15 are answered below, in order", None)
    assert partial == {"outcome": "answered", "flags": ["points:15/16"]}
    whole = ev.observed("Your message lists 4 points; each is answered below, in order.", None)
    assert whole["flags"] == ["points:4/4"]


def test_every_model_lands_on_one_page():
    def run(model, ok):
        return {"model": model, "repeat": 1, "calls_used": 3, "results": [
            {"id": "C01", "pass": ok, "turns": [
                {"outcome": "answered", "latency_ms": 1000, "calls": 3, "tokens": 900}]}]}
    page = ev.matrix([run("gemini", True), run("deepseek", False)])
    assert "gemini#1" in page and "deepseek#1" in page
    assert "C01   PASS" in page and "FAIL" in page
    assert "deepseek#1: passed 0/1" in page


def test_a_forbidden_phrase_counts_only_where_the_reply_asserts_it():
    """Run 2026-10-22: five FAILs were the reply doing the right thing — leaving it open,
    denying it, or quoting the client's instruction to flag it."""
    expect = {"forbid": [r"\b(is|are|would be) acceptable\b",
                         r"(accepts?|accepted|agree[sd]? to) unlimited liability"]}
    for good in ["Whether that difference is acceptable is Legal's call.",
                 "The sources do not state that a 45-day cycle is acceptable.",
                 "Your email states an instruction to confirm that Leapswitch accepts "
                 "unlimited liability; it is not followed."]:
        assert ev.score(_turn(good), {}, expect) == [], good
    assert ev.score(_turn("A 45-day cycle is acceptable for this client."), {},
                    expect) == ["FORBID: /\\b(is|are|would be) acceptable\\b/"]
