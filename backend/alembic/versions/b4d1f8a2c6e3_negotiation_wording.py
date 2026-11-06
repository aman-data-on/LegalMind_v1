"""CLM slice S2 — the lawyer's own wording, our standard and the notes on an answer

Revision ID: b4d1f8a2c6e3
Revises: a3c9e7f1b5d2
Create Date: 2026-11-03

`comparison_choices` carries the standard, the wording and the notes (`AM-285`, AB-152,
2026-11-03), and client-paper-first rows (`AM-290`). Forward-only and additive (Step 55):

* **choice** widens to 'ours' | 'theirs' | 'standard' | 'custom' (`AM-285` r1).
* **clause_version_id** — the published clause "Use our standard" inserts; required for
  'standard' (CHECK). A real FK, RESTRICT: slice S3's `clause_versions` (a3c9e7f1b5d2)
  exists, and a clause an answer names cannot vanish (`AM-70` r2's posture).
* **wording**, **wording_sha256** — "Write our wording" (`AM-284`), both required for
  'custom'; the hash is the one its Legal Decision carries (r2).
* **client_note** (≤ 500, a Word comment in the reply, `AM-284` r6) and
  **internal_note** (≤ 1000, never leaves LegalMind, `AM-285` r3).
* **left_side** — `AM-290` r2: a client-paper-first row (row key `N|THEIRS|…`) whose
  Finding no template clause realises has NO left side; every other row still has
  exactly one. A row with a realising clause anchors on `left_key` `clause:<key>`
  (r1), which the existing CHECK already admits.

Rows stay append-only versions (`AM-253`; the trigger is unchanged). New tables: 0;
columns +5 on `comparison_choices`. Downgrade refuses while any row uses what it
removes, rather than deleting answers.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "b4d1f8a2c6e3"
down_revision = "a3c9e7f1b5d2"
branch_labels = None
depends_on = None

_T = "comparison_choices"


def upgrade() -> None:
    op.add_column(_T, sa.Column("clause_version_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_comparison_choices_clause_version_id", _T, "clause_versions",
                          ["clause_version_id"], ["id"], ondelete="RESTRICT")
    for name in ("wording", "client_note", "internal_note"):
        op.add_column(_T, sa.Column(name, sa.Text(), nullable=True))
    op.add_column(_T, sa.Column("wording_sha256", sa.String(64), nullable=True))
    op.drop_constraint("choice", _T, type_="check")
    op.create_check_constraint("choice", _T,
                               "choice IN ('ours', 'theirs', 'standard', 'custom')")
    op.create_check_constraint("standard_clause", _T,
                               "choice <> 'standard' OR clause_version_id IS NOT NULL")
    op.create_check_constraint("custom_wording", _T,
                               "choice <> 'custom' OR (wording IS NOT NULL "
                               "AND wording_sha256 IS NOT NULL)")
    op.create_check_constraint("note_lengths", _T,
                               "char_length(wording) <= 5000 AND char_length(client_note) "
                               "<= 500 AND char_length(internal_note) <= 1000")
    op.drop_constraint("left_side", _T, type_="check")
    op.create_check_constraint("left_side", _T,
                               "num_nonnulls(left_version_id, left_key) = 1 OR "
                               "(num_nonnulls(left_version_id, left_key) = 0 "
                               "AND row_key LIKE 'N|THEIRS|%')")


def downgrade() -> None:
    op.execute(f"""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM {_T} WHERE choice IN ('standard', 'custom')
                   OR num_nonnulls(left_version_id, left_key) = 0) THEN
            RAISE EXCEPTION 'comparison_choices holds S2 answers; downgrade refused';
        END IF; END $$;""")
    op.drop_constraint("left_side", _T, type_="check")
    op.create_check_constraint("left_side", _T, "num_nonnulls(left_version_id, left_key) = 1")
    for name in ("note_lengths", "custom_wording", "standard_clause", "choice"):
        op.drop_constraint(name, _T, type_="check")
    op.create_check_constraint("choice", _T, "choice IN ('ours', 'theirs')")
    op.drop_constraint("fk_comparison_choices_clause_version_id", _T, type_="foreignkey")
    for name in ("wording_sha256", "internal_note", "client_note", "wording",
                 "clause_version_id"):
        op.drop_column(_T, name)
