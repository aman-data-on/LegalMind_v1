"""Social turns in Ask — greetings, thanks, goodbyes, acknowledgements (`AM-109`).

    kind = conversational.kind(question)          # None, or a Social kind
    core = conversational.strip_social(question)  # "hi, what is X?" -> "What is X?"

Before this, "hi" went through retrieval and came back as "Information not found in the
organization's approved positions or in the approved statute corpus", and mid-chat
"thanks" or "ok" was read as a one-word follow-up and re-answered the previous legal
question. A turn that is ONLY social is recognised here, deterministically and without a
model, and answered with fixed wording that states no legal content — so, like the
capability route (`AM-68`), it is rendered, never generated, and reaches no source. A
social phrase around a real question is stripped so the question is answered as asked.
"""
from __future__ import annotations

import re
from enum import Enum


class Social(str, Enum):
    GREETING = "GREETING"
    THANKS = "THANKS"
    FAREWELL = "FAREWELL"
    ACK = "ACK"
    #: "who are you", "help" — answered by the capability manifest (`AM-68`).
    IDENTITY = "IDENTITY"
    #: "what about it?" as the first turn, with no document — nothing to refer to.
    UNCLEAR = "UNCLEAR"


# Phrases, longest first within a kind so "thank you" wins over "thank".
_PHRASES: dict[Social, tuple[str, ...]] = {
    Social.IDENTITY: ("who are you", "what are you", "what is legalmind",
                      "what is this", "how does this work", "how do i use this",
                      "how do i use you", "help me", "help", "tum kaun ho",
                      "aap kaun ho"),
    Social.FAREWELL: ("good night", "goodbye", "good bye", "see you later", "see you",
                      "see ya", "bye bye", "bye", "cya", "later", "alvida"),
    Social.THANKS: ("thank you very much", "thank you so much", "thanks a lot",
                    "thanks so much", "many thanks", "much appreciated",
                    "appreciate it", "thank you", "thank u", "thankyou", "thanks",
                    "thanx", "thx", "ty", "shukriya", "dhanyavaad", "dhanyawad",
                    "dhanyavad"),
    Social.GREETING: ("good morning", "good afternoon", "good evening", "good day",
                      "hello", "hiya", "hey", "hi", "greetings", "namaste",
                      "namaskar", "hola", "yo"),
    Social.ACK: ("got it", "understood", "alright", "all right", "okay", "ok",
                 "okk", "k", "cool", "great", "nice", "perfect", "fine", "noted",
                 "sure", "sounds good", "makes sense", "theek hai", "thik hai",
                 "accha", "acha", "achha"),
}
# Interjections that may follow a social phrase ("hi there", "thanks so much, team").
_TRAIL = frozenset({"there", "legalmind", "again", "so", "much", "very", "all",
                    "everyone", "team", "sir", "madam", "ji", "oh", "ah", "um",
                    "please", "pls", "plz"})
# Joining words, allowed only BETWEEN two social phrases ("thanks and bye") — never
# eaten before a question ("thanks — and for NDAs?" keeps "and for NDAs?").
_JOIN = frozenset({"and", "then", "now", "for", "the", "your", "that", "this"})
_ORDER = (Social.IDENTITY, Social.FAREWELL, Social.THANKS, Social.GREETING, Social.ACK)
_ALL = sorted(((p.split(), k) for k, ps in _PHRASES.items() for p in ps),
              key=lambda pk: -len(pk[0]))
_WORD = re.compile(r"[a-z]+", re.I)


def _words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _consume(words: list[str]) -> tuple[list[Social], int, int]:
    """(social kinds found from the start, how far phrases and filler reach, where the
    social lead ends — after the last phrase and its trailing interjections)."""
    found: list[Social] = []
    i = end = 0
    while i < len(words):
        for phrase, k in _ALL:
            if words[i:i + len(phrase)] == phrase:
                found.append(k)
                i += len(phrase)
                while i < len(words) and words[i] in _TRAIL:
                    i += 1
                end = i
                break
        else:
            if words[i] in _TRAIL | _JOIN:
                i += 1
                continue
            break
    return found, i, end


