"""The comparison-question matrix — every phrasing that reached generation on 2026-09-08."""
import pytest

from legalmind.assist.intent import is_comparison_question, is_statute_question

ROUTED = [
    "Please compare this document with our approved legal position. What is acceptable, unacceptable, or requires modification?",
    "Does this document comply with our standard position?",
    "What clauses are missing compared with our approved position?",
    "Compare this against company standards.",
    "Does this contract meet our standard?",
    "What deviations exist from our position?",
    "Is this acceptable under our legal position?",
    "Which clauses require attention against our policy?",
    "Please compare and tell me what is acceptable and unacceptable for us.",
    "Does this liability clause match our approved position?",
    "Is this liability cap OK against our standard?",
    "Can we accept this indemnity clause under company policy?",
    "Is this compliant with our baseline?",
    "Where does this deviate from the Leapswitch template?",
    "Does this meet our approved legal position?",
    "Is this clause consistent with our position?",
]

DESCRIPTIVE = [
    "What is the termination notice period?",
    "Who are the parties to this agreement?",
    "What does this document say about confidentiality?",
    "What is the liability cap in this document?",
    "Is there a clause covering data protection?",
    "What are our payment obligations under this contract?",   # 'our' alone is descriptive
    "What does Section 138 of the Negotiable Instruments Act say?",
    "When does this agreement commence?",
    "Summarise the indemnity clause.",
    "What is our approved position on widget handling care?",   # a position lookup, not a comparison
    "What is our standard liability cap?",
    "What does company policy say about late fees?",
    "What about that?",
    "",
]


@pytest.mark.parametrize("q", ROUTED)
def test_a_comparison_question_is_detected(q):
    assert is_comparison_question(q), q


@pytest.mark.parametrize("q", DESCRIPTIVE)
def test_a_descriptive_question_is_not(q):
    assert not is_comparison_question(q), q


def test_follow_family_is_a_comparison_signal_but_follow_up_is_not():
    """AM-50 r1: 'Does this NDA follow our standards?' is the evaluator's question."""
    from legalmind.assist.intent import is_comparison_question
    assert is_comparison_question("Does this NDA follow our standards?")
    assert is_comparison_question("Does the contract adhere to our approved position?")
    assert not is_comparison_question("What are our follow-up obligations under this contract?")
    assert not is_comparison_question("Following our call, what does the NDA say about notice?")


# --------------------------------------------------------------------------
# The verdict screen for generated text (2026-09-09) — narrower than the router
# --------------------------------------------------------------------------
from legalmind.assist.intent import is_verdict_statement  # noqa: E402


def test_a_real_verdict_is_caught():
    for text in ("This clause complies with our approved standard [1].",
                 "The liability cap deviates from the company's position [2].",
                 "The document is consistent with the approved policy on notice [1].",
                 "This meets the LeapSwitch template's baseline [1]."):
        assert is_verdict_statement(text), text


def test_a_descriptive_answer_is_not_a_verdict():
    for text in ("Leapswitch may terminate the agreement if the breach is not cured within "
                 "thirty (30) days after receipt of written notice [3].",
                 "For non-payment of invoiced amounts, Leapswitch may terminate with thirty "
                 "(30) days' written notice [3].",
                 "CloudPe accepts payment by card [1].",
                 "The parties agree to meet in Mumbai for the review [2].",
                 "The approved vendor list is attached as Schedule B [1]."):
        assert not is_verdict_statement(text), text


# --------------------------------------------------------------------------
# Follow-up detection (2026-09-10) — the deterministic half of conversation memory
# --------------------------------------------------------------------------
@pytest.mark.parametrize("question", [
    "What about clause 7?",
    "What does that mean?",
    "And the penalty?",
    "What happens after that?",
    "Explain more.",
    "Is it the same for the customer?",
    "How long is it?",
])
def test_a_question_that_cannot_stand_alone_is_a_follow_up(question):
    from legalmind.assist.intent import is_follow_up
    assert is_follow_up(question), question


@pytest.mark.parametrize("question", [
    "What is the termination notice period?",
    "Does the contract allow termination for convenience?",
    "What is the liability cap under this Agreement?",
    "Which law governs this document?",
    "What does section 3 of the Synthetic Widgets Act say about handlers?",
    "",
])
def test_a_self_contained_question_is_not_a_follow_up(question):
    from legalmind.assist.intent import is_follow_up
    assert not is_follow_up(question), question


