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
    """One planning call, or None. None means: retrieve exactly as before."""
    if not config.query_planner_enabled():
        return None
    question = (question or "").strip()
    if not question:
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
