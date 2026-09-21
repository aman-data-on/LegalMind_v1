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
from dataclasses import dataclass

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
# Every first-person form, either case — defined below the two case sets it unions, so
# the vocabulary has one home. `mentions_organization` wants them all: a question saying
# "we" or "our" may be about the organization's position and is a Domain A CANDIDATE.
# `is_comparison_question` needs the cases apart, which is what the two sets are for.
# Exact words, not stems: "follow-up" and "following our call" are not comparisons.
_VERB_WORDS = frozenset({"follow", "follows", "adhere", "adheres", "honour", "honor"})
_ORG_STEMS = ("compan", "approv", "standard", "position", "polic",
              "constitution", "baseline", "playbook", "template", "leapswitch", "cloudpe",
              # Hindi: मानक standard · नीति policy · संविधान constitution · कंपनी company
              "मानक", "नीति", "संविधान", "कंपनी")
_VERB_STEMS = ("compar", "against", "conform", "align", "meet", "meets",
               "satisf", "deviat", "match", "differ", "accept", "unaccept", "approv",
               "violat", "breach", "consistent", "inconsistent", "conflict",
               # Hindi: तुलना compare · अनुसार/अनुरूप according to · पालन comply ·
               # उल्लंघन violate · विपरीत contrary · मेल match
               "तुलना", "अनुसार", "अनुरूप", "पालन", "उल्लंघन", "विपरीत", "मेल")
# The comply family as EXACT words, not the stem "compl" it used to be matched by.
# Measured 2026-09-16 on the ratified set: "compl" matched "complete", so "why do we
# have to COMPLETE identity verification?" carried a comparison signal. It would have
# matched "complex", "complicated" and "complimentary" too.
_COMPLY_WORDS = frozenset({"comply", "complies", "complied", "complying"})
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

# --------------------------------------------------------------------------
# Why this is a RELATION and not two bags of words (rewritten 2026-09-16)
# --------------------------------------------------------------------------
# The screen used to be: an organization word anywhere AND a comparison word anywhere.
# That is co-occurrence, not intent, and measured on the ratified 77-question set it
# misrouted SEVEN of 64 answerable questions to the evaluator — a user asking "how much
# time do we get to fix a breach before the provider can terminate?" was answered with
# "run a Review" instead of the cure period. Every one fired on an unrelated pair:
#
#     we ... breach          a contract EVENT, not a comparison
#     we ... complete        the stem "compl" reaching "complete"
#     our marketing emails ... meet ... acceptable
#     a security standard ... satisfying
#     a company ... data breach
#     sign contracts on behalf of a company
#
# What actually distinguishes the evaluator's question is that the comparison verb takes
# THE ORGANIZATION'S POSITION as its object: "comply with OUR APPROVED STANDARD", "match
# OUR STANDARD POSITION", "deviate from THE COMPANY STANDARD". So the screen now asks for
# a position REFERENCE — a position noun qualified as the organization's own — rather than
# for any word from an organization-flavoured list. Three shapes route to the evaluator:
#
#   (A) COMPARISON AGAINST OUR POSITION   a position reference + a comparison signal
#   (B) SIGNING READINESS                 first-person subject + an acceptance word +
#                                         a reference to the document itself
#   (C) AN UNAMBIGUOUS COMPARISON VERB    "compare", "comply", "deviate", "तुलना" — words
#                                         with no other meaning in this domain
#
# Case is what separates (B) from the false positives. "OUR marketing emails" is a
# POSSESSIVE determiner: it possesses the noun after it, and that noun is not a position.
# "acceptable to US" and "should WE sign" are nominative/objective: the first person is
# the party deliberating. The old set collapsed both into one bag of pronouns.
_FIRST_PERSON_POSSESSIVE = frozenset({
    "our", "ours",
    "hamara", "hamare", "hamari", "humara", "humare", "humari",
    "हमारा", "हमारे", "हमारी",
})
_FIRST_PERSON_SUBJECT = frozenset({
    "we", "us",
    "hum", "humein", "hamein",
    "हम", "हमें",
})
_ORG_PRONOUNS = _FIRST_PERSON_POSSESSIVE | _FIRST_PERSON_SUBJECT

