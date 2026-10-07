"""The local models are loaded at startup, not on the first reader's question.

`embedding_runtime` loads lazily, so before this the first ask of a process paid the
checksum verification and the ONNX session build inside its own retrieval stage. The
warm-up moves that to boot. Two things are worth pinning, and they are the two that
would actually break: it must run off the request path, and a deployment with NO
provisioned weights must still start (`AM-26` r5 — absence is a mode, not an error).
"""
from __future__ import annotations

from unittest.mock import patch

from legalmind.api import app as app_module


def test_the_warm_up_loads_the_model_once_and_reports_it():
    calls: list[str] = []

    with patch("legalmind.assist.ingestion.embedding_runtime.embed_query",
               side_effect=lambda q: (calls.append(q), ([0.1], "stub/model"))[1]), \
         patch("legalmind.assist.ingestion.embedding_runtime.identity", return_value="stub/model"):
        app_module._warm_models()

    assert calls, "the warm-up never asked the model for an embedding"


def test_a_deployment_with_no_provisioned_weights_still_starts():
    # `embed_query` returns None when nothing is provisioned. The warm-up must treat
    # that as a mode and return quietly — never raise into the lifespan, which would
    # stop the API binding at all.
    with patch("legalmind.assist.ingestion.embedding_runtime.embed_query", return_value=None), \
         patch("legalmind.assist.ingestion.embedding_runtime.identity", return_value=None):
        app_module._warm_models()  # must not raise


def test_a_model_that_raises_does_not_take_the_api_down():
    with patch("legalmind.assist.ingestion.embedding_runtime.embed_query",
               side_effect=RuntimeError("corrupt weights")):
        app_module._warm_models()  # must not raise


def test_the_lifespan_starts_the_warm_up_off_the_request_path():
    """It is a daemon THREAD: a model slow to verify must not delay the port binding,
    and must not die holding the process open at shutdown."""
    import inspect

    source = inspect.getsource(app_module._lifespan)
    assert "_warm_models" in source
    assert "daemon=True" in source


def test_the_reranker_and_the_verifier_are_warmed_too():
    """The first Ask after a restart paid 255.5–266.2 ms for the reranker and
    1,895.6–1,955.4 ms for the NLI verifier (latency diagnosis, 2026-10-07)."""
    warmed: list[str] = []
    with patch("legalmind.assist.ingestion.embedding_runtime.embed_query", return_value=None), \
         patch("legalmind.assist.retrieval.rerank.scores",
               side_effect=lambda q, t: warmed.append("rerank")), \
         patch("legalmind.assist.verification.verify.entailment",
               side_effect=lambda p: warmed.append("verify")):
        app_module._warm_models()
    assert warmed == ["rerank", "verify"]
