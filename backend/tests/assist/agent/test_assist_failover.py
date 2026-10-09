"""Provider failover (`AM-124`, owner 2026-10-08): Gemini → DeepSeek → Bonsai on an
infrastructure failure only. Fakes throughout — no provider is ever called."""
import pytest

from legalmind.assist.agent import agent
from legalmind.assist.agent import model_router as mr
from legalmind.assist.llm import generation

GEMINI, DEEPSEEK, BONSAI = (mr.MODELS[i] for i in ("gemini", "deepseek", "bonsai"))


def _result(model: str) -> generation.TurnResult:
    return generation.TurnResult(text="ok", model=model, prompt_version="v",
                                 payload_sha256="h", latency_ms=5,
                                 prompt_tokens=1000, output_tokens=100)


class Fake:
    def __init__(self, name, *failures):
        self.name, self.failures, self.calls = name, list(failures), 0

    def turn(self, system, contents, **kw):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return _result(self.name)


def _call(p, timeout_s=30.0):
    return p.turn("system", [{"text": "q"}], tools=None, schema=None,
                  timeout_s=timeout_s, request_id="r")


@pytest.fixture(autouse=True)
def windows(monkeypatch):
    monkeypatch.setenv("LEGALMIND_DEEPSEEK_CONTEXT_TOKENS", "128000")
    monkeypatch.setenv("LEGALMIND_BONSAI_CONTEXT_TOKENS", "128000")
    events = []
    monkeypatch.setattr(mr, "log_event", lambda event, **kw: events.append((event, kw)))
    mr._RECENT.clear()
    return events


def _unavailable(message):
    return generation.GenerationUnavailable(message)


@pytest.mark.parametrize("failure", ["provider returned HTTP 503", "provider returned HTTP 429",
                                     "provider returned HTTP 502", "TimeoutError",
                                     "URLError", "RemoteDisconnected"])
def test_an_infrastructure_failure_moves_on_to_the_next_model(failure, windows):
    g, d = Fake("gemini", _unavailable(failure)), Fake("deepseek")
    p = mr.FailoverProvider([(GEMINI, g), (DEEPSEEK, d)])
    assert _call(p).model == "deepseek"
    assert p.hops == [{"from": "gemini", "to": "deepseek", "reason": failure}]
    assert any(e == "assist.agent.failover" and kw["reason"] == failure for e, kw in windows)


@pytest.mark.parametrize("failure", [
    generation.GenerationRefused("payload screen"),          # LEGAL-02 — never elsewhere
    _unavailable("provider returned HTTP 400"),
    _unavailable("provider response had no candidate"),       # quality is routing
])
def test_a_refusal_a_4xx_or_a_bad_reply_is_never_failed_over(failure):
    g, d = Fake("gemini", failure), Fake("deepseek")
    with pytest.raises(type(failure)):
        _call(mr.FailoverProvider([(GEMINI, g), (DEEPSEEK, d)]))
    assert d.calls == 0


def test_a_model_whose_window_is_unknown_or_too_small_is_skipped(monkeypatch):
    monkeypatch.delenv("LEGALMIND_DEEPSEEK_CONTEXT_TOKENS")
    monkeypatch.setenv("LEGALMIND_BONSAI_CONTEXT_TOKENS", "1")
    g, d, b = Fake("gemini", _unavailable("TimeoutError")), Fake("deepseek"), Fake("bonsai")
    with pytest.raises(generation.GenerationUnavailable):
        _call(mr.FailoverProvider([(GEMINI, g), (DEEPSEEK, d), (BONSAI, b)]))
    assert d.calls == b.calls == 0


def test_failover_is_sticky_for_the_rest_of_the_turn():
    g, d = Fake("gemini", _unavailable("provider returned HTTP 503")), Fake("deepseek")
    p = mr.FailoverProvider([(GEMINI, g), (DEEPSEEK, d)])
    _call(p), _call(p)
    assert (g.calls, d.calls) == (1, 2)


def test_no_hop_when_too_little_of_the_turn_is_left():
    g, d = Fake("gemini", _unavailable("TimeoutError")), Fake("deepseek")
    with pytest.raises(generation.GenerationUnavailable):
        _call(mr.FailoverProvider([(GEMINI, g), (DEEPSEEK, d)]), timeout_s=mr.MIN_HOP_S - 1)
    assert d.calls == 0


def test_the_turn_keeps_the_chosen_models_profile():
    p = mr.FailoverProvider([(DEEPSEEK, Fake("deepseek")), (BONSAI, Fake("bonsai"))])
    assert (p.label, p.lean, p.done_check) == ("DeepSeek", False, False)


def test_the_cost_difference_is_logged_when_the_rates_are_set(monkeypatch, windows):
    for k, v in {"GEMINI_USD_PER_M_IN": "0.3", "GEMINI_USD_PER_M_OUT": "2.5",
                 "DEEPSEEK_USD_PER_M_IN": "0.5", "DEEPSEEK_USD_PER_M_OUT": "1.5"}.items():
        monkeypatch.setenv(f"LEGALMIND_{k}", v)
    g, d = Fake("gemini", _unavailable("provider returned HTTP 503")), Fake("deepseek")
    _call(mr.FailoverProvider([(GEMINI, g), (DEEPSEEK, d)]))
    answered = [kw for e, kw in windows if e == "assist.agent.failover_answered"]
    # 1000 in, 100 out: DeepSeek 0.00065 against Gemini 0.00055
    assert answered and answered[0]["cost_delta_usd"] == pytest.approx(0.0001)


def test_more_than_five_percent_of_calls_failing_over_raises_the_signal(windows):
    def hop():
        _call(mr.FailoverProvider([(GEMINI, Fake("gemini", _unavailable("TimeoutError"))),
                                   (DEEPSEEK, Fake("deepseek"))]))
    steady = mr.FailoverProvider([(GEMINI, Fake("gemini")), (DEEPSEEK, Fake("deepseek"))])
    for _ in range(19):
        _call(steady)
    hop()                                   # 1 in 20: exactly 5%, not more — quiet
    assert not [e for e, _ in windows if e == "assist.provider_failover_rate"]
    hop()                                   # 2 in 21: over 5% — a human looks
    signals = [kw for e, kw in windows if e == "assist.provider_failover_rate"]
    assert signals and signals[0]["signal"] == "assist.provider_failover_rate"


def _configure(monkeypatch, flag):
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "on")
    monkeypatch.setenv("LEGALMIND_ASK_FAILOVER", flag)
    for m in (DEEPSEEK, BONSAI):
        monkeypatch.setenv(m.key_env, "k")
        monkeypatch.setenv(m.base_url_env, "https://example.invalid/v1")


def test_off_by_default_the_chosen_model_alone_answers(monkeypatch):
    _configure(monkeypatch, "off")
    assert isinstance(mr.provider("gemini"), agent.GeminiProvider)


def test_on_the_chain_runs_forward_from_the_chosen_model_never_back_to_gemini(monkeypatch):
    _configure(monkeypatch, "on")
    chain = mr.provider("gemini")
    assert [m.id for m, _ in chain.chain] == ["gemini", "deepseek", "bonsai"]
    assert [m.id for m, _ in mr.provider("deepseek").chain] == ["deepseek", "bonsai"]
    assert isinstance(mr.provider("bonsai"), agent.OpenAICompatProvider)
