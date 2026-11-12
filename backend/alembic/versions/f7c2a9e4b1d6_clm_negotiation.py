"""CLM Phase 1 — negotiate and decide: answer history, sent, collaborators, notifications

Revision ID: f7c2a9e4b1d6
Revises: e1c7a3f9b2d5
Create Date: 2026-11-02

Every Phase 1 schema change, each term traceable to AB-150 in `all_lock.md` (collected
by `AM-279`, forward-only and additive, Step 55):

* **`comparison_choices` keeps its history** (`AM-253` r5'). A choice is a versioned
  row: `version_number` (current = highest) and an optional one-line `reason` (≤ 200
  characters, by a CHECK). The one-current-row constraint becomes one row per
  (pair, row_key, version_number) — still NULLS NOT DISTINCT for a website side, and
  still leading with `right_version_id`, so it stays the read index. Existing rows
  become version 1. `legalmind_append_only()` is attached: a row is never updated or
  deleted, except by a cascade from its document version (`AM-176` r1).
* **`document_versions.sent_at` / `sent_by`** (`AM-260` r4): when a version went to the
  client, and who sent it — written once, audited `document.version_sent`.
* **`contract_collaborators`** (`AM-259` r1): who may answer a contract's changes
  beside its owner. CASCADE with the contract (the `AM-55` posture, `AM-70` r2 ruled
  explicitly); one row per (contract, user).
* **`notifications`** (`AM-273` m3): a kind and a link, never clause text, position
  or counterparty name. CASCADE with the user and with the contract it points at.

New tables: 2. Downgrade removes them and the columns, and keeps only the current
choice of each difference — the history is lost, as it did not exist before.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f7c2a9e4b1d6"
down_revision = "e1c7a3f9b2d5"
branch_labels = None
depends_on = None

#: Kept in step with `analysis.document_comparison.REASON_MAX`.
REASON_MAX = 200
_PAIR = "right_version_id, right_key, left_version_id, left_key, row_key"


def upgrade() -> None:
    op.add_column("comparison_choices",
                  sa.Column("version_number", sa.Integer(), nullable=False,
                            server_default=sa.text("1")))
    op.add_column("comparison_choices", sa.Column("reason", sa.Text(), nullable=True))
    op.create_check_constraint("reason", "comparison_choices",
                               f"char_length(reason) <= {REASON_MAX}")
    op.drop_constraint("uq_comparison_choices_pair_row", "comparison_choices",
                       type_="unique")
    op.execute("ALTER TABLE comparison_choices ADD CONSTRAINT "
               "uq_comparison_choices_pair_row_version UNIQUE NULLS NOT DISTINCT "
               f"({_PAIR}, version_number)")
    op.execute("CREATE TRIGGER trg_comparison_choices_append_only "
               "BEFORE UPDATE OR DELETE ON comparison_choices "
               "FOR EACH ROW EXECUTE FUNCTION legalmind_append_only();")

    op.add_column("document_versions",
                  sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("document_versions",
                  sa.Column("sent_by", sa.UUID(as_uuid=True),
                            sa.ForeignKey("users.id", name="fk_document_versions_sent_by"),
                            nullable=True))
    op.create_check_constraint("sent", "document_versions",
                               "(sent_at IS NULL) = (sent_by IS NULL)")

    op.create_table(
        "contract_collaborators",
        sa.Column("contract_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("contracts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("added_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_contract_collaborators_user_id", "contract_collaborators",
                    ["user_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("contract_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("link", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    # A reader's bell: their unread first, newest first.
    op.create_index("ix_notifications_user_id_created_at", "notifications",
                    ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_notifications_contract_id", "notifications", ["contract_id"],
                    postgresql_where=sa.text("contract_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("contract_collaborators")
    op.drop_constraint("sent", "document_versions", type_="check")
    op.drop_column("document_versions", "sent_by")
    op.drop_column("document_versions", "sent_at")

    op.execute("DROP TRIGGER IF EXISTS trg_comparison_choices_append_only "
               "ON comparison_choices;")
    # Only the current choice of each difference survives (the one-row shape).
    op.execute("DELETE FROM comparison_choices c USING comparison_choices n "
               "WHERE n.version_number > c.version_number "
               "AND n.row_key = c.row_key "
               "AND n.right_version_id IS NOT DISTINCT FROM c.right_version_id "
               "AND n.right_key IS NOT DISTINCT FROM c.right_key "
               "AND n.left_version_id IS NOT DISTINCT FROM c.left_version_id "
               "AND n.left_key IS NOT DISTINCT FROM c.left_key")
    op.drop_constraint("uq_comparison_choices_pair_row_version", "comparison_choices",
                       type_="unique")
    op.execute("ALTER TABLE comparison_choices ADD CONSTRAINT "
               f"uq_comparison_choices_pair_row UNIQUE NULLS NOT DISTINCT ({_PAIR})")
    op.drop_constraint("reason", "comparison_choices",
                       type_="check")
    op.drop_column("comparison_choices", "reason")
    op.drop_column("comparison_choices", "version_number")
