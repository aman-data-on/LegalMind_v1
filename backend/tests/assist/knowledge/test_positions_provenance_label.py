"""`AM-221`: a ratified quote kept only as provenance is labelled in Ask's index before it
is read, naming the standard that holds the position. C26 (2026-10-27): Ask gave
ARBITRATION-MSA-001's template "Mumbai" as our MSA arbitration position; C-27 settled it
as Pune (`AM-150` r2). No database, no model."""
import json

from legalmind.assist.knowledge import positions


def _payload(code):
    return json.loads((positions.RATIFIED_STANDARDS_DIR / f"{code}.json").read_text())


def test_the_mumbai_quote_is_labelled_as_history_and_names_the_pune_position():
    content = positions._compose_content(_payload("ARBITRATION-MSA-001"))
    label = content.index("[Historical template wording, not the company position; the "
                          "company position is DISPUTE-VENUE-MSA-001.]")
    assert label < content.index("Mumbai")


def test_only_a_marked_standard_is_labelled_and_the_marker_names_a_live_standard():
    marked = [p for p in sorted(positions.RATIFIED_STANDARDS_DIR.glob("*.json"))
              if json.loads(p.read_text()).get("quote_not_position")]
    assert [p.stem for p in marked] == ["ARBITRATION-MSA-001"]
    held = json.loads(marked[0].read_text())["quote_not_position"]
    assert not _payload(held).get("retired")
    assert "Historical" not in positions._compose_content(_payload("DISPUTE-VENUE-MSA-001"))
