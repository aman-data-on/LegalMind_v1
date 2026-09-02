"""The Gemini connection verifier — every path except a real network call.

The tool must reuse the one permitted egress seam (`AM-26` r1), so these tests
monkeypatch ``legalmind.assist.generation.generate`` itself for the live path and
drive the configuration checks through real environment manipulation. No test
here touches the network, and none can: the seam is replaced before --live runs.
"""

from __future__ import annotations

import pytest

from legalmind.assist import generation
from tools import verify_gemini_connection as tool

# Credential-shaped and obviously not a credential. These tests exercise the
# live-call path, and since 2026-09-01 the tool refuses to attempt a provider call
# with a placeholder — a one-character "k" no longer reaches the code under test.
# That refusal is the point (it is what would have caught a literal `***` in the
# server env), so the fixture supplies a plausible value rather than the rule
# being loosened to accommodate it.
FAKE_KEY = "test-not-a-secret-value"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("LEGALMIND_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LEGALMIND_GENERATION_MODEL", raising=False)


def test_no_key_is_not_ready(capsys):
    assert tool.main(["--environment", "development"]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "api_key" in out and "NOT READY" in out


def test_key_value_is_never_printed(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "sk-SECRET-VALUE-123")
    tool.main(["--environment", "development"])
    assert "sk-SECRET-VALUE-123" not in capsys.readouterr().out


def test_config_only_makes_no_call(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", FAKE_KEY)

    def _boom(*a, **kw):  # pragma: no cover - the assertion is that it never runs
        raise AssertionError("config-only mode must not call generate()")

    monkeypatch.setattr(generation, "generate", _boom)
    assert tool.main(["--environment", "development"]) == 0
    assert "no network call made" in capsys.readouterr().out


def test_floating_model_alias_fails(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("LEGALMIND_GENERATION_MODEL", "gemini-flash-latest")
    assert tool.main(["--environment", "development"]) == 1
    assert "floating alias" in capsys.readouterr().out


def test_production_is_ready_since_the_gate_release(monkeypatch, capsys):
    """The AM-31 gate was RELEASED 2026-08-31 by its appended record, so a
    production posture with a key is READY. (Before the release this test
    asserted NOT READY with the gate row failing — that behavior now lives
    only in history, as it should.)"""
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", FAKE_KEY)
    assert tool.main(["--environment", "production"]) == 0
    out = capsys.readouterr().out
    assert "am31_gate" in out and "READY" in out


def test_live_path_uses_the_one_seam_and_passes_on_a_cited_reply(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", FAKE_KEY)
    seen: dict = {}

    def _fake_generate(question, evidence, *, environment, request_id=None):
        seen.update(question=question, evidence=evidence, environment=environment)
        return generation.GenerationResult(
            text="The vehicle is blue. [1]", model="gemini-3.6-flash",
            prompt_version=generation.PROMPT_VERSION,
            payload_sha256="ab" * 32, latency_ms=42)

    monkeypatch.setattr(generation, "generate", _fake_generate)
    assert tool.main(["--environment", "staging", "--live"]) == 0
    assert "READY" in capsys.readouterr().out
    # Synthetic-only, 55.3: exactly the fixed test strings, nothing else.
    assert seen["question"] == tool._SYNTHETIC_QUESTION
    assert seen["evidence"] == tool._SYNTHETIC_EVIDENCE
    assert seen["environment"] == "staging"


def test_live_path_fails_an_uncited_reply(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", FAKE_KEY)

    def _fake_generate(*a, **kw):
        return generation.GenerationResult(
            text="The vehicle is blue.", model="gemini-3.6-flash",
            prompt_version=generation.PROMPT_VERSION,
            payload_sha256="ab" * 32, latency_ms=42)

    monkeypatch.setattr(generation, "generate", _fake_generate)
    assert tool.main(["--environment", "staging", "--live"]) == 1
    assert "no citation marker" in capsys.readouterr().out


def test_live_path_reports_refusal_and_unavailability(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", FAKE_KEY)

    def _refused(*a, **kw):
        raise generation.GenerationRefused("gate says no")

    monkeypatch.setattr(generation, "generate", _refused)
    assert tool.main(["--environment", "staging", "--live"]) == 1
    assert "refused: gate says no" in capsys.readouterr().out

    def _down(*a, **kw):
        raise generation.GenerationUnavailable("HTTP 503")

    monkeypatch.setattr(generation, "generate", _down)
    assert tool.main(["--environment", "staging", "--live"]) == 1
    assert "provider unavailable" in capsys.readouterr().out


def test_synthetic_payload_carries_no_forbidden_content():
    """55.3 + AM-30 t3/t4: the fixed test strings are self-describing and inert."""
    blob = (tool._SYNTHETIC_QUESTION + " ".join(tool._SYNTHETIC_EVIDENCE)).lower()
    for forbidden in ("leapswitch", "cloudpe", "liability", "fees", "clause",
                      "acceptable_max", "deviation"):
        assert forbidden not in blob


def test_a_placeholder_key_fails_and_never_calls_the_provider(monkeypatch, capsys):
    """The check this tool was missing until 2026-09-01.

    It reported `PASS api_key — is set` for a literal `***` in the server
    environment, which was true and useless: the value was set and was not a
    credential, so the provider answered 400 `API_KEY_INVALID` four layers away
    and the assist lane degraded silently on every upload.

    Two assertions, and the second matters as much as the first: the tool must
    also NOT spend a provider call on a value it already knows is not a key.
    """
    called: list[object] = []

    def _boom(*args, **kwargs):  # pragma: no cover - asserted never to run
        called.append(1)
        raise AssertionError("the provider must not be called with a placeholder")

    monkeypatch.setattr(generation, "generate_raw", _boom)

    for masked in ("***", "k", "changeme", "<redacted>", "xxxxxxxx", "   "):
        monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", masked)
        assert tool.main(["--environment", "staging", "--live"]) == 1, masked
        out = capsys.readouterr().out
        assert "PLACEHOLDER" in out or "not set" in out, masked
        assert "not calling" in out, masked

    assert called == []
