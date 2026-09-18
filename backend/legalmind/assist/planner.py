"""Query understanding — what a question is ABOUT, so retrieval can be aimed at it.

Until 2026-09-17 the assist lane knew a question's SHAPE (comparison, capability,
statute, follow-up — `intent.py`) and nothing about its subject. "What is the
termination notice period?" and "what is the liability cap?" ran the identical
unconstrained scan over the same candidates, differing only by embedding distance.
Measured on the ratified 77-question set: shipped recall@10 0.891 against a 0.938
vector ceiling, every fusion/depth/weight lever at 0.000, and Domain A searched all 40
position chunks for every position question although each ratified standard already
carries the Constitution's Appendix-B topic.

This module asks the model ONE thing before retrieval: what is the question about, and
how would a lawyer phrase a search for it. It returns a small structured plan that the
retrieval code may use to aim — and may not use for anything else.

THE BOUNDARY, which is the whole design:

    The plan is ADVISORY and FAILS CLOSED. It may narrow Domain A to a topic the
    ratified standards already carry, and add up to three reformulated retrieval
    queries that are embedded LOCALLY. It may not add a domain the caller is not
    authorized for (`routing.plan` decides that from permissions, before this runs),
    may not touch the comparison decision (`AM-25` r4 stays code — `intent.
    is_comparison_question` runs first and returns before this is reached), may not
    open the gate, and is never cited. On any failure — flag off, refusal, timeout,
    unparseable reply — the plan is None and retrieval runs exactly as it did before.

EGRESS: the payload is the question, the same prior USER questions `AM-58` r1 already
admits, and this template. That is a SUBSET of what `AM-30` t2 (as amended by `AM-58`)
permits for generation — no chunk, no position, no statute text. A new PURPOSE for the
seam, as the rescue was, recorded under its own prompt version and hash-audited
(`AM-30` t5). The model's reply is used only to steer local retrieval and is recorded
on `retrieval_runs.filters.plan` — it never reaches a reader.

Imports no retrieval and no persistence: it reads a plan out of the model and returns
it. Pinned by `tests/test_assist_planner.py`.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass

from legalmind import config
from legalmind.assist import generation
from legalmind.observability.logs import log_event

PLAN_PROMPT_VERSION = "query-plan-1"
#: A hard cap on the planner's provider call. A plan that arrives late is worth less
#: than no plan — the pipeline it steers is the one that runs without it.
#: MEASURED 2026-09-17: a ~150-token JSON plan from gemini-3.6-flash at MINIMAL thinking
#: takes 2.4–8.0 s, bimodal (~2.4 s or ~7.9 s — provider-side, not prompt size). At a
#: 4 s cap only 26 of 79 gate questions received a plan and the rest paid the 4 s for
#: nothing; the first Phase 1 gate run therefore measured a timeout, not a planner. 10 s
#: lets every measured call complete. The latency cost is real, and reported rather than
#: hidden.
PLAN_TIMEOUT_S = 10.0
MAX_QUERIES = 3
MAX_QUERY_CHARS = 160
MIN_QUERY_CHARS = 3
MAX_SUBJECT_CHARS = 120

_INTENTS = frozenset({"FACT", "LIST", "EXPLAIN", "PROCEDURE"})
_PARTIES = frozenset({"ORGANIZATION", "COUNTERPARTY", "EITHER", "NONE"})
_SOURCES = frozenset({"DOCUMENT", "POSITIONS", "STATUTES", "ANY"})
_SECTION = re.compile(r"^\d{1,3}(?:\.\d{1,3}){0,3}[a-z]?$", re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

# The topic vocabulary is the Constitution's Appendix B, read off the ratified standards
# themselves (`configuration.constitution.topic`) — nothing authored here. Same files
# `positions.RATIFIED_STANDARDS_DIR` names; the path is spelled out so this module
# imports no retrieval code.
RATIFIED_STANDARDS_DIR = (pathlib.Path(__file__).resolve().parents[2]
                          / "config" / "company_standards")


def _load_topics() -> tuple[str, ...]:
    topics: set[str] = set()
    for path in sorted(RATIFIED_STANDARDS_DIR.glob("*.json")):
        try:
            topic = json.loads(path.read_text())["configuration"]["constitution"]["topic"]
        except (KeyError, TypeError, ValueError):
            continue
        if isinstance(topic, str) and topic.strip():
            topics.add(topic.strip())
    return tuple(sorted(topics))


TOPICS: tuple[str, ...] = _load_topics()


@dataclass(frozen=True)
class QueryPlan:
    #: FACT | LIST | EXPLAIN | PROCEDURE — the answer's shape (used by generation later;
    #: recorded now).
    intent: str
    #: One of `TOPICS`, or None. The ONLY field that narrows a search (Domain A).
    topic: str | None
    #: What is being asked about, in the model's words. Recorded; never shown.
    subject: str
    #: ORGANIZATION | COUNTERPARTY | EITHER | NONE — whose position/obligation. Recorded.
    party: str
    #: DOCUMENT | POSITIONS | STATUTES | ANY — advisory; routing decides domains.
    source_preference: str
    #: Up to MAX_QUERIES short search phrases, embedded locally beside the question.
    queries: tuple[str, ...]
    #: A clause number the question names, or None.
    section_hint: str | None

    def as_filters(self) -> dict:
        """The record for `retrieval_runs.filters.plan` — enums, the topic, the
        reformulations. No chunk text, nothing a reader sees."""
        return {"prompt_version": PLAN_PROMPT_VERSION, "intent": self.intent,
                "topic": self.topic, "subject": self.subject, "party": self.party,
                "source_preference": self.source_preference,
                "queries": list(self.queries), "section_hint": self.section_hint}


# ---------------------------------------------------------------------------
# THE CHEAP PATH (Phase 1, 2026-09-18)
# ---------------------------------------------------------------------------
# Phase 1's first attempt asked the provider about EVERY question: measured
# +4,788 ms p50 for a targeting gain of about one question in 64, and evidence
# precision FELL 0.390 -> 0.358 because every extra query adds its own
# rank-fused list and dilutes the gold share. Both causes are addressed here
# rather than retuned:
#
#   1. Most questions do not need a model to say what they are about. One
#      lexical table answers it for nothing, so the provider is reached only
#      for a question this table cannot place.
#   2. A reformulation only helps when it contributes a TERM THE QUESTION DOES
#      NOT ALREADY CONTAIN. "What is the cure period?" gains nothing from
#      "cure period" as a second query and pays the precision for it; "How
#      much time do we get to fix a breach?" gains the term outright. So an
#      extra query is emitted only when the canonical term is absent.
#
# WHAT THIS TABLE IS: search vocabulary — the words a lawyer would type for
# what a reader typed, plus the Constitution Appendix-B topic each belongs to.
# It is the same kind of object as `statutes._ACT_ALIASES` ("Names only — no
# law") and is held to the same rule: NO threshold, NO position, NO acceptance
# policy, NO carve-out, nothing about what any standard requires (rules 7 and
# 21). Every topic string is validated against `TOPICS` at import, which is
# read off the ratified standards themselves — a typo here cannot invent a
# topic, it fails the assertion.
#
# (cue matched in the question, canonical legal term, Constitution topic)
_TERMS: tuple[tuple[str, str, str], ...] = (
    (r"fix (?:a |the )?breach|cure (?:a |the )?breach|remedy (?:a |the )?(?:breach"
      r"|default)"
     r"|time to (?:fix|cure)|put it right",
     "cure period", "Termination & Suspension"),
    (r"walk away|get out of|exit early|end (?:it |the (?:contract|agreement) )?early"
     r"|leave before|before it expires|cancel early",
     "termination for convenience early termination",
     "Fixed-Term Commitments & Early Exit"),
    (r"how much notice|notice (?:period|to terminate)|how long before.*(?:terminat"
      r"|cancel)",
     "notice period termination", "Termination & Suspension"),
    (r"most we (?:can|could) (?:be liable|owe|lose)|maximum (?:we|they) (?:owe|pay)"
     r"|liability cap|cap on (?:liability|damages)|limit of liability|how much.*liable",
     "limitation of liability cap", "Liability"),
    (r"who pays if|cover us if|defend us|hold us harmless|third.?party claim",
     "indemnification indemnify", "Indemnification"),
    (r"roll(?:s|ed)? over|renew(?:s|al)? automatic|automatic(?:ally)? renew"
      r"|keep going after",
     "automatic renewal renewal term", "Renewal (Auto-Renewal)"),
    (r"uptime|downtime|service credit|availability guarantee|how reliable",
     "service level availability uptime", "SLA / Service Levels"),
    (r"our data|personal data|privacy|data breach|where.*data.*stored|delete our data",
     "data protection personal data", "Data Protection & Privacy"),
    (r"keep (?:it |things )?(?:secret|confidential)|nda|non.?disclos|trade secret",
     "confidentiality confidential information",
     "Confidentiality & Intellectual Property"),
    (r"which (?:court|law)|governing law|jurisdiction|arbitrat|where.*sue|dispute",
     "governing law dispute resolution", "Governing Law & Dispute Resolution"),
    (r"act of god|natural disaster|pandemic|strike|beyond (?:their|our) control"
     r"|force majeure",
     "force majeure", "Force Majeure"),
    (r"raise (?:the )?price|increase (?:the )?(?:price|fee)|late pay|payment term"
     r"|invoice|gst|tax",
     "payment terms fees taxes", "Payment Terms & Taxes"),
    (r"stop (?:providing|offering) the service|discontinu|sunset|shut (?:it )?down",
     "service discontinuation", "Major Changes — Service Discontinuation"),
    (r"bought|acquir|merger|change of control|sold to",
     "change of control assignment", "Major Changes — Change of Control"),
    (r"as.?is|no warrant|disclaim|guarantee the software",
     "warranty disclaimer", "Warranty Disclaimer"),
)

# A cue's topic must be one the ratified standards actually carry. This is the
# guard that keeps the table vocabulary rather than invention.
assert not TOPICS or all(topic in TOPICS for _, _, topic in _TERMS), \
    "planner._TERMS names a topic no ratified standard carries"

_TERMS_COMPILED = tuple((re.compile(cue, re.IGNORECASE), term, topic)
                        for cue, term, topic in _TERMS)

#: A question with none of the cues and none of these hedges is taken at face
#: value: retrieval runs exactly as it does today, with no plan and no call.
#: These are the shapes where a reader is NOT naming the thing they want --
#: multi-part, conditional, comparative or referential -- and where the model
#: has something to add that a substring cannot.
_AMBIGUOUS = re.compile(
    r"\band\b.*\?|\bor\b.*\?"          # two questions in one
    r"|\bif\b|\bwhen\b|\bunless\b|\bwhat happens\b"   # conditional
    r"|\bdifference\b|\bcompared\b|\bversus\b|\bvs\b"  # comparative
    r"|\bthis\b|\bthat\b|\bit\b|\bthey\b|\bthose\b"  # referential
    r"|\banything else\b|\bany other\b|\bwhat about\b",
    re.IGNORECASE)


def plan_lexical(question: str) -> QueryPlan | None:
    """A plan for nothing, or None. No provider call, no network, no I/O.

    Returns a plan when the question names something the table places: the
    topic narrows Domain A, and the canonical term becomes an extra query ONLY
    if the question does not already use it.

    `party` and `source_preference` stay NEUTRAL. Both are recorded fields
    that narrow nothing -- routing decides domains from permissions (`AM-45`
    r1) and the comparison screen is code -- so a lexical guess at either buys
    no retrieval and would read as authority it does not have. Reading `party`
    off `intent.mentions_organization` was tried and reverted: the boundary
    test `test_the_planner_reaches_no_retrieval_and_no_persistence` forbids
    this module importing a safety screen, and it is right to. The provider
    path still fills both when it runs.
    """
    text_in = (question or "").strip()
    if not text_in:
        return None
    lowered = text_in.casefold()
    topic: str | None = None
    queries: list[str] = []
    subject = ""
    for pattern, term, cue_topic in _TERMS_COMPILED:
        # A question may arrive in a reader's words (the cue) or already in a
        # lawyer's (the canonical term). Either places the TOPIC; only the
        # first is missing the term.
        by_cue = bool(pattern.search(text_in))
        # "Already said it" is per DISTINCTIVE word, not the whole phrase. A
        # reader who typed "liability" already has that lexical pass; a second
        # near-duplicate list of "limitation of liability cap" only dilutes the
        # gold share. Short words ("of", "cap") carry no retrieval signal.
        has_term = any(w in lowered for w in term.casefold().split() if len(w) >= 5)
        if not (by_cue or has_term):
            continue
        if topic is None:
            topic, subject = cue_topic, term
        # The precision rule: contribute a term, never a paraphrase. A term
        # already in the reader's own words is already in the lexical pass,
        # and a second list of it only dilutes the gold share (measured).
        if not has_term and term not in queries and len(queries) < MAX_QUERIES:
            queries.append(term)
    hint = _SECTION_IN_QUESTION.search(text_in)
    section_hint = hint.group(1) if hint else None
    if topic is None and not queries and section_hint is None:
        return None
    return QueryPlan(
        intent="FACT", topic=topic, subject=subject,
        party="NONE", source_preference="ANY",
        queries=tuple(queries[:MAX_QUERIES]),
        section_hint=section_hint)


#: "section 7.2", "clause 13" -- the number a reader names, for `section_hint`.
#: `_SECTION` validates a bare token; this finds one inside a sentence.
_SECTION_IN_QUESTION = re.compile(
    r"(?:section|clause|article|para(?:graph)?)\s+(\d{1,3}(?:\.\d{1,3}){0,3}[a-z]?)",
    re.IGNORECASE)


PLAN_PROMPT_TEMPLATE = """You are planning a search over legal documents for an \
assistant. Do NOT answer the question. Do NOT give legal advice or opinions.

