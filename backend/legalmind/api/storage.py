"""Storage backend as an injected dependency.

Locked Step 39 specifies S3-compatible object storage; the local backend
implements the same write-once contract (34.5, 34.18) so which one is running is a
deployment decision (Step 55) and never changes a service or a route.
"""

from __future__ import annotations

from legalmind import config
from legalmind.ingestion.storage import LocalFilesystemStorage, S3Storage, StorageBackend

_backend: StorageBackend | None = None


def _build() -> StorageBackend:
    backend = config.storage_backend()
    if backend == "local":
        return LocalFilesystemStorage(config.storage_root())
    if backend == "s3":
        bucket = config.s3_bucket()
        if not bucket:
            raise RuntimeError(
                "LEGALMIND_STORAGE_BACKEND=s3 requires LEGALMIND_S3_BUCKET")
        return S3Storage(bucket, endpoint_url=config.s3_endpoint_url(),
                         region=config.s3_region())
    raise RuntimeError(f"LEGALMIND_STORAGE_BACKEND={backend!r}: expected 'local' or 's3'")


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = _build()
    return _backend


def set_storage(backend: StorageBackend | None) -> None:
    """Used by the test harness to point at a temporary root."""
    global _backend
    _backend = backend