# Who is DELIBERATING, which is not the same question as whose position it is — so this
# is its own set rather than a widening of the one above. "Should I approve this?" is a
# signing question; "help me" and "show me" are not, which is why the dative "me" is
# absent. Widening `_ORG_PRONOUNS` instead made `mentions_organization` fire on "what
# can you help me with?", routing a capability question at the organization's positions
# (caught by test_assist_capability_route on 2026-09-16).
_DELIBERATING_SUBJECT = _FIRST_PERSON_SUBJECT | {"i"}

# The nouns that can BE a position. "standard" is here; "company" and "approved" are not
# — they qualify a position, they are not one, which is why "a security standard" and
# "a company" no longer count as references to ours.
_POSITION_NOUNS = ("standard", "position", "polic", "constitution", "baseline",
                   "playbook", "template", "मानक", "नीति", "संविधान")
# What marks a position noun as OURS rather than anyone's, besides a first-person
# possessive: the organization, or the fact that we approved it.
_POSITION_QUALIFIERS = ("compan", "approv", "leapswitch", "cloudpe", "कंपनी")
# How far before the noun a qualifier may sit. Three covers a full English determiner +
# adjective stack — "our approved legal position" — and Hindi/Hinglish put the possessive
# adjacent. It is a noun-phrase span, not a score to tune: widening it would let a
# qualifier from a different phrase reach across, which is the defect being fixed.
_QUALIFIER_SPAN = 3

# Verbs with no non-comparison reading in this domain. These need no object to be a
# comparison request: "please compare and tell me what is acceptable for us" names no
# position and is still the evaluator's question.
_UNAMBIGUOUS_STEMS = ("compar", "deviat", "conform", "redline", "noncompliant",
                      "तुलना")
_UNAMBIGUOUS_WORDS = frozenset({"tulna", "anupalan"}) | _COMPLY_WORDS

# (B): deciding whether to ENTER the document. `AM-25` r4 already forbids the assistant
# deciding whether a document meets the standard; "should we sign this?" asks for
# strictly more, so it goes to the evaluator, which answers with Findings rather than a
# yes/no. Exact words: "sign" as a stem would swallow "significant" and "signatory".
_ACCEPTANCE_WORDS = frozenset({
    "sign", "signing", "accept", "accepts", "accepted", "acceptable", "unacceptable",
    "approve", "approves", "agree", "chahiye", "हस्ताक्षर", "swikar",
})
# ... and it must be THIS document being signed, not signature rules in the abstract.
# Without this leg, "what happens if we do not accept delivery?" is a signing question.
_DOCUMENT_WORDS = frozenset({
    "this", "these", "that", "those", "it", "contract", "contracts", "agreement",
    "agreements", "document", "clause", "nda", "msa", "tos", "sla", "deal",
    "yeh", "yah", "isko", "ismein", "isme", "iska", "ise", "यह", "इस", "इसे",
})


def _stems(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("-", ""))


def _hits(tokens: list[str], stems: tuple[str, ...]) -> set[int]:
    return {i for i, tok in enumerate(tokens) if tok.startswith(stems)}


def _comparison_signals(tokens: list[str]) -> set[int]:
    """Indices of tokens that signal a comparison, in any supported script."""
    signal = _hits(tokens, _VERB_STEMS) | _hits(tokens, _NOUN_STEMS)
    signal |= {i for i, t in enumerate(tokens)
               if t in _VERB_WORDS or t in _COMPARISON_WORDS or t in _COMPLY_WORDS}
    # Postpositional bigrams: the second token carries the signal, so "ke according"
    # marks the index of "according".
    signal |= {i + 1 for i, t in enumerate(tokens[:-1])
               if (t, tokens[i + 1]) in _COMPARISON_BIGRAMS}
    return signal


