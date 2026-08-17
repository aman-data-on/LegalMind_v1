"""Error taxonomy and denial semantics — locked 43.22, 47.7, 49.5.

    401  no valid session
    403  object visible; operation permission absent
    404  outside the caller's scope — existence is NOT disclosed
    409  conflict, including a decision version collision
    422  business-rule rejection
    429  rate limit exceeded

The single most important property here is 49.5 r1: **a 404 for an out-of-scope
object and a 404 for a non-existent object are byte-identical.** Any difference is
an enumeration oracle. That is why ``NOT_FOUND_MESSAGE`` is a constant and the
raising site's own message is discarded on the way out, so ``NotVisible("review
not found")`` and ``NotVisible("evaluation not found")`` render the same bytes.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from legalmind.api.context import REQUEST_ID_HEADER, request_id_of
from legalmind.api.envelope import error
from legalmind.api.ratelimit import RateLimited
from legalmind.evaluation.service import EvidenceCardinalityViolation
from legalmind.ingestion.validation import UploadRejected
from legalmind.security.errors import (
    Forbidden,
    NotVisible,
    SecurityError,
    Unauthenticated,
)

NOT_FOUND_CODE = "NOT_FOUND"
NOT_FOUND_MESSAGE = "The requested resource was not found."


class BusinessRuleRejected(SecurityError):
    """422 — locked 43.22. A rule the caller could in principle satisfy."""

    status_code = 422
    code = "BUSINESS_RULE_REJECTED"


class Conflict(SecurityError):
    """409 — locked 43.22."""

    status_code = 409
    code = "CONFLICT"


def _json(status: int, body: dict[str, Any], request_id: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=body,
                        headers={REQUEST_ID_HEADER: request_id})


def not_found(request_id: str) -> JSONResponse:
    """The one and only 404 body (49.5 r1)."""
    return _json(404, error(code=NOT_FOUND_CODE, message=NOT_FOUND_MESSAGE,
                            request_id=request_id), request_id)


def install(app: FastAPI) -> None:
    """Register every handler. No exception may reach Starlette's default
    renderer, which would emit a body outside the locked envelope."""

    @app.exception_handler(NotVisible)
    async def _not_visible(request: Request, exc: NotVisible) -> JSONResponse:
        # The exception's own message is deliberately dropped. Callers get the
        # same bytes whether the object is absent or merely out of scope.
        return not_found(request_id_of(request))

    @app.exception_handler(Unauthenticated)
    async def _unauthenticated(request: Request,
                               exc: Unauthenticated) -> JSONResponse:
        rid = request_id_of(request)
        return _json(401, error(code="UNAUTHENTICATED",
                                message="Authentication is required.",
                                request_id=rid), rid)

    @app.exception_handler(Forbidden)
    async def _forbidden(request: Request, exc: Forbidden) -> JSONResponse:
        rid = request_id_of(request)
        # str(exc) names the missing permission. That is the caller's own
        # authority, not an internal legal position (49.5 r2), so it is safe and
        # it is what makes a 403 actionable.
        return _json(403, error(code="FORBIDDEN", message=str(exc),
                                request_id=rid), rid)

    @app.exception_handler(RateLimited)
    async def _rate_limited(request: Request, exc: RateLimited) -> JSONResponse:
        rid = request_id_of(request)
        # 49.10 — no detail about the limit's shape. No Retry-After, no
        # remaining-quota header: both describe the limit.
        return _json(429, error(code="RATE_LIMITED",
                                message="Too many requests.",
                                request_id=rid), rid)

    @app.exception_handler(SecurityError)
    async def _security(request: Request, exc: SecurityError) -> JSONResponse:
        """Covers VersionConflict (409), InvalidTransition (422),
        SecondPersonRequired (422) and anything else deriving from
        SecurityError, using the status and code the exception declares."""
        rid = request_id_of(request)
        if exc.status_code == 404:                      # pragma: no cover
            return not_found(rid)
        return _json(exc.status_code,
                     error(code=exc.code, message=str(exc), request_id=rid), rid)

    @app.exception_handler(UploadRejected)
    async def _upload_rejected(request: Request,
                               exc: UploadRejected) -> JSONResponse:
        rid = request_id_of(request)
        return _json(422, error(code="UPLOAD_REJECTED", message=str(exc),
                                request_id=rid), rid)

    @app.exception_handler(EvidenceCardinalityViolation)
    async def _evidence_cardinality(
            request: Request,
            exc: EvidenceCardinalityViolation) -> JSONResponse:  # pragma: no cover
        rid = request_id_of(request)
        return _json(422, error(code="EVIDENCE_REQUIRED", message=str(exc),
                                request_id=rid), rid)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request,
                          exc: RequestValidationError) -> JSONResponse:
        """49.5 r4 — list the offending fields, never echo the values.

        FastAPI's default body includes ``input`` and an interpolated ``msg``,
        either of which can carry submitted content. Both are dropped: only the
        field location and the error type survive.
        """
        rid = request_id_of(request)
        fields = [
            {"field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
             "code": str(err.get("type", "invalid"))}
            for err in exc.errors()
        ]
        return _json(422, error(code="VALIDATION_FAILED",
                                message="The request could not be validated.",
                                request_id=rid, fields=fields), rid)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request,
                    exc: StarletteHTTPException) -> JSONResponse:
        rid = request_id_of(request)
        if exc.status_code == 404:
            # An unknown route renders exactly like an out-of-scope object, so
            # route existence is not probeable either.
            return not_found(rid)
        return _json(exc.status_code,
                     error(code=_code_for(exc.status_code),
                           message=str(exc.detail), request_id=rid), rid)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request,
                         exc: Exception) -> JSONResponse:  # pragma: no cover
        rid = request_id_of(request)
        # Never surface the exception text: it can contain SQL, thresholds or
        # clause content (LEGAL-02, 49.5 r2). It is logged, not returned.
        return _json(500, error(code="INTERNAL_ERROR",
                                message="An internal error occurred.",
                                request_id=rid), rid)


_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "BUSINESS_RULE_REJECTED",
    429: "RATE_LIMITED",
}


def _code_for(status: int) -> str:
    return _STATUS_CODES.get(status, "ERROR")
