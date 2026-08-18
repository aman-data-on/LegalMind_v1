"""Runtime configuration. Secrets come from the environment, never source (S-6)."""

from __future__ import annotations

import os


def database_url() -> str:
    return os.environ.get(
        "LEGALMIND_DATABASE_URL",
        "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_dev",
    )


def test_database_url() -> str:
    return os.environ.get(
        "LEGALMIND_TEST_DATABASE_URL",
        "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_test",
    )


def storage_root() -> str:
    """Local write-once document store.

    Production uses S3-compatible object storage (locked Step 39); the backend is
    injected, so which one is a deployment choice (Step 55) rather than a code
    change.
    """
    return os.environ.get("LEGALMIND_STORAGE_ROOT", "/var/lib/legalmind/documents")


def environment() -> str:
    """Which of locked 55.3's three environments this process is running as.

    Not a security control on its own — every check that matters is enforced in code
    regardless — but the preflight reports against it, and 55.3's separation (real
    contracts never leave production) is stated in terms of it.
    """
    return os.environ.get("LEGALMIND_ENVIRONMENT", "development")


def broker_url() -> str | None:
    """The Celery broker — locked Step 39 (Celery + Redis) and locked 55.1.

    ``None`` means no queue is configured, and analysis then runs **inline in the
    request** instead of as a worker job. That is a development convenience and is
    not the locked deployment shape: 55.1's diagram has a worker behind a queue, so
    the production preflight fails a deployment configured this way rather than
    letting an inline fallback pass silently.
    """
    return os.environ.get("LEGALMIND_BROKER_URL") or None


def queue_enabled() -> bool:
    return broker_url() is not None


def analysis_time_limit_seconds() -> int:
    """Hard ceiling on one analysis job.

    An operational guard, not a specified value: nothing locked fixes a duration.
    It exists because a pathological document must not hold a worker slot for ever,
    and because a job killed by the time limit rolls its transaction back — so the
    Review returns to its pre-analysis state rather than being left half-analysed.
    """
    return int(os.environ.get("LEGALMIND_ANALYSIS_TIME_LIMIT", 30 * 60))


def max_upload_bytes() -> int:
    """Upload size ceiling — locked 34.16 (untrusted input) and Step 39's
    upload-validation checklist item. A deployment limit, not a specified one."""
    return int(os.environ.get("LEGALMIND_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))
