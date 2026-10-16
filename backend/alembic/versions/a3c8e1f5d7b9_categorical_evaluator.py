"""A third evaluator type, CATEGORICAL — a stated value against the allowed ones (AM-148)

Revision ID: a3c8e1f5d7b9
Revises: f1a7c3e9b2d5
Create Date: 2026-10-16

Owner, 2026-10-16: a customer's markup moved the courts and the arbitration seat to
Bengaluru and the review read "Acceptable", because PRESENCE asks only whether a dispute
clause exists (45D). Constitution §22 states the position as a VALUE — "courts at Pune
… seated in Pune". AM-148 amends AM-16 to add the evaluator that reads it. One enum
value; no table, column or CHECK changes.
"""
from __future__ import annotations

from alembic import op

revision = "a3c8e1f5d7b9"
down_revision = "f1a7c3e9b2d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE may not run inside the migration's transaction on every supported
    # PostgreSQL, so it runs in its own autocommit block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE evaluator_type ADD VALUE IF NOT EXISTS 'CATEGORICAL'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value. Rows written with it are the record of
    # Reviews that used it (rule 17), so the value is deliberately left in place.
    pass
