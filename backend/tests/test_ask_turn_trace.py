"""The Ask turn trace (enterprise-readiness plan §7A step 3): what it reads off the record.
Pure functions only — no database, no journal, no model."""
from datetime import UTC, datetime, timedelta

from tools import ask_turn_trace as trace


def _turn(message="what is the uptime?", cited=(), log=None, ordinal=0, state="ANSWERED"):
    t = trace.Turn(ordinal, message, "reply", state, "m", datetime(2026, 10, 22, 10, 30,
                                                                    tzinfo=UTC))
    t.cited = [trace.Cited(k, "src", b, s) for k, b, s in cited]
    t.log = log
    return t


def test_a_published_policy_names_its_brand_and_nothing_else_does():
    assert trace.brand_of("PUBLISHED_TOS_CLOUDPE") == "CloudPe"
    assert trace.brand_of("PUBLISHED_SLA_LEAPSWITCH") == "Leapswitch"
    assert trace.brand_of("COMPANY_CONSTITUTION") is None and trace.brand_of(None) is None


def test_the_findings_are_the_plans_failure_classes_on_the_record():
    both = [("C1", "CloudPe", "current"), ("C2", "Leapswitch", "current")]
    mixed = _turn(cited=both, log={"outcome": "answered", "flags": [], "brand": "CloudPe"})
    assert any(f.startswith("T1 WRONG_BRAND") for f in trace.findings(mixed))
    # no brand decided: both brands, each labelled, is the design (C-19) — noted, never
    # a zero-tolerance trigger (production replay 2026-10-23: 19 false alarms)
    open_scope = _turn(cited=both, log={"outcome": "answered", "flags": []})
    assert [f for f in trace.findings(open_scope) if f.startswith("T1")] == [
        "T1 BOTH_BRANDS: no brand decided; cites ['CloudPe', 'Leapswitch']"]
    wrong = _turn("the CloudPe SLA credits", [("C2", "Leapswitch", "current")],
                  {"outcome": "answered", "flags": []})
    assert any(f.startswith("T1 WRONG_BRAND") for f in trace.findings(wrong))
    stale = _turn(cited=[("C3", None, "stale")], log={"outcome": "answered", "flags": []})
    assert any(f.startswith("T3 NOT_CURRENT") for f in trace.findings(stale))
    labelled = _turn(cited=[("H1", None, "historical"), ("D5", None, "draft")],
                     log={"outcome": "answered", "flags": []})
    assert trace.findings(labelled) == []     # labels the reader sees, not staleness
    partial = _turn(log={"outcome": "answered", "flags": ["points:14/16"], "dropped": "17"})
    found = trace.findings(partial)
    assert "T8 POINTS_PARTIAL: 14 of 16 points answered" in found
    assert "VERIFIER_DROPPED: blocks 17" in found
    fixed = _turn(ordinal=2, log={"outcome": "prerouted", "flags": ""})
    assert "T18 FIXED_REPLY_MID_CONVERSATION" in trace.findings(fixed)
    assert trace.findings(_turn(log={"outcome": "answered", "flags": []})) == []


def test_each_reply_takes_the_turn_line_logged_just_before_it_once():
    a, b = _turn(ordinal=0), _turn(ordinal=2)
    b.created_at = a.created_at + timedelta(minutes=2)
    lines = [{"_ts": a.created_at - timedelta(seconds=70), "outcome": "answered"},
             {"_ts": b.created_at - timedelta(seconds=1), "outcome": "prerouted"},
             {"_ts": a.created_at - timedelta(hours=1), "outcome": "stray"}]
    a.log = b.log = None
    trace.match_logs([a, b], lines)
    assert a.log["outcome"] == "answered" and b.log["outcome"] == "prerouted"
