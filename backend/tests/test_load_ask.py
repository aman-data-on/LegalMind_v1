"""Concurrent Ask under load — the validation the production system design review
named as its P0 test-matrix row (§17.3, 2026-09-29).

Opt-in: `LEGALMIND_LOAD_TEST=1`. It runs N real `service.ask` calls at once, each in
its own pooled session (what `get_db` gives a request), against the migrated scratch
schema, with the provider replaced by a delay — and it runs the same load TWICE: with
`_release_connection` (the §6.4 fix) and with it disabled. What is measured:

    latency p50 / p95 / p99 per question
    pool connections checked out — max overall, and max WHILE a provider call is in
        flight (the number the fix exists to drive down)
    provider calls in flight at once, and total calls
    failures
    CPU seconds and RSS growth of the process

Knobs: `LEGALMIND_LOAD_N` (default 30, above the 15-connection pool) and
`LEGALMIND_LOAD_GEMINI_DELAY_S` (default 1.5). A report is written to
`tests/assist_eval/load_ask_<date>.json` — numbers only, never text.

Seeds committed rows into the session-scoped schema (they are dropped with it), so
run it alone: `LEGALMIND_LOAD_TEST=1 python3 -m pytest tests/test_load_ask.py -s`.
"""
import contextlib
import io
import json
import os
import resource
import statistics
import threading
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

import pytest
from sqlalchemy.orm import Session

from legalmind.assist import service
from legalmind.assist.retrieval import rerank
from legalmind.assist.verification import verify
from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.test_assist_ask import USER_PERMS, _synthetic_statute

pytestmark = pytest.mark.skipif(os.environ.get("LEGALMIND_LOAD_TEST") != "1",
                                reason="opt-in load validation (LEGALMIND_LOAD_TEST=1)")

QUESTION = "What does section 3 of the Synthetic Widgets Act say about widget handling?"
SENTENCE = "Every handler shall handle every widget with synthetic care [1]."


