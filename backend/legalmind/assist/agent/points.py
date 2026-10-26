"""Every point the reader asked about, answered (D1, owner 2026-10-07).

An e-mail with 17 numbered requests and "which of these conflict with our standards?"
was answered on 4 to 6 of them: the model chose which, and nothing counted. Here code
does the counting. The points are read deterministically from the reader's own words,
each is searched on its own, the answer is asked for point by point, and what was
answered is counted against what was asked. A point left unanswered is named, never
silently dropped.
"""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass

MIN_POINTS = 3                          # two numbered lines are a sentence, not a list


@dataclass(frozen=True)
class Point:
    n: int
    title: str                          # "Auto-Renewal", what a heading and a note name
    text: str                           # the reader's own words for it, whole


_ITEM = re.compile(r"^\s*\(?(\d{1,2})[.)]\s+(\S.*)$")
#: an e-mail's asks are as often bulleted as numbered: "• With your mentioned SLA …"
_BULLET = re.compile(r"^\s*[•▪●◦*\-]\s+(\S.*)$")
#: or plain lines the message itself points at: three asks, a blank line, "Please
#: confirm on the above points." (2026-10-14: those three unnumbered asks were lost and
#: the attached quote's own numbered terms were answered in their place)
_HERE = re.compile(r"\b(above|following|below)\s+(?:points?|items?|questions?|queries|"
                   r"requests?|asks?|issues?)\b", re.I)
MAX_PLAIN = 12                          # a longer block is prose, not a list of asks
_FINISHED = re.compile(r"[.?!:;]\s*$")  # a bullet that ends a sentence is not wrapped
_TITLE_END = re.compile(r"\s+[\u2014\u2013-]\s+|:\s")
#: the question is about the list as a whole, not about one thing in it — and not about
#: something that merely shares a word with it: "Which of the TWO has the longer
#: confidentiality period?" (an MSA and an attached NDA) matched a bare "which of", the
#: NDA's 15 numbered clauses became 15 points to answer, the MSA was never read and the
#: turn took 130 s (2026-10-08). "each" and "every" count only before a list noun.
_ABOUT_THEM = re.compile(
    r"\b(?:these|those|the following|points|items|requests|changes|asks|"
    r"(?:each|every) (?:point|item|request|change|ask|one)|"
    r"(?:which|any|all) of them|them all)\b", re.I)
_RANGE = re.compile(r"\bpoints?\s+(\d{1,2})\s*(?:-|\u2013|to|through)\s*(\d{1,2})\b",
                    re.I)
_SOME = re.compile(r"\bpoints?\s+((?:\d{1,2}\s*(?:,|and|&)\s*)+\d{1,2})\b", re.I)


_SUB_CLAUSE = re.compile(r"^\s*\d{1,2}\.\d{1,2}\.?\s", re.M)


def enumerate_points(text: str | None) -> list[Point]:
    """The reader's list in `text`: the first run numbered 1, 2, 3 ..., else the first
    bulleted run, else the plain lines the text calls "the above / following points" —
    each at least `MIN_POINTS` long."""
    return _numbered(text) or _bulleted(text) or _pointed_at(text)


def _points(found: list[list]) -> list[Point]:
    if len(found) < MIN_POINTS:
        return []
    # cut at a word: a title cut mid-word left "**1. … the **" and broke the bold
    return [Point(n, textwrap.shorten(_TITLE_END.split(body, maxsplit=1)[0], 70,
                                      placeholder="…") or f"Point {n}",
                  body) for n, body in found]


def _bulleted(text: str | None) -> list[Point]:
    """The first run of bulleted lines; an unbulleted line right after a bullet continues
    it, and a blank line closes it."""
    found: list[list] = []
    open_ = False
    for line in (text or "").splitlines():
        m = _BULLET.match(line)
        if m:
            found.append([len(found) + 1, m.group(1).strip()])
            open_ = True
        elif not line.strip():
            open_ = False
        elif open_ and found and not _FINISHED.search(found[-1][1]):
            found[-1][1] += " " + line.strip()                    # a wrapped line
        elif len(found) >= MIN_POINTS:
            break                       # "Please confirm on the above points." closes it
        else:
            found, open_ = [], False
    return _points(found)


def _pointed_at(text: str | None) -> list[Point]:
    """One point per line of the block the text points at: "the above points" — the
    lines before the reference in its own block, else the block before it; "the
    following / below points" — the lines after it, else the block after it."""
    lines = (text or "").splitlines()
    blocks: list[list[int]] = [[]]
    for i, line in enumerate(lines):
        if line.strip():
            blocks[-1].append(i)
        elif blocks[-1]:
            blocks.append([])
    # every reference is tried: "the client asked me about below points" may open the
    # message and point at a salutation, while "the above points" closes it
    for ref, line in enumerate(lines):
        match = _HERE.search(line)
        if match is None:
            continue
        at = next(k for k, b in enumerate(blocks) if ref in b)
        if match.group(1).lower() == "above":
            own = [i for i in blocks[at] if i < ref]
            chosen = own if len(own) >= MIN_POINTS else (blocks[at - 1] if at else [])
        else:
            own = [i for i in blocks[at] if i > ref]
            chosen = own if len(own) >= MIN_POINTS else (
                blocks[at + 1] if at + 1 < len(blocks) else [])
        found = _points([[n, lines[i].strip()] for n, i in enumerate(chosen, 1)])
        if found and len(chosen) <= MAX_PLAIN:
            return found
    return []


