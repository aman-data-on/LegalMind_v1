"""Deal brief — what Legal told the client (batch 3+4, AB-218)

Revision ID: f1a7c3e9d5b2
Revises: e4b9a2d7c318
Create Date: 2026-11-20

One new table, `deal_positions`: Legal's own words of what the client was told on this
deal (at most 500 characters), optionally when, and the client changes Legal tied to it
(``ties``, ``{row_key: "AS_TOLD" | "BEYOND"}``) — a label for the row, never a Legal
Decision, a route, an effect, an answer or a Rule Outcome.

* **append-only, versioned per position** (`AM-253` r5' pattern, migration f7c2a9e4b1d6):
  a replace, a withdrawal or a new tie is a new row, the current one the highest
  ``version_number``. `legalmind_append_only()` refuses UPDATE and DELETE; a cascade from
  a deleted contract still passes (`AM-176` r1, d8b3f1a6c4e2), so `AM-55` deletion keeps
  working. The user who recorded a row is RESTRICT: never deleted under it.
* internal (LEGAL-02): nothing that builds a reply, a package, an annexure, a send or an
  export reads this table.

New tables: 1. Downgrade drops it (the record is lost, as it did not exist before).
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "f1a7c3e9d5b2"
down_revision = "e4b9a2d7c318"
branch_labels = None
depends_on = None

_UUID = sa.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "deal_positions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("contract_id", _UUID, sa.ForeignKey("contracts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("position_key", sa.String(32), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("withdrawn", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("told_on", sa.Date(), nullable=True),
        sa.Column("ties", JSONB(), nullable=False),
        sa.Column("recorded_by", _UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("contract_id", "position_key", "version_number",
                            name="uq_deal_positions_contract_key_version"),
        sa.CheckConstraint("char_length(text) BETWEEN 1 AND 500",
                           name="ck_deal_positions_text_length"),
        sa.CheckConstraint("version_number >= 1",
                           name="ck_deal_positions_version_number"),
    )
    op.execute("CREATE TRIGGER trg_deal_positions_append_only "
               "BEFORE UPDATE OR DELETE ON deal_positions "
               "FOR EACH ROW EXECUTE FUNCTION legalmind_append_only();")


def downgrade() -> None:
    op.drop_table("deal_positions")