class _Provider:
    """A delayed stand-in for the network, counting what is in flight."""

    def __init__(self, delay_s: float):
        self.delay_s = delay_s
        self.lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = 0
        body = {"candidates": [{"content": {"parts": [{"text": SENTENCE}]},
                                "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}}
        self.body = json.dumps(body).encode()

    def __call__(self, request, timeout=None):
        with self.lock:
            self.in_flight += 1
            self.calls += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            time.sleep(self.delay_s)
        finally:
            with self.lock:
                self.in_flight -= 1

        class _Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False
        return _Response(self.body)


def _rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return 0.0


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    q = statistics.quantiles(ordered, n=100, method="inclusive") if len(ordered) > 1 \
        else [ordered[0]] * 99
    return {"p50": round(q[49], 3), "p95": round(q[94], 3), "p99": round(q[98], 3),
            "max": round(ordered[-1], 3)}


def _scenario(engine, user_id, provider, n, release: bool) -> dict:
    """N questions at once, one pooled session each; the pool sampled every 20 ms."""
    with Session(engine) as setup:
        conversations = [service.create_conversation(setup, user_id=user_id,
                                                     contract_id=None)
                         for _ in range(n)]
        setup.commit()

    samples: list[tuple[int, int]] = []          # (checked out, provider in flight)
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            samples.append((engine.pool.checkedout(), provider.in_flight))
            time.sleep(0.02)

    latencies: list[float] = []
    failures: list[str] = []
    lock = threading.Lock()

    def one(conversation_id):
        started = time.perf_counter()
        try:
            with Session(engine) as db:              # exactly what get_db does
                out = service.ask(db, conversation_id=conversation_id,
                                  question=QUESTION, document_version_id=None,
                                  permissions=USER_PERMS,
                                  request_id=f"load-{conversation_id.hex[:8]}")
                db.commit()
                if out.answer_state.value != "ANSWERED":
                    raise AssertionError(out.answer_state.value)
        except Exception as exc:
            with lock:
                failures.append(f"{type(exc).__name__}: {str(exc)[:160]}")
        finally:
            with lock:
                latencies.append(time.perf_counter() - started)

    release_patch = (contextlib.nullcontext() if release else
                     mock.patch.object(service, "_release_connection", lambda db: None))
    cpu0 = resource.getrusage(resource.RUSAGE_SELF)
    rss0 = _rss_mb()
    sampler = threading.Thread(target=sample, daemon=True)
    calls0 = provider.calls
    provider.max_in_flight = 0
    wall = time.perf_counter()
    with release_patch, ThreadPoolExecutor(max_workers=n) as pool:
        sampler.start()
        list(pool.map(one, conversations))
    wall = time.perf_counter() - wall
    stop.set()
    sampler.join(timeout=1)
    cpu1 = resource.getrusage(resource.RUSAGE_SELF)

    during_provider = [c for c, inflight in samples if inflight > 0]
    return {
        "release_connection": release,
        "questions": n,
        "wall_s": round(wall, 2),
        "latency_s": _percentiles(latencies),
        "failures": failures,
        "pool_checked_out_max": max(c for c, _ in samples),
        # Connections held while the provider is answering: the mean is the honest
        # number (the max also counts questions still retrieving when the first call
        # starts), and connection-seconds per question is what the pool actually pays.
        "pool_checked_out_mean_while_provider_in_flight":
            round(statistics.fmean(during_provider), 2) if during_provider else 0,
        "connection_seconds_per_question":
            round(sum(c for c, _ in samples) * 0.02 / n, 3),
        "provider_calls": provider.calls - calls0,
        "provider_max_in_flight": provider.max_in_flight,
        "cpu_s": round((cpu1.ru_utime - cpu0.ru_utime) + (cpu1.ru_stime - cpu0.ru_stime), 2),
        "rss_growth_mb": round(_rss_mb() - rss0, 1),
        "samples": len(samples),
    }


def test_concurrent_ask_releases_the_pool_for_the_provider_round_trip(engine, tmp_path,
                                                                      monkeypatch):
    n = int(os.environ.get("LEGALMIND_LOAD_N", "30"))
    delay = float(os.environ.get("LEGALMIND_LOAD_GEMINI_DELAY_S", "1.5"))
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "test-not-a-secret")
    # The offline stand-ins the multi-source tests use; the embedder is the real,
    # locally provisioned model, so CPU contention is measured too.
    monkeypatch.setattr(verify, "check_answer",
                        lambda text_, *a, **k: verify.Result(True, text_, [], []))
    monkeypatch.setattr(rerank, "scores", lambda q, texts, **k: [
        10.0 if "widget" in t.lower() else -10.0 for t in texts])
    provider = _Provider(delay)
    monkeypatch.setattr(urllib.request, "urlopen", provider)

    with Session(engine) as setup:
        user = M.User(email=f"load-{uuid.uuid4().hex[:8]}@example.test",
                      name="Load", status=E.UserStatus.ACTIVE)
        setup.add(user)
        setup.flush()
        _synthetic_statute(setup, tmp_path)
        user_id = user.id
        setup.commit()

    pool_limit = engine.pool.size() + engine.pool._max_overflow
    report = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "pool_size_plus_overflow": pool_limit,
        "provider_delay_s": delay,
        "cpus": os.cpu_count(),
        "scenarios": [_scenario(engine, user_id, provider, n, release=True),
                      _scenario(engine, user_id, provider, n, release=False)],
    }
    out = Path(__file__).parent / "assist_eval" / f"load_ask_{report['date'][:10]}.json"
    out.write_text(json.dumps(report, indent=2))
    print("\n" + json.dumps(report, indent=2))

    fixed, before = report["scenarios"]
    assert not fixed["failures"] and not before["failures"]
    # The property the fix exists for: while the provider is answering, the old
    # path holds the whole pool and the fixed path holds a fraction of it; and the
    # pool no longer caps how many provider calls can be in flight.
    key = "pool_checked_out_mean_while_provider_in_flight"
    assert before[key] >= 0.8 * min(n, pool_limit), before
    assert fixed[key] <= before[key] / 3, (fixed, before)
    assert before["provider_max_in_flight"] <= pool_limit < fixed["provider_max_in_flight"]
