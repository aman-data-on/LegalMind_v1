"""Run the five synthetic contracts through the REAL API and check the answers.

Drives the same endpoints the browser does — login, contract, upload, review,
analyze, findings — so what it measures is the shipped path, not a mirror of it.
Nothing is asserted about the law here: the expected outcome for every clause
comes from `expected.json`, which the generator derives from the ratified
Company Standard's own number.

Usage:
    python3 -m tools.run_contract_tests --email user@leapswitch.com
    (password from LEGALMIND_TEST_PASSWORD, or --password)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests

CSRF_COOKIE = "legalmind_csrf"
DOCX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document")


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.s = requests.Session()

    def login(self, email: str, password: str) -> None:
        """Log in ONCE, then confirm the session is actually usable.

        Two things bite here. nginx rate-limits the `legalmind_auth` zone, so a
        harness that re-logs-in per request earns 503s — hence one login for the
        whole run. And a GET issued in the same second as the login has been
        seen to come back 401 while the session row exists, so the session is
        polled until it answers rather than assumed live. If the first poll ever
        fails and a later one succeeds, that is a real settling delay and the
        count is printed rather than hidden.
        """
        r = self.s.post(f"{self.base}/api/v1/auth/login",
                        json={"email": email, "password": password}, timeout=30)
        r.raise_for_status()
        if CSRF_COOKIE not in self.s.cookies:
            raise SystemExit("no CSRF cookie after login")
        for attempt in range(1, 8):
            probe = self.s.get(f"{self.base}/api/v1/auth/session", timeout=30)
            if probe.ok:
                if attempt > 1:
                    print(f"note: session became usable only on probe {attempt} "
                          f"— a settling delay, worth reporting")
                return
            time.sleep(attempt * 0.75)
        raise SystemExit(f"session never became usable: {probe.status_code}")

    def _headers(self, extra: dict | None = None) -> dict:
        h = {"X-CSRF-Token": self.s.cookies[CSRF_COOKIE]}
        h.update(extra or {})
        return h

    def post(self, path: str, body: dict | None = None) -> dict:
        # 429 is expected here rather than exceptional: analysis is rate-limited
        # per account, and five contracts back to back exceed it. Backing off is
        # the correct client behaviour, not a workaround — the limit is a real
        # control and this harness is a well-behaved caller of it.
        for attempt in range(1, 7):
            r = self.s.post(f"{self.base}/api/v1{path}", json=body,
                            headers=self._headers(), timeout=300)
            if r.status_code != 429:
                break
            wait = 20 * attempt
            print(f"        rate-limited on {path}; waiting {wait}s")
            time.sleep(wait)
        if not r.ok:
            raise SystemExit(f"POST {path} -> {r.status_code} {r.text[:400]}")
        return (r.json() or {}).get("data", {})

    def get(self, path: str) -> dict:
        r = self.s.get(f"{self.base}/api/v1{path}", timeout=120)
        if not r.ok:
            raise SystemExit(f"GET {path} -> {r.status_code} {r.text[:400]}")
        return (r.json() or {}).get("data", {})

    def upload(self, contract_id: str, path: Path) -> dict:
        r = self.s.post(
            f"{self.base}/api/v1/contracts/{contract_id}/document-versions",
            headers=self._headers({"Content-Type": DOCX_MIME,
                                   "X-Filename": path.name}),
            data=path.read_bytes(), timeout=300)
        if not r.ok:
            raise SystemExit(f"upload -> {r.status_code} {r.text[:400]}")
        return (r.json() or {}).get("data", {})


def analyse(client: Client, slug: str, spec: dict, docs: Path,
            snapshot_id: str) -> dict:
    """Upload one contract, analyse it, and return {code: user_status}."""
    contract = client.post("/contracts", {
        "name": f"{spec['title']} [{slug}]",
        "contract_type": spec["declared_type"],
    })
    uploaded = client.upload(contract["id"], docs / spec["file"])
    review = client.post("/reviews", {
        "document_version_id": uploaded["document_version"]["id"],
        "configuration_snapshot_id": snapshot_id,
    })
    run = client.post(f"/reviews/{review['id']}/analyze")
    # The analyze call can REFUSE (rule 15 fails closed) and still return 200
    # with a reason. Ignoring that is how a run reports "0 findings" as though
    # the engine had looked and found nothing.
    refusal = run.get("refusal_reason") or run.get("reason") or run.get("refused")
    if refusal:
        print(f"        ANALYSIS REFUSED: {refusal}")

    # In production `analyze` returns mode="queued": the work goes to the Celery
    # worker and the endpoint returns immediately. Reading findings straight
    # afterwards reports "0 findings" for a review the engine has not looked at
    # yet — which is indistinguishable from the engine finding nothing, and is
    # exactly how this harness lied on its first run. So wait for a terminal
    # state rather than assuming inline execution.
    TERMINAL = {"ANALYSIS_COMPLETE", "ANALYSIS_FAILED", "LEGAL_REVIEW",
                "RESOLVED", "CLOSED", "CANCELLED"}
    status = run.get("review_status")
    if run.get("mode") == "queued":
        for _ in range(120):                          # up to ~4 minutes
            time.sleep(2)
            status = (client.get(f"/reviews/{review['id']}") or {}).get("status")
            if status in TERMINAL:
                break
        else:
            print(f"        TIMED OUT waiting for analysis (last status {status})")
    if status == "ANALYSIS_FAILED":
        print("        ANALYSIS FAILED on the worker")

    findings = client.get(f"/reviews/{review['id']}/findings")
    got: dict[str, str] = {}
    for f in findings if isinstance(findings, list) else []:
        code = (f.get("requirement") or {}).get("code") or f.get("requirement_code")
        status = f.get("user_status") or f.get("status")
        if code:
            got[code] = status
    return {"review_id": review["id"], "contract_id": contract["id"],
            "statuses": got, "finding_count": len(findings or []),
            "analyze_response": run, "review_status": status}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="https://legalmind.lsnw.io")
    ap.add_argument("--email", default="user@leapswitch.com")
    ap.add_argument("--password", default=os.environ.get("LEGALMIND_TEST_PASSWORD"))
    ap.add_argument("--docs", type=Path,
                    default=Path(__file__).resolve().parents[2]
                    / "legal-docs" / "synthetic")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args(argv)
    if not args.password:
        raise SystemExit("password required (--password or LEGALMIND_TEST_PASSWORD)")

    expected_all = json.loads((args.docs / "expected.json").read_text())

    client = Client(args.base)
    client.login(args.email, args.password)
    snapshots = client.get("/configuration/snapshots?page_size=1")
    items = snapshots.get("items", snapshots) if isinstance(snapshots, dict) else snapshots
    snapshot_id = items[0]["id"]
    print(f"snapshot: {snapshot_id[:8]} "
          f"({items[0].get('requirement_count','?')} requirements)\n")

    results, failures = {}, 0
    for index, (slug, spec) in enumerate(expected_all.items()):
        if index:
            time.sleep(25)                            # stay under the analysis limit
        out = analyse(client, slug, spec, args.docs, snapshot_id)
        got, exp = out["statuses"], spec["expected"]
        wrong = {c: (e, got.get(c, "(no finding)"))
                 for c, e in exp.items() if got.get(c) != e}
        extra = {c: s for c, s in got.items() if c not in exp}
        status = "PASS" if not wrong else "FAIL"
        failures += bool(wrong)
        print(f"{status}  {slug}  [{spec['declared_type']}]  "
              f"{out['finding_count']} findings, "
              f"{len(exp) - len(wrong)}/{len(exp)} expected outcomes correct")
        for code, (e, g) in sorted(wrong.items()):
            print(f"        MISMATCH {code}: expected {e}, got {g}")
        if extra:
            print(f"        (also produced: {', '.join(sorted(extra))})")
        results[slug] = {**out, "expected": exp, "mismatches": wrong,
                         "unexpected": extra}

    print(f"\n{len(expected_all) - failures}/{len(expected_all)} contracts fully correct")
    if args.json_out:
        args.json_out.write_text(json.dumps(results, indent=2) + "\n")
        print(f"detail: {args.json_out}")
    return 1 if failures else 0


if __name__ == "__main__":                            # pragma: no cover
    raise SystemExit(main())
