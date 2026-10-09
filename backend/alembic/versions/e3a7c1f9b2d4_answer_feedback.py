"""Answer feedback — the reader's rating and the implicit signals (AM-123)

Revision ID: e3a7c1f9b2d4
Revises: f4b8d2a6c1e9
Create Date: 2026-10-08

One ADDITIVE table in the assist schema (owner D2c, 2026-10-08). No existing table,
column, constraint, index or enum changes, so `tests/test_locked_schema_columns.py`
is untouched by this revision.

  answer_feedback   one row per (assistant message, reader, signal kind)

What the answer was made of — model, prompt version, cited records and their source
versions — is NOT copied here: it is reached by join through `ai_answers` and
`answer_evidence`/`conversation_evidence`, so there is one record of it (42.1).

Evaluation data only. Nothing reads this table to change an answer: no tuning, no
retraining, no ranking (`AM-26`). It is not a legal-domain record — nothing here is a
Finding, Evaluation, Classification, Rule Outcome, Mapping State or Legal Decision
(`AM-25` r1) — and its vocabulary is shared with none of the five legal axes or the
assist answer state (`AM-29`).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'e3a7c1f9b2d4'
down_revision = 'f4b8d2a6c1e9'
branch_labels = None
depends_on = None

#: Kept in step with `api.schemas.FEEDBACK_REASON_MAX`.
REASON_MAX = 500


def upgrade() -> None:
    schema = config.assist_schema()
    op.create_table(
        'answer_feedback',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('rating', sa.String(length=4), nullable=True),
        sa.Column('reason', sa.String(length=REASON_MAX), nullable=True),
        # Deterministic, computed in code from the question and the cited domains.
        sa.Column('query_type', sa.String(length=96), nullable=False),
        # The retrieval strategy plus the live corpus stamp (`feedback.corpus_version`).
        sa.Column('corpus_version', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], [f'{schema}.messages.id'],
                                name=op.f('fk_answer_feedback_message_id'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                name=op.f('fk_answer_feedback_user_id')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_answer_feedback')),
        sa.UniqueConstraint('message_id', 'user_id', 'kind',
                            name=op.f('uq_answer_feedback_message_user_kind')),
        sa.CheckConstraint(
            "kind IN ('RATING', 'COPY', 'CITE_CLICK', 'QUICK_CLOSE', 'REASK')",
            name=op.f('ck_answer_feedback_kind')),
        # A rating only on RATING, and every RATING has one; a reason only beside it.
        sa.CheckConstraint(
            "(kind = 'RATING') = (rating IS NOT NULL) "
            "AND (rating IS NULL OR rating IN ('UP', 'DOWN')) "
            "AND (reason IS NULL OR kind = 'RATING')",
            name=op.f('ck_answer_feedback_rating')),
        schema=schema,
    )
    op.create_index('ix_answer_feedback_rating_query_type', 'answer_feedback',
                    ['rating', 'query_type', 'created_at'], schema=schema,
                    postgresql_where=sa.text("kind = 'RATING'"))


def downgrade() -> None:
    op.execute(sa.text(f'DROP TABLE IF EXISTS "{config.assist_schema()}".answer_feedback'))
