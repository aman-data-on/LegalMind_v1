"""Request context — correlation identifiers (49.9) and CSRF (S-3).

Locked 49.9 requires that every request carries or is assigned an
``X-Request-Id`` which is echoed on every response, recorded in the metadata of
every audit event the request produces, and propagated into background jobs. It
is the anchor Step 53 builds observability on, so it is established in middleware
before any route runs and is available even to error handlers.
"""

from __future__ import annotations

import hmac
import re
import secrets
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

REQUEST_ID_HEADER = "X-Request-Id"
CSRF_HEADER = "X-CSRF-Token"
SESSION_COOKIE = "legalmind_session"
CSRF_COOKIE = "legalmind_csrf"

# An inbound request id is untrusted input that ends up in audit metadata and in
# log lines. Constrain it rather than trust it: anything else is replaced.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def request_id_of(request: Request) -> str:
    """Never raises — error handlers depend on this being available."""
    return getattr(request.state, "request_id", "") or "-"


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns the correlation id and echoes it on every response (49.9)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        rid = incoming if incoming and _SAFE_REQUEST_ID.match(incoming) \
            else uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie check on every state-changing request (S-3).

    The session lives in an ``HttpOnly`` cookie, which a cross-site form post
    would send automatically; the CSRF cookie is readable by our own script and
    must be echoed in a header, which a cross-origin caller cannot do. Requests
    carrying no session cookie are exempt — there is nothing to ride on, and the
    login endpoint has to be reachable before a session exists.
    """

    def __init__(self, app, exempt_paths: frozenset[str] = frozenset()):
        super().__init__(app)
        self.exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next) -> Response:
        if (request.method in _UNSAFE_METHODS
                and request.url.path not in self.exempt_paths
                and request.cookies.get(SESSION_COOKIE)):
            cookie = request.cookies.get(CSRF_COOKIE)
            header = request.headers.get(CSRF_HEADER)
            if not cookie or not header or not hmac.compare_digest(cookie, header):
                rid = request_id_of(request)
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "CSRF_TOKEN_INVALID",
                                       "message": "A valid CSRF token is required.",
                                       "request_id": rid}},
                    headers={REQUEST_ID_HEADER: rid},
                )
        return await call_next(request)
