"""Constitution retrieval records — roadmap PHASE 3, `AM-82`, 2026-09-24

Revision ID: b8e2f6a4d1c3
Revises: a7d3e9b1c5f2
Create Date: 2026-09-24

The hierarchy `f4c1e8a2b7d9` stored becomes searchable: each item carries a
`breadcrumb` (document · section · provision) that is indexed with its text but is
never part of its content, the full-text index covers both, and vectors live in
`knowledge_item_embeddings` exactly as every other domain's do. One embedding model
serves all domains (`AM-32` r9), so the DDL literal is the same 384.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = 'b8e2f6a4d1c3'
down_revision = 'a7d3e9b1c5f2'
branch_labels = None
depends_on = None

DIMENSIONS = 384  # all-MiniLM-L6-v2 — must equal chunk_embeddings' literal


def upgrade() -> None:
    schema = config.assist_schema()
    vec_schema = op.get_bind().execute(sa.text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'")).scalar()
    op.add_column('knowledge_items', sa.Column('breadcrumb', sa.Text(),
                                               server_default='', nullable=False),
                  schema=schema)
    op.drop_index('ix_knowledge_items_content_tsv', 'knowledge_items', schema=schema)
    op.drop_column('knowledge_items', 'content_tsv', schema=schema)
    op.add_column('knowledge_items', sa.Column(
        'content_tsv', postgresql.TSVECTOR(),
        sa.Computed("to_tsvector('english', breadcrumb || ' ' || coalesce(clause, '') "
                    "|| ' ' || content)", persisted=True), nullable=False), schema=schema)
    op.create_index('ix_knowledge_items_content_tsv', 'knowledge_items', ['content_tsv'],
                    postgresql_using='gin', schema=schema)
    op.execute(sa.text(f"""
        CREATE TABLE "{schema}".knowledge_item_embeddings (
            id                  UUID PRIMARY KEY,
            knowledge_item_id   UUID NOT NULL
                                REFERENCES "{schema}".knowledge_items(id) ON DELETE CASCADE,
            embedding_model_id  UUID NOT NULL
                                REFERENCES "{schema}".embedding_models(id),
            embedding           "{vec_schema}".vector({DIMENSIONS}) NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (knowledge_item_id, embedding_model_id)
        )"""))


def downgrade() -> None:
    schema = config.assist_schema()
    op.drop_table('knowledge_item_embeddings', schema=schema)
    op.drop_index('ix_knowledge_items_content_tsv', 'knowledge_items', schema=schema)
    op.drop_column('knowledge_items', 'content_tsv', schema=schema)
    op.add_column('knowledge_items', sa.Column(
        'content_tsv', postgresql.TSVECTOR(),
        sa.Computed("to_tsvector('english', coalesce(clause, '') || ' ' || content)",
                    persisted=True), nullable=False), schema=schema)
    op.create_index('ix_knowledge_items_content_tsv', 'knowledge_items', ['content_tsv'],
                    postgresql_using='gin', schema=schema)
    op.drop_column('knowledge_items', 'breadcrumb', schema=schema)
