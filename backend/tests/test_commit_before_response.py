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

ROUTERS = sorted((pathlib.Path(__file__).resolve().parents[1]
                  / "legalmind" / "api" / "routers").glob("*.py"))
DECLARE = re.compile(r"^router = APIRouter\((?P<args>[^)]*)\)", re.M)


def _router_modules():
    return [p for p in ROUTERS if DECLARE.search(p.read_text())]


def test_every_router_module_is_found():
    """If this drops, the discovery below silently stops guarding anything."""
    assert len(_router_modules()) == 12


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
