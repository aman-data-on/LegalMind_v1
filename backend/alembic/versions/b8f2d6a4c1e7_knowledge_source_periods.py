"""Published-policy version periods — lawyer judgement P1 (`AM-476`, `AM-477`), 2026-11-26

Revision ID: b8f2d6a4c1e7
Revises: d340ac8e60fd
Create Date: 2026-11-26

Which stored version of a published policy was in force on a date. `knowledge_sources`
cannot say: when a page goes A → B → A, ingestion revives A's row (its records and
embeddings are kept) with A's first start date and no end, so A appears to cover B's
whole period. This table is APPEND-ONLY (the `legalmind_append_only` trigger): one row
each time a version becomes the one in force, `started_on` the day it was read; a
period runs until the next row of the same policy. Backfilled from each existing row's
`effective_from` — a revival that already happened cannot be recovered and is not
guessed.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = "b8f2d6a4c1e7"
down_revision = "d340ac8e60fd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = config.assist_schema()
    op.create_table(
        "knowledge_source_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(f"{schema}.knowledge_sources.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        schema=schema)
    op.create_index("ix_knowledge_source_periods_type_started", "knowledge_source_periods",
                    ["source_type", "started_on", "created_at"], schema=schema)
    op.execute(sa.text(
        f'CREATE TRIGGER trg_knowledge_source_periods_append_only BEFORE UPDATE OR DELETE '
        f'ON "{schema}".knowledge_source_periods FOR EACH ROW EXECUTE FUNCTION '
        "legalmind_append_only()"))
    op.execute(sa.text(f"""
        INSERT INTO "{schema}".knowledge_source_periods (source_type, source_id, started_on,
                                                         created_at)
        SELECT source_type, id, effective_from, now() FROM "{schema}".knowledge_sources
         WHERE source_type LIKE 'PUBLISHED\\_%' AND effective_from IS NOT NULL
         ORDER BY effective_from"""))


def downgrade() -> None:
    schema = config.assist_schema()
    op.drop_table("knowledge_source_periods", schema=schema)
