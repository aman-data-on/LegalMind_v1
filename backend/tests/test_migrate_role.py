"""`alembic/env.py` SETs ROLE legalmind_migrate only where that role owns the
schema — `legalmind.db.migrate_role` (2026-09-29, after a production deploy stopped
at the migration step because membership existed but ownership did not)."""
from sqlalchemy import text

from legalmind.db.migrate_role import PROBE, should_set_migrate_role


def test_a_database_the_connecting_role_owns_never_sets_role(engine):
    """Dev, CI and this test database: no migrate role, the connecting role owns
    everything — the same answer a production that ran only the GRANT must get."""
    with engine.connect() as c:
        assert should_set_migrate_role(c) is False


def test_the_probe_asks_about_ownership_not_only_membership(engine):
    """The 2026-09-29 gap, pinned in the query itself: a role one may act as is not
    a role that owns `alembic_version`."""
    sql = str(PROBE)
    assert "pg_has_role" in sql and "tableowner" in sql and "alembic_version" in sql
    with engine.connect() as c:                      # it is valid SQL, and answers
        assert c.execute(text(str(PROBE))).scalar() is False
