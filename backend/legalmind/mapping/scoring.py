"""Deterministic candidate scoring — locked Step 35.8.

Locked 35.1/35.2: mapping is deterministic; this module's own scoring uses no
LLM, RAG, vector database or semantic AI. `AM-54` (owner, 2026-09-09) adds ONE
further signal source — `analysis/semantic.py`, a grounded semantic
confirmation verified on a verbatim span of the clause — which enters through
`map_requirement`'s `extra_signals` and is scored, thresholded and explained
exactly like a configured phrase. Locked 35.19 still holds: no opaque confidence
score is ever the basis of a legal conclusion — a similarity score only
shortlists, and a confirmation carries the model identity, the payload hash
and the span that justifies it (35.18, "every confirmed mapping records its
deterministic explanation/evidence").

Same inputs + same rule version => same score, always (ENG-11).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from legalmind.mapping.rules import MappingRules


@dataclass(frozen=True)
class Signal:
    """One deterministic reason the score moved. This is the explanation."""

    kind: str
    matched: str
    delta: int


@dataclass(frozen=True)
class CandidateScore:
    score: int
    signals: tuple[Signal, ...] = field(default_factory=tuple)

    @property
    def explanation(self) -> list[str]:
        """Human-readable derivation — 35.8's worked example."""
        return [f"{s.kind}: {s.matched!r} ({s.delta:+d})" for s in self.signals]


def _equivalences() -> tuple[re.Pattern[str], dict[str, str]]:
    """The configured equivalences (`config/mapping/equivalences.json`, AB-104): one
    pattern of every variant, longest first, on word boundaries."""
    path = Path(__file__).resolve().parents[2] / "config/mapping/equivalences.json"
    table = {" ".join(v.lower().split()): " ".join(e["canonical"].lower().split())
             for e in json.loads(path.read_text())["equivalences"] for v in e["variants"]}
    alternatives = "|".join(re.escape(v) for v in sorted(table, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternatives})\b"), table


_EQUIVALENT, _CANONICAL = _equivalences()


def normalize(text: str) -> str:
    """Case and whitespace folding, then the configured equivalences — terminology is
    configuration (35.4 as amended by AB-104), never something the engine invents, and
    the same table reads the contract and every configured phrase, so a standard's
    "remedy such default within" also reads "remedy it within". A phrase's last word is
    read in its regular inflections at match time (`phrase_pattern`, `AM-151`).

    Public because the fact extractor matches configured phrases too, and the
    boundary semantics below must be identical in both layers rather than
    reimplemented.
    """
    folded = re.sub(r"\s+", " ", text or "").strip().lower()
    return _EQUIVALENT.sub(lambda m: _CANONICAL[m.group(0)], folded)


def phrase_pattern(needle: str) -> str:
    """The regex for one configured phrase: whole words, and its LAST word in any
    regular inflection (`AM-151`, owner 2026-10-16). The early-exit standard's
    "early termination charge" missed a customer's "early termination charges" — so
    in a phrase of two or more words "charge" also reads charges, charged, charging.
    A one-word term reads its plural only ("fee" fees, "liability" liabilities): its
    other forms are other words ("limit" is not "Private Limited", "invoice" is not
    "invoicing" — `AM-155`, measured on the supplied NDA and MSA). Inner words stay
    exact; a last word under three letters, or not alphabetic, stays exact ("gst").
    """
    *head, last = needle.split(" ")
    if len(last) < 3 or not last.isalpha():
        return rf"(?<!\w){re.escape(needle)}(?!\w)"
    if last.endswith("y") and last[-2] not in "aeiou":      # liability, apply
        stem, tail = last[:-1], "(?:y|ies|ied|ying)" if head else "(?:y|ies)"
    elif not head:                                          # fee, cap, notice
        stem, tail = last, "(?:s|es)?"
    elif last.endswith("e"):                                # charge, terminate
        stem, tail = last[:-1], "(?:e|es|ed|ing)"
    else:                                                   # cure period, refund
        stem, tail = last, "(?:s|es|ed|ing)?"
    prefix = re.escape(" ".join(head) + " ") if head else ""
    return rf"(?<!\w){prefix}{re.escape(stem)}{tail}(?!\w)"


def contains_phrase(haystack: str, needle: str) -> bool:
    """Whole-phrase containment on word boundaries (and its last word's regular
    inflections, `phrase_pattern`).

    Boundaries matter: without them 'lien' would match inside 'client', which is
    exactly the false-positive class locked 35.5 exists to prevent.
    """
    n = normalize(needle)
    if not n:
        return False
    return re.search(phrase_pattern(n), haystack) is not None


def _occurrences(haystack: str, needle: str):
    """Every whole-phrase occurrence, on `contains_phrase`'s boundaries."""
    n = normalize(needle)
    return re.finditer(phrase_pattern(n), haystack) if n else iter(())


# Retained as private aliases so existing call sites and tests keep working.
_normalize = normalize
_contains_phrase = contains_phrase


def score_clause(
    rules: MappingRules,
    *,
    content: str,
    section_title: str | None = None,
) -> CandidateScore:
    """Score one clause against one Requirement's mapping rules.

    Signal order is fixed so the explanation is byte-stable across runs.
    """
    body = _normalize(content)
    heading = _normalize(section_title or "")
    w = rules.weights
    signals: list[Signal] = []

    # Longest match wins (AM-147): one passage of text is ONE phrase, scored once.
    # "intellectual property rights" also holds the alias "intellectual property",
    # and "shall be governed by" both "shall be governed" and "governed by"; scored
    # twice, a liability carve-out naming IP infringement reached the threshold for
    # IP OWNERSHIP on its own words, and a Force Majeure row confirmed governing law.
    # A phrase scores when it occurs somewhere no longer phrase already claimed.
    claimed: list[tuple[int, int]] = []
    phrases = [("exact_phrase", p) for p in rules.exact_phrases] + \
        [("alias", a) for a in rules.aliases]
    scored: set[tuple[str, str]] = set()
    for kind, phrase in sorted(phrases, key=lambda kp: -len(_normalize(kp[1]))):
        free = [m.span() for m in _occurrences(body, phrase)
                if not any(a < m.end() and m.start() < b for a, b in claimed)]
        if free:
            claimed += free
            scored.add((kind, phrase))
    for kind, phrase in phrases:                  # the configured order, byte-stable
        if (kind, phrase) in scored:
            signals.append(Signal(kind, phrase, w[kind]))

    for group in rules.keyword_groups:
        # A group scores only when EVERY term in it is present (35.4).
        if group and all(_contains_phrase(body, term) for term in group):
            signals.append(
                Signal("keyword_group", " + ".join(group), w["keyword_group"]))

    if heading:
        # A heading term is a configured label, matched exactly: inflected, one
        # heading word scored twice ("INVOICING" as both "invoice" and "invoicing")
        # and a bare heading confirmed on its own (`AM-155`).
        for term in rules.section_heading_terms:
            if re.search(rf"(?<!\w){re.escape(_normalize(term))}(?!\w)", heading):
                signals.append(
                    Signal("section_heading", term, w["section_heading"]))

    # 35.5 — negative patterns subtract. Applied last so the explanation reads
    # as "matched X, but negative pattern Y".
    for pattern in rules.negative_patterns:
        if _contains_phrase(body, pattern):
            signals.append(
                Signal("negative_pattern", pattern, w["negative_pattern"]))

    return CandidateScore(score=sum(s.delta for s in signals),
                          signals=tuple(signals))
