"""AM-399 — "Ask the client" on any change: a question in our reply

Revision ID: c5e2a9d7f1b4
Revises: f3b8c1d6e2a7
Create Date: 2026-11-17

`comparison_choices.choice` widens to 'ask' (AB-211 `AM-399`): the client's text stays and
the question — ``client_note``, required for 'ask' (CHECK) — goes into our reply as a Word
comment. Forward-only and additive; downgrade refuses while any row uses 'ask'.
"""
from __future__ import annotations

from alembic import op

revision = "c5e2a9d7f1b4"
down_revision = "f3b8c1d6e2a7"
branch_labels = None
depends_on = None

_T = "comparison_choices"


def upgrade() -> None:
    op.drop_constraint("choice", _T, type_="check")
    op.create_check_constraint("choice", _T,
                               "choice IN ('ours', 'theirs', 'standard', 'custom', 'ask')")
    op.create_check_constraint("ask_question", _T,
                               "choice <> 'ask' OR client_note IS NOT NULL")


def downgrade() -> None:
    op.execute(f"""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM {_T} WHERE choice = 'ask') THEN
            RAISE EXCEPTION 'comparison_choices holds Ask the client answers; downgrade refused';
        END IF; END $$;""")
    op.drop_constraint("ask_question", _T, type_="check")
    op.drop_constraint("choice", _T, type_="check")
    op.create_check_constraint("choice", _T,
                               "choice IN ('ours', 'theirs', 'standard', 'custom')")
