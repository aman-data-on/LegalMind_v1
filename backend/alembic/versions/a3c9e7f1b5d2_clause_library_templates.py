"""CLM slice S3 — clause library, templates, generated drafts, saved answers

Revision ID: a3c9e7f1b5d2
Revises: f7c2a9e4b1d6
Create Date: 2026-11-03

Four new tables, each authorised by `AM-279` (AB-150, 2026-11-02; `draft_answers` by
`AM-265` d1). Forward-only and additive (Step 55).

* **`clause_versions`** — a clause of the library, one row per (clause_key, version).
  FROZEN once it leaves DRAFT: `legalmind_frozen_once_approved()` lets only the status
  move (DRAFT→APPROVED→RETIRED, or DRAFT→RETIRED) with the approval columns written in
  that same update; any other change, and any DELETE of a non-DRAFT row, is refused.
  No cascade: nothing owns a clause (`AM-70` r2 ruled here: RESTRICT).
* **`template_versions`** — the same freeze (DRAFT→APPROVED→PUBLISHED→RETIRED, a DRAFT
  or APPROVED version may be RETIRED), one PUBLISHED version per `template_key` by a
  partial unique index, and a PUBLISHED row must name the snapshot its publish check
  ran against. RESTRICT from `configuration_snapshots` (a snapshot is never deleted).
* **`contract_drafts`** — what generated a contract version. CASCADE with its contract
  and its document version (the `AM-55` posture); RESTRICT on its template version,
  so a template that generated a contract cannot vanish. `legalmind_append_only()`:
  insert-only, a cascade passing (`AM-176` r1).
* **`draft_answers`** — answers before "Save as v1" (`AM-265` d1). Mutable by design
  (a person is still typing); SET NULL with its counterparty, RESTRICT on its
  template version.

New tables: 4 (36 → 40, counted from this migration). Downgrade drops them and the
trigger function.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "a3c9e7f1b5d2"
down_revision = "f7c2a9e4b1d6"
branch_labels = None
depends_on = None

_FROZEN = """
    CREATE OR REPLACE FUNCTION legalmind_frozen_once_approved() RETURNS trigger AS $$
    -- TG_ARGV: the permitted status moves, as 'FROM>TO'. The `kept` columns change
    -- only WITH such a move; nothing else of a row that left DRAFT ever changes.
    DECLARE
        moving boolean;
        kept text[] := ARRAY['status', 'approved_by', 'approved_at', 'published_by',
                             'published_at', 'checked_snapshot_id'];
    BEGIN
        IF TG_OP = 'DELETE' THEN
            IF OLD.status = 'DRAFT' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION '% % is %, and cannot be deleted', TG_TABLE_NAME, OLD.id,
                OLD.status USING ERRCODE = 'restrict_violation';
        END IF;
        moving := OLD.status IS DISTINCT FROM NEW.status;
        IF moving AND NOT ((OLD.status || '>' || NEW.status) = ANY (TG_ARGV)) THEN
            RAISE EXCEPTION '% % may not move from % to %', TG_TABLE_NAME, OLD.id,
                OLD.status, NEW.status USING ERRCODE = 'restrict_violation';
        END IF;
        IF (moving AND (to_jsonb(NEW) - kept) IS DISTINCT FROM (to_jsonb(OLD) - kept))
           OR (NOT moving AND OLD.status <> 'DRAFT'
               AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)) THEN
            RAISE EXCEPTION '% % is %; it is frozen', TG_TABLE_NAME, OLD.id,
                OLD.status USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""


def _common() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'DRAFT'")),
    ]


def _users(*names: str) -> list[sa.Column]:
    return [sa.Column(n, sa.UUID(as_uuid=True), sa.ForeignKey("users.id"),
                      nullable=n not in ("created_by", "owner_id"))
            for n in names]


