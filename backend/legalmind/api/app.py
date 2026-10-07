"""Application factory — locked 43.30, 43.21, 43.23, 49.1.

Locked 43.30 fixes ``/api/v1/`` from the beginning; 49.1 fixes plural kebab-case
resources, UUID identifiers, ISO-8601 UTC timestamps, and GET/POST/PATCH/DELETE
with **no PUT**.

The frontend boundary (49.11, 38.22, 38.23, 43.31) is enforced by what exists
rather than by policy: this is the only way into the domain, so the UI cannot reach
the database and cannot implement evaluation, classification, roll-up or
authorization logic even if it wanted to. The permission array from
``GET /auth/session`` drives presentation only.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from legalmind.api import errors
from legalmind.api.context import (
    CsrfMiddleware,
    RequestContextMiddleware,
    RequestLoggingMiddleware,
)
from legalmind.api.permission_map import API_PREFIX
from legalmind.api.routers import (
    admin,
    assist,
    audit,
    configuration,
    contracts,
    counterparties,
    decisions,
    documents,
    export,
    findings,
    reviews,
)
from legalmind.api.routers import auth as auth_router
from legalmind.observability import configure_logging


def _docs_enabled() -> bool:
    """Off by default.

    49.12 lists OpenAPI generation as deferred to implementation, so gating it is
    a free choice — and an unauthenticated schema document is a reconnaissance aid
    that would sit oddly beside 49.3's "no endpoint is implicitly public" and the
    404-over-403 posture of 47.7. Enabled explicitly for development.
    """
    return os.environ.get("LEGALMIND_ENABLE_DOCS", "").lower() in {"1", "true", "yes"}


def _warm_models() -> None:
    """Load and exercise the local models once, off the first request's back.

    The embedding model, the reranker and the NLI verifier all load lazily, so before
    this the FIRST question of a process paid for the SHA-256 verification of their
    weights and their ONNX session builds on the critical path — the embedding model
    measured as the slowest ask of any deploy (2026-09-17), the reranker and verifier
    255.5–266.2 and 1,895.6–1,955.4 ms (latency diagnosis, 2026-10-07). A restart is
    exactly when a reader is most likely to be waiting, so the cost is moved to a moment
    when nobody is.

    Absence stays a mode, not an error (`AM-26` r5's degradation): each returns None when
    its weights are not provisioned (or, for the reranker, it is switched off), its
    loader has already logged that, and this thread simply finds nothing to warm. It
    changes no retrieval or verification behaviour and no result — only when the loading
    happens.
    """
    import logging

    from legalmind import config
    from legalmind.assist.ingestion import embedding_runtime
    from legalmind.assist.retrieval import rerank
    from legalmind.assist.verification import verify
    from legalmind.observability.logs import log_event, timed

    for name, warm, identity in (
            ("embedding", lambda: embedding_runtime.embed_query("warm") is not None,
             embedding_runtime.identity),
            ("rerank", lambda: rerank.scores("warm", ["warm"]) is not None,
             rerank.identity),
            ("verify", lambda: verify.entailment([("warm", "warm")]) is not None,
             config.nli_model_repo)):
        try:
            # `timed` reports the duration the next deploy's first reader no longer pays.
            with timed(f"assist.{name}.warm") as stage:
                stage["warmed"] = warm()
                stage["model"] = identity()
        except Exception as exc:  # never let a warm-up take the API down with it
            log_event(f"assist.{name}.warm_failed", level=logging.WARNING,
                      error=type(exc).__name__, operational_failure=True)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Re-dispatch OCR jobs a previous process left unfinished (2026-09-03), and warm
    the local models (embedding 2026-09-17; reranker and verifier 2026-10-07).

    Deferred OCR runs as a daemon thread, which dies with its process — so a
    restart or deploy mid-OCR would otherwise strand the version in PROCESSING
    forever. The database is the ledger; this replays it. In a thread so a slow
    or briefly-absent database cannot block the API from binding;
    `reconcile_interrupted_ocr` itself never raises. Runs when a SERVER starts
    (uvicorn drives the lifespan); a bare TestClient does not, which keeps the
    test harness quiet.

    The model warm-up rides the same pattern for the same reason: a daemon thread,
    so a model that is slow to verify or absent altogether cannot delay the port
    binding or the OCR replay.
    """
    import threading

    from legalmind.worker.dispatch import reconcile_interrupted_ocr

    threading.Thread(target=reconcile_interrupted_ocr,
                     name="legalmind-ocr-reconcile", daemon=True).start()
    threading.Thread(target=_warm_models,
                     name="legalmind-model-warm", daemon=True).start()
    yield


def create_app() -> FastAPI:
    docs = _docs_enabled()
    app = FastAPI(
        lifespan=_lifespan,
        title="LegalMind API",
        version="1",
        # The generated document is a convenience, never the specification. The
        # locked documents are.
        docs_url="/api/v1/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json" if docs else None,
        # Every response goes through the locked envelope, so FastAPI's own
        # validation renderer must not get a chance to emit its default body.
        redirect_slashes=False,
    )

    configure_logging()

    # Order matters, and Starlette runs middleware in reverse registration order —
    # so the LAST registered runs first. The request id must exist before CSRF can
    # put it in an error body and before anything is logged against it.
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestContextMiddleware)

    errors.install(app)

    v1 = APIRouter(prefix=API_PREFIX)
    v1.include_router(auth_router.router)
    v1.include_router(contracts.router)
    v1.include_router(counterparties.router)
    v1.include_router(documents.router)
    v1.include_router(reviews.router)
    v1.include_router(export.router)
    v1.include_router(findings.router)
    v1.include_router(decisions.router)
    v1.include_router(configuration.router)
    v1.include_router(audit.router)
    v1.include_router(admin.router)
    v1.include_router(assist.router)
    app.include_router(v1)

    @app.get("/health", tags=["operations"])
    def health() -> dict:
        """Liveness only, and deliberately contentless.

        The one route that is unauthenticated by design (declared as such in
        ``permission_map``). It reports nothing about the database, the
        configuration or any object — a probe must not become a reconnaissance
        endpoint. Readiness and dependency checks belong to Step 53.
        """
        return {"data": {"status": "ok"}}

    return app


def registered_routes(app: FastAPI) -> Iterator[tuple[str, str]]:
    """Every (method, path) the application serves.

    Used by the permission-coverage test to hold 49.3's "no endpoint is implicitly
    public" to account. Walks the router tree rather than the OpenAPI document,
    because a route excluded from the schema is still a route.
    """
    seen: set[tuple[str, str]] = set()
    for path, operations in app.openapi().get("paths", {}).items():
        for method in operations:
            key = (method.upper(), path)
            if key not in seen:
                seen.add(key)
                yield key
    # Anything mounted outside the API routers — the docs endpoints when they are
    # enabled. Listed too, so an unauthenticated schema document cannot slip past
    # the coverage test unnoticed.
    for route in app.routes:
        if isinstance(route, APIRoute) or not hasattr(route, "path"):
            continue
        for method in (getattr(route, "methods", None) or ()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, route.path)
            if key not in seen:
                seen.add(key)
                yield key


app = create_app()
