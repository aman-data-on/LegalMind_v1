"""The pooled connection is released for the provider round-trip, and two turns that
reach one conversation at the same moment are a 409 — system design review §6.4 and
§9 (2026-09-29).

Before: the request's session was held, uncommitted, across every Gemini call — up to
the 60 s timeout, one to five times per question — against a pool of fifteen
connections per process. One slow provider response starved every other endpoint.
"""
import io
import json
import logging
import urllib.request

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import generation, rerank, service, verify
from tests.test_assist_ask import (
    USER_PERMS,
    _synthetic_statute,
)

QUESTION = "What does section 3 of the Synthetic Widgets Act say about widget handling?"
SENTENCE = "Every handler shall handle every widget with synthetic care [1]."


def _provider(observe):
    """A stand-in for the network: `observe()` runs at the moment of the call, then
    the provider answers with one cited sentence."""
    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    body = json.dumps({
        "candidates": [{"content": {"parts": [{"text": SENTENCE}]},
                        "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}}).encode()

    def urlopen(request, timeout=None):
        observe()
        return _Response(body)
    return urlopen


@pytest.fixture
def credential(monkeypatch):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "test-not-a-secret")


def test_the_hook_runs_after_every_screen_and_before_the_network_call(monkeypatch,
                                                                       credential):
    order: list[str] = []
    monkeypatch.setattr(urllib.request, "urlopen",
                        _provider(lambda: order.append("network")))
    token = generation.BEFORE_EGRESS.set(lambda: order.append("release"))
    try:
        generation.generate_raw("prompt", prompt_version="t", environment="development")
    finally:
        generation.BEFORE_EGRESS.reset(token)
    assert order == ["release", "network"]


def test_a_refused_call_never_reaches_the_hook(monkeypatch):
    """Nothing is committed for a call the gate or the payload screen refused."""
    monkeypatch.delenv("LEGALMIND_GEMINI_API_KEY", raising=False)
    released: list[int] = []
    token = generation.BEFORE_EGRESS.set(lambda: released.append(1))
    try:
        with pytest.raises(generation.GenerationRefused):
            generation.generate_raw("prompt", prompt_version="t",
                                    environment="development")
    finally:
        generation.BEFORE_EGRESS.reset(token)
    assert released == []


def test_outside_the_ask_service_nothing_is_committed(monkeypatch, credential):
    """The analysis lane and the worker keep one transaction per job: the hook is
    unset there, and the seam does nothing."""
    assert generation.BEFORE_EGRESS.get() is None
    monkeypatch.setattr(urllib.request, "urlopen", _provider(lambda: None))
    result = generation.generate_raw("prompt", prompt_version="t",
                                     environment="development")
    assert result.text == SENTENCE


@pytest.mark.parametrize("flag", ["off", "on"])
def test_the_session_holds_no_transaction_while_the_provider_answers(
        db, user, tmp_path, monkeypatch, caplog, credential, flag):
    """On BOTH paths: at the moment of the network call the session has committed
    (no transaction, so no pooled connection is held) and no savepoint is open (a
    commit under one would break the caller's rollback — `_release_connection`
    refuses and logs instead, which this also proves never happens)."""
    _synthetic_statute(db, tmp_path)
    monkeypatch.setenv("LEGALMIND_ASK_MULTI_SOURCE", flag)
    # The offline stand-ins `test_ask_multi_source_rollout.py` uses: no cross-encoder
    # and no entailment model in CI.
    monkeypatch.setattr(verify, "check_answer",
                        lambda text_, *a, **k: verify.Result(True, text_, [], []))
    monkeypatch.setattr(rerank, "scores", lambda q, texts, **k: [
        10.0 if "widget" in t.lower() else -10.0 for t in texts])
    observed: list[tuple[bool, bool]] = []
    monkeypatch.setattr(urllib.request, "urlopen", _provider(
        lambda: observed.append((db.in_transaction(), db.in_nested_transaction()))))
    caplog.set_level(logging.INFO)

    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    out = service.ask(db, conversation_id=conv, question=QUESTION,
                      document_version_id=None, permissions=USER_PERMS,
                      request_id="req-release")

    assert observed, "the provider was called"
    assert observed == [(False, False)] * len(observed), observed
    assert "assist.db.release_skipped" not in {r.getMessage() for r in caplog.records}
    assert out.answer_state.value == "ANSWERED"
    # The writes after the call landed in the session's NEXT transaction: the reply
    # is there, and the session is still usable.
    schema = config.assist_schema()
    roles = db.execute(text(f'SELECT role FROM "{schema}".messages WHERE '
                            'conversation_id = :c ORDER BY ordinal'),
                       {"c": conv}).scalars().all()
    assert roles == ["USER", "ASSISTANT"]


def test_a_simultaneous_turn_is_retried_once_and_a_second_collision_is_a_409(
        db, user, monkeypatch):
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    service._append_turn(db, conv, "USER", "first")                 # ordinal 0
    # A second request that read max(ordinal) before the first turn landed sees 0
    # again; the unique constraint refuses it, and the re-read finds 1.
    real = service._next_ordinal
    stale = [0]
    monkeypatch.setattr(service, "_next_ordinal",
                        lambda d, c: stale.pop() if stale else real(d, c))
    service._append_turn(db, conv, "USER", "second")
    schema = config.assist_schema()
    ordinals = db.execute(text(f'SELECT ordinal FROM "{schema}".messages WHERE '
                               'conversation_id = :c ORDER BY ordinal'),
                          {"c": conv}).scalars().all()
    assert ordinals == [0, 1]

    # Colliding twice is reported as a conflict the reader can act on — a 409
    # through the SecurityError handler — never as an internal error, and the
    # session survives it because each attempt ran under its own savepoint.
    monkeypatch.setattr(service, "_next_ordinal", lambda d, c: 0)
    with pytest.raises(service.ConversationConflict) as raised:
        service._append_turn(db, conv, "USER", "third")
    assert raised.value.status_code == 409
    assert db.execute(text("SELECT 1")).scalar_one() == 1
    assert not db.in_nested_transaction()
