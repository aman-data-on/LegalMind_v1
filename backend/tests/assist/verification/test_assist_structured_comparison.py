"""AMENDMENT A to AM-90, Option 2 (2026-10-08): a comparison with a company position is a
structured diff — Agreement / Standard / Delta — whose fields are checked exactly, whose
delta is computed by code, and whose prose is optional commentary. Synthetic records only
(rule 21). No NLI model is needed: the fields are matched, not entailed."""
from __future__ import annotations

import json

import pytest

from legalmind.assist.agent import agent
from legalmind.assist.verification import agent_verify as av

CLAUSE = av.Evidence(
    "D63", "14.3 TERMINATION FOR CONVENIENCE — Subject to Clause 5.1 above, either party "
    "may terminate the Agreement for convenience by giving at least ninety (90) days "
    "advance written notice.", "14.3", av.SELECTED, False, "documents")
POSITION = av.Evidence(
    "P7", "For MSA agreements either party may terminate for convenience on thirty (30) "
    "days' written notice, with a thirty-day cure period for cause.", "§13",
    "MSA agreements only", False, "positions")
SHOWN = {"D63": CLAUSE, "P7": POSITION}


def block(**over):
    cmp = {"agreement": "at least 90 days advance written notice",
           "agreement_cite": "D63",
           "standard": "30 days' written notice", "standard_cite": "P7"}
    cmp.update({k: v for k, v in over.items() if k in cmp})
    return {"kind": "sourced", "text": over.get("text", ""), "cites": ["D63", "P7"],
            "compare": cmp}


def codes(b, shown=SHOWN, instruments=frozenset()):
    return [v.check for v in av.verify([b], shown, document_selected=True,
                                       assessment="n/a", instruments=instruments)]


# ----------------------------------------------------------------- exact spans
@pytest.mark.parametrize("span, ok", [
    ("at least 90 days advance written notice", True),     # "ninety (90)" is 90
    ("at least ninety (90) days advance written notice", True),
    ("AT LEAST 90 DAYS' ADVANCE WRITTEN NOTICE", True),     # case and apostrophe
    ("terminate the Agreement … 90 days advance written notice", True),   # ellipsis
    ("either party may leave on 90 days notice", False),    # a paraphrase
    ("at least 60 days advance written notice", False),     # another figure
    ("", False), ("ab", False),
])
def test_a_span_must_be_the_records_own_words(span, ok):
    assert av.in_record(span, CLAUSE.text) is ok


# ------------------------------------------------------------------- the delta
def test_the_delta_is_computed_from_the_two_spans():
    assert av.compare_delta("90 days advance written notice", "30 days' written notice") \
        == "90 days against 30 days: the agreement is 60 days longer"
    assert av.compare_delta("a 3 month period", "12 months") \
        == "3 months against 12 months: the agreement is 9 months shorter"
    assert av.compare_delta("interest at 24% per annum", "2 percent") \
        == "24 % against 2 %: the agreement is 22 % higher"
    assert av.compare_delta("a 12 month cap", "a 12-month cap") == "same (12 months)"


def test_a_percent_that_is_lower_is_said_lower():
    """Review finding: the direction for % was hard-coded "higher"."""
    assert av.compare_delta("interest at 1%", "interest at 2%") \
        == "1 % against 2 %: the agreement is 1 % lower"


def test_no_word_of_the_models_is_read():
    """Review finding: for money, multiples or mixed units the delta fell back to the
    model's "matches" — the F9 case (an "aligned" clause that was not) came back."""
    assert av.compare_delta("capped at USD 10,000", "capped at USD 50,000") \
        == "10000 USD against 50000 USD: the agreement is 40000 USD lower"
    assert av.compare_delta("1 year notice", "6 months notice") == "not comparable"
    assert av.compare_delta("2 times the fees paid", "the total fees paid") \
        == "not comparable"
    assert av.compare_delta("Pune seat", "Mumbai seat") == "not comparable"
    assert av.compare_delta("the Pune seat", "The Pune seat.") == "matches"
    assert av.compare_delta("12 months, then 30 days", "30 days, then 12 months") \
        == "not comparable"          # the same figures in another order are another claim
    assert av.compare_delta("12 months and 30 days", "12 months and 30 days of fees") \
        == "matches"
    assert av.compare_delta("12 months and 30 days", "12 months") == "not comparable"


