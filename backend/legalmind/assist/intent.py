"""Question-shape detection for the assist lane — deterministic, no model, no regex soup.

`AM-25` r4: the assist lane never answers "does this document meet our standard?"
— that belongs to the deterministic evaluator. The screen this replaces was one regex
(`complian[ct]`, `match(es)? our (standard|position)`) and, measured live on 2026-09-08,
it passed every natural phrasing of the question: "compare this document with our
approved legal position", "does this document comply with our standard position",
"what clauses are missing compared with our approved position". Each was then answered
generatively over document chunks and refused as "not found in the selected document" —
a false refusal of the manager's own question.

The shape of a comparison question, per the Constitution's own vocabulary (§24: Accepted /
Deviation; §3.2A: "aligns with the approved position", "identifies deviations"):

    an ORGANIZATION REFERENCE   our / company / approved / standard / position / policy /
                                constitution / baseline / playbook
    AND
    a COMPARISON SIGNAL         a verb (compare, comply, conform, align, meet, satisfy,
that belongs to the deterministic evaluator. The screen this replaces was one regex
                                (deviation, gap, missing, acceptable, unacceptable,
                                compliant, non-compliant, compliance, redline)

Both groups are matched on normalized word stems so "comply / complies / compliant /
compliance / non-compliance" and "deviate / deviation / deviates" collapse together. A
question with only one group is descriptive ("what are our payment obligations under
this contract?" names the organization but asks what the document SAYS) and is answered
from the document. `tests/test_assist_intent.py` pins the matrix both ways.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z]+")

# Stems, not words: prefix-matched against each normalized token.
# Exact matches — a prefix would let "use" and "were" through.
_ORG_PRONOUNS = frozenset({"our", "ours", "us", "we"})
_ORG_STEMS = ("compan", "approv", "standard", "position", "polic",
              "constitution", "baseline", "playbook", "template", "leapswitch", "cloudpe")
_VERB_STEMS = ("compar", "against", "compl", "conform", "align", "meet", "meets",
               "satisf", "deviat", "match", "differ", "accept", "unaccept", "approv",
               "violat", "breach", "consistent", "inconsistent", "conflict")
_NOUN_STEMS = ("deviation", "gap", "missing", "acceptab", "unacceptab", "compliance",
               "compliant", "noncompliant", "redline", "attention", "modif", "risk")

# "approv" appears in both groups on purpose: "our approved position" is an organization
# reference; "can we approve this" is a comparison verb. One token cannot serve as both,
# so a question that only says "approved" once still needs a second signal.


def _stems(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("-", ""))


def _hits(tokens: list[str], stems: tuple[str, ...]) -> set[int]:
    return {i for i, tok in enumerate(tokens) if tok.startswith(stems)}


def is_comparison_question(question: str) -> bool:
    """True when the question asks how the document stands against the organization's
    position — the evaluator's question, never the model's."""
    tokens = _stems(question or "")
    org = _hits(tokens, _ORG_STEMS)
    org |= {i for i, t in enumerate(tokens) if t in _ORG_PRONOUNS}
    signal = _hits(tokens, _VERB_STEMS) | _hits(tokens, _NOUN_STEMS)
    # Two distinct tokens are needed: one token may not carry both roles ("approv").
    return bool(org) and bool(signal) and len(org | signal) >= 2
