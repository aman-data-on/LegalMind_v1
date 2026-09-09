"""finding explanations — the grounded explanation layer, assist lane (owner, 2026-09-09)

Revision ID: f3a9c2d7e1b4
Revises: c8e4a1b7d2f6
Create Date: 2026-09-09

`AM-49` (AB-15): one additive table in the assist schema caching the ONE
plain-English sentence the Finding card shows under its status. Same placement,
cascade and derived-store posture as `AM-27`'s tables and `AM-35`'s; `AM-27` r2
is untouched — no locked table, column, constraint, index or enum changes, and
`tests/test_locked_schema_columns.py` passes unchanged across this revision.

What a row is NOT: never a Finding, Evaluation, Classification, Rule Outcome or
any authoritative-lane value (`AM-25` r1). `status` is the explanation's own
three-valued state (ACCEPTED · FALLBACK · FAILED) — it shares no value with any
of the five legal axes or with the assist answer state (`AM-29` r1/r2).

`source_hash` binds a row to the exact material it was generated from
(requirement version, its approved description, the classification word, the
cited evidence rows, the prompt version): when any of those change the hash
changes, the old row stays as history and a new one is generated — the same
Finding never silently changes wording, and never keeps wording its sources no
longer support.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'f3a9c2d7e1b4'
down_revision = 'c8e4a1b7d2f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = config.assist_schema()
    op.create_table(
        'finding_explanations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('finding_id', sa.UUID(), nullable=False),
        sa.Column('requirement_version_id', sa.UUID(), nullable=False),
        # sha256 over (requirement_version_id, description, classification,
        # cited evidence ids, prompt_version) — see explanations.source_hash().
        sa.Column('source_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        # The sentence, when ACCEPTED; NULL when the model's reply was rejected
        # (FALLBACK — the card shows the approved description instead).
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=200), nullable=True),
        sa.Column('model_identity', sa.String(length=255), nullable=True),
        sa.Column('prompt_version', sa.String(length=64), nullable=False),
        # AM-30 t5: the hash of what left the building — never the payload.
        sa.Column('payload_sha256', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['finding_id'], ['findings.id'],
            name=op.f('fk_finding_explanations_finding_id'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['requirement_version_id'], ['requirement_versions.id'],
            name=op.f('fk_finding_explanations_requirement_version_id'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_finding_explanations')),
        sa.UniqueConstraint('finding_id', 'source_hash',
                            name=op.f('uq_finding_explanations_finding_source')),
        sa.CheckConstraint("status IN ('ACCEPTED', 'FALLBACK', 'FAILED')",
                           name=op.f('ck_finding_explanations_status')),
        schema=schema,
    )
    op.create_index('ix_finding_explanations_finding_id', 'finding_explanations',
                    ['finding_id'], schema=schema)


def downgrade() -> None:
    schema = config.assist_schema()
    op.drop_table('finding_explanations', schema=schema)
