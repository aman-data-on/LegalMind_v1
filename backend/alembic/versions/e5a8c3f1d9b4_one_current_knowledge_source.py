"""One CURRENT copy per knowledge source type — review, 2026-10-14

Revision ID: e5a8c3f1d9b4
Revises: d3f7a1c9e5b2
Create Date: 2026-10-14

Every reader of `knowledge_sources` assumes at most one CURRENT row per
`source_type` (Ask's published policies, Diff-Talk's website side, the
Constitution). The writers demote the old row before making a new one CURRENT,
but nothing stopped two refreshes running at once from both inserting one. A
partial unique index makes the second fail instead of leaving two CURRENT copies.

An index only: no table, column, CHECK or enum changes. The assist schema
(`AM-27` r1), as every assist migration.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = "e5a8c3f1d9b4"
down_revision = "d3f7a1c9e5b2"
branch_labels = None
depends_on = None

NAME = "uq_knowledge_sources_one_current"


def upgrade() -> None:
    op.create_index(NAME, "knowledge_sources", ["source_type"], unique=True,
                    postgresql_where=sa.text("status = 'CURRENT'"),
                    schema=config.assist_schema())


def downgrade() -> None:
    op.drop_index(NAME, table_name="knowledge_sources", schema=config.assist_schema())
