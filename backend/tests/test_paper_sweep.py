"""UX Batch 1 slice A: real papers read through `parse()` and `_units` — a repeated
clause number is named only by that clause's own words, and no two clauses with one
number read the same. Runs on the owner's files when present (source material stays
outside the repo, locked 54.6); skips otherwise. Asserts no legal conclusion."""

from __future__ import annotations

import os
import uuid
from collections import Counter
from pathlib import Path

import pytest

from legalmind.analysis.negotiation import _ZERO_WIDTH, _num, _units, clause_label
from legalmind.ingestion.parsing import parse
from legalmind.mapping.engine import Clause

#: the owner's test papers: only from the environment, never a host path (CI cannot read one)
DRIVE = Path(os.environ.get("LEGALMIND_TEST_FILES_DIR", "/nonexistent"))
DOCS = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "/nonexistent"))
FILES = [DRIVE / n for n in ("client-A.docx", "client-B.docx", "client-C-markup.docx",
                             "client-D.pdf")] + \
        [DOCS / n for n in ("MSA.pdf", "MSA-GRP-2026-07-30.pdf", "MSA-Feb.pdf", "NDA.pdf",
                            "SLA-leapswitch.pdf", "TOS-leapswitch.pdf",
                            "SLA-cloudpe.pdf", "TOS-cloudpe.pdf")]
MIME = {".pdf": "application/pdf", ".md": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _words(text: str) -> list[str]:
    return text.translate(_ZERO_WIDTH).replace("**", "").split()


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_a_repeated_number_is_named_by_its_own_words_only(path):
    if not os.access(path, os.R_OK):                     # absent, or a folder we cannot read
        pytest.skip(f"{path.name} is not readable on this host")
    read = parse(path.read_bytes(), MIME[path.suffix], defer_ocr=True, ocr=False)
    units = _units([Clause(uuid.uuid4(), s.content, s.section_number, s.section_title,
                           s.page_number, bool(s.metadata.get("heading")))
                    for s in read.segments])
    numbers = Counter(_num(u["number"]) for u in units if u["number"])
    # slice C: a repeated number is never left unnamed (a unit with words of its own),
    # and no two numbered units read the same label
    unnamed = [u["number"] for u in units if u["number"] and numbers[_num(u["number"])] > 1
               and not u["name"] and _words(u["text"].removeprefix(u["number"]))]
    assert unnamed == []
    labels = Counter(clause_label(u) for u in units if u["number"])
    assert [k for k, n in labels.items() if n > 1] == []
    said: dict[tuple[str, str | None], int] = {}
    for u in units:
        if not u["name"]:
            continue
        own = u["name"] == (u["heading"] or "").strip() or \
            " ".join(_words(u["name"].rstrip("…"))) in " ".join(_words(u["text"]))
        assert own, (u["number"], u["name"])
        said[(u["number"], u["name"])] = said.get((u["number"], u["name"]), 0) + 1
    assert [k for k, n in said.items() if n > 1] == []
