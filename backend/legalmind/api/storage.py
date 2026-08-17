"""Storage backend as an injected dependency.

Locked Step 39 specifies S3-compatible object storage; the local backend
implements the same write-once contract (34.5, 34.18) so which one is running is a
deployment decision (Step 55) and never changes a service or a route.
"""

from __future__ import annotations

from legalmind.config import storage_root
from legalmind.ingestion.storage import LocalFilesystemStorage, StorageBackend

_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = LocalFilesystemStorage(storage_root())
    return _backend


def set_storage(backend: StorageBackend | None) -> None:
    """Used by the test harness to point at a temporary root."""
    global _backend
    _backend = backend
