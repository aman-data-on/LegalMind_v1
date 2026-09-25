"""Roadmap PHASE 10 / `AM-89`: generation over the evidence bundle, checked outside it."""
import uuid

import pytest

from legalmind.assist import answer, evidence, generation, verify
from legalmind.assist import query_plan as qp
from legalmind.assist.retrieval import Candidate


@pytest.fixture(autouse=True)
def mechanical_layer_only(monkeypatch):
    """These pin PHASE 10's mechanical checks. The PHASE 11 semantic layer is pinned in
    `test_claim_verification.py` and measured with real weights by
    `tools/eval_verification.py`; here it passes everything through unchanged."""
    monkeypatch.setattr(verify, "check_answer",
                        lambda text, *a, **k: verify.Result(True, text, [], []))
    monkeypatch.setattr(answer, "REPAIR", False)

GOLDEN = ("A client says their signed MSA mentions 6 months of compensation for early "
          "termination, but we cannot find the final signed copy. What does our Legal "
          "Constitution say about early termination compensation?")
POLICY = "The full remaining committed-term value is payable on early exit."
HISTORY = "One past agreement allowed exit after 6 months with no fee."


def _source(ref, text, kind, *, authority="COMPANY_CONSTITUTION", status="CURRENT",
            domain="CONSTITUTION"):
    c = Candidate(domain, ref, uuid.uuid4(), text, 0.0, authority, status)
    return evidence.Source(kind, c, text, 5.0, True, None)


def _bundle(*sources, assertions=(), missing=False):
    part = evidence.Part("What does the Constitution say?", (qp.COMPANY_POSITION,),
                         evidence.SUPPORTED, tuple(sources))
    return evidence.Bundle((part,), tuple(sources), tuple(assertions), missing)


def _reply(text):
    def generate(question, block, **_):
        generate.block = block
        return generation.GenerationResult(text, "m", "v", "", 5, 100, 20)
    return generate


@pytest.fixture
def golden():
    policy = _source("CONST:14", POLICY, qp.COMPANY_POSITION)
    history = _source("CONST:31.2", HISTORY, qp.HISTORICAL_EXCEPTION,
                      authority="HISTORICAL_EXCEPTION", status="HISTORICAL")
    claim = evidence.Assertion("A client says their signed MSA mentions 6 months.",
                               ("6 months",), ("6 months",),
                               (qp.HISTORICAL_EXCEPTION,))
    return _bundle(policy, history, assertions=[claim], missing=True)


def test_an_unanswerable_bundle_never_reaches_the_model():
    empty = evidence.Bundle((evidence.Part("q", (), evidence.INSUFFICIENT, ()),), (),
                            (), False)

    def never(*a, **k):
        raise AssertionError("the model was called on an unanswerable bundle")
    out = answer.respond(empty, "q", environment="development", generate=never)
    assert not out.generated and "do not answer" in out.text


def test_the_payload_labels_every_kind_and_keeps_the_assertion_apart(golden):
    gen = _reply("The Constitution requires the full remaining committed-term value "
                 "[1]. Six months appears only in a past negotiated deal, not in current "
                 "policy [2]. The client's 6 months is their account and must be checked "
                 "[A]. The signed MSA is missing, so its terms cannot be confirmed [M].")
    out = answer.respond(golden, GOLDEN, environment="development", generate=gen)
    assert out.generated, out.failures
    block = gen.block
    assert "COMPANY POSITION (current policy) — Legal Constitution L1.10 §14" in block
    assert "HISTORICAL EXCEPTION (a past negotiated deal — NOT current policy)" in block
    assert "[A] " in block and "NOT evidence" in block
    assert "No company position states 6 months" in block and "[M] MISSING" in block
    assert str(golden.sources[0].candidate.item_id) not in block, "an internal id egressed"


def test_the_readers_figure_said_as_the_position_is_never_shown(golden):
    out = answer.respond(golden, GOLDEN, environment="development",
                         generate=_reply("Our policy is 6 months of compensation [1]."))
    assert not out.generated
    assert any("reader's figure" in f or "not in the cited text" in f
               for f in out.failures)
    assert "not a verified term" in out.text, "the fallback names the claim for what it is"


def test_a_figure_its_citation_does_not_carry_fails_closed(golden):
    out = answer.respond(golden, GOLDEN, environment="development",
                         generate=_reply("Early exit costs 3 months of fees [1]."))
    assert not out.generated and "figure" in out.failures[0]


