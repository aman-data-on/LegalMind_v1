"""Roadmap §13 — multi-source legal reasoning, end to end through `answer.respond`.

The golden question needs the Constitution, the executed MSA's availability, historical
exception evidence, the law and the reader's own claim in one answer — "not blended into
one undifferentiated truth" but each said as itself: "Our Constitution says…", "The
customer is claiming…", "The signed MSA is not currently available…", "Historical
agreements are exceptions, not current policy…", "The amount cannot be confirmed…".
Deterministic: a stub stands in for Gemini, the entailment layer passes through (it is
pinned in `test_claim_verification.py`), the records cases read the real Constitution.
"""
import uuid

import pytest

from legalmind.assist import answer, constitution, evidence, generation, verify
from legalmind.assist import query_plan as qp
from legalmind.assist.retrieval import Candidate

GOLDEN = ("A client says their signed MSA mentions 6 months of compensation for early "
          "termination, but we cannot find the final signed copy. What does our Legal "
          "Constitution say about early termination compensation?")
POLICY = "The full remaining committed-term value is payable on early exit."
READING = ("[the company's reading of the law] Section 74 caps recovery at reasonable "
           "compensation where a stipulated sum is a penalty.")
HISTORY = "One past agreement allowed exit after 6 months with no fee."


@pytest.fixture(autouse=True)
def contract_path(monkeypatch):
    monkeypatch.setattr(verify, "check_answer",
                        lambda text, *a, **k: verify.Result(True, text, [], []))
    monkeypatch.setattr(answer, "REPAIR", False)


def _source(ref, text, kind, *, authority="COMPANY_CONSTITUTION", status="CURRENT"):
    c = Candidate("CONSTITUTION", ref, uuid.uuid4(), text, 0.0, authority, status)
    return evidence.Source(kind, c, text, 5.0, True, None)


@pytest.fixture
def golden():
    sources = (_source("CONST:14", POLICY, qp.COMPANY_POSITION),
               _source("CONST:28.4.1", READING, qp.LAW,
                       authority="SECONDARY_REFERENCE"),
               _source("CONST:31.2", HISTORY, qp.HISTORICAL_EXCEPTION,
                       authority="HISTORICAL_EXCEPTION", status="HISTORICAL"))
    part = evidence.Part("What does the Constitution say?", (qp.COMPANY_POSITION,),
                         evidence.SUPPORTED, sources)
    claim = evidence.Assertion("A client says their signed MSA mentions 6 months.",
                               ("6 months",), ("6 months",), (qp.HISTORICAL_EXCEPTION,))
    return evidence.Bundle((part,), sources, (claim,), True)


def _numbers(bundle):
    _, cs = answer.contract_payload(bundle, GOLDEN)
    return {c.kind: c.n for c in cs}


def _model(text, finish=None):
    def generate(question, block, **_):
        generate.block = block
        return generation.GenerationResult(text, "m", "v", "", 5, 100, 20, finish)
    return generate


def _respond(bundle, text, finish=None):
    return answer.respond(bundle, GOLDEN, environment="test",
                          generate=_model(text, finish))


def _layered(n):
    return (f"The company position is that the full remaining committed-term value is "
            f"payable on early exit [{n['COMPANY_POSITION']}]. "
            f"Historically (a past negotiated deal, not current policy), one past "
            f"agreement allowed exit after 6 months with no fee [{n['HISTORICAL_EXCEPTION']}].")


def test_every_layer_reaches_the_model_labelled_and_apart(golden):
    payload, cs = answer.contract_payload(golden, GOLDEN)
    kinds = {c.kind for c in cs}
    assert {"COMPANY_POSITION", "LAW_READING", "HISTORICAL_EXCEPTION"} <= kinds
    assert "No company position states 6 months" in payload.assertion_line
    assert "signed/controlling agreement is not available" in payload.missing_line
    for say in ("The company position", "The company's reading of the law",
                "Historically (a past negotiated deal, not current policy)"):
        assert f"SAY AS: {say}" in payload.block


def test_an_answer_that_forgets_the_readers_claim_and_the_missing_msa_still_says_both(
        golden):
    shown = _respond(golden, _layered(_numbers(golden)))
    assert shown.generated, shown.failures
    assert "No company position states 6 months; that figure is the reader's account, " \
        "not a verified term [A]." in shown.text, "the customer's claim, as a claim"
    assert "The signed agreement is not available here, so its actual terms cannot be " \
        "confirmed [M]." in shown.text, "the amount cannot be confirmed"


def test_an_answer_cut_at_the_output_cap_keeps_its_finished_sentences(golden):
    # Run 9 (GT-00, GT-09): the unfinished last sentence failed as "no citation" and the
    # golden answer fell back to a source dump.
    cut = _layered(_numbers(golden)) + " You cannot confirm the compensation amount " \
        "without checking the signed MSA because the controlling"
    shown = _respond(golden, cut, finish="MAX_TOKENS")
    assert shown.generated, shown.failures
    assert "because the controlling" not in shown.text
    assert "[M]." in shown.text and "[A]." in shown.text
    unfinished = _respond(golden, cut)             # the provider did NOT say it was cut
    assert not unfinished.generated and any("no citation" in f
                                            for f in unfinished.failures)


