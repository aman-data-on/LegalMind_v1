"""The cross-encoder reranker — REORDERS retrieved evidence, decides nothing.

`AM-25`'s permitted list names "hybrid retrieval with reranking" and `AM-26`'s stack
table names a "Reranking model | local, self-hosted, open-weight, cross-encoder", so no
amendment is needed for this. What `AM-26` does impose is r2 (smallest candidate upward,
stop at the first that passes), r3 (measured on real supplied material including
unanswerable questions), r4 (pinned, recorded) and r5 (obtained once, checksummed, never
fetched at runtime) — all satisfied the same way the embedding model satisfies them, by
`tools/provision_model.py` and `onnx_backend.OnnxCrossEncoderBackend`.

THE BOUNDARY, which is the whole design:

    The reranker REORDERS a list the gate has already admitted. It never opens a shut
    gate, never closes an open one, never adds or removes a candidate, and its score
    never reaches a reader. `calibration.gate_is_open` keeps its calibrated inputs and
    its calibrated decision, untouched.

That boundary is not caution, it is what the measurement of 2026-09-17 requires. The
bakeoff scored each candidate's TOP rerank score on the answerable questions the gate
wrongly refuses against the 13 questions with no answer at all, and the two distributions
overlap almost entirely — for `ms-marco-MiniLM-L-6-v2` the *unanswerable* median (-2.30)
sits ABOVE the false-refusal median (-3.12). So no floor on this score can reopen a gate
without admitting the unanswerable, which is the same wall the 35-point threshold sweep,
the IDF-weighted overlap feature and the embedding-model swap each hit. Reordering is
what the evidence supports; gate-opening is not, and is not implemented.

Local and self-hosted: no egress (`AM-30` t1 untouched — generation remains the one
permitted call). Imports no network client, as `tests/test_import_boundaries.py` requires
of everything under `legalmind/`.
"""

from __future__ import annotations

import logging
import threading

from legalmind import config
from legalmind.assist.onnx_backend import OnnxCrossEncoderBackend, model_root
from legalmind.observability.logs import log_event

_lock = threading.Lock()
_backend: OnnxCrossEncoderBackend | None = None
_failed = False


def _load() -> OnnxCrossEncoderBackend | None:
    """The provisioned reranker, or None — loaded once per process, failure sticky.

    Mirrors `embedding_runtime._load`: a missing or corrupt model is an operational
    condition that degrades the lane rather than failing the request, because reordering
    is an improvement to an answer the pipeline can produce without it.
    """
    global _backend, _failed
    if _backend is not None or _failed:
        return _backend
    with _lock:
        if _backend is not None or _failed:
            return _backend
        repo = config.rerank_model_repo()
        revision = config.rerank_model_revision()
        directory = model_root() / repo.replace("/", "__") / revision
        try:
            _backend = OnnxCrossEncoderBackend(directory)
        except Exception as exc:
            _failed = True
            log_event("assist.rerank.unavailable", level=logging.WARNING,
                      operational_failure=True, reason=type(exc).__name__,
                      model=f"{repo}@{revision}")
            return None
        log_event("assist.rerank.loaded", model=_backend.identity)
        return _backend


def reset_for_tests() -> None:
    global _backend, _failed
    with _lock:
        _backend, _failed = None, False


def available() -> bool:
    return config.rerank_enabled() and _load() is not None


def identity() -> str | None:
    backend = _load() if config.rerank_enabled() else None
    return backend.identity if backend else None


def reorder(query: str, hits: list, *, request_id: str | None = None) -> list:
    """The same hits, best first. Returns the SAME list object when it cannot run.

    Never changes the membership of `hits` — only their order — so the gate's decision,
    the evidence floor and the sufficiency check all see exactly what they saw before.
    """
    if not config.rerank_enabled() or len(hits) < 2:
        return hits
    backend = _load()
    if backend is None:
        return hits
    try:
        scores = backend.score(query, [h.content for h in hits])
    except Exception as exc:
        log_event("assist.rerank.failed", level=logging.WARNING,
                  operational_failure=True, reason=type(exc).__name__,
                  request_id=request_id)
        return hits
    order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
    if order == list(range(len(hits))):
        return hits
    log_event("assist.rerank.reordered", request_id=request_id, hits=str(len(hits)),
              moved_to_front=str(order[0]), level=logging.DEBUG)
    return [hits[i] for i in order]
