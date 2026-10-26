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
            breaker.guarded("Gemini", _failing(generation.GenerationUnavailable("429"),
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
    for exc in (generation.GenerationUnavailable("503"), generation.GenerationRefused("x"),
                generation.GenerationUnavailable("503")):
        with pytest.raises((generation.GenerationUnavailable, generation.GenerationRefused)):
            breaker.guarded("Gemini", _failing(exc, calls))
    assert breaker.guarded("Gemini", lambda: "ok") == "ok"
    for _ in range(2):                              # a success resets the count
        with pytest.raises(generation.GenerationUnavailable):
            breaker.guarded("Gemini", _failing(generation.GenerationUnavailable("x"), calls))
    assert breaker.guarded("Gemini", lambda: "ok") == "ok"
