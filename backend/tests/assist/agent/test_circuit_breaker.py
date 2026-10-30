"""A model that keeps failing is not called again for a while (enterprise-readiness plan
D10; Azure/AWS circuit-breaker pattern; `AM-204`): a daily-quota 429 made every reader
wait a full timeout and get the floor. No provider is called."""
import pytest

from legalmind.assist.llm import breaker, generation


@pytest.fixture(autouse=True)
def _fresh():
    breaker.reset()
    yield
    breaker.reset()


def _failing(exc, calls):
    def call():
        calls.append(1)
        raise exc
    return call


def test_three_infrastructure_failures_open_the_circuit_and_skip_the_network():
    now, calls = [1000.0], []
    for _ in range(3):
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("Gemini", _failing(generation.GenerationUnavailable("provider returned HTTP 429"),
                                                calls), clock=lambda: now[0])
    with pytest.raises(generation.GenerationUnavailable, match="circuit open"):
        breaker.guarded("Gemini", lambda: calls.append(1) or "ok", clock=lambda: now[0])
    assert len(calls) == 3                          # no network while open
    # another model is unaffected: failover moves on at once
    assert breaker.guarded("DeepSeek", lambda: "ok", clock=lambda: now[0]) == "ok"
    now[0] += breaker.BREAKER_OPEN_S + 1            # cool-down over: a trial goes through
    assert breaker.guarded("Gemini", lambda: "ok", clock=lambda: now[0]) == "ok"


def test_a_refusal_or_a_success_never_trips_it():
    calls: list[int] = []
    for exc in (generation.GenerationUnavailable("provider returned HTTP 503"), generation.GenerationRefused("x"),
                generation.GenerationUnavailable("provider returned HTTP 503")):
        with pytest.raises((generation.GenerationUnavailable, generation.GenerationRefused)):
            breaker.guarded("Gemini", _failing(exc, calls))
    assert breaker.guarded("Gemini", lambda: "ok") == "ok"
    for _ in range(2):                              # a success resets the count
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("Gemini", _failing(generation.GenerationUnavailable("x"), calls))
    assert breaker.guarded("Gemini", lambda: "ok") == "ok"


def test_only_the_providers_failures_count():
    """Code review 2026-10-26: a 400 from our own payload, an empty candidate, or a
    timeout on the few seconds a turn had left is one request's failure, not an outage —
    three of them must never shut a healthy model for every reader."""
    calls: list[int] = []
    mine = [generation.GenerationUnavailable("provider returned HTTP 400"),
            generation.GenerationUnavailable("provider response had no candidate")]
    for exc in mine * 2:
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("Gemini", _failing(exc, calls))
    for _ in range(3):                              # a short budget's timeout
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("Gemini", _failing(generation.GenerationUnavailable(
                "TimeoutError"), calls), budget_s=4.0)
    assert breaker.guarded("Gemini", lambda: "ok") == "ok"


def test_a_failed_trial_reopens_at_once():
    now, calls = [1000.0], []
    fail = generation.GenerationUnavailable("provider returned HTTP 503")
    for _ in range(3):
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("Gemini", _failing(fail, calls), clock=lambda: now[0])
    now[0] += breaker.BREAKER_OPEN_S + 1
    with pytest.raises(generation.GenerationUnavailable):   # the trial fails ...
        breaker.guarded("Gemini", _failing(fail, calls), clock=lambda: now[0])
    with pytest.raises(generation.GenerationUnavailable, match="circuit open"):
        breaker.guarded("Gemini", lambda: "ok", clock=lambda: now[0])  # ... open again
    assert len(calls) == 4


def test_a_failure_long_after_a_closed_circuit_is_counted_afresh():
    now, calls = [1000.0], []
    fail = generation.GenerationUnavailable("provider returned HTTP 503")
    for _ in range(3):
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("Gemini", _failing(fail, calls), clock=lambda: now[0])
    now[0] += 3600                                   # an hour later, one 503 ...
    with pytest.raises(generation.GenerationUnavailable):
        breaker.guarded("Gemini", _failing(fail, calls), clock=lambda: now[0])
    assert breaker.guarded("Gemini", lambda: "ok", clock=lambda: now[0]) == "ok"  # ... closed


def _fail(model, said, now):
    with pytest.raises(generation.GenerationUnavailable):
        breaker.guarded(model, _failing(generation.GenerationUnavailable(said), []),
                        clock=lambda: now)


def test_one_402_pauses_the_model_for_minutes_and_a_success_ends_it(caplog):
    """AM-222 (2026-10-27): the credit ran out (HTTP 402). One is enough — a retry in
    seconds cannot help — and the cause is kept for the notice, alerted once."""
    now = [1000.0]
    for _ in range(2):
        _fail("Gemini", "provider returned HTTP 402", now[0])
        now[0] += breaker.PAUSE_OPEN_S + 1        # the second 402 is the trial
    assert breaker.paused(lambda: now[0] - breaker.PAUSE_OPEN_S)["Gemini"][0] == "payment"
    assert sum(r.message == "assist.provider_paused" for r in caplog.records) == 1
    now[0] -= breaker.PAUSE_OPEN_S                # inside the second pause
    with pytest.raises(generation.GenerationUnavailable, match=r"\(paused: payment\)"):
        breaker.guarded("Gemini", lambda: "ok", clock=lambda: now[0])
    now[0] += breaker.PAUSE_OPEN_S + 1
    assert breaker.guarded("Gemini", lambda: "ok", clock=lambda: now[0]) == "ok"
    assert breaker.paused(lambda: now[0]) == {}


