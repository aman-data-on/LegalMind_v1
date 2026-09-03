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


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Re-dispatch OCR jobs a previous process left unfinished (2026-09-03).

    Deferred OCR runs as a daemon thread, which dies with its process — so a
    restart or deploy mid-OCR would otherwise strand the version in PROCESSING
    forever. The database is the ledger; this replays it. In a thread so a slow
    or briefly-absent database cannot block the API from binding;
    `reconcile_interrupted_ocr` itself never raises. Runs when a SERVER starts
    (uvicorn drives the lifespan); a bare TestClient does not, which keeps the
    test harness quiet.
    """
    import threading

    from legalmind.worker.dispatch import reconcile_interrupted_ocr

    threading.Thread(target=reconcile_interrupted_ocr,
                     name="legalmind-ocr-reconcile", daemon=True).start()
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
