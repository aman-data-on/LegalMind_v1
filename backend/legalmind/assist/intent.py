"""Question-shape detection for the assist lane — deterministic, no model, no regex soup.

`AM-25` r4: the assist lane never answers "does this document meet our standard?"
— that belongs to the deterministic evaluator. The screen this replaces was one regex
(`complian[ct]`, `match(es)? our (standard|position)`) and, measured live on 2026-09-08,
it passed every natural phrasing of the question: "compare this document with our
approved legal position", "does this document comply with our standard position",
"what clauses are missing compared with our approved position". Each was then answered
generatively over document chunks and refused as "not found in the selected document" —
a false refusal of the manager's own question.

The shape of a comparison question, per the Constitution's own vocabulary (§24: Accepted /
Deviation; §3.2A: "aligns with the approved position", "identifies deviations"):

    an ORGANIZATION REFERENCE   our / company / approved / standard / position / policy /
                                constitution / baseline / playbook
    AND
    a COMPARISON SIGNAL         a verb (compare, comply, conform, align, meet, satisfy,
that belongs to the deterministic evaluator. The screen this replaces was one regex
                                (deviation, gap, missing, acceptable, unacceptable,
                                compliant, non-compliant, compliance, redline)

Both groups are matched on normalized word stems so "comply / complies / compliant /
compliance / non-compliance" and "deviate / deviation / deviates" collapse together. A
question with only one group is descriptive ("what are our payment obligations under
this contract?" names the organization but asks what the document SAYS) and is answered
from the document. `tests/test_assist_intent.py` pins the matrix both ways.
"""

from __future__ import annotations

import re

# Devanagari is matched alongside ASCII. Before this, `[a-z]+` tokenized
# "हमारे मानक से तुलना करें" ("compare with our standard") to the EMPTY list, so
# `is_comparison_question` was False and the evaluator's own question — the one
# `AM-25` r4 says is never answered generatively — went to the model instead.
# A safety screen that answers "no" for everything it cannot read is not a screen.
_WORD = re.compile(r"[a-z]+|[ऀ-ॿ]+")

# Stems, not words: prefix-matched against each normalized token.
# Exact matches — a prefix would let "use" and "were" through.
# Hindi first-person possessives are the exact equivalent of "our", and appear both
# romanized and in Devanagari in real questions ("hamare standard", "हमारे मानक").
_ORG_PRONOUNS = frozenset({
    "our", "ours", "us", "we",
    "hamara", "hamare", "hamari", "humara", "humare", "humari",
    "hum", "humein", "hamein",
    "हमारा", "हमारे", "हमारी", "हम", "हमें",
})
# Exact words, not stems: "follow-up" and "following our call" are not comparisons.
_VERB_WORDS = frozenset({"follow", "follows", "adhere", "adheres", "honour", "honor"})
_ORG_STEMS = ("compan", "approv", "standard", "position", "polic",
              "constitution", "baseline", "playbook", "template", "leapswitch", "cloudpe",
              # Hindi: मानक standard · नीति policy · संविधान constitution · कंपनी company
              "मानक", "नीति", "संविधान", "कंपनी")
_VERB_STEMS = ("compar", "against", "compl", "conform", "align", "meet", "meets",
               "satisf", "deviat", "match", "differ", "accept", "unaccept", "approv",
               "violat", "breach", "consistent", "inconsistent", "conflict",
               # Hindi: तुलना compare · अनुसार/अनुरूप according to · पालन comply ·
               # उल्लंघन violate · विपरीत contrary · मेल match
               "तुलना", "अनुसार", "अनुरूप", "पालन", "उल्लंघन", "विपरीत", "मेल")
_NOUN_STEMS = ("deviation", "gap", "missing", "acceptab", "unacceptab", "compliance",
               "compliant", "noncompliant", "redline", "attention", "modif", "risk")

# Romanized Hindi comparison is POSTPOSITIONAL — "X ke according", "X ke hisaab se",
# "X ke mutabik" — so it is matched as a BIGRAM, not as a bare stem. Matching
# "according" alone would misread the ordinary English "according to our agreement,
# what is the notice period?" (a document question) as a compliance verdict request.
_COMPARISON_BIGRAMS = frozenset({
    ("ke", "according"), ("ke", "hisaab"), ("ke", "hisab"), ("ke", "mutabik"),
    ("ke", "mutaabik"), ("ke", "anusaar"), ("ke", "anusar"), ("ke", "anuroop"),
    ("se", "alag"), ("ke", "khilaf"),
})

# Single romanized tokens that are unambiguously comparison signals on their own.
_COMPARISON_WORDS = frozenset({"tulna", "palan", "ullanghan", "anupalan"})

# Signing-readiness. `AM-25` r4 already forbids the assistant deciding whether a
# document meets the standard; "should we sign this?" asks for strictly more than
# that, so until Phase 3 gives it its own structured route it is treated as a
# comparison and handed to the evaluator — which answers with Findings rather than
# a yes/no, exactly what the question should get. Exact words: "sign" as a stem
# would swallow "significant" and "signatory".
_SIGNING_WORDS = frozenset({"sign", "signing", "हस्ताक्षर"})

