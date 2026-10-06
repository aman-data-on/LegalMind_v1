"""Whether Alembic should `SET ROLE legalmind_migrate` before migrating — 55.2.

`ops/production/role_sep.sql` moves ownership of every table to `legalmind_migrate`
and grants that role to `legalmind`, so migrations run as the owner and the runtime
role holds DML only. `alembic/env.py` decides per database, and the decision has to
be true in three worlds at once: dev/CI/tests (the connecting role owns everything,
no migrate role exists), a production that ran all of role_sep.sql, and a production
that ran only part of it.

The third world is real. On 2026-09-29 production had the GRANT (membership) but
`REASSIGN OWNED` had never run: every table, `alembic_version` included, was still
owned by `legalmind`. A membership-only probe then handed Alembic a role that owned
nothing — "permission denied for table alembic_version" — and the deploy stopped at
the migration step. So the probe asks the one question that matters: does the
migrate role OWN the table every migration must write? Ownership of
`alembic_version` follows the REASSIGN exactly, and a fresh database with no
version table yet answers no, which is right — the connecting role creates it.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

MIGRATE_ROLE = "legalmind_migrate"

PROBE = text(f"""
    SELECT to_regrole('{MIGRATE_ROLE}') IS NOT NULL
       AND pg_has_role(current_user, to_regrole('{MIGRATE_ROLE}'), 'MEMBER')
       AND COALESCE((SELECT tableowner = '{MIGRATE_ROLE}'
                       FROM pg_tables WHERE tablename = 'alembic_version'), FALSE)
""")


def should_set_migrate_role(connection: Connection) -> bool:
    """True only when the migrate role exists, this connection may act as it, AND it
    owns `alembic_version` — i.e. role_sep.sql's ownership move actually happened."""
    return bool(connection.execute(PROBE).scalar())


def set_role(connection: Connection, role: str = MIGRATE_ROLE) -> None:
    """Act as `role` for the rest of the session, leaving NO transaction open.
    The SET autobegins one, and Alembic treats an already-open transaction as the
    caller's and never commits it: every migration logged "Running upgrade" and
    then rolled back on close (production deploy of 7d12ea5, 2026-10-06). SET ROLE
    is session-level, so the commit keeps the role."""
    connection.execute(text(f'SET ROLE "{role}"'))
    connection.commit()