# --------------------------------------------------------------------------
# The 2026-09-16 false positives — measured, not imagined
# --------------------------------------------------------------------------
# The screen used to be "an organization word anywhere AND a comparison word anywhere",
# which is co-occurrence rather than intent. Run through the corrected Tier-2 gate it
# misrouted SEVEN of the 64 answerable questions in the ratified set to the evaluator,
# so a user asking about a cure period was answered with "run a Review".
#
# These are the seven verbatim, each annotated with the unrelated pair that fired it.
MISROUTED_2026_09_16 = [
    # we ... breach — a contract EVENT, not a comparison
    "How much time do we get to fix a breach before the provider can terminate?",
    # we/our ... against — "a claim we have against the provider"
    "Can we deduct a disputed amount from our next payment to offset a claim we have "
    "against the provider?",
    # we ... complete — the stem "compl" reaching "complete"
    "Why do we have to complete identity verification before servers are activated, "
    "and how is it done?",
    # our marketing emails ... meet ... acceptable — "our" possesses the emails
    "What conditions must our marketing emails meet to be acceptable?",
    # a security standard ... satisfying — not OUR standard
    "Which security standard is recognised as satisfying the reasonable-security "
    "requirement for sensitive personal data?",
    # a company ... data breach
    "Can a company be made to pay damages for a data breach caused by its own poor "
    "security?",
    # sign ... a company — signature rules in the abstract
    "Who can validly sign contracts on behalf of a company?",
]


@pytest.mark.parametrize("q", MISROUTED_2026_09_16)
def test_a_factual_question_is_not_a_comparison(q):
    assert not is_comparison_question(q), q


# --------------------------------------------------------------------------
# Generalization — phrasings that appear in no list this classifier was built from
# --------------------------------------------------------------------------
# The fix has to hold for questions nobody wrote down, or it is seven exceptions in a
# trench coat. Neither list below was used while developing the rule.
UNSEEN_COMPARISONS = [
    "How does this differ from our standard terms?",
    "Does the vendor's cap conflict with our approved position?",
    "Is this NDA consistent with our baseline?",
    "Are there any deviations from the Leapswitch template here?",
    "Can we sign this MSA as drafted?",
    "Should I approve this contract?",
    "Tell me whether this agreement is acceptable to us.",
    "Does clause 7 violate our company policy?",
    "Is the indemnity here unacceptable under our approved standard?",
    "Compare the notice periods.",
    "Does this conform to the CloudPe standard?",
    "Is this contract compliant with our position on data protection?",
    "Kya yeh agreement hamari policy ke mutabik hai?",
    "क्या यह अनुबंध हमारे मानक के अनुरूप है?",
]

UNSEEN_FACTUAL = [
    "How much notice must we give before we terminate for convenience?",
    "What happens if we breach the confidentiality clause?",
    "Who signs the agreement on behalf of the provider?",
    "What is the process to complete onboarding?",
    "Which ISO standard does the provider hold certification against?",
    "Can we offset a disputed invoice against amounts owed?",
    "What conditions must our data be stored under?",
    "Are our support tickets subject to a response time?",
    "What risks does the indemnity clause allocate to us?",
    "Does the provider have to meet an uptime target?",
    "Is a company liable for a breach by its subcontractor?",
    "What is the standard cure period in this agreement?",
    "When must we complete identity verification?",
    "What are our obligations if the provider becomes insolvent?",
    "How do we accept delivery of the hardware?",
    "Who is authorised to sign a purchase order for a company?",
]


@pytest.mark.parametrize("q", UNSEEN_COMPARISONS)
def test_an_unseen_comparison_still_reaches_the_evaluator(q):
    """`AM-25` r4 is the reason this direction matters more than the other: a missed
    comparison is a compliance verdict handed to the model."""
    assert is_comparison_question(q), q


@pytest.mark.parametrize("q", UNSEEN_FACTUAL)
def test_an_unseen_factual_question_is_answered_from_the_evidence(q):
    assert not is_comparison_question(q), q


# --------------------------------------------------------------------------
# The three shapes, asserted as shapes rather than as a word list
# --------------------------------------------------------------------------
def test_a_position_noun_needs_a_qualifier_naming_it_as_ours():
    """The single distinction that removes five of the seven: "a security standard" is
    someone's standard, "our approved standard" is the one the evaluator compares to."""
    assert is_comparison_question("Does this meet our standard?")
    assert is_comparison_question("Does this meet the company standard?")
    assert not is_comparison_question("Which security standard does this meet?")
    assert not is_comparison_question("What standard does the provider meet?")


