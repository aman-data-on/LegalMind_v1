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
from dataclasses import dataclass

MIN_POINTS = 3                          # two numbered lines are a sentence, not a list


@dataclass(frozen=True)
class Point:
    n: int
    title: str                          # "Auto-Renewal", what a heading and a note name
    text: str                           # the reader's own words for it, whole


_ITEM = re.compile(r"^\s*\(?(\d{1,2})[.)]\s+(\S.*)$")
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


def enumerate_points(text: str | None) -> list[Point]:
    """The first run numbered 1, 2, 3 ... in `text`, at least `MIN_POINTS` long. A point
    is its numbered line and the lines that continue it, up to the next number or a
    blank line."""
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
    if len(found) < MIN_POINTS:
        return []
    return [Point(n, _TITLE_END.split(body, maxsplit=1)[0].strip()[:70] or f"Point {n}",
                  body) for n, body in found]


def asked(points: list[Point], question: str) -> list[Point]:
    """The points this question is about: those it names ("points 7 to 17", "points 3,
    5 and 9"), else all of them when it asks about the list, else none."""
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
    return list(points) if _ABOUT_THEM.search(q) else []


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
