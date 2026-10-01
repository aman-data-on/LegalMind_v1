"""Ask attachments, the evidence ledger, and document attributes (Ask plan 1B/1C/1.13)

Revision ID: a9e4c2f7b1d3
Revises: c2d4e6f8a1b3
Create Date: 2026-10-01

Six ADDITIVE tables in the assist schema, as the owner-approved design note specifies
(`docs/architecture/ASK_AGENT_TABLES_DESIGN_NOTE.md`, D13/D14). No existing table,
column, constraint, index or enum changes, so `tests/test_locked_schema_columns.py`
is untouched by this revision. Applied to scratch databases only until the owner
opens the staging/production gate (charter hard gate 1).

  conversation_attachments     pasted or uploaded user material, per conversation
  attachment_chunks            its retrieval units (content as written, marks apart)
  attachment_chunk_embeddings  same shape as chunk_embeddings
  conversation_evidence        the per-conversation ledger: code-assigned C/P/S/H/D/U ids
  answer_evidence              which ledger records each answer cited
  document_version_attributes  near-duplicate grouping of uploaded versions (1.13)

None of these is a legal-domain record: nothing here is a Finding, Evaluation,
Classification, Rule Outcome, Mapping State or Legal Decision (`AM-25` r1), and no
status vocabulary is shared with the five legal axes or the assist answer state.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = 'a9e4c2f7b1d3'
down_revision = 'c2d4e6f8a1b3'
branch_labels = None
depends_on = None

DIMENSIONS = 384  # the same embedding model as chunk_embeddings


def _created_at() -> sa.Column:
    return sa.Column('created_at', sa.DateTime(timezone=True),
                     server_default=sa.text('now()'), nullable=False)


def upgrade() -> None:
    schema = config.assist_schema()

    op.create_table(
        'conversation_attachments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=True),
        sa.Column('kind', sa.String(length=8), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('byte_size', sa.BigInteger(), nullable=False),
        sa.Column('content_sha256', sa.String(length=64), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('failure_code', sa.String(length=64), nullable=True),
        _created_at(),
        sa.Column('ready_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], [f'{schema}.conversations.id'],
                                name=op.f('fk_conversation_attachments_conversation_id'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], [f'{schema}.messages.id'],
                                name=op.f('fk_conversation_attachments_message_id'),
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_conversation_attachments')),
        sa.UniqueConstraint('conversation_id', 'content_sha256',
                            name=op.f('uq_conversation_attachments_conversation_sha')),
        sa.CheckConstraint("kind IN ('PASTE', 'FILE')",
                           name=op.f('ck_conversation_attachments_kind')),
        sa.CheckConstraint("status IN ('PROCESSING', 'READY', 'FAILED', 'EXPIRED')",
                           name=op.f('ck_conversation_attachments_status')),
        schema=schema,
    )
    op.create_index('ix_conversation_attachments_conversation_created',
                    'conversation_attachments', ['conversation_id', 'created_at'],
                    schema=schema)
    op.create_index('ix_conversation_attachments_expiring', 'conversation_attachments',
                    ['expires_at'], schema=schema,
                    postgresql_where=sa.text("status <> 'EXPIRED'"))

    op.create_table(
        'attachment_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('attachment_id', sa.UUID(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('location', sa.String(length=64), nullable=True),
        sa.Column('start_offset', sa.BigInteger(), nullable=True),
        sa.Column('end_offset', sa.BigInteger(), nullable=True),
        sa.Column('annotations', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
        sa.Column('chunking_algorithm_version', sa.String(length=64), nullable=False),
        sa.Column('content_tsv', postgresql.TSVECTOR(),
                  sa.Computed("to_tsvector('english', content)", persisted=True),
                  nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(['attachment_id'], [f'{schema}.conversation_attachments.id'],
                                name=op.f('fk_attachment_chunks_attachment_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_attachment_chunks')),
        sa.UniqueConstraint('attachment_id', 'ordinal',
                            name=op.f('uq_attachment_chunks_attachment_ordinal')),
        schema=schema,
    )
    op.create_index('ix_attachment_chunks_content_tsv', 'attachment_chunks',
                    ['content_tsv'], postgresql_using='gin', schema=schema)

    # Schema-qualified `vector`, exactly as chunk_embeddings does it: the test harness
    # pins search_path to a private schema (F-4), so an unqualified type would not resolve.
    vec_schema = op.get_bind().execute(sa.text(
        "SELECT n.nspname FROM pg_extension e "
        "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'"
    )).scalar()
    if not vec_schema:
        raise RuntimeError("the pgvector extension is not installed in this database; "
                           "it is a deployment precondition (legalmind.deploy.preflight)")
    op.execute(sa.text(f"""
        CREATE TABLE "{schema}".attachment_chunk_embeddings (
            id                  uuid PRIMARY KEY,
            chunk_id            uuid NOT NULL
                                REFERENCES "{schema}".attachment_chunks(id) ON DELETE CASCADE,
            embedding_model_id  uuid NOT NULL
                                REFERENCES "{schema}".embedding_models(id),
            embedding           "{vec_schema}".vector({DIMENSIONS}) NOT NULL,
            created_at          timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_attachment_chunk_embeddings_chunk_model
                UNIQUE (chunk_id, embedding_model_id)
        )
    """))

    op.create_table(
        'conversation_evidence',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        # The code-assigned label the model cites ("C3", "U1"); not a reference.
        sa.Column('evidence_key', sa.String(length=8), nullable=False),
        sa.Column('source_class', sa.String(length=1), nullable=False),
        sa.Column('domain', sa.String(length=16), nullable=False),
        sa.Column('source_ref', sa.String(length=255), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=True),
        sa.Column('position_chunk_id', sa.UUID(), nullable=True),
        sa.Column('statute_chunk_id', sa.UUID(), nullable=True),
        sa.Column('knowledge_item_id', sa.UUID(), nullable=True),
        sa.Column('attachment_chunk_id', sa.UUID(), nullable=True),
        sa.Column('authority', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('source_version', sa.String(length=64), nullable=True),
        sa.Column('location', sa.String(length=128), nullable=True),
        sa.Column('text_hash', sa.String(length=64), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('turn_message_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], [f'{schema}.conversations.id'],
                                name=op.f('fk_conversation_evidence_conversation_id'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['turn_message_id'], [f'{schema}.messages.id'],
                                name=op.f('fk_conversation_evidence_turn_message_id'),
                                ondelete='CASCADE'),
        # Pointers are a fast path only: a re-chunk NULLs them instead of deleting the
        # ledger row, and re-fetch falls back to `source_ref` (design note §3, A5-1).
        sa.ForeignKeyConstraint(['chunk_id'], [f'{schema}.chunks.id'],
                                name=op.f('fk_conversation_evidence_chunk_id'),
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['position_chunk_id'], [f'{schema}.position_chunks.id'],
                                name=op.f('fk_conversation_evidence_position_chunk_id'),
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['statute_chunk_id'], [f'{schema}.statute_chunks.id'],
                                name=op.f('fk_conversation_evidence_statute_chunk_id'),
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['knowledge_item_id'], [f'{schema}.knowledge_items.id'],
                                name=op.f('fk_conversation_evidence_knowledge_item_id'),
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['attachment_chunk_id'], [f'{schema}.attachment_chunks.id'],
                                name=op.f('fk_conversation_evidence_attachment_chunk_id'),
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_conversation_evidence')),
        sa.UniqueConstraint('conversation_id', 'evidence_key',
                            name=op.f('uq_conversation_evidence_conversation_key')),
        sa.UniqueConstraint('conversation_id', 'source_ref', 'text_hash',
                            name=op.f('uq_conversation_evidence_conversation_ref_hash')),
        sa.CheckConstraint("source_class IN ('C', 'P', 'S', 'H', 'D', 'U')",
                           name=op.f('ck_conversation_evidence_source_class')),
        sa.CheckConstraint(
            "domain IN ('DOCUMENTS', 'POSITIONS', 'CONSTITUTION', 'STATUTES', 'ATTACHMENTS')",
            name=op.f('ck_conversation_evidence_domain')),
        sa.CheckConstraint(
            "num_nonnulls(chunk_id, position_chunk_id, statute_chunk_id, "
            "knowledge_item_id, attachment_chunk_id) <= 1",
            name=op.f('ck_conversation_evidence_one_pointer')),
        schema=schema,
    )
    op.create_index('ix_conversation_evidence_turn_message_id', 'conversation_evidence',
                    ['turn_message_id'], schema=schema)

    op.create_table(
        'answer_evidence',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('answer_id', sa.UUID(), nullable=False),
        sa.Column('ledger_id', sa.UUID(), nullable=False),
        sa.Column('claim_ordinal', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['answer_id'], [f'{schema}.ai_answers.id'],
                                name=op.f('fk_answer_evidence_answer_id'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ledger_id'], [f'{schema}.conversation_evidence.id'],
                                name=op.f('fk_answer_evidence_ledger_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_answer_evidence')),
        sa.UniqueConstraint('answer_id', 'ledger_id', 'claim_ordinal',
                            name=op.f('uq_answer_evidence_answer_ledger_claim')),
        schema=schema,
    )

    op.create_table(
        'document_version_attributes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_version_id', sa.UUID(), nullable=False),
        # Copies of one agreement share it; the first member's id seeds it. Not a
        # reference — there is no groups table — hence no `_id` suffix.
        sa.Column('version_group', sa.UUID(), nullable=False),
        sa.Column('normalized_text_sha256', sa.String(length=64), nullable=False),
        sa.Column('similarity', sa.Float(), nullable=True),
        sa.Column('algorithm_version', sa.String(length=64), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'],
                                name=op.f('fk_document_version_attributes_document_version_id'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_document_version_attributes')),
        sa.UniqueConstraint('document_version_id',
                            name=op.f('uq_document_version_attributes_version')),
        schema=schema,
    )
    op.create_index('ix_document_version_attributes_group', 'document_version_attributes',
                    ['version_group'], schema=schema)


def downgrade() -> None:
    """Drops only what upgrade created, in dependency order. Storage bytes of expired or
    deleted attachments are the purge job's to remove, never a downgrade's."""
    schema = config.assist_schema()
    for table in ('answer_evidence', 'conversation_evidence', 'attachment_chunk_embeddings',
                  'attachment_chunks', 'conversation_attachments',
                  'document_version_attributes'):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{schema}".{table}'))
