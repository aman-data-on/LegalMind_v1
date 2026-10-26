"""A per-turn token ceiling (enterprise-readiness plan D8; owner O2 "maximum cost per
query"; OWASP LLM10 unbounded consumption; `AM-203`). Unset, nothing changes; set, no
new decision step starts once the turn has spent it — the answer is still written."""
from legalmind import config
from legalmind.assist.agent import agent


def _turn_with(tokens):
    r = agent.TurnResult(blocks=[], assessment="n/a", outcome="answered", registry=None)
    r.calls = [agent.CallStat("decision", tokens, 0, 10, "m", "v", "")]
    return r


def test_no_ceiling_unless_one_is_set(monkeypatch):
    monkeypatch.delenv("LEGALMIND_ASK_MAX_TOKENS_PER_TURN", raising=False)
    assert config.ask_max_tokens_per_turn() is None
    assert agent._should_stop(_turn_with(10**7), 0.0) is None


def test_the_turn_stops_deciding_at_its_token_ceiling(monkeypatch):
    monkeypatch.setenv("LEGALMIND_ASK_MAX_TOKENS_PER_TURN", "50000")
    assert agent._should_stop(_turn_with(49_000), 0.0) is None
    assert agent._should_stop(_turn_with(50_000), 0.0) == "token_budget"
    monkeypatch.setenv("LEGALMIND_ASK_MAX_TOKENS_PER_TURN", "not a number")
    assert config.ask_max_tokens_per_turn() is None
