"""`AM-67` — Domain A as a controlled reading aid, and the boundaries around it.

The amendment permits published Company Standard clause text into a generation payload
so a non-lawyer gets an explanation rather than only a quote. That is a real
confidentiality change — the organization's own positions reach the provider — so the
tests that matter most are the ones about what may NOT go, and about what happens when
anything goes wrong.

Everything here runs with the feature OFF unless a test turns it on, because r7 forbids
enabling it in an environment whose position corpus has not been re-chunked.
"""

from __future__ import annotations

import pytest

from legalmind import config
from legalmind.assist import generation, positions


# --------------------------------------------------------------------------
# r7 — the prerequisite, enforced in code rather than in a runbook
# --------------------------------------------------------------------------
def test_a_span_carrying_an_internal_locator_is_refused_before_it_can_leave():
    """8 standards carried a counterparty note and 24 an environment path inside
    `source_document`. Sending those would breach `AM-30` t4/t5 on the first call."""
    for span in [
        "LIABILITY-MSA-001 — MSA.pdf at LEGALMIND_SOURCE_MATERIAL_DIR: the cap is 12 months.",
        "CONF-SURVIVAL-NDA-001 — docs/02-legal-domain/LEGAL_CONSTITUTION_L1.10.md: 3 years.",
        "X — NDA.pdf (counterparty deliberately not named in this repository): text.",
    ]:
        with pytest.raises(positions.PositionEgressRefused):
            positions.screen_for_egress([span])


def test_ordinary_legal_prose_containing_a_slash_is_NOT_refused():
    """Measured against the real corpus: three ratified standards contain a bare slash
    in perfectly ordinary legal English. Refusing those would block the feature on the
    organization's own wording, so the egress screen is narrower than the sanitizer —
    it looks for env-var tokens, filenames and the reviewer's note, not separators."""
    positions.screen_for_egress([
        "CLAIM-WINDOW-SLA-001 §11 SLA / Service Levels — Legal Constitution: 30 days.",
        "DATA-PURGE-MSA-001 7.6.6 — subject to the legal/compliance retention carve-out.",
        "SERVICE-DISCONTINUATION-MSA-001 31.14 A. Planned Full Service "
        "Discontinuation / Retirement — Legal Constitution: 30 days' notice.",
    ])


def test_a_sanitised_span_passes_the_screen():
    """The inverse failure would be a screen so strict nothing ships."""
    positions.screen_for_egress([
        "LIABILITY-MSA-001 9 Limitation of Liability (MSA) — Legal Constitution, Lawyer "
        "Review Version L1.10: liability is capped at 12 months of total fees paid.",
    ])


def test_the_screen_refuses_a_whole_batch_if_any_span_is_dirty():
    """One dirty span poisons the call; there is no partial send."""
    with pytest.raises(positions.PositionEgressRefused):
        positions.screen_for_egress(["clean position text about notice periods.",
                                     "dirty — MSA.pdf at LEGALMIND_SOURCE_MATERIAL_DIR"])


def test_the_real_corpus_would_pass_the_egress_screen():
    """After the 2026-09-15 sanitizer, every ratified standard is safe to send. This is
    the check an operator performs before enabling the feature — run here so it cannot
    silently stop being true."""
    import json
    spans = [positions._compose_content(json.loads(f.read_text()))
             for f in sorted(positions.RATIFIED_STANDARDS_DIR.glob("*.json"))]
    assert len(spans) >= 40
    positions.screen_for_egress(spans)


# --------------------------------------------------------------------------
# The feature is OFF until an operator turns it on
# --------------------------------------------------------------------------
def test_synthesis_is_off_by_default(monkeypatch):
    """r7: a DEPLOY does not satisfy the prerequisite — a re-chunk does, and that is a
    separate operation on live data."""
    monkeypatch.delenv("LEGALMIND_POSITION_SYNTHESIS", raising=False)
    assert config.position_synthesis_enabled() is False


def test_the_helper_returns_nothing_while_it_is_off(monkeypatch):
    from legalmind.assist import service
    monkeypatch.delenv("LEGALMIND_POSITION_SYNTHESIS", raising=False)

    def boom(*a, **k):
        raise AssertionError("AM-67 is off; no generation call may be made")

    monkeypatch.setattr(generation, "generate_position_reading_aid", boom)
    hit = positions.PositionHit(position_chunk_id=None, standard_code="X-MSA-001",
                                document_type="MSA", source_clause="9",
                                content="Liability is capped at 12 months of fees.",
                                score=0.9)
    assert service._position_reading_aid("what is our cap?", [hit], None) is None


