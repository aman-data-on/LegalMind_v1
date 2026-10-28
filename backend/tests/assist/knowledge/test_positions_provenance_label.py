"""`AM-221`: a ratified quote kept only as provenance is labelled when Ask shows it, with
the position it points to in that standard's own words. C26 (2026-10-27): Ask gave
ARBITRATION-MSA-001's template "Mumbai" as our MSA arbitration position; C-27 settled it
as Pune (`AM-150` r2). The label is never indexed: the chunk stays the ratified file's
own fields (AM-30 t3; code review of PR #244). No database, no model."""
import json

from legalmind.assist.knowledge import positions


def _payload(code):
    return json.loads((positions.RATIFIED_STANDARDS_DIR / f"{code}.json").read_text())


def test_the_mumbai_quote_is_shown_labelled_with_the_pune_position_in_its_own_words():
    note = positions.provenance_note("ARBITRATION-MSA-001")
    assert note.startswith("[Historical template wording kept as provenance — NOT the "
                           "company position.")
    assert "seated in Pune" in note and "DISPUTE-VENUE" not in note   # no internal code
    assert "Historical" not in positions._compose_content(_payload("ARBITRATION-MSA-001"))


def test_only_a_marked_standard_is_labelled_and_the_marker_names_a_live_standard():
    marked = [p for p in sorted(positions.RATIFIED_STANDARDS_DIR.glob("*.json"))
              if json.loads(p.read_text()).get("quote_not_position")]
    assert [p.stem for p in marked] == ["ARBITRATION-MSA-001"]
    held = json.loads(marked[0].read_text())["quote_not_position"]
    assert not _payload(held).get("retired")
    assert positions.provenance_note("DISPUTE-VENUE-MSA-001") == ""
