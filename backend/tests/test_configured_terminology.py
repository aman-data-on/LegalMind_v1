"""Configured terminology must be able to match — the truncated-stem guard.

Mapping and extraction match on WORD BOUNDARIES (`mapping.scoring.contains_phrase`,
whose docstring records why: without them "lien" would match inside "client"). A
term written as a truncated stem therefore matches nothing at all: `terminat` never
matches "termination", `invoic` never matches "invoice", `discontinu` never matches
"discontinuation". The term contributes no score and the loss is silent — the
standard still confirms through its other terms, so no test failed and no verdict
looked wrong. Seven such terms were found on 2026-09-14, all in standards authored
the day before.

The check needs no dictionary: a token is a truncated stem when it does not appear
as a whole word anywhere in the standard's own cited text and terminology, but IS a
strict prefix of a word that does. That is exactly the mistake — the author meant
the longer word.
"""
from __future__ import annotations

import json
import re

import pytest

from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR

_WORD = re.compile(r"[a-z][a-z'-]*")

STANDARDS = sorted(RATIFIED_STANDARDS_DIR.glob("*.json"))
assert STANDARDS, "no ratified standards found"


def _terms(payload: dict) -> list[tuple[str, str]]:
    """(where, term) for every configured term a matcher will see."""
    mr = payload.get("mapping_rules") or {}
    ex = (payload.get("configuration") or {}).get("extraction") or {}
    out = [(k, t) for k in ("exact_phrases", "aliases", "section_heading_terms",
                            "negative_patterns") for t in mr.get(k, [])]
    out += [("keyword_groups", t) for g in mr.get("keyword_groups", []) for t in g]
    out += [(f"extraction.units.{k}", t) for k, v in (ex.get("units") or {}).items() for t in v]
    out += [(f"extraction.bases.{k}", t) for k, v in (ex.get("bases") or {}).items() for t in v]
    for key in ("cap_phrases", "unlimited_phrases", "composite_phrases"):
        out += [(f"extraction.{key}", t) for t in ex.get(key, [])]
    return out


def _vocabulary(payload: dict) -> set[str]:
    """Every word the standard itself writes down — its quoted source, its
    description, its calibration notes and all of its own terms."""
    parts = [payload.get("source_quote") or "", payload.get("description") or ""]
    parts += [str(x) for x in (payload.get("_calibration") or [])]
    parts += [t for _, t in _terms(payload)]
    return set(_WORD.findall(" ".join(parts).lower()))


@pytest.mark.parametrize("path", STANDARDS, ids=lambda p: p.stem)
def test_no_configured_term_is_a_truncated_stem(path):
    payload = json.loads(path.read_text())
    vocabulary = _vocabulary(payload)
    offenders = []
    for where, term in _terms(payload):
        for token in _WORD.findall(term.lower()):
            if token in vocabulary:
                continue
            longer = sorted(w for w in vocabulary if w.startswith(token) and w != token)
            if longer:
                offenders.append(f"{where}: {term!r} -> {token!r} never matches "
                                 f"{longer[0]!r} (matching is word-boundary)")
    assert not offenders, f"{path.name}: " + "; ".join(offenders)
