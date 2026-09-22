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


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]+|\d[\d.,%]*", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


# --------------------------------------------------------------------------
# Entailment screens (2026-09-22). Lexical overlap answers "could this text be
# the source of this sentence"; it cannot answer "does it say the same thing".
# Measured on 15 claim transformations: overlap alone admitted 9 of them, three
# scoring a PERFECT 1.00 — a claim that inverts the law scores higher than a
# faithful paraphrase, because dropping words only shrinks the numerator. A
# floor sweep settles that this is structural, not calibration: at a floor of
# 1.00 (which refuses all paraphrase) three false claims still pass.
#
# Three screens, each scoped to what it can decide:
#
#   quantity  — every number the claim asserts must appear in the cited TEXT.
#               Scoped to the whole chunk, because a clause number or an Act year
#               is a REFERENCE that lives elsewhere in the same chunk, while a
#               changed or invented figure is absent from it entirely.
#   polarity  — compared per PREDICATE the claim shares with its evidence, never
#               per sentence and never per word. "shall not exceed" reported as
#               "does exceed" is caught; "shall not exceed X" paraphrased as
#               "capped at X" is not a contradiction and must not be refused.
#   modality  — likewise per predicate: a permission reported as an obligation.
#
# Every one of those scopes was forced by measurement, and the numbers are in the
# tests. Whole-sentence polarity refused 25 of 54 real answers; per-word polarity
# refused 21; per-predicate refuses 2.
#
# Deliberately NOT screened: a dropped carve-out and a swapped party. Both need to
# know which words attach to which, and every lexical proxy measured for them
# refused more true answers than it caught false ones. They are pinned as KNOWN in
# `tests/test_assist_answer_integrity.py` so that closing one flips a test.
# --------------------------------------------------------------------------

# `not`/`no` are STOPWORDS, so polarity is invisible to `_content_words` and has
# to be read off the raw sentence. That is the whole bug in one line.
_NEGATION = frozenset(("not", "no", "never", "nor", "neither", "cannot", "without"))

# These scope over the whole clause from the SUBJECT position, unlike "not",
# which scopes over its verb. Bare "no" is deliberately absent — "no later than
# thirty days" does not negate what follows it.
_SUBJECT_NEGATION = frozenset(("neither", "nothing", "none", "nor"))
_PERMISSIVE = frozenset(("may", "can", "could", "might", "optional", "discretion"))
_OBLIGATORY = frozenset(("must", "shall", "will", "required", "requires", "obliged"))

# "renews automatically unless notice is given" and "will not renew if notice is
# given" say the SAME thing with opposite polarity on the same verb. Where either
# side carries a condition or an exception, a lexical polarity comparison is not
# evidence of a contradiction, so the screen declines to judge rather than
# refusing a correct answer — it falls back to the overlap check alone.
_CONDITIONAL = frozenset((
    "unless", "except", "if", "where", "provided", "otherwise", "subject",
    "notwithstanding", "save",
))

_NUMBER_WORDS = frozenset((
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "ninety", "hundred", "thousand", "million", "billion",
))
_UNIT_WORDS = frozenset((
    "lakh", "lakhs", "crore", "crores", "day", "days", "week", "weeks",
    "month", "months", "year", "years", "hour", "hours", "annum", "percent", "%",
))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z%]+|\d[\d.,]*", text.lower())


def _norm(w: str) -> str:
    """Singular/plural are the same quantity: "12 month period" supports "12 months"."""
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def _quantities(text: str) -> set[str]:
    """Number-bearing tokens: digits, units, and number WORDS that qualify a unit.

    "one" in "one another" is not a quantity; "one (1) year" is. Requiring a unit
    or a digit within the next two tokens is what separates them, and without it
    the screen refused real answers over the word "one".
    """
    ws = _words(text)
    out = set()
    for i, w in enumerate(ws):
        if w[0].isdigit():
            # "Clause 20.5" and "the Act, 1996" are REFERENCES, not quantities.
            if "." in w or (len(w) == 4 and w.isdigit() and w.startswith(("19", "20"))):
                continue
            out.add(_norm(w))
        elif w in _UNIT_WORDS or (w in _NUMBER_WORDS and any(
                x in _UNIT_WORDS or x[0].isdigit() for x in ws[i + 1:i + 3])):
            out.add(_norm(w))
    return out


# Negation reaches its verb THROUGH auxiliaries and copulas and nothing else:
# "is not allowed to undertake" negates "undertake", while "shall not exceed the
# total fees" does NOT negate "total". Allowing any word between the two refused
# 21 of 54 real answers; allowing none missed periphrastic negation entirely.
_CARRIES_NEGATION = frozenset((
    "allowed", "permitted", "entitled", "required", "able", "to", "be", "been",
    "is", "are", "was", "were", "do", "does", "did", "have",
    "has", "had", "will", "shall", "may", "can", "deemed", "considered",
))


def _verb_position(words: list[str], i: int) -> bool:
    """Is the token at `i` where a verb goes — right after a modal, an auxiliary or
    a negator?

    Polarity attaches to the PREDICATE. Comparing every shared word instead made
    "shall not exceed the total fees" look like a claim about a negated "total",
    and a clause-scoping "Neither party ... shall exceed" negate every word after
    it. This is the cheap stand-in for a parser, and it is the whole reason the
    screen can use subject-scope negation without refusing correct answers.
    """
    return i > 0 and (words[i - 1] in _CARRIES_NEGATION or words[i - 1] in _NEGATION
                      or words[i - 1] in _PERMISSIVE or words[i - 1] in _OBLIGATORY)


