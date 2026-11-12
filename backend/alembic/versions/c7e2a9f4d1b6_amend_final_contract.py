"""An amendment may amend a Final contract, not only a signed one (`AM-318`)

Revision ID: c7e2a9f4d1b6
Revises: b4f8e2a6d9c1
Create Date: 2026-11-09

The deal cycle ends at the final clean copy (owner, 2026-11-06): stamping and signing
happen in another tool, so a new deal never gets an execution record. The governed-by
trigger (`AM-267`/`AM-309`, migration ``b4f8e2a6d9c1``) refused an amendment unless its
parent was SIGNED; it now also admits a parent holding a final contract — a version with
``package_of`` (`AM-307`) or ``final_copy_of`` (`AM-318`). The application checks the
rest (the final copy's contract decision is Sign as is). Every other rule of the trigger
is unchanged. The old migration is not edited: this one replaces the function, and its
downgrade puts the old body back.
"""
from __future__ import annotations

from alembic import op

revision = "c7e2a9f4d1b6"
down_revision = "b4f8e2a6d9c1"
branch_labels = None
depends_on = None

_FINAL = """
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
                             AND (metadata->>'version_role' = 'FINAL_SIGNED'
                                  OR metadata ? 'package_of'
                                  OR metadata ? 'final_copy_of')) THEN
            RAISE EXCEPTION 'contracts: only a Final or signed contract is amended'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""

_SIGNED_ONLY = """
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
    op.execute(_FINAL)


def downgrade() -> None:
    op.execute(_SIGNED_ONLY)
