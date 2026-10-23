"""A finished review can reopen; a contract's deletion takes its decisions with it (AM-175/AM-176)

Revision ID: d8b3f1a6c4e2
Revises: c6e2a9d4f1b7
Create Date: 2026-10-22

AM-175 (owner, 2026-10-22): a late change that needs work reopens a finished Review —
`reviews.reopened_at` records when, so the stage can tell a reopened review from one that
never closed; nothing is deleted.

AM-176: AM-55 r3 destroys a contract's Legal Decisions with it, but `legalmind_append_only()`
refused every DELETE, so deleting any decided contract failed (found by the break tests,
2026-10-22). The function now lets a DELETE through only when a cascade fired it
(`pg_trigger_depth() > 1`); a direct UPDATE or DELETE is refused exactly as before.
Caveat, declared: a DELETE issued from inside another trigger would also pass — no such
trigger exists. `contract_outcomes` gets the same trigger.

Downgrade restores the strict function; a decided contract then cannot be deleted again.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d8b3f1a6c4e2"
down_revision = "c6e2a9d4f1b7"
branch_labels = None
depends_on = None

_STRICT = """
    CREATE OR REPLACE FUNCTION legalmind_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION
            '% is append-only; % is not permitted', TG_TABLE_NAME, TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql;
"""

_CASCADE_AWARE = """
    CREATE OR REPLACE FUNCTION legalmind_append_only() RETURNS trigger AS $$
    BEGIN
        -- AM-176: a row removed by an ON DELETE CASCADE (a contract's deletion, AM-55)
        -- may go; nothing else may update or delete it.
        IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION
            '% is append-only; % is not permitted', TG_TABLE_NAME, TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_CASCADE_AWARE)
    op.execute("CREATE TRIGGER trg_contract_outcomes_append_only "
               "BEFORE UPDATE OR DELETE ON contract_outcomes "
               "FOR EACH ROW EXECUTE FUNCTION legalmind_append_only();")
    op.add_column("reviews", sa.Column("reopened_at", sa.DateTime(timezone=True),
                                       nullable=True))


def downgrade() -> None:
    op.drop_column("reviews", "reopened_at")
    op.execute("DROP TRIGGER IF EXISTS trg_contract_outcomes_append_only "
               "ON contract_outcomes;")
    op.execute(_STRICT)
