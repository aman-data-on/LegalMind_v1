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

from legalmind.domain.document_types import DOCUMENT_TYPES

FRONTEND_FILE = (pathlib.Path(__file__).resolve().parents[2]
                 / "frontend" / "src" / "lib" / "documentTypes.ts")


def test_frontend_document_types_match_step_6_exactly():
    if not FRONTEND_FILE.exists():
        pytest.skip("frontend tree not present in this checkout")
    codes = re.findall(r'\{\s*code:\s*"([A-Z_]+)"', FRONTEND_FILE.read_text())
    assert tuple(codes) == DOCUMENT_TYPES, (
        "frontend/src/lib/documentTypes.ts drifted from locked Step 6's vocabulary")
