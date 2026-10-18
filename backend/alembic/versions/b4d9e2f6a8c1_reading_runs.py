"""reading_runs — the lawyer's second read, assist lane (AM-162, 2026-10-18)

Revision ID: b4d9e2f6a8c1
Revises: a3c8e1f5d7b9
Create Date: 2026-10-18

One additive table in the assist schema, extending AM-27's closed set under AM-162
(owner-approved lawyer-grade plan, release 3). One row per reading of a document
version: the verified items as JSONB, keyed on document text + prompt + model so a
repeat analysis asks nothing. Never a Finding, a Classification or a Rule Outcome, and
no column holds any of the five legal axes' vocabularies. No locked table changes.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = 'b4d9e2f6a8c1'
down_revision = 'a3c8e1f5d7b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = config.assist_schema()
    op.create_table(
        'reading_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_version_id', sa.UUID(), nullable=False),
        sa.Column('document_sha256', sa.String(length=64), nullable=False),
        sa.Column('prompt_sha256', sa.String(length=64), nullable=False),
        sa.Column('prompt_version', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=255), nullable=False),
        sa.Column('items', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'],
                                name=op.f('fk_reading_runs_document_version_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reading_runs')),
        sa.UniqueConstraint('document_version_id', 'document_sha256', 'prompt_sha256',
                            'model', name=op.f('uq_reading_runs_key')),
        schema=schema,
    )
    op.create_index('ix_reading_runs_cache', 'reading_runs',
                    ['document_sha256', 'prompt_sha256', 'model'], schema=schema)


def downgrade() -> None:
    schema = config.assist_schema()
    op.drop_index('ix_reading_runs_cache', table_name='reading_runs', schema=schema)
    op.drop_table('reading_runs', schema=schema)
