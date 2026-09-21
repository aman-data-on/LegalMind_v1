"""Citation verification and refusal — `AM-25` r5, enforced outside the model.

`AM-25` r5: *"No answer reaches a user unless every claim in it resolves to retrieved
evidence. Enforcement is mechanical and sits outside the model."* `AM-28` r2 adds the
structural condition: this component is *"tested independently of prompt and model code,
and does not import them. A guardrail that a prompt change can affect is not a
guardrail."*

So this module imports NO model, NO prompt, NO network client and NO generation code —
`tests/test_import_boundaries.py` and its own tests enforce that. Everything here is a
pure function over data the caller already holds.

--------------------------------------------------------------------------
What the calibration proved this layer must do
--------------------------------------------------------------------------
The retrieval gate catches "nothing relevant exists" (12/13 measured). What it cannot
catch — measured, not assumed — is the adversarial near-miss: a question whose nearest
clause is genuinely topical but does not answer it. Those score INSIDE the answerable
distribution for every candidate model, so no similarity feature separates them. They
are caught here instead, at the claim level: an answer whose sentences do not ground in
the retrieved text fails verification, whatever its retrieval scores looked like.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from legalmind.assist.state import AssistAnswerState

# A generated answer must mark each claim's source with [n] markers referring to the
# 1-based position of the supporting chunk in the evidence list it was given. The
# format is part of the generation CONTRACT (the prompt instructs it), but its
# enforcement lives here and depends only on the marker grammar.
_MARKER = re.compile(r"\[(\d{1,2})\]")

# Sentence-ish split for grounding checks. Deliberately simple: the unit of
# verification is "a claim with a marker", and anything unmarkered is itself a defect.
# The danda `।` and double danda `॥` are Devanagari full stops: without them a whole
# Hindi answer was ONE sentence, so a single `[1]` anywhere in it satisfied the
# marker check for every claim it made.
_SENTENCES = re.compile(r"(?<=[.!?।॥])\s+")

# The share of a claim's content words that must appear in its cited chunk for the
# claim to count as grounded. This is NOT a legal threshold and NOT retrieval
# confidence: it is a lexical-overlap floor for "the cited text could actually be the
# source of this sentence", catching fabricated citations and grafted numbers. Content
# words, because stopwords ground everything.
_GROUNDING_OVERLAP = 0.5

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "by",
        "with",
        "as",
        "at",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "from",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "their",
        "his",
        "her",
        "they",
        "he",
        "she",
        "we",
        "you",
        "your",
        "our",
        "us",
        "not",
        "no",
        "if",
        "then",
        "than",
        "shall",
        "may",
        "must",
        "can",
        "will",
        "would",
        "should",
        "under",
        "over",
        "any",
        "all",
        "each",
        "which",
        "who",
        "whom",
        "what",
        "when",
        "where",
        "how",
        "such",
        "other",
        "into",
        "upon",
        "per",
    ]
)


@dataclass(frozen=True)
class Citation:
    claim: str
    chunk_index: int  # 1-based position in the evidence list
    grounded: bool


@dataclass(frozen=True)
class Verification:
    state: AssistAnswerState
    citations: list[Citation]
    failures: list[str]

    @property
    def passed(self) -> bool:
        return self.state is AssistAnswerState.ANSWERED


# A claim's QUANTITIES must appear in the text it cites. The overlap check below
# cannot see this: it is a bag-of-words ratio, so one decisive token is diluted by the
# copied words around it. Measured 2026-09-21 on the ratified corpus — every one of
# these PASSED the 0.5 overlap check and would have reached a reader:
#
#   "at least 90 days' prior written notice"        overlap 0.92   (source says 30)
#   "shall not exceed fifty lakh rupees"            overlap 0.67   (invented cap)
#   "Trade secret obligations expire after ten years" overlap 0.57  (invented expiry)
#
# A notice period, a cap and an expiry are the whole content of a legal answer, and a
# wrong one is worse than a refusal. This check is exact, local and costs nothing.
#
# Digits always count. A number WORD counts only when a unit follows it, because
# "either one of the parties" is not a quantity and requiring "1" in the evidence
# would refuse honest paraphrases.
_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11",
    "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30", "forty": "40",
    "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
    "hundred": "100", "thousand": "1000", "lakh": "100000", "crore": "10000000",
    "million": "1000000", "billion": "1000000000",
}
_UNIT = (r"day|days|week|weeks|month|months|year|years|hour|hours|"
         r"rupee|rupees|lakh|lakhs|crore|crores|percent|%|inr|usd|rs")
_DIGIT_QUANTITY = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD_QUANTITY = re.compile(
    rf"\b({'|'.join(_NUMBER_WORDS)})\b[\s\-]+(?:{_UNIT})\b", re.IGNORECASE)


def _quantities(text: str) -> set[str]:
    """Every number the text ASSERTS, normalised so 'twelve (12)' matches '12'."""
    stripped = _MARKER.sub("", text).lower()
    found = {m.replace(",", "").rstrip(".") for m in _DIGIT_QUANTITY.findall(stripped)}
    found |= {_NUMBER_WORDS[m.lower()] for m in _WORD_QUANTITY.findall(stripped)}
    return found


# A claim may not introduce a POLARITY the evidence does not carry. The ratio above
# cannot see this either, for the same reason: an inversion reuses the source's own
# words and scores high. Measured 2026-09-21 against the ratified Partner Agreement
# position, which says either party MAY terminate on 30 days' notice —
#
#   "A Partner Agreement may ONLY be terminated with the written consent of both
#    parties"                                          overlap 0.62, and it PASSED
#
# — the opposite of what the organization approved, built from its own vocabulary.
#
# Checked as CLASSES, not as words, so a paraphrase may restate a negation the
# evidence already carries: "No early-termination fee is payable" and "Neither side
# owes an early-termination fee" both hold a negation, so the second is not flagged.
# Only a class the evidence does not use at all is treated as introduced.
# `AM-76`: a grounded explanation may not "add facts, conditions, exceptions,
# quantities, or legal conclusions not supported by evidence". Quantities are checked
# above; these are the other three shapes that a word ratio cannot see, because each
# is built from the source's own vocabulary.
_POLARITY_CLASSES = {
    # NO GENERAL NEGATION CLASS, and that is a measured decision rather than an
    # oversight. A negation is very often a faithful restatement of something the
    # source states positively: "may terminate for convenience" genuinely means "a
    # breach is not required", and flagging that rejected an answer the owner had
    # already judged grounded (tests/test_assist_ask.py, the 2026-09-09 live answer).
    # Across the 18-case set the negation class caught nothing the exception and
    # exclusivity classes did not, so it cost accuracy and bought nothing.
    "exclusivity": re.compile(r"\b(only|solely|exclusively)\b", re.I),
    # A carve-out the source does not make is a new condition, whatever words carry
    # it. Measured: "…capped at the fees paid in the 12 months before the claim,
    # EXCEPT in cases of gross negligence" scored 0.67 against a cap clause that
    # carves out nothing, and passed. Where the source DOES carve out ("except that
    # obligations relating to trade secrets…"), a paraphrase may restate it.
    "exception": re.compile(
        r"\b(except|unless|save for|other than|apart from|provided that|"
        r"subject to|carve-?out)\b", re.I),
}


def _introduced_polarity(claim: str, cited: list[str]) -> list[str]:
    """Polarity classes the claim uses that its cited text does not use at all."""
    text = _MARKER.sub("", claim)
    evidence = " ".join(cited)
    return [name for name, pattern in _POLARITY_CLASSES.items()
            if pattern.search(text) and not pattern.search(evidence)]


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]+|\d[\d.,%]*", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def evidence_is_sufficient(chunks: list[str]) -> bool:
    """The pre-generation sufficiency check — `AM-29`'s second outcome.

    The model is NOT called when there is nothing of substance to ground in. The
    retrieval gate has already ruled on relevance; this rules on there being enough
    text to constitute evidence at all — an empty list, or fragments too short to
    contain a clause, cannot support any answer and calling the model over them would
    manufacture one.
    """
    return sum(len(c.strip()) for c in chunks) >= 80


def verify_answer(answer: str, chunks: list[str]) -> Verification:
    """Mechanically verify a generated answer against the evidence it was given.

    Four checks, all deterministic, all independent of how the answer was produced:

      1. Refusal passthrough — an answer that IS a refusal needs no citations.
      2. Every sentence carries at least one citation marker.
      3. Every marker resolves to a chunk that actually exists in the evidence list.
      4. Every cited sentence lexically grounds in its cited chunk(s).

    Failure yields CLAIM_UNSUPPORTED and the answer never reaches a user
    (`AM-25` r5); the failures list says exactly which claim failed and why, because a
    reviewer must be able to reconstruct the refusal.
    """
    failures: list[str] = []
    citations: list[Citation] = []

    text = (answer or "").strip()
    if not text:
        return Verification(
            AssistAnswerState.CLAIM_UNSUPPORTED,
            [],
            ["the model produced an empty answer"],
        )

    # 1 — a self-declared refusal is honored as EVIDENCE_INSUFFICIENT: the model was
    # shown evidence and judged it non-responsive. It is never rewritten into an
    # answer, and it carries no citations to verify.
    if text.upper().startswith("NOT FOUND"):
        return Verification(AssistAnswerState.EVIDENCE_INSUFFICIENT, [], [])

    sentences = [s.strip() for s in _SENTENCES.split(text) if s.strip()]
    for sentence in sentences:
        markers = [int(m) for m in _MARKER.findall(sentence)]
        if not markers:
            failures.append(f"unsupported claim (no citation): {sentence[:80]!r}")
            continue
        cited_chunks: list[str] = []
        for n in markers:
            if not (1 <= n <= len(chunks)):
                failures.append(f"citation [{n}] does not exist in the evidence")
                continue
            cited_chunks.append(chunks[n - 1])
        if not cited_chunks:
            continue
        claim_words = _content_words(_MARKER.sub("", sentence))
        cited_words = set().union(*(_content_words(c) for c in cited_chunks))
        if not claim_words:
            # FAIL CLOSED. This used to default the overlap to 1.0, which read as
            # "a sentence with no content words asserts nothing, so it grounds
            # vacuously". `_content_words` matches [A-Za-z] and digits only, so a
            # Devanagari sentence yields an empty set — and every Hindi answer was
            # therefore admitted unconditionally, fabricated numbers and compliance
            # verdicts included. Measured 2026-09-15: "यह क्लॉज हमारे मानक के अनुसार
            # है और देयता की सीमा पचास लाख रुपये है [1]" passed against an English
            # confidentiality clause, while its English equivalent was rejected.
            #
            # `AM-25` r5 requires every claim to resolve to retrieved evidence, with
            # enforcement mechanical and outside the model. A screen that cannot
            # read a claim has not verified it, so it must refuse it. The remedy for
            # a language this check cannot compare is a check that can — never a
            # default that lets it through.
            failures.append(
                f"claim cannot be verified against its cited text "
                f"(no comparable content): {sentence[:80]!r}"
            )
            grounded = False
        else:
            overlap = len(claim_words & cited_words) / len(claim_words)
            grounded = overlap >= _GROUNDING_OVERLAP
            if not grounded:
                failures.append(
                    f"claim does not ground in its cited text "
                    f"(overlap {overlap:.2f}): {sentence[:80]!r}"
                )
            # EVERY FIGURE THE CLAIM STATES MUST BE IN THE TEXT IT CITES. Checked
            # separately from the ratio above, and exactly, because a ratio cannot see
            # it: swapping 30 days for 90 leaves twelve of thirteen words untouched and
            # scores 0.92. Two answers that differ only in the number a reader will act
            # on are not equally grounded, however similar their vocabulary.
            invented = _quantities(sentence) - set().union(
                *(_quantities(c) for c in cited_chunks))
            if invented:
                grounded = False
                failures.append(
                    f"claim states a figure its cited text does not "
                    f"({', '.join(sorted(invented))}): {sentence[:80]!r}"
                )
            # Same discipline, applied to meaning-reversing words rather than
            # figures: an inversion is built from the source's own vocabulary and so
            # scores HIGH on the ratio. See `_POLARITY_CLASSES`.
            polarity = _introduced_polarity(sentence, cited_chunks)
            if polarity:
                grounded = False
                failures.append(
                    f"claim introduces {'/'.join(polarity)} its cited text does not "
                    f"carry: {sentence[:80]!r}"
                )
        for n in markers:
            if 1 <= n <= len(chunks):
                citations.append(Citation(sentence, n, grounded))

    state = (
        AssistAnswerState.ANSWERED
        if not failures
        else AssistAnswerState.CLAIM_UNSUPPORTED
    )
    return Verification(state, citations, failures)


# --------------------------------------------------------------------------
# Key Obligations (owner, 2026-08-31) — the descriptive/judgment boundary,
# enforced mechanically. An extracted obligation is a fact about the text;
# any line that reads as a compliance verdict, a risk assessment or advice is
# discarded before persistence, whatever the prompt said.
# --------------------------------------------------------------------------
_JUDGMENT_LANGUAGE = re.compile(
    r"\b(compli(?:es|ant|ance)|non-compliant|acceptable|unacceptable|risk[sy]?|"
    r"recommend(?:s|ed|ation)?|should (?:not )?accept|violat(?:es|ion)|"
    r"meets? (?:our|the) standard|deviat(?:es|ion))\b",
    re.IGNORECASE)


def is_judgment_language(text: str) -> bool:
    """True when an extracted line carries compliance/risk vocabulary.

    The obligations feature never produces a Finding, a Classification or any
    judgment (AM-25) — this screen makes that a property of the code, not of
    the prompt (`AM-28` r2's spirit: a guardrail a prompt change can affect is
    not a guardrail).
    """
    return bool(_JUDGMENT_LANGUAGE.search(text or ""))
