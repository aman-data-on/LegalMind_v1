"""Off-server backup retention — the one code path that can destroy a backup.

`ops/production/s3_object.py prune` deletes objects from the off-server bucket.
Everything else in that file either reads or adds; this is the only thing that
removes, so it is the only thing tested here.

The property that matters is not "old things are deleted" — it is **"a broken
clock or a mistyped prefix must not empty the archive."** A wrong system time or
a prefix that matches nothing the way you expected makes every object look
expired at once, and that is far more likely than an entire archive genuinely
ageing out on the same night.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "ops" / "production" / "s3_object.py"
_spec = importlib.util.spec_from_file_location("s3_object", _SRC)
s3_object = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s3_object)

NOW = dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.UTC)


def obj(key: str, days_old: int) -> dict:
    return {"Key": key, "LastModified": NOW - dt.timedelta(days=days_old)}


def test_only_objects_past_the_window_are_selected():
    objects = [obj("a", 1), obj("b", 89), obj("c", 91), obj("d", 400)]
    stale, problem = s3_object.stale_keys(objects, 90, now=NOW)
    assert problem is None
    assert stale == ["c", "d"]


def test_the_boundary_is_not_off_by_a_day():
    """Exactly 90 days old is inside a 90-day window."""
    stale, _ = s3_object.stale_keys([obj("edge", 90), obj("fresh", 1)], 90, now=NOW)
    assert stale == []


def test_it_refuses_to_delete_every_object():
    """A clock skew that ages the whole bucket must delete nothing at all."""
    objects = [obj("a", 500), obj("b", 600), obj("c", 700)]
    stale, problem = s3_object.stale_keys(objects, 90, now=NOW)
    assert stale == []
    assert problem is not None
    assert "all 3 object(s)" in problem


def test_an_empty_bucket_is_not_a_refusal():
    """Nothing to prune is a normal first run, not an error."""
    stale, problem = s3_object.stale_keys([], 90, now=NOW)
    assert stale == []
    assert problem is None


def test_one_survivor_is_enough_to_proceed():
    objects = [obj("old", 500), obj("keep", 1)]
    stale, problem = s3_object.stale_keys(objects, 90, now=NOW)
    assert problem is None
    assert stale == ["old"]


@pytest.mark.parametrize("name", ["LEGALMIND_S3_ACCESS_KEY_ID",
                                  "LEGALMIND_S3_SECRET_ACCESS_KEY"])
def test_secret_names_are_required_but_never_defaulted(name):
    """No credential may have a fallback value — a default key is a silent
    misconfiguration that reaches the wrong bucket."""
    assert name in s3_object.REQUIRED
    assert f'"{name}"' not in _SRC.read_text().split("REQUIRED = (")[0]
