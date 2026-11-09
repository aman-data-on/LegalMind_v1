"""The structural layer of the answer check (P2a, 2026-11-03): a claim that restates a
clause without one of its limbs, widens its party, or grafts on a conclusion is refused
by the SHAPE of the sentence, which precision-mode NLI cannot see (every word of the
claim is in the evidence). Each check says PASS, FAIL or UNKNOWN and never PASS on what
it cannot parse; an UNKNOWN on a sentence with limbs ABSTAINS, never accepts.

These are verifier inputs, not company positions: the clauses are synthetic drafting
shapes, paraphrased, and none is taken from the measured claim sets. No model is loaded —
where the NLI model is consulted its scores are stubbed.
"""
import pytest

from legalmind.assist.verification import structural as st
from legalmind.assist.verification import verify

TERMINATE = ("If the Customer fails to pay an undisputed invoice within thirty days, the "
             "Supplier may suspend the Services.")
ASSIGN = ("The Licensee may assign this licence to an affiliate, except where the "
          "affiliate competes with the Licensor.")


@pytest.fixture
def entail(monkeypatch):
    """Stub the NLI model: every pair scores (entailment, contradiction) = `scores`."""
    def use(scores):
        monkeypatch.setattr(verify, "entailment",
                            lambda pairs: None if scores is None else [scores] * len(pairs))
    return use


# ── limbs ────────────────────────────────────────────────────────────────────────────

def test_a_claim_that_drops_a_leading_condition_fails_anchored_on_it():
    got = st.check("The Supplier may suspend the Services.", [TERMINATE])
    assert got.state == st.FAIL and got.reason == "CONDITION_DROPPED"
    assert got.span.startswith("If the Customer fails to pay")


def test_a_claim_that_omits_a_trailing_exception_fails():
    got = st.check("The Licensee may assign this licence to an affiliate.", [ASSIGN])
    assert (got.state, got.reason) == (st.FAIL, "EXCEPTION_OMITTED")


def test_a_faithful_restatement_that_keeps_every_limb_in_other_words_passes():
    claim = ("Under the agreement, where the Customer does not pay an undisputed invoice "
             "within thirty days, the Supplier may suspend the Services.")
    assert st.check(claim, [TERMINATE]).state == st.PASS


def test_a_limb_restated_elsewhere_in_the_answer_is_not_omitted():
    answer = ("This applies only where the Customer fails to pay an undisputed invoice "
              "within thirty days.",)
    assert st.check("The Supplier may suspend the Services.", [TERMINATE],
                    answer).state != st.FAIL


def test_a_claim_that_states_the_act_more_narrowly_itself_is_not_failed():
    got = st.check("The Supplier may suspend the Services only during a declared "
                   "emergency.", [TERMINATE])
    assert got.state != st.FAIL