def test_a_pause_never_outlives_its_evidence():
    """Review of #240: the screen's minute poll never calls the model, so a pause must
    end by itself — a 402 ten minutes after it was last seen, a 429 with its circuit."""
    _fail("Gemini", "provider returned HTTP 402", 1000.0)
    assert "Gemini" in breaker.paused(lambda: 1000.0 + breaker.PAUSE_OPEN_S - 1)
    assert breaker.paused(lambda: 1000.0 + breaker.PAUSE_OPEN_S + 1) == {}
    breaker.reset()
    _fail("Gemini", "provider returned HTTP 429", 1000.0)  # one per-minute limit: no pause
    assert breaker.paused(lambda: 1000.0) == {}
    assert breaker.guarded("Gemini", lambda: "ok", clock=lambda: 1001.0) == "ok"


def test_the_latest_cause_is_reported_and_another_failure_clears_it():
    _fail("Gemini", "provider returned HTTP 429", 1000.0)
    _fail("Gemini", "provider returned HTTP 402", 1001.0)   # a later 402 is the cause now
    assert breaker.paused(lambda: 1002.0)["Gemini"][0] == "payment"
    breaker.reset()
    _fail("Gemini", "provider returned HTTP 402", 1000.0)
    _fail("Gemini", "provider returned HTTP 503", 1000.0 + breaker.PAUSE_OPEN_S + 1)
    with pytest.raises(generation.GenerationUnavailable) as raised:   # a 503 trial: no tag
        breaker.guarded("Gemini", lambda: "ok", clock=lambda: 1000.0 + breaker.PAUSE_OPEN_S + 2)
    assert "paused" not in str(raised.value)


class _FakeRedis:
    """The four calls the shared pause makes, with expiry by a settable clock."""
    def __init__(self):
        self.now, self.data = 0.0, {}

    def set(self, key, value, ex):
        self.data[key] = (value.encode(), self.now + ex)

    def get(self, key):
        value = self.data.get(key if isinstance(key, str) else key.decode())
        return value[0] if value and value[1] > self.now else None

    def delete(self, key):
        self.data.pop(key, None)

    def scan_iter(self, pattern):
        return [k.encode() for k, (_, until) in self.data.items()
                if k.startswith(pattern.rstrip("*")) and until > self.now]


def test_a_pause_is_shared_by_every_process_and_survives_a_restart(monkeypatch):
    """2026-10-30: with the Redis backend, a 402 seen by one API process pauses the model
    for all of them, and a restart (a fresh process) still knows it until it expires."""
    fake = _FakeRedis()
    monkeypatch.setenv("LEGALMIND_BREAKER_BACKEND", "redis")
    monkeypatch.setattr(breaker, "_client", [fake])
    calls: list[int] = []
    with pytest.raises(generation.GenerationUnavailable):
        breaker.guarded("Gemini", _failing(
            generation.GenerationUnavailable("provider returned HTTP 402"), calls))
    breaker.reset()                                  # another process / a restart
    assert breaker.paused()["Gemini"][0] == "payment"
    with pytest.raises(generation.GenerationUnavailable, match="circuit open"):
        breaker.guarded("Gemini", lambda: calls.append(1) or "ok")
    assert len(calls) == 1                           # nobody calls the paused provider
    fake.now += breaker.PAUSE_OPEN_S + 1             # the evidence expires
    assert breaker.paused() == {}
    assert breaker.guarded("Gemini", lambda: "ok") == "ok"


def test_only_an_open_circuit_is_shared_and_a_quota_pause_is_short(monkeypatch):
    fake, now = _FakeRedis(), [1000.0]
    monkeypatch.setenv("LEGALMIND_BREAKER_BACKEND", "redis")
    monkeypatch.setattr(breaker, "_client", [fake])
    quota = generation.GenerationUnavailable("provider returned HTTP 429")
    with pytest.raises(generation.GenerationUnavailable):
        breaker.guarded("DeepSeek", _failing(quota, []), clock=lambda: now[0])
    assert fake.data == {}                           # one 429 opens no circuit
    for _ in range(2):
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("DeepSeek", _failing(quota, []), clock=lambda: now[0])
    value, until = fake.data["legalmind:paused:DeepSeek"]
    assert value.startswith(b"quota|") and until == breaker.BREAKER_OPEN_S


def test_redis_down_means_the_per_process_breaker_as_before(monkeypatch):
    class Down:
        def __getattr__(self, name):
            raise ConnectionError("redis down")
    monkeypatch.setenv("LEGALMIND_BREAKER_BACKEND", "redis")
    monkeypatch.setattr(breaker, "_client", [Down()])
    assert breaker.paused() == {}
    assert breaker.guarded("Gemini", lambda: "ok") == "ok"
