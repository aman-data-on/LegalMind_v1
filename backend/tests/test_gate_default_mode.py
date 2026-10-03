"""The Tier-2 gate's DEFAULT mode is unchanged by the Phase 2 options (owner, 2026-10-03).

Phase 2 added a generated-only mode and a question filter for the generation baseline.
Unset, the gate must run as before: the retrieval half, then every question generated.
"""
from tools import verify_assist_quality as gate

QUESTIONS = [{"id": "Q-01"}, {"id": "Q-02"}, {"id": "N-01"}]


def test_unset_means_the_full_gate(monkeypatch):
    monkeypatch.delenv("LEGALMIND_GATE_GENERATED_ONLY", raising=False)
    monkeypatch.delenv("LEGALMIND_GATE_GENERATE_IDS", raising=False)
    generated_only, only = gate.run_options()
    assert generated_only is False and only == set()
    assert gate.selected(QUESTIONS, only) == QUESTIONS


def test_the_options_only_narrow_when_set(monkeypatch):
    monkeypatch.setenv("LEGALMIND_GATE_GENERATED_ONLY", "1")
    monkeypatch.setenv("LEGALMIND_GATE_GENERATE_IDS", "Q-02, ,N-01")
    generated_only, only = gate.run_options()
    assert generated_only is True
    assert only == {"Q-02", "N-01"}                   # spaces and empties ignored
    assert [q["id"] for q in gate.selected(QUESTIONS, only)] == ["Q-02", "N-01"]
    monkeypatch.setenv("LEGALMIND_GATE_GENERATED_ONLY", "0")
    assert gate.run_options()[0] is False
