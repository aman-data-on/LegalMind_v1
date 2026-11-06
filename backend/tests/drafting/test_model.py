"""Template + answers → the canonical model: conditions, numbering, xrefs, validation."""

import pytest

from legalmind.drafting.model import ModelError, model_hash, resolve, text_of


def _fields(exc):
    return {p["field"] for p in exc.value.problems}


def test_numbers_xrefs_and_conditions(placeholder, answers):
    m = resolve(*placeholder, answers)
    assert [c["clause_key"] for c in m["body"]] == [
        "DEFINITIONS", "CLAUSE_A", "CLAUSE_B", "CLAUSE_C", "CLAUSE_D", "CLAUSE_E"]
    assert m["numbers"]["CLAUSE_A_DEEP"] == "2.1.1.1.1"          # level five
    assert m["numbers"]["SCHEDULE_A_2"] == "2"                    # schedules restart
    clause_b = m["body"][2]["body"][0]["runs"]
    assert text_of(clause_b) == "Clause B text, subject to clause 2.1 and clause 2.1.1.1.1."
    without_d = resolve(*placeholder, {**answers, "include_clause_d": False,
                                       "clause_d_value": None, "include_schedule_b": False})
    assert "CLAUSE_D" not in [c["clause_key"] for c in without_d["body"]]
    assert [s["key"] for s in without_d["schedules"]] == ["SCHEDULE_A"]
    assert without_d["numbers"]["CLAUSE_E"] == "5"                # renumbered, not gapped


def test_every_problem_is_named(placeholder, answers):
    bad = {**answers, "unknown_field": 1, "count_value": 99, "option_value": "Option 9",
           "party_one_name": "Someone Else", "effective_date": "not a date"}
    bad.pop("party_two_name")
    with pytest.raises(ModelError) as exc:
        resolve(*placeholder, bad)
    assert {"unknown_field", "count_value", "option_value", "party_one_name",
            "effective_date", "party_two_name"} <= _fields(exc)


def test_conditional_field_required_only_when_asked(placeholder, answers):
    with pytest.raises(ModelError) as exc:
        resolve(*placeholder, {**answers, "clause_d_value": None})
    assert _fields(exc) == {"clause_d_value"}
    m = resolve(*placeholder, {**answers, "include_clause_d": False, "clause_d_value": "x"})
    assert "clause_d_value" not in m["values"]


def test_an_xref_to_a_clause_left_out_is_refused(placeholder, answers):
    template, clauses = placeholder
    clauses[("CLAUSE_E", 1)]["body"].append({"kind": "p", "text": "see {xref:CLAUSE_D}"})
    with pytest.raises(ModelError, match="CLAUSE_D, which this contract does not contain"):
        resolve(template, clauses, {**answers, "include_clause_d": False,
                                    "clause_d_value": None})


def test_an_undefined_term_and_unknown_slot_are_refused(placeholder, answers):
    template, clauses = placeholder
    clauses[("CLAUSE_E", 1)]["body"].append(
        {"kind": "p", "text": "{term:Never Defined} and {no_such_field}"})
    with pytest.raises(ModelError) as exc:
        resolve(template, clauses, answers)
    text = str(exc.value)
    assert "Never Defined" in text and "no_such_field" in text


def test_text_answers_cannot_smuggle_slots(placeholder, answers):
    with pytest.raises(ModelError, match="party_two_name"):
        resolve(*placeholder, {**answers, "party_two_name": "{xref:CLAUSE_A}"})


def test_model_hash_is_deterministic(placeholder, answers):
    assert model_hash(resolve(*placeholder, answers)) == model_hash(resolve(*placeholder, answers))
    assert model_hash(resolve(*placeholder, answers)) != model_hash(
        resolve(*placeholder, {**answers, "count_value": 4}))
