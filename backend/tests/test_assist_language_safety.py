"""The mechanical screens must not be weaker in one language than another.

Measured live 2026-09-15, against the shipped code, with a document attached:

    "does this document comply with our standard?"       -> evaluator      (safe)
    "ABC agreement Company Constitution ke according hai?" -> GENERATIVE   (bypass)
    "हमारे मानक से तुलना करें"  (= "compare with our standard")  -> GENERATIVE   (bypass)

`is_comparison_question` is how `AM-25` r4 — *"the assist lane NEVER answers 'does this
document meet our standard?' … it is never answered generatively"* — is enforced, and
`_WORD = [a-z]+` tokenized the Devanagari question to the empty list. `AM-28` r2's
out-of-model verdict screen was blind the same way, and `guardrails._content_words`
turned the grounding check inside out: an empty content-word set defaulted the overlap
to 1.0, so a fabricated Hindi claim with a citation marker was admitted unconditionally
while its English equivalent was rejected.

None of this relaxes a locked decision. The locks are written without reference to
language, and the code quietly assumed one. These tests pin the guarantees as stated.

The matrix runs BOTH directions on purpose. A screen widened until it fires on
everything is not safer — it just moves every document question to the evaluator — so
every positive case here has a negative twin.
"""

from __future__ import annotations

import pytest

from legalmind.assist import guardrails, intent
from legalmind.assist.state import AssistAnswerState

CHUNK = ("The Receiving Party shall keep all Confidential Information secret for a "
         "period of two (2) years from the date of disclosure.")


# --------------------------------------------------------------------------
# AM-25 r4 — the comparison question reaches the evaluator in every script
# --------------------------------------------------------------------------
@pytest.mark.parametrize("question", [
    # English — the existing matrix, unchanged behaviour
    "does this document comply with our standard?",
    "compare this document with our approved legal position",
    "what clauses are missing compared with our approved position?",
    # Romanized Hinglish — every one of these was answered generatively before
    "ABC agreement Company Constitution ke according hai?",
    "Kya yeh Company Standard ke according hai?",
    "Yeh clause hamare standard ke hisaab se sahi hai?",
    "Kya yeh hamari policy ke mutabik hai?",
    "Hamare approved position se alag kya hai?",
    # Devanagari — tokenized to [] before, so every screen returned False
    "हमारे मानक से तुलना करें",
    "क्या यह हमारी नीति के अनुसार है?",
    "यह दस्तावेज़ हमारे संविधान का पालन करता है?",
])
def test_a_comparison_question_is_detected_in_every_script(question):
    assert intent.is_comparison_question(question) is True


@pytest.mark.parametrize("question", [
    # Descriptive questions that NAME the organization but ask what the document says.
    # These must keep going to the document, or the evaluator swallows ordinary work.
    "what are our payment obligations under this contract?",
    "what does our standard say about liability?",
    "according to our agreement, what is the notice period?",   # the bigram trap
    "following our call, what changed in clause 7?",
    # Hinglish descriptive — names the organization, asks for content
    "hamare contract mein payment terms kya hain?",
    "hamari policy mein notice period kitna hai?",
    # No organization reference at all
    "what is the confidentiality period?",
    "ismein confidentiality period kya hai?",
    "इसमें गोपनीयता की अवधि क्या है?",
])
def test_a_descriptive_question_is_not_a_comparison(question):
    assert intent.is_comparison_question(question) is False


def test_signing_readiness_reaches_the_evaluator_rather_than_the_model():
    """"Should we sign this?" asks for strictly more than a compliance verdict. Until
    Phase 3 gives it a structured route it is handed to the evaluator, which answers
    with Findings — never a generated yes/no (`AM-25` r1/r4)."""
    for question in ("Should we sign this agreement?",
                     "Kya humein ABC agreement sign karna chahiye?",
                     "क्या हमें यह अनुबंध हस्ताक्षर करना चाहिए?"):
        assert intent.is_comparison_question(question) is True, question


# --------------------------------------------------------------------------
# AM-28 r2 — the verdict screen, outside the model, in every script
# --------------------------------------------------------------------------
@pytest.mark.parametrize("answer", [
    "This clause complies with our approved standard.",
    "The cap deviates from the company standard.",
    "Yeh clause Company Standard ke according nahi hai.",
    "Yeh liability cap hamare approved standard se alag hai.",
    "Yeh clause hamari policy ke hisaab se sahi hai.",
    "यह क्लॉज हमारे मानक के अनुसार है।",
    "यह प्रावधान हमारी नीति का उल्लंघन करता है।",
])
def test_a_verdict_statement_is_blocked_in_every_script(answer):
    assert intent.is_verdict_statement(answer) is True


