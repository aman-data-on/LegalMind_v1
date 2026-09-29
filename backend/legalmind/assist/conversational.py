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
    r"\b(?:write|compose|create|generate|make|give|tell)\b(?:\W+\w+){0,4}?\W+"
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
    Social.GREETING: (
        "Hello. I can answer questions about a contract you attach, the organisation's "
        "ratified Company Standards and Legal Constitution, and the approved Indian "
        "statutes — every answer cites where it came from. What would you like to "
        "know?"),
    Social.THANKS: "You're welcome. Ask a follow-up whenever you're ready.",
    Social.FAREWELL: "Goodbye. This conversation stays in Recent chats if you need it "
                     "again.",
    Social.ACK: "Ask your next question whenever you're ready.",
}

