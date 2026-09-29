"""escalations — at most one ACTIVE escalation per Finding (decision 339, 2026-09-29)

Revision ID: c2d4e6f8a1b3
Revises: a4d8e1c9f2b6
Create Date: 2026-09-29

Locked 43.28 makes escalation idempotent: "an already-escalated Finding returns
its existing escalation rather than stacking a second one". The code enforced
that with a check-then-insert (`workflow/escalation.py`), which two simultaneous
requests both pass — each inserts, and `withdraw_escalation` then withdraws one
of the two, leaving the Finding escalated after its withdrawal. Found by the
2026-09-29 production system design review (§14.4, §28.4); never observed
(production held 0 escalations when this was written).

The invariant moves into the database, as the decision version did (AM-12): a
partial unique index over the ACTIVE rows only. History keeps every withdrawn
escalation — nothing about the audit trail or the table's columns changes, so
`test_locked_schema_columns.py` is unaffected. `escalate_finding` catches the
constraint under a savepoint and returns the row that won, so both callers get
the same escalation and neither gets an error.
"""
from __future__ import annotations

from alembic import op

revision = 'c2d4e6f8a1b3'
down_revision = 'a4d8e1c9f2b6'      # the semantic-recognition cache landed first (PR #130)
branch_labels = None
depends_on = None

INDEX = "uq_escalations_one_active"


def upgrade() -> None:
    op.create_index(INDEX, "escalations", ["finding_id"], unique=True,
                    postgresql_where="withdrawn_at IS NULL")


def downgrade() -> None:
    op.drop_index(INDEX, table_name="escalations")
