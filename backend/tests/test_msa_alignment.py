"""AM-395 (C4): every MSA standard that quotes our MSA quotes it verbatim.

The wording sent back on a point may be the standard's `source_quote` (AM-395 b), so a
quote that is not in MSA.pdf would put words in the client's reply that our MSA never
said. Reads the owner's MSA.pdf from `LEGALMIND_SOURCE_MATERIAL_DIR` (source material
stays outside the repo, locked 54.6); skips where it is absent. Asserts no legal
conclusion: only that the quoted words are our MSA's own, in order ("…" joins parts).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from legalmind.assist.knowledge.positions import RATIFIED_STANDARDS_DIR
from legalmind.ingestion.parsing import parse

MSA = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "/nonexistent")) / "MSA.pdf"
QUOTING = sorted(
    p for p in RATIFIED_STANDARDS_DIR.glob("*MSA*.json")
    if str(json.loads(p.read_text()).get("source_document", ""))
    .startswith("Leapswitch Master Services Agreement"))


def _flat(text: str) -> str:
    """Words only — the PDF's line breaks, quote marks and dashes aside."""
    return re.sub(r"\W+", "", text).lower()


@pytest.fixture(scope="module")
def msa_text() -> str:
    if not os.access(MSA, os.R_OK):
        pytest.skip("MSA.pdf is not readable on this host")
    read = parse(MSA.read_bytes(), "application/pdf", defer_ocr=True, ocr=False)
    return _flat(" ".join(s.content for s in read.segments))


def test_there_are_msa_quoting_standards():
    assert len(QUOTING) >= 10


@pytest.mark.parametrize("path", QUOTING, ids=lambda p: p.stem)
def test_the_quote_is_in_msa_pdf(path, msa_text):
    quote = json.loads(path.read_text())["source_quote"]
    parts = [p for p in re.split(r"\s*(?:…|\.\.\.)\s*", quote) if p.strip()]
    missing = [p[:80] for p in parts if _flat(p) not in msa_text]
    assert not missing, f"{path.stem}: not in MSA.pdf: {missing}"