def test_calendar_and_business_days_are_days():
    assert av.compare_delta("90 calendar days notice", "30 days notice").endswith(
        "60 days longer")
    assert av.compare_delta("2 weeks notice", "14 days notice") == "not comparable"


# ---------------------------------------------------------------- the record span
def test_a_span_may_not_cut_the_negation_off_the_record():
    record = "Invoices are not payable within 30 days of receipt; refunds follow."
    assert av.in_record("not payable within 30 days of receipt", record)
    assert not av.in_record("payable within 30 days of receipt", record)


def test_stretches_keep_the_records_order():
    record = "The liability cap is 12 months of fees. Invoices are due in 60 days."
    assert av.in_record("liability cap \u2026 12 months of fees", record)
    assert not av.in_record("60 days \u2026 liability cap", record)


# --------------------------------------------------------------------- parsing
def test_a_comparison_is_a_sourced_block_with_its_two_cites():
    b = agent._block({"kind": "comparison", "text": "", "agreement": "90 days",
                      "agreement_cite": "D63", "standard": "30 days",
                      "standard_cite": "P7"})
    assert b["kind"] == "sourced" and b["cites"] == ["D63", "P7"]
    assert set(b["compare"]) == {"agreement", "agreement_cite", "standard", "standard_cite"}


@pytest.mark.parametrize("missing", ["agreement", "agreement_cite", "standard",
                                     "standard_cite"])
def test_a_comparison_missing_a_field_is_dropped_not_guessed(missing):
    raw = {"kind": "comparison", "text": "", "agreement": "90 days",
           "agreement_cite": "D63", "standard": "30 days", "standard_cite": "P7"}
    raw[missing] = ""
    parsed = agent._parse(json.dumps({"analysis": "", "assessment": "n/a",
                                      "blocks": [raw, {"kind": "reasoning", "text": "x."}]}))
    assert [b["kind"] for b in parsed[0]] == ["reasoning"]


def test_the_schema_offers_the_comparison_fields():
    props = agent.ANSWER_SCHEMA["properties"]["blocks"]["items"]["properties"]
    assert {"agreement", "agreement_cite", "standard", "standard_cite"} <= set(props)
    assert "delta" not in props          # code computes it; the model writes none
    assert "comparison" in props["kind"]["enum"]


# ---------------------------------------------------------------------- checks
def test_a_true_comparison_has_no_violation():
    assert codes(block()) == []


def test_the_agreement_field_must_cite_a_document_and_the_standard_a_company_record():
    assert "C1" in codes(block(agreement_cite="P7"))
    assert "C1" in codes(block(standard_cite="D63"))


def test_a_span_that_is_not_in_its_record_is_refused():
    assert "C2" in codes(block(agreement="at least 60 days advance written notice"))
    assert "C2" in codes(block(standard="12 months' written notice"))
    assert "C2" in codes(block(agreement="either party may leave on 90 days notice"))


def test_historical_evidence_is_not_a_standard():
    history = av.Evidence("H1", POSITION.text, "§31.2", None, False, "constitution")
    shown = {"D63": CLAUSE, "H1": history}
    assert "C1" in codes(block(standard_cite="H1"), shown)


def test_a_citation_never_shown_is_refused():
    assert "V1" in codes(block(standard_cite="P99"))


def test_a_position_for_another_kind_of_agreement_is_refused():
    other = av.Evidence("P7", POSITION.text, "§31.3", "PARTNER_AGREEMENT agreements only",
                        False, "positions")
    assert "P2" in codes(block(), {"D63": CLAUSE, "P7": other},
                         instruments=frozenset({"MSA"}))
    assert "P2" not in codes(block(), instruments=frozenset({"MSA"}))


def test_commentary_may_carry_no_figure_the_records_do_not():
    assert codes(block(text="The notice is longer.")) == []
    assert "V2" in codes(block(text="It is also 45 days longer than the SLA."))


def test_no_nli_reads_a_structured_comparison(monkeypatch):
    """The prose is exempt from the entailment checker: a comparison that the NLI model
    would call a contradiction (the clause says 90, the standard 30) is just a diff."""
    def boom(*_a, **_k):
        raise AssertionError("the entailment checker must not read a comparison")
    monkeypatch.setattr(av, "_entail", boom)
    monkeypatch.setattr(av, "_entailed", boom)
    assert codes(block()) == []


