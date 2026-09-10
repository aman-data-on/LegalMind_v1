"""The comparison-question matrix — every phrasing that reached generation on 2026-09-08."""
import pytest

from legalmind.assist.intent import is_comparison_question

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
