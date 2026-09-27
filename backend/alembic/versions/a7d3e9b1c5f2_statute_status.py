"""Statute repeal status as a column — `AM-79` r4 / roadmap PHASE 2, 2026-09-24

Revision ID: a7d3e9b1c5f2
Revises: f4c1e8a2b7d9
Create Date: 2026-09-24

Until now "is this Act in force?" was a substring of `official_title`
("(REPEALED …)"), matched by `LIKE` in every query that needed it. Roadmap §2 and §14
make repeal status retrieval metadata in its own right. The column is backfilled from
that SAME marker — no repeal is inferred here, and none may be (rule 7) — and ingestion
writes it from the registry title thereafter. The title keeps its marker: it is the
provenance a reader sees. WITHDRAWN marks an Act refused on re-ingest (`AM-80` r9):
its row and citations stay, and neither retrieval path serves it.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = 'a7d3e9b1c5f2'
down_revision = 'f4c1e8a2b7d9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = config.assist_schema()
    op.add_column('statutes', sa.Column('status', sa.String(length=32),
                                        server_default='CURRENT', nullable=False),
                  schema=schema)
    op.create_check_constraint('ck_statutes_status', 'statutes',
                               "status IN ('CURRENT', 'REPEALED', 'WITHDRAWN')",
                               schema=schema)
    op.execute(sa.text(f"""UPDATE "{schema}".statutes SET status = 'REPEALED'
                            WHERE official_title LIKE '%REPEALED%'"""))


def downgrade() -> None:
    schema = config.assist_schema()
    # The metadata naming convention (ck_%(table_name)s_%(constraint_name)s) made
    # upgrade's constraint `ck_statutes_ck_statutes_status`; op.f() drops that exact
    # name. Found rehearsing the downgrade against a production-like copy, PHASE 13.
    op.drop_constraint(op.f('ck_statutes_ck_statutes_status'), 'statutes', type_='check',
                       schema=schema)
    op.drop_column('statutes', 'status', schema=schema)