def test_an_uncited_sentence_or_a_dangling_marker_fails(golden):
    for text in ("The remaining value is payable.", "The remaining value is payable [9]."):
        out = answer.respond(golden, GOLDEN, environment="development",
                             generate=_reply(text))
        assert not out.generated


def test_a_section_reference_is_not_a_figure(golden):
    out = answer.respond(golden, GOLDEN, environment="development", generate=_reply(
        "Under §14 the full remaining committed-term value is payable [1]."))
    assert out.generated, out.failures


def test_citing_the_assertion_does_not_launder_a_figure_into_policy(golden):
    out = answer.respond(golden, GOLDEN, environment="development",
                         generate=_reply("Our policy is 6 months of fees [1][A]."))
    assert not out.generated and any("reader's figure" in f for f in out.failures)
    assert out.draft == "Our policy is 6 months of fees [1][A].", "the draft is kept"


def test_a_question_figure_is_reported_on_the_assertion_line_not_computed_by_the_model():
    policy = _source("CONST:14", POLICY, qp.COMPANY_POSITION)
    gen = _reply("No 6-month lock-in is stated in the company position [A]. The full "
                 "remaining committed-term value is payable on early exit [1].")
    out = answer.respond(_bundle(policy), "Is there a 6-month lock-in in our MSA?",
                         environment="development", generate=gen)
    assert "No company position states 6 month" in gen.block
    assert out.generated, out.failures


def test_a_question_figure_named_absent_passes_but_never_as_a_bound(golden):
    ok = answer.respond(golden, GOLDEN, environment="development", generate=_reply(
        "The position requires the full remaining value rather than 6 months [1]."))
    assert ok.generated, ok.failures
    bound = answer.respond(golden, GOLDEN, environment="development", generate=_reply(
        "The fee is not more than 6 months of charges [1]."))
    assert not bound.generated


def test_a_company_name_abbreviation_is_not_a_sentence_break(golden):
    out = answer.respond(golden, GOLDEN, environment="development", generate=_reply(
        "The position applies to Leapswitch Networks Pvt. Ltd. agreements [1]."))
    assert out.generated, out.failures


def test_describing_what_the_position_calls_unacceptable_is_not_a_verdict(golden):
    ok = answer.respond(golden, GOLDEN, environment="development", generate=_reply(
        "The company position treats suspension without notice as unacceptable [1]."))
    assert ok.generated, ok.failures
    judged = answer.respond(golden, GOLDEN, environment="development", generate=_reply(
        "The client's claim is not consistent with our position [1][A]."))
    assert not judged.generated and any("verdict" in f for f in judged.failures)


def test_an_unanswered_part_gets_a_missing_line_to_cite():
    policy = _source("CONST:14", POLICY, qp.COMPANY_POSITION)
    parts = (evidence.Part("What is the policy?", (qp.COMPANY_POSITION,),
                           evidence.SUPPORTED, (policy,)),
             evidence.Part("Is it enforceable?", (qp.LAW,), evidence.INSUFFICIENT, ()))
    b = evidence.Bundle(parts, (policy,), (), False)
    payload = answer.render(b, "q")
    assert payload.missing_line and "Is it enforceable?" in payload.missing_line


def test_a_dirty_span_refuses_egress_before_any_call():
    dirty = _source("POS:X", "See LEGAL_CONSTITUTION_L1.10.md for the value.",
                    qp.COMPANY_POSITION, domain="POSITIONS")

    def never(*a, **k):
        raise AssertionError("egressed a span carrying an internal locator")
    out = answer.respond(_bundle(dirty), "q", environment="development", generate=never)
    assert not out.generated and out.failures[0].startswith("egress screen")


def test_an_assertion_alone_never_makes_the_readers_figure_a_fact(golden):
    out = answer.respond(golden, GOLDEN, environment="development",
                         generate=_reply("The compensation is 6 months [A]."))
    assert not out.generated and "stated as fact" in out.failures[0]


def test_a_historical_exception_is_never_called_policy(golden):
    out = answer.respond(golden, GOLDEN, environment="development",
                         generate=_reply("Current policy allows exit after 6 months [2]."))
    assert not out.generated
    assert any("historical exception stated as policy" in f for f in out.failures)
