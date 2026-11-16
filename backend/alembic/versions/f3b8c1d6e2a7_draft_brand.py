"""The brand on a draft (one MSA for every brand, AM-341): which brand the client buys

Revision ID: f3b8c1d6e2a7
Revises: c7e2a9f4d1b6
Create Date: 2026-11-16

Additive: ``draft_answers.brand`` nullable, LEAPSWITCH | CLOUDPE | CLOUDJIFFY by a CHECK.
Downgrade drops it.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3b8c1d6e2a7"
down_revision = "c7e2a9f4d1b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("draft_answers", sa.Column("brand", sa.String(16), nullable=True))
    op.create_check_constraint("brand", "draft_answers",
                               "brand IN ('LEAPSWITCH', 'CLOUDPE', 'CLOUDJIFFY')")


def downgrade() -> None:
    op.drop_constraint("brand", "draft_answers", type_="check")
    op.drop_column("draft_answers", "brand")
