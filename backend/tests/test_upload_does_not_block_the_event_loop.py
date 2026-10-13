"""An ``async`` route never touches the database on the event loop (2026-10-13).

Every request updates its session row (``last_seen_at``), and a synchronous route
commits on the event loop after its threadpool work returns. An ``async`` route that
queried the database directly could wait on that row's lock with the loop blocked —
so the lock holder could never commit, and the whole API froze. It happened: the
Dashboard loading during an upload hung the e2e API mid-suite. The two ``async``
routes read the request body and hand everything else to ``run_in_threadpool``;
this pins that no call in one passes the ``Guard`` (the database) any other way.
"""

import ast
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "legalmind" / "api" / "routers"


def _uses_guard(node: ast.Call) -> bool:
    if getattr(node.func, "id", "") == "run_in_threadpool":
        return False
    on_guard = (isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "guard")
    passes_guard = any(isinstance(a, ast.Name) and a.id == "guard" for a in node.args)
    return on_guard or passes_guard


def test_no_async_route_runs_database_work_on_the_event_loop():
    offenders, routes = [], 0
    for path in sorted(ROUTERS.glob("*.py")):
        for fn in ast.walk(ast.parse(path.read_text())):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            routes += 1
            for call in ast.walk(fn):
                if isinstance(call, ast.Call) and _uses_guard(call):
                    offenders.append(f"{path.name}:{call.lineno} {fn.name}")
    assert routes >= 2
    assert offenders == []
