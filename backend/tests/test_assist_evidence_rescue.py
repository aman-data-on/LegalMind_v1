"""The evidence-rescue judge — a second look at a refusal, never at an answer.

Measured 2026-09-16 on the ratified 77-question set: the calibrated gate refuses 21 of
64 answerable questions, and **15 of those already have the gold chunk retrieved**.
Recall 0.625 could reach 0.859 by fixing the decision alone, with no retrieval change.

Three cheaper fixes were measured first and none works — a 35-point threshold sweep
(no configuration raises recall without raising wrongly-answered), an IDF-weighted
overlap feature (false refusals 0.185 vs unanswerable 0.196, indistinguishable), and a
different embedding model (gte-small 11/13 · 45/64 against MiniLM 12/13 · 41/64).

What is asserted hardest here is the SAFETY SHAPE, not the feature: the judge can only
turn a refusal into an attempt, and that attempt still faces every mechanical screen.
"""

from __future__ import annotations

import pytest

from legalmind.assist import generation, rescue


def _fake(text: str):
    return generation.GenerationResult(text=text, model="fake", prompt_version="test",
                                       payload_sha256="0" * 64, latency_ms=1)


CHUNKS = ["Either party may terminate on thirty (30) days written notice.",
          "The Receiving Party shall keep Confidential Information secret.",
          "Fees are payable within forty-five (45) days of invoice."]


def test_it_is_on_since_the_owner_approved_it(monkeypatch):
    """Approved 2026-09-16 after measurement: recall 0.625 -> 0.828 with
    wrongly-answered unchanged at 1/13."""
    monkeypatch.delenv("LEGALMIND_EVIDENCE_RESCUE", raising=False)
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake("YES 1"))
    assert rescue.rescue_indices("what is the notice period?", CHUNKS) == [0]


def test_the_flag_is_the_rollback(monkeypatch):
    """Off restores the pre-rescue behaviour with a restart and no deploy, and makes
    no provider call at all."""
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "off")

    def boom(*a, **k):
        raise AssertionError("no provider call may be made while disabled")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert rescue.rescue_indices("what is the notice period?", CHUNKS) == []


@pytest.mark.parametrize("reply,expected", [
    ("YES 1", [0]),
    ("YES 1 3", [0, 2]),
    ("yes 2", [1]),
    ("YES", [0, 1, 2]),          # a YES naming nothing means the whole set
    ("NO", []),
    ("no", []),
    ("", []),                    # unparseable is a refusal, not a guess
    ("MAYBE", []),
    ("I think excerpt 1 helps", []),   # not the required shape
])
def test_the_judges_reply_is_parsed_strictly(monkeypatch, reply, expected):
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake(reply))
    assert rescue.rescue_indices("q", CHUNKS) == expected


def test_an_index_the_judge_invented_is_dropped(monkeypatch):
    """An index outside the set is not evidence. Dropping it rather than trusting it
    keeps the rescued evidence a subset of what retrieval actually found."""
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake("YES 2 9 44"))
    assert rescue.rescue_indices("q", CHUNKS) == [1]


def test_a_provider_failure_leaves_the_refusal_standing(monkeypatch):
    """Every failure path returns [], and [] means today's behaviour. Nothing
    degrades when the judge cannot run."""
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")
    for exc in (generation.GenerationUnavailable("no key"),
                generation.GenerationRefused("LEGAL-02")):
        def raiser(*a, _e=exc, **k):
            raise _e
        monkeypatch.setattr(generation, "generate_raw", raiser)
        assert rescue.rescue_indices("q", CHUNKS) == []


def test_no_evidence_means_no_call(monkeypatch):
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")

    def boom(*a, **k):
        raise AssertionError("nothing to judge; no call should be made")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert rescue.rescue_indices("q", []) == []


def test_the_prompt_asks_for_a_decision_not_an_answer():
    """The judge must not answer the question — that is generation's job, and its
    output faces the grounding screens. A judge that answered would route model prose
    around them."""
    t = rescue.RESCUE_PROMPT_TEMPLATE.lower()
    assert "do not answer the question itself" in t
    assert "near-miss is no" in t


def test_rescue_imports_no_retrieval_and_writes_nothing():
    """It reads a decision out of the model and returns indices. If it could retrieve
    or persist, a later edit could give it authority it must never have."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(rescue.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported |= {a.name for a in node.names}
    assert not (imported & {"store", "positions", "statutes", "sqlalchemy"}), imported
