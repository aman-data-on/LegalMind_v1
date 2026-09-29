"""`S3Storage` is behaviourally identical to `LocalFilesystemStorage` (Step 39),
and `get_storage()` selects by configuration and never falls back silently.

`moto` is not installed, so the S3 client is a tiny in-memory fake exposing only
the four boto3 calls the backend makes."""

from __future__ import annotations

import re

import pytest

from legalmind.api import storage as api_storage
from legalmind.ingestion.storage import LocalFilesystemStorage, S3Storage, fingerprint

KEY = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{64}-[0-9a-f]{8}(\.pdf|\.docx|\.md|\.txt)?$")


class _ClientError(Exception):
    pass


class _FakeS3:
    class exceptions:
        ClientError = _ClientError

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket, Key, Body, **_):
        self.objects[(Bucket, Key)] = bytes(Body)

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise _ClientError("NoSuchKey")
        return {"Body": __import__("io").BytesIO(self.objects[(Bucket, Key)])}

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise _ClientError("404")
        return {}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def _s3(monkeypatch):
    # The fake is injected, so boto3 — the optional `s3` extra, absent in CI — is
    # never imported by these tests.
    return S3Storage("bucket", client=_FakeS3())


@pytest.fixture(params=["local", "s3"])
def storage(request, tmp_path, monkeypatch):
    if request.param == "local":
        return LocalFilesystemStorage(tmp_path / "objects")
    return _s3(monkeypatch)


def test_round_trip_and_content_addressed_key(storage):
    data = b"%PDF-1.7 a"
    key = storage.put(data, suggested_name="msa.PDF")
    assert KEY.match(key) and key.startswith(f"{fingerprint(data)[:2]}/{fingerprint(data)}")
    assert key.endswith(".pdf")                       # allow-listed suffix, lowercased
    assert storage.get(key) == data
    assert storage.exists(key)


def test_suffix_allow_list(storage):
    key = storage.put(b"x", suggested_name="evil.exe")
    assert KEY.match(key) and "." not in key            # unlisted extension dropped


def test_write_once_and_discard(storage):
    assert not hasattr(storage, "update") and not hasattr(storage, "delete")
    data = b"same"
    k1, k2 = storage.put(data, suggested_name="a.pdf"), storage.put(data, suggested_name="a.pdf")
    assert k1 != k2 and storage.get(k1) == storage.get(k2) == data
    assert storage.discard(k1) is True
    assert storage.discard(k1) is False
    assert not storage.exists(k1) and storage.exists(k2)


# ───────────────────────────────────────────── get_storage() selects by config
@pytest.fixture
def fresh(monkeypatch, tmp_path):
    api_storage.set_storage(None)
    monkeypatch.setenv("LEGALMIND_STORAGE_ROOT", str(tmp_path))
    yield
    api_storage.set_storage(None)


def test_local_is_the_default(fresh, monkeypatch):
    monkeypatch.delenv("LEGALMIND_STORAGE_BACKEND", raising=False)
    assert isinstance(api_storage.get_storage(), LocalFilesystemStorage)


def test_s3_when_configured(fresh, monkeypatch):
    monkeypatch.setenv("LEGALMIND_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("LEGALMIND_S3_BUCKET", "docs")
    monkeypatch.setattr(api_storage, "S3Storage",
                        lambda bucket, **k: S3Storage(bucket, client=_FakeS3()))
    backend = api_storage.get_storage()
    assert isinstance(backend, S3Storage) and backend.bucket == "docs"
    assert api_storage.get_storage() is backend                # cached


@pytest.mark.parametrize("value, expected", [("s3", "LEGALMIND_S3_BUCKET"), ("nfs", "expected")])
def test_misconfiguration_fails_loudly_never_falls_back(fresh, monkeypatch, value, expected):
    monkeypatch.setenv("LEGALMIND_STORAGE_BACKEND", value)
    monkeypatch.delenv("LEGALMIND_S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match=expected):
        api_storage.get_storage()
