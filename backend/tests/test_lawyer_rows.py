"""R2 step 0 / D1 / D2 / D4 / D5 / D6 — pure functions, synthetic clauses (no legal
content: illustrative wording only, rule 21)."""
from __future__ import annotations

from uuid import uuid4

from legalmind.analysis import lawyer_rows as L
from legalmind.mapping.engine import Clause


def _c(number: str, text: str, marks: dict | None = None) -> Clause:
    return Clause(evidence_id=uuid4(), content=f"{number} {text}", section_number=number,
                  marks=marks)


OURS = [
    _c("1", "Definitions"),
    _c("1.1", "“Widget” means the thing described in the order form."),
    _c("2", "Billing"),
    _c("2.1", "The Customer shall raise any invoice dispute within 5 days of the invoice."),
    _c("2.2", "An invoice error must be raised as a dispute within 5 days."),
    _c("2.3", "The Customer shall pay every invoice within 21 days of its date."),
    _c("3", "Suspension"),
    _c("3.1", "LeapSwitch may suspend the Services under Clause 2.3 after notice."),
]


def test_changed_evidence_and_origin():
    theirs = [OURS[0], OURS[1], OURS[2],
              _c("2.1", "The Customer shall raise any invoice dispute within 30 days of "
                        "the invoice."), OURS[4], OURS[5], OURS[6], OURS[7]]
    changed = L.changed_evidence(OURS, theirs)
    assert changed == {str(theirs[3].evidence_id)}
    # a point on a changed row is the client's; on an unchanged row with the same
    # result on our version it was already ours; a different result is the client's
    assert L.origin([str(theirs[3].evidence_id)], "X", "DEVIATION", changed,
                    {"X": "MATCH"}) == L.CLIENT_CHANGED
    assert L.origin([str(theirs[5].evidence_id)], "Y", "DEVIATION", changed,
                    {"Y": "DEVIATION"}) == L.ALREADY_OURS
    assert L.origin([], "Z", "MISSING", changed, {"Z": "MATCH"}) == L.CLIENT_CHANGED
    # no review of ours: an unchanged row is ours, an evidence-less point unknown
    assert L.origin([str(theirs[5].evidence_id)], "Y", "DEVIATION", changed,
                    None) == L.ALREADY_OURS
    assert L.origin([], "Z", "MISSING", changed, None) is None
    # nothing to compare with and no tracked change: no label at all
    assert L.changed_evidence(None, theirs) is None
    assert L.origin(["a"], "Y", "DEVIATION", None, None) is None


def test_changed_evidence_from_tracked_changes():
    marked = _c("2.1", "x", {"changes": [{"inserted": "30"}], "comments": []})
    assert L.changed_evidence(None, [OURS[0], marked]) == {str(marked.evidence_id)}


def test_lettered_points_bound_and_benefits():
    before = ("LeapSwitch may suspend the Services on notice. The Customer shall pay "
              "within 5 days.")
    after = ("LeapSwitch may suspend the Services on notice. The Customer shall pay "
             "within 30 days. LeapSwitch shall provide support at all times.")
    got = L.points(before, after)
    assert [p["letter"] for p in got] == ["a", "b"]
    assert got[0]["kind"] == "CHANGED" and got[0]["bound"] == L.THEIRS
    assert got[1]["kind"] == "ADDED" and got[1]["bound"] == L.OURS \
        and got[1]["benefits"] == L.THEIRS
    assert L.mutuality(before, got) == L.MIXED
    only_us = L.points("", "LeapSwitch shall provide support at all times.")
    assert L.mutuality("", only_us) == L.ONTO_US


def test_standards_map_findings_then_topic_then_legal():
    assert L.standards({"review": {"before": [], "after": [
        {"requirement_code": "B"}, {"requirement_code": "A"}]}})["codes"] == ["A", "B"]
    topic = L.standards({"review": {"before": [], "after": []},
                         "triage": {"topics": [{"section": "16", "title": "Payment",
                                                "position": "x"}]}})
    assert topic == {"source": "HEADING_TOPIC",
                     "topics": [{"section": "16", "title": "Payment"}]}
    assert L.standards({"review": {}, "triage": None}) == {"source": L.LEGAL_DECIDES}


def test_notes_for_legal():
    theirs = [
        _c("1", "Definitions"),
        _c("2", "Billing"),
        _c("2.1", "The Customer shall raise any invoice dispute within 30 days of the "
                  "invoice and the Widget shall be returned."),
        OURS[4],
        OURS[6],
        OURS[7],
    ]
    # 1.1 (the Widget definition) and 2.3 deleted; 2.1 changed to 30 days
    notes = L.notes_for_legal(OURS, theirs)
    kinds = {n["kind"]: n for n in notes}
    assert kinds["FIGURE_DIFFERS"]["clauses"] == ["2.1", "2.2"]
    assert kinds["REFERS_TO_DELETED"]["clauses"] == ["3.1", "2.3"]
    assert kinds["DEFINITION_DELETED"]["clauses"] == ["2.1"]
    assert "Widget" in kinds["DEFINITION_DELETED"]["text"]
    # nothing changed: no notes
    assert L.notes_for_legal(OURS, OURS) == []


def test_duplicate_sentence():
    ours = [_c("4", "Liability"),
            _c("4.1", "Neither party shall be liable for any indirect or consequential "
                      "loss of profit or data."),
            _c("4.2", "Fees are payable monthly.")]
    theirs = [ours[0], ours[1],
              _c("4.2", "Neither party shall be liable for any indirect or consequential "
                        "loss of profit or data whatsoever.")]
    notes = L.notes_for_legal(ours, theirs)
    assert [n["kind"] for n in notes] == ["DUPLICATE"]
    assert notes[0]["clauses"] == ["4.2", "4.1"]


def test_an_unchanged_paragraph_beside_a_changed_table_is_already_ours():
    """Batch 8 R3c-1: a venue paragraph read in one unit with a price table under it —
    only the table changed, so a point on the paragraph is ours, not the client's."""
    venue = "9. Disputes go to the courts at City A."
    ours = [Clause(uuid4(), venue, "9"), Clause(uuid4(), "| Item | Qty |"),
            Clause(uuid4(), "| Node | 4 |")]
    theirs = [Clause(uuid4(), venue, "9"), Clause(uuid4(), "| Item | Qty |"),
              Clause(uuid4(), "| Node | 5 |")]
    changed = L.changed_evidence(ours, theirs)
    assert changed == {str(theirs[2].evidence_id)}
    assert L.origin([str(theirs[0].evidence_id)], "VENUE", "DEVIATION", changed,
                    {"VENUE": "DEVIATION"}) == L.ALREADY_OURS
    assert L.origin([str(theirs[2].evidence_id)], "QTY", "DEVIATION", changed,
                    {"QTY": "DEVIATION"}) == L.CLIENT_CHANGED
