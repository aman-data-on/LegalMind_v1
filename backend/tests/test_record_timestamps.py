"""Record times come from the clock, never an estimate (owner, 2026-10-03).

Every `YYYY-MM-DDTHH:MM+05:30` in the Ask agent records must be no later than now: an
estimated time runs ahead of the clock, which is how Phase 1's records went wrong. Take
times from `python3 -m tools.stamp`.
"""
import pathlib
import re
from datetime import datetime, timedelta

from tools.stamp import IST

ROOT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "architecture"
RECORDS = [ROOT / "IMPLEMENTATION_LOG.md",
           *sorted((ROOT / "ask-agent").glob("*.md"))]
STAMP = re.compile(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\+05:30\b")


def test_no_record_time_is_in_the_future():
    limit = datetime.now(IST) + timedelta(minutes=5)
    ahead = [(p.name, m) for p in RECORDS if p.exists()
             for m in STAMP.findall(p.read_text())
             if datetime.fromisoformat(m + "+05:30") > limit]
    assert not ahead, f"record times later than the clock: {ahead[:5]}"


def test_the_stamp_helper_reads_the_clock():
    from tools.stamp import now
    stamped = datetime.fromisoformat(now())
    assert abs((stamped - datetime.now(IST)).total_seconds()) < 120
