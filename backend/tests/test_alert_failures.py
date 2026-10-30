"""The failure alert carries no content and repeats a problem at most every 6 hours."""
import json

from tools import alert_failures as a


def test_only_failures_count_and_only_safe_fields_leave():
    lines = [json.dumps({"event": "assist.provider_paused", "level": "ERROR", "model": "DeepSeek",
                         "kind": "payment", "request_id": "r1", "question": "secret clause"}),
             json.dumps({"event": "assist.generation.failed", "level": "WARNING", "status": "402",
                         "operational_failure": True, "payload_sha256": "abc"}),
             json.dumps({"event": "assist.ask.trace", "level": "INFO"}),
             "not json"]
    seen = a.problems(lines, ["legalmind-hard-benchmark.service"])
    assert set(seen) == {"assist.provider_paused model=DeepSeek kind=payment",
                         "assist.generation.failed status=402",
                         "systemd unit failed: legalmind-hard-benchmark.service"}
    text = a.message(seen, list(seen))
    assert "secret" not in text and "r1" not in text and "abc" not in text


def test_a_problem_is_repeated_at_most_every_six_hours():
    seen = a.problems([json.dumps({"event": "x", "level": "ERROR"})], [])
    state: dict[str, float] = {}
    assert a.due(seen, state, 1000.0) == ["x"]
    assert a.due(seen, state, 1000.0 + 600) == []
    assert a.due(seen, state, 1000.0 + a.REPEAT_S) == ["x"]
