"""The OpenAI-compatible Ask provider (`AM-117`): the agent's Gemini shapes translated
both ways at one point, and every call through the one egress seam — the payload
screen, the credential rule, the usage count and the audit identity of a Gemini call.
No network: `urllib.request.urlopen` is replaced, and nothing is sent anywhere."""
import io
import json
import urllib.request

import pytest

from legalmind.assist.llm import generation

ENDPOINT = generation.Endpoint(provider="indierouter", base_url="https://router.example/v1/",
                               key="sk-real-looking-key", model="deepseek-v4.1-flash")


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _provider(monkeypatch, message: dict, sent: list):
    body = json.dumps({"model": "deepseek-v4.1-flash", "choices": [
        {"message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30}}).encode()

    def urlopen(request, timeout=None):
        sent.append(request)
        return _Response(body)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def test_gemini_schema_types_become_json_schema_types():
    schema = {"type": "OBJECT", "properties": {
        "kind": {"type": "STRING", "enum": ["sourced"]},
        "cites": {"type": "ARRAY", "items": {"type": "STRING"}}}}
    assert generation.openai_schema(schema) == {"type": "object", "properties": {
        "kind": {"type": "string", "enum": ["sourced"]},
        "cites": {"type": "array", "items": {"type": "string"}}}}


def test_a_tool_call_and_its_response_keep_their_pairing_and_order():
    contents = [
        {"role": "user", "parts": [{"text": "NEW MESSAGE:\nIs the cap enforceable?"}]},
        {"role": "model", "parts": [
            {"functionCall": {"name": "search_knowledge", "args": {"query": "cap"},
                              "id": "c-1"}},
            {"functionCall": {"name": "search_statutes", "args": {"query": "s. 74"},
                              "id": "c-2"}}]},
        {"role": "user", "parts": [
            {"functionResponse": {"name": "search_knowledge", "response": {"n": 1}}},
            {"functionResponse": {"name": "search_statutes", "response": {"n": 2}}}]},
        {"role": "user", "parts": [{"text": "Write the final answer."}]},
    ]
    messages = generation.openai_messages("SYSTEM", contents)
    assert messages[0] == {"role": "system", "content": "SYSTEM"}
    assert messages[1]["content"].endswith("Is the cap enforceable?")
    calls = messages[2]["tool_calls"]
    assert [c["id"] for c in calls] == ["c-1", "c-2"]
    assert json.loads(calls[1]["function"]["arguments"]) == {"query": "s. 74"}
    assert [(m["role"], m["tool_call_id"]) for m in messages[3:5]] == [
        ("tool", "c-1"), ("tool", "c-2")]
    assert json.loads(messages[4]["content"]) == {"n": 2}
    assert messages[5] == {"role": "user", "content": "Write the final answer."}


def test_a_decision_step_forces_a_search_and_returns_the_agent_shape(monkeypatch):
    sent: list = []
    _provider(monkeypatch, {"content": None, "tool_calls": [
        {"id": "c-9", "type": "function",
         "function": {"name": "search_knowledge", "arguments": '{"query": "cap"}'}}]},
        sent)
    usage = {}
    token = generation.USAGE.set(usage)
    try:
        tools = [{"name": "search_knowledge", "parameters": {"type": "OBJECT"}},
                 {"name": "ask_user", "parameters": {"type": "OBJECT"}}]
        result = generation.generate_openai_turn(
            "SYSTEM", [{"role": "user", "parts": [{"text": "q"}]}], endpoint=ENDPOINT,
            prompt_version="test", environment="development", tools=tools,
            tool_mode="ANY", allowed_tools=["search_knowledge"])
    finally:
        generation.USAGE.reset(token)
    request = sent[0]
    assert request.full_url == "https://router.example/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-real-looking-key"
    payload = json.loads(request.data)
    assert payload["model"] == "deepseek-v4.1-flash" and payload["temperature"] == 0.0
    assert payload["tool_choice"] == "required"
    assert [t["function"]["name"] for t in payload["tools"]] == ["search_knowledge"]
    assert result.function_calls == ({"name": "search_knowledge", "args": {"query": "cap"},
                                      "id": "c-9"},)
    assert result.parts == ({"functionCall": result.function_calls[0]},)
    # The audit row's identity, and the usage the benchmark reports (cost guard).
    assert (result.provider, result.model) == ("indierouter", "deepseek-v4.1-flash")
    assert usage["calls"] == 1 and usage["prompt_tokens"] == 120
    assert usage["output_tokens"] == 30


def test_the_final_answer_asks_for_the_answer_schema(monkeypatch):
    sent: list = []
    _provider(monkeypatch, {"content": '{"blocks": []}'}, sent)
    result = generation.generate_openai_turn(
        "S", [], endpoint=ENDPOINT, prompt_version="t", environment="development",
        response_schema={"type": "OBJECT", "properties": {}})
    payload = json.loads(sent[0].data)
    assert payload["response_format"]["json_schema"]["schema"] == {
        "type": "object", "properties": {}}
    assert "tools" not in payload and result.text == '{"blocks": []}'


def test_the_payload_screen_and_the_credential_rule_hold_for_every_provider(monkeypatch):
    sent: list = []
    _provider(monkeypatch, {"content": "x"}, sent)
    with pytest.raises(generation.GenerationRefused):
        generation.generate_openai_turn(
            "S", [{"role": "user", "parts": [{"text": "acceptable_max: 12"}]}],
            endpoint=ENDPOINT, prompt_version="t", environment="development")
    placeholder = generation.Endpoint("bonsai", "https://lm.example/v1", "***", "m")
    with pytest.raises(generation.GenerationRefused):
        generation.generate_openai_turn("S", [], endpoint=placeholder,
                                        prompt_version="t", environment="development")
    assert sent == []          # refused before anything left the process


def test_thinking_is_sent_as_reasoning_effort_and_the_key_never_prints(monkeypatch):
    """Reasoning tokens count against `max_tokens`: at the provider default a decision
    step spent all 2,048 thinking and returned no tool call (DeepSeek, 2026-10-07)."""
    sent: list = []
    _provider(monkeypatch, {"content": "x"}, sent)
    for thinking, effort in (("MINIMAL", "none"), ("LOW", "low"), (None, None)):
        generation.generate_openai_turn("S", [], endpoint=ENDPOINT, prompt_version="t",
                                        environment="development", thinking=thinking)
        assert json.loads(sent[-1].data).get("reasoning_effort") == effort
    assert ENDPOINT.key not in repr(ENDPOINT)
