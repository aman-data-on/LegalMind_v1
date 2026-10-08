"""The process-wide embedding backend, resolved from configuration — `AM-26` r1.

One place knows which model is running; everything else calls `embed_query` /
`embed_texts` and stays model-agnostic. The identity comes from `calibration.py`
(selected by measurement) and the weights from the local provisioned store
(`AM-26` r5, checksum-verified at load).

Absence is a mode, not an error: a deployment without provisioned weights — CI, or a
fresh environment — degrades to lexical-only retrieval. Locked 34.9's instinct applies:
never invent what is missing, and never fail the surrounding operation because an
optional capability is absent. The degradation is logged so it is visible, and the
refusal gate's lexical branch remains sound without vectors (measured: lexical refuses
13/13 unanswerable questions on its own).
"""

from __future__ import annotations

import functools
import logging
import threading

from legalmind.assist.retrieval import calibration
from legalmind.observability.logs import log_event

_lock = threading.Lock()
_backend = None
_backend_failed = False


def _load():
    global _backend, _backend_failed
    if _backend is not None or _backend_failed:
        return _backend
    with _lock:
        if _backend is not None or _backend_failed:
            return _backend
        try:
            from legalmind.assist.ingestion.onnx_backend import (
                OnnxEmbeddingBackend,
                model_root,
            )

            directory = (model_root()
                         / calibration.EMBEDDING_MODEL_REPO.replace("/", "__")
                         / calibration.EMBEDDING_MODEL_REVISION)
            backend = OnnxEmbeddingBackend(directory)
            if backend.dimensions != calibration.EMBEDDING_DIMENSIONS:
                # A mismatched model would write vectors the schema cannot hold and
                # queries could not compare. Refuse loudly; run lexical-only.
                raise RuntimeError(
                    f"provisioned model has {backend.dimensions} dimensions; the "
                    f"calibrated schema holds {calibration.EMBEDDING_DIMENSIONS}")
            _backend = backend
        except Exception as exc:
            _backend_failed = True
            log_event("assist.embedding.unavailable", level=logging.WARNING,
                      model=calibration.EMBEDDING_MODEL_REPO,
                      error=type(exc).__name__, operational_failure=True)
    return _backend


def available() -> bool:
    return _load() is not None


def identity() -> str | None:
    backend = _load()
    return backend.identity if backend else None


def checksum_fragment() -> str | None:
    """First 16 hex chars of the model graph's sha256, for the registry row."""
    import json

    from legalmind.assist.ingestion.onnx_backend import MANIFEST, model_root

    directory = (model_root()
                 / calibration.EMBEDDING_MODEL_REPO.replace("/", "__")
                 / calibration.EMBEDDING_MODEL_REVISION)
    manifest_path = directory / MANIFEST
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text())["model.onnx"]


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    backend = _load()
    return backend.embed(texts) if backend else None


def embed_query(query: str):
    """The callable `store.search_hybrid` expects: text -> (vector, identity) | None."""
    backend = _load()
    if backend is None:
        return None
    return _embedded(backend, query), backend.identity


@functools.lru_cache(maxsize=256)
def _embedded(backend, query: str) -> tuple[float, ...]:
    """One search embeds the same query about six times (D1 profile, 2026-10-08: 40-49
    ms a search). Keyed on the exact string and the backend — so the model identity —
    holding a query and its vector only, never corpus text. A tuple: shared, so never
    mutated."""
    return tuple(backend.embed([query])[0])


def reset_for_tests() -> None:
    """Forget the cached backend so a test can exercise both modes."""
    global _backend, _backend_failed
    _embedded.cache_clear()
    with _lock:
        _backend = None
        _backend_failed = False
