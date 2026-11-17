"""`AM-221`: a ratified quote kept only as provenance is labelled when Ask shows it, with
the position it points to in that standard's own words. C26 (2026-10-27): Ask gave
ARBITRATION-MSA-001's template "Mumbai" as our MSA arbitration position; C-27 settled it
as Pune (`AM-150` r2); `AM-380` (2026-11-16) made Mumbai the MSA venue. The label is never indexed: the chunk stays the ratified file's
own fields (AM-30 t3; code review of PR #244). No database, no model."""
import json

from legalmind.assist.knowledge import positions


def _payload(code):
    return json.loads((positions.RATIFIED_STANDARDS_DIR / f"{code}.json").read_text())


def test_the_mumbai_quote_is_the_msa_position_and_is_not_labelled_historical():
    """AM-380 (owner 2026-11-16): our MSA 19.3/19.4 (Mumbai) IS the MSA venue position,
    so ARBITRATION-MSA-001's quote is no longer provenance-only and carries no label."""
    assert positions.provenance_note("ARBITRATION-MSA-001") == ""
    assert "Historical" not in positions._compose_content(_payload("ARBITRATION-MSA-001"))


def test_every_marker_names_a_live_standard():
    for p in sorted(positions.RATIFIED_STANDARDS_DIR.glob("*.json")):
        held = json.loads(p.read_text()).get("quote_not_position")
        if held:
            assert not _payload(held).get("retired"), p.stem
            assert positions.provenance_note(p.stem).startswith("[Historical")
    assert positions.provenance_note("DISPUTE-VENUE-MSA-001") == ""
