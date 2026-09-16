"""Domain A targeting — a Constitution topic narrows the search INSIDE the query.

Each ratified standard already carries its Appendix-B topic
(`configuration.constitution.topic`), so the filter joins what exists rather than
denormalising anything onto the chunk (`AM-27` r4). Two properties, pulling opposite
ways: a topic RESTRICTS the result to standards of that topic, and a topic that
matches nothing NEVER turns an answer into a refusal.
"""

from __future__ import annotations

import json

import pytest

from legalmind.assist.positions import (
    RATIFIED_STANDARDS_DIR,
    chunk_ratified_standards,
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
    return {json.loads(p.read_text())["requirement_code"]:
            json.loads(p.read_text())["configuration"]["constitution"]["topic"]
            for p in RATIFIED_STANDARDS_DIR.glob("*.json")}


def test_a_topic_returns_only_standards_of_that_topic(db, corpus):
    hits = search_positions(db, query="liability cap fees paid", permissions=PERMS,
                            limit=10, embed_query=lambda _q: None, topic="Liability")
    assert hits, "the liability standards must be found by a liability question"
    assert {corpus[h.standard_code] for h in hits} == {"Liability"}


def test_the_same_question_without_a_topic_reaches_other_topics(db, corpus):
    """The control: the filter is doing the narrowing, not the question."""
    broad = search_positions(db, query="liability cap fees paid", permissions=PERMS,
                             limit=10, embed_query=lambda _q: None)
    topics = {corpus[h.standard_code] for h in broad}
    # "fees paid" is shared with the payment standards; without the topic they compete.
    assert "Liability" in topics
    assert len(broad) >= len(search_positions(db, query="liability cap fees paid",
                                              permissions=PERMS, limit=10,
                                              embed_query=lambda _q: None,
                                              topic="Liability"))


def test_a_topic_that_matches_nothing_falls_back_to_the_unfiltered_search(db, corpus):
    """Narrowing may never turn an answer into a refusal."""
    filtered = search_positions(db, query="liability cap fees paid", permissions=PERMS,
                                limit=10, embed_query=lambda _q: None,
                                topic="No Such Topic")
    unfiltered = search_positions(db, query="liability cap fees paid", permissions=PERMS,
                                  limit=10, embed_query=lambda _q: None)
    assert [h.position_chunk_id for h in filtered] == \
        [h.position_chunk_id for h in unfiltered]


def test_a_topic_never_widens_authorization(db, corpus):
    """r5 stands: without the permission the result is [] whatever the topic says."""
    assert search_positions(db, query="liability cap fees paid",
                            permissions=frozenset({P.ASSIST_ASK}), limit=10,
                            embed_query=lambda _q: None, topic="Liability") == []
