"""AB-14 follow-up: the two mechanically checkable Constitution prohibitions.

Only LIABILITY-*-001 (uncapped/unlimited, s.9) and DATA-RETRIEVAL-TOS-001
(export window under 30 days, s.13) are wired — see constitution_boundaries.py
for why the other five Unacceptable Position paragraphs are not. This module
never asserts a legal conclusion itself (rule 21); it pins the mechanical
match/no-match behaviour against the Constitution's own quoted text.
"""
from legalmind.evaluation.constitution_boundaries import constitution_prohibition_for


def test_unlimited_liability_matches_section_9():
    result = constitution_prohibition_for("LIABILITY-MSA-001", {"cap_status": "UNLIMITED"})
    assert result == {
        "section": "9",
        "quote": "An uncapped/unlimited liability term […]",
    }
    assert constitution_prohibition_for("LIABILITY-TOS-001", {"cap_status": "UNLIMITED"}) == result


def test_a_finite_liability_cap_is_not_a_prohibition_even_when_it_deviates():
    assert constitution_prohibition_for(
        "LIABILITY-MSA-001", {"cap_value": 24, "cap_unit": "MONTHS", "cap_basis": "FEES_PAID"},
    ) is None


def test_a_retrieval_window_under_30_days_matches_section_13():
    assert constitution_prohibition_for(
        "DATA-RETRIEVAL-TOS-001", {"cap_value": 15, "cap_unit": "DAYS"},
    ) == {
        "section": "13",
        "quote": "A post-termination data-export window shorter than 30 days […]",
    }


def test_a_retrieval_window_of_30_days_or_more_is_not_a_prohibition():
    assert constitution_prohibition_for("DATA-RETRIEVAL-TOS-001", {"cap_value": 30, "cap_unit": "DAYS"}) is None
    assert constitution_prohibition_for("DATA-RETRIEVAL-TOS-001", {"cap_value": 45, "cap_unit": "DAYS"}) is None


def test_a_retrieval_value_in_months_is_not_compared_as_days():
    # 3 MONTHS is not "less than 30 DAYS" — units are never silently converted.
    assert constitution_prohibition_for("DATA-RETRIEVAL-TOS-001", {"cap_value": 3, "cap_unit": "MONTHS"}) is None


def test_every_other_reconciled_standard_returns_none():
    # The four qualitative Unacceptable Position paragraphs are not wired.
    for code in ["CONF-SURVIVAL-NDA-001", "LATE-FEE-TOS-001", "CLAIM-WINDOW-SLA-001",
                 "DATA-PURGE-MSA-001", "INDEMNIFICATION-MSA-001"]:
        assert constitution_prohibition_for(code, {"cap_value": 1, "cap_unit": "DAYS"}) is None


def test_a_shape_the_function_does_not_recognise_returns_none_rather_than_guessing():
    assert constitution_prohibition_for("LIABILITY-MSA-001", "UNLIMITED") is None
    assert constitution_prohibition_for("LIABILITY-MSA-001", None) is None
    assert constitution_prohibition_for(None, {"cap_status": "UNLIMITED"}) is None
