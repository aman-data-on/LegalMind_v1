"""A chat's own model choice (AM-122)

Revision ID: c2d7e4a9b1f6
Revises: f4b8d2a6c1e9
Create Date: 2026-10-08

One nullable column on `assist.conversations`: the model the reader chose for this
chat ("gemini", "deepseek", "bonsai" — the registry's own ids). NULL means "never
chosen", and the server's default answers exactly as before, so every existing row
reads as it did. The choice lived in the browser tab until now (sessionStorage), so a
chat reopened elsewhere silently went back to Gemini (owner, 2026-10-08). No locked
table changes, so `tests/test_locked_schema_columns.py` is untouched by this revision.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'c2d7e4a9b1f6'
down_revision = 'b5d9f2a4c7e1'
branch_labels = None
depends_on = None

#: Kept in step with `api.schemas.MODEL_ID_MAX`.
MODEL_ID_MAX = 32


def upgrade() -> None:
    op.add_column('conversations', sa.Column('model', sa.String(length=MODEL_ID_MAX),
                                             nullable=True),
                  schema=config.assist_schema())
    # A fixed reply (no model ran) now stores no latency, so the footer can tell it
    # from a floor (a model ran, its draft was not used). Rows written before this
    # carry the pre-router's own milliseconds; the fastest floor on record took 3,094
    # ms (a seed search alone is ~1 s), so under one second is a fixed reply. A
    # bookkeeping column of the assist lane only — no legal or audit table. ONE-WAY:
    # the downgrade does not restore these values, and a floor that failed inside a
    # second (none on record) would now read as an instant reply.
    op.execute(f'UPDATE "{config.assist_schema()}".ai_answers SET latency_ms = NULL '
               "WHERE model_identity IS NULL AND latency_ms < 1000")


def downgrade() -> None:
    op.drop_column('conversations', 'model', schema=config.assist_schema())
