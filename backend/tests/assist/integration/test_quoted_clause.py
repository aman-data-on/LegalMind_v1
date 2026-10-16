"""A routed question that QUOTES the open document's clause (`AM-149`).

A manager pasted Clause 13 and asked "is it acceptable based on standard". The
compliance question is the evaluator's (`AM-25` r4) — but the reply listed all 23 of
the document's Findings and said nothing about Clause 13. `quoted_clause` finds the
clause by its own words, so the table shows that clause's Findings and its changes.
"""

from __future__ import annotations

from legalmind.assist import service
from tests.test_analysis import build, storage  # noqa: F401

CLAUSES = [
    "12. Support will be provided on the basis of the ticket raised by the customer.",
    "13. Service Termination: The Customer may terminate the Services by providing 15 days "
    "prior written notice. Leapswitch may terminate the Services only if the Customer fails "
    "to pay undisputed fees for 2 consecutive months.",
    "14. Governing Law: this Agreement is governed by the laws of India.",
]


def _version(build):
    return build.review(CLAUSES).document_version_id


def test_a_pasted_clause_with_its_question_is_that_clause(build, db):
    version = _version(build)
    asked = (CLAUSES[1][4:].replace("15 days", "15 days\n") +
             " is it acceptable based on standard")
    found = service.quoted_clause(db, version, asked)
    assert found is not None
    assert len(found["evidence_ids"]) == 1
    assert found["location"].startswith("§13")
    assert found["changes"] == []              # a clean document records no change


def test_a_question_quoting_no_clause_is_none(build, db):
    version = _version(build)
    assert service.quoted_clause(db, version, "Is our termination position acceptable?") is None
    assert service.quoted_clause(
        db, version, "Leapswitch may terminate the Services only if the weather is bad "
                     "and nobody has paid the electricity bill for three years") is None


def test_no_document_is_none(db):
    assert service.quoted_clause(db, None, CLAUSES[1]) is None
