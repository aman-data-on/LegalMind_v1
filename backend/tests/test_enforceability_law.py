"""AM-242 (AB-139, 2026-10-30): every statute line beside an enforceability note is quoted
verbatim from the SUPPLIED statute, and the note never concludes (§29.1.1 item 5)."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pymupdf
import pytest

from legalmind.domain import enforceability as E

_FILES = {"Indian Contract Act, 1872": "Indian_Contract_Act_1872.pdf",
          "Digital Personal Data Protection Rules, 2025": "DPDP_Rules_2025.pdf"}
_DIR = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "/nonexistent")) \
    / "Indian_Laws_and_Acts"


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.skipif(not _DIR.is_dir(), reason="supplied statutes not present (54.6)")
def test_every_statute_line_is_the_supplied_statute_word_for_word():
    texts = {src: _flat(" ".join(p.get_text() for p in pymupdf.open(_DIR / f)))
             for src, f in _FILES.items()}
    for stem, (_, _, law) in E._NOTES.items():
        if law:
            assert _flat(law[2]) in texts[law[0]], stem


def test_a_note_carries_the_law_beside_the_constitution_and_never_a_conclusion():
    note = E.note_for("DISPUTE-WINDOW-MSA-001")
    assert note["text"] == E.COUNSEL and note["law"]["section"] == "28(b)"
    assert E.note_for("EARLY-TERM-RESTRICTION-MSA-001")["section"] == "29.1.1"
    assert E.note_for("GOVLAW-MSA-001") is None
    for stem in E._NOTES:
        assert not re.search(r"\b(?:is|are)\s+(?:not\s+)?(?:enforceable|void)\b",
                             E._NOTES[stem][1])
