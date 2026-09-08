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
    "What about that?",
    "",
]


@pytest.mark.parametrize("q", ROUTED)
def test_a_comparison_question_is_detected(q):
    assert is_comparison_question(q), q


@pytest.mark.parametrize("q", DESCRIPTIVE)
def test_a_descriptive_question_is_not(q):
    assert not is_comparison_question(q), q