def kind(question: str) -> Social | None:
    """The kind of a turn that is ONLY social, or None. "hi", "thanks, bye", "ok got
    it", "hello LegalMind!" are social; "hi, what is our cap?" and "thanks — and for
    NDAs?" are not (their question is answered, see `strip_social`)."""
    words = _words(question)
    if not words or len(words) > 8:
        return None
    found, reach, _ = _consume(words)
    if not found or reach < len(words):
        return None
    return next(k for k in _ORDER if k in found)


def strip_social(question: str) -> str:
    """The question without a leading social phrase ("Hi, what is…", "Thanks — and
    for NDAs?", "OK so what…") or a trailing one ("…, thanks", "…please"). Unchanged
    when nothing substantive would remain or nothing social leads."""
    text = (question or "").strip()
    words = _words(text)
    found, _, end = _consume(words)
    if found and Social.IDENTITY not in found and 0 < end < len(words):
        m = re.match(rf"^(?:\W*[a-z]+){{{end}}}([\s,.!:;—-]*)", text, re.I)
        # Only a greeting, or a phrase set off by punctuation: "Later amendments to
        # clause 5?" and "Fine print in clause 3?" keep their first word.
        separated = m is not None and (found[0] is Social.GREETING
                                       or bool(re.search(r"[,.!:;—-]", m.group(1))))
        if m is not None and separated and len(_words(text[m.end():])) >= 2:
            text = text[m.end():].strip()
    tail = re.sub(r"[\s,.!—-]*\b(?:thanks|thank you|thx|please|pls|plz)\W*$", "",
                  text, flags=re.I)
    if tail != text and len(_words(tail)) >= 2:
        text = tail.rstrip() + ("?" if text.rstrip().endswith("?") else "")
    return text[:1].upper() + text[1:] if text else text


# Requests outside what Ask is for — creative writing, weather, recipes — answered by
# one scope sentence instead of a search. "Write me a poem about contracts" is one
# (`tests/assist_eval/understanding_matrix.json` must refuse it); "draft a clause" is
# not listed and is left to routing.
_OFF_SCOPE = re.compile(
    # "the story behind the indemnity clause" is a question, "a story" a request.
    r"\b(?:write|compose|create|generate|make|give|tell)\b(?:\W+(?!the\b)\w+){0,4}?\W+"
    r"(?:poems?|songs?|story|stories|jokes?|haikus?|limericks?|lyrics|raps?|riddles?)\b"
    r"|\b(?:weather|forecast|temperature)\b(?:\W+\w+){0,4}?\W+(?:today|tomorrow|in)\b"
    r"|\brecipes?\b", re.I)

SCOPE_REPLY = (
    "I can't help with that here. LegalMind answers questions about a contract you "
    "attach, the organisation's ratified Company Standards and Legal Constitution, and "
    "the approved Indian statutes.")


def off_scope(question: str) -> bool:
    """A request Ask is not for (`AM-109`) — refused in one sentence, never searched."""
    return bool(_OFF_SCOPE.search(question or ""))


REPLY: dict[Social, str] = {
    Social.UNCLEAR: (
        "What would you like to know about? Name a topic such as liability or "
        "termination, a Constitution section or a statute — or attach a contract with "
        "Add files and ask about it."),
    # One line (owner, 2026-10-07, `AM-118` r1): a greeting matches the reader's
    # brevity. It re-introduced the product and listed its sources, which "how can you
    # help me?" answers when it is asked (the capability brief).
    Social.GREETING: "Hello. What can I help you with today?",
    Social.THANKS: "You're welcome. Ask a follow-up whenever you're ready.",
    Social.FAREWELL: "Goodbye. This conversation stays in Recent chats if you need it "
                     "again.",
    Social.ACK: "Ask your next question whenever you're ready.",
}


# ---------------------------------------------------------------- AM-118
# Two kinds of turn that a model answered too much (owner, 2026-10-07): a question
# about the reader's OWN agreement when none is in the chat, and a broad intent with
# nothing specific to answer. Both get one fixed, honest line and no model call. The
# test of "specific" is the planner's own topic vocabulary, never a second list.

