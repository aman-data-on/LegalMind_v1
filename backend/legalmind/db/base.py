"""Declarative base and shared column conventions.

Locked basis — Step 42.1 design rules:
  2. Domain IDs use UUID.
  3. Timestamps are stored in UTC.
  4. Foreign keys enforce important relationships.
  10. JSONB is used for genuinely variable configuration, not to hide core
      relationships.
"""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, MetaData, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, mapped_column

# Explicit naming convention so Alembic autogenerate produces stable,
# reviewable constraint names across migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

UUIDType = PGUUID(as_uuid=True)
TS = DateTime(timezone=True)


class Base(DeclarativeBase):
    metadata = metadata


def pk_uuid():
    """UUID primary key (42.1 rule 2)."""
    return mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)


def fk_uuid(target: str, *, nullable: bool = False, ondelete: str | None = None,
            primary_key: bool = False):
    """UUID foreign key (42.1 rule 4)."""
    return mapped_column(
        UUIDType,
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        primary_key=primary_key,
    )


def ts_created():
    """UTC creation timestamp (42.1 rule 3, 41.27)."""
    return mapped_column(TS, nullable=False, server_default=text("now()"))


def ts_updated():
    return mapped_column(
        TS, nullable=False, server_default=text("now()"), onupdate=text("now()")
    )


def ts_nullable():
    return mapped_column(TS, nullable=True)


def jsonb_col(*, nullable: bool = True, name: str | None = None):
    """JSONB for genuinely variable configuration only (42.1 rule 10)."""
    if name:
        return mapped_column(name, JSONB, nullable=nullable)
    return mapped_column(JSONB, nullable=nullable)