def _position_reference(tokens: list[str]) -> set[int]:
    """Indices of every token forming a reference to THE ORGANIZATION'S OWN position.

    A position noun qualified, within `_QUALIFIER_SPAN` tokens before it, by a
    first-person possessive or by the organization itself. Returns the whole phrase —
    qualifier through noun — so a caller can require a comparison signal from OUTSIDE
    it: "what is our approved position on X?" is a position LOOKUP, and its only
    comparison-flavoured token ("approved") is part of the reference itself.
    """
    reference: set[int] = set()
    for noun in _hits(tokens, _POSITION_NOUNS):
        for i in range(max(0, noun - _QUALIFIER_SPAN), noun):
            if tokens[i] in _FIRST_PERSON_POSSESSIVE \
                    or tokens[i].startswith(_POSITION_QUALIFIERS):
                reference |= set(range(i, noun + 1))
                break
    return reference


def is_comparison_question(question: str) -> bool:
    """True when the question asks how the document stands against the organization's
    position — the evaluator's question, never the model's.

    Three shapes, any one of which routes (see the note above `_FIRST_PERSON_POSSESSIVE`
    for why this is a relation between the two halves and not the co-occurrence test it
    replaced).
    """
    tokens = _stems(question or "")
    if not tokens:
        return False
    present = set(tokens)

    # (C) A verb that means nothing else here. No object required.
    if _hits(tokens, _UNAMBIGUOUS_STEMS) or present & _UNAMBIGUOUS_WORDS:
        return True

    # (A) A comparison signal bearing on OUR position — the signal must come from
    # outside the reference, or "our approved position" would compare with itself.
    reference = _position_reference(tokens)
    if reference and (_comparison_signals(tokens) - reference):
        return True

    # (B) Deciding whether to sign THIS document. All three legs, or "what happens if
    # we do not accept delivery?" and "who may sign on behalf of a company?" route here.
    return bool(present & _DELIBERATING_SUBJECT
                and present & _ACCEPTANCE_WORDS
                and present & _DOCUMENT_WORDS)


def mentions_organization(question: str) -> bool:
    """True when the question refers to the organization's own position — "our
    standard", "company policy", "the approved position", "Leapswitch's template".
    The Domain A candidate signal; authorization decides whether it is honoured."""
    tokens = _stems(question or "")
    return bool(_hits(tokens, _ORG_STEMS)
                or {i for i, t in enumerate(tokens) if t in _ORG_PRONOUNS})


# --------------------------------------------------------------------------
# GENERAL LAW — the Domain C candidate signal (rebuilt 2026-09-21)
# --------------------------------------------------------------------------
# This was one flat regex: a section number, or any of a dozen statute words, anywhere
# in the question. That is the same co-occurrence test `is_comparison_question` was
# rebuilt away from on 2026-09-16, and it failed the same two ways.
#
# It fired on words that are not instruments. `\bact\b` matches the English VERB, so
# "the commissioned setup is not what we expected — how quickly must we act?" was a
# question about the law (measured on the ratified set, 2026-09-21).
#
# And it missed almost everything, because it required the question to NAME the
# instrument and a reader does not: 2 of the 23 statute questions matched. The other 21
# were held to `require_semantic` in the fall-through, so Domain C stayed silent on
# eight whose answering section was already in the lexical top six.
#
# GENERAL LAW means the reader wants a rule or a source, NOT an opinion on a particular
# piece of paper. So it is a relation, not a vocabulary:
#
#   (A) NAMES AN INSTRUMENT         a section number, a known Act, or "the Act" — an
#                                   explicit source reference, which wins outright
#   (B) ASKS FOR THE GENERAL RULE   jurisdiction framing or a rule-seeking question
#                                   shape, AND no target of its own to be measured
#                                   against — no document, no position
#
# (B)'s negative half is the whole safety property. `require_semantic` keeps 44 of the
# 54 contract questions out of the statute corpus, and this flag drops it, so a deal
# question that borrows statutory vocabulary must not reach (B).
# Instrument TYPES, taken from the corpus's own official titles: 13 of the 17 are an
# "Act", 3 "Rules", and one is the CERT-In "Directions" — which is why a question
# about "the cyber security directions" names an instrument as squarely as one about
# "the IT Act" does.
_INSTRUMENT_NOUNS = ("statute", "statutor", "adhiniyam", "ordinance", "regulation",
                     "direction")
