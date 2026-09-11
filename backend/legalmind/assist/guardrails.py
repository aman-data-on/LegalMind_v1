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


# --------------------------------------------------------------------------
# Word normalisation — what "the same word" means on both sides of a comparison
# --------------------------------------------------------------------------
# `_content_words` feeds two grounding checks: the Ask answer's citation overlap
# (`verify_answer`, floor 0.5) and the Finding explanation's (floor 0.75). Both
# compare a generated sentence against its source material by SET MEMBERSHIP, so
# a word only counts as grounded when the two sides produce the identical token.
#
# Measured on the live explanation corpus (2026-09-11): of 63 rejected
# explanations, ~37 were rejected for "ungrounded words" that ARE in the source
# in another surface form — `leapswitch's` against `Leapswitch`, `one-year`
# against `one year`, `2,` against `2`, `ends`/`ending` against `end`,
# `specifies` against `specify`. The sentences were grounded; the comparison was
# not measuring it. That is a validation defect, not a model failure, and the
# fix is to normalise BOTH sides identically rather than to lower either floor —
# the floors are unchanged by this, and an invented word still grounds nowhere.
#
# Deliberately a small deterministic stemmer, not a dependency (rule 19) and not
# a model: `intent.py` already takes the same in-house approach, and a stemmer
# that changes between library versions would silently move a guardrail.
_TOKEN = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*|\d[\d.,%]*")
_SUFFIXES = ("ing", "edly", "ed", "es", "ly", "s")


def _stem(word: str) -> str:
    """One conservative surface form for a word. Short words are left alone."""
    if len(word) <= 3:
        return word
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    # `exclude`/`excludes`/`excluding` all meet at `exclud`.
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    # `specify`/`specifies` meet at `specifi`; `company`/`companies` at `compani`.
    if word.endswith("y"):
        word = word[:-1] + "i"
    # `running` -> `runn` -> `run`; never applied to a genuine double vowel.
    if len(word) >= 4 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]
    return word


def _normalise(token: str) -> set[str]:
    """Every form of one raw token that should count as the same word.

    A hyphenated compound contributes its parts AND its joined form, so
    `non-disclosure` meets `non disclosure` and `nondisclosure` alike; a number
    sheds trailing punctuation so `2,` meets `2`; a possessive sheds its `'s`.
    Nothing here invents a word the token did not contain.
    """
    token = token.strip("'\u2019-")
    if not token:
        return set()
    if token[0].isdigit():
        # Numbers are compared as written, minus trailing punctuation. A single
        # digit counts: it was dropped before, so a claim's `2,` could never meet
        # a source's `2`, and every digit read as an ungrounded word.
        return {t for t in [token.strip(".,%")] if t}
    for possessive in ("'s", "\u2019s"):
        if token.endswith(possessive):
            token = token[: -len(possessive)]
    parts = [p for p in token.replace("\u2019", "'").split("-") if len(p) > 2]
    forms = {_stem(p) for p in parts}
    if len(parts) > 1:
        forms.add(_stem("".join(parts)))
    return {f for f in forms if len(f) > 1}


# Stop words in their normalised form as well as their raw one: the tokens being
# filtered are normalised, so a raw-form list alone would stop matching them.
_STOPWORD_FORMS = frozenset(
    _STOPWORDS | {f for w in _STOPWORDS for f in _normalise(w)})


def normalised_forms(words) -> frozenset[str]:
    """The normalised forms of a vocabulary list — for callers that keep their
    own raw-word set and must compare it against `_content_words` output."""
    return frozenset(f for w in words for f in _normalise(w.lower()))


def _content_tokens(text: str) -> list[set[str]]:
    """The claim side of a grounding comparison: ONE entry per content word,
    holding every surface form that word may legitimately match.

    A flat set would count `non-disclosure` as three words (`non`,
    `disclosur`, `nondisclosur`) where the old raw comparison counted it as one,
    so a single unmatched compound could triple its own weight in the
    denominator — measured on the live corpus, that alone rejected five
    explanations the raw comparison had accepted. A word is grounded when ANY of
    its forms appears in the source, and it counts once either way.
    """
    tokens: list[set[str]] = []
    for raw in _TOKEN.findall(text.lower()):
        if raw in _STOPWORD_FORMS:
            continue
        forms = {f for f in _normalise(raw) if f not in _STOPWORD_FORMS}
        if forms:
            tokens.append(forms)
    return tokens


def grounded_fraction(claim: str, source_words: set[str],
                      ignore: frozenset[str] = frozenset()) -> float:
    """Share of the claim's content words present in `source_words`, counting
    each word once. 1.0 when the claim has no content word to check."""
    tokens = [t for t in _content_tokens(claim) if not (t & ignore)]
    if not tokens:
        return 1.0
    return sum(1 for t in tokens if t & source_words) / len(tokens)


def _content_words(text: str) -> set[str]:
    """The comparable content words of a text — stop words removed, each in the
    normalised form `_normalise` defines. Applied to BOTH sides of every
    grounding comparison, so the check stays symmetric."""
    out: set[str] = set()
    for raw in _TOKEN.findall(text.lower()):
        if raw in _STOPWORD_FORMS:
            continue
        for form in _normalise(raw):
            if form not in _STOPWORD_FORMS:
                out.add(form)
    return out


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
        cited_words = set().union(*(_content_words(c) for c in cited_chunks))
        overlap = grounded_fraction(_MARKER.sub("", sentence), cited_words)
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
