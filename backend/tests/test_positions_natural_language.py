"""A reader's own wording must reach a ratified position that exists.

Reported from the live site, 2026-09-16: "Explain our termination standard." answered
"Information not found in the organization's approved positions", while "What standards
do we require for liability?" answered fully and cited `LIABILITY-MSA-001`. Termination
standards ARE ratified — `CONVENIENCE-NOTICE-MSA-001`, `CURE-PERIOD-MSA-001`,
`TERM-NOTICE-NDA-001`, `EARLY-TERM-RESTRICTION-MSA-001` — so this was retrieval, not
ratification, and not an authorization refusal.

The cause is the match floor. Lexemes are OR-ed and a chunk must share at least two of
them (`positions.py`), which is what stops one common word fetching the corpus. But the
floor counts EVERY lexeme of the question, including the ones carrying no retrieval
signal: "explain our termination standard" stems to {explain, termin, standard}, so the
floor is 2 while every termination chunk shares exactly one — `termin`. The liability
question worked by accident: `LIABILITY-MSA-001`'s quote literally contains the word
"standard", which gave it a second match.

These run against the REAL ratified corpus, not a synthetic fixture, because the defect
is a property of the real text: how many chunks carry "standard" is the whole question.
`embed_query` is stubbed to None throughout — `search_positions` lets the gated vector
branch decide whenever it finds anything, so a machine with the embedding model
provisioned would mask what is asserted here.
"""

from __future__ import annotations

import pytest

from legalmind.security import permissions as P

PERMS = frozenset({P.ASSIST_ASK, P.CONFIGURATION_VIEW})

# The ratified standards that state the organization's termination positions.
TERMINATION_CODES = {
    "CONVENIENCE-NOTICE-MSA-001",
    "CURE-PERIOD-MSA-001",
    "TERM-NOTICE-NDA-001",
    "EARLY-TERM-RESTRICTION-MSA-001",
}

# Natural phrasings of one question. None is special-cased anywhere: the fix is to the
# floor, so any wording whose distinctive word is "termination" has to work.
TERMINATION_QUESTIONS = (
    "Explain our termination standard.",
    "What is our termination standard?",
    "What does our standard say about termination?",
    "What is the termination notice requirement?",
)


@pytest.fixture
def real_corpus(db, user):
    """The ratified standards, imported and chunked exactly as production does."""
    import tools.import_ratified_standards as imp
    from legalmind.assist.positions import (
        RATIFIED_STANDARDS_DIR,
        chunk_ratified_standards,
    )
    from tools.import_ratified_standards import import_standards

    original = imp.RATIFIED_STANDARDS_DIR
    imp.RATIFIED_STANDARDS_DIR = RATIFIED_STANDARDS_DIR
    try:
        import_standards(db, actor_email=user.email)
    finally:
        imp.RATIFIED_STANDARDS_DIR = original
    chunk_ratified_standards(db)
    return db


def _search(db, query: str, limit: int = 5):
    from legalmind.assist.positions import search_positions

    return search_positions(db, query=query, permissions=PERMS, limit=limit,
                            embed_query=lambda _q: None)


@pytest.mark.parametrize("question", TERMINATION_QUESTIONS)
def test_a_natural_question_about_termination_reaches_a_termination_standard(
        real_corpus, question):
    hits = _search(real_corpus, question)
    assert hits, f"{question!r} retrieved nothing at all"
    codes = {h.standard_code for h in hits}
    assert codes & TERMINATION_CODES, (
        f"{question!r} retrieved {sorted(codes)}, none of which states a termination "
        f"position")


def test_the_liability_question_that_already_worked_still_works(real_corpus):
    """The control. It passed before the fix by accident — its quote happens to contain
    the word "standard" — and must still pass after it."""
    hits = _search(real_corpus, "What standards do we require for liability?")
    assert {h.standard_code for h in hits} & {"LIABILITY-MSA-001", "LIABILITY-TOS-001"}


def test_a_question_naming_no_subject_still_retrieves_nothing(real_corpus):
    """The floor exists so one incidental word cannot fetch a position, and the relaxed
    second pass must not undo that.

    "Explain our standard." is the case that keeps the two apart. Its only lexeme present
    in the corpus is `standard`, which occurs in exactly ONE chunk — inside a liability
    quote that happens to use the word. That is not a subject the organization holds a
    position about, so the relaxed pass does not admit it and the question is still
    refused. Were the second pass a plain floor of 1, this would answer a question about
    "our standard" with the liability cap.

    Not asserted here: "What is the company position?", which retrieves at the STRICT
    floor today (compani and posit are each in 6 chunks, so it never reaches the second
    pass) and is unchanged by this fix."""
    assert _search(real_corpus, "Explain our standard.") == []


def test_the_sanitized_internal_locators_stay_unsearchable(real_corpus):
    """`test_assist_positions_sanitization` asserts these retrieve nothing at floor 2.
    The tokens were removed from the chunk text, so they must still retrieve nothing at a
    relaxed floor — otherwise the relaxation, rather than the chunker, is what protects
    them."""
    for query in ("docs md pdf", "legalmind_source_material_dir", "repository docs md"):
        assert _search(real_corpus, query) == [], f"{query!r} retrieves a position"
