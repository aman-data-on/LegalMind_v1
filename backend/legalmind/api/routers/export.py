"""Review export — locked 49.3's ``POST /reviews/{id}/export`` row.

Formats were left NOT YET SPECIFIED by 49.12; the owner's 2026-08-31 directive
("Export Report … PDF, DOCX", with the exact content list) is the decision that
closes it — recorded in AUTO_MODE_DECISIONS.md. Email delivery was also named
and is deliberately NOT built: the locked Step 39 stack has no mail component,
and adding one is a rule-19 decision.

The file is assembled from the SAME serializations the API serves this caller —
``serialize_finding`` with the caller's ``legal_position`` flag, the report
aggregation — so an export can never disclose a field the screens omit
(LEGAL-02: omitted, not nulled, in the file exactly as on the wire).

Rate-limited per 49.10 (export generation is one of its three named surfaces),
and every export writes an audit event: a copy of legal analysis leaving the
system is at least as consequential as a document download.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from legalmind.api import ratelimit
from legalmind.api.deps import Guard, get_guard
from legalmind.api.export_render import (
    MEDIA_TYPES,
    RENDERERS,
    build_export_model,
)
from legalmind.api.reporting import report_payload, review_findings
from legalmind.api.schemas import Body
from legalmind.api.serializers import (
    serialize_contract,
    serialize_document_version,
    serialize_finding,
    serialize_review,
)
from legalmind.db import models as M
from legalmind.security import audit
from legalmind.security import permissions as P

router = APIRouter(tags=["export"])

_limiter: ratelimit.RateLimiter = ratelimit.InProcessRateLimiter()


class ReviewExportRequest(Body):
    format: Literal["pdf", "docx"]


def _safe_filename(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c in "._- ")
    return cleaned.strip() or "analysis"


@router.post("/reviews/{review_id}/export")
def export_review(review_id: UUID, body: ReviewExportRequest,
                  guard: Guard = Depends(get_guard)) -> Response:
    review = guard.review(review_id, P.EXPORT_GENERATE)

    # S-5 / 49.10 — rendering a whole Review is an expensive path, keyed per
    # user so one caller cannot exhaust the limit for everyone.
    _limiter.check(f"export:{guard.user_id}", ratelimit.EXPORT)

    contract = guard.db.get(M.Contract, review.contract_id)
    version = guard.db.get(M.DocumentVersion, review.document_version_id)
    assert contract is not None and version is not None  # FK-guaranteed

    exported_at = datetime.now(UTC).isoformat()
    blocks = build_export_model(
        contract=serialize_contract(contract),
        version=serialize_document_version(version),
        review=serialize_review(review),
        report=report_payload(guard.db, review),
        findings=[
            serialize_finding(guard.db, f,
                              legal_position=guard.sees_legal_position)
            for f in review_findings(guard.db, review.id)
        ],
        exported_at=exported_at,
    )
    content = RENDERERS[body.format](blocks)

    audit.record(
        guard.db,
        action=audit.REPORT_EXPORTED,
        entity_type="review",
        entity_id=review.id,
        actor_id=guard.user_id,
        request_id=guard.request_id,
        after={"format": body.format, "size_bytes": len(content)},
    )

    filename = _safe_filename(
        f"{contract.name}-v{version.version_number}-analysis.{body.format}")
    return Response(
        content=content,
        media_type=MEDIA_TYPES[body.format],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