# "approv" appears in both groups on purpose: "our approved position" is an organization
# reference; "can we approve this" is a comparison verb. One token cannot serve as both,
# so a question that only says "approved" once still needs a second signal.


def _stems(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("-", ""))


def _hits(tokens: list[str], stems: tuple[str, ...]) -> set[int]:
    return {i for i, tok in enumerate(tokens) if tok.startswith(stems)}


def _comparison_signals(tokens: list[str]) -> set[int]:
    """Indices of tokens that signal a comparison, in any supported script."""
    signal = _hits(tokens, _VERB_STEMS) | _hits(tokens, _NOUN_STEMS)
    signal |= {i for i, t in enumerate(tokens) if t in _VERB_WORDS}
    signal |= {i for i, t in enumerate(tokens) if t in _COMPARISON_WORDS}
    signal |= {i for i, t in enumerate(tokens) if t in _SIGNING_WORDS}
    # Postpositional bigrams: the second token carries the signal, so "ke according"
    # marks the index of "according".
    signal |= {i + 1 for i, t in enumerate(tokens[:-1])
               if (t, tokens[i + 1]) in _COMPARISON_BIGRAMS}
    return signal


def is_comparison_question(question: str) -> bool:
    """True when the question asks how the document stands against the organization's
    position — the evaluator's question, never the model's."""
    tokens = _stems(question or "")
    org = _hits(tokens, _ORG_STEMS)
    org |= {i for i, t in enumerate(tokens) if t in _ORG_PRONOUNS}
    signal = _comparison_signals(tokens)
    # A signal token that is NOT itself an organization token is required: "our
    # approved position" is a position LOOKUP (Domain A), not a comparison, even
    # though "approved" is also a verb stem. "match our approved position" has one.
    return bool(org) and bool(signal - org)


def mentions_organization(question: str) -> bool:
    """True when the question refers to the organization's own position — "our
    standard", "company policy", "the approved position", "Leapswitch's template".
    The Domain A candidate signal; authorization decides whether it is honoured."""
    tokens = _stems(question or "")
    return bool(_hits(tokens, _ORG_STEMS)
                or {i for i, t in enumerate(tokens) if t in _ORG_PRONOUNS})


_STATUTE = re.compile(
    r"\b(section|sec\.?|s\.)\s*\d+[a-z]?\b|\b(act|statute|statutory|rules?,?\s*\d{4}|"
    r"regulation|ordinance|adhiniyam|ipc|crpc|dpdp|cert-?in|it act|contract act|"
    r"companies act|negotiable instruments|evidence act|penal code)\b",
    re.IGNORECASE)


def is_statute_question(question: str) -> bool:
    """True when the question asks about the law itself — a section number, an Act,
    a set of Rules. The Domain C candidate signal."""
    return bool(_STATUTE.search(question or ""))


# --------------------------------------------------------------------------
# Verdict screen for GENERATED text (2026-09-09) — narrower than the question router
# --------------------------------------------------------------------------
# `is_comparison_question` routes QUESTIONS, and is deliberately wide: "does this
# comply with Leapswitch's template?" must reach the evaluator. Reused on an ANSWER it
# over-fires: a party name ("Leapswitch") is an organization token and "breach" is a
# comparison stem, so the grounded, verified, purely descriptive sentence "Leapswitch
# may terminate if the breach is not cured within thirty days [3]" was thrown away as
# a compliance verdict (measured live, 2026-09-09 — the answer to the owner's own
# question). A VERDICT is a statement about the document's standing against the
# organization's POSITION: it needs a reference to that position (standard, policy,
# approved position, constitution, baseline, playbook, template — never a mere party
# name or pronoun) and a compliance signal (comply, conform, align, meet, satisfy,
# deviate, match, acceptable, violate, consistent). "Breach" is a document word and
# is not a signal here. Real verdicts — "this clause complies with our approved
# standard", "the cap deviates from the company's position" — are still caught.
_POSITION_STEMS = ("standard", "position", "polic", "approv", "constitution",
                   "baseline", "playbook", "template",
                   "मानक", "नीति", "संविधान")
_VERDICT_STEMS = ("compl", "conform", "align", "meet", "meets", "satisf", "deviat",
                  "match", "accept", "unaccept", "violat", "consistent", "inconsistent",
                  "noncompliant", "compliant", "compliance",
                  "अनुसार", "अनुरूप", "पालन", "उल्लंघन", "स्वीकार्य", "विपरीत")
# Romanized verdict vocabulary. "sahi"/"theek" (correct/fine) and "alag" (different)
# are how a Hinglish verdict is actually phrased — "yeh clause hamari policy ke
# hisaab se sahi hai" — and none of the English stems above touch them.
_VERDICT_WORDS = frozenset({"sahi", "theek", "thik", "alag", "galat", "swikarya",
                            "anurup", "palan", "ullanghan"})


