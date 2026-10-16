"""Reading the values a clause STATES — the extraction step of AM-148.

`evaluation.categorical.evaluate_categorical` compares and reads no text (45D); this
reads the CONFIRMED clauses for the standard's configured terms — a closed lexicon,
longest match first, on the same word boundaries as mapping — and nothing else.
"""

from __future__ import annotations

import re

from legalmind.evaluation.categorical import configured
from legalmind.evaluation.contracts import CategoricalFacts, StatedValue
from legalmind.mapping.scoring import normalize


def read_values(clauses, standard: dict) -> CategoricalFacts:
    """The configured values the clauses' own words name, in document order. Longest
    term first: "Bombay High Court" (which §22 itself names, for appeals) claims its
    words, so "Bombay" inside it is never read as a second city."""
    _, recognised = configured(standard)
    terms = sorted(((normalize(t), key) for key, ts in recognised.items() for t in ts),
                   key=lambda tk: -len(tk[0]))
    found: list[tuple[int, int, StatedValue]] = []
    for index, clause in enumerate(clauses):
        body = re.sub(r"\s+", " ", clause.content or "").strip()   # its own casing
        claimed: list[tuple[int, int]] = []
        for term, key in terms:
            for m in re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", body, re.I):
                if any(a < m.end() and m.start() < b for a, b in claimed):
                    continue
                claimed.append(m.span())
                found.append((index, m.start(), StatedValue(key, m.group(0),
                                                            clause.evidence_id)))
    values = tuple(v for *_, v in sorted(found, key=lambda f: (f[0], f[1])))
    return CategoricalFacts(values=values,
                            evidence_refs=tuple(dict.fromkeys(
                                c.evidence_id for c in clauses)))
