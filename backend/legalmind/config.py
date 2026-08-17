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


def max_upload_bytes() -> int:
    """Upload size ceiling — locked 34.16 (untrusted input) and Step 39's
    upload-validation checklist item. A deployment limit, not a specified one."""
    return int(os.environ.get("LEGALMIND_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))