# --------------------------------------------------------------------------
# r3, r4, r5, r8 — what the reading aid may be, and what happens when it fails
# --------------------------------------------------------------------------
def _hit(content: str):
    return positions.PositionHit(position_chunk_id=None, standard_code="LIABILITY-MSA-001",
                                 document_type="MSA", source_clause="9",
                                 content=content, score=0.9)


def _fake(text: str):
    return generation.GenerationResult(text=text, model="fake", prompt_version="test",
                                       payload_sha256="0" * 64, latency_ms=1)


QUOTE = ("LIABILITY-MSA-001 9 Limitation of Liability (MSA) — Legal Constitution: "
         "liability is capped at 12 months of total fees paid.")


@pytest.mark.parametrize("generated,why", [
    ("This clause complies with our approved standard [1].", "r4 — a verdict"),
    ("The cap deviates from the company standard [1].", "r4 — a verdict"),
    ("Yeh clause Company Standard ke according nahi hai [1].", "r4 — a Hinglish verdict"),
    ("The liability cap is five million dollars [1].", "r5 — ungrounded"),
    ("NOT FOUND", "the model's own refusal"),
    ("", "an empty answer"),
])
def test_an_unsafe_or_absent_reading_aid_falls_back_to_the_quote(monkeypatch, generated, why):
    """r8 — every failure path returns None, and None means the reader gets exactly what
    they got before `AM-67` existed: the fixed sentence and the verbatim quote."""
    from legalmind.assist import service
    monkeypatch.setenv("LEGALMIND_POSITION_SYNTHESIS", "on")
    monkeypatch.setattr(generation, "generate_position_reading_aid",
                        lambda *a, **k: _fake(generated))
    assert service._position_reading_aid("what is our cap?", [_hit(QUOTE)], None) is None, why


def test_a_grounded_descriptive_explanation_is_returned(monkeypatch):
    from legalmind.assist import service
    monkeypatch.setenv("LEGALMIND_POSITION_SYNTHESIS", "on")
    monkeypatch.setattr(
        generation, "generate_position_reading_aid",
        lambda *a, **k: _fake("Liability is capped at 12 months of total fees paid [1]."))
    out = service._position_reading_aid("what is our cap?", [_hit(QUOTE)], None)
    assert out and "12 months" in out.text
    # The result carries what the answer row records (model, latency) — 2026-09-17.
    assert out.model == "fake" and out.latency_ms == 1


def test_generation_failure_falls_back_to_the_quote(monkeypatch):
    from legalmind.assist import service
    monkeypatch.setenv("LEGALMIND_POSITION_SYNTHESIS", "on")

    def unavailable(*a, **k):
        raise generation.GenerationUnavailable("no credential")

    monkeypatch.setattr(generation, "generate_position_reading_aid", unavailable)
    assert service._position_reading_aid("what is our cap?", [_hit(QUOTE)], None) is None


def test_a_stale_corpus_refuses_the_call_rather_than_sanitising_it(monkeypatch):
    """r7 again, at the service layer: a locator here means the corpus was never
    re-chunked, and quietly cleaning it up would hide that."""
    from legalmind.assist import service
    monkeypatch.setenv("LEGALMIND_POSITION_SYNTHESIS", "on")

    def boom(*a, **k):
        raise AssertionError("a stale span reached the model")

    monkeypatch.setattr(generation, "generate_position_reading_aid", boom)
    dirty = _hit("LIABILITY-MSA-001 — MSA.pdf at LEGALMIND_SOURCE_MATERIAL_DIR: text.")
    assert service._position_reading_aid("what is our cap?", [dirty], None) is None


# --------------------------------------------------------------------------
# r6 — the forbidden-payload screen is narrowed, not removed
# --------------------------------------------------------------------------
@pytest.mark.parametrize("payload", [
    '{"deviation_outcome": "UNACCEPTABLE"}',
    '{"rule_outcome": "ACCEPTABLE"}',
    '{"acceptable_max": 12}',
])
def test_the_egress_screen_still_refuses_every_key_it_refused_before(payload):
    with pytest.raises(generation.GenerationRefused):
        generation._forbidden_payload_check(payload)


def test_the_position_prompt_forbids_a_compliance_statement():
    """r4 in the instructions as well as in the screen — belt and brace, since a prompt
    is a request and `AM-28` r2 requires the guarantee to live outside the model."""
    template = generation.POSITION_PROMPT_TEMPLATE.lower()
    assert "never say whether any document" in template
    assert "not recommend, approve, or advise whether to sign" in template
