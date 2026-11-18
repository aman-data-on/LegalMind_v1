"""AM-408 — "Note for Legal" on Send to Legal (AB-213 D3)

Revision ID: e4b9a2d7c318
Revises: c5e2a9d7f1b4
Create Date: 2026-11-18

`review_assignments.note`: what the deal owner tells the lawyer when sending the review
(optional, plain text, shown to whoever holds the review). Additive and nullable.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e4b9a2d7c318"
down_revision = "c5e2a9d7f1b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_assignments", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("review_assignments", "note")