# Short names people type for the Acts in the corpus. `statutes.expand_aliases` maps
# them to official-title words for the title match; here their presence IS the
# instrument reference, so the two uses share one table rather than two drifting ones.
ACT_ALIASES = {
    "dpdp": "digital personal data protection",
    "dpdpa": "digital personal data protection",
    "it act": "information technology act",
    "ni act": "negotiable instruments act",
    "cpc": "code of civil procedure",
    "bsa": "bharatiya sakshya adhiniyam",
    "cgst": "central goods and services tax",
    "igst": "integrated goods and services tax",
    "cert-in": "cert-in",
}
# Tokens that, standing next to "act"/"rules", make it the name of an instrument
# rather than a verb or an ordinary noun: a determiner, or a word from an Act's name.
_INSTRUMENT_DETERMINERS = frozenset({"the", "this", "that", "said", "an", "a"})
_ACT_NAME_TOKENS = frozenset(
    tok for phrase in (*ACT_ALIASES, *ACT_ALIASES.values()) for tok in phrase.split()
) | frozenset({"companies", "contract", "evidence", "penal", "ipc", "crpc",
               "information", "technology", "negotiable", "instruments", "arbitration",
               "copyright", "income", "tax"})
_SECTION_REFERENCE = re.compile(r"\b(?:section|sec\.?|s\.)\s*\d+[a-z]?\b|"
                                r"\b(?:act|rules)\s*,?\s*\d{4}\b", re.IGNORECASE)

# Jurisdiction framing: the reader is asking what the law of a place provides.
_JURISDICTION = re.compile(
    r"\b(?:in india|indian law|under indian law|law in india|under india)\b"
    # "India's DATA PROTECTION law" — the qualifier is a phrase, not one word.
    r"|\bindia'?s\b[^?]{0,40}\blaw\b",
    re.IGNORECASE)
# Rule-seeking SHAPES, not legal vocabulary. "enforceable" and "liable" are ordinary
# deal words and are deliberately absent: what marks a general-law question is that it
# asks for the rule ("what does the law say", "is it lawful to"), not that it uses a
# word a lawyer also uses.
_RULE_FRAMING = re.compile(
    r"\bwhat (?:does|do) (?:the |indian )?(?:law|act|statute|rules?) "
    r"(?:say|provide|require|state)\b"
    r"|\bwhat (?:is|are) the legal (?:rule|position|requirement|standard)s?\b"
    r"|\b(?:is|are) it (?:legal|lawful|permissible)\b"
    r"|\bunder (?:the )?law\b|\bby law\b|\blegally\b"
    r"|\bvalidly\b"                       # "who can VALIDLY sign" — a capacity question
    r"|\b(?:is|are|can|may)\b[^?]{0,60}?\b(?:valid|void|voidable|unlawful|illegal)\b",
    re.IGNORECASE)

# The reader's OWN paper. A document NOUN carrying a DEFINITE, demonstrative or
# possessive determiner — "this agreement", "the clause", "my document". The
# determiner is the discrimination that matters: "a contract is broken" is the general
# concept and routes to the law; "the contract" is the one on the desk and does not.
_DOCUMENT_NOUNS = ("contract", "agreement", "document", "clause", "msa", "nda", "tos",
                   "sla", "deal", "annexure", "schedule", "addendum", "amendment")