Return ONLY a JSON object with exactly these keys:
  "intent": one of FACT, LIST, EXPLAIN, PROCEDURE
  "topic": one of the TOPICS below that the question is about, or null if none fits
  "subject": what is being asked about, in at most 12 words
  "party": ORGANIZATION if the question asks about our own organization's position \
or obligations, COUNTERPARTY if the other side's, EITHER if both, NONE if neither
  "source_preference": DOCUMENT (the uploaded contract), POSITIONS (our organization's \
own approved standards), STATUTES (the law itself), or ANY
  "queries": a list of up to 3 short search phrases (3 to 8 words each) a lawyer would \
use to find the relevant clause. Vary the wording and use synonyms; do not repeat the \
question.
  "section_hint": a clause or section number if the question names one, else null

TOPICS:
{topics}
{context}
QUESTION: {question}

JSON:"""
CONTEXT_HEADER = ("EARLIER QUESTIONS IN THIS CONVERSATION (context only — the current "
                  "question may refer to them; do not plan for them):")


def plan(question: str, prior_questions: tuple[str, ...] | list[str] = (), *,
         request_id: str | None = None) -> QueryPlan | None:
    """A plan, or None. None means: retrieve exactly as before.

    THREE OUTCOMES, cheapest first — the Phase 1 shape (2026-09-18):

      1. `plan_lexical` places the question — a topic, a legal term the reader
         did not use, or a section number. Returned immediately: no provider
         call, no added latency. This is the common case.
      2. Nothing placed it and it reads as a plain, self-contained question.
         None: retrieval runs exactly as it does today, still no call. A simple
         question does not pay for a planner (the Phase 1 measurement is why).
      3. Nothing placed it AND it reads as ambiguous — multi-part, conditional,
         comparative or referential. Only here is the provider asked, and only
         here is its latency spent.

    The boundary is unchanged in all three: advisory, fails closed to None,
    never a domain, never the gate, never the comparison, never cited.
    """
    if not config.query_planner_enabled():
        return None
    question = (question or "").strip()
    if not question:
        return None
    cheap = plan_lexical(question)
    if cheap is not None:
        log_event("assist.plan.lexical", request_id=request_id,
                  topic=cheap.topic or "", queries=str(len(cheap.queries)),
                  section_hint=str(bool(cheap.section_hint)))
        return cheap
    if not _AMBIGUOUS.search(question):
        log_event("assist.plan.skipped", request_id=request_id, reason="plain")
        return None
    context = ""
    if prior_questions:
        listed = "\n".join(f"- {q}" for q in prior_questions)
        context = f"\n{CONTEXT_HEADER}\n{listed}\n"
    prompt = PLAN_PROMPT_TEMPLATE.format(
        topics="\n".join(f"- {t}" for t in TOPICS), context=context, question=question)
    try:
        result = generation.generate_raw(
            prompt, prompt_version=PLAN_PROMPT_VERSION, environment=config.environment(),
            request_id=request_id, max_output_tokens=256, timeout_s=PLAN_TIMEOUT_S)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        log_event("assist.plan.unavailable", request_id=request_id,
                  reason=type(exc).__name__)
        return None
    made = parse_plan(result.text, question)
    if made is None:
        log_event("assist.plan.unparseable", request_id=request_id)
        return None
    # Enums and counts only — a reformulated question is the user's question in other
    # words, and the log is not where the user's questions live (53.3).
    log_event("assist.plan.made", request_id=request_id, intent=made.intent,
              topic=made.topic or "", party=made.party,
              source=made.source_preference, queries=str(len(made.queries)),
              section_hint=str(bool(made.section_hint)))
    return made


def parse_plan(reply: str, question: str) -> QueryPlan | None:
    """Strict, forgiving only about surrounding prose: the first {...} block must be a
    JSON object. Every field is validated against a closed vocabulary or clipped; an
    unknown enum falls to its neutral value, an unknown topic to None. Only an
    unparseable reply yields None."""
    match = _JSON_OBJECT.search(reply or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    def enum(key: str, allowed: frozenset[str], default: str) -> str:
        value = str(data.get(key) or "").strip().upper()
        return value if value in allowed else default

    topic_raw = str(data.get("topic") or "").strip()
    topic = next((t for t in TOPICS if t.casefold() == topic_raw.casefold()), None)
    subject = str(data.get("subject") or "").strip()[:MAX_SUBJECT_CHARS]
    raw_queries = data.get("queries")
    queries: list[str] = []
    if isinstance(raw_queries, list):
        for item in raw_queries:
            q = " ".join(str(item or "").split())[:MAX_QUERY_CHARS]
            if len(q) < MIN_QUERY_CHARS or q.casefold() == question.casefold() \
                    or any(q.casefold() == k.casefold() for k in queries):
                continue
            queries.append(q)
            if len(queries) == MAX_QUERIES:
                break
    hint_raw = str(data.get("section_hint") or "").strip().rstrip(".")
    section_hint = hint_raw if hint_raw and _SECTION.match(hint_raw) else None
    return QueryPlan(intent=enum("intent", _INTENTS, "FACT"), topic=topic,
                     subject=subject, party=enum("party", _PARTIES, "NONE"),
                     source_preference=enum("source_preference", _SOURCES, "ANY"),
                     queries=tuple(queries), section_hint=section_hint)