def is_verdict_statement(text: str) -> bool:
    """True when generated text states how the document stands against the
    organization's position — the sentence the assistant may never utter
    (`AM-25` r1/r4). Mechanical, outside the model (`AM-28` r2)."""
    tokens = _stems(text or "")
    position = _hits(tokens, _POSITION_STEMS)
    signal = _hits(tokens, _VERDICT_STEMS)
    signal |= {i for i, t in enumerate(tokens) if t in _VERDICT_WORDS}
    signal |= {i + 1 for i, t in enumerate(tokens[:-1])
               if (t, tokens[i + 1]) in _COMPARISON_BIGRAMS}
    return bool(position) and bool(signal - position)


# --------------------------------------------------------------------------
# Follow-up detection (2026-09-10) — the deterministic half of conversation memory
# --------------------------------------------------------------------------
# "What about clause 7?", "what does that mean?", "and the penalty?" carry no content of
# their own: their meaning is the previous question's. `service.ask` resolves such a
# question by expanding retrieval with the requester's own earlier questions and
# passing those questions — never an earlier ANSWER (`AM-30` t2) — as labelled context.
# No model rewrites anything: the test is a stop-word count and a small anaphora list,
# so the same question always resolves the same way and the record can say why.
_ANAPHORA = frozenset({"this", "that", "it", "its", "those", "these", "same", "previous",
                       "above", "earlier", "there", "then", "latter", "former",
                       # Hinglish demonstratives — "isko samjhao", "ismein kya hai",
                       # "yeh sahi hai?". Without these a Hinglish follow-up carried
                       # no anaphora, so no prior question widened its retrieval and
                       # it went to the index cold.
                       # NOT the bare forms "is", "us", "use": romanized इस/उस/उसे
                       # collide with the English verb, pronoun and verb respectively,
                       # and "What IS the notice period in this agreement?" became a
                       # follow-up. The inflected forms carry the same meaning and are
                       # unambiguous, so the bare ones are simply not worth their cost.
                       "isko", "ismein", "isme", "iska", "iski", "ise",
                       "usko", "usme", "usmein", "uska", "uski",
                       "yeh", "ye", "woh", "wo", "vah", "yah", "upar", "uper",
                       "इसको", "इसमें", "इसका", "इसकी", "इसे", "उसको", "उसमें",
                       "उसका", "यह", "ये", "वह", "वो", "ऊपर", "पिछला", "पिछले"})
_OPENERS = frozenset({"and", "also", "but", "so", "plus"})
_STOP = frozenset({
    "what", "about", "how", "is", "are", "the", "a", "an", "of", "in", "on", "for", "to",
    "does", "do", "did", "or", "with", "mean", "means", "say", "says", "said", "happen",
    "happens", "after", "before", "clause", "section", "article", "please", "tell", "me",
    "explain", "more", "who", "which", "when", "where", "why", "can", "could", "would",
    "should", "be", "was", "were", "has", "have", "had", "any", "other", "again", "under",
    "if", "into", "detail", "details", "elaborate", "part", "point", "one", "much",
    "many", "long", "exactly", "specifically", "number", "no",
})


# Demonstratives that can introduce a noun rather than point back — "this Agreement",
# "yeh agreement". Anything here is exempted from the anaphora rule when a document
# noun follows it, in every script.
_DEMONSTRATIVES = frozenset({"this", "that", "these", "those",
                             "yeh", "ye", "woh", "wo", "is", "us", "yah", "vah",
                             "यह", "ये", "वह", "वो", "इस", "उस"})

# "this Agreement", "that document": a determiner in front of the thing being asked
# about, not a reference to an earlier turn.
_DETERMINED = frozenset({"agreement", "contract", "document", "clause", "section",
                         "msa", "nda", "sla", "policy", "version", "act", "provision",
                         # Hindi nouns that take the same determiners
                         "samjhauta", "dastavez", "anubandh",
                         "समझौता", "दस्तावेज", "अनुबंध", "खंड", "धारा"})


def is_follow_up(question: str) -> bool:
    """True when a question cannot stand alone: it points back ("that", "the previous
    clause"), opens as a continuation ("and …"), or has at most one content word once
    stop words and clause references are removed ("what about clause 7?")."""
    tokens = _stems(question or "")
    if not tokens:
        return False
    if tokens[0] in _OPENERS:
        return True
    for i, tok in enumerate(tokens):
        if tok in _ANAPHORA and not (tok in _DEMONSTRATIVES
                                     and i + 1 < len(tokens)
                                     and tokens[i + 1] in _DETERMINED):
            return True
    # ponytail: a one-content-word standalone ("who are the parties?") also counts as
    # a follow-up and gets the previous question added to its retrieval. Harmless —
    # the current question still drives generation — but a real intent model is the
    # upgrade if that ever measurably dilutes the top-k.
    return len([t for t in tokens if t not in _STOP and t not in _ANAPHORA]) <= 1
