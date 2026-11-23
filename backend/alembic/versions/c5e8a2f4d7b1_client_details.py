"""Client details before drafting (batch 7, AB-220)

Revision ID: c5e8a2f4d7b1
Revises: f1a7c3e9d5b2
Create Date: 2026-11-23

Forward-only and additive (Step 55): six nullable columns on ``counterparties``, none
backfilled (rule 21 — every value is typed or uploaded by a person):

* ``registered_email`` — the company's email as on its GST certificate;
* ``signatory_email`` and ``line_of_business`` — the signatory's official email and the
  client's nature of business (spec §5: typed once on the client, never per deal);
* ``gst_certificate`` — JSONB, the one current certificate file's record (storage key,
  name, type, size, sha256, when and by whom, and what the code read from it for a
  person to confirm). The bytes stay in write-once storage; a replacement is a new
  object and an audit event;
* ``details_verified_at`` / ``details_verified_by`` — the person who ticked "checked
  against the GST certificate and the GST/MCA records", and when. SET NULL on a deleted
  user, as ``account_owner_id``.

Downgrade drops them.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "c5e8a2f4d7b1"
down_revision = "f1a7c3e9d5b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("registered_email", "signatory_email", "line_of_business"):
        op.add_column("counterparties", sa.Column(name, sa.String(), nullable=True))
    op.add_column("counterparties", sa.Column("gst_certificate", JSONB(), nullable=True))
    op.add_column("counterparties", sa.Column("details_verified_at",
                                              sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("counterparties", sa.Column(
        "details_verified_by", sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    for name in ("details_verified_by", "details_verified_at", "gst_certificate",
                 "line_of_business", "signatory_email", "registered_email"):
        op.drop_column("counterparties", name)