def test_a_possessive_does_not_make_the_thing_it_possesses_a_position():
    """"our marketing emails" is not a position; "our policy" is. The old screen could
    not tell them apart because it never looked at what the possessive possessed."""
    assert is_comparison_question("Are these terms acceptable under our policy?")
    assert not is_comparison_question(
        "What conditions must our marketing emails meet to be acceptable?")


def test_signing_readiness_needs_a_first_person_subject_and_this_document():
    """(B). All three legs — drop any one and an ordinary question routes."""
    assert is_comparison_question("Should we sign this agreement?")
    # no first-person subject
    assert not is_comparison_question("Who can sign this agreement?")
    # no acceptance word
    assert not is_comparison_question("Should we read this agreement?")
    # not about entering THIS document
    assert not is_comparison_question("How do we accept delivery of the hardware?")


def test_an_unambiguous_comparison_verb_needs_no_object():
    """(C). "Please compare and tell me what is acceptable for us" names no position and
    is still the evaluator's question — the verb has no other meaning here."""
    assert is_comparison_question("Please compare.")
    assert is_comparison_question("Does this comply?")
    assert is_comparison_question("List the deviations.")
    # ... and the near-misses that used to ride in on the stem "compl"
    assert not is_comparison_question("What is the process to complete onboarding?")
    assert not is_comparison_question("Is the pricing complex?")


def test_the_screen_reads_every_supported_script():
    """`AM-69`: a screen that cannot evaluate an input fails closed, never open."""
    assert is_comparison_question("हमारे मानक से तुलना करें")
    assert is_comparison_question("Yeh clause hamare standard ke hisaab se sahi hai?")
    assert is_comparison_question("Kya humein ABC agreement sign karna chahiye?")
    assert not is_comparison_question("इस अनुबंध में नोटिस अवधि क्या है?")


# --------------------------------------------------------------------------
# The Domain C candidate signal (widened 2026-09-21)
# --------------------------------------------------------------------------

def test_a_law_question_that_names_no_act_is_still_a_law_question():
    """(B) — jurisdiction framing or a rule-seeking shape, with nothing of the
    reader's own to measure against. The naming test alone recognised 2 of the
    ratified set's 23 statute questions."""
    assert is_statute_question("Is restraint of trade valid in India?")
    assert is_statute_question("What does Indian law say about indemnity?")
    assert is_statute_question("What is the legal rule for liquidated damages?")
    assert is_statute_question("Under Indian law, can a company indemnify its "
                               "own directors?")
    assert is_statute_question("Are agreements stopping someone from carrying on "
                               "their trade or profession enforceable in India?")


def test_an_ambiguous_law_question_is_left_to_the_evidence_gate():
    """Deliberate. "When does a hosting intermediary lose its immunity?" asks for a
    rule, but by SHAPE it is indistinguishable from a contract question about the
    provider's duties — measured, an impersonal-duty signal that caught it also
    routed 4 contract questions to the law, one of them a must-refuse control. The
    router stays conservative and `require_semantic` decides."""
    assert not is_statute_question("When does a hosting intermediary lose its "
                                   "immunity for content its users post?")


def test_the_english_verb_act_is_not_an_Act():
    """The flat regex matched `\\bact\\b`, so "how quickly must we act?" — a question
    about a botched installation — was a question about the law."""
    assert not is_statute_question("The commissioned setup is not what we expected. "
                                   "What is our recourse, and how quickly must we act?")
    assert is_statute_question("What does the Act provide about compensation?")


def test_naming_the_instrument_still_works():
    """(A) — an explicit source reference wins outright, even over a document target:
    "what does s. 43A say about our liability?" names the source to answer from."""
    assert is_statute_question("What does section 43A of the IT Act say?")
    assert is_statute_question("What is the DPDP Act?")
    assert is_statute_question("What does the Companies Act, 2013 require?")
    assert is_statute_question("Does section 27 apply to our agreement?")


def test_a_question_about_the_readers_own_paper_is_never_a_law_question():
    """This flag makes STATUTES a PRIMARY domain and drops `require_semantic` in the
    fall-through — the guard that keeps 44 of the 54 contract questions out of the
    statute corpus. A deal question borrowing statutory vocabulary must not trip it."""
    for question in ("Is our liability cap enforceable?",
                     "Are we liable for indirect losses under this agreement?",
                     "What penalties does the contract impose on us?",
                     "Is the MSA's indemnity legally binding?",
                     "Can we walk away from the agreement before it expires?"):
        assert not is_statute_question(question), question


def test_an_ordinary_deal_question_is_not_a_law_question():
    assert not is_statute_question("What is the termination notice period?")
    assert not is_statute_question("Who signs the order form?")
