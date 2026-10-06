"""The ONLY source of a record timestamp — the system clock, in IST (charter §7).

    python3 -m tools.stamp          # 2026-10-03T20:41+05:30

Phase 1's records carried times estimated by the agent that ran up to two hours ahead of
the clock (owner, 2026-10-03). `tests/test_record_timestamps.py` fails on any record time
later than now, so an estimated stamp cannot land again unnoticed.
"""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%dT%H:%M") + "+05:30"


if __name__ == "__main__":
    print(now())
