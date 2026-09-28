"""Canonical knowledge/source model — `AM-79` (AB-29), roadmap PHASE 1, 2026-09-24

Revision ID: f4c1e8a2b7d9
Revises: e9f2b6c4a173
Create Date: 2026-09-24

Roadmap §1: the original Legal Constitution stays the canonical source document, and a
structured representation sits alongside it — source → sections → subsections /
provisions → paragraphs — each item carrying the metadata retrieval needs (version,
status, jurisdiction, effective period, authority, supersession, cross-references).

Two tables, because the metadata lives at two levels:

* `knowledge_sources` — ONE row per canonical document version (the L1.10
  Constitution, the superseded L1.5). Source-level facts: type, title, version,
  status, jurisdiction, effective_from/to, authority, SHA-256 fingerprint, and
  `supersedes_id` (superseded_by is its inverse, never stored twice).
* `knowledge_items` — the hierarchy. `parent_id` is a real self-FK; `section_path`
  is the document's OWN numbering ("14", "31.2", "28.4.1"), never generated. An item
  carries its own authority and status because they vary inside one document: the
  Constitution's §31.2 "Historical exceptions" paragraph is HISTORICAL, not policy;
  its "Applicable Law / Legal Basis" provisions are the company's reading of law
  (SECONDARY_REFERENCE), not law; §31.6a is UNRATIFIED (`AM-73`'s own carve-out).

Authority and status are CHECK-constrained strings, not PG enums: none of the values
is shared with a legal axis (`AM-29` r1/r2 — asserted by test_assist_schema).
No locked table, column, constraint or enum is touched.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from legalmind import config

revision = 'f4c1e8a2b7d9'
down_revision = 'e9f2b6c4a173'
branch_labels = None
depends_on = None

AUTHORITIES = ("COMPANY_CONSTITUTION", "APPROVED_COMPANY_DOCUMENT", "EXECUTED_DOCUMENT",
               "DRAFT_DOCUMENT", "HISTORICAL_EXCEPTION", "PRIMARY_LAW",
               "SECONDARY_REFERENCE")
STATUSES = ("CURRENT", "SUPERSEDED", "HISTORICAL", "UNRATIFIED", "REPEALED")
KINDS = ("DOCUMENT", "SECTION", "SUBSECTION", "PROVISION", "PARAGRAPH")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    schema = config.assist_schema()
    op.create_table(
        'knowledge_sources',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('authority', sa.String(length=64), nullable=False),
        sa.Column('jurisdiction', sa.String(length=16), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('supersedes_id', sa.UUID(), nullable=True),
        sa.Column('source_file', sa.String(length=512), nullable=False),
        sa.Column('file_sha256', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(_in('status', STATUSES), name=op.f('ck_knowledge_sources_status')),
        sa.CheckConstraint(_in('authority', AUTHORITIES),
                           name=op.f('ck_knowledge_sources_authority')),
        sa.ForeignKeyConstraint(['supersedes_id'], [f'{schema}.knowledge_sources.id'],
                                name=op.f('fk_knowledge_sources_supersedes_id'),
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_sources')),
        sa.UniqueConstraint('source_type', 'version', name=op.f('uq_knowledge_sources_type_version')),
        schema=schema,
    )
    op.create_table(
        'knowledge_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=False),
        sa.Column('parent_id', sa.UUID(), nullable=True),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('section_path', sa.String(length=64), nullable=True),
        sa.Column('clause', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('authority', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('cross_references', postgresql.ARRAY(sa.String(length=64)),
                  server_default=sa.text("'{}'"), nullable=False),
        sa.Column('line_start', sa.Integer(), nullable=False),
        sa.Column('line_end', sa.Integer(), nullable=False),
        sa.Column('content_tsv', postgresql.TSVECTOR(),
                  sa.Computed("to_tsvector('english', coalesce(clause, '') || ' ' || content)",
                              persisted=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(_in('status', STATUSES), name=op.f('ck_knowledge_items_status')),
        sa.CheckConstraint(_in('authority', AUTHORITIES), name=op.f('ck_knowledge_items_authority')),
        sa.CheckConstraint(_in('kind', KINDS), name=op.f('ck_knowledge_items_kind')),
        sa.ForeignKeyConstraint(['source_id'], [f'{schema}.knowledge_sources.id'],
                                name=op.f('fk_knowledge_items_source_id'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], [f'{schema}.knowledge_items.id'],
                                name=op.f('fk_knowledge_items_parent_id'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_items')),
        sa.UniqueConstraint('source_id', 'ordinal', name=op.f('uq_knowledge_items_source_ordinal')),
        schema=schema,
    )
    op.create_index('ix_knowledge_items_source_section', 'knowledge_items',
                    ['source_id', 'section_path'], schema=schema)
    op.create_index('ix_knowledge_items_parent_id', 'knowledge_items', ['parent_id'], schema=schema)
    op.create_index('ix_knowledge_items_content_tsv', 'knowledge_items', ['content_tsv'],
                    postgresql_using='gin', schema=schema)


def downgrade() -> None:
    schema = config.assist_schema()
    op.drop_table('knowledge_items', schema=schema)
    op.drop_table('knowledge_sources', schema=schema)
