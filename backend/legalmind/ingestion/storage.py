"""Document storage — locked Step 34.5, 34.18; Step 39 (S3-compatible).

Two locked rules govern this module:

* **34.2 / 34.5** — the original uploaded file is preserved immutably.
* **34.18** — the ingestion layer must not alter the original source document.

Storage is therefore write-once: there is deliberately no update or overwrite
operation, so no code path can modify a stored original.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4


def fingerprint(data: bytes) -> str:
    """Cryptographic fingerprint — locked 34.4 / 34.6.

    SHA-256. Used for exact-duplicate detection (34.5); indexed but NOT unique,
    because the same source file may legitimately appear in several contracts
    (locked 42.4).
    """
    return hashlib.sha256(data).hexdigest()


class StorageBackend(Protocol):
    """Write-once object storage. No update, no overwrite (34.18).

    ``discard`` is not an exception to write-once: an object is still never
    rewritten in place, and the only caller is the hard-delete branch of
    contract deletion (owner approval 2026-09-01), which runs solely for a
    contract that was never analyzed. A contract carrying a Review is
    soft-deleted instead and its bytes stay exactly where they are, because
    rule 17 requires that history remain reproducible.
    """

    def put(self, data: bytes, *, suggested_name: str) -> str: ...
    def get(self, storage_key: str) -> bytes: ...
    def exists(self, storage_key: str) -> bool: ...
    def discard(self, storage_key: str) -> bool: ...


class LocalFilesystemStorage:
    """Development/test backend.

    Production uses S3-compatible object storage (locked Step 39). This
    implements the same write-once contract so the service layer is identical
    either way; the provider itself is a deployment choice (Step 55).
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, *, suggested_name: str) -> str:
        # Content-addressed prefix + random component: a distinct key per upload
        # even for identical content, so an existing object is never overwritten.
        digest = fingerprint(data)
        key = f"{digest[:2]}/{digest}-{uuid4().hex[:8]}{_suffix(suggested_name)}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():                      # pragma: no cover - defensive
            raise FileExistsError(f"refusing to overwrite {key}")
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        path.chmod(0o440)                      # read-only once written
        return key

    def get(self, storage_key: str) -> bytes:
        return (self.root / storage_key).read_bytes()

    def exists(self, storage_key: str) -> bool:
        return (self.root / storage_key).exists()

    def discard(self, storage_key: str) -> bool:
        """Remove one object. True if it was there, False if it was not.

        Missing is not an error: the caller is deleting a contract, and a key
        already gone is the state it wanted. `put` chmods objects to 0o440, so
        the parent directory's write permission is what governs removal here.
        """
        path = self.root / storage_key
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True


def _suffix(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return suffix if suffix in {".pdf", ".docx"} else ""
