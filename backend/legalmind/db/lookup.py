"""Narrowing a lookup that a NOT NULL foreign key already guarantees.

`Session.get` returns `Row | None` because that is true in general. It is *not* true
when the id came from a NOT NULL foreign key: locked 42.x makes `evaluations.finding_id`,
`findings.review_id` and the rest NOT NULL, so a missing row means referential
integrity has been violated, not that the caller asked for something optional.

Both readings currently produce a failure. The difference is where:

```text
without   finding.review_id  ->  AttributeError: 'NoneType' has no attribute
                                 'review_id', several frames from the cause
with      MissingReference: findings row for evaluation <id> does not exist
```

For an append-only legal record the second is worth having. It also lets the type
checker see what the schema already guarantees, so the narrowing is stated once here
rather than assumed at each of ten call sites.

This raises rather than returning a default **by design**. A default would be a
fabricated legal object (rule 15, ENG-09).
"""

from __future__ import annotations

from uuid import UUID


class MissingReference(Exception):
    """A row referenced by a NOT NULL foreign key does not exist.

    Never a request error and never a Finding: the database is inconsistent. Surfaces
    as a 500, which is correct — nothing the caller did caused it and nothing they can
    change will fix it.
    """


def must_exist[T](row: T | None, what: str,
                  referenced_by: UUID | str | None = None) -> T:
    if row is None:
        where = f" referenced by {referenced_by}" if referenced_by else ""
        raise MissingReference(f"{what}{where} does not exist")
    return row
