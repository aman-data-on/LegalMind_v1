"""semantic recognition cache — restores rule 9 determinism for AM-54's RECOGNITION step

Revision ID: a4d8e1c9f2b6
Revises: b8e2f6a4d1c3
Create Date: 2026-09-29

Bug report, 2026-09-22: the byte-identical NDA, re-uploaded and re-analyzed
under the SAME configuration snapshot, produced a different Finding count on
each run. Root cause, confirmed against the live database: `AM-54`'s semantic
RECOGNITION step (`analysis/semantic.adjudicate`) calls Gemini once per pinned
Requirement to verify whether a shortlisted clause addresses it, at
`temperature: 0.0` — which reduces but does not guarantee bit-reproducible
output on a hosted model. Since the verdict decides Mapping State and Mapping
State decides Finding classification, two analyses of the identical document
under the identical snapshot could disagree — a real violation of rule 9
("same inputs + same configuration snapshot + same engine version -> same
result"), not a config-timing artifact (ruled out: same file hash, same
snapshot id, same evaluator version, ten minutes apart).

This is NOT an assist-lane table (`AM-27` r1's separate schema is for the
assistive Ask/RAG lane, which never produces a Finding; this table feeds
Mapping State, which is part of the AUTHORITATIVE analysis path), so it is
created in the default/locked schema like `evaluation_evidence` and
`document_evidence`. `test_locked_schema_columns.py`'s snapshot moves in this
same commit, which is its own docstring's only permitted way for that to
happen.

Keyed on the exact prompt text sent (hashed to `prompt_sha256`), the pinned
model that answered it, and the configuration snapshot it was asked under: a
repeat analysis of the same content under the same snapshot AND the same
pinned model reuses the recorded verdict instead of re-asking Gemini. `model`
is part of the unique key, not just a stored column: `MAPPING_PROMPT_VERSION`
(`analysis/semantic.py`) is a hardcoded constant independent of
`LEGALMIND_GENERATION_MODEL`, so an operator pinning a new model (AM-30 t7)
without a reason to also bump the prompt version must get fresh verdicts from
the new model rather than this cache silently replaying the old model's. The
unique constraint on the key means a concurrent analysis race writes at most
one row per (snapshot, prompt, model) (`ON CONFLICT DO NOTHING` at the call
site); whichever wins is what every later analysis of this content, under
this snapshot and this model, will see from here on.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = 'a4d8e1c9f2b6'
down_revision = 'b8e2f6a4d1c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'semantic_recognition_cache',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('configuration_snapshot_id', sa.UUID(), nullable=False),
        sa.Column('prompt_version', sa.String(), nullable=False),
        sa.Column('prompt_sha256', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('payload_sha256', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['configuration_snapshot_id'], ['configuration_snapshots.id'],
            name=op.f('fk_semantic_recognition_cache_configuration_snapshot_id'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_semantic_recognition_cache')),
        sa.UniqueConstraint('configuration_snapshot_id', 'prompt_version', 'prompt_sha256',
                            'model', name='uq_semantic_recognition_cache_key'),
    )


def downgrade() -> None:
    op.drop_table('semantic_recognition_cache')