def test_the_settle_keeps_a_sound_comparison_whole_and_drops_a_false_one():
    good, bad = block(), block(agreement="at least 60 days advance written notice")
    found = av.verify([good, bad], SHOWN, document_selected=True, assessment="n/a")
    kept, dropped = av.settle([good, bad], SHOWN, found, document_selected=True)
    assert dropped == 1 and kept[0]["cites"] == ["D63", "P7"]
    assert kept[0]["compare"] == good["compare"]


# -------------------------------------------------------------------- the reader
def test_a_comparison_renders_as_three_labelled_lines_with_their_own_markers():
    text = av.render([block(text="Longer than ours.")], SHOWN)
    head, _, legend = text.partition("\n\nSources\n\n")
    assert head.split("\n") == [
        "Agreement (cl. 14.3): at least 90 days advance written notice [D63]",
        "Standard (MSA agreements only): 30 days' written notice [P7]",
        "Delta: 90 days against 30 days: the agreement is 60 days longer",
        "Longer than ours."]
    assert "- D63: 14.3" in legend and "- P7: §13, MSA agreements only" in legend


def test_two_comparisons_with_the_same_cites_are_never_merged():
    one = block()
    other = block(agreement="advance written notice", standard="written notice")
    text = av.render([one, other], SHOWN)
    assert text.count("Agreement") == 2 and text.count("Delta:") == 2


def test_a_comparison_counts_as_citing_the_document():
    assert av.cites_document([block()], SHOWN)


# ------------------------------------------------------- when the format is asked for
@pytest.mark.parametrize("message, wanted", [
    ("does this conflict with our standard?", True),
    ("How does the notice period compare with our standard position?", True),
    ("is the cap in line with our policy", True),
    ("does the cap differ from the company standard?", True),
    ("What are your points on this?", False),      # a review asks via `reviewing`
    ("what is our standard position on liability?", False),
    ("What is the notice period?", False),
])
def test_the_format_is_asked_for_when_the_question_compares(message, wanted):
    assert bool(agent._COMPARE.search(message)) is wanted


def test_the_instruction_carries_the_format_only_when_asked():
    asked = agent._final_instruction("en", "does this conflict with our standard?",
                                     compare=True)
    assert "COMPARISON FORMAT" in asked and "kind comparison" in asked
    assert "COMPARISON FORMAT" not in agent._final_instruction("en", "What is the notice?")
    assert "COMPARISON FORMAT" in agent._final_instruction("en", "points?", review=True)


def test_a_comparison_can_cite_only_what_this_turn_showed():
    """An open cite field ran on into a looping paragraph until the output cap cut the
    JSON off — 3 of 11 live Gemini review turns floored on it (2026-10-08); Gemini
    ignores maxLength, so the field is an enum of the shown keys."""
    props = agent.answer_schema(["P7", "D63"])["properties"]["blocks"]["items"]["properties"]
    assert props["agreement_cite"]["enum"] == props["standard_cite"]["enum"] == ["D63", "P7"]
    # the string fields share one dict in the schema: an enum must reach only the two
    # cites (2026-10-08: every field came back as "D58" and 20 of 20 runs floored)
    assert all("enum" not in props[n] for n in ("text", "agreement", "standard", "cites"))
    assert "enum" not in agent.answer_schema(["D63"])["properties"]["analysis"]
    assert "enum" not in agent.ANSWER_SCHEMA["properties"]["blocks"]["items"]["properties"][
        "standard_cite"]


# ---------------------------------------------------------------- the commentary
def _settled(text):
    b = block(text=text)
    found = av.verify([b], SHOWN, document_selected=True, assessment="n/a")
    out, _ = av.settle([b], SHOWN, found, document_selected=True)
    return out


def test_commentary_with_a_verdict_is_removed_and_the_three_lines_stand():
    """Review finding: the commentary skipped every text check, so "acceptable … complies
    with all law … should sign" rode inside a cited block."""
    out = _settled("This deviation is acceptable and the agreement complies with all "
                   "applicable law, so the company should sign.")
    assert len(out) == 1 and out[0]["text"] == "" and out[0]["compare"]
    assert "Delta:" in av._compare_lines(out[0], SHOWN)


def test_commentary_that_the_records_do_not_bear_out_is_removed():
    out = _settled("The agreement gives the customer a 45 day refund window.")
    assert out and out[0]["text"] == ""


def test_commentary_the_records_state_stays():
    kept = "The agreement asks for 90 days advance written notice; the position says 30 days."
    out = _settled(kept)
    assert out and out[0]["text"] == kept
