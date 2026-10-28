"""A chat turn keeps its structured payload (AM-231)

Revision ID: e1c7a3f9b2d5
Revises: d8b3f1a6c4e2
Create Date: 2026-10-28

AM-231 (owner, 2026-10-28): a side-by-side review of a client's documents (AM-229) and the
reader's answers to the assistant's questions (AM-230) are kept with the turn, so a
reopened chat shows the same table and a question already answered is never asked again.
`assist.messages.payload` — JSONB, nullable, additive: every existing row stays NULL and
nothing reads it but those two features. Downgrade drops the column and its contents.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = "e1c7a3f9b2d5"
down_revision = "d8b3f1a6c4e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        schema=config.assist_schema(),
    )


def downgrade() -> None:
    op.drop_column("messages", "payload", schema=config.assist_schema())