def test_history_is_never_current_and_the_readers_figure_never_the_policy(golden):
    n = _numbers(golden)
    for blended in (
            f"The company position is that exit after 6 months with no fee is allowed "
            f"[{n['COMPANY_POSITION']}].",
            f"Historically (a past negotiated deal, not current policy), the current "
            f"policy allows exit after 6 months [{n['HISTORICAL_EXCEPTION']}]."):
        shown = _respond(golden, blended)
        # Caught, and replaced by the approved record text (sentence repair) or the
        # fixed answer — either way the blend never reaches the reader.
        assert blended not in shown.text
        assert "allows exit after 6 months" not in shown.text
        assert "exit after 6 months with no fee is allowed" not in shown.text


def test_the_fixed_answer_says_each_layer_as_itself(golden):
    shown = _respond(golden, "")
    assert not shown.generated
    lines = shown.text.split("\n")
    assert any(x.startswith("The company position") for x in lines)
    assert any(x.startswith("The company's reading of the law") for x in lines)
    assert any(x.startswith("Historically (a past negotiated deal") for x in lines)
    assert "No company position states 6 months; that figure is the reader's account, " \
        "not a verified term." in lines
    assert "The signed agreement is not available here, so its actual terms cannot be " \
        "confirmed." in lines


def test_a_historical_restatement_named_as_history_is_not_a_verdict(golden):
    n = _numbers(golden)
    said = (f"Historically (as a past negotiated deal, not current policy), one past "
            f"agreement allowed exit after 6 months with no fee "
            f"[{n['HISTORICAL_EXCEPTION']}].")
    assert not any("compliance verdict" in f for f in answer.check(
        said, answer.contract_payload(golden, GOLDEN)[0], golden))


@pytest.fixture
def records(db):
    constitution.ingest(db)
    return db


def _const(db, section, kind):
    from sqlalchemy import text as sql

    from legalmind import config
    item = db.execute(sql(f'SELECT id FROM "{config.assist_schema()}".knowledge_items '
                          "WHERE section_path = :s AND kind = 'PARAGRAPH' LIMIT 1"),
                      {"s": section}).scalar()
    c = Candidate("CONSTITUTION", f"CONST:{section}", item, "x", 0.0,
                  "HISTORICAL_EXCEPTION", "CURRENT", (kind,))
    return evidence.Source(kind, c, "Standard Position: renewal on 30 days' notice. "
                           "[Customer A] had a 12-month renewal.", 5.0, True, None)


def test_a_figure_one_claim_of_a_mixed_source_states_is_never_called_unstated(records):
    # Run 9 (H-03), all three runs: §31.15 holds the standard renewal position (30 days'
    # notice) AND the historical deals. Read by the source's label, "30 day" was
    # "stated by no company position" — told to Gemini, and the true sentence rejected.
    source = _const(records, "31.15", qp.HISTORICAL_EXCEPTION)
    part = evidence.Part("Were there past MSAs with a 30-day exit?",
                         (qp.HISTORICAL_EXCEPTION,), evidence.SUPPORTED, (source,))
    bundle = evidence.Bundle((part,), (source,), (), False)
    payload, cs = answer.contract_payload(
        bundle, "Were there past signed MSAs with a 30-day, no-penalty exit?", records)
    assert cs and "30 day" not in payload.reader_figures
    assert "No company position states" not in payload.assertion_line
    six, _ = answer.contract_payload(bundle, "Did we agree a 6-month renewal?", records)
    assert six.reader_figures == ("6 month",), \
        "a figure only the historical deals state is still not the position"


def test_the_company_position_is_never_stated_from_a_historical_deal(golden):
    # Live (GT-00): one sentence spoke for the Constitution while citing only a past deal.
    n = _numbers(golden)
    h = n["HISTORICAL_EXCEPTION"]
    blended = (f"The Legal Constitution does not specify 6 months of compensation, though "
               f"historically, under a past negotiated deal and not current policy, one "
               f"agreement allowed exit after 6 months with no fee [{h}].")
    shown = _respond(golden, _layered(n) + " " + blended)
    assert "The Legal Constitution does not specify" not in shown.text
    for fine in (f"Historically (a past negotiated deal, not current policy), one past "
                 f"agreement allowed exit after 6 months with no fee [{h}].",
                 f"No company position states 6 months; historically one past agreement "
                 f"allowed exit after 6 months with no fee [A][{h}]."):
        assert fine in _respond(golden, _layered(n).split(". Historically")[0] + ". "
                                + fine).text, fine
