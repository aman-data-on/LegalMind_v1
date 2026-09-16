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


# --------------------------------------------------------------------------
# The capability question (`AM-68` r1) — PROPOSED, disabled by default
# --------------------------------------------------------------------------
# "What can you help me with in LegalMind?" is not a legal question, and answering it
# from the Constitution is how the reported defect looked: three unrelated standards,
# because the POSITIONS fallback is unconditional and a document-less Ask has no
# primary route at all.
#
# The shape: a reference to the PRODUCT or to the assistant itself, plus a capability
# signal, and — the leg that does the real work — NO legal anchor. "Can you find the
# termination clause?" has the first two and is a document question; the third
# separates them. Deterministic, no model (`AM-68` r1).
_SELF_WORDS = frozenset({"legalmind", "legal mind", "you", "your", "yourself",
                         "tum", "tumhara", "aap", "aapka", "आप", "तुम"})
_CAPABILITY_WORDS = frozenset({
    "help", "helps", "capable", "capabilities", "capability", "features", "feature",
    "support", "supports", "able", "abilities", "purpose", "use", "uses", "usage",
    "work", "works", "offer", "offers", "provide", "provides", "assist",
    # "what can LegalMind DO?" — the plainest phrasing of the question, and the one
    # the first draft missed. Safe because a legal anchor already excludes
    # "can you find the termination clause?" and "what does our standard say?".
    "do", "does", "can", "could",
    # Hinglish: "kya kar sakta hai", "kaam", "madad", "istemaal"
    "kar", "sakta", "sakte", "sakti", "kaam", "madad", "istemaal", "faayda",
    "क्या", "मदद", "काम", "सकता", "सकते",
})
# A legal anchor means the question is about legal CONTENT, not about the product.
# Kept deliberately wide: a false negative here is a capability question answered the
# old way, which is today's behaviour; a false positive is a legal question diverted
# to a product answer, which is worse.
_LEGAL_ANCHOR_STEMS = ("clause", "contract", "agreement", "liabilit", "indemnit",
                       "terminat", "confidential", "warrant", "arbitrat", "jurisdict",
                       "notice", "renew", "payment", "breach", "sla", "nda", "msa",
                       "tos", "cap", "deviat", "finding", "standard", "constitution",
                       "polic", "statut", "act", "section", "obligat", "penalt",
                       "अनुबंध", "खंड", "धारा", "मानक", "नीति", "संविधान")


def is_capability_question(question: str) -> bool:
    """True when the question asks what the PRODUCT can do, not what the law says.

    `AM-68` is not approved, so nothing routes on this yet — `routing.plan` consults it
    only when the capability route is explicitly enabled. Shipping the classifier dark
    keeps it measurable and reviewable without changing a single answer.
    """
    tokens = _stems(question or "")
    if not tokens:
        return False
    if _hits(tokens, _LEGAL_ANCHOR_STEMS):
        return False
    self_ref = {i for i, t in enumerate(tokens) if t in _SELF_WORDS}
    capability = {i for i, t in enumerate(tokens) if t in _CAPABILITY_WORDS}
    return bool(self_ref) and bool(capability - self_ref)


# --------------------------------------------------------------------------
# The general-knowledge question — "what IS an NDA?"
# --------------------------------------------------------------------------
# Distinct from every other shape, and the distinction is the article. A question about
# a legal CONCEPT takes an indefinite or bare form — "what is an NDA", "explain force
# majeure", "indemnity ka matlab kya hai". A question about a PARTICULAR term takes a
# possessive or a deictic — "what is OUR notice period", "what does THIS agreement say".
# The first has no answer in any authorised source; the second does.
#
# Before this, the first fell through to the unconditional POSITIONS fallback and was
# answered with three Company Standards, as though the organization's positions defined
# what an NDA is. Measured live 2026-09-16: "What is an NDA?" returned NON-SOLICIT,
# GOVLAW and RESIDUALS.
_DEFINITIONAL = re.compile(
    r"\b(what\s+(is|are)|what\s+does\s+\w+\s+mean|explain|define|definition\s+of|"
    r"tell\s+me\s+about|meaning\s+of)\b"
    r"|\b(kya\s+(hai|hota|hoti|h)|matlab|samjhao|kya\s+cheez)\b"
    r"|(क्या\s+ह|मतलब|समझा)", re.IGNORECASE)

# A bare legal concept — the kind of thing a dictionary defines, not a clause.
_CONCEPT_WORDS = frozenset({
    "nda", "msa", "sla", "tos", "indemnity", "indemnification", "liability",
    "arbitration", "jurisdiction", "warranty", "confidentiality", "termination",
    "force", "majeure", "consideration", "novation", "assignment", "lien",
    "injunction", "damages", "breach", "contract", "agreement", "clause",
    "covenant", "waiver", "severability", "governing", "law", "tort", "privity",
})
# A possessive or deictic makes it a question about a PARTICULAR instrument, which the
# document or the positions can answer. Kept separate from `_ORG_PRONOUNS` because
# "this"/"that" are not organization references.
_PARTICULARISERS = frozenset({
    "our", "ours", "we", "us", "my", "company", "this", "that", "these", "those",
    "hamara", "hamare", "hamari", "humara", "humare", "humari", "hum",
    # NOT bare "is": romanized इस collides with the English verb, and including it
    # made "what IS an NDA?" a particular question. The same collision cost a
    # false follow-up detection earlier; the inflected forms are unambiguous.
    "isme", "ismein", "iska", "yeh", "ye", "uploaded", "attached",
    "हमारा", "हमारे", "हमारी", "इस", "यह", "ये",
})


# Words that carry the question's FORM rather than its subject, stripped before the
# concept test so "what is an NDA" reduces to {nda}.
_DEFINITION_FRAME = frozenset({
    "what", "is", "are", "does", "do", "mean", "means", "meaning", "explain", "define",
    "definition", "of", "tell", "me", "about", "a", "an", "the", "please", "in",
    "simple", "language", "terms", "words", "exactly",
    "kya", "hai", "hota", "hoti", "h", "matlab", "samjhao", "ka", "ki", "ke", "cheez",
    "क्या", "है", "मतलब", "समझाओ", "का", "की", "के",
})


def is_general_knowledge_question(question: str) -> bool:
    """True when the question asks what a legal CONCEPT means, in general.

    Deliberately narrow. A false positive sends a question about the organization's own
    position to a general explanation, which is the worse error, so anything carrying a
    possessive, a deictic or a statute reference is excluded.
    """
    text = question or ""
    if not _DEFINITIONAL.search(text):
        return False
    if is_statute_question(text) or is_capability_question(text):
        return False
    tokens = _stems(text)
    if any(t in _PARTICULARISERS for t in tokens):
        return False
    if _hits(tokens, _ORG_STEMS):
        return False
    # EVERY content word must be a legal concept, not merely one of them. That is what
    # separates "what is an NDA" (content: {nda}) and "explain force majeure" (content:
    # {force, majeure}) from "what is the termination notice period" (content:
    # {termination, notice, period}) — the last is a compound TERM of some instrument,
    # and the owner's 2026-09-09 ruling is that it is answered from the ratified
    # positions. A rule that merely looked for one concept word would have swallowed it.
    content = [t for t in tokens if t not in _DEFINITION_FRAME]
    return bool(content) and all(t in _CONCEPT_WORDS for t in content)


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
