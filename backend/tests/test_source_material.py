"""Source material presence — locked 54.6, owner ruling 2026-08-18.

The organization's own legal documents live OUTSIDE the repository at an agreed
path. These tests assert the *contract with that path*, not the documents: the code
must locate it, tolerate its absence, and never fall back to evaluating with less
material.

Absence is the normal case in CI and must stay green.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from legalmind import config

# The six documents supplied on 2026-08-18, by the filenames the README fixes so a
# fixture can cite one without embedding its content.
EXPECTED_DOCUMENTS = (
    "MSA.pdf",
    "TOS-leapswitch.pdf",
    "TOS-cloudpe.pdf",
    "SLA-leapswitch.pdf",
    "SLA-cloudpe.pdf",
    "NDA.pdf",
)


def _source_dir() -> Path:
    return Path(config.source_material_dir())


def test_the_source_material_path_never_enters_version_control():
    """54.6, re-interpreted by owner ruling 2026-08-19: the documents live INSIDE
    the project at ``legal-docs/`` for convenience, but "the repository" means
    version control — so the directory must be gitignored and nothing under it
    may ever be tracked. Two independent checks, because either alone can rot:
    the ignore rule could be deleted, or a file force-added past it.
    """
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    source = _source_dir().resolve()
    if not source.is_relative_to(repo_root):
        return          # outside the tree entirely — trivially untracked

    rel = source.relative_to(repo_root)
    gitignore = (repo_root / ".gitignore").read_text()
    assert f"{rel.as_posix()}/" in gitignore or rel.as_posix() in gitignore, (
        f"{rel} is inside the working tree but not gitignored; a plain "
        "`git add -A` could commit the executed NDA (locked 54.6)")

    tracked = subprocess.run(
        ["git", "ls-files", str(rel)], cwd=repo_root,
        capture_output=True, text=True)
    if tracked.returncode == 0:          # git available
        assert tracked.stdout.strip() == "", (
            f"files under {rel} are TRACKED by git — 54.6 violated: "
            f"{tracked.stdout.splitlines()[:5]}")


def test_absent_source_material_is_not_an_error():
    """CI has no source material. Absence must degrade to "cannot run here"."""
    assert isinstance(config.source_material_dir(), str)
    # Resolving the path must never require it to exist.
    _source_dir()


@pytest.mark.parametrize("filename", EXPECTED_DOCUMENTS)
def test_document_is_present_or_the_case_is_skipped(filename):
    """Reports which documents are available, without ever failing for absence.

    This is the signal that tells a reader whether the seven document-level Step 45E
    cases can be authored yet. It is deliberately a skip and not an xfail: a missing
    document is an unmet precondition, not an expected failure.
    """
    path = _source_dir() / filename
    if not path.exists():
        pytest.skip(f"{filename} not supplied yet at {_source_dir()}")
    assert path.stat().st_size > 0, f"{filename} is present but empty"


def test_no_source_document_has_been_copied_into_the_repository():
    """The prohibition that matters most, checked mechanically.

    Rule: no file named like one of the six may exist anywhere in the repository.
    Catches the easy mistake of copying a PDF in "just for the test run".
    """
    repo_root = Path(__file__).resolve().parents[2]
    offenders = [
        p for name in EXPECTED_DOCUMENTS
        for p in repo_root.rglob(name)
        if ".git" not in p.parts and "legal-docs" not in p.parts
    ]
    assert not offenders, (
        "source documents copied into the repository: "
        f"{[str(p) for p in offenders]} — locked 54.6 forbids it")


# Archive extensions. A container walks the blocked document types straight past
# an extension rule — on 2026-08-18 a .zip of seven statute PDFs sat in the
# repository root and neither .gitignore nor CI job 8 objected. Both were fixed;
# this test is the local half, so the gap cannot reopen silently.
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tgz", ".gz", ".7z", ".rar")


def test_no_archive_sits_in_the_repository():
    """54.6 blocks contract file types; an archive of them must be blocked too.

    Checking the working tree rather than the diff, because the failure mode is a
    file dropped in and forgotten — which is exactly how it happened.
    """
    repo_root = Path(__file__).resolve().parents[2]
    offenders = [
        p for p in repo_root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in ARCHIVE_SUFFIXES
        and ".git" not in p.parts
        and "node_modules" not in p.parts
        and ".venv" not in p.parts
        and "build" not in p.parts
        # the sanctioned, gitignored document home (owner ruling 2026-08-19);
        # its own test above proves it can never be committed
        and "legal-docs" not in p.parts
    ]
    assert not offenders, (
        "archive(s) in the repository — an archive can carry the document types "
        f"54.6 forbids: {[str(p.relative_to(repo_root)) for p in offenders]}")
