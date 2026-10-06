from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import legalmind.db.models  # noqa: F401  (registers all tables)
from alembic import context
from legalmind.config import database_url
from legalmind.db.base import Base
from legalmind.db.migrate_role import set_role, should_set_migrate_role

config = context.config
if config.config_file_name is not None:
    # `disable_existing_loggers=False` is load-bearing, not a style choice.
    #
    # `fileConfig` defaults to True, which sets `disabled = True` on every logger that
    # already exists — including `legalmind`. Migrations are run in-process in several
    # places (the test harness, `tools/e2e_bootstrap`, `tools/verify_*`, and any
    # deployment that migrates from the application image), and in every one of those
    # the default would silently switch off the application's own logging for the rest
    # of the process. Locked 53.1 makes logs non-authoritative, so nothing legal would
    # break — and nothing would be observable either, which is precisely the failure
    # 53.4's operator-facing half exists to prevent.
    #
    # Found when a test that logged after touching the database captured nothing.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Respect a URL supplied by the caller (e.g. the test harness); fall back to
# the configured default. Without this guard the test harness would silently
# migrate the development database.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", database_url())
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # role_sep.sql (55.2) moves DDL ownership to legalmind_migrate so the runtime
    # role can't ALTER/DROP the legal record; migrations must then run AS that
    # owner. `should_set_migrate_role` says whether this database is in that
    # state — the role exists, we may act as it, and it OWNS alembic_version.
    # Membership alone was not enough (2026-09-29: production had the GRANT but
    # not the REASSIGN, and SET ROLE handed Alembic a role that owned nothing).
    # Dev, CI and tests answer no: they connect as a role that owns everything.
    #
    # Checked on ITS OWN connection, not the migrations connection: executing
    # anything on that connection before handing it to `context.configure`
    # autobegins a transaction, and Alembic then treats an already-open
    # transaction as caller-owned and never commits its own — every DDL
    # statement runs and logs, then silently rolls back when the connection
    # closes. Found when CI reported migrations reaching head with the target
    # schema left completely empty (backend/alembic/env.py, 2026-09-29).
    with connectable.connect() as probe:
        migrate_role = should_set_migrate_role(probe)

    with connectable.connect() as connection:
        if migrate_role:
            set_role(connection)
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
