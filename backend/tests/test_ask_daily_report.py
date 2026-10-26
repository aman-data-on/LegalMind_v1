"""The daily Ask report's numbers and rollback triggers (plan D9) — pure, no database."""
from datetime import UTC, datetime

from tools import ask_daily_report as rep
from tools import ask_turn_trace as trace


def _t(log, findings=()):
    t = trace.Turn(0, "q", "r", "ANSWERED", "m", datetime(2026, 10, 22, tzinfo=UTC))
    t.log, t.findings = log, list(findings)
    return t


def test_a_clean_day_fires_nothing_and_counts_points_latency_and_tokens():
    day = [_t({"outcome": "answered", "total_ms": "20000", "calls": "3",
               "prompt_tokens": "40000", "output_tokens": "2000",
               "flags": "points:15/16"}),
           _t({"outcome": "prerouted", "total_ms": "5", "calls": "0"})]
    s = rep.summarise(day, floor_rate=0.1)
    assert s["triggers"] == [] and s["points_answered"] == "15/16"
    assert s["model_turns"] == 1 and s["tokens_per_turn"] == 42000


def test_a_cross_brand_citation_or_too_many_floors_fires_a_trigger():
    bad = [_t({"outcome": "answered", "total_ms": "1"}, ["T1 WRONG_BRAND: x"]),
           _t({"outcome": "floor", "total_ms": "1"})]
    s = rep.summarise(bad, floor_rate=0.1)
    assert "T1 WRONG_BRAND: 1" in s["triggers"]
    assert any(x.startswith("floor rate") for x in s["triggers"])
