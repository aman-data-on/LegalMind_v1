"""A chat file's parser segments — the input of its temporary contract review (AM-143)

Revision ID: f1a7c3e9b2d5
Revises: e5a8c3f1d9b4
Create Date: 2026-10-15

Owner, 2026-10-15: an Ask attachment is reviewed by the same contract-review engine as a
Dashboard document, and the result is temporary — never saved as a Contract. The engine
reads evidence rows as the parser produced them; a chat file keeps no bytes (A-15) and
its chunks split and drop rows, so the parser's segments are kept beside the
attachment, and expire with it. One nullable column: no table, CHECK or enum changes.
The assist schema (`AM-27` r1), as every assist migration.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = "f1a7c3e9b2d5"
down_revision = "e5a8c3f1d9b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversation_attachments",
                  sa.Column("segments", postgresql.JSONB(), nullable=True),
                  schema=config.assist_schema())


def downgrade() -> None:
    op.drop_column("conversation_attachments", "segments",
                   schema=config.assist_schema())
