"""Indexes for the contract delete cascade and the audit-trail reads (P3: DB-2, DB-5)

Revision ID: d340ac8e60fd
Revises: c5e8a2f4d7b1
Create Date: 2026-11-23

Indexes only: no column, constraint, enum or data changes (`test_locked_schema_columns`
passes unchanged). Locked 41.25 already asks for ``finding_evidence.evidence_id`` and for
indexes "based on actual query patterns"; the full-stack audit of 2026-11-23 measured both:

* DB-2: deleting a contract cascades to its evidence, and each deleted evidence row's FK
  check seq-scanned the four tables pointing at ``document_evidence`` and
  ``assist.conversation_evidence.chunk_id`` (SET NULL, so only non-null rows are indexed);
* DB-5: nine reads filter ``audit_events`` by ``action`` (+ ``entity_id``, ordered by
  ``timestamp``) and no index led with ``action``.

Built ``CONCURRENTLY`` so the live API keeps writing while the deploy migrates
(``audit_events`` takes a row on nearly every request). That cannot run inside the
migration's transaction, hence the autocommit block — which keeps the migrate role:
``set_role`` issues a session-level ``SET ROLE`` (55.2), and the block only switches the
connection to autocommit (proven against a role-separated copy, P3 build report).
A failed concurrent build leaves an INVALID index behind; this migration drops such a
leftover before building, and refuses to finish unless every index is valid. The lock
wait is bounded so a session idle in a transaction fails the deploy instead of hanging it
(the deploy then stops before restarting the API; re-running it is safe).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = "d340ac8e60fd"
down_revision = "c5e8a2f4d7b1"
branch_labels = None
depends_on = None

# A concurrent build waits for every transaction that could see the table; Ask turns
# hold theirs for up to ~1.5 min (P1's request log), so a minute per wait, then fail.
LOCK_TIMEOUT = "60s"

# (name, table, columns, in the assist schema, partial-index predicate)
INDEXES: tuple[tuple[str, str, list[str], bool, str | None], ...] = (
    ("ix_unmatched_provisions_evidence_id", "unmatched_provisions", ["evidence_id"],
     False, None),
    ("ix_evaluation_evidence_evidence_id", "evaluation_evidence", ["evidence_id"],
     False, None),
    ("ix_finding_evidence_evidence_id", "finding_evidence", ["evidence_id"], False, None),
    ("ix_obligation_extractions_evidence_id", "obligation_extractions", ["evidence_id"],
     True, None),
    ("ix_conversation_evidence_chunk_id", "conversation_evidence", ["chunk_id"],
     True, "chunk_id IS NOT NULL"),
    ("ix_audit_events_action_entity_id_timestamp", "audit_events",
     ["action", "entity_id", "timestamp"], False, None),
)


def _valid(name: str, schema: str | None) -> bool | None:
    """True/False for a valid/INVALID index, None when there is none."""
    qualified = f'"{schema}".{name}' if schema else name
    return op.get_bind().execute(sa.text(
        "SELECT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:n)"),
        {"n": qualified}).scalar()


def upgrade() -> None:
    assist = config.assist_schema()
    with op.get_context().autocommit_block():
        op.execute(f"SET lock_timeout = '{LOCK_TIMEOUT}'")
        try:
            for name, table, columns, in_assist, where in INDEXES:
                schema = assist if in_assist else None
                if _valid(name, schema) is False:      # a failed earlier build's leftover
                    op.drop_index(name, table_name=table, schema=schema,
                                  postgresql_concurrently=True, if_exists=True)
                op.create_index(name, table, columns, schema=schema,
                                postgresql_where=sa.text(where) if where else None,
                                postgresql_concurrently=True, if_not_exists=True)
                if _valid(name, schema) is not True:
                    raise RuntimeError(f"index {name} is missing or INVALID after its "
                                       "concurrent build; the migration is not complete")
        finally:
            op.execute("RESET lock_timeout")


def downgrade() -> None:
    assist = config.assist_schema()
    with op.get_context().autocommit_block():
        op.execute(f"SET lock_timeout = '{LOCK_TIMEOUT}'")
        try:
            for name, table, _, in_assist, _ in reversed(INDEXES):
                op.drop_index(name, table_name=table, schema=assist if in_assist else None,
                              postgresql_concurrently=True, if_exists=True)
        finally:
            op.execute("RESET lock_timeout")
