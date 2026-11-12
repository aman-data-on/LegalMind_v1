"""An amendment names the signed contract it amends (`AM-267`, built under `AM-309`)

Revision ID: b4f8e2a6d9c1
Revises: a8d4c2e6f1b9
Create Date: 2026-11-05

Forward-only and additive (Step 55). One nullable column on `contracts`:
``governed_by_contract_id`` — ONE parent pointer, never a join table (`AM-267` r2),
``ON DELETE RESTRICT`` (r1; r4: a parent with children is never deleted under them).

A trigger holds the rule in the database, whoever writes the row (`AM-267` r1 as
`AM-309` amends it):

* the child is an AMENDMENT or an ORDER_FORM;
* the parent is SIGNED — an execution record with ``signed_at``, or a version declared
  FINAL_SIGNED before the signing step (`AM-298` r4);
* the parent is not itself an amendment, nor governed by anything, and a contract that
  already governs others is never made governed (no amending an amendment, no chains in
  either order, no self-parenting);
* both carry the SAME non-null counterparty — and a parent's counterparty or type
  cannot then move away from its children.

Existing rows are untouched: the column is NULL for every one, so the ALTER fires
nothing.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b4f8e2a6d9c1"
down_revision = "a8d4c2e6f1b9"
branch_labels = None
depends_on = None

_GOVERNED = """
    CREATE OR REPLACE FUNCTION legalmind_contract_governed_by() RETURNS trigger AS $$
    DECLARE
        parent contracts%ROWTYPE;
    BEGIN
        IF TG_OP = 'UPDATE' AND EXISTS (
                SELECT 1 FROM contracts WHERE governed_by_contract_id = NEW.id)
           AND (NEW.counterparty_id IS DISTINCT FROM OLD.counterparty_id
                OR NEW.contract_type IS DISTINCT FROM OLD.contract_type) THEN
            RAISE EXCEPTION 'contracts: an amended contract keeps its client and type'
                USING ERRCODE = 'restrict_violation';
        END IF;
        IF NEW.governed_by_contract_id IS NULL THEN
            RETURN NEW;
        END IF;
        IF NEW.contract_type IS NULL OR NEW.contract_type NOT IN ('AMENDMENT', 'ORDER_FORM')
        THEN
            RAISE EXCEPTION 'contracts: only an amendment or an order form is governed by '
                            'another contract' USING ERRCODE = 'check_violation';
        END IF;
        IF EXISTS (SELECT 1 FROM contracts WHERE governed_by_contract_id = NEW.id) THEN
            RAISE EXCEPTION 'contracts: a contract with amendments is never itself '
                            'governed' USING ERRCODE = 'check_violation';
        END IF;
        SELECT * INTO parent FROM contracts WHERE id = NEW.governed_by_contract_id;
        IF parent.id = NEW.id OR parent.governed_by_contract_id IS NOT NULL
           OR parent.contract_type IS NOT DISTINCT FROM 'AMENDMENT' THEN
            RAISE EXCEPTION 'contracts: an amendment amends a contract, never an amendment'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.counterparty_id IS NULL
           OR NEW.counterparty_id IS DISTINCT FROM parent.counterparty_id THEN
            RAISE EXCEPTION 'contracts: an amendment is with the same client as its '
                            'contract' USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM executions
                       WHERE contract_id = parent.id AND signed_at IS NOT NULL)
           AND NOT EXISTS (SELECT 1 FROM document_versions
                           WHERE contract_id = parent.id
                             AND metadata->>'version_role' = 'FINAL_SIGNED') THEN
            RAISE EXCEPTION 'contracts: only a signed contract is amended'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.add_column("contracts", sa.Column(
        "governed_by_contract_id", sa.UUID(as_uuid=True),
        sa.ForeignKey("contracts.id", ondelete="RESTRICT",
                      name="fk_contracts_governed_by_contract_id"), nullable=True))
    op.create_index("ix_contracts_governed_by_contract_id", "contracts",
                    ["governed_by_contract_id"])
    op.execute(_GOVERNED)
    op.execute("CREATE TRIGGER trg_contracts_governed_by BEFORE INSERT OR UPDATE OF "
               "governed_by_contract_id, counterparty_id, contract_type ON contracts "
               "FOR EACH ROW EXECUTE FUNCTION legalmind_contract_governed_by();")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_contracts_governed_by ON contracts")
    op.execute("DROP FUNCTION IF EXISTS legalmind_contract_governed_by()")
    op.drop_index("ix_contracts_governed_by_contract_id", table_name="contracts")
    op.drop_column("contracts", "governed_by_contract_id")
