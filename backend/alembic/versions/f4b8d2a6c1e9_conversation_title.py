"""A chat's own name (AM-116)

Revision ID: f4b8d2a6c1e9
Revises: a9e4c2f7b1d3
Create Date: 2026-10-06

One nullable column on `assist.conversations`: the name the reader gave the chat.
NULL means "not renamed" and the list keeps titling the chat by its first question,
so every existing row reads exactly as before. No locked table changes, so
`tests/test_locked_schema_columns.py` is untouched by this revision.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'f4b8d2a6c1e9'
down_revision = 'a9e4c2f7b1d3'
branch_labels = None
depends_on = None

#: Kept in step with `api.schemas.TITLE_MAX`.
TITLE_MAX = 120


def upgrade() -> None:
    op.add_column('conversations', sa.Column('title', sa.String(length=TITLE_MAX),
                                             nullable=True),
                  schema=config.assist_schema())


def downgrade() -> None:
    op.drop_column('conversations', 'title', schema=config.assist_schema())
