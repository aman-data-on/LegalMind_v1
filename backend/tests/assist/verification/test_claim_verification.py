"""Roadmap PHASE 11 / `AM-90`: claims verified against their evidence, outside the model.

Entailment is stubbed: these pin the verifier's DECISIONS — which checks run, what fails
closed, which citation is assigned — independently of the provisioned NLI weights, whose
accuracy is measured separately (`tools/eval_verification.py`)."""
import uuid

import pytest

from legalmind.assist.llm import generation
from legalmind.assist.query import query_plan as qp
from legalmind.assist.retrieval import evidence
from legalmind.assist.retrieval.retrieval import Candidate
from legalmind.assist.synthesis import answer
from legalmind.assist.verification import verify

POLICY = ("Either party may terminate the agreement for convenience with thirty (30) "
          "days' written notice. Payments are due within 21 days of the invoice date.")
LAW = "Section 74 permits a contract to stipulate a sum payable on breach."
OTHER = "The arbitration shall take place in Mumbai, India."


@pytest.fixture
def nli(monkeypatch):
    """Entailment by containment: a premise entails a claim sharing all its long words."""
    def fake(pairs):
        out = []
        for premise, claim in pairs:
            words = {w for w in claim.lower().replace(".", "").split() if len(w) > 5}
            hit = all(w in premise.lower() for w in words)
            out.append((0.95, 0.01) if hit else (0.02, 0.10))
        return out
    monkeypatch.setattr(verify, "entailment", fake)


def _judge(sentence, *evidence_, kinds=None, auth=None):
    ev = list(evidence_) or [POLICY]
    return verify.judge(sentence, ev, kinds or [qp.COMPANY_POSITION] * len(ev),
                        auth or ["COMPANY_CONSTITUTION"] * len(ev))


def test_a_supported_paraphrase_passes_and_keeps_its_citation(nli):
    j = _judge("Either party may terminate for convenience with thirty days notice [1].")
    assert j.verdict == "SUPPORTED" and j.citations == (1,)


def test_a_claim_cited_to_a_neighbour_is_recited_to_its_support(nli):
    j = _judge("Either party may terminate for convenience [1].", OTHER, POLICY)
    assert j.verdict == "SUPPORTED" and j.citations == (2,)


def test_a_claim_nothing_entails_is_unsupported(nli):
    assert _judge("The customer receives a refund of prepaid charges [1].").verdict \
        == "UNSUPPORTED"


def test_negating_what_the_evidence_asserts_fails_even_when_entailed(monkeypatch):
    monkeypatch.setattr(verify, "entailment", lambda pairs: [(0.99, 0.0)] * len(pairs))
    j = _judge("Payments are not due within 21 days of the invoice date [1].")
    assert j.verdict == "CONTRADICTED" and "negates" in j.reason


def test_a_permission_reported_as_an_obligation_fails(monkeypatch):
    monkeypatch.setattr(verify, "entailment", lambda pairs: [(0.99, 0.0)] * len(pairs))
    j = _judge("Either party must terminate the agreement for convenience [1].")
    assert j.verdict == "CONTRADICTED" and "obligation" in j.reason


def test_a_company_position_is_never_stated_as_the_law(monkeypatch):
    monkeypatch.setattr(verify, "entailment", lambda pairs: [(0.99, 0.0)] * len(pairs))
    j = _judge("The Indian Contract Act provides that either party may terminate [1].")
    assert j.kind_error == "a company position stated as the law"
    ok = _judge("Section 74 permits a contract to stipulate a sum payable on breach [1].",
                LAW, kinds=[qp.LAW], auth=["PRIMARY_LAW"])
    assert ok.verdict == "SUPPORTED" and ok.kind_error is None


def test_the_companys_reading_is_never_stated_as_the_law(monkeypatch):
    monkeypatch.setattr(verify, "entailment", lambda pairs: [(0.99, 0.0)] * len(pairs))
    j = _judge("Section 74 permits a contract to stipulate a sum payable on breach [1].",
               LAW, kinds=[qp.LAW], auth=["SECONDARY_REFERENCE"])
    assert j.kind_error == "the company's reading of the law stated as the law"
    said = _judge("In the company's reading, Section 74 permits a stipulated sum [1].",
                  LAW, kinds=[qp.LAW], auth=["SECONDARY_REFERENCE"])
    assert said.kind_error is None


def test_a_historical_exception_is_never_current_policy(monkeypatch):
    monkeypatch.setattr(verify, "entailment", lambda pairs: [(0.99, 0.0)] * len(pairs))
    j = _judge("Current company policy allows exit after 6 months [1].",
               "One past agreement allowed exit after 6 months.",
               kinds=[qp.HISTORICAL_EXCEPTION], auth=["HISTORICAL_EXCEPTION"])
    assert j.kind_error == "a historical exception stated as current policy"


def test_no_verifier_model_fails_closed(monkeypatch):
    monkeypatch.setattr(verify, "entailment", lambda pairs: None)
    r = verify.check_answer("Either party may terminate [1].", [POLICY],
                            [qp.COMPANY_POSITION], [""], ["Either party may terminate [1]."])
    assert not r.ok


def test_the_verifier_assigns_the_citation_in_the_shown_text(nli):
    s = "Either party may terminate for convenience [1]."
    r = verify.check_answer(s, [OTHER, POLICY], [qp.COMPANY_POSITION] * 2, ["", ""], [s])
    assert r.ok and r.text == "Either party may terminate for convenience [2]."


# --- the corrective retry, end to end through answer.respond --------------------------

