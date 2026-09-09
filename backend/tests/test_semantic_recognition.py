"""AM-54 — grounded semantic recognition, tested against materially different
drafting styles with the generative model FAKED (no egress in the suite) and the
local embedding model real. Every accepted semantic claim must be verifiable in
the clause text; every unverifiable one must fail closed to a person.
"""
from __future__ import annotations

import json

import pytest

from legalmind.analysis import semantic
from legalmind.analysis.service import run_analysis
from legalmind.assist import embedding_runtime, generation
from legalmind.domain import enums as E
from legalmind.evaluation.user_status import by_finding
from tests.test_analysis import LEGAL_RULE, MAPPING, STANDARD, build, storage  # noqa: F401

pytestmark = pytest.mark.skipif(not embedding_runtime.available(),
                                reason="local embedding model not provisioned")

ZERO_TOLERANCE = {"deviation_outcome": "UNACCEPTABLE", "unlimited_outcome": "UNACCEPTABLE",
                  "rule_configuration": LEGAL_RULE["rule_configuration"]}

# A presence requirement whose configured terminology is deliberately narrow, so
# a paraphrase confirms nothing lexically and the semantic stage has to speak.
RESIDUALS_MAPPING = {"exact_phrases": ["incidentally retained in the unaided memory"],
                     "aliases": ["residuals", "residual information"],
                     "section_heading_terms": ["residuals"], "confirm_threshold": 5}
# Typed MSA so the builder's declared MSA contract puts it in the family (AM-51):
# outside the family an unresolved mapping produces no Finding at all.
RESIDUALS_STANDARD = {"document_type": "MSA", "expected_presence": "PRESENT",
                      "scope_key": "RESIDUALS", "applicability": "REQUIRED"}
RESIDUALS_DESCRIPTION = ("The receiving party's staff may use confidential information "
                         "they happen to remember, in their ordinary work.")

PARAPHRASES = [
    "Free Use of Recollections. Personnel of the recipient shall be free to use, in the "
    "course of their ordinary business, any know-how that remains in their unaided "
    "recollection without deliberate memorisation, and this shall not be a breach.",
    "Nothing in this Agreement restricts the receiving side's employees from applying "
    "general skills, ideas and concepts they retain mentally after working with the "
    "disclosed material, provided no document or copy is kept.",
]


