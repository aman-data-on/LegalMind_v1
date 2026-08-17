"""Mapping engine tests — locked Steps 28 and 35."""

from __future__ import annotations

from uuid import uuid4

import pytest

from legalmind.domain.enums import MappingState
from legalmind.mapping.engine import Clause, map_document, map_requirement
from legalmind.mapping.rules import DEFAULT_WEIGHTS, MappingRules
from legalmind.mapping.scoring import score_clause

LIABILITY_RULES = MappingRules(
    exact_phrases=("limitation of liability",),
    aliases=("aggregate liability", "total liability"),
    keyword_groups=(("liability", "shall not exceed"),),
    section_heading_terms=("liability",),
    negative_patterns=("shall not be limited",),
)

GOVERNING_LAW_RULES = MappingRules(
    exact_phrases=("governing law",),
    aliases=("governed by the laws",),
    keyword_groups=(("laws of", "jurisdiction"),),
    section_heading_terms=("governing law", "jurisdiction"),
)


def clause(text, *, number=None, title=None):
    return Clause(evidence_id=uuid4(), content=text,
                  section_number=number, section_title=title)


# =========================================================== determinism
def test_scoring_is_deterministic(db=None):
    """35.1 / ENG-11 — same inputs, same rule version, same score."""
    c = "The aggregate liability shall not exceed six months of fees."
    runs = [score_clause(LIABILITY_RULES, content=c, section_title="Liability")
            for _ in range(20)]
    assert len({r.score for r in runs}) == 1
    assert len({tuple(r.explanation) for r in runs}) == 1


def test_candidate_order_does_not_affect_outcome(db=None):
    """ENG-11 — equal scores must not depend on input ordering."""
    a = clause("Aggregate liability shall not exceed six months of fees.",
               number="8.2", title="Limitation of Liability")
    b = clause("Total liability shall not exceed twelve months of fees.",
               number="14.1", title="Limitation of Liability")
    rv = uuid4()
    forward = map_requirement(rv, LIABILITY_RULES, [a, b])
    reverse = map_requirement(rv, LIABILITY_RULES, [b, a])
    assert forward.state is reverse.state
    assert {c.clause.evidence_id for c in forward.candidates} == \
           {c.clause.evidence_id for c in reverse.candidates}


def test_score_is_explainable_not_opaque(db=None):
    """35.19 — no opaque confidence score may underpin a legal conclusion."""
    result = score_clause(
        LIABILITY_RULES,
        content="The aggregate liability shall not exceed six months of fees.",
        section_title="Limitation of Liability")
    assert result.score == sum(s.delta for s in result.signals)   # fully derived
    assert result.explanation                                     # and stated
    for line in result.explanation:
        assert any(k in line for k in
                   ("exact_phrase", "alias", "keyword_group", "section_heading"))


# ======================================================= Step 28 states
def test_confirmed_when_one_clear_winner(db=None):
    r = map_requirement(uuid4(), LIABILITY_RULES, [
        clause("The aggregate liability shall not exceed six months of fees.",
               number="8.2", title="Limitation of Liability"),
        clause("Payment is due within thirty days.", number="3.1",
               title="Payment Terms"),
    ])
    assert r.state is MappingState.CONFIRMED
    assert len(r.candidates) == 1
    assert r.evidence_ids


def test_ambiguous_when_two_plausible_candidates(db=None):
    """Locked Step 28: "More than one plausible mapping exists and LegalMind
    must not silently choose one." """
    r = map_requirement(uuid4(), LIABILITY_RULES, [
        clause("Aggregate liability shall not exceed six months of fees.",
               number="8.2", title="Limitation of Liability"),
        clause("Total liability shall not exceed twelve months of fees.",
               number="14.1", title="Limitation of Liability"),
    ])
    assert r.state is MappingState.AMBIGUOUS
    assert len(r.candidates) == 2
    assert len(r.evidence_ids) == 2          # both retained, neither chosen
    assert any("must not choose" in e for e in r.explanation)


def test_unresolved_when_signals_are_too_weak(db=None):
    """Locked Step 28: "The system cannot establish the mapping reliably." """
    r = map_requirement(uuid4(), LIABILITY_RULES, [
        clause("General liability matters are addressed elsewhere.",
               number="9", title="Liability"),
    ])
    assert r.state is MappingState.UNRESOLVED
    assert r.candidates == ()                # nothing confirmed
    assert r.evidence_ids                    # but the near-miss is retained


def test_none_when_nothing_is_even_plausible(db=None):
    """45D — established absence, distinct from 'could not decide'.

    The distinction matters downstream: NONE + REQUIRED yields MISSING, whereas
    UNRESOLVED yields UNABLE_TO_EVALUATE (Step 28 r6). Collapsing them would
    turn uncertainty into a legal conclusion.
    """
    r = map_requirement(uuid4(), LIABILITY_RULES, [
        clause("Payment is due within thirty days.", number="3.1",
               title="Payment Terms"),
    ])
    assert r.state is MappingState.NONE
    assert r.evidence_ids == ()


def test_unresolved_and_none_are_distinct_states(db=None):
    weak = map_requirement(uuid4(), LIABILITY_RULES,
                           [clause("Liability generally.", title="Liability")])
    absent = map_requirement(uuid4(), LIABILITY_RULES,
                             [clause("Payment terms are net 30.", title="Payment")])
    assert weak.state is not absent.state


