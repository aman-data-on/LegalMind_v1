"""CLM flow 5 "Final" — the execution record: stamp duty, who signed, the signed copy

Revision ID: e6b3d9a1c7f5
Revises: d2a7f4c8e1b3
Create Date: 2026-11-03

Forward-only and additive (Step 55). One new table, `executions`, authorised by `AM-279`
(`AM-274` e7) with `AM-292`'s fields, its further columns by `AM-297` (AB-156):

* **append-only history** (`AM-292` r3): every save is a new row, the current record the
  highest ``version_number`` — which is also the ``expected_version`` a save names.
  `legalmind_append_only()` refuses UPDATE and DELETE.
* **immutable once signed**: the row that carries ``signed_at`` is the last one — a
  BEFORE INSERT trigger refuses any row after it, and a partial unique index allows one.
* **RESTRICT, never CASCADE** (`AM-276`, ruled here per `AM-279`): a contract, a
  document version or a user an execution row names cannot be deleted under it.
* The stamp method is one of three words the person records; the duty is text exactly as
  typed — LegalMind computes no duty and names no article or rate (`AM-292` r2).

New tables: 1. Downgrade drops it.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "e6b3d9a1c7f5"
down_revision = "d2a7f4c8e1b3"
branch_labels = None
depends_on = None

_UUID = sa.UUID(as_uuid=True)
_TS = sa.TIMESTAMP(timezone=True)

_SEALED = """
    CREATE OR REPLACE FUNCTION legalmind_execution_sealed() RETURNS trigger AS $$
    BEGIN
        IF EXISTS (SELECT 1 FROM executions
                   WHERE contract_id = NEW.contract_id AND signed_at IS NOT NULL) THEN
            RAISE EXCEPTION 'executions: the contract is signed; its record is final'
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("contract_id", _UUID,
                  sa.ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("stamp_method", sa.String(16), nullable=True),
        sa.Column("stamp_reference", sa.Text(), nullable=True),
        sa.Column("stamp_state", sa.Text(), nullable=True),
        sa.Column("duty_paid", sa.Text(), nullable=True),
        sa.Column("stamped_on", sa.Date(), nullable=True),
        sa.Column("not_stamped_ack_by", _UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("signatories", JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("seal_used", sa.Boolean(), nullable=True),
        sa.Column("witnesses", JSONB(), nullable=True),
        sa.Column("signed_document_version_id", _UUID,
                  sa.ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("differences_accepted_by", _UUID,
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("differences_reason", sa.Text(), nullable=True),
        sa.Column("comparison", JSONB(), nullable=True),
        sa.Column("signed_at", _TS, nullable=True),
        sa.Column("recorded_by", _UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("created_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("contract_id", "version_number",
                            name="uq_executions_contract_version"),
        sa.CheckConstraint("stamp_method IN ('E_STAMP', 'STAMP_PAPER', 'NOT_STAMPED')",
                           name="ck_executions_stamp_method"),
        sa.CheckConstraint("version_number >= 1", name="ck_executions_version_number"),
        sa.CheckConstraint("(differences_accepted_by IS NULL) = (differences_reason IS NULL)",
                           name="ck_executions_differences_accepted"),
        sa.CheckConstraint("signed_at IS NULL OR signed_document_version_id IS NOT NULL",
                           name="ck_executions_signed_copy"),
    )
    op.create_index("uq_executions_signed_once", "executions", ["contract_id"],
                    unique=True, postgresql_where=sa.text("signed_at IS NOT NULL"))
    op.execute("CREATE TRIGGER trg_executions_append_only "
               "BEFORE UPDATE OR DELETE ON executions "
               "FOR EACH ROW EXECUTE FUNCTION legalmind_append_only();")
    op.execute(_SEALED)
    op.execute("CREATE TRIGGER trg_executions_sealed BEFORE INSERT ON executions "
               "FOR EACH ROW EXECUTE FUNCTION legalmind_execution_sealed();")


def downgrade() -> None:
    op.drop_table("executions")
    op.execute("DROP FUNCTION IF EXISTS legalmind_execution_sealed()")