# A LEGAL ACTOR: who the rule binds, named in the abstract. A general-law question
# asks what "a company", "a platform", "an intermediary" must do; a deal question asks
# what WE must do, or what THE provider — this one, on this paper — committed to. The
# determiner carries the distinction, and it was measured rather than assumed:
# admitting a definite commercial actor ("the provider") took recall to 0.889 and put
# FOUR document questions into the statute lane, two of them must-refuse controls.
_LEGAL_ACTORS = (r"company|companies|platform|platforms|organisation|organization|"
                 r"provider|providers|intermediary|intermediaries|person|persons|"
                 r"party|parties|board|body corporate|data fiduciary|fiduciary")
_LEGAL_ACTOR = re.compile(
    # indefinite, with up to two adjectives: "an online platform", "a hosting
    # intermediary", "a Significant Data Fiduciary"
    rf"\b(?:a|an|any|every|each)\s+(?:\w+\s+){{0,2}}(?:{_LEGAL_ACTORS})\b"
    # A bare plural is indefinite by itself: "what must cloud and VPS PROVIDERS keep".
    # "parties" is NOT admitted here: in a deal question it means the counterparties,
    # and "who are the parties?" is a document question (caught by the routing suite,
    # not by the 91-case matrix — the phrasing is not in the dataset).
    r"|\b(?:companies|platforms|providers|intermediaries)\b"
    # ...and the narrow definite case: a party named by its ROLE IN A LEGAL RELATION,
    # which a deal question does not use. "the provider" is commercial and excluded;
    # "the injured party" is not.
    r"|\b(?:the|an?)\s+(?:injured|innocent|aggrieved|affected|defaulting|promisor|"
    r"promisee|surety)\s+(?:party|person|parties)\b"
    r"|\bthe\s+board\s+(?:of\s+directors\s+)?(?:need|needs|must|may|shall|approve)"
    r"|\bthe\s+(?:promisor|promisee|surety)\b",
    re.IGNORECASE)
# First person is the plainest statement that the question is about the asker's own
# situation, and it needs no noun to be one: "if a third party sues the provider
# because of something OUR users hosted" is a deal question with no document noun in
# it. Measured on the 91-case matrix: present in 42 of the 64 document questions and
# in NONE of the 27 general-law ones. It is what makes the wider actor forms safe.
_FIRST_PERSON = _ORG_PRONOUNS | frozenset({"i", "me", "my", "mine"})
_DEFINITE_DETERMINERS = frozenset({"the", "this", "these", "that", "those", "my",
                                   "its"}) | _FIRST_PERSON_POSSESSIVE

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


def _instrument_reference(question: str, tokens: list[str]) -> bool:
    """(A) — the question names a source: a section, a known Act, or "the Act"."""
    if _SECTION_REFERENCE.search(question):
        return True
    if _hits(tokens, _INSTRUMENT_NOUNS):
        return True
    lowered = f" {question.lower()} "
    if any(f" {short} " in lowered for short in ACT_ALIASES):
        return True
    # "act" and "rules" are an instrument only next to a determiner or an Act's name —
    # never the bare verb in "how quickly must we act".
    for i, token in enumerate(tokens):
        if token not in ("act", "acts", "rules"):
            continue
        neighbours = tokens[max(0, i - 2):i] + tokens[i + 1:i + 2]
        if any(n in _INSTRUMENT_DETERMINERS or n in _ACT_NAME_TOKENS
               for n in neighbours):
            return True
    return False


def _document_target(tokens: list[str]) -> bool:
    """A document noun carrying a definite, demonstrative or possessive determiner —
    the piece of paper in front of the reader, as opposed to the general concept."""
    for noun in _hits(tokens, _DOCUMENT_NOUNS):
        for i in range(max(0, noun - _QUALIFIER_SPAN), noun):
            if tokens[i] in _DEFINITE_DETERMINERS:
                return True
    return False


