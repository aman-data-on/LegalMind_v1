"""Liability fact extraction — locked 44.10, 44.11, 44.17, 44.24, 44.30, 45B.4.

**Every value in this file is STRUCTURAL and carries no legal meaning.** The phrases,
units and carve-out terms are supplied by the test to exercise the algorithm; they
are not the organization's Company Standard and no expected output here asserts a
legal conclusion (rule 21, Step 45E provenance). The one real assertion about legal
behaviour is negative: the extractor invents nothing.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from legalmind.domain.enums import EvaluationKind, ExtractionStatus
from legalmind.extraction.liability import (
    FINITE,
    UNKNOWN,
    UNLIMITED,
    ExceptionPattern,
    LiabilityExtractionConfig,
    extract_liability_facts,
)
from legalmind.mapping.engine import Clause

# ---------------------------------------------------------------- structural
# Configured terminology. Deliberately generic rather than realistic, so nothing
# here can be mistaken for a legal position.
CONFIG = LiabilityExtractionConfig(
    cap_phrases=("shall not exceed",),
    unlimited_phrases=("shall not be limited",),
    units=("months", "days"),
    bases={"BASIS_FEES": ("fees paid",), "BASIS_CONTRACT_VALUE": ("contract value",)},
    exceptions=(
        ExceptionPattern(scope="SCOPE_X", terms=("term x",), scope_label="Term X"),
        ExceptionPattern(scope="SCOPE_Y", terms=("term y",), scope_label="Term Y"),
    ),
)


def clause(text: str, *, number: str | None = None) -> Clause:
    return Clause(evidence_id=uuid4(), content=text, section_number=number)


# =====================================================================
# 44.10 — text becomes a structured fact
# =====================================================================
def test_a_general_cap_becomes_one_primary_cap():
    facts = extract_liability_facts(
        [clause("Liability shall not exceed 12 months of fees paid.", number="11.2")],
        CONFIG)

    assert facts.extraction_status is ExtractionStatus.COMPLETE
    assert len(facts.caps) == 1
    cap = facts.caps[0]
    assert cap.cap_kind is EvaluationKind.PRIMARY
    assert cap.cap_status == FINITE
    assert cap.cap_value == 12.0
    assert cap.cap_unit == "months"
    assert cap.cap_basis == "BASIS_FEES"
    # Rule 11 / 45B.3 — the fact traces back to the evidence it came from.
    assert len(cap.evidence_refs) == 1


def test_magnitudes_with_separators_and_decimals_are_read():
    facts = extract_liability_facts(
        [clause("Liability shall not exceed 1,500 days.")], CONFIG)
    assert facts.caps[0].cap_value == 1500.0
    facts = extract_liability_facts(
        [clause("Liability shall not exceed 1.5 months.")], CONFIG)
    assert facts.caps[0].cap_value == 1.5


# =====================================================================
# 44.17 — the general rule and its carve-outs are NEVER flattened
# =====================================================================
def test_a_general_cap_and_two_carveouts_produce_three_separate_caps():
    """Locked 44.17: "LegalMind should not flatten this into liability_cap = 6
    months only. It should preserve: General Rule + Exceptions / Carve-outs."

    This is the "hidden carve-out" case. If the carve-outs were folded into the
    general cap, a conforming aggregate figure would mask an exception the
    organization may find unacceptable — and 45C's per-scope evaluation, which
    exists to surface exactly that, would have nothing to work with.
    """
    facts = extract_liability_facts([
        clause("Aggregate liability shall not exceed 6 months of fees paid.",
               number="11.1"),
        clause("Liability for term x shall not exceed 24 months of fees paid.",
               number="11.2"),
        clause("Liability for term y shall not be limited.", number="11.3"),
    ], CONFIG)

    assert len(facts.caps) == 3
    by_scope = {c.scope: c for c in facts.caps}

    general = by_scope["GENERAL"]
    assert general.cap_kind is EvaluationKind.PRIMARY
    assert general.cap_value == 6.0

    first = by_scope["SCOPE_X"]
    assert first.cap_kind is EvaluationKind.EXCEPTION
    assert first.scope_label == "Term X"
    assert first.cap_value == 24.0

    second = by_scope["SCOPE_Y"]
    assert second.cap_kind is EvaluationKind.EXCEPTION
    assert second.cap_status == UNLIMITED
    assert second.cap_value is None


def test_a_clause_naming_only_a_carveout_yields_no_general_cap():
    """Recording a general cap here would invent a position the clause does not
    state."""
    facts = extract_liability_facts(
        [clause("Liability for term x shall not exceed 24 months.")], CONFIG)
    assert len(facts.caps) == 1
    assert facts.caps[0].cap_kind is EvaluationKind.EXCEPTION
    assert facts.caps[0].scope == "SCOPE_X"


def test_one_clause_may_state_several_carveouts():
    facts = extract_liability_facts(
        [clause("Liability for term x and term y shall not exceed 36 months.")],
        CONFIG)
    assert {c.scope for c in facts.caps} == {"SCOPE_X", "SCOPE_Y"}
    assert all(c.cap_kind is EvaluationKind.EXCEPTION for c in facts.caps)


# =====================================================================
# 44.24 / 45B.7 — uncertainty is recorded, never resolved
# =====================================================================
def test_cap_language_without_a_recognisable_magnitude_is_unknown():
    """Locked 44.24 — deterministic uncertainty. A number must never be guessed,
    and "six" is not interpreted because word-number vocabulary would be
    terminology the engine invented (35.4, 44.29)."""
    facts = extract_liability_facts(
        [clause("Liability shall not exceed six months.", number="11.2")], CONFIG)

    assert facts.caps[0].cap_status == UNKNOWN
    assert facts.caps[0].cap_value is None
    assert any("no magnitude was recognised" in d
               for d in facts.extraction_diagnostics)


def test_unlimited_language_never_acquires_a_value():
    facts = extract_liability_facts(
        [clause("Liability shall not be limited in any way.")], CONFIG)
    assert facts.caps[0].cap_status == UNLIMITED
    assert facts.caps[0].cap_value is None
    assert facts.caps[0].cap_unit is None


def test_an_unconfigured_unit_is_not_read_as_a_magnitude():
    """Only configured units count. Reading "12 weeks" here would be inventing a
    unit vocabulary."""
    facts = extract_liability_facts(
        [clause("Liability shall not exceed 12 weeks of fees paid.")], CONFIG)
    assert facts.caps[0].cap_status == UNKNOWN


def test_an_unrecognised_basis_is_none_not_assumed():
    """Locked 45B.4: "We should not assume equivalence between different bases."

    A None basis is treated as non-comparable by RuleConfiguration, so this fails
    closed downstream rather than being equated with the Company Standard's basis.
    """
    facts = extract_liability_facts(
        [clause("Liability shall not exceed 12 months of revenue.")], CONFIG)
    assert facts.caps[0].cap_basis is None


def test_a_clause_with_no_cap_language_yields_nothing():
    """45C.15 — absence never manufactures a position, and a mapped clause need not
    contain a cap."""
    facts = extract_liability_facts(
        [clause("This Agreement is governed by the laws of Ruritania.")], CONFIG)
    assert facts.caps == ()
    assert facts.extraction_status is ExtractionStatus.COMPLETE
    assert facts.extraction_diagnostics == ()


# =====================================================================
# ENG-09 — no configuration means no extraction
# =====================================================================
def test_absent_configuration_fails_rather_than_guessing():
    empty = LiabilityExtractionConfig.from_config({})
    assert not empty.is_usable

    facts = extract_liability_facts(
        [clause("Liability shall not exceed 12 months of fees paid.")], empty)
    assert facts.extraction_status is ExtractionStatus.FAILED
    assert facts.caps == ()
    assert facts.extraction_diagnostics


def test_failed_extraction_becomes_unable_to_evaluate():
    """45B.7 — the fail-closed path needs no new code: the evaluator already
    refuses to use unusable facts."""
    from legalmind.domain.enums import EvaluatorType, FindingClassification
    from legalmind.evaluation.contracts import (
        CompanyStandard,
        EvaluatorInput,
        RequirementContext,
    )
    from legalmind.evaluation.registry import evaluate, version_for

    facts = extract_liability_facts(
        [clause("Liability shall not exceed 12 months.")],
        LiabilityExtractionConfig.from_config(None))
    assert facts.extraction_status is ExtractionStatus.FAILED

    output = evaluate(EvaluatorInput(
        requirement=RequirementContext(
            requirement_version_id=uuid4(), code="STRUCTURAL-1",
            evaluator_type=EvaluatorType.NUMERIC_COMPARISON),
        company_standard=CompanyStandard(version_id=uuid4(), configuration={}),
        evaluator_version=version_for(EvaluatorType.NUMERIC_COMPARISON),
        facts=facts))
    assert output.finding_classification is FindingClassification.UNABLE_TO_EVALUATE


def test_unreadable_clauses_are_partial_not_silently_dropped():
    facts = extract_liability_facts([
        clause("Liability shall not exceed 12 months of fees paid.", number="11.1"),
        clause("   ", number="11.2"),
    ], CONFIG)
    assert facts.extraction_status is ExtractionStatus.PARTIAL
    assert len(facts.caps) == 1
    assert any("no readable text" in d for d in facts.extraction_diagnostics)


def test_all_clauses_unreadable_is_failed_not_absence():
    """Established absence and "could not read" must never be confused: only the
    first may be treated as a legitimate position (45C.15)."""
    facts = extract_liability_facts([clause(""), clause("  ")], CONFIG)
    assert facts.extraction_status is ExtractionStatus.FAILED
    assert facts.caps == ()


def test_no_clauses_at_all_is_absence_not_failure():
    facts = extract_liability_facts([], CONFIG)
    assert facts.extraction_status is ExtractionStatus.COMPLETE
    assert facts.caps == ()


# =====================================================================
# ENG-11 — determinism
# =====================================================================
def test_extraction_is_deterministic():
    clauses = [
        clause("Aggregate liability shall not exceed 6 months of fees paid.",
               number="11.1"),
        clause("Liability for term y shall not be limited.", number="11.2"),
        clause("Liability shall not exceed six months.", number="11.3"),
    ]
    first = extract_liability_facts(clauses, CONFIG)
    second = extract_liability_facts(clauses, CONFIG)
    assert first == second
    assert first.extraction_diagnostics == second.extraction_diagnostics


def test_basis_resolution_is_order_independent():
    """A clause matching two configured bases must resolve identically every run."""
    both = clause("Liability shall not exceed 12 months of fees paid, "
                  "being the contract value.")
    assert (extract_liability_facts([both], CONFIG).caps[0].cap_basis
            == extract_liability_facts([both], CONFIG).caps[0].cap_basis)


# =====================================================================
# Rule 21 / 44.29 — the module ships no legal content
# =====================================================================
def test_the_module_ships_no_terminology_of_its_own():
    """44.29 puts patterns and terminology in configuration. A built-in cap phrase
    or unit list here would become the organization's position by default."""
    empty = LiabilityExtractionConfig()
    assert empty.cap_phrases == ()
    assert empty.unlimited_phrases == ()
    assert empty.units == ()
    assert empty.bases == {}
    assert empty.exceptions == ()
    assert not empty.is_usable


def test_configuration_is_read_from_the_company_standard_extraction_block():
    config = LiabilityExtractionConfig.from_config({
        "extraction": {
            "cap_phrases": ["shall not exceed"],
            "units": ["months"],
            "bases": {"BASIS_FEES": ["fees paid"]},
            "exceptions": [{"scope": "SCOPE_X", "terms": ["term x"],
                            "scope_label": "Term X"}],
        }
    })
    assert config.is_usable
    assert config.units == ("months",)
    assert config.exceptions[0].scope == "SCOPE_X"
    assert config.bases["BASIS_FEES"] == ("fees paid",)
