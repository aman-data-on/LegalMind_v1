"""Client Profiles — the counterparty grows a profile

Revision ID: e9f2b6c4a173
Revises: a1b2c3d4e5f6
Create Date: 2026-09-10

Owner instruction, 2026-09-10 ("Client Profiles"): give the company on the
other side of a deal a real profile page, and make it the place every document
for that company is organised under.

**No new table, and no second document store.** AB-13 (2026-09-06) already made
the counterparty an entity and already links contracts to it, so the client
profile IS the counterparty row and a client's documents ARE its contracts.
This migration only widens that row with the fields the profile screen shows.
Nothing about documents, versions, evidence, reviews or findings is touched.

Twelve nullable columns plus one NOT NULL with a default:

* `status` — ACTIVE / PROSPECTIVE / INACTIVE, the relationship state a
  non-legal reader scans the list by. Deliberately a validated STRING and not
  a Postgres enum: `document_types.py` records why the same choice was made
  for Document Type (a controlled vocabulary in tested code, no DB type to
  migrate), and adding an enum type is the heavier of the two changes. Backfills
  to ACTIVE, which is what every existing row demonstrably is — each one was
  created by someone recording a live deal.
* Everything else is NULLABLE and **nothing is backfilled** (rule 21). An
  unknown industry, website or contact is a fact about what we know, and this
  migration invents none of it. The UI renders "Not available" rather than a
  blank that looks checked.
* `account_owner_id` — who inside the organisation owns the relationship.
  ON DELETE SET NULL: a departed colleague must not make a client
  undeletable, and the profile survives them.

Locked-table snapshot: `counterparties` 7 → 19 columns; total 209 → 221.
`test_locked_schema_columns.py` moves in this same commit, which its own
docstring names as the only permitted way for that snapshot to change.
Application tables stay at 31 — C-14 is untouched and stays open.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e9f2b6c4a173"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


#: Name, type — in the order they are added, so upgrade and downgrade cannot
#: drift apart by hand-editing one of the two lists.
_PROFILE_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("legal_name", sa.String()),
    ("website", sa.String()),
    ("city", sa.String()),
    ("state_region", sa.String()),
    ("country", sa.String()),
    ("primary_contact_name", sa.String()),
    ("primary_contact_email", sa.String()),
    ("primary_contact_phone", sa.String()),
    ("legal_contact_name", sa.String()),
    ("legal_contact_email", sa.String()),
)


def upgrade() -> None:
    for name, type_ in _PROFILE_COLUMNS:
        op.add_column("counterparties", sa.Column(name, type_, nullable=True))

    # The one non-nullable addition. `server_default` is what makes it safe on a
    # table that already has rows; it stays on the column afterwards so a row
    # inserted by anything that does not name `status` is still valid.
    op.add_column(
        "counterparties",
        sa.Column("status", sa.String(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
    )
    op.create_index("ix_counterparties_status", "counterparties", ["status"])

    op.add_column(
        "counterparties",
        sa.Column("account_owner_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_counterparties_account_owner_id", "counterparties", "users",
        ["account_owner_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_counterparties_account_owner_id", "counterparties",
                    ["account_owner_id"])


def downgrade() -> None:
    op.drop_index("ix_counterparties_account_owner_id",
                  table_name="counterparties")
    op.drop_constraint("fk_counterparties_account_owner_id", "counterparties",
                       type_="foreignkey")
    op.drop_column("counterparties", "account_owner_id")
    op.drop_index("ix_counterparties_status", table_name="counterparties")
    op.drop_column("counterparties", "status")
    for name, _ in reversed(_PROFILE_COLUMNS):
        op.drop_column("counterparties", name)
