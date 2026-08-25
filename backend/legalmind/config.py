"""Runtime configuration. Secrets come from the environment, never source (S-6)."""

from __future__ import annotations

import os
from pathlib import Path


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


def assist_schema() -> str:
    """The database schema holding the assist-lane tables — locked `AM-27` r1.

    `AM-27` r1: *"Assist-lane tables live in a database schema separate from the
    locked tables."* This is a **name**, not a toggle: there is no mode in which the
    assist tables share a schema with the locked ones.

    Configurable for one specific reason. The test harness builds the locked tables
    in a private per-process schema (``t_<epoch>_<random>``, the `F-4` isolation
    fix), and a hardcoded ``assist`` would put every concurrent run's assist tables
    in one shared schema — reintroducing exactly the cross-run collision `F-4`
    fixed. `conftest` therefore derives ``<run_schema>_assist`` per run. Production
    uses the default and never sets this.
    """
    return os.environ.get("LEGALMIND_ASSIST_SCHEMA", "assist")


def storage_root() -> str:
    """Local write-once document store.

    Production uses S3-compatible object storage (locked Step 39); the backend is
    injected, so which one is a deployment choice (Step 55) rather than a code
    change.
    """
    return os.environ.get("LEGALMIND_STORAGE_ROOT", "/var/lib/legalmind/documents")


def source_material_dir() -> str:
    """Where the organization's own legal source documents live (untracked).

    Locked 54.6: *"golden fixtures use synthetic or cleared contract text. Real
    counterparty contracts do not enter the repository."* Owner ruling 2026-08-19:
    the documents live INSIDE the project at ``legal-docs/`` for convenience, but
    the directory is gitignored and must never be tracked — "the repository" means
    version control, and nothing sensitive is ever committed.
    ``tests/test_source_material.py`` enforces both halves.

    Absence is normal and must never be an error: CI has no source material and the
    document-level corpus fixtures skip when it is missing. A missing directory
    means "those fixtures cannot run here", never "evaluate with less material".

    Owner ruling, 2026-08-18: the six documents named in CLAUDE.md § Source material
    are the ONLY source material for this project. Other document collections exist
    elsewhere on this machine and belong to a different project; do not read from
    them or use them to populate this directory.
    """
    return os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR",
                          str(Path(__file__).resolve().parents[2] / "legal-docs"))


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
