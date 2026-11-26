"""Published-policy check columns — source integrity B1 (`AM-130` extension), 2026-11-26

Revision ID: c7e3a9f15b28
Revises: d340ac8e60fd
Create Date: 2026-11-26

Four nullable columns on `knowledge_sources`, written only by the published-policy
refresh (`published.refresh`):

* ``page_updated_on`` — the page's own "Last updated" date, NULL when the page gives none
  that parses (never the date LegalMind first read it — that is ``effective_from``);
* ``last_checked_ok_at`` — the last time a fetch of the live page succeeded and matched
  or replaced this version; the send gate treats a policy not confirmed in the last 26 h
  as "not re-checked" (it cannot rule out a change);
* ``final_url`` / ``http_status`` — where the last fetch ended after redirects, and its
  HTTP status (a dead page is the FINAL response 404/410 twice, never a redirect).

No backfill: NULL reads as "not re-checked", which the next daily refresh clears.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind import config

revision = "c7e3a9f15b28"
down_revision = "d340ac8e60fd"
branch_labels = None
depends_on = None

COLUMNS = (("page_updated_on", sa.Date()),
           ("last_checked_ok_at", sa.DateTime(timezone=True)),
           ("final_url", sa.String(length=512)),
           ("http_status", sa.SmallInteger()))


def upgrade() -> None:
    for name, kind in COLUMNS:
        op.add_column("knowledge_sources", sa.Column(name, kind, nullable=True),
                      schema=config.assist_schema())


def downgrade() -> None:
    for name, _ in reversed(COLUMNS):
        op.drop_column("knowledge_sources", name, schema=config.assist_schema())
