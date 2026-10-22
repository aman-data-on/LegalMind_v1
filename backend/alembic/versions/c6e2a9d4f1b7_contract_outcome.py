"""A point not applicable to this contract, and the decision on the whole contract (AM-173/AM-174)

Revision ID: c6e2a9d4f1b7
Revises: b4d9e2f6a8c1
Create Date: 2026-10-22

Owner, 2026-10-22: a lawyer must be able to say a point does not apply to this contract,
and a review must end with what to do with the contract. AM-173 adds one DecisionType
value; AM-174 adds one append-only table for the reviewer's outcome on the whole
contract, its own enum type (never one of the five axes). No locked table changes.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c6e2a9d4f1b7"
down_revision = "b4d9e2f6a8c1"
branch_labels = None
depends_on = None

OUTCOMES = ("SIGN_AS_IS", "SIGN_WITH_CHANGES", "DO_NOT_SIGN", "ON_HOLD")


def upgrade() -> None:
    # ADD VALUE may not run inside the migration's transaction on every supported
    # PostgreSQL, so it runs in its own autocommit block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE decision_type "
                   "ADD VALUE IF NOT EXISTS 'NOT_APPLICABLE_TO_CONTRACT'")
    outcome = postgresql.ENUM(*OUTCOMES, name="contract_outcome")
    outcome.create(op.get_bind(), checkfirst=True)
    column = postgresql.ENUM(*OUTCOMES, name="contract_outcome", create_type=False)
    op.create_table(
        "contract_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("outcome", column, nullable=False),
        sa.Column("suggested", column, nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"],
                                name=op.f("fk_contract_outcomes_review_id"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"],
                                name=op.f("fk_contract_outcomes_decided_by")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_outcomes")),
        sa.UniqueConstraint("review_id", "version_number",
                            name="uq_contract_outcomes_review_version"),
    )


def downgrade() -> None:
    op.drop_table("contract_outcomes")
    postgresql.ENUM(name="contract_outcome").drop(op.get_bind(), checkfirst=True)
    # PostgreSQL cannot drop an enum value; decisions written with it are the record of
    # Reviews that used it (rule 17), so NOT_APPLICABLE_TO_CONTRACT stays.
