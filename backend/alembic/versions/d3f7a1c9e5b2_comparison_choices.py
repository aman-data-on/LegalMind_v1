"""AB-81 / AM-136 — Diff-Talk's drafting choices, kept by LegalMind

Revision ID: d3f7a1c9e5b2
Revises: c2d7e4a9b1f6
Create Date: 2026-10-13

One new application table, `comparison_choices` (32 → 33), each term traceable to
lock record AB-81 in `all_lock.md`:

* **One row per difference per compared pair** (r1). A side is a document version
  (FK, ON DELETE CASCADE — `AM-55`'s posture, r6) or a website document key; a CHECK
  makes it exactly one. `choice` is 'ours' or 'theirs', by a CHECK.
* **The unique constraint is the read index.** Every read names a pair, so the
  constraint leads with `right_version_id` (the client's document: the most
  selective column, and the one a right-side CASCADE looks up). NULLS NOT DISTINCT,
  because a website side is a NULL version id and Postgres would otherwise let two
  rows for the same website pair coexist. `left_version_id` gets a partial index of
  its own, so deleting a version never scans the table.
* **Not a relationship** (r2): nothing here, and no endpoint, lists the pairs.

Nothing is backfilled: choices made before this lived in one browser, and the page
offers to bring them over itself, under the reader's own permission (r4).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d3f7a1c9e5b2"
down_revision = "c2d7e4a9b1f6"
branch_labels = None
depends_on = None

#: Kept in step with `analysis.document_comparison` (KEY_MAX, ROW_KEY_MAX).
KEY_MAX = 64
ROW_KEY_MAX = 200


def upgrade() -> None:
    op.create_table(
        "comparison_choices",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("left_version_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("left_key", sa.String(KEY_MAX), nullable=True),
        sa.Column("right_version_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("right_key", sa.String(KEY_MAX), nullable=True),
        sa.Column("row_key", sa.String(ROW_KEY_MAX), nullable=False),
        sa.Column("choice", sa.String(8), nullable=False),
        sa.Column("decided_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("num_nonnulls(left_version_id, left_key) = 1",
                           name="left_side"),
        sa.CheckConstraint("num_nonnulls(right_version_id, right_key) = 1",
                           name="right_side"),
        sa.CheckConstraint("choice IN ('ours', 'theirs')",
                           name="choice"),
        sa.UniqueConstraint("right_version_id", "right_key", "left_version_id", "left_key",
                            "row_key", name="uq_comparison_choices_pair_row",
                            postgresql_nulls_not_distinct=True),
    )
    op.create_index("ix_comparison_choices_left_version_id", "comparison_choices",
                    ["left_version_id"],
                    postgresql_where=sa.text("left_version_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_comparison_choices_left_version_id", table_name="comparison_choices")
    op.drop_table("comparison_choices")