@pytest.fixture(autouse=True)
def excerpt_path(monkeypatch):
    """These pin PHASE 11 on the excerpt-numbered path; PHASE 12's contract path has
    its own tests (`test_claim_contracts.py`)."""
    monkeypatch.setattr(answer, "CONTRACTS", False)


def _bundle():
    c = Candidate("CONSTITUTION", "CONST:13", uuid.uuid4(), POLICY, 0.0,
                  "COMPANY_CONSTITUTION", "CURRENT")
    src = evidence.Source(qp.COMPANY_POSITION, c, POLICY, 5.0, True, None)
    part = evidence.Part("q", (qp.COMPANY_POSITION,), evidence.SUPPORTED, (src,))
    return evidence.Bundle((part,), (src,), (), False)


def _result(text):
    return generation.GenerationResult(text, "m", "v", "", 5, 100, 20)


def test_one_corrective_retry_then_the_verified_answer(nli):
    calls = []

    def repair(question, block, draft, failures, **_):
        calls.append(failures)
        return _result("Either party may terminate for convenience [1].")
    out = answer.respond(_bundle(), "q", environment="development", repair=repair,
                         generate=lambda *a, **k: _result("Refunds are always given [1]."))
    assert out.generated and out.calls == 2 and len(calls) == 1
    assert out.first_draft == "Refunds are always given [1]."


def test_a_second_failure_shows_the_fixed_grounded_answer(nli):
    bad = lambda *a, **k: _result("Refunds are always given [1].")  # noqa: E731
    out = answer.respond(_bundle(), "q", environment="development", generate=bad,
                         repair=bad)
    assert not out.generated and out.calls == 2
    assert out.text == answer.fallback(_bundle()), "never a partly verified answer"


def test_precision_mode_keeps_a_grounded_claim_entailment_is_unsure_about(monkeypatch):
    monkeypatch.setattr(verify, "entailment", lambda pairs: [(0.2, 0.1)] * len(pairs))
    monkeypatch.setattr(verify, "STRICT", False)
    grounded = _judge("Payments are due within 21 days of the invoice date [1].")
    invented = _judge("The customer receives a refund of prepaid charges [1].")
    assert grounded.verdict == "SUPPORTED", "neutral entailment is not an error"
    assert invented.verdict == "UNSUPPORTED", "its words are not in the evidence"
    monkeypatch.setattr(verify, "entailment", lambda pairs: [(0.1, 0.9)] * len(pairs))
    assert _judge("Payments are due within 21 days of the invoice date [1].").verdict \
        == "CONTRADICTED", "a confident contradiction still fails"


# 2026-10-06 — two true claims the agent's verifier cut in a live conversation, both
# from a Constitution entry laid out as a table (synthetic rows, the same shape).
_ENTRY = """Entry: Example Obligation:

[the company's reading of the law] | Field | Content |
| :---- | :---- |
| Act / Rule / Regulation | Example Act 2000, Section 9A |
| Applicability | Body corporates handling sensitive personal data; private entities |
| Trigger / Event | Negligence in maintaining reasonable security practices for sensitive personal data by a body corporate |
| Exception / Condition | None identified in the source material |
| Scope Note | Section 9A covers a body corporate maintaining sensitive personal data with reasonable security practices |
| Legal Obligation | Maintain reasonable security practices for sensitive personal data |
| Legal Consequence / Penalty | Non-compliance is punishable by a fine which may extend to Rs 1 lakh. Civil liability to pay compensation to the affected person. |
| Company Requirement | Maintain reasonable security practices for sensitive personal data under Section 9A |
| Legal Applicability | Directly applicable to a private body corporate handling sensitive personal data under Section 9A |"""


def test_a_none_in_one_table_row_does_not_negate_the_next_row():
    from legalmind.assist.verification import guardrails
    claim = "Non-compliance is punishable by a fine up to Rs 1 lakh."
    assert guardrails._polarity_failure(claim, guardrails._words(claim), [_ENTRY]) is None


def test_the_premise_holds_the_row_that_states_the_claim():
    # common words ("sensitive personal data") are on most rows; the rare ones pick it
    top = verify.premises("Under Section 9A a body corporate negligent in maintaining "
                          "reasonable security practices for sensitive personal data has "
                          "civil liability to pay compensation to the affected person.",
                          _ENTRY)[0]
    assert "Civil liability to pay compensation" in top


def test_warm_batches_every_claim_and_judge_then_reads_the_memo(monkeypatch):
    """A 21-block answer judged claim by claim ran 118 model calls (34 s, 2026-10-07);
    warmed, two calls score the same pairs and the verdicts do not change."""
    calls: list[int] = []

    class Containment:
        def pair_logits(self, pairs):
            calls.append(len(pairs))
            return [[-5.0, 5.0 if all(w in p.lower() for w in h.lower().replace(".", "")
                                      .split() if len(w) > 5) else -5.0, 0.0]
                    for p, h in pairs]
    monkeypatch.setattr(verify, "_load", lambda: Containment())
    verify._memo.clear()
    jobs = [(s, [POLICY], [qp.COMPANY_POSITION], ["COMPANY_CONSTITUTION"]) for s in (
        "Either party may terminate for convenience with thirty days notice [1].",
        "The customer receives a refund of prepaid charges [1].")]
    verify.warm(jobs)
    assert len([n for n in calls if n]) == 2
    warmed = len(calls)
    assert [verify.judge(*j).verdict for j in jobs] == ["SUPPORTED", "UNSUPPORTED"]
    assert not any(calls[warmed:])                  # every pair came from the memo
