"""AMENDMENT A to AM-90 (2026-10-08): chained entailment for a claim that synthesises
several sources. A multi-source comparison — "the clause says X, whereas our standard
says Y" — is entailed part by part, each part by the chunk it speaks about. A claim with
one cited chunk is judged exactly as before. Synthetic records only (rule 21)."""
from __future__ import annotations

import pytest

from legalmind.assist.query import query_plan as qp
from legalmind.assist.verification import verify

needs_model = pytest.mark.skipif(verify._load() is None,
                                 reason="measures the local NLI model itself")

CLAUSE = ("14.3 Either party may terminate this Agreement for its convenience by giving "
          "the other party at least ninety (90) days advance written notice.")
STANDARD = ("For MSA agreements the company's standard position is that either party may "
            "terminate for convenience on thirty (30) days' written notice.")
LAW = "23.1 This Agreement is governed by the laws of India."
KINDS = [qp.CONTRACT, qp.COMPANY_POSITION, qp.CONTRACT]


def _judge(claim: str, evidence: list[str], marks: str):
    return verify.judge(f"{claim} {marks}", evidence, KINDS[:len(evidence)],
                        [""] * len(evidence))


def test_a_part_naming_the_standard_rests_on_the_companys_records_only():
    both = (1, 2)
    assert verify._route("our standard is 30 days", both, KINDS) == (2,)
    assert verify._route("the clause allows 90 days", both, KINDS) == (1,)
    assert verify._route("anything", (1, 3), KINDS) == (1, 3)      # no company record
    assert verify._route("our standard", (2,), KINDS) == (2,)      # one source: unchanged


def test_a_judgement_is_direct_unless_it_says_otherwise():
    j = verify.Judgement("s", "SUPPORTED", (1,), (1,), 0.9, 0.0)
    assert j.derivation == "direct"


@needs_model
def test_a_true_comparison_is_a_synthesis_supported_part_by_part():
    j = _judge("Clause 14.3 allows termination for convenience on 90 days' written "
               "notice, whereas the company's standard position is 30 days' written "
               "notice.", [CLAUSE, STANDARD], "[1][2]")
    assert j.verdict == "SUPPORTED"
    assert j.derivation == "synthesis" and j.citations == (1, 2)


@needs_model
def test_a_cite_that_supports_no_part_is_not_credited_and_the_sentence_stays():
    j = _judge("Clause 14.3 allows termination for convenience on 90 days' written "
               "notice, whereas the company's standard position is 30 days' written "
               "notice.", [CLAUSE, STANDARD, LAW], "[1][2][3]")
    assert j.verdict == "SUPPORTED" and 3 not in j.citations


@needs_model
@pytest.mark.parametrize("claim", [
    "Clause 14.3 allows termination for convenience on 60 days' written notice, whereas "
    "the company's standard position is 30 days' written notice.",
    "Clause 14.3 allows termination for convenience on 90 days' written notice, whereas "
    "the company's standard position is 12 months' written notice.",
])
def test_a_false_part_is_still_rejected_in_a_synthesis(claim):
    assert _judge(claim, [CLAUSE, STANDARD], "[1][2]").verdict != "SUPPORTED"


@needs_model
def test_a_comparison_is_not_contradicted_by_the_chunk_of_the_other_part():
    """"…whereas our standard is 30 days" read against the document's own 90 days is a
    comparison, not a contradiction of the document: the part rests on the standard."""
    j = _judge("Clause 14.3 allows termination for convenience on 90 days' written "
               "notice, whereas the company's standard position is 30 days' written "
               "notice and no early exit is permitted without a financial consequence.",
               [CLAUSE, STANDARD], "[1][2]")
    assert j.verdict != "CONTRADICTED"


@needs_model
def test_a_single_source_claim_is_judged_exactly_as_before():
    wrong = verify.judge("Either party may terminate for convenience on 90 days' notice. "
                         "[1]", [STANDARD], [qp.COMPANY_POSITION], [""])
    assert wrong.verdict in {"CONTRADICTED", "UNSUPPORTED"}
    right = verify.judge("Either party may terminate for convenience on 30 days' written "
                         "notice. [1]", [STANDARD], [qp.COMPANY_POSITION], [""])
    assert right.verdict == "SUPPORTED" and right.derivation == "direct"


# --------------------------------------------- model-free: a scripted entailment scorer
# Review finding (2026-10-08): every test of `judge`'s chained branches needed the local
# model, so none ran in CI. These drive the same branches with a scorer that reads the
# figures and words of each (premise, part) pair — the routing, the part-by-part rule and
# the crediting are the code's; only the scores are scripted.
_NUMBER = {"ninety": "90", "thirty": "30", "sixty": "60"}


def _nums(text: str) -> set[str]:
    import re
    for word, digit in _NUMBER.items():
        text = re.sub(rf"\b{word}\b", digit, text.lower())
    return set(re.findall(r"\d+", text))


def _words(text: str) -> set[str]:
    import re
    return set(re.findall(r"[a-z]{5,}", text.lower()))


def _scripted(pairs):
    out = []
    for premise, part in pairs:
        said, held = _nums(part), _nums(premise)
        overlap = len(_words(part) & _words(premise)) / max(1, len(_words(part)))
        if said and held and not said <= held:
            out.append((0.02, 0.95))            # a figure the premise does not carry
        elif overlap >= 0.5:
            out.append((0.92, 0.03))
        else:
            out.append((0.1, 0.1))
    return out


@pytest.fixture()
def scripted(monkeypatch):
    monkeypatch.setattr(verify, "entailment", _scripted)


TRUE = ("Clause 14.3 allows termination for convenience on 90 days' written notice, "
        "whereas the company's standard position is 30 days' written notice.")


def test_scripted_a_true_comparison_is_a_synthesis_supported_part_by_part(scripted):
    j = _judge(TRUE, [CLAUSE, STANDARD], "[1][2]")
    assert j.verdict == "SUPPORTED" and j.derivation == "synthesis"
    assert j.citations == (1, 2)


def test_scripted_a_cite_that_supports_no_part_is_not_credited(scripted):
    j = _judge(TRUE, [CLAUSE, STANDARD, LAW], "[1][2][3]")
    assert j.verdict == "SUPPORTED" and 3 not in j.citations


@pytest.mark.parametrize("claim", [
    TRUE.replace("90 days", "60 days"),                  # the clause's part is wrong
    TRUE.replace("is 30 days", "is 60 days"),            # the standard's part is wrong
])
def test_scripted_a_part_its_own_record_does_not_carry_fails_the_claim(scripted, claim):
    assert _judge(claim, [CLAUSE, STANDARD], "[1][2]").verdict != "SUPPORTED"


def test_scripted_one_cited_record_is_judged_directly(scripted):
    j = _judge("Clause 14.3 allows termination for convenience on 90 days' written "
               "notice.", [CLAUSE], "[1]")
    assert j.verdict == "SUPPORTED" and j.derivation == "direct"
