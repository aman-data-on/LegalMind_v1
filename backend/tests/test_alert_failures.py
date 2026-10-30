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


def test_the_alert_is_emailed_over_starttls_when_a_recipient_is_set(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent.append(("connect", host, port))
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def starttls(self):
            sent.append(("starttls",))
        def login(self, user, password):
            sent.append(("login", user))
        def send_message(self, msg):
            sent.append(("send", msg["To"], msg["Subject"], msg.get_content().strip()))

    monkeypatch.setattr(a.smtplib, "SMTP", FakeSMTP)
    monkeypatch.delenv("LEGALMIND_ALERT_EMAIL_TO", raising=False)
    a._email("x")
    assert sent == []                                  # no recipient: nothing sent
    monkeypatch.setenv("LEGALMIND_ALERT_EMAIL_TO", "ops@example.com")
    monkeypatch.setenv("LEGALMIND_ALERT_SMTP_USER", "alerts@example.com")
    a._email("LegalMind needs attention")
    assert sent == [("connect", "smtp.gmail.com", 587), ("starttls",),
                    ("login", "alerts@example.com"),
                    ("send", "ops@example.com", "LegalMind needs attention",
                     "LegalMind needs attention")]