@dataclass(frozen=True)
class LegalQuestionSignals:
    """The deterministic signals behind a GENERAL LAW routing decision, and why.

    Recorded so a route can be explained after the fact. Never shown to a reader.
    """
    names_instrument: bool
    jurisdiction: bool
    rule_framing: bool
    legal_actor: bool
    document_target: bool
    position_target: bool
    first_person: bool

    @property
    def general_law(self) -> bool:
        # (A) An explicit source reference wins outright: "what does section 43A say
        # about our liability?" names the Act, and that is the source to answer from.
        if self.names_instrument:
            return True
        # (B) Otherwise the question must ask for the general rule — by jurisdiction,
        # by its framing, or by naming in the abstract who the rule binds — AND have
        # nothing of its own to be measured against. Conflicting signals keep the
        # conservative path, where `require_semantic` and the gate decide.
        if self.document_target or self.position_target or self.first_person:
            return False
        return self.jurisdiction or self.rule_framing or self.legal_actor

    @property
    def because(self) -> tuple[str, ...]:
        """The signals that fired, for the routing log."""
        named = (("names_instrument", self.names_instrument),
                 ("jurisdiction", self.jurisdiction),
                 ("rule_framing", self.rule_framing),
                 ("legal_actor", self.legal_actor),
                 ("document_target", self.document_target),
                 ("position_target", self.position_target),
                 ("first_person", self.first_person))
        return tuple(name for name, fired in named if fired)


def legal_question_signals(question: str) -> LegalQuestionSignals:
    """Score a question against the GENERAL LAW signals. Deterministic, no model."""
    text = question or ""
    tokens = _stems(text)
    return LegalQuestionSignals(
        names_instrument=_instrument_reference(text, tokens),
        jurisdiction=bool(_JURISDICTION.search(text)),
        rule_framing=bool(_RULE_FRAMING.search(text)),
        legal_actor=bool(_LEGAL_ACTOR.search(text)),
        document_target=_document_target(tokens),
        position_target=bool(_position_reference(tokens)),
        first_person=bool(set(tokens) & _FIRST_PERSON),
    )


def is_statute_question(question: str) -> bool:
    """The Domain C candidate signal — `legal_question_signals(...).general_law`."""
    return legal_question_signals(question).general_law


# --------------------------------------------------------------------------
# Verdict screen for GENERATED text (2026-09-09) — narrower than the question router
# --------------------------------------------------------------------------
# `is_comparison_question` routes QUESTIONS; this screens ANSWERS, and the two must not
# be the same test. Reused on an answer the router over-fired: a party name
# ("Leapswitch") is an organization token and "breach" is a comparison stem, so the
# grounded, verified, purely descriptive sentence "Leapswitch may terminate if the
# breach is not cured within thirty days [3]" was thrown away as a compliance verdict
# (measured live, 2026-09-09 — the answer to the owner's own question). A VERDICT is a
# statement about the document's standing against the organization's POSITION: it needs
# a reference to that position (standard, policy, approved position, constitution,
# baseline, playbook, template — never a mere party name or pronoun) and a compliance
# signal. "Breach" is a document word and is not a signal here. Real verdicts — "this
# clause complies with our approved standard", "the cap deviates from the company's
# position" — are still caught.
#
# This note used to add that the router is "deliberately wide" because over-routing a
# QUESTION is harmless. Measured 2026-09-16, it was not: the router sent 7 of 64
# answerable questions to the evaluator, so "how much time do we get to fix a breach?"
# was answered with "run a Review". The router now requires the same relation this
# screen already required — a position REFERENCE, not a position-flavoured word — and
# the two are no longer wide and narrow versions of one test but the same idea applied
# on each side. See `_FIRST_PERSON_POSSESSIVE` above.
#
# `_VERDICT_STEMS` below still carries the stem "compl", which also matches "complete"
# and "complex". Left as it is deliberately: over-firing HERE withholds an answer,
# which fails closed, whereas over-firing in the router hands the user the wrong
# product. Narrowing a screen on generated text is its own change with its own
# faithfulness measurement, not a line in a routing fix.
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
