"""Response envelope — locked 43.21, extended by 49.4.

Three shapes and no others:

    {"data": {...}}
    {"data": [...], "pagination": {...}}
    {"error": {"code": ..., "message": ..., "request_id": ...}}

Responses are assembled as plain dicts rather than through a Pydantic
``response_model``. That is deliberate: 49.7 r4 requires confidential fields to be
**omitted, not nulled**, and a declared response model would reintroduce them as
``null`` — which still signals that a value exists (Step 52.4). Request bodies
*are* Pydantic models, where strict validation is what matters.
"""

from __future__ import annotations

from typing import Any

MAX_PAGE_SIZE = 100          # 49.6 — clamped server-side, whatever the client asks


def data(payload: Any) -> dict[str, Any]:
    return {"data": payload}


def paginated(items: list[Any], *, page: int, page_size: int,
              total: int) -> dict[str, Any]:
    return {
        "data": items,
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


def error(*, code: str, message: str, request_id: str,
          fields: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Locked 43.21 error shape plus 49.5's ``request_id``.

    ``fields`` carries validation detail as field names and error codes only —
    49.5 r4: offending fields are listed **without echoing the values**.
    """
    body: dict[str, Any] = {"code": code, "message": message,
                            "request_id": request_id}
    if fields is not None:
        body["fields"] = fields
    return {"error": body}
