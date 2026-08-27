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
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "k")

    def _boom(*a, **kw):  # pragma: no cover - the assertion is that it never runs
        raise AssertionError("config-only mode must not call generate()")

    monkeypatch.setattr(generation, "generate", _boom)
    assert tool.main(["--environment", "development"]) == 0
    assert "no network call made" in capsys.readouterr().out


def test_floating_model_alias_fails(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "k")
    monkeypatch.setenv("LEGALMIND_GENERATION_MODEL", "gemini-flash-latest")
    assert tool.main(["--environment", "development"]) == 1
    assert "floating alias" in capsys.readouterr().out


def test_production_reports_the_closed_gate_and_is_not_ready(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "k")
    assert tool.main(["--environment", "production"]) == 1
    out = capsys.readouterr().out
    assert "am31_gate" in out and "CLOSED" in out


def test_live_path_uses_the_one_seam_and_passes_on_a_cited_reply(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "k")
    seen: dict = {}

    def _fake_generate(question, evidence, *, environment, request_id=None):
        seen.update(question=question, evidence=evidence, environment=environment)
        return generation.GenerationResult(
            text="The vehicle is blue. [1]", model="gemini-2.5-flash",
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
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "k")

    def _fake_generate(*a, **kw):
        return generation.GenerationResult(
            text="The vehicle is blue.", model="gemini-2.5-flash",
            prompt_version=generation.PROMPT_VERSION,
            payload_sha256="ab" * 32, latency_ms=42)

    monkeypatch.setattr(generation, "generate", _fake_generate)
    assert tool.main(["--environment", "staging", "--live"]) == 1
    assert "no citation marker" in capsys.readouterr().out


def test_live_path_reports_refusal_and_unavailability(monkeypatch, capsys):
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "k")

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
