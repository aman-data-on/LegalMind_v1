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
_SENTENCES = re.compile(r"(?<=[.!?])\s+")

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
        overlap = (
            len(claim_words & cited_words) / len(claim_words) if claim_words else 1.0
        )
        grounded = overlap >= _GROUNDING_OVERLAP
        if not grounded:
            failures.append(
                f"claim does not ground in its cited text "
                f"(overlap {overlap:.2f}): {sentence[:80]!r}"
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