def _fake(monkeypatch, replies: list[str], calls: list[str]):
    def fake(prompt, *, prompt_version, environment, request_id=None,
             evidence_count=None, max_output_tokens=1024):
        calls.append(prompt)
        text = replies.pop(0) if replies else "{}"
        return generation.GenerationResult(text=text, model="fake@test",
                                           prompt_version=prompt_version,
                                           payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(generation, "generate_raw", fake)


def _refuse(monkeypatch, calls: list[str]):
    def fake(prompt, **kw):
        calls.append(prompt)
        raise generation.GenerationRefused("no credential")
    monkeypatch.setattr(generation, "generate_raw", fake)


def _yes(span: str, position: str = "SAME") -> str:
    return json.dumps({"verdicts": [{"clause": 1, "addresses": "YES",
                                     "position": position, "span": span}]})


def _residuals(build, description=RESIDUALS_DESCRIPTION):
    rv = build.requirement("RESIDUALS-NDA-001", E.EvaluatorType.PRESENCE,
                           mapping=RESIDUALS_MAPPING, standard=RESIDUALS_STANDARD,
                           legal_rule=ZERO_TOLERANCE)
    rv.description = description
    build.db.flush()
    return rv


# 1 — materially different drafting, none of the configured words: recognised
@pytest.mark.parametrize("clause", PARAPHRASES, ids=["recollection-style", "skills-style"])
def test_a_paraphrase_is_recognised_on_a_verbatim_span(build, db, monkeypatch, clause):
    _residuals(build)
    review = build.review(["11. Confidential Information — Use", clause])
    calls: list[str] = []
    span = clause.split(". ", 1)[-1][:80] if ". " in clause else clause[:80]
    _fake(monkeypatch, [_yes(span)], calls)
    run = run_analysis(db, review)
    outcome = run.outcomes[0]
    assert outcome.mapping_state == "CONFIRMED"
    assert outcome.classification == "MATCH"
    assert len(calls) == 1 and "DATA ONLY" in calls[0]
    # The company's position never left the building (AM-30 t3).
    assert "expected_presence" not in calls[0] and "PRESENT" not in calls[0]
    assert any("confirmed on a verbatim span" in d for d in outcome.diagnostics)


# 2 — a YES without a verifiable span is not a claim: fail closed
def test_an_unverifiable_yes_leaves_the_mapping_unresolved(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["11. Confidential Information — Use", PARAPHRASES[0]])
    calls: list[str] = []
    _fake(monkeypatch, [_yes("this sentence does not appear in the clause at all")], calls)
    run = run_analysis(db, review)
    outcome = run.outcomes[0]
    assert outcome.mapping_state == "UNRESOLVED"
    assert outcome.classification == "UNABLE_TO_EVALUATE"
    assert by_finding(db, [review.id])[review.id][outcome.finding_id] == "NEEDS_REVIEW"


# 2b — a clause ON the subject that states a DIFFERENT position is a person's call
def test_a_different_position_on_the_subject_is_never_confirmed(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["11. Confidential Information — Use", PARAPHRASES[0]])
    _fake(monkeypatch, [_yes(PARAPHRASES[0][:80], position="DIFFERENT")], [])
    run = run_analysis(db, review)
    assert run.outcomes[0].mapping_state == "UNRESOLVED"
    assert run.outcomes[0].classification == "UNABLE_TO_EVALUATE"
    assert any("different position" in d for d in run.outcomes[0].diagnostics)


# 3 — no model reached: no semantic evidence either way, so the deterministic
# lexical result stands and the gap is on the record (a bare similarity score
# decides nothing — 35.19)
def test_without_a_model_the_lexical_result_stands_and_the_gap_is_recorded(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["11. Confidential Information — Use", PARAPHRASES[0]])
    calls: list[str] = []
    _refuse(monkeypatch, calls)
    run = run_analysis(db, review)
    outcome = run.outcomes[0]
    assert len(calls) == 1
    assert outcome.mapping_state == "NONE"
    assert outcome.classification == "MISSING"
    assert any("no model reached" in d for d in outcome.diagnostics)


# 3b — a transient provider failure is retried once; a refusal never is
def test_a_transient_provider_failure_is_retried_once(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["11. Confidential Information — Use", PARAPHRASES[0]])
    calls: list[str] = []
    span = PARAPHRASES[0].split(". ", 1)[-1][:80]

    def flaky(prompt, *, prompt_version, environment, request_id=None,
              evidence_count=None, max_output_tokens=1024):
        calls.append(prompt)
        if len(calls) == 1:
            raise generation.GenerationUnavailable("provider returned HTTP 503")
        return generation.GenerationResult(text=_yes(span), model="fake@test",
                                           prompt_version=prompt_version,
                                           payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(generation, "generate_raw", flaky)
    monkeypatch.setattr("time.sleep", lambda s: None)
    run = run_analysis(db, review)
    assert len(calls) == 2
    assert run.outcomes[0].classification == "MATCH"


def test_a_refusal_is_never_retried(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["11. Confidential Information — Use", PARAPHRASES[0]])
    calls: list[str] = []
    _refuse(monkeypatch, calls)
    run_analysis(db, review)
    assert len(calls) == 1


# 4 — the model says NO: the deterministic answer stands, evidence-free absence
def test_a_no_verdict_keeps_established_absence(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["11. Confidential Information — Use", PARAPHRASES[0]])
    calls: list[str] = []
    _fake(monkeypatch, [json.dumps({"verdicts": [{"clause": 1, "addresses": "NO", "span": ""}]})], calls)
    run = run_analysis(db, review)
    assert run.outcomes[0].mapping_state == "NONE"
    assert run.outcomes[0].classification == "MISSING"


# 5 — an unrelated document never reaches the model at all
def test_an_unrelated_clause_is_never_sent_to_the_model(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["8. Invoicing", "Invoices are payable within fifteen (15) days "
                           "of receipt by bank transfer to the account nominated by Leapswitch."])
    calls: list[str] = []
    _refuse(monkeypatch, calls)
    run = run_analysis(db, review)
    assert calls == []
    assert run.outcomes[0].mapping_state == "NONE"


# 5b — outside the declared family the stage is silent: applicability across
# families stays lexical (AM-51), so no cross-family adjacency can create a Finding
def test_an_out_of_family_requirement_never_reaches_the_model(build, db, monkeypatch):
    rv = build.requirement("RESIDUALS-NDA-001", E.EvaluatorType.PRESENCE,
                           mapping=RESIDUALS_MAPPING,
                           standard={**RESIDUALS_STANDARD, "document_type": "NDA"},
                           legal_rule=ZERO_TOLERANCE)
    rv.description = RESIDUALS_DESCRIPTION
    build.db.flush()
    review = build.review(["11. Confidential Information — Use", PARAPHRASES[0]])
    calls: list[str] = []
    _refuse(monkeypatch, calls)
    run = run_analysis(db, review)                      # the contract is declared MSA
    assert calls == []
    assert run.findings_created == 0


# 6 — lexical confirmation is never widened semantically
def test_lexical_confirmation_skips_the_semantic_stage(build, db, monkeypatch):
    _residuals(build)
    review = build.review(["11. Residuals", "The Receiving Party's personnel may use "
                           "Confidential Information incidentally retained in the unaided "
                           "memory of such personnel."])
    calls: list[str] = []
    _refuse(monkeypatch, calls)
    run = run_analysis(db, review)
    assert calls == []
    assert run.outcomes[0].classification == "MATCH"


# 7 — stage 2: a cap the configured phrases cannot read, verified in the text
def _liability(build):
    rv = build.requirement("LIABILITY-MSA-STRUCT", E.EvaluatorType.NUMERIC_COMPARISON,
                           mapping=MAPPING, standard=STANDARD, legal_rule=ZERO_TOLERANCE)
    rv.description = "Each party's total liability is capped at the fees paid over a set period."
    build.db.flush()


def _cap_reply(value, unit, span, states_cap=True, unlimited=False):
    return json.dumps({"states_cap": states_cap, "unlimited": unlimited,
                       "value": value, "unit": unit, "span": span})


@pytest.mark.parametrize("clause,value,expected", [
    ("Limitation of Liability. Each party's aggregate liability under this Agreement "
     "is capped at 6 months of fees paid.", 6, "MATCH"),
    ("Limitation of Liability. Each party's aggregate liability under this Agreement "
     "is capped at twelve months of fees paid.", 12, "DEVIATION"),
], ids=["capped-at-digits-same", "capped-at-words-different"])
def test_a_verified_semantic_magnitude_feeds_the_deterministic_comparison(
        build, db, monkeypatch, clause, value, expected):
    _liability(build)
    review = build.review(["3. Limitation of Liability", clause])
    span = clause.split("Liability. ", 1)[1]
    _fake(monkeypatch, [_cap_reply(value, "months", span)], [])
    run = run_analysis(db, review)
    outcome = run.outcomes[0]
    assert outcome.classification == expected, outcome.diagnostics
    assert any("verified in span" in d for d in outcome.diagnostics)


def test_a_magnitude_not_written_in_the_clause_is_refused(build, db, monkeypatch):
    _liability(build)
    clause = ("Limitation of Liability. Each party's aggregate liability under this "
              "Agreement is capped at 6 months of fees paid.")
    review = build.review(["3. Limitation of Liability", clause])
    _fake(monkeypatch, [_cap_reply(24, "months", clause.split("Liability. ", 1)[1])], [])
    run = run_analysis(db, review)
    assert run.outcomes[0].classification == "UNABLE_TO_EVALUATE"   # Needs review
    assert any("not written in the span" in d for d in run.outcomes[0].diagnostics)


def test_an_unlimited_claim_is_never_taken_from_the_model(build, db, monkeypatch):
    _liability(build)
    clause = ("Limitation of Liability. Each party's liability under this Agreement "
              "is without any limit whatsoever.")
    review = build.review(["3. Limitation of Liability", clause])
    _fake(monkeypatch, [_cap_reply(None, None, clause, unlimited=True)], [])
    run = run_analysis(db, review)
    assert run.outcomes[0].classification == "UNABLE_TO_EVALUATE"


def test_no_cap_stated_keeps_the_absence_with_its_evidence(build, db, monkeypatch):
    """Lexically confirmed clause (the heading term maps it), no quantity: absence
    is the deterministic, established answer — as before AM-54."""
    _liability(build)
    review = build.review(["3. Limitation of Liability",
                           "Neither party is liable for indirect or consequential loss."])
    _fake(monkeypatch, [_cap_reply(None, None, "", states_cap=False)], [])
    run = run_analysis(db, review)
    assert run.outcomes[0].classification == "MISSING"


def test_a_semantically_mapped_clause_with_no_readable_quantity_needs_review(build, db, monkeypatch):
    """No configured word confirmed this clause; the model did. A quantity the text
    then does not yield is uncertainty, never absence: Needs review, not MISSING."""
    _liability(build)
    clause = ("Cap on Damages. The most either side can be made to pay the other under "
              "this contract is one year of total fees paid.")
    review = build.review(["9. Cap on Damages", clause])
    _fake(monkeypatch, [_yes(clause[:70]), _cap_reply(None, None, "", states_cap=False)], [])
    run = run_analysis(db, review)
    assert run.outcomes[0].mapping_state == "CONFIRMED"
    assert run.outcomes[0].classification == "UNABLE_TO_EVALUATE"


# 8 — the pure mechanics, without a document
def test_a_verbatim_span_must_be_long_enough_and_present():
    assert semantic._verbatim("the total fees paid by the customer", "X the Total fees  paid by the Customer Y")
    assert not semantic._verbatim("fees paid", "the total fees paid by the customer")
    assert not semantic._verbatim("the total fees paid by the vendor", "the total fees paid by the customer")


def test_fenced_or_broken_json_is_tolerated_as_unclear():
    assert semantic._parse_verdicts('```json\n{"verdicts":[{"clause":1,"addresses":"yes","position":"same","span":"x"}]}\n```', 1) == {1: ("YES", "SAME", "x")}
    assert semantic._parse_verdicts('{"verdicts":[{"clause":1,"addresses":"YES","span":"x"}]}', 1) == {1: ("YES", "UNCLEAR", "x")}
    assert semantic._parse_verdicts("not json", 1) == {}
    assert semantic._parse_verdicts('{"verdicts":[{"clause":7,"addresses":"YES","span":"x"}]}', 1) == {}
