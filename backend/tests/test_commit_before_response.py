"""Every router commits before its response is sent — see `deps.CommitBeforeResponse`.

WHY A SOURCE-LEVEL TEST. The failure this guards against is not subtle behaviour;
it is someone adding a thirteenth router and not knowing this exists. And it
cannot be caught by driving the app: `tests/conftest.py` overrides `get_db`
entirely, so `request.state.db` is never set under the test client and the wrapper
is a no-op there. The behaviour itself was verified against a real API and a real
database (60/60 rows committed before the client held the 200, against 11/60
without it); what a test can hold to account is the wiring.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi import Request

ROUTERS = sorted((pathlib.Path(__file__).resolve().parents[1]
                  / "legalmind" / "api" / "routers").glob("*.py"))
DECLARE = re.compile(r"^router = APIRouter\((?P<args>[^)]*)\)", re.M)


def _router_modules():
    return [p for p in ROUTERS if DECLARE.search(p.read_text())]


def test_every_router_module_is_found():
    """If this drops, the discovery below silently stops guarding anything."""
    assert len(_router_modules()) == 23   # + deal_brief (AB-218), negotiation, todo, collaborators, notifications, ask_filing (AB-150), templates (S4), drafts (S5), execution (AM-297), playbook (AM-305), amendments (AM-309)


@pytest.mark.parametrize("path", _router_modules(), ids=lambda p: p.stem)
def test_router_commits_before_its_response(path: pathlib.Path):
    """`include_router` preserves each SOURCE route's class, so setting
    `route_class` on the aggregating `v1` router does nothing — measured at zero
    routes wrapped. It has to be set where the `APIRouter` is constructed."""
    args = DECLARE.search(path.read_text()).group("args")
    assert "route_class=CommitBeforeResponse" in args, (
        f"{path.name}: APIRouter must be constructed with "
        "route_class=CommitBeforeResponse, or every write it serves commits "
        "after its response has been sent (see deps.CommitBeforeResponse)")


def test_get_db_publishes_the_session_for_the_route_to_commit():
    """The wrapper finds the session on `request.state`; without this line it
    silently commits nothing and the window comes back."""
    deps = (pathlib.Path(__file__).resolve().parents[1]
            / "legalmind" / "api" / "deps.py").read_text()
    assert "request.state.db = db" in deps


def test_get_db_still_commits_in_its_own_teardown():
    """Belt and braces, deliberately. A router added WITHOUT the route class keeps
    working exactly as it did rather than silently persisting nothing — the old
    race returns for that one route, which is survivable; losing its writes is
    not."""
    deps = (pathlib.Path(__file__).resolve().parents[1]
            / "legalmind" / "api" / "deps.py").read_text()
    body = deps[deps.index("def get_db("):deps.index("class CommitBeforeResponse")]
    assert "db.commit()" in body and "db.rollback()" in body


def test_the_request_commit_never_blocks_the_event_loop():
    """BE-11 (2026-11-23): the commit ran ON the loop, so a commit waiting on a lock
    (or a slow after-commit hook) froze every other request in the process — the
    2026-10-13 freeze class. Now it runs in the threadpool, still before the response."""
    import asyncio
    import threading
    import time

    import httpx
    from fastapi import APIRouter, FastAPI

    from legalmind.api.deps import CommitBeforeResponse

    release = threading.Event()

    class SlowCommit:
        def commit(self):
            release.wait(5)

    router = APIRouter(route_class=CommitBeforeResponse)

    @router.get("/slow")
    def slow(request: Request):
        request.state.db = SlowCommit()
        return {}

    @router.get("/fast")
    async def fast():
        return {}

    app = FastAPI()
    app.include_router(router)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            started = time.monotonic()
            held = asyncio.create_task(client.get("/slow"))
            await asyncio.sleep(0.3)                     # /slow is now inside its commit
            other = await client.get("/fast")
            waited = time.monotonic() - started - 0.3
            release.set()
            return other.status_code, waited, (await held).status_code
    other, waited, held = asyncio.run(run())
    assert (other, held) == (200, 200)
    assert waited < 1.0, f"another request waited {waited:.1f}s on a commit"


def test_a_request_transaction_carries_its_statement_and_idle_limits(engine, monkeypatch):
    """Pool timeouts (2026-11-23): every transaction a REQUEST opens is bounded, the
    one after a mid-request commit too; a session the worker opens is not."""
    from types import SimpleNamespace

    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import sessionmaker

    from legalmind.api import deps

    monkeypatch.setenv("LEGALMIND_DB_STATEMENT_TIMEOUT_MS", "150")
    monkeypatch.setenv("LEGALMIND_DB_IDLE_IN_TX_TIMEOUT_MS", "5678")
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(deps, "new_session", factory)
    request = SimpleNamespace(state=SimpleNamespace())
    requests_db = deps.get_db(request)
    db = next(requests_db)
    show = "SELECT current_setting('statement_timeout'), " \
           "current_setting('idle_in_transaction_session_timeout')"
    assert db.execute(text(show)).one() == ("150ms", "5678ms")
    db.commit()                                          # a mid-request commit
    assert db.execute(text(show)).one() == ("150ms", "5678ms")
    with pytest.raises(OperationalError, match="statement timeout"):
        db.execute(text("SELECT pg_sleep(1)"))
    with pytest.raises(OperationalError):
        requests_db.throw(OperationalError("x", {}, Exception("x")))   # get_db rolls back
    with factory() as worker:                            # not a request: untouched
        assert worker.execute(text(show)).one()[0] != "150ms"
