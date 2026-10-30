"""QA-039/040 (2026-10-30): a payload the provider received is an egress whatever comes
back — audited — and a provider out of credit is not asked again for every requirement.
No network: `urllib.request.urlopen` is replaced."""
from __future__ import annotations

import contextlib
import io
import urllib.error
import urllib.request

import pytest

from legalmind.assist.llm import breaker, generation
from legalmind.db import models as M
from legalmind.security import audit


def _402(monkeypatch, sent: list):
    def urlopen(request, timeout=None):
        sent.append(request)
        raise urllib.error.HTTPError(request.full_url, 402, "Payment Required", {},
                                     io.BytesIO(b"{}"))
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("LEGALMIND_GEMINI_API_KEY", "gemini-test-credential-0123456789")
    monkeypatch.setenv("LEGALMIND_ENVIRONMENT", "development")


def test_a_payload_the_provider_refused_is_still_audited(monkeypatch, db):
    sent: list = []
    _402(monkeypatch, sent)

    @contextlib.contextmanager
    def same_db():
        yield db              # the test's transaction stands in for the seam's own
    monkeypatch.setattr("legalmind.db.session.new_session", same_db)
    monkeypatch.setattr(db, "commit", db.flush)
    with pytest.raises(generation.GenerationUnavailable) as caught:
        generation.generate_raw("clause text", prompt_version="t-1",
                                environment="development", request_id="r-1")
    assert caught.value.status == 402 and len(sent) == 1
    row = db.query(M.AuditEvent).filter_by(action=audit.ASSIST_GENERATION_CALLED).one()
    assert row.after_state["outcome"] == "failed" and row.after_state["cause"] == "HTTP 402"
    assert row.after_state["payload_sha256"] and row.after_state["purpose"] == "t-1"


def test_the_review_stops_asking_a_provider_that_is_out_of_credit(monkeypatch):
    """QA-040: every requirement's clause text went out, retried once each, after a 402."""
    from legalmind.analysis import service
    sent: list = []
    _402(monkeypatch, sent)
    monkeypatch.setattr(generation, "_audit_failed_send", lambda **_: None)
    breaker.reset()
    try:
        for _ in range(5):
            with pytest.raises(generation.GenerationUnavailable):
                service.ask_review_model(None, "clause text", "t-1", None)
        assert len(sent) == 1, "one 402 pauses the model; the rest are not sent"
    finally:
        breaker.reset()
