"""Pagination — locked 49.6.

Three rules, all of which exist to stop a list from behaving differently from the
single-resource endpoint beside it:

* ``page_size`` is **clamped server-side** at 100 regardless of client input.
* Ordering is explicit and stable, with a deterministic tiebreaker on ``id`` so
  pagination can neither drop nor duplicate a row.
* A collection applies the same object-level scope as its ``GET /{id}``
  counterpart — a list never leaks an object a ``GET`` would 404 on.

Filtering is an allow-list per endpoint; arbitrary field filtering is not
supported, so a filter can never become a probe for fields the caller may not see.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from legalmind.api.envelope import MAX_PAGE_SIZE


@dataclass(frozen=True)
class Page:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1),
) -> Page:
    """``page_size`` is clamped rather than rejected: a client asking for 5000
    gets 100 back, which is what 49.6 specifies."""
    return Page(page=page, page_size=min(page_size, MAX_PAGE_SIZE))


def run(db: DBSession, stmt, page: Page, *order_by: Any) -> tuple[list[Any], int]:
    """Execute a scoped SELECT as one page plus a total count.

    The count uses the same WHERE clause as the page, so ``total`` never counts
    rows the caller could not fetch.
    """
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    rows = db.execute(
        stmt.order_by(*order_by).limit(page.page_size).offset(page.offset)
    ).scalars().all()
    return list(rows), total
