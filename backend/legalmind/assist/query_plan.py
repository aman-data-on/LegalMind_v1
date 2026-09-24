"""The structured query plan — roadmap §6, PHASE 6 (`AM-85`).

Deterministic and free: no model, no database, no network. It composes what already
exists — `understanding.understand` (intent, requested fact, authority, jurisdiction,
time, operation), `planner.plan_lexical` (topic, canonical search terms, section hint)
— and adds what roadmap §6 names and nothing read before:

  language        en · hi (Devanagari) · hinglish (romanised Hindi)
  figures         every "number + unit" the reader wrote ("6 months", "12 months")
  claims          sentences in which someone ASSERTS something ("the client says …",
                  "we promised …") — context, never evidence (roadmap §9, `AM-78`)
  document_state  UNAVAILABLE when the reader says the controlling paper is missing
  lanes           which KINDS of source the answer must keep apart (roadmap §9):
                  COMPANY_POSITION · CONTRACT · LAW · HISTORICAL_EXCEPTION ·
                  USER_ASSERTION · MISSING_DOCUMENT
  sub_questions   one focused retrieval query per question the reader actually asked,
                  each tagged with the lane that can answer it (roadmap §6
                  decomposition) — a context sentence is never a sub-question

The words below recognise the SHAPE of what is said (reported speech, "cannot find",
"old signed", "enforceable"), never a legal position: no threshold, no carve-out, no
statement of what any standard requires (rules 7, 21). A lane says what KIND of source
bears on a part of the question; it never decides whether evidence suffices (`AM-84`
r4) and never widens what the caller may read — routing still intersects with
permissions (`AM-45` r1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from legalmind.assist import planner, understanding

COMPANY_POSITION = "COMPANY_POSITION"
CONTRACT = "CONTRACT"
LAW = "LAW"
HISTORICAL_EXCEPTION = "HISTORICAL_EXCEPTION"
USER_ASSERTION = "USER_ASSERTION"
MISSING_DOCUMENT = "MISSING_DOCUMENT"

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Function words of romanised Hindi — grammar, like the Devanagari script test above.
_HINGLISH = frozenset((
    "hai", "hain", "ka", "ki", "ke", "ko", "kya", "kaise", "kitna", "kitne", "kitni",
    "nahi", "nahin", "karna", "karne", "karta", "chahta", "chahiye", "hamari",
    "hamara", "hamare", "humari", "humara", "humne", "hamne", "toh", "tak", "kab",
    "baad", "milta", "milti", "chalti", "saal", "din", "mein", "aur", "ya", "bhi",
    "jaldi", "wala"))
_WORD = re.compile(r"[a-z]+")
# "6 months", "30 days", "12-month", "six weeks", "₹5 lakh", "25%".
_FIGURE = re.compile(
    r"(?:₹|rs\.?\s*)?\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|twelve|fifteen|thirty|sixty|ninety)[\s-]*"
    r"(days?|weeks?|months?|years?|hours?|%|per ?cent|lakhs?|crores?)\b", re.I)
# Someone other than the governing text ASSERTS something: reported speech, a promise.
_CLAIM = re.compile(
    r"\b(?:client|customer|counterparty|vendor|partner|they|he|she|someone|sales)\b"
    r"[^.?]{0,40}\b(?:says?|said|claims?|claimed|mentions?|mentioned|insists?|argues?|"
    r"told|tells|states?)\b"
    r"|\b(?:we|i|humne|hamne)\b[^.?]{0,20}\b(?:promised|agreed|told|offered|committed)\b"
    r"|\bbol (?:raha|rahi) hai\b|\bkeh (?:raha|rahi) hai\b", re.I)
_MISSING = re.compile(
    r"\b(?:cannot|can't|can ?not|couldn't|could not|unable to)\s+(?:find|locate|trace)\b"
    r"|\b(?:missing|lost|misplaced|unavailable|not available)\b"
    r"|\b(?:do not|don't|dont) have\b[^.?]{0,30}\b(?:signed|executed|final|copy)\b"
    r"|\bwithout (?:checking |seeing |the )?(?:the )?(?:signed|executed|final)\b", re.I)
# The reader points at an actual agreement — never the bare word "contract", which
# `document_target` reads in "Contract Act" and "remaining contract value" alike.
_CONTRACT = re.compile(
    r"\b(?:signed|executed|countersigned)\b|\bour contract with\b|\bthis customer'?s\b"
    r"|\bwith (?:this|the) (?:client|customer)\b"
    r"|\b(?:this|the attached|the uploaded|their)\s+(?:nda|msa|agreement|contract|"
    r"document|order form|sla|po)\b", re.I)
_HISTORICAL = re.compile(
    r"\b(?:old|older|past|previous|earlier|historical|legacy)\b[^.?]{0,25}"
    r"\b(?:signed|msa|agreement|contract|deal)s?\b", re.I)
_SIGNED = re.compile(r"\b(?:signed|executed|countersigned)\b", re.I)
_LAW = re.compile(
    r"\b(?:enforceab\w*|legally|recoverable|recover|under (?:indian )?law|the law|"
    r"statute)\b", re.I)
# How much of a compensation / damages / penalty sum is due is a question the law of
# compensation for breach bears on, whatever the paper says (the Constitution §14 and
# §28.4.1 say the same of themselves) — so an AMOUNT of one opens the LAW lane.
_AMOUNT_OF_SUM = re.compile(
    r"\b(?:amount|how much|confirm|quantum)\b[^.?]{0,40}\b(?:compensation|damages|"
    r"penalty|fee)\b|\b(?:compensation|damages|penalty)\b[^.?]{0,25}\bamount\b", re.I)
_POSITION = re.compile(r"\b(?:constitution|our (?:position|policy|standard)|policy|"
                       r"company position|standard msa)\b", re.I)
_QUESTION = re.compile(r"\b(?:what|which|how|when|where|who|why|is|are|does|do|did|can|"
                       r"could|should|would|will|may|must|kya|kitna|kitne|kab|kaise)\b",
                       re.I)
_SENTENCE = re.compile(r"(?<=[.?!])\s+")
_CLAUSE = re.compile(r",\s+(?:and|or|but)\s+(?=(?:what|which|how|can|could|should|is|"
                     r"are|does|do|will|may|must)\b)", re.I)


@dataclass(frozen=True)
class SubQuestion:
    text: str
    lanes: tuple[str, ...]
    query: str


@dataclass(frozen=True)
class QueryPlan:
    question: str
    understood: understanding.QuestionUnderstanding
    topic: str | None
    terms: tuple[str, ...]
    language: str
    figures: tuple[str, ...]
    claims: tuple[str, ...]
    document_state: str | None
    lanes: frozenset[str]
    sub_questions: tuple[SubQuestion, ...]
    section_hint: str | None

    @property
    def complex(self) -> bool:
        """More than one thing is being asked, or more than one kind of source must
        be kept apart — the case roadmap §6 decomposes."""
        return len(self.sub_questions) > 1 or len(self.lanes) > 1


def language(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "hi"
    words = _WORD.findall(text.lower())
    return "hinglish" if sum(w in _HINGLISH for w in words) >= 2 else "en"


def _lanes(text: str, topic: str | None) -> set[str]:
    """The lanes one piece of text bears on, read from that piece alone."""
    u = understanding.understand(text)
    lanes: set[str] = set()
    if _CLAIM.search(text):
        lanes.add(USER_ASSERTION)
    if _MISSING.search(text):
        lanes.add(MISSING_DOCUMENT)
    historical = bool(_HISTORICAL.search(text))
    # A reader who reports what someone's SIGNED paper says ("the client says their
    # signed MSA mentions 6 months") is citing paper we cannot see: the Constitution's
    # record of past negotiated paper is the source kind that bears on it (PHASE 9,
    # `AM-88`). The shape of the sentence, never a position.
    if historical or (_CLAIM.search(text) and _SIGNED.search(text)):
        lanes.add(HISTORICAL_EXCEPTION)
    if understanding.GENERAL_LAW in u.authority or _LAW.search(text) \
            or _AMOUNT_OF_SUM.search(text):
        lanes.add(LAW)
    if _CONTRACT.search(text) and not historical:   # old paper is history, not THE deal
        lanes.add(CONTRACT)
    # A placed topic with nothing else claiming the question is the organization's
    # position on it; an unplaced question gets no lane — routing decides (`AM-45`).
    if (understanding.POSITION in u.authority or _POSITION.search(text)
            or (topic and not lanes - {USER_ASSERTION, MISSING_DOCUMENT})):
        lanes.add(COMPANY_POSITION)
    return lanes


def plan(question: str, *, has_document: bool | None = None,
         prior: tuple[str, ...] | list[str] = ()) -> QueryPlan:
    """`has_document` is the router's fact (`AM-25` r4): when the question needs the
    contract and none is in scope, the controlling paper is UNAVAILABLE even though
    the reader never said "missing" — "what is the cap in our signed contract with
    this customer?" asked with no document open. None means unknown: nothing added."""
    text = (question or "").strip()
    u = understanding.understand(text)
    lexical = planner.plan_lexical(text)
    # Conversation (roadmap §15, within `AM-58`): a turn that names no topic inherits
    # the most recent prior USER question's — "What if the customer says they were
    # promised 6 months?" after an early-termination question is still about early
    # termination. Only the TOPIC carries; the prior turn's claims and figures do not,
    # and nothing from an earlier ANSWER is read (`AM-58` r2).
    if (lexical is None or lexical.topic is None) and prior:
        for earlier in reversed(list(prior)):
            inherited = planner.plan_lexical(earlier)
            if inherited and inherited.topic:
                lexical = inherited if lexical is None else planner.QueryPlan(
                    intent=lexical.intent, topic=inherited.topic,
                    subject=inherited.subject, party=lexical.party,
                    source_preference=lexical.source_preference,
                    queries=lexical.queries, section_hint=lexical.section_hint)
                break
    topic = lexical.topic if lexical else None
    terms = lexical.queries if lexical else ()
    subject = lexical.subject if lexical else ""
    sentences = [s for s in _SENTENCE.split(text) if s.strip()]
    claims = tuple(s for s in sentences if _CLAIM.search(s))
    subs: list[SubQuestion] = []
    for sentence in sentences:
        for part in _CLAUSE.split(sentence):
            part = part.strip()
            asks = part.endswith("?") or bool(_QUESTION.match(part))
            if not asks or (part in claims and not part.endswith("?")):
                continue            # context, not a question: a claim or a statement
            lanes = _lanes(part, topic)
            # The whole question's topic carries into a part that does not name one
            # ("Does it specify 6 months …?" is still about early exit).
            query = " ".join(x for x in (subject, part) if x)
            subs.append(SubQuestion(part, tuple(sorted(lanes)), query))
    if not subs:
        subs = [SubQuestion(text, tuple(sorted(_lanes(text, topic))),
                            " ".join(x for x in (subject, text) if x))]
    # Context sentences (a claim, "we cannot find the signed copy") add their lanes to
    # the plan without becoming questions of their own.
    all_lanes = set().union(*(s.lanes for s in subs), *(_lanes(s, topic)
                                                          for s in sentences))
    if has_document is False and CONTRACT in all_lanes:
        all_lanes.add(MISSING_DOCUMENT)
    return QueryPlan(
        question=text, understood=u, topic=topic, terms=tuple(terms),
        language=language(text),
        figures=tuple(dict.fromkeys(f"{m.group(1)} {m.group(2).lower()}"
                                    for m in _FIGURE.finditer(text))),
        claims=claims,
        document_state="UNAVAILABLE" if MISSING_DOCUMENT in all_lanes else None,
        lanes=frozenset(all_lanes), sub_questions=tuple(subs),
        section_hint=lexical.section_hint if lexical else None)
