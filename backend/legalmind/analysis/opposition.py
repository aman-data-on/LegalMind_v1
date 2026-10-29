"""QA-001 (2026-10-29): a clause that states the OPPOSITE of a presence position.

Keyword co-occurrence confirms that a clause is on the topic; it never read which way
the clause points, so "The Customer shall be the owner of the Services" confirmed
LeapSwitch's ownership and MATCHED. These are grammar of the ratified positions and the
Constitution's "Unacceptable" lines: who owns the Services, whether indirect loss is
excluded, whether disputes go to arbitration, whether suspension for non-payment comes
with notice, whether Indian law governs. A hit is an opposing signal, so the clause is a
DEVIATION for Legal — never Acceptable, never a new position. Keyed by the standard's
``scope_key``. An indemnity we give is read against §10's causes by
`service.our_indemnity_beyond`, not here.
"""

from __future__ import annotations

import re
from uuid import UUID

from legalmind.mapping.engine import Clause, Signal

_THEM = r"(?:the\s+)?(?:customer|client|buyer|purchaser)"
#: A word that negates or excludes in the same sentence.
_NEGATION = re.compile(r"\b(?:no|not|neither|nor|never|exclud\w*|except)\b|"
                       r"\bin\s+no\s+event\b|\bunder\s+no\s+circumstances\b", re.I)


def _foreign_law(sentence: str) -> bool:
    return (re.search(r"\b(?:governed|construed|interpreted)\b[^.;]{0,80}?\blaws?\b",
                      sentence, re.I) is not None
            and re.search(r"\bindian?\b", sentence, re.I) is None)


def _indirect_loss_owed(sentence: str) -> bool:
    return (re.search(r"\bliab(?:le|ility)\b", sentence, re.I) is not None
            and re.search(r"\b(?:indirect|consequential)\b", sentence, re.I) is not None
            and re.search(r"\b(?:shall|will|is|are)\s+(?:be\s+)?(?:fully\s+)?liable\b",
                          sentence, re.I) is not None
            and _NEGATION.search(sentence) is None)


_OPPOSES = {
    "IP_OWNERSHIP": re.compile(
        rf"\b{_THEM}\s+(?:is|shall\s+be|will\s+be|shall\s+remain|becomes|shall\s+become)\s+"
        r"the\s+(?:sole\s+(?:and\s+exclusive\s+)?)?owner\b[^.;]{0,120}?"
        r"\b(?:the\s+services|the\s+platform|the\s+software)\b|"
        r"\b(?:the\s+services|the\s+platform|the\s+software)\b[^.;]{0,120}?"
        rf"\b(?:vest\w*\s+(?:solely\s+)?in|owned\s+by)\s+{_THEM}\b", re.I),
    "ARBITRATION": re.compile(
        r"\b(?:shall|will|may)\s+not\s+(?:be\s+)?(?:referred|submitted|subject(?:ed)?|"
        r"resolved|settled|resort)\b[^.;]{0,40}?\barbitrat\w*|"
        r"\bno\s+(?:dispute|claim|matter|difference)s?\b[^.;]{0,120}?"
        r"\b(?:shall|will|may)\s+be\s+(?:referred|submitted)\s+to\s+arbitrat\w*", re.I),
    "SUSPENSION_NOTICE_AND_CURE": re.compile(
        r"\bsuspen\w*\b[^.;]{0,160}?\b(?:without|with\s+no|no)\s+(?:(?:any|prior|advance|"
        r"further|written)\s+)*(?:notice|cure)\b|"
        r"\bnot\s+(?:be\s+)?(?:required|obliged|obligated|bound)\s+to\s+(?:give|provide|"
        r"serve)\b[^.;]{0,60}?\bnotice\b[^.;]{0,60}?\bsuspen\w*", re.I),
}
_PAYMENT = re.compile(r"\b(?:non[\s-]?payment|payment|overdue|unpaid|dues|fees)\b", re.I)
_TESTS = {
    "GOVERNING_LAW": _foreign_law,
    "CONSEQUENTIAL_DAMAGES_EXCLUSION": _indirect_loss_owed,
}


def opposes(scope_key: str | None, sentence: str) -> bool:
    """Whether ``sentence`` states the opposite of the position ``scope_key`` names."""
    if scope_key in _TESTS:
        return _TESTS[scope_key](sentence)
    pattern = _OPPOSES.get(scope_key or "")
    if pattern is None or not pattern.search(sentence):
        return False
    return scope_key != "SUSPENSION_NOTICE_AND_CURE" or bool(_PAYMENT.search(sentence))


def opposing_signals(clauses: list[Clause], scope_key: str | None, threshold: int,
                     sentences) -> dict[UUID, tuple[Signal, ...]]:
    """An opposing signal on each clause with a sentence that ``opposes`` the position,
    confirmed at the threshold like a configured waiver phrase (`waiver_signals`)."""
    if scope_key not in _OPPOSES and scope_key not in _TESTS:
        return {}
    out: dict[UUID, tuple[Signal, ...]] = {}
    for clause in clauses:
        hit = next((s for s in sentences(clause.content) if opposes(scope_key, s)), None)
        if hit is not None:
            out[clause.evidence_id] = (Signal(
                "waiver_pattern", f"the clause states the opposite; span: {hit[:160]}",
                threshold),)
    return out
