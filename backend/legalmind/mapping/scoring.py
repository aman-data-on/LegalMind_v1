"""Deterministic candidate scoring — locked Step 35.8.

Locked 35.1/35.2: mapping is deterministic; no LLM, RAG, vector database or
semantic AI. Locked 35.19: no opaque confidence score may be the basis of a V1
legal conclusion — which is why every score here carries the exact list of
signals that produced it (35.18, "every confirmed mapping records its
deterministic explanation/evidence").

Same inputs + same rule version => same score, always (ENG-11).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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


def normalize(text: str) -> str:
    """Case and whitespace folding only. No stemming, no synonym expansion:
    terminology is configuration (35.4), not something the engine invents.

    Public because the fact extractor matches configured phrases too, and the
    boundary semantics below must be identical in both layers rather than
    reimplemented.
    """
    return re.sub(r"\s+", " ", text or "").strip().lower()


def contains_phrase(haystack: str, needle: str) -> bool:
    """Whole-phrase containment on word boundaries.

    Boundaries matter: without them 'lien' would match inside 'client', which is
    exactly the false-positive class locked 35.5 exists to prevent.
    """
    n = normalize(needle)
    if not n:
        return False
    return re.search(rf"(?<!\w){re.escape(n)}(?!\w)", haystack) is not None


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

    for phrase in rules.exact_phrases:
        if _contains_phrase(body, phrase):
            signals.append(Signal("exact_phrase", phrase, w["exact_phrase"]))

    for alias in rules.aliases:
        if _contains_phrase(body, alias):
            signals.append(Signal("alias", alias, w["alias"]))

    for group in rules.keyword_groups:
        # A group scores only when EVERY term in it is present (35.4).
        if group and all(_contains_phrase(body, term) for term in group):
            signals.append(
                Signal("keyword_group", " + ".join(group), w["keyword_group"]))

    if heading:
        for term in rules.section_heading_terms:
            if _contains_phrase(heading, term):
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
