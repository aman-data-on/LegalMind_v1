"""Engine and session construction, in one place — locked 55.1.

Locked 55.1: "Workers run the SAME image as the API — a version skew would break
`evaluator_version` reproducibility, so they deploy together." The same reasoning
applies one level down: the API and the worker must reach the *same* database in the
*same* way, so URL resolution and connection arguments live here rather than being
written out twice and drifting.

Lazy by construction. Importing the application must never open a connection: the
test harness replaces the API's session dependency entirely and points the worker at
its own engine, and a module-scope `create_engine` would make importing either one
depend on a reachable database.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import sessionmaker

from legalmind.config import database_url, db_pool

_engine: Engine | None = None
_sessionmaker: sessionmaker | None = None


def engine() -> Engine:
    """The process-wide engine, built on first use.

    ``pool_pre_ping`` because a worker process is long-lived and idles between
    jobs; a connection recycled by the server would otherwise surface as a failed
    analysis rather than as a reconnect. The pool's size, overflow and wait come
    from `config.db_pool` — a request that finds no free connection fails after
    ``pool_timeout`` with `TimeoutError`, never an unbounded queue.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(database_url(), future=True, pool_pre_ping=True,
                                **db_pool())
    return _engine


def session_factory() -> sessionmaker:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(bind=engine(), future=True)
    return _sessionmaker


def new_session() -> DBSession:
    return session_factory()()


def reset() -> None:
    """Drop the cached engine — for tests, and for a worker that must reconnect
    after its configuration changed. Never called on a request path."""
    global _engine, _sessionmaker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None


def on_rollback(db: DBSession, fn: Callable[[], object]) -> None:
    """Run ``fn`` if the transaction open now — or one enclosing it — rolls back, and
    never once it commits. A savepoint opened and rolled back later leaves it alone
    (``after_soft_rollback`` fires for every savepoint, so the ancestry is checked)."""
    mine = db.get_nested_transaction() or db.get_transaction()
    live = [mine is not None]

    def rolled_back(_session: DBSession, previous: object) -> None:
        tx = mine
        while live[0] and tx is not None:
            if tx is previous:
                live[0] = False
                fn()
            tx = tx.parent

    def committed(_session: DBSession) -> None:
        live[0] = False

    # ponytail: the rollback listener stays on the session until it is closed (one per
    # request or job); remove it on commit if a session ever lives long
    event.listen(db, "after_soft_rollback", rolled_back)
    event.listen(db, "after_commit", committed, once=True)
