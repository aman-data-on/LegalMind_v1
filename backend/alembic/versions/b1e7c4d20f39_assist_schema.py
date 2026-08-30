"""assist schema — locked AM-27 (AB-3), Gate section 5b unit A1

Revision ID: b1e7c4d20f39
Revises: 9c2f41ab77e3
Create Date: 2026-08-25

`AM-27` r1: *"Assist-lane tables live in a database schema separate from the locked
tables."* r2: *"The 30 existing tables are not altered."* **This migration touches no
locked table, no locked column, no locked constraint, no locked index and no locked
enum** — `tests/test_locked_schema_columns.py` is the mechanical proof of that, and it
is expected to pass unchanged across this revision.

--------------------------------------------------------------------------
Eight tables, not nine — `chunk_embeddings` is deliberately absent
--------------------------------------------------------------------------
`AM-27` permits nine. This creates eight. `chunk_embeddings` is *"one row per chunk per
embedding model"*, and its embedding column needs a **fixed dimension**. That number is
a property of the embedding model, and `AM-26` r2 says the model is chosen by
measurement, smallest-that-passes — so no model is selected yet and no dimension is
known. Writing `vector(768)` today would put a number nobody chose into the schema,
which is rule 7's habit applied to DDL. It is created in Gate section 5b unit A3, with
the model that fixes it. `embedding_models.dimensions` is where that number will be
recorded first.

--------------------------------------------------------------------------
Why this migration does not CREATE EXTENSION vector
--------------------------------------------------------------------------
Verified on PostgreSQL 16: `pg_trgm` is a **trusted** extension, so the application
role may create it; `vector` is **not trusted** and requires superuser. The
application role is not, and must not be, a superuser — the Step 39 stack's own
least-privilege position, and a migration that demanded superuser would force one.

So pgvector is a **deployment precondition**, provisioned out of band and verified by
`legalmind.deploy.preflight`, never created here. Nothing in this revision needs it,
which is the other reason `chunk_embeddings` is not in it.

--------------------------------------------------------------------------
Schema placement
--------------------------------------------------------------------------
The schema name comes from `config.assist_schema()`. Foreign keys into the locked
tables are written **unqualified** so they resolve through `search_path` to whichever
schema the locked tables occupy — `public` in production, the private
``t_<epoch>_<random>`` in a test run. Cross-schema references with `ON DELETE CASCADE`
are verified to work in this arrangement, which is what `AM-27` r5 requires.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = 'b1e7c4d20f39'
down_revision = '9c2f41ab77e3'
branch_labels = None
depends_on = None


# `AM-29` — the SIXTH state axis. A new enum type, in the assist schema, sharing no
# name with any of the five legal axes (r1) and reusing none of the nine values r2
# forbids: UNABLE_TO_EVALUATE, NOT_APPLICABLE, AMBIGUOUS, MATCH, DEVIATION, MISSING,
# CONFLICT, ACCEPTABLE, UNACCEPTABLE.
#
# The three refusal outcomes are `AM-29` r3 verbatim, kept separate "because they have
# different causes and different remedies": nothing was retrievable; something was
# retrieved but too weak to call the model at all; the model answered and a claim
# failed verification. ANSWERED is the fourth, successful case.
ANSWER_STATE_VALUES = (
    'ANSWERED',
    'NO_EVIDENCE_RETRIEVED',
    'EVIDENCE_INSUFFICIENT',
    'CLAIM_UNSUPPORTED',
)


def upgrade() -> None:
    schema = config.assist_schema()
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    # Trusted extension, so the application role may install it — unlike `vector`,
    # which needs superuser. Used by the trigram index on chunk content, for the
    # section numbers, case numbers and party names that a stemmed full-text index
    # mangles.
    #
    # Pinned to `public` rather than left to search_path. An extension installs into
    # the first schema on the path, which in a test run is the private
    # ``t_<epoch>_<random>`` that gets dropped at teardown — so the extension would be
    # recreated per run, and its operator classes would vanish with the schema.
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public'))

    # The operator class is then schema-qualified from wherever the extension actually
    # landed, rather than adding `public` to search_path. Widening the path would give
    # every unqualified lookup in a test run a fallback into a shared schema, which is
    # the isolation the private schema exists to provide (`F-4`). Looked up rather
    # than assumed, because an extension installed before this migration may sit
    # somewhere else entirely.
    trgm_schema = op.get_bind().execute(sa.text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'pg_trgm'"
    )).scalar()
    if not trgm_schema:                      # pragma: no cover - defensive
        raise RuntimeError("pg_trgm is required for the assist schema's trigram index")

    # Created explicitly, then referenced with create_type=False so create_table
    # does not attempt a second CREATE TYPE for the same name.
    postgresql.ENUM(*ANSWER_STATE_VALUES, name='assist_answer_state',
                    schema=schema).create(op.get_bind(), checkfirst=True)
    answer_state = postgresql.ENUM(*ANSWER_STATE_VALUES, name='assist_answer_state',
                                   schema=schema, create_type=False)

    # ----------------------------------------------------------------------
    # chunks — "derived text spans of a Document Version, with page and offsets"
    #
    # `AM-27` r4: a chunk "is derived from an existing immutable Document Version and
    # references the Document Evidence row it came from. It carries no independent
    # provenance and creates no second source of truth for document content."
    #
    # Two consequences, both deliberate:
    #   * `evidence_id` is NOT NULL and singular — the locked text says "the Document
    #     Evidence row", so one chunk resolves to exactly one evidence row. A chunk is
    #     a span within an evidence row, never a concatenation across several.
    #   * page_number, section_number, section_title and source_type are NOT copied
    #     here. They live on the evidence row and are reached by join. Duplicating
    #     them would be the "independent provenance" r4 forbids, and a denormalized
    #     copy is the standard way a derived store silently drifts from its source.
    #
    # `content` is stored, and that is not a contradiction: r6 says retrieval and
    # answer records "do not duplicate document text into a second store; the text
    # remains reachable through the chunk reference" — which presupposes the chunk
    # holds it. Evidence stays authoritative; the chunk is a derived, disposable view
    # of it, and dropping this schema loses nothing that cannot be rebuilt.
    # ----------------------------------------------------------------------
    op.create_table(
        'chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_version_id', sa.UUID(), nullable=False),
        sa.Column('evidence_id', sa.UUID(), nullable=False),
        # Position within the document version. Makes the chunk sequence
        # reconstructable and gives a stable citation order.
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        # Byte offsets into the document, carried from the evidence row's own span so
        # a citation can point at an exact range. Nullable because DOCX has no
        # reliable page model and some parse paths leave offsets unset.
        sa.Column('start_offset', sa.BigInteger(), nullable=True),
        sa.Column('end_offset', sa.BigInteger(), nullable=True),
        # Which chunker produced this row. `AM-27` authorizes no run table, so the
        # algorithm version lives on the row rather than in a parent record.
        sa.Column('chunking_algorithm_version', sa.String(length=64), nullable=False),
        # Generated, so it can never disagree with `content`. A trigger or an
        # application write could drift; a generated column cannot.
        sa.Column('content_tsv', postgresql.TSVECTOR(),
                  sa.Computed("to_tsvector('english', content)", persisted=True),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        # ON DELETE CASCADE on both parents is `AM-27` r5: "Deleting a document
        # hard-deletes its chunks and embeddings. A soft-deleted document whose chunks
        # remain retrievable is a defect, not a state." Unqualified target names
        # resolve through search_path to the locked tables' schema.
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'],
                                name=op.f('fk_chunks_document_version_id'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['document_evidence.id'],
                                name=op.f('fk_chunks_evidence_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_chunks')),
        sa.UniqueConstraint('document_version_id', 'ordinal',
                            name=op.f('uq_chunks_document_version_ordinal')),
        schema=schema,
    )
    op.create_index('ix_chunks_document_version_id', 'chunks',
                    ['document_version_id'], schema=schema)
    op.create_index('ix_chunks_evidence_id', 'chunks', ['evidence_id'], schema=schema)
    # The keyword half of hybrid retrieval. NOTE for anyone quoting this elsewhere:
    # this is PostgreSQL full-text search with `ts_rank`, which is NOT BM25. True
    # BM25 needs an extension that is not authorized.
    op.create_index('ix_chunks_content_tsv', 'chunks', ['content_tsv'],
                    postgresql_using='gin', schema=schema)
    # Trigram, for exact-ish matching of section numbers, case numbers and party
    # names that stemming mangles.
    op.create_index('ix_chunks_content_trgm', 'chunks', ['content'],
                    postgresql_using='gin',
                    postgresql_ops={'content': f'{trgm_schema}.gin_trgm_ops'},
                    schema=schema)

    # ----------------------------------------------------------------------
    # embedding_models — "the embedding model registry"
    #
    # `AM-26` r4/r5: the version is pinned and recorded against every answer, and
    # weights are "obtained once, checksummed, stored locally, and never fetched at
    # runtime". `checksum` is that record. `dimensions` is where the number that will
    # eventually shape `chunk_embeddings` gets written down first.
    # ----------------------------------------------------------------------
    op.create_table(
        'embedding_models',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('dimensions', sa.Integer(), nullable=False),
        sa.Column('checksum', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_embedding_models')),
        sa.UniqueConstraint('name', 'version',
                            name=op.f('uq_embedding_models_name_version')),
        sa.CheckConstraint('dimensions > 0',
                           name=op.f('ck_embedding_models_dimensions_positive')),
        schema=schema,
    )

    # ----------------------------------------------------------------------
    # prompt_versions — "the prompt registry"
    #
    # Append-only by construction: a version number is unique per code and there is no
    # update path. `AM-30` t7 requires the prompt version to be recorded against every
    # answer, which is only meaningful if a version cannot be edited underneath it.
    # ----------------------------------------------------------------------
    op.create_table(
        'prompt_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_prompt_versions')),
        sa.UniqueConstraint('code', 'version_number',
                            name=op.f('uq_prompt_versions_code_version')),
        schema=schema,
    )

    # ----------------------------------------------------------------------
    # conversations — "an assist-lane session"
    #
    # `contract_id` is nullable on purpose: a document conversation is scoped to a
    # Contract, and a general legal-research question has no document at all. It is
    # NOT an authorization mechanism — `AM-25` r6 puts authorization inside the
    # retrieval query, resolved server-side from the session, and a column on a
    # conversation row is not that.
    # ----------------------------------------------------------------------
    op.create_table(
        'conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('contract_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                name=op.f('fk_conversations_user_id')),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'],
                                name=op.f('fk_conversations_contract_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_conversations')),
        schema=schema,
    )
    op.create_index('ix_conversations_user_id', 'conversations',
                    ['user_id'], schema=schema)
    op.create_index('ix_conversations_contract_id', 'conversations',
                    ['contract_id'], schema=schema)

    # ----------------------------------------------------------------------
    # messages — "one row per turn"
    #
    # Append-only: unique ordinal per conversation, no update path. `role` is a plain
    # constrained string rather than an enum, deliberately — it is a transport
    # concern, not a controlled legal vocabulary, and minting an enum type for it
    # would put a non-legal vocabulary next to the five axes.
    # ----------------------------------------------------------------------
    op.create_table(
        'messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], [f'{schema}.conversations.id'],
                                name=op.f('fk_messages_conversation_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_messages')),
        sa.UniqueConstraint('conversation_id', 'ordinal',
                            name=op.f('uq_messages_conversation_ordinal')),
        sa.CheckConstraint("role IN ('USER', 'ASSISTANT')",
                           name=op.f('ck_messages_role')),
        schema=schema,
    )
    op.create_index('ix_messages_conversation_id', 'messages',
                    ['conversation_id'], schema=schema)

    # ----------------------------------------------------------------------
    # retrieval_runs — "the retrieval record behind an answer: query, filters,
    #                   chunk ids, scores"
    #
    # `results` is JSONB holding [{chunk_id, score, rank}]. Two things about that.
    #
    # It is a variable-length list and `AM-27` authorizes no child table for it — the
    # record's list of nine is closed with "No other table is authorized by this
    # record" — so a JSONB array is the only representation available. r3 restricts
    # JSONB to "genuinely variable configuration"; a result set is genuinely variable
    # though not configuration, and the alternative (parallel Postgres arrays) trades
    # one compromise for a worse one.
    #
    # The cost is real and worth stating: these chunk ids carry no foreign key, so a
    # deleted chunk leaves a dangling id here. That is tolerable precisely because
    # this is a diagnostic record of one query and not a source of truth — the
    # *verified* citations, which do need referential integrity, live in
    # `answer_citations` with a real FK.
    # ----------------------------------------------------------------------
    op.create_table(
        'retrieval_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('strategy_version', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], [f'{schema}.messages.id'],
                                name=op.f('fk_retrieval_runs_message_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_retrieval_runs')),
        schema=schema,
    )
    op.create_index('ix_retrieval_runs_message_id', 'retrieval_runs',
                    ['message_id'], schema=schema)

    # ----------------------------------------------------------------------
    # ai_answers — "the answer record: model, prompt version, answer state, latency"
    #
    # `model_identity` and `prompt_version_id` are nullable, and that nullability is
    # load-bearing rather than lazy: `AM-29` r3's `EVIDENCE_INSUFFICIENT` means "the
    # model is not called at all", so an honest record of that outcome has no model
    # and no prompt. A non-null default would fabricate a call that never happened.
    #
    # There is deliberately no `confidence` column. `AI-03` locked item 16: "The
    # system does not use generic AI confidence scores." The answer state IS the
    # signal; per-citation retrieval scores live in `retrieval_runs.results` and are
    # retrieval scores, never legal confidence.
    # ----------------------------------------------------------------------
    op.create_table(
        'ai_answers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('retrieval_run_id', sa.UUID(), nullable=True),
        sa.Column('answer_state', answer_state, nullable=False),
        sa.Column('model_identity', sa.String(length=255), nullable=True),
        sa.Column('prompt_version_id', sa.UUID(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], [f'{schema}.messages.id'],
                                name=op.f('fk_ai_answers_message_id'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['retrieval_run_id'], [f'{schema}.retrieval_runs.id'],
                                name=op.f('fk_ai_answers_retrieval_run_id'),
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['prompt_version_id'], [f'{schema}.prompt_versions.id'],
                                name=op.f('fk_ai_answers_prompt_version_id')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_answers')),
        sa.UniqueConstraint('message_id', name=op.f('uq_ai_answers_message_id')),
        schema=schema,
    )

    # ----------------------------------------------------------------------
    # answer_citations — "one row per verified claim-to-chunk link"
    #
    # There is no `verified` flag: the locked description says "one row per VERIFIED
    # link", so a row's existence is the verification. A flag would permit an
    # unverified row to exist, which is the state `AM-25` r5 forbids reaching a user.
    # ----------------------------------------------------------------------
    op.create_table(
        'answer_citations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('answer_id', sa.UUID(), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=False),
        sa.Column('claim_ordinal', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['answer_id'], [f'{schema}.ai_answers.id'],
                                name=op.f('fk_answer_citations_answer_id'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chunk_id'], [f'{schema}.chunks.id'],
                                name=op.f('fk_answer_citations_chunk_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_answer_citations')),
        sa.UniqueConstraint('answer_id', 'claim_ordinal', 'chunk_id',
                            name=op.f('uq_answer_citations_claim_chunk')),
        schema=schema,
    )
    op.create_index('ix_answer_citations_answer_id', 'answer_citations',
                    ['answer_id'], schema=schema)
    op.create_index('ix_answer_citations_chunk_id', 'answer_citations',
                    ['chunk_id'], schema=schema)


def downgrade() -> None:
    """Drop the whole schema.

    The assist tables are a derived store: every chunk is recomputable from the
    Document Evidence it came from, and no legal record lives here. So unlike the
    locked schema, dropping this loses nothing authoritative — which is also the
    property that makes every phase built on it independently revertible.
    """
    schema = config.assist_schema()
    op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