def _modal_at(words: list[str], i: int) -> str | None:
    """"may" or "must" for the verb at `i`, or None when nothing governs it.

    Scoped like `_negated`, and for the same reason: comparing sentence-level
    modality made "Either party MAY terminate on ninety days notice" contradict
    "Termination REQUIRES ninety days notice", which are the same rule. The
    permission is to terminate; the requirement is the notice.
    """
    for j in range(i - 1, max(-1, i - 4), -1):
        if words[j] in _PERMISSIVE:
            return "may"
        if words[j] in _OBLIGATORY:
            return "must"
        if words[j] not in _CARRIES_NEGATION and words[j] not in _NEGATION:
            return None
    return None


def _negated(words: list[str], i: int) -> bool:
    """Is the token at `i` inside a negation's scope?

    Two routes, because legal drafting negates in two places. "shall not exceed"
    and "is not allowed to undertake" negate through the verb chain; "NEITHER
    party's aggregate liability ... shall exceed" and "NOTHING in these Terms
    shall limit" negate from the SUBJECT, arbitrarily far to the left. The two
    say the same thing, and a screen reading only the first refuses a correct
    answer every time a contract uses the second — which they constantly do.
    """
    if any(w in _SUBJECT_NEGATION for w in words[:i]):
        return True
    for j in range(i - 1, max(-1, i - 4), -1):
        if words[j] in _NEGATION:
            return True
        if words[j] not in _CARRIES_NEGATION:
            return False
    return False


def _best_span(claim_words: set[str], chunk: str) -> str:
    """The SENTENCE of this chunk that best accounts for the claim.

    Per chunk, not across all of them: the union of everything cited is what let
    a claim borrow "may" from one chunk and "thirty days" from another and ground
    against neither. A reader following a citation lands on a sentence.
    """
    spans = [s for s in _SENTENCES.split(chunk) if s.strip()]
    if not spans:
        return ""
    return max(spans, key=lambda s: len(claim_words & _content_words(s)))


def _entailment_failure(sentence: str, claim_words: set[str],
                        cited_chunks: list[str]) -> str | None:
    """Why this claim is not entailed by its cited span(s), or None if it is.

    Both screens only ever REFUSE — they can turn an answer into a refusal and
    never the reverse, the direction F-4 permits (widening a fail-closed path,
    never narrowing one).
    """
    spans = [s for s in (_best_span(claim_words, c) for c in cited_chunks) if s]
    if not spans:
        return None

    # 1 — every quantity asserted must appear in the cited TEXT. A cap of 12
    # months reported as 24, or an invented figure, changes the only thing a
    # liability sentence is FOR. The Findings explainer already screens digits
    # this way; Ask simply never did.
    #
    # Scoped to the whole cited chunk rather than the aligned span, because a
    # clause number or an Act year ("Clause 20.5", "the Act, 1996") is a
    # REFERENCE, not a quantity, and lives elsewhere in the same chunk. A changed
    # or fabricated figure is absent from the chunk entirely, so the screen keeps
    # all four quantity mutations and stops refusing real citations.
    invented = _quantities(sentence) - set().union(
        *(_quantities(c) for c in cited_chunks))
    if invented:
        return (f"claim states a quantity its cited text does not "
                f"({', '.join(sorted(invented))}): {sentence[:80]!r}")

    # 2 — polarity, scoped to the PREDICATE the claim shares with its span.
    # Comparing whole-sentence polarity refused 25 of 54 real answers, because
    # paraphrasing "shall not exceed X" as "is capped at X" drops a negation
    # legitimately. What is never legitimate is asserting the same word the
    # evidence negates: "shall not exceed" reported as "does exceed".
    cw = _words(re.sub(r"^\s*(no|yes)\s*,\s*", "", sentence, flags=re.I))
    if set(cw) & _CONDITIONAL:
        return None
    for i, w in enumerate(cw):
        if w in _NEGATION or w in _STOPWORDS or len(w) < 4 or not _verb_position(cw, i):
            continue
        seen = agreed = False
        mood_seen = mood_agreed = False
        claim_mood = _modal_at(cw, i)
        for chunk in cited_chunks:
            for span in _SENTENCES.split(chunk):
                sw = _words(span)
                for j, x in enumerate(sw):
                    if x != w or not _verb_position(sw, j):
                        continue
                    seen = True
                    if _negated(sw, j) == _negated(cw, i):
                        agreed = True
                    span_mood = _modal_at(sw, j)
                    if claim_mood and span_mood:
                        mood_seen = True
                        if claim_mood == span_mood:
                            mood_agreed = True
        if seen and not agreed:
            return (f"claim reverses what its cited text says about "
                    f"{w!r}: {sentence[:80]!r}")
        if mood_seen and not mood_agreed:
            return (f"claim changes what its cited text requires of "
                    f"{w!r}: {sentence[:80]!r}")

    return None


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
            else:
                # Overlap says the cited text COULD be the source. These say it
                # says the same thing — see `_entailment_failure`.
                unentailed = _entailment_failure(
                    _MARKER.sub("", sentence), claim_words, cited_chunks)
                if unentailed:
                    failures.append(unentailed)
                    grounded = False
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
