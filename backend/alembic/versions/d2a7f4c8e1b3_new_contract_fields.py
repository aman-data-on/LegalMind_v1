"""CLM slice S5 — the client's legal details, the issuing entity, a saved answer's version

Revision ID: d2a7f4c8e1b3
Revises: b4d1f8a2c6e3
Create Date: 2026-11-03

Forward-only and additive (Step 55):

* **counterparties** + ten nullable columns (`AM-286` r1): entity_type, cin_or_llpin,
  pan, gstin, registered_office, notice_address, notice_email, signatory_name,
  signatory_designation, authority_reference. Format checks (CIN/LLPIN, PAN, GSTIN) are
  the API schema's, not the database's (r3).
* **contracts.issuing_entity** — LEAPSWITCH | CLOUDPE by a CHECK, nullable for every
  existing contract (`AM-287` r1).
* **draft_answers.version** — the `expected_version` of a saved questionnaire (N-1
  Option C, as every other edit takes it).

Downgrade drops them.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d2a7f4c8e1b3"
down_revision = "b4d1f8a2c6e3"
branch_labels = None
depends_on = None

COUNTERPARTY_LEGAL = ("entity_type", "cin_or_llpin", "pan", "gstin", "registered_office",
                      "notice_address", "notice_email", "signatory_name",
                      "signatory_designation", "authority_reference")


def upgrade() -> None:
    for name in COUNTERPARTY_LEGAL:
        op.add_column("counterparties", sa.Column(name, sa.String(), nullable=True))
    op.add_column("contracts", sa.Column("issuing_entity", sa.String(16), nullable=True))
    op.create_check_constraint("issuing_entity", "contracts",
                               "issuing_entity IN ('LEAPSWITCH', 'CLOUDPE')")
    op.add_column("draft_answers", sa.Column("version", sa.Integer(), nullable=False,
                                             server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("draft_answers", "version")
    op.drop_constraint("ck_contracts_issuing_entity", "contracts", type_="check")
    op.drop_column("contracts", "issuing_entity")
    for name in COUNTERPARTY_LEGAL:
        op.drop_column("counterparties", name)
