"""chunk_embeddings — the ninth AM-27 table, its dimension now measured

Revision ID: c4a91f6e2d87
Revises: b1e7c4d20f39
Create Date: 2026-08-26

The A1 migration deliberately created eight of `AM-27`'s nine tables, refusing to pin a
vector dimension before a model existed to fix it — writing `vector(768)` on a guess
would have been rule 7's habit applied to DDL. That blocker is now discharged the way
`AM-26` r2 requires: the model was selected BY MEASUREMENT on the owner-ratified
77-question evaluation set (2026-08-26), the smallest candidate passing the quality bar
won, and its dimension is a property of its weights:

    sentence-transformers/all-MiniLM-L6-v2  ->  384 dimensions

The dimension is intentionally a DDL literal rather than configuration: a different
model with a different width is a NEW MIGRATION, so swapping models can never silently
leave stored vectors incomparable with fresh query vectors. That friction is the point.

Raw SQL rather than SQLAlchemy column types, because the `vector` type belongs to the
pgvector extension and the application deliberately carries no pgvector Python
dependency — vectors cross the wire as text literals cast in SQL.

No ANN index is created, deliberately. Retrieval is scoped to ONE document version
(`AM-25` r6 — authorization inside the query), so a query scans at most a few hundred
rows exactly, with zero recall loss. An approximate index pays off at corpus scale and
is exactly where pgvector < 0.8.0's filtered-scan starvation bites (see preflight);
adding one is a measured decision for the corpus phase, not a default.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'c4a91f6e2d87'
down_revision = 'b1e7c4d20f39'
branch_labels = None
depends_on = None

DIMENSIONS = 384  # all-MiniLM-L6-v2, read from the model graph and verified in tests


def upgrade() -> None:
    schema = config.assist_schema()
    # The extension is a deployment precondition (superuser-only, not trusted); the
    # preflight reports it. The TYPE is schema-qualified from a live lookup for the
    # same reason the A1 migration qualifies `gin_trgm_ops`: the test harness pins
    # `search_path` to a private per-run schema (`F-4`), so an unqualified `vector`
    # does not resolve there, and widening the path would undo that isolation.
    vec_schema = op.get_bind().execute(sa.text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'"
    )).scalar()
    if not vec_schema:
        raise RuntimeError(
            "the pgvector extension is not installed in this database; it is a "
            "deployment precondition (see legalmind.deploy.preflight) and cannot be "
            "created by the application role")
    op.execute(sa.text(f"""
        CREATE TABLE "{schema}".chunk_embeddings (
            id                  uuid PRIMARY KEY,
            chunk_id            uuid NOT NULL
                                REFERENCES "{schema}".chunks(id) ON DELETE CASCADE,
            embedding_model_id  uuid NOT NULL
                                REFERENCES "{schema}".embedding_models(id),
            embedding           "{vec_schema}".vector({DIMENSIONS}) NOT NULL,
            created_at          timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_chunk_embeddings_chunk_model
                UNIQUE (chunk_id, embedding_model_id)
        )
    """))
    op.execute(sa.text(
        f'CREATE INDEX ix_chunk_embeddings_chunk_id '
        f'ON "{schema}".chunk_embeddings (chunk_id)'))


def downgrade() -> None:
    schema = config.assist_schema()
    op.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".chunk_embeddings'))