# ================================================= negative patterns (35.5)
def test_negative_pattern_prevents_false_positive(db=None):
    """35.5 / 45C.12 — requirement-adjacent wording must not falsely map.

    "Liability shall not be limited" contains 'liability' but states the
    opposite position; it must not be confirmed as a liability *cap*.
    """
    r = map_requirement(uuid4(), LIABILITY_RULES, [
        clause("Liability shall not be limited in respect of fraud.",
               number="8.5", title="Liability"),
    ])
    assert r.state is not MappingState.CONFIRMED


def test_word_boundaries_prevent_substring_matches(db=None):
    """A substring match would map 'client' to a 'lien' Requirement."""
    rules = MappingRules(exact_phrases=("lien",), confirm_threshold=5)
    r = map_requirement(uuid4(), rules,
                        [clause("The client shall pay all fees.")])
    assert r.state is MappingState.NONE


# ============================================ multiplicity (35.12 / 35.13)
def test_one_requirement_may_map_to_multiple_clauses(db=None):
    """35.12 / Step 28 r2 — several supporting clauses are all retained.

    Distinct scores, so there is no tie and therefore no ambiguity: the engine
    is not being asked to choose.
    """
    rules = MappingRules(
        exact_phrases=("limitation of liability",),
        keyword_groups=(("liability", "shall not exceed"),),
        section_heading_terms=("liability",),
        confirm_threshold=3,
        tie_margin=0,
    )
    r = map_requirement(uuid4(), rules, [
        clause("Limitation of Liability. Liability shall not exceed six months.",
               number="8.1", title="Limitation of Liability"),
        clause("Liability shall not exceed the fees paid.", number="8.3"),
    ])
    assert r.state is MappingState.CONFIRMED
    assert len(r.candidates) == 2


def test_one_clause_may_map_to_multiple_requirements(db=None):
    """35.13 / Step 28 r1 — a clause serving two Requirements is claimed by both."""
    combined = clause(
        "Aggregate liability shall not exceed six months of fees, and this "
        "Agreement is governed by the laws of India with exclusive jurisdiction "
        "in Mumbai.",
        number="8.2", title="Limitation of Liability")
    liability_rv, law_rv = uuid4(), uuid4()
    results = map_document(
        {liability_rv: LIABILITY_RULES, law_rv: GOVERNING_LAW_RULES}, [combined])
    assert results[liability_rv].state is MappingState.CONFIRMED
    assert results[law_rv].state is MappingState.CONFIRMED
    assert results[liability_rv].evidence_ids == results[law_rv].evidence_ids


def test_identical_restatements_are_not_ambiguous(db=None):
    """45C.17 reasoning at the mapping layer: the same position stated twice is
    one position, not a choice between candidates."""
    text = "Aggregate liability shall not exceed six months of fees."
    r = map_requirement(uuid4(), LIABILITY_RULES, [
        clause(text, number="8.2", title="Limitation of Liability"),
        clause(text, number="20.1", title="Limitation of Liability"),
    ])
    assert r.state is MappingState.CONFIRMED
    assert len(r.evidence_ids) == 2          # both evidence refs retained


# ====================================================== no forced mapping
def test_engine_never_forces_a_mapping(db=None):
    """35.17 — a clause may remain unmapped when evidence is insufficient."""
    r = map_requirement(uuid4(), LIABILITY_RULES, [])
    assert r.state is MappingState.NONE
    assert r.candidates == ()


def test_mapping_produces_no_classification_or_outcome(db=None):
    """Step 28 r8 / ENG-03 — Mapping is separate from Evaluation.

    A structural check: the result object has no field through which a
    classification, rule outcome or Finding could leak out of this layer.
    """
    r = map_requirement(uuid4(), LIABILITY_RULES,
                        [clause("Aggregate liability shall not exceed six months.")])
    fields = set(vars(r))
    assert not (fields & {"classification", "rule_outcome", "finding",
                          "finding_classification", "risk"})


# ================================================= thresholds are config
def test_thresholds_are_configuration_not_code(db=None):
    """35.10 / B-11 — thresholds must be calibrated against a representative
    contract set, so changing one must not require a code change."""
    text = "Liability shall not exceed six months of fees."
    strict = MappingRules(keyword_groups=(("liability", "shall not exceed"),),
                          confirm_threshold=99)
    lenient = MappingRules(keyword_groups=(("liability", "shall not exceed"),),
                           confirm_threshold=1)
    assert map_requirement(uuid4(), strict, [clause(text)]).state \
        is MappingState.UNRESOLVED
    assert map_requirement(uuid4(), lenient, [clause(text)]).state \
        is MappingState.CONFIRMED


def test_rules_round_trip_through_jsonb_config(db=None):
    """42.10 — rules are versioned configuration, so they must survive the
    JSONB round trip exactly."""
    restored = MappingRules.from_config(LIABILITY_RULES.to_config())
    assert restored == LIABILITY_RULES


def test_default_weights_are_the_illustrative_locked_values(db=None):
    """35.8's illustrative weights are the calibration starting point."""
    assert DEFAULT_WEIGHTS == {"exact_phrase": 5, "alias": 3, "keyword_group": 3,
                               "section_heading": 2, "negative_pattern": -5}


def test_no_step35_band_vocabulary_is_produced(db=None):
    """B-11 — the band -> state mapping was deliberately deferred by the owner.

    This engine derives state from Step 28's locked definitions and must never
    emit Step 35's provisional band names.
    """
    produced = {s.value for s in MappingState}
    assert produced == {"CONFIRMED", "AMBIGUOUS", "UNRESOLVED", "NONE"}
    for banned in ("CANDIDATE", "CANDIDATE-REVIEW", "NOT MAPPED",
                   "NO_CONFIDENT_MAPPING"):
        assert banned not in produced
