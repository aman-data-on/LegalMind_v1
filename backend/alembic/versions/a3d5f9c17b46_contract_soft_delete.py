"""Contract soft-delete marker

Re-chained 2026-09-01: this revised down_revision from f2c8a1b3d4e5 to
e5b8d3f17a2c when the oidc_provider_tokens migration was reverted (owner
decision — that table had no authorising lock record; AM-36 says "No table,
column or enum changes"). Nothing about this migration itself changed. — owner-approved contract deletion (2026-09-01)

Revision ID: a3d5f9c17b46
Revises: e5b8d3f17a2c
Create Date: 2026-09-01

Adds `contracts.deleted_at`, the marker for the SOFT half of the two-mode
contract deletion the owner approved on 2026-09-01 (closing the gap `AM-31`
left explicitly open: *"No hard-delete path for a Contract exists today, and
this record does not create one or assume its shape."*).

Two modes, decided by whether the contract has ever been analyzed:

* **No Review exists** — hard delete. The row, its document versions, their
  extracted evidence, the stored bytes and the assist-lane chunks all go.
  Nothing downstream references it, so nothing is lost. This is the
  mistaken-upload case, and `AM-27 r5` requires the chunks to go with it.
* **A Review exists** — soft delete, which is what this column records. The
  contract leaves every list, summary and detail response, but its findings,
  evaluations, decisions and audit entries stay exactly where they are.

That split is what keeps **rule 17** (append-only audit trail, historical
Reviews stay reproducible) intact. Rule 17 was not authorised for override and
a hard delete of an analyzed contract would break it.

Why a nullable timestamp rather than a sixth `ContractStatus` value: that enum
is the locked 42.3 / Step 2 vocabulary, and "deleted" is not a contract
lifecycle state alongside DRAFT / ACTIVE / SUPERSEDED — it is a visibility
marker orthogonal to lifecycle. A nullable column is additive and leaves the
locked vocabulary untouched.

The index is partial (`WHERE deleted_at IS NULL`), because that is the only
predicate the read paths ever use — every list, summary and detail query now
carries it.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = 'a3d5f9c17b46'
down_revision = 'e5b8d3f17a2c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'contracts',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_contracts_deleted_at',
        'contracts',
        ['deleted_at'],
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_contracts_deleted_at', table_name='contracts')
    op.drop_column('contracts', 'deleted_at')
