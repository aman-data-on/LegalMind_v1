"""obligation extractions — Key Obligations, assist lane (owner, 2026-08-31)

Revision ID: e5b8d3f17a2c
Revises: d7e2a9c41b58
Create Date: 2026-08-31

The owner authorized a new assist-lane capability this session: a descriptive
extraction of what each party has to do, grouped under the DOCUMENT'S OWN role
labels. Two additive tables in the assist schema — the same placement, cascade
and derived-store posture as AM-27's tables. **This is an addition beyond
AM-27's original nine-table list**, made on the owner's explicit instruction
(recorded in CHANGELOG and AUTO_MODE_DECISIONS, 2026-08-31); AM-27 r2 is
untouched — no locked table, column, constraint, index or enum changes, and
`tests/test_locked_schema_columns.py` passes unchanged across this revision.

What these rows are NOT: an obligation is never a Finding, an Evaluation, a
Classification, a Rule Outcome or any other authoritative-lane value (AM-25),
and no column here may ever hold one of the five legal axes' vocabularies.
`evidence_id` is NOT NULL — an extracted obligation that cannot point at the
text it came from is discarded, never stored (rule 11's spirit applied to the
assist lane).

`party_role_hint` is a constrained string, not an enum type — the same
reasoning as `messages.role`: a transport-ish, best-effort annotation, not a
controlled legal vocabulary, and minting an enum would put a non-legal
vocabulary next to the five axes. It is nullable because no code anywhere
records which contracting party is "us"; the document's own verbatim label
(`party_label`) is the honest primary grouping.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'e5b8d3f17a2c'
down_revision = 'd7e2a9c41b58'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = config.assist_schema()

    # One row per extraction attempt. Needed so "extracted, nothing found" and
    # "never extracted" stay distinguishable states, and so a FAILED attempt is
    # a countable fact rather than silence. No RUNNING state: extraction runs
    # synchronously in the request (the Ask precedent), so a row is written
    # only once the outcome is known.
    op.create_table(
        'obligation_extraction_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_version_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('model_identity', sa.String(length=255), nullable=True),
        sa.Column('prompt_version', sa.String(length=64), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['document_version_id'], ['document_versions.id'],
            name=op.f('fk_obligation_extraction_runs_document_version_id'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_obligation_extraction_runs')),
        sa.CheckConstraint("status IN ('COMPLETED', 'FAILED')",
                           name=op.f('ck_obligation_extraction_runs_status')),
        schema=schema,
    )
    op.create_index('ix_obligation_extraction_runs_document_version_id',
                    'obligation_extraction_runs', ['document_version_id'],
                    schema=schema)

    op.create_table(
        'obligation_extractions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('document_version_id', sa.UUID(), nullable=False),
        # The evidence row the obligation was read from — NOT NULL: ungrounded
        # output is discarded before it reaches this table.
        sa.Column('evidence_id', sa.UUID(), nullable=False),
        # The document's own verbatim role label ("Customer", "Provider"…).
        sa.Column('party_label', sa.String(length=200), nullable=False),
        sa.Column('party_role_hint', sa.String(length=16), nullable=True),
        sa.Column('obligation_text', sa.Text(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['run_id'], [f'{schema}.obligation_extraction_runs.id'],
            name=op.f('fk_obligation_extractions_run_id'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['document_version_id'], ['document_versions.id'],
            name=op.f('fk_obligation_extractions_document_version_id'),
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['evidence_id'], ['document_evidence.id'],
            name=op.f('fk_obligation_extractions_evidence_id'),
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_obligation_extractions')),
        sa.UniqueConstraint('run_id', 'ordinal',
                            name=op.f('uq_obligation_extractions_run_ordinal')),
        sa.CheckConstraint(
            "party_role_hint IS NULL OR party_role_hint IN "
            "('ORGANIZATION', 'COUNTERPARTY', 'BOTH', 'UNKNOWN')",
            name=op.f('ck_obligation_extractions_party_role_hint')),
        schema=schema,
    )
    op.create_index('ix_obligation_extractions_document_version_id',
                    'obligation_extractions', ['document_version_id'],
                    schema=schema)
    op.create_index('ix_obligation_extractions_run_id',
                    'obligation_extractions', ['run_id'], schema=schema)


def downgrade() -> None:
    schema = config.assist_schema()
    op.drop_table('obligation_extractions', schema=schema)
    op.drop_table('obligation_extraction_runs', schema=schema)
