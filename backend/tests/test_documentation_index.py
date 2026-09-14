"""Every document in `docs/` is reachable from the documentation index.

`CONTRIBUTING.md` § Documentation hygiene already says it — *"When you add a
document, add it to the documentation index (docs/README.md) in the same
change"* — and `CLAUDE.md` § Working a session repeats it. Nothing enforced it,
and on 2026-09-14 eight files had drifted out of the index, the largest of them
1,895 lines. An unlinked document is one a reader cannot find and a later
session will rewrite from scratch.

The check is deliberately about REACHABILITY, not formatting: a file counts as
indexed if the index mentions its path at all, in a table row or in prose.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs"
INDEX = DOCS / "README.md"

#: The index cannot list itself, and the API snapshot's folder carries its own.
EXEMPT = {"README.md"}


def _indexed() -> str:
    return INDEX.read_text(encoding="utf-8")


def _documents() -> list[Path]:
    return sorted(p for p in DOCS.rglob("*.md")
                  if p.relative_to(DOCS).as_posix() not in EXEMPT)


def test_the_index_exists_and_is_not_empty():
    assert INDEX.is_file() and len(_indexed()) > 500


@pytest.mark.parametrize("path", _documents(), ids=lambda p: p.relative_to(DOCS).as_posix())
def test_every_document_is_reachable_from_the_index(path):
    relative = path.relative_to(DOCS).as_posix()
    index = _indexed()
    # A link may be written relative to docs/ ("02-legal-domain/X.md") or as a
    # bare filename in prose; both make the document findable.
    assert relative in index or f"({relative})" in index or path.name in index, (
        f"{relative} is not reachable from docs/README.md — add a row in the same "
        "change that added the file (CONTRIBUTING.md § Documentation hygiene)")


def test_the_index_links_nothing_that_does_not_exist():
    """The other direction: a dead link sends a reader somewhere that is not there."""
    index = _indexed()
    broken = []
    for target in re.findall(r"\]\((?!https?:|#)([^)\s]+\.md)\)", index):
        candidate = (DOCS / target).resolve()
        if not candidate.is_file():
            # Links out of docs/ (../CLAUDE.md, ../ops/README.md) resolve too.
            broken.append(target)
    assert not broken, f"docs/README.md links to missing files: {sorted(set(broken))}"
