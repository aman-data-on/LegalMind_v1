"""Semantic-recognition memoization — bug fix, 2026-09-29 (rule 9 restored).

Live incident: the byte-identical NDA, analyzed twice under the SAME
configuration snapshot, got two different Gemini verdicts on the same clause
and so a different Finding count — `AM-54`'s RECOGNITION step calls Gemini at
`temperature: 0.0`, which reduces but does not guarantee bit-reproducible
output on a hosted model. `_egress_for`'s cache is what stops that: a repeat
call with the exact same prompt, under the exact same configuration snapshot,
reuses the first call's verdict instead of asking again. No local embedding
model is needed to test this — the cache wraps the egress call itself,
independent of what built the prompt.
"""
from __future__ import annotations

from legalmind.analysis.service import _egress_for
from legalmind.assist.llm import generation
from tests.conftest import make_review_for, make_user


def _fake_returning(replies, calls):
    def fake(prompt, *, prompt_version, environment, request_id=None,
            evidence_count=None, max_output_tokens=1024, timeout_s=60.0):
        calls.append(prompt)
        # Mirrors generate_raw's own tail: it always reports the model IT
        # actually asked (`generation._model()`), never a hardcoded string —
        # the cache key relies on that being true (models.py's docstring).
        return generation.GenerationResult(
            text=replies.pop(0), model=generation._model(), prompt_version=prompt_version,
            payload_sha256="0" * 64, latency_ms=1)
    return fake


def test_a_repeat_prompt_under_the_same_snapshot_is_never_reasked(db, monkeypatch):
    owner = make_user(db)
    review = make_review_for(db, owner)
    db.commit()

    calls: list[str] = []
    monkeypatch.setattr(generation, "generate_raw",
                        _fake_returning(["first verdict", "second, DIFFERENT verdict"], calls))
    egress = _egress_for(db, review, actor_id=owner.id, request_id=None)

    first = egress("Does this clause address the requirement?", "mapping-v1")
    second = egress("Does this clause address the requirement?", "mapping-v1")

    assert len(calls) == 1                       # the model was asked once
    assert first.text == "first verdict"
    assert second.text == "first verdict"        # the cache, not a second roll of the die


def test_a_different_prompt_is_still_asked(db, monkeypatch):
    owner = make_user(db)
    review = make_review_for(db, owner)
    db.commit()

    calls: list[str] = []
    monkeypatch.setattr(generation, "generate_raw",
                        _fake_returning(["verdict for A", "verdict for B"], calls))
    egress = _egress_for(db, review, actor_id=owner.id, request_id=None)

    a = egress("clause A", "mapping-v1")
    b = egress("clause B", "mapping-v1")

    assert len(calls) == 2
    assert (a.text, b.text) == ("verdict for A", "verdict for B")


def test_a_different_snapshot_is_still_asked(db, monkeypatch):
    """The same prompt under a DIFFERENT configuration snapshot must not reuse
    another snapshot's verdict — the cache is scoped to what rule 9 actually
    promises (same snapshot -> same result), not to the prompt alone."""
    import uuid

    from legalmind.db import models as M

    owner = make_user(db)
    review_a = make_review_for(db, owner)
    review_b = make_review_for(db, owner)
    other_snapshot = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex,
                                             created_by=owner.id)
    db.add(other_snapshot)
    db.flush()
    review_b.configuration_snapshot_id = other_snapshot.id
    db.commit()

    calls: list[str] = []
    monkeypatch.setattr(generation, "generate_raw",
                        _fake_returning(["verdict under A", "verdict under B"], calls))

    first = _egress_for(db, review_a, actor_id=owner.id, request_id=None)(
        "same prompt", "mapping-v1")
    second = _egress_for(db, review_b, actor_id=owner.id, request_id=None)(
        "same prompt", "mapping-v1")

    assert len(calls) == 2
    assert (first.text, second.text) == ("verdict under A", "verdict under B")


def test_a_pinned_model_change_is_still_asked(db, monkeypatch):
    """`MAPPING_PROMPT_VERSION` never changes with `LEGALMIND_GENERATION_MODEL`
    (models.py's `SemanticRecognitionCache` docstring) — an operator pinning a
    new model, with no reason to also bump the prompt version, must get a
    fresh verdict from the new model rather than this cache replaying the old
    model's answer under the same snapshot and the same prompt text."""
    owner = make_user(db)
    review = make_review_for(db, owner)
    db.commit()

    calls: list[str] = []
    monkeypatch.setattr(generation, "generate_raw",
                        _fake_returning(["verdict from model A", "verdict from model B"], calls))

    monkeypatch.setenv("LEGALMIND_GENERATION_MODEL", "model-a")
    first = _egress_for(db, review, actor_id=owner.id, request_id=None)(
        "same prompt", "mapping-v1")

    monkeypatch.setenv("LEGALMIND_GENERATION_MODEL", "model-b")
    second = _egress_for(db, review, actor_id=owner.id, request_id=None)(
        "same prompt", "mapping-v1")

    assert len(calls) == 2
    assert (first.text, second.text) == ("verdict from model A", "verdict from model B")
