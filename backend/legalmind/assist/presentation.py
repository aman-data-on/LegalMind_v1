"""The reader's presentation instruction — what TASK they want done and in what SHAPE
(`AM-108`): "Give me a short summary", "Summarize this in 5 bullet points", "Put the
termination clauses in a table", "Explain this in simple language", "What are the key
risks?", "List only the termination clauses", "… without comparing it to our standard".

Read deterministically, once, from the question's own words. It controls presentation
and task scope ONLY: which shape the answer takes, how long it is, how plain its words
are, and — for a document task — that the document, not the company position, is the
subject. It never touches evidence, authorization, a contract check, the verifier or the
fail-closed rules; a shaped answer is verified sentence by sentence exactly as prose is.

    p = presentation.read("Summarize this in 5 bullet points.")
    p.task, p.shape, p.count, p.topic      # SUMMARY, BULLETS, 5, ""

`topic` is what is left of the instruction once its task and format words are removed —
what retrieval has to search for. An empty topic with a document attached is a
DOCUMENT-WIDE task: the whole document is the subject (`retrieval.outline`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ANSWER, SUMMARY, LIST, EXPLAIN, RISKS = "ANSWER", "SUMMARY", "LIST", "EXPLAIN", "RISKS"
PROSE, BULLETS, TABLE = "PROSE", "BULLETS", "TABLE"
SHORT, SIMPLE = "SHORT", "SIMPLE"

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_COUNT = re.compile(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
                    r"(?:bullet|point|item|line|sentence|row|clause|key)", re.I)
_BULLETS = re.compile(r"\b(?:bullets?|bullet ?points?|points?|as a list|in a list|"
                      r"list form|listed)\b", re.I)
_TABLE = re.compile(r"\b(?:tables?|tabular|tabulate|in columns|side[- ]by[- ]side)\b",
                    re.I)
_SUMMARY = re.compile(r"\b(?:summar\w*|overview|tl;?dr|gist|brief me|recap|"
                      r"key (?:points|terms|takeaways))\b", re.I)
_LIST = re.compile(r"\b(?:list(?: only| out| all| me)?|enumerate|which clauses|what "
                   r"clauses|extract|the \w+(?: \w+)? (?:clauses?|provisions?|"
                   r"sections?))\b", re.I)
_EXPLAIN = re.compile(r"\b(?:explain|walk me through|what does (?:this|it|that) mean|"
                      r"help me understand|break (?:this|it) down)\b", re.I)
_RISKS = re.compile(r"\b(?:risks?|risky|exposures?|concerns?|red flags?|watch out|"
                    r"dangers?|pitfalls?|onerous)\b", re.I)
_SHORT = re.compile(r"\b(?:short|brief(?:ly)?|concise(?:ly)?|quick(?:ly)?|in a "
                    r"(?:sentence|line|nutshell)|one[- ]liner?|tl;?dr|succinct\w*)\b",
                    re.I)
_SIMPLE = re.compile(r"\b(?:simple|simply|plain (?:english|language|words|terms)|"
                     r"layman'?s?|non[- ]lawyer|easy to understand|in easy words|"
                     r"like i'?m (?:five|5)|jargon[- ]free|without jargon)\b", re.I)
_NO_COMPARISON = re.compile(r"\b(?:without|not|don'?t|do not|no need to|never|rather "
                            r"than|instead of)\s+(?:\w+\s+){0,2}?(?:compar\w*|"
                            r"measur\w*|assess\w*|check\w*|judg\w*|evaluat\w*|"
                            r"benchmark\w*)\b|\bno comparison\b", re.I)
# Words that carry the instruction and nothing of the subject: removed to leave the
# topic. "the termination clauses" survives; "give me a short summary" leaves nothing.
_INSTRUCTION_WORDS = re.compile(
    r"\b(?:give|gimme|provide|make|create|produce|prepare|write|draft|show|tell|put|"
    r"present|format|render|do|can|could|would|please|kindly|just|only|me|us|i|we|"
    r"you|a|an|the|this|that|it|these|those|of|in|into|as|for|with|and|or|to|be|is|"
    r"are|about|on|from|what|which|whole|entire|full|complete|document|agreement|"
    r"contract|file|attached|attachment|uploaded|upload|pdf|text|here|now|"
    r"summar\w*|overview|tl;?dr|gist|recap|brief\w*|short\w*|concise\w*|quick\w*|"
    r"simple|simply|plain|english|language|words|terms|layman'?s?|easy|understand|"
    r"jargon|explain|explanation|walk|through|break|down|mean|means|help|"
    r"bullets?|points?|list\w*|enumerate|extract|table|tabular|tabulate|columns?|"
    r"rows?|items?|lines?|sentences?|form|format|key|main|top|important|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2}|"
    r"without|not|don'?t|no|need|compar\w*|our|standard|standards|position|"
    r"positions|constitution|policy|policies|against|risks?|risky|exposures?|"
    r"concerns?|red|flags?|watch|out|dangers?|pitfalls?|onerous|takeaways)\b",
    re.I)
_PUNCT = re.compile(r"[^\w\s'-]")


@dataclass(frozen=True)
class Presentation:
    task: str = ANSWER
    shape: str = PROSE
    count: int | None = None
    length: str | None = None
    register: str | None = None
    #: "… without comparing it to our standard": the document alone is the subject.
    no_comparison: bool = False
    #: What is left to search for once the instruction's own words are removed.
    topic: str = ""

    @property
    def is_instruction(self) -> bool:
        """The reader asked for a task or a shape, not a plain question."""
        return (self.task != ANSWER or self.shape != PROSE or self.length is not None
                or self.register is not None or self.no_comparison)

    @property
    def document_task(self) -> bool:
        """A task ABOUT THE DOCUMENT (summary, list, explanation, risks): the document
        is its subject, and the company position is not searched for it unless the
        reader brings the organization in."""
        return self.task != ANSWER or self.no_comparison

    @property
    def document_wide(self) -> bool:
        """A document task that names no topic: the whole document is the subject."""
        return self.document_task and not self.topic

    def describe(self) -> str:
        """The PRESENTATION line the prompt carries — the instruction in fixed words."""
        parts = {SUMMARY: "a summary", LIST: "a list of what was asked for, nothing else",
                 EXPLAIN: "an explanation", RISKS: "the provisions that carry risk for "
                 "the reader, described as what they provide"}.get(self.task, "an answer")
        shape = {BULLETS: "as bullet points" + (f", exactly {self.count} of them"
                                                 if self.count else ""),
                 TABLE: "as a table"}.get(self.shape, "in prose")
        extras = []
        if self.length == SHORT:
            extras.append("short — under 60 words")
        if self.register == SIMPLE:
            extras.append("in plain, simple words a non-lawyer understands, keeping "
                          "every condition and exception")
        if self.no_comparison:
            extras.append("what the document says only — no comparison with any "
                          "company position")
        return f"{parts}, {shape}" + ("; " + "; ".join(extras) if extras else "")


def read(question: str) -> Presentation:
    text = (question or "").strip()
    if not text:
        return Presentation()
    count = None
    m = _COUNT.search(text)
    if m:
        raw = m.group(1).lower()
        count = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
    task = (SUMMARY if _SUMMARY.search(text) else RISKS if _RISKS.search(text)
            else EXPLAIN if _EXPLAIN.search(text) else LIST if _LIST.search(text)
            else ANSWER)
    no_comparison = bool(_NO_COMPARISON.search(text))
    if task == ANSWER and no_comparison:
        task = LIST if _LIST.search(text) else EXPLAIN
    # A list of clauses and a set of risks are one item per line unless the reader
    # said otherwise; a summary or an explanation is prose unless they asked for points.
    shape = (TABLE if _TABLE.search(text)
             else BULLETS if _BULLETS.search(text) or count or task in (LIST, RISKS)
             else PROSE)
    topic = " ".join(_INSTRUCTION_WORDS.sub(" ", _PUNCT.sub(" ", text)).split())
    return Presentation(task=task, shape=shape, count=count,
                        length=SHORT if _SHORT.search(text) else None,
                        register=SIMPLE if _SIMPLE.search(text) else None,
                        no_comparison=no_comparison, topic=topic)