def test_a_limb_restated_with_the_opposite_sense_fails():
    evidence = ["The Provider shall not disclose the report unless the regulator "
                "requests it in writing."]
    got = st.check("The Provider shall not disclose the report if the regulator "
                   "requests it in writing.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "LIMB_REVERSED")


def test_dropping_a_qualifier_from_its_noun_fails():
    evidence = ["The Customer may terminate this Agreement by giving prior written "
                "notice to the Supplier."]
    got = st.check("The Customer may terminate this Agreement by giving notice to the "
                   "Supplier.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "CONDITION_DROPPED")


def test_a_statute_proviso_is_a_limb_of_the_sentence_before_it():
    evidence = ["9. Refund of deposit.—(1) The landlord shall refund the deposit within "
                "sixty days of vacation. Provided that the landlord may deduct any unpaid "
                "rent from the deposit."]
    got = st.check("The landlord shall refund the deposit within sixty days of "
                   "vacation.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "CONDITION_DROPPED")


def test_a_limb_of_another_clause_of_the_sentence_is_not_the_claims_limb():
    evidence = ["The Supplier shall publish the price list each quarter; if a price "
                "rises, the Supplier shall give the Customer thirty days' notice."]
    got = st.check("The Supplier shall publish the price list each quarter.", evidence)
    assert got.state == st.PASS


def test_a_claim_restating_only_part_of_a_limited_clause_abstains_never_passes():
    evidence = ["Where the Customer requests it in writing, the Supplier shall provide a "
                "copy of the audit report, the remediation plan and the auditor's "
                "certificate within ten working days of the request."]
    got = st.check("The Supplier shall provide the remediation plan.", evidence)
    assert got.state == st.UNKNOWN and got.limbs
    assert st.combine(True, got) == st.ABSTAIN


def test_a_leading_on_or_following_phrase_is_a_condition_limb():
    evidence = ["On receipt of a written request, the Supplier shall deliver the logs "
                "within five days."]
    got = st.check("The Supplier shall deliver the logs within five days.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "CONDITION_DROPPED")
    evidence = ["Following approval of the estimate, the Supplier shall begin the work."]
    assert st.check("The Supplier shall begin the work.", evidence).state == st.FAIL


def test_two_limbs_each_restated_with_their_own_sense_are_not_reversed():
    evidence = ["Upon expiry of the Term, the licence renews for one year, unless a party "
                "gives notice of non-renewal."]
    got = st.check("Upon expiry of the Term, the licence renews for one year, unless a "
                   "party gives notice of non-renewal.", evidence)
    assert got.state == st.PASS


def test_upon_restated_as_if_is_not_a_reversal():
    evidence = ["Upon termination of the contract, the Supplier shall return the data."]
    got = st.check("If the contract is terminated, the Supplier shall return the data.",
                   evidence)
    assert got.reason != "LIMB_REVERSED"


def test_a_limb_whose_words_its_clause_repeats_is_dropped_when_the_claim_has_no_limb():
    evidence = ["If approved, the refund will be issued within ten days of the approval."]
    got = st.check("The refund will be issued within ten days of the approval.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "CONDITION_DROPPED")


def test_a_short_claim_aligns_on_a_verbatim_run_and_its_dropped_exception_fails():
    evidence = ["This Deed may not be varied except by a writing signed by both parties."]
    got = st.check("This Deed may not be varied.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "EXCEPTION_OMITTED")


def test_a_short_claim_with_no_verbatim_run_does_not_anchor():
    evidence = ["The parties shall vary the schedule only in writing, and the deed "
                "governs."]
    got = st.check("Deed varied.", evidence)
    assert got.state == st.UNKNOWN and not got.limbs


def test_statute_headings_and_the_acts_year_do_not_hide_a_dropped_limb():
    evidence = ["EFFECT OF REGISTRATION (1) On the registration of the deed, the "
                "Registrar shall certify that the deed is recorded."]
    claim = ("Under the Registration of Deeds Act, 1999, the Registrar shall certify that "
             "the deed is recorded.")
    assert st.check(claim, evidence).reason == "CONDITION_DROPPED"
    evidence = ["4.Effect of notice.—If the notice is served, the tenant shall vacate the "
                "premises within thirty days."]
    assert st.check("The tenant shall vacate the premises within thirty days.",
                    evidence).reason == "CONDITION_DROPPED"


# ── scope ────────────────────────────────────────────────────────────────────────────

def test_a_word_limiting_a_quantified_class_deleted_is_widening():
    evidence = ["Every listed company shall appoint an independent auditor."]
    got = st.check("Every company shall appoint an independent auditor.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "SCOPE_WIDENED")


def test_a_footnote_number_after_a_quantifier_is_not_a_limit():
    evidence = ["The debtor shall appear in any 1 proceeding when called upon."]
    got = st.check("The debtor shall appear in any proceeding when called upon.", evidence)
    assert got.state == st.PASS


def test_a_named_party_widened_to_each_party_fails():
    evidence = ["The Distributor shall maintain insurance cover of a reasonable amount "
                "with a reputable insurer."]
    got = st.check("Each party shall maintain insurance cover of a reasonable amount "
                   "with a reputable insurer.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "SCOPE_WIDENED")


def test_an_affected_class_widened_to_all_fails():
    evidence = ["The Supplier shall refund the fees for the affected services."]
    got = st.check("The Supplier shall refund the fees for all services.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "SCOPE_WIDENED")


def test_a_universal_the_evidence_itself_states_is_not_widening():
    evidence = ["Either party may terminate this Agreement for material breach."]
    got = st.check("Either party may terminate the Agreement for material breach.",
                   evidence)
    assert got.state == st.PASS


# ── parts ────────────────────────────────────────────────────────────────────────────

def test_a_grafted_conclusion_the_model_does_not_entail_fails(entail):
    entail((0.05, 0.1))
    evidence = ["The Customer shall keep the access credentials confidential."]
    got = st.check("The Customer shall keep the access credentials confidential; "
                   "therefore a leak voids the warranty.", evidence)
    assert (got.state, got.reason) == (st.FAIL, "UNSUPPORTED_CONCLUSION")


def test_a_second_part_the_model_entails_passes(entail):
    entail((0.95, 0.01))
    evidence = ["The Customer shall keep the access credentials confidential and shall "
                "report any suspected leak promptly."]
    got = st.check("The Customer shall keep the access credentials confidential; "
                   "accordingly, a suspected leak must be reported promptly.", evidence)
    assert got.state == st.PASS


def test_without_the_model_a_conclusion_part_is_unknown_and_abstains(entail):
    entail(None)
    evidence = ["The Customer shall keep the access credentials confidential."]
    got = st.check("The Customer shall keep the access credentials confidential; "
                   "therefore a leak voids the warranty.", evidence)
    assert got.state == st.UNKNOWN and st.combine(True, got) == st.ABSTAIN


def test_a_list_divided_by_semicolons_is_not_read_as_conclusions(entail):
    entail((0.0, 0.0))
    evidence = ["The notice shall state: the affected service; the expected retirement "
                "date; and any available migration option."]
    got = st.check("The notice shall state the affected service; the expected "
                   "retirement date; and any available migration option.", evidence)
    assert got.state == st.PASS


def test_an_enumerations_items_are_not_read_as_conclusions(entail):
    entail((0.0, 0.0))
    evidence = ["The officer shall,— (a) receive every complaint; (b) acknowledge it "
                "within a day; and (c) resolve it within fifteen days."]
    got = st.check("The officer shall,— (a) receive every complaint; (b) acknowledge it "
                   "within a day; and (c) resolve it within fifteen days.", evidence)
    assert got.state == st.PASS


# ── combining ────────────────────────────────────────────────────────────────────────

def test_no_anchor_is_never_a_fail_and_leaves_the_existing_verdict():
    got = st.check("Arbitration shall be seated in a neutral venue.", [TERMINATE])
    assert got.state == st.UNKNOWN and not got.limbs
    assert st.combine(True, got) is True


def test_combine_follows_the_owners_rule():
    assert st.combine(False, st.Check(st.PASS)) is False          # rejection stands
    assert st.combine(True, st.Check(st.FAIL, "SCOPE_WIDENED")) is False
    assert st.combine(True, st.Check(st.UNKNOWN, limbs=True)) == st.ABSTAIN
    assert st.combine(True, st.Check(st.PASS)) is True


# ── production wiring ────────────────────────────────────────────────────────────────

def _judge(claim, evidence):
    return verify.judge(f"{claim} [1].", [evidence], ["COMPANY_POSITION"],
                        ["COMPANY_CONSTITUTION"])


@pytest.mark.parametrize("flag", [None, "off", "nonsense"])
def test_the_flag_is_off_by_default_and_judge_is_unchanged(monkeypatch, entail, flag):
    entail((0.95, 0.01))
    if flag is None:
        monkeypatch.delenv("LEGALMIND_STRUCTURAL_CHECK", raising=False)
    else:
        monkeypatch.setenv("LEGALMIND_STRUCTURAL_CHECK", flag)
    assert st.mode() == "off"
    assert _judge("The Supplier may suspend the Services", TERMINATE).verdict == "SUPPORTED"


def test_with_the_flag_on_a_dropped_limb_is_contradicted(monkeypatch, entail):
    entail((0.95, 0.01))
    monkeypatch.setenv("LEGALMIND_STRUCTURAL_CHECK", "on")
    j = _judge("The Supplier may suspend the Services", TERMINATE)
    assert j.verdict == "CONTRADICTED" and j.reason == "structural: CONDITION_DROPPED"
    assert _judge("If the Customer fails to pay an undisputed invoice within thirty "
                  "days, the Supplier may suspend the Services",
                  TERMINATE).verdict == "SUPPORTED"


def test_in_shadow_mode_the_finding_is_logged_and_the_verdict_kept(monkeypatch, entail):
    entail((0.95, 0.01))
    monkeypatch.setenv("LEGALMIND_STRUCTURAL_CHECK", "shadow")
    seen = []
    monkeypatch.setattr(verify, "log_event", lambda event, **f: seen.append((event, f)))
    assert _judge("The Supplier may suspend the Services", TERMINATE).verdict == "SUPPORTED"
    assert seen and seen[0][0] == "assist.verify.structural"
    assert seen[0][1]["reason"] == "CONDITION_DROPPED"


def test_with_the_flag_on_check_answer_reads_the_other_sentences(monkeypatch, entail):
    entail((0.95, 0.01))
    monkeypatch.setenv("LEGALMIND_STRUCTURAL_CHECK", "on")
    sentences = ["The Supplier may suspend the Services [1].",
                 "That right arises only if the Customer fails to pay an undisputed "
                 "invoice within thirty days [1]."]
    result = verify.check_answer(" ".join(sentences), [TERMINATE], ["COMPANY_POSITION"],
                                 ["COMPANY_CONSTITUTION"], sentences)
    assert result.judgements[0].verdict == "SUPPORTED"
