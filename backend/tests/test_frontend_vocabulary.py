"""The frontend's presentation copy of a locked vocabulary must equal the source.

Locked Step 6's Document Types live in `legalmind.domain.document_types` and are
validated there. The new UI's intake screen offers them from
`frontend/src/lib/documentTypes.ts` — a copy, because the frontend must not reach
the backend's source at build time (52.1). A copy drifts silently unless something
compares it; this does. Skipped only where the frontend tree is genuinely absent
(a backend-only checkout), never to make a mismatch pass.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from legalmind.domain.client_profile import CLIENT_STATUSES, VERSION_ROLES
from legalmind.domain.document_types import DOCUMENT_SOURCES, DOCUMENT_TYPES

FRONTEND_FILE = (pathlib.Path(__file__).resolve().parents[2]
                 / "frontend" / "src" / "lib" / "documentTypes.ts")


def test_frontend_document_types_match_step_6_exactly():
    if not FRONTEND_FILE.exists():
        pytest.skip("frontend tree not present in this checkout")
    codes = re.findall(r'\{\s*code:\s*"([A-Z_]+)"', FRONTEND_FILE.read_text())
    assert tuple(codes) == DOCUMENT_TYPES, (
        "frontend/src/lib/documentTypes.ts drifted from locked Step 6's vocabulary")


def test_frontend_document_sources_match_step_6_exactly():
    """Step 6's second axis (2026-09-06). Keyed `value:` in the frontend so the
    TYPE regex above cannot count these — and so this one cannot count those."""
    if not FRONTEND_FILE.exists():
        pytest.skip("frontend tree not present in this checkout")
    values = re.findall(r'\{\s*value:\s*"([A-Z_]+)"', FRONTEND_FILE.read_text())
    assert tuple(values) == DOCUMENT_SOURCES, (
        "frontend/src/lib/documentTypes.ts drifted from Step 6's source vocabulary")


def test_frontend_version_roles_match_the_backend_exactly():
    """The Client Profiles axis (2026-09-10). Keyed `role:` in the frontend so
    neither the TYPE regex nor the SOURCE regex above can count these — and so
    this one cannot count those. Three keys, three regexes, no overlap."""
    if not FRONTEND_FILE.exists():
        pytest.skip("frontend tree not present in this checkout")
    roles = re.findall(r'\{\s*role:\s*"([A-Z_]+)"', FRONTEND_FILE.read_text())
    assert tuple(roles) == VERSION_ROLES, (
        "frontend/src/lib/documentTypes.ts drifted from the version-role vocabulary")


def test_frontend_client_statuses_match_the_backend_exactly():
    """Keyed `state:`, for the same non-collision reason."""
    if not FRONTEND_FILE.exists():
        pytest.skip("frontend tree not present in this checkout")
    states = re.findall(r'\{\s*state:\s*"([A-Z_]+)"', FRONTEND_FILE.read_text())
    assert tuple(states) == CLIENT_STATUSES, (
        "frontend/src/lib/documentTypes.ts drifted from the client-status vocabulary")
