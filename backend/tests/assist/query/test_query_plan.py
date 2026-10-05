"""Roadmap PHASE 6 / `AM-85`: the deterministic structured query plan. No DB, no model."""
from legalmind.assist.query import query_plan as Q

EARLY_EXIT = "Fixed-Term Commitments & Early Exit"
GOLDEN = ("A client says their signed MSA mentions 6 months of compensation for early "
          "termination, but we cannot find the final signed copy. What does our Legal "
          "Constitution say about early termination compensation? Does it specify 6 "
          "months, 12 months, or the full remaining contract value? What should we do in "
          "this situation, and can we confirm the compensation amount without checking "
          "the signed MSA?")


def test_equivalent_wording_converges_on_one_topic():
    for q in ("terminate early", "end the MSA early", "exit before the term ends",
              "customer wants to leave early", "agreement ko jaldi end karna hai",
              "Is there a 6-month lock-in in our standard MSA?"):
        assert Q.plan(q).topic == EARLY_EXIT, q
    assert Q.plan("What is the notice period to terminate?").topic != EARLY_EXIT


def test_the_golden_question_decomposes_and_keeps_its_sources_apart():
    p = Q.plan(GOLDEN, has_document=False)
    assert p.topic == EARLY_EXIT and p.complex
    assert p.figures == ("6 months", "12 months")
    assert p.document_state == "UNAVAILABLE"
    assert {Q.COMPANY_POSITION, Q.USER_ASSERTION, Q.MISSING_DOCUMENT, Q.LAW} <= p.lanes
    # The client's assertion is context, never a question to retrieve for.
    assert len(p.claims) == 1
    assert not any(s.text.startswith("A client says") for s in p.sub_questions)
    assert len(p.sub_questions) == 4
    assert all("early exit fixed-term commitment" in s.query for s in p.sub_questions)


def test_lanes_fire_on_what_is_said_not_on_a_bare_word():
    assert Q.LAW not in Q.plan("The customer says we promised them 6 months of "
                               "compensation on early exit. Is that our policy?").lanes
    assert Q.CONTRACT not in Q.plan("Does it specify the full remaining contract "
                                    "value?").lanes
    old = Q.plan("An old signed MSA says 30 days and no penalty. Is that our policy?")
    assert Q.HISTORICAL_EXCEPTION in old.lanes and Q.CONTRACT not in old.lanes
    assert Q.plan("What is the weather in Pune today?").lanes == frozenset()


def test_a_contract_question_with_no_document_in_scope_marks_it_unavailable():
    q = "What is the liability cap in our signed contract with this customer?"
    assert Q.MISSING_DOCUMENT in Q.plan(q, has_document=False).lanes
    assert Q.MISSING_DOCUMENT not in Q.plan(q, has_document=True).lanes
    assert Q.MISSING_DOCUMENT not in Q.plan(q).lanes          # unknown adds nothing


def test_language_is_read_from_script_and_grammar():
    assert Q.plan("इस NDA में गोपनीयता की अवधि क्या है?").language == "hi"
    assert Q.plan("NDA ki confidentiality kitne saal tak chalti hai?").language == "hinglish"
    assert Q.plan("What is our liability cap?").language == "en"


def test_a_claim_about_signed_paper_opens_the_historical_record():
    # PHASE 9 (`AM-88`): paper we cannot see may be a past negotiated exception.
    q = "A client says their signed MSA mentions 6 months. What is our policy?"
    assert Q.HISTORICAL_EXCEPTION in Q.plan(q).lanes
    assert Q.HISTORICAL_EXCEPTION not in Q.plan("What is our early exit policy?").lanes


def test_with_a_document_open_every_part_asks_the_document():
    """`AM-106`: 26 of 44 ratified document questions missed their clause because the
    plan gave them only the company-position lane; the document entered as a one-slot
    extra. Without a document the lane is not added."""
    q = "Can we walk away from the agreement before it expires, and what would it cost us?"
    with_doc = Q.plan(q, has_document=True)
    assert all(Q.CONTRACT in s.lanes for s in with_doc.sub_questions)
    without = Q.plan("What is our liability cap?", has_document=False)
    assert all(Q.CONTRACT not in s.lanes for s in without.sub_questions)