def _numbered(text: str | None) -> list[Point]:
    """The first run numbered 1, 2, 3 ... A point is its numbered line and the lines
    that continue it, up to the next number or a blank line. An agreement's own
    sections — numbered headings over 1.1, 1.2 … — are not a list of requests: an
    attached addendum's seven section headings were answered as "your message lists 7
    points" (2026-10-14); this also covers a pasted contract."""
    if len(_SUB_CLAUSE.findall(text or "")) >= MIN_POINTS:
        return []
    found: list[list] = []
    open_ = False
    for line in (text or "").splitlines():
        m = _ITEM.match(line)
        if m and int(m.group(1)) == len(found) + 1:
            found.append([int(m.group(1)), m.group(2).strip()])
            open_ = True
        elif m and int(m.group(1)) == 1 and len(found) < MIN_POINTS:
            found, open_ = [[1, m.group(2).strip()]], True       # a list starts again
        elif m and found:
            break                                                # the run is over
        elif not line.strip():
            open_ = False
        elif open_ and found:
            found[-1][1] += " " + line.strip()
    return _points(found)


#: An EARLIER turn's list is taken up only when the question names it as a list: "the
#: changes we should make to termination" had re-answered a 10-point e-mail from two
#: turns before (code review 2026-10-26).
_NAMES_THE_LIST = re.compile(
    r"\b(?:the|these|those|all|each|every|remaining|other|above)\s+(?:points?|items?|"
    r"asks?|requests?)\b|\bthe (?:above|list)\b|\b(?:all|each) of (?:them|these)\b",
    re.I)


def asked(points: list[Point], question: str, *, earlier: bool = False) -> list[Point]:
    """The points this question is about: those it names ("points 7 to 17", "points 3,
    5 and 9"), else all of them when it asks about the list, else none. An `earlier`
    turn's list is about the question only when the question names it as a list."""
    if len(points) < MIN_POINTS:
        return []
    q = question or ""
    m = _RANGE.search(q)
    if m:
        a, b = sorted(int(x) for x in m.groups())
        return [p for p in points if a <= p.n <= b]
    m = _SOME.search(q)
    if m:
        want = {int(x) for x in re.findall(r"\d{1,2}", m.group(1))}
        return [p for p in points if p.n in want]
    return list(points) if (_NAMES_THE_LIST if earlier else _ABOUT_THEM).search(q) else []


def answered(blocks: list[dict], kinds: frozenset[str] | set[str]) -> set[int]:
    """The point numbers at least one answering block (of `kinds`) is about. Restating
    what the point asks (user_stated) is not answering it: when every substantive block
    of a point fails its checks, the point is asked again, then named."""
    return {b["point"] for b in blocks
            if isinstance(b.get("point"), int) and b.get("kind") in kinds
            and b.get("kind") != "user_stated"}


def coverage_line(asked_: list[Point], answered_: set[int]) -> str:
    """What the reply covers, said first — the count the reader can check."""
    done = sum(p.n in answered_ for p in asked_)
    if done == len(asked_):
        return (f"Your message lists {len(asked_)} points; each is answered below, "
                "in order.")
    return (f"Your message lists {len(asked_)} points; {done} are answered below, in "
            "order, and the rest are listed at the end.")


def missing_line(missing: list[Point]) -> str:
    names = "; ".join(f"{p.n}. {p.title}" for p in missing)
    numbers = ", ".join(str(p.n) for p in missing)
    return (f"Not answered in this reply: {names}. Ask \"answer points {numbers}\" and "
            "I'll take them on their own.")


#: A point's own lettered asks: "(a) the billing basis; (b) whether public IP …" (D3,
#: `AM-202`). Read in order from (a); a stray "(d)" in a sentence is not a list.
_SUB = re.compile(r"\(([a-h])\)\s")


def sub_items(text: str) -> list[str]:
    """The letters of a point's sub-asks, (a) onwards in order, at least two."""
    found: list[str] = []
    for letter in _SUB.findall(text or ""):
        if ord(letter) - ord("a") == len(found):
            found.append(letter)
    return found if len(found) >= 2 else []


def uncovered_subs(asked_: list[Point], blocks: list[dict]) -> list[str]:
    """Each asked point's sub-asks that no block of that point names by its letter —
    "1(b)" — so a point answered in one generic line is not counted as whole."""
    out = []
    for p in asked_:
        said = " ".join(b.get("text", "") for b in blocks if b.get("point") == p.n)
        out += [f"{p.n}({s})" for s in sub_items(p.text) if f"({s})" not in said]
    return out


def uncovered_line(subs: list[str]) -> str:
    return (f"Sub-points not answered on their own: {', '.join(subs)}. Ask about any of "
            "them and I'll take it on its own.")


_WORD = re.compile(r"[a-z0-9]{3,}")
_STOP = frozenset({"the", "and", "for", "our", "that", "this", "with", "are", "not",
                   "does", "state", "documents", "confirm", "leapswitch", "position",
                   "company", "msa", "agreements", "any", "its", "from", "will", "all"})
#: A block names its point when it shares this many content words with the point.
MATCH_WORDS = 2


def _words(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower())) - _STOP


def assign_points(blocks: list[dict], asked: list[Point]) -> list[dict]:
    """Blocks the model left without a "point", placed on the asked point their words
    match (`AM-202`): DeepSeek answered 16 points in order with no point numbers and the
    count read 0 of 16 (2026-10-22). Never backwards — the answer runs in the reader's
    order — and a block with no match stays on the point before it."""
    order = [p.n for p in asked]
    words = {p.n: _words(p.text) for p in asked}
    current: int | None = None
    out = []
    for b in blocks:
        if isinstance(b.get("point"), int) or not asked:
            current = b.get("point") if b.get("point") in order else current
            out.append(b)
            continue
        said = _words(b.get("text", ""))
        ahead = order[order.index(current):] if current in order else order
        best = max(ahead, key=lambda n: len(said & words[n]))
        if len(said & words[best]) >= MATCH_WORDS:
            current = best
        out.append({**b, "point": current} if current is not None else b)
    return out
