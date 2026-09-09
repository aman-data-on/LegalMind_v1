"""AB-13 — the counterparty becomes an entity

Revision ID: c8e4a1b7d2f6
Revises: b7c3d9e1f2a4
Create Date: 2026-09-06

Lock record AB-13 in `all_lock.md` (owner, 2026-09-06). Two objects, each
traceable to a term of that record:

1. **`counterparties`** (r1). The profile management asked for and nothing
   more — no address book, no contacts, no pipeline. `industry` and
   `relationship_notes` are NULLABLE and this migration writes neither:
   rule 21 forbids inventing company or industry information, and a
   counterparty that is not fully known yet is the normal case.

2. **`contracts.counterparty_id`** (r2). Nullable FK, ON DELETE RESTRICT —
   a company with contracts against it cannot be deleted out from under
   them, the same posture AB-12 gave `users.department_id`.

**Nothing is backfilled.** No existing contract is linked, because the only
honest source for that link is a human saying so. In particular the free-text
declarations already on `document_versions.metadata` are deliberately NOT
converted into rows (r7): they are per-version historical declarations, some
are test placeholders, and promoting a string into an identity is exactly the
invention rule 21 forbids. Rule 17 keeps them where they are.

Application tables: 30 → 31. That count coincidence does not resolve C-14
(r10), which stays open.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c8e4a1b7d2f6"
down_revision = "b7c3d9e1f2a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "counterparties",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("relationship_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_counterparties_name", "counterparties", ["name"])

    op.add_column(
        "contracts",
        sa.Column("counterparty_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_contracts_counterparty_id", "contracts", "counterparties",
        ["counterparty_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_contracts_counterparty_id", "contracts", ["counterparty_id"])


def downgrade() -> None:
    op.drop_index("ix_contracts_counterparty_id", table_name="contracts")
    op.drop_constraint("fk_contracts_counterparty_id", "contracts", type_="foreignkey")
    op.drop_column("contracts", "counterparty_id")
    op.drop_index("ix_counterparties_name", table_name="counterparties")
    op.drop_table("counterparties")
