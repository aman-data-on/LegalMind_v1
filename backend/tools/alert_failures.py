"""Tell a person when LegalMind fails (owner's plan, 2026-10-30; no new service).

Every 10 minutes (ops/production/legalmind-alerts.timer): read the last 11 minutes of the
API, worker and benchmark journals, keep the lines the code already marks as failures
(``level`` ERROR or ``operational_failure``), add any failed ``legalmind-*`` unit, and post
ONE message per new kind of problem to ``LEGALMIND_ALERT_WEBHOOK_URL`` (a Slack incoming
webhook). The same problem is repeated at most every 6 hours. Unset URL: printed only.

Content-free by construction: only the event name and the whitelisted fields below leave
the server — never a question, a clause, a user or a request id.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

UNITS = ("legalmind-api", "legalmind-worker", "legalmind-hard-benchmark")
SAFE = ("model", "kind", "status", "error")          # the only fields that leave
STATE = Path(os.environ.get("LEGALMIND_ALERT_STATE", "/var/lib/legalmind/alerts.json"))
REPEAT_S = 6 * 3600


def problems(lines: list[str], failed_units: list[str]) -> Counter[str]:
    """Each failure kind, content-free, with how often it was seen."""
    seen: Counter[str] = Counter()
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or not (row.get("level") == "ERROR"
                                             or row.get("operational_failure")):
            continue
        parts = [str(row.get("event", "unknown"))]
        parts += [f"{k}={row[k]}" for k in SAFE if row.get(k) not in (None, "")]
        seen[" ".join(parts)] += 1
    for unit in failed_units:
        seen[f"systemd unit failed: {unit}"] += 1
    return seen


def due(seen: Counter[str], state: dict[str, float], now: float) -> list[str]:
    """The problems not reported in the last REPEAT_S, and records them as sent."""
    fresh = [k for k in seen if k not in state or now - state[k] >= REPEAT_S]
    for k in fresh:
        state[k] = now
    return fresh


def message(seen: Counter[str], fresh: list[str]) -> str:
    rows = "\n".join(f"• {k} — {seen[k]} times in 10 min" for k in sorted(fresh))
    return f"LegalMind needs attention:\n{rows}\nDetails: journalctl -u legalmind-api --since -15min"


def _journal() -> list[str]:
    cmd = ["journalctl", "--since", "-11min", "-o", "cat", "--no-pager"]
    for unit in UNITS:
        cmd += ["-u", unit]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()


def _failed_units() -> list[str]:
    out = subprocess.run(["systemctl", "list-units", "--failed", "--plain", "--no-legend",
                          "legalmind-*"], capture_output=True, text=True).stdout
    return [line.split()[0] for line in out.splitlines() if line.strip()]


def main() -> int:
    seen = problems(_journal(), _failed_units())
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    fresh = due(seen, state, time.time())
    if not fresh:
        return 0
    text = message(seen, fresh)
    url = os.environ.get("LEGALMIND_ALERT_WEBHOOK_URL", "").strip()
    if url:
        req = urllib.request.Request(url, data=json.dumps({"text": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).close()
    print(text)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
