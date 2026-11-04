"""Filed as signed — where the signing happened (`AM-298`, AB-157)

Revision ID: a8d4c2e6f1b9
Revises: e6b3d9a1c7f5
Create Date: 2026-11-03

Forward-only and additive (Step 55). One column on `executions`: ``origin`` —
``IN_LEGALMIND`` (the record "Mark signed" closes, every row before this migration) or
``SIGNED_OUTSIDE`` (a contract filed as already signed: the executed copy uploaded and
declared Final signed, with no negotiation in LegalMind). A constant default, so the
append-only trigger is not fired by the ALTER.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a8d4c2e6f1b9"
down_revision = "e6b3d9a1c7f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("executions", sa.Column("origin", sa.String(16), nullable=False,
                                          server_default=sa.text("'IN_LEGALMIND'")))
    op.create_check_constraint("ck_executions_origin", "executions",
                               "origin IN ('IN_LEGALMIND', 'SIGNED_OUTSIDE')")


def downgrade() -> None:
    op.drop_column("executions", "origin")