@pytest.mark.parametrize("answer", [
    # Descriptive, grounded sentences that merely name a party or quote the document.
    # The 2026-09-09 regression: these were thrown away as compliance verdicts.
    "Leapswitch may terminate if the breach is not cured within thirty days.",
    "The Receiving Party shall keep Confidential Information secret for two years.",
    "Leapswitch ko tees din ka notice dena hoga.",
    "प्राप्तकर्ता पक्ष को जानकारी गोपनीय रखनी होगी।",
])
def test_a_descriptive_sentence_is_not_a_verdict(answer):
    assert intent.is_verdict_statement(answer) is False


# --------------------------------------------------------------------------
# AM-25 r5 — a claim the screen cannot read is NOT grounded
# --------------------------------------------------------------------------
@pytest.mark.parametrize("answer,why", [
    ("यह क्लॉज हमारे मानक के अनुसार है और देयता की सीमा पचास लाख रुपये है [1].",
     "a fabricated liability figure AND a compliance verdict"),
    ("यह अनुबंध हस्ताक्षर के लिए स्वीकार्य है [1].",
     "'this contract is acceptable to sign'"),
    ("गोपनीयता की अवधि दस वर्ष है [1].",
     "'the confidentiality period is ten years' — the chunk says two"),
])
def test_an_unreadable_claim_is_refused_rather_than_vacuously_grounded(answer, why):
    """Before: `_content_words` matched [A-Za-z] only, so a Devanagari sentence gave an
    empty set and `overlap = ... if claim_words else 1.0` admitted it unconditionally.
    A screen that cannot read a claim has not verified it."""
    result = guardrails.verify_answer(answer, [CHUNK])
    assert result.state is AssistAnswerState.CLAIM_UNSUPPORTED, why
    assert result.failures, why


def test_the_english_behaviour_is_unchanged():
    """The fix must not move the English path — the whole point is that the two agree."""
    grounded = ("The Receiving Party shall keep Confidential Information secret for "
                "two (2) years from the date of disclosure [1].")
    assert guardrails.verify_answer(grounded, [CHUNK]).state is AssistAnswerState.ANSWERED
    fabricated = "The liability cap is five million dollars [1]."
    assert guardrails.verify_answer(
        fabricated, [CHUNK]).state is AssistAnswerState.CLAIM_UNSUPPORTED


def test_a_danda_separated_answer_is_verified_sentence_by_sentence():
    """`_SENTENCES` did not know `।`, so a whole Hindi answer was ONE sentence and a
    single marker anywhere in it satisfied the citation check for every claim."""
    two_claims = "गोपनीयता की अवधि दो वर्ष है [1]। देयता की सीमा पचास लाख रुपये है।"
    result = guardrails.verify_answer(two_claims, [CHUNK])
    # The second sentence carries no marker at all — it must be named as unsupported.
    assert result.state is AssistAnswerState.CLAIM_UNSUPPORTED
    assert any("no citation" in f for f in result.failures), result.failures


# --------------------------------------------------------------------------
# Conversation memory — a Hinglish follow-up must resolve its referent
# --------------------------------------------------------------------------
@pytest.mark.parametrize("question", [
    "What does that mean?",
    "And the penalty?",
    "Isko simple language mein samjhao.",
    "Ismein kya likha hai?",
    "Iska matlab kya hai?",
    "Yeh kya hai?",
    "upar wala clause dikhao",
    "इसका मतलब क्या है?",
    "इसे सरल भाषा में समझाओ।",
])
def test_a_follow_up_is_detected_in_every_script(question):
    assert intent.is_follow_up(question) is True


@pytest.mark.parametrize("question", [
    # A demonstrative introducing a noun is not a reference to an earlier turn —
    # in any script. "yeh agreement" is this agreement, not "the thing we discussed".
    "What is the termination notice period in this agreement?",
    "Is agreement mein termination notice period kitna hai?",
    "Yeh agreement kab tak valid hai?",
    "इस अनुबंध में समाप्ति की सूचना अवधि क्या है?",
])
def test_a_demonstrative_before_a_document_noun_is_not_a_follow_up(question):
    assert intent.is_follow_up(question) is False
