"""Domain A/C corpus tables — locked AM-32 (AB-5), approved 2026-08-27

Revision ID: d7e2a9c41b58
Revises: c4a91f6e2d87
Create Date: 2026-08-27

`AM-32` permits five new tables in the assist schema (the sixth slot — judgments —
stays reserved and is NOT created here) and column additions on the two AM-27-batch
tables. **No locked table, column, constraint, index or enum is touched** —
`tests/test_locked_schema_columns.py` passes unchanged across this revision, the
same mechanical proof AM-27 r2 named.

--------------------------------------------------------------------------
Domain A — position chunks (r3, r4, r5)
--------------------------------------------------------------------------
A position chunk references a published `company_standard_versions` row by real FK
with ON DELETE CASCADE — r3's lifecycle: superseding a standard version deletes its
chunks and the new version is chunked. There is NO positions content table; the
ratified standard remains the single source of truth, and the chunk's `content` is
composed exclusively of the ratified file's own verbatim fields (code, source
clause, source quote) by `tools/chunk_standards.py`.

--------------------------------------------------------------------------
Domain C — statutes (r6, r7)
--------------------------------------------------------------------------
The `statutes` registry makes r6's provenance record a schema fact: every
provenance column is NOT NULL, so a statute with no provenance cannot exist, not
merely "should not". Section identity lives on the chunk (r7): a Domain C citation
is Act + section, never a bare page.

--------------------------------------------------------------------------
answer_citations — per-domain FK columns (the MODIFIED TABLES clause)
--------------------------------------------------------------------------
`chunk_id` becomes nullable and two nullable siblings arrive; a CHECK enforces
exactly one of the three per row. Verified citations are where referential
integrity matters — `retrieval_runs.results` stays the JSONB diagnostic record
AM-27 designed (its entries never carried a FK; Domain A/C results are
distinguished there by a `domain` key inside each entry, a code-level convention
recorded in AUTO_MODE_DECISIONS.md).

Embedding tables use the same raw-SQL/vector-literal pattern as chunk_embeddings
(c4a91f6e2d87), with the same 384 DDL literal — one embedding model serves all
three domains (r9), so a different number here would be a defect, not a choice.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = 'd7e2a9c41b58'
down_revision = 'c4a91f6e2d87'
branch_labels = None
depends_on = None

DIMENSIONS = 384  # all-MiniLM-L6-v2 — must equal chunk_embeddings' literal (r9)


def _vector_schema() -> str:
    vec_schema = op.get_bind().execute(sa.text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'"
    )).scalar()
    if not vec_schema:
        raise RuntimeError(
            "the pgvector extension is not installed in this database; it is a "
            "deployment precondition reported by legalmind.deploy.preflight")
    return vec_schema


def _trgm_schema() -> str:
    trgm_schema = op.get_bind().execute(sa.text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'pg_trgm'"
    )).scalar()
    if not trgm_schema:                      # pragma: no cover - defensive
        raise RuntimeError("pg_trgm is required (installed by b1e7c4d20f39)")
    return trgm_schema


def upgrade() -> None:
    schema = config.assist_schema()
    trgm_schema = _trgm_schema()
    vec_schema = _vector_schema()

    # ----------------------------------------------------------------------
    # position_chunks — Domain A (r3). FK into the locked table is written
    # unqualified so it resolves through search_path, exactly as chunks' FKs do.
    # `standard_code` and `source_clause` are the citation fields r4's extractive
    # answer renders; they are copies of identifiers, not of legal content.
    # ----------------------------------------------------------------------
    op.create_table(
        'position_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('standard_version_id', sa.UUID(), nullable=False),
        sa.Column('standard_code', sa.String(length=128), nullable=False),
        sa.Column('document_type', sa.String(length=32), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_clause', sa.String(length=255), nullable=True),
        sa.Column('chunking_algorithm_version', sa.String(length=64), nullable=False),
        sa.Column('content_tsv', postgresql.TSVECTOR(),
                  sa.Computed("to_tsvector('english', content)", persisted=True),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['standard_version_id'],
                                ['company_standard_versions.id'],
                                name=op.f('fk_position_chunks_standard_version_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_position_chunks')),
        sa.UniqueConstraint('standard_version_id', 'ordinal',
                            name=op.f('uq_position_chunks_version_ordinal')),
        schema=schema,
    )
    op.create_index('ix_position_chunks_standard_version_id', 'position_chunks',
                    ['standard_version_id'], schema=schema)
    op.create_index('ix_position_chunks_content_tsv', 'position_chunks',
                    ['content_tsv'], postgresql_using='gin', schema=schema)
    op.create_index('ix_position_chunks_content_trgm', 'position_chunks',
                    ['content'], postgresql_using='gin',
                    postgresql_ops={'content': f'{trgm_schema}.gin_trgm_ops'},
                    schema=schema)

    op.execute(sa.text(f"""
        CREATE TABLE "{schema}".position_chunk_embeddings (
            id                  UUID PRIMARY KEY,
            position_chunk_id   UUID NOT NULL
                                REFERENCES "{schema}".position_chunks(id)
                                ON DELETE CASCADE,
            embedding_model_id  UUID NOT NULL
                                REFERENCES "{schema}".embedding_models(id),
            embedding           "{vec_schema}".vector({DIMENSIONS}) NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (position_chunk_id, embedding_model_id)
        )"""))
    op.execute(sa.text(
        'CREATE INDEX ix_position_chunk_embeddings_chunk_id '
        f'ON "{schema}".position_chunk_embeddings (position_chunk_id)'))

    # ----------------------------------------------------------------------
    # statutes — the Domain C registry (r6). Every provenance field NOT NULL:
    # the refusal to ingest an unprovenanced statute is a schema property.
    # `as_amended_date` is a string, not a DATE — India Code prints consolidation
    # dates in several formats and the value is provenance to be quoted verbatim,
    # never arithmetic to be done.
    # ----------------------------------------------------------------------
    op.create_table(
        'statutes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('official_title', sa.String(length=512), nullable=False),
        sa.Column('act_number_year', sa.String(length=128), nullable=False),
        sa.Column('jurisdiction', sa.String(length=16), nullable=False),
        sa.Column('source', sa.String(length=128), nullable=False),
        sa.Column('source_ref', sa.String(length=1024), nullable=False),
        sa.Column('as_amended_date', sa.String(length=64), nullable=False),
        sa.Column('file_sha256', sa.String(length=64), nullable=False),
        sa.Column('supplied_by', sa.String(length=255), nullable=False),
        sa.Column('supplied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_statutes')),
        sa.UniqueConstraint('official_title', 'as_amended_date',
                            name=op.f('uq_statutes_title_version')),
        schema=schema,
    )

    # ----------------------------------------------------------------------
    # statute_chunks — section-based (r7). `section_number` NOT NULL: a chunk
    # that cannot name its section may not exist, because a Domain C citation
    # is Act + section. Schedules and chapter headings get their own labelled
    # units ("SCHEDULE I", "CHAPTER XVII") in the same column.
    # ----------------------------------------------------------------------
    op.create_table(
        'statute_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('statute_id', sa.UUID(), nullable=False),
        sa.Column('section_number', sa.String(length=64), nullable=False),
        sa.Column('sub_section', sa.String(length=64), nullable=True),
        sa.Column('marginal_note', sa.Text(), nullable=True),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('char_start', sa.BigInteger(), nullable=True),
        sa.Column('char_end', sa.BigInteger(), nullable=True),
        sa.Column('chunking_algorithm_version', sa.String(length=64), nullable=False),
        sa.Column('content_tsv', postgresql.TSVECTOR(),
                  sa.Computed("to_tsvector('english', content)", persisted=True),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['statute_id'], [f'{schema}.statutes.id'],
                                name=op.f('fk_statute_chunks_statute_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_statute_chunks')),
        sa.UniqueConstraint('statute_id', 'ordinal',
                            name=op.f('uq_statute_chunks_statute_ordinal')),
        schema=schema,
    )
    op.create_index('ix_statute_chunks_statute_id', 'statute_chunks',
                    ['statute_id'], schema=schema)
    op.create_index('ix_statute_chunks_content_tsv', 'statute_chunks',
                    ['content_tsv'], postgresql_using='gin', schema=schema)
    op.create_index('ix_statute_chunks_content_trgm', 'statute_chunks',
                    ['content'], postgresql_using='gin',
                    postgresql_ops={'content': f'{trgm_schema}.gin_trgm_ops'},
                    schema=schema)

    op.execute(sa.text(f"""
        CREATE TABLE "{schema}".statute_chunk_embeddings (
            id                  UUID PRIMARY KEY,
            statute_chunk_id    UUID NOT NULL
                                REFERENCES "{schema}".statute_chunks(id)
                                ON DELETE CASCADE,
            embedding_model_id  UUID NOT NULL
                                REFERENCES "{schema}".embedding_models(id),
            embedding           "{vec_schema}".vector({DIMENSIONS}) NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (statute_chunk_id, embedding_model_id)
        )"""))
    op.execute(sa.text(
        'CREATE INDEX ix_statute_chunk_embeddings_chunk_id '
        f'ON "{schema}".statute_chunk_embeddings (statute_chunk_id)'))

    # ----------------------------------------------------------------------
    # answer_citations — the MODIFIED TABLES clause. chunk_id relaxes to
    # nullable, two per-domain FK siblings arrive, CHECK exactly-one. The old
    # NOT NULL was the exactly-one rule for a one-domain world; the CHECK is
    # the same rule for three.
    # ----------------------------------------------------------------------
    op.alter_column('answer_citations', 'chunk_id', nullable=True, schema=schema)
    op.add_column('answer_citations',
                  sa.Column('position_chunk_id', sa.UUID(), nullable=True),
                  schema=schema)
    op.add_column('answer_citations',
                  sa.Column('statute_chunk_id', sa.UUID(), nullable=True),
                  schema=schema)
    op.create_foreign_key(op.f('fk_answer_citations_position_chunk_id'),
                          'answer_citations', 'position_chunks',
                          ['position_chunk_id'], ['id'],
                          source_schema=schema, referent_schema=schema,
                          ondelete='CASCADE')
    op.create_foreign_key(op.f('fk_answer_citations_statute_chunk_id'),
                          'answer_citations', 'statute_chunks',
                          ['statute_chunk_id'], ['id'],
                          source_schema=schema, referent_schema=schema,
                          ondelete='CASCADE')
    op.create_check_constraint(
        op.f('ck_answer_citations_exactly_one_chunk'),
        'answer_citations',
        "(chunk_id IS NOT NULL)::int + (position_chunk_id IS NOT NULL)::int "
        "+ (statute_chunk_id IS NOT NULL)::int = 1",
        schema=schema)


def downgrade() -> None:
    schema = config.assist_schema()
    op.drop_constraint(op.f('ck_answer_citations_exactly_one_chunk'),
                       'answer_citations', schema=schema)
    op.drop_constraint(op.f('fk_answer_citations_statute_chunk_id'),
                       'answer_citations', schema=schema)
    op.drop_constraint(op.f('fk_answer_citations_position_chunk_id'),
                       'answer_citations', schema=schema)
    op.drop_column('answer_citations', 'statute_chunk_id', schema=schema)
    op.drop_column('answer_citations', 'position_chunk_id', schema=schema)
    # Restoring NOT NULL is only valid if no per-domain rows were written; a
    # downgrade across data loss is refused by the database itself here.
    op.alter_column('answer_citations', 'chunk_id', nullable=False, schema=schema)
    op.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".statute_chunk_embeddings'))
    op.drop_table('statute_chunks', schema=schema)
    op.drop_table('statutes', schema=schema)
    op.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".position_chunk_embeddings'))
    op.drop_table('position_chunks', schema=schema)
