"""Domain A — a position about another kind of paper is not an answer.

The defect these pin, reported live 2026-09-18: "what is written about partner
agreement in the constitution" returned AUTORENEW-MSA-001, CURE-PERIOD-MSA-001 and
SUSPENSION-NOTICE-CURE-MSA-001 under the sentence "The organization's approved
position relevant to this question is quoted below, verbatim from the ratified
standard." Zero Partner Agreement standards are ratified — or even proposed — so
there was no better-ranked answer being missed. MSA positions were presented as the
organization's position on a Partner Agreement question.

That is a fail-open of rule 15 and of `AM-25` r4, so the test that matters is the
REFUSAL one: narrowing here is permitted to end in "we hold no position", because a
position about the wrong document type is wrong, not weak.
"""

from __future__ import annotations

import json

import pytest

from legalmind.assist.positions import (
    RATIFIED_STANDARDS_DIR,
    chunk_ratified_standards,
    coverage,
    named_document_type,
    search_positions,
)
from legalmind.security import permissions as P

PERMS = frozenset({P.ASSIST_ASK, P.CONFIGURATION_VIEW})


@pytest.fixture
def corpus(db, user):
    import tools.import_ratified_standards as imp
    from tools.import_ratified_standards import import_standards

    original = imp.RATIFIED_STANDARDS_DIR
    imp.RATIFIED_STANDARDS_DIR = RATIFIED_STANDARDS_DIR
    try:
        import_standards(db, actor_email=user.email)
    finally:
        imp.RATIFIED_STANDARDS_DIR = original
    chunk_ratified_standards(db)
    return {json.loads(p.read_text())["configuration"]["document_type"]
            for p in RATIFIED_STANDARDS_DIR.glob("*.json")}


@pytest.mark.parametrize("question,expected", [
    ("what is written about partner agreement in the constitution",
     "PARTNER_AGREEMENT"),
    ("What does our Channel Partner Agreement say about termination?",
     "PARTNER_AGREEMENT"),
    ("what is our vendor agreement position", "VENDOR_AGREEMENT"),
    # The bare subject of a §31 family names its paper (live phrasing, 2026-09-18).
    ("what does our constitution say about partners", "PARTNER_AGREEMENT"),
    ("who handles support for partner customers", "PARTNER_AGREEMENT"),
    # ...but a partner question that also names another type narrows nothing.
    ("what does the MSA say about partner obligations", None),
    ("what is the termination notice period in the MSA", "MSA"),
    ("our master services agreement liability cap", "MSA"),
    ("what does the NDA say about residuals", "NDA"),
    # Named nothing — the common case, which must stay on its existing path.
    ("what is the termination notice period", None),
    # "agreement" alone is not a document type. Matching it would refuse nearly
    # every question, which is how a fail-closed fix becomes its own outage.
    ("what does this agreement say about liability", None),
    # Two types named is not a narrowing this function may pick between.
    ("does our MSA say the same as the order form", None),
])
def test_named_document_type(question, expected):
    assert named_document_type(question) == expected


def test_partner_agreement_question_retrieves_no_position(corpus, db):
    """THE REPORTED DEFECT. No Partner Agreement standard is ratified, so the honest
    result is nothing — not three MSA positions."""
    hits = search_positions(
        db, query="what is written about partner agreement in the constitution",
        permissions=PERMS, limit=3, embed_query=lambda _q: None)
    assert hits == [], [h.standard_code for h in hits]


def test_a_named_type_we_do_hold_still_answers(corpus, db):
    """The guard must not become an outage: MSA is covered, so an MSA question still
    retrieves, and retrieves ONLY MSA."""
    hits = search_positions(db, query="what is the notice period in the MSA",
                            permissions=PERMS, limit=3, embed_query=lambda _q: None)
    assert hits, "an MSA question retrieved nothing"
    assert {h.document_type for h in hits} == {"MSA"}


def test_coverage_names_the_types_held_and_not_the_ones_missing(corpus, db):
    held = coverage(db)
    assert "MSA" in held and "NDA" in held
    assert "PARTNER_AGREEMENT" not in held
    assert set(held) <= corpus
