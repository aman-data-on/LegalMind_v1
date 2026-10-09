"""Statute generations: STAGED and STANDBY beside the live corpus (AM-125)

Revision ID: b5d9f2a4c7e1
Revises: e3a7c1f9b2d4
Create Date: 2026-10-08

A re-ingest under a new parser (`section-6`) is built as a SECOND row per Act in status
STAGED, invisible to every read, then swapped in by a status flip; the swapped-out rows
wait as STANDBY for a rollback and are retired to WITHDRAWN. Nothing is deleted: the
old rows' chunks carry `answer_citations` (ON DELETE CASCADE, `d7e2a9c41b58`).

Two rows per Act cannot share (official_title, as_amended_date) under the full unique
constraint, so it becomes a partial unique index over the LIVE statuses only — one
served row per Act and version, which is what the constraint was for. No new table or
column (`AM-27`).

Downgrade refuses while a STAGED or STANDBY row exists (roll back or retire first). Once
a generation has been RETIRED it is refused for good: the retired WITHDRAWN row shares
its title and version with its live successor, the full constraint cannot be restored
over both, and rule 17 forbids deleting the row that past answers cite. That is a
consequence of keeping history, recorded in `AM-125` r5, not a state to wait out.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'b5d9f2a4c7e1'
down_revision = 'e3a7c1f9b2d4'
branch_labels = None
depends_on = None

_OLD = "('CURRENT', 'REPEALED', 'WITHDRAWN')"
_NEW = "('CURRENT', 'REPEALED', 'WITHDRAWN', 'STAGED', 'STANDBY')"


def _status_check(schema: str, allowed: str) -> None:
    # `a7d3e9b1c5f2` named it through the metadata convention; see its downgrade.
    op.drop_constraint(op.f('ck_statutes_ck_statutes_status'), 'statutes', type_='check',
                       schema=schema)
    op.create_check_constraint('ck_statutes_status', 'statutes', f"status IN {allowed}",
                               schema=schema)


def upgrade() -> None:
    schema = config.assist_schema()
    _status_check(schema, _NEW)
    op.drop_constraint(op.f('uq_statutes_title_version'), 'statutes', type_='unique',
                       schema=schema)
    op.create_index(op.f('uq_statutes_live_title_version'), 'statutes',
                    ['official_title', 'as_amended_date'], unique=True, schema=schema,
                    postgresql_where=sa.text("status IN ('CURRENT', 'REPEALED')"))


def downgrade() -> None:
    schema = config.assist_schema()
    op.execute(sa.text(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM "{schema}".statutes WHERE status IN ('STAGED', 'STANDBY'))
          THEN
            RAISE EXCEPTION 'statute generations exist: roll back or retire them first';
          END IF;
          IF EXISTS (SELECT 1 FROM "{schema}".statutes
                      GROUP BY official_title, as_amended_date HAVING count(*) > 1) THEN
            RAISE EXCEPTION 'irreversible: a retired statute generation is never deleted (AM-125 r5)';
          END IF;
        END $$"""))
    op.drop_index(op.f('uq_statutes_live_title_version'), 'statutes', schema=schema)
    op.create_unique_constraint(op.f('uq_statutes_title_version'), 'statutes',
                                ['official_title', 'as_amended_date'], schema=schema)
    _status_check(schema, _OLD)