#: "my contract", "my liability cap", "this agreement" — the reader's own paper.
_THEIR_PAPER = re.compile(
    r"\b(?P<who>my|this|that)\s+(?:[a-z-]+\s+){0,2}?"
    r"(?:contract|agreement|msa|nda|sla|clause|cap|terms|draft|document|deal|"
    r"notice period|indemnity)\b", re.I)


#: What a reader gives or asks for that needs no agreement in the chat (final review,
#: 2026-10-07): the clause quoted or set out after a colon, a figure stated ("my cap of
#: 3 months' fees"), a drafting request, or more than a bare question's length.
_GIVES_ITS_OWN = re.compile(
    r'["\u201c\u201d]|:\s*\S+(?:\s+\S+){2}|\d|\b(?:draft|write|prepare|redline|create)\b',
    re.I)


def their_document_topic(question: str, *, has_prior: bool) -> str | None:
    """The topic of a question about the reader's own agreement, when no agreement or
    pasted material is in the chat — "" when it names none — or None when the question
    is not about their paper. "This/that agreement" can refer to an earlier turn, so
    only "my …" counts once the chat has history; "our" is the company's standard and
    is answered from it. A question that carries its own text or figure, or asks for a
    draft, is answered: there is nothing missing to ask for."""
    from legalmind.assist.query import planner
    m = _THEIR_PAPER.search(question or "")
    if (m is None or (has_prior and m.group("who").lower() != "my")
            or _GIVES_ITS_OWN.search(question) or len(_words(question)) > 20):
        return None
    topics = sorted(planner.topics_in(question))
    return topics[0].split(" & ")[0].lower() if topics else ""


def needs_document(topic: str) -> str:
    """The reply when the answer depends on an agreement this chat does not have."""
    clause = f"the {topic} clause" if topic else "the clause"
    return ("I don't have that agreement in this chat yet. Attach it with Add files, or "
            f"paste {clause}, and I'll answer from its text, our standards and the law.")


#: A broad thing to talk about, with no question asked.
_INTENT = re.compile(
    r"^\s*(?:i|we)\s+(?:want|would like|wanna|need|have|got)\b", re.I)
_VAGUE_NOUN = re.compile(
    r"\b(dispute|issue|problem|matter|situation|complaint|claim|concern|case)s?\b", re.I)
_CLARIFY = {
    "dispute": "Is the dispute about payment, termination, a breach of the agreement, "
               "or something else?",
}
_CLARIFY_ANY = ("What is it about — a payment, a termination, a breach of the agreement, "
                "or something else?")


#: The words of a broad intent that name nothing: who, how, and the filler around them.
_GENERIC = frozenset({
    "i", "we", "want", "would", "like", "wanna", "need", "have", "got", "to", "talk",
    "speak", "discuss", "chat", "with", "someone", "somebody", "a", "an", "the", "about",
    "regarding", "on", "my", "our", "some", "me", "us", "lawyer", "counsel", "help",
    "advice", "question"})


def vague_intent(question: str) -> str | None:
    """One clarifying question for "I want to talk about a dispute", or None. Vague
    means: an intent to talk, short, no question asked, and nothing specific once the
    broad noun itself is set aside ("a payment dispute" names payment and is answered)."""
    from legalmind.assist.query import planner
    text = (question or "").strip()
    noun = _VAGUE_NOUN.search(text)
    # specific is ANY word beyond the intent, the broad noun and how one talks about it
    # — "a claim under the DPDP Act" names the Act (final review, 2026-10-07)
    named = set(_words(_VAGUE_NOUN.sub(" ", text))) - _GENERIC
    if (noun is None or "?" in text or len(_words(text)) > 14
            or not _INTENT.match(text) or named
            or planner.topics_in(_VAGUE_NOUN.sub(" ", text))):
        return None
    return _CLARIFY.get(noun.group(1).lower(), _CLARIFY_ANY)

