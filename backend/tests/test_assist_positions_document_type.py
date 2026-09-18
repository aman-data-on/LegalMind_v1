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


def test_partner_agreement_question_answers_from_partner_positions(corpus, db):
    """THE REPORTED DEFECT, now ANSWERED rather than merely refused.

    On 2026-09-18 this question returned three MSA standards. The first fix made it
    refuse — honest, but useless to the reader. The owner then resolved C-23
    (Constitution-final text is ratified), so §31's Partner Agreement positions exist
    and the question answers from them. What must never come back is an MSA position.
    """
    hits = search_positions(
        db, query="what is written about partner agreement in the constitution",
        permissions=PERMS, limit=3, embed_query=lambda _q: None)
    assert hits, "the Partner Agreement question retrieved nothing"
    assert {h.document_type for h in hits} == {"PARTNER_AGREEMENT"}, \
        [(h.standard_code, h.document_type) for h in hits]


def test_the_three_reported_msa_standards_never_come_back(corpus, db):
    """The exact regression — the three codes the owner's screenshot showed."""
    reported = {"AUTORENEW-MSA-001", "CURE-PERIOD-MSA-001",
                "SUSPENSION-NOTICE-CURE-MSA-001"}
    hits = search_positions(
        db, query="what is written about partner agreement in the constitution",
        permissions=PERMS, limit=10, embed_query=lambda _q: None)
    assert reported.isdisjoint({h.standard_code for h in hits})


def test_partner_positions_cite_their_constitution_section(corpus, db):
    """A usable answer cites §31.x, so the section must survive into the hit."""
    hits = search_positions(db, query="partner agreement termination notice",
                            permissions=PERMS, limit=5, embed_query=lambda _q: None)
    assert hits
    assert all((h.source_clause or "").startswith("§31") for h in hits), \
        [(h.standard_code, h.source_clause) for h in hits]


def test_no_standard_is_ratified_for_the_not_adopted_section():
    """§31.6a says the L1/L2/L3 structure is NOT CURRENTLY ADOPTED, and that LegalMind
    'must NOT flag the absence of an L1/L2/L3 structure as a deviation in any
    document'. Ratifying it would state a position the Constitution itself disclaims —
    the same fail-open as the reported bug, one layer up. The `NOT_ADOPTED` basis
    exists precisely so this stays visible and refusable."""
    import json
    for path in RATIFIED_STANDARDS_DIR.glob("*.json"):
        block = (json.loads(path.read_text())["configuration"]
                 .get("constitution") or {})
        assert block.get("section") != "31.6a", path.name
        assert block.get("basis") != "NOT_ADOPTED", path.name


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
    # Every §31 document type is ratified (`AM-72`, owner 2026-09-18).
    for document_type in ("PARTNER_AGREEMENT", "VENDOR_AGREEMENT",
                          "DISTRIBUTION_AGREEMENT", "ORDER_FORM", "AMENDMENT"):
        assert document_type in held, document_type
    # Step 6 carries types the Constitution states no position for; those still refuse.
    assert "DPA" not in held
    assert set(held) <= corpus


def test_a_type_with_no_position_still_refuses_honestly(corpus, db):
    """The refusal path did not become dead code when the §31 types started answering.

    It is still the right answer for a type nothing is ratified for. DPA is that type:
    Step 6 carries it, the Constitution states no position for it, so the honest reply
    is "no approved position covers DPA" plus the list of types that ARE covered — not
    the nearest-scoring MSA clause, which is the defect this file exists for.
    """
    hits = search_positions(db, query="what does our data processing agreement say",
                            permissions=PERMS, limit=3, embed_query=lambda _q: None)
    assert hits == [], [(h.standard_code, h.document_type) for h in hits]


@pytest.mark.parametrize("question,expected_type", [
    ("what is our vendor agreement position on subcontractors", "VENDOR_AGREEMENT"),
    ("what does the distribution agreement say about territory",
     "DISTRIBUTION_AGREEMENT"),
    ("what is written about partner agreement in the constitution", "PARTNER_AGREEMENT"),
    ("does a purchase order override the MSA", "ORDER_FORM"),
])
def test_every_ratified_section_31_type_answers_from_its_own_positions(
        corpus, db, question, expected_type):
    """The owner's requirement in one test: each §31 type answers, and answers ONLY
    from its own positions — no MSA noise on a Partner question."""
    hits = search_positions(db, query=question, permissions=PERMS, limit=3,
                            embed_query=lambda _q: None)
    assert hits, f"{question!r} retrieved nothing"
    assert {h.document_type for h in hits} == {expected_type}, \
        [(h.standard_code, h.document_type) for h in hits]
