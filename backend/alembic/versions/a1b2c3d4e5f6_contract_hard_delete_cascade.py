"""contract hard delete — cascade the deletion subtree (owner, 2026-09-09)

Revision ID: a1b2c3d4e5f6
Revises: f3a9c2d7e1b4
Create Date: 2026-09-09

AM-55 (amends AB-12's AM-40 narrowly): restores a real, unconditional
`DELETE /contracts/{id}` — owner's explicit choice, made after the tradeoff
was named: this reaches contracts with a Review too, so an analyzed
contract's Findings, Evaluations, LegalDecisions and evidence are destroyed
with it, not just hidden. Rule 17 (audit trail append-only, historical
Reviews reproducible) no longer holds for a deleted contract's Review — the
owner accepted that explicitly. What DOES survive: the `audit_events` row for
the delete itself (polymorphic entity_id, no FK to contracts), so "a contract
existed and was deleted by X at T" stays answerable even though its content
does not.

Every FK on the Contract subtree gets ON DELETE CASCADE so one `DELETE FROM
contracts WHERE id = :id` does the rest at the database level — no hand-rolled
cascade code. The assist schema (chunks, finding_explanations, etc.) already
cascades from `contracts`/`document_versions`/`findings` per AM-27/AM-49; only
the core schema needed this.

Archive is untouched — AM-40's `archived_at` stays as the reversible, "keep
everything" option. Delete is now the second, destructive option beside it.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f3a9c2d7e1b4'
branch_labels = None
depends_on = None

# (table, column, referenced table) — every FK in the Contract deletion
# subtree that was NO ACTION and needs to become CASCADE.
EDGES = [
    ("document_versions", "contract_id", "contracts"),
    ("document_processing_runs", "document_version_id", "document_versions"),
    ("document_evidence", "document_version_id", "document_versions"),
    ("document_evidence", "processing_run_id", "document_processing_runs"),
    ("reviews", "contract_id", "contracts"),
    ("reviews", "document_version_id", "document_versions"),
    ("findings", "review_id", "reviews"),
    ("evaluations", "finding_id", "findings"),
    ("finding_evidence", "finding_id", "findings"),
    ("finding_evidence", "evidence_id", "document_evidence"),
    ("evaluation_evidence", "evaluation_id", "evaluations"),
    ("evaluation_evidence", "evidence_id", "document_evidence"),
    ("legal_decisions", "finding_id", "findings"),
    ("legal_decisions", "evaluation_id", "evaluations"),
    ("unmatched_provisions", "review_id", "reviews"),
    ("unmatched_provisions", "evidence_id", "document_evidence"),
]


def upgrade() -> None:
    for table, column, ref in EDGES:
        fk = f"fk_{table}_{column}"
        op.drop_constraint(fk, table, type_="foreignkey")
        op.create_foreign_key(fk, table, ref, [column], ["id"], ondelete="CASCADE")
    # Composite FK keeping a decision on its Evaluation's own Finding — not
    # covered by the simple edges above, needs the same treatment.
    op.drop_constraint("fk_legal_decisions_evaluation_same_finding",
                       "legal_decisions", type_="foreignkey")
    op.create_foreign_key(
        "fk_legal_decisions_evaluation_same_finding", "legal_decisions", "evaluations",
        ["finding_id", "evaluation_id"], ["finding_id", "id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_legal_decisions_evaluation_same_finding",
                       "legal_decisions", type_="foreignkey")
    op.create_foreign_key(
        "fk_legal_decisions_evaluation_same_finding", "legal_decisions", "evaluations",
        ["finding_id", "evaluation_id"], ["finding_id", "id"])
    for table, column, ref in reversed(EDGES):
        fk = f"fk_{table}_{column}"
        op.drop_constraint(fk, table, type_="foreignkey")
        op.create_foreign_key(fk, table, ref, [column], ["id"])