def upgrade() -> None:
    op.execute(_FROZEN)
    op.create_table(
        "clause_versions",
        *_common(),
        sa.Column("clause_key", sa.String(40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", JSONB(), nullable=False),
        sa.Column("realises", JSONB(), nullable=False),
        sa.Column("stance", sa.String(16), nullable=True),
        sa.Column("source", JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        *_users("created_by", "approved_by"),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("clause_key", "version", name="uq_clause_versions_key_version"),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'RETIRED')", name="status"),
        sa.CheckConstraint("stance IN ('NON_NEGOTIABLE', 'PREFERRED', 'FLEXIBLE')",
                           name="stance"),
        sa.CheckConstraint("(status = 'DRAFT') OR (approved_by IS NOT NULL)",
                           name="approved"),
    )
    op.execute("CREATE TRIGGER trg_clause_versions_frozen BEFORE UPDATE OR DELETE ON "
               "clause_versions FOR EACH ROW EXECUTE FUNCTION legalmind_frozen_once_approved"
               "('DRAFT>APPROVED', 'APPROVED>RETIRED', 'DRAFT>RETIRED');")

    op.create_table(
        "template_versions",
        *_common(),
        sa.Column("template_key", sa.String(64), nullable=False),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("brand", sa.String(32), nullable=True),
        *(sa.Column(n, JSONB(), nullable=False)
          for n in ("layout", "clauses", "variables", "annexures", "assets", "source")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("checked_snapshot_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("configuration_snapshots.id"), nullable=True),
        *_users("created_by", "approved_by"),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        *_users("published_by"),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("template_key", "version", name="uq_template_versions_key_version"),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'PUBLISHED', 'RETIRED')",
                           name="status"),
        sa.CheckConstraint("(status <> 'PUBLISHED') OR (checked_snapshot_id IS NOT NULL "
                           "AND published_by IS NOT NULL)", name="published"),
    )
    op.create_index("uq_template_versions_one_published", "template_versions",
                    ["template_key"], unique=True,
                    postgresql_where=sa.text("status = 'PUBLISHED'"))
    op.execute("CREATE TRIGGER trg_template_versions_frozen BEFORE UPDATE OR DELETE ON "
               "template_versions FOR EACH ROW EXECUTE FUNCTION "
               "legalmind_frozen_once_approved('DRAFT>APPROVED', 'APPROVED>PUBLISHED', "
               "'PUBLISHED>RETIRED', 'APPROVED>RETIRED', 'DRAFT>RETIRED');")

    op.create_table(
        "contract_drafts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_version_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_version_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("template_versions.id"), nullable=False),
        sa.Column("values", JSONB(), nullable=False),
        sa.Column("model_hash", sa.String(64), nullable=False),
        sa.Column("renderer_version", sa.String(64), nullable=False),
        sa.Column("libreoffice_version", sa.String(128), nullable=True),
        sa.Column("clean_storage_key", sa.Text(), nullable=True),
        sa.Column("pdf_storage_key", sa.Text(), nullable=True),
        *_users("created_by"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("document_version_id",
                            name="uq_contract_drafts_document_version_id"),
    )
    op.create_index("ix_contract_drafts_contract_id", "contract_drafts", ["contract_id"])
    op.execute("CREATE TRIGGER trg_contract_drafts_append_only BEFORE UPDATE OR DELETE ON "
               "contract_drafts FOR EACH ROW EXECUTE FUNCTION legalmind_append_only();")

    op.create_table(
        "draft_answers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_version_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("template_versions.id"), nullable=False),
        sa.Column("counterparty_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("counterparties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answers", JSONB(), nullable=False),
        *_users("owner_id", "created_by"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_draft_answers_owner_id", "draft_answers", ["owner_id"])


def downgrade() -> None:
    op.drop_table("draft_answers")
    op.drop_table("contract_drafts")
    op.drop_table("template_versions")
    op.drop_table("clause_versions")
    op.execute("DROP FUNCTION IF EXISTS legalmind_frozen_once_approved()")
