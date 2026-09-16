"""Domain A chunks must never carry an internal locator to the reader.

Measured live 2026-09-15: 34 of the 40 ratified standards append an internal locator to
`source_document` — a repo path, the `LEGALMIND_SOURCE_MATERIAL_DIR` env var, or a
reviewer's note — and `_compose_content` baked it into the chunk text, which `AskDock`
renders verbatim in a blockquote. "What is our liability cap?" was answered with
"docs/02-legal-domain/LEGAL_CONSTITUTION_L1.5.md; owner ruling 2026-09-08".

Two properties are asserted here, and they pull in opposite directions:

    NOTHING INTERNAL SURVIVES   no path separator, no filename, no env var, no
                                reviewer's note reaches the composed chunk
    NOTHING RATIFIED IS LOST    `source_quote` is byte-identical inside the chunk, and
                                every real standard still yields a NON-EMPTY name

The second is why this is not simply "strip everything after the em-dash":
`LIABILITY-MSA-001` reads "Legal Mind — Legal Constitution … L1.5 (docs/….md; …)", so an
em-dash split first truncates the document's name to "Legal Mind".
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text as sql_text

from legalmind import config
from legalmind.assist.positions import (
    RATIFIED_STANDARDS_DIR,
    _compose_content,
    public_source_name,
)

# What must never reach a reader. Checked case-insensitively against composed output.
FORBIDDEN = ("docs/", ".md", ".pdf", "legalmind_source_material_dir",
             "repository", "\\")


def _ratified() -> list[dict]:
    return [json.loads(p.read_text())
            for p in sorted(RATIFIED_STANDARDS_DIR.glob("*.json"))]


# --------------------------------------------------------------------------
# The edge matrix — every row measured against the implementation
# --------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    # --- POSIX paths, with and without an extension ---
    ("Legal Constitution, Lawyer Review Version L1.10 — "
     "docs/02-legal-domain/LEGAL_CONSTITUTION_L1.10.md",
     "Legal Constitution, Lawyer Review Version L1.10"),
    ("Leapswitch MSA v2 — /var/lib/legalmind/msa", "Leapswitch MSA v2"),
    ("~/legal-docs/msa.txt", ""),
    # --- Windows and UNC: the first draft leaked all three of these ---
    (r"Leapswitch MSA v2 — C:\Users\legal\Documents\MSA", "Leapswitch MSA v2"),
    (r"Leapswitch MSA v2 — C:\legal\MSA.docx", "Leapswitch MSA v2"),
    (r"Leapswitch MSA v2 — \\fileserver\legal\MSA", "Leapswitch MSA v2"),
    # --- environment variables, named and unknown ---
    ("Leapswitch Master Services Agreement, Version 2 (July 2025) — "
     "MSA.pdf at LEGALMIND_SOURCE_MATERIAL_DIR",
     "Leapswitch Master Services Agreement, Version 2 (July 2025)"),
    ("Leapswitch MSA v2 — MSA at LEGALMIND_DOCS_ROOT", "Leapswitch MSA v2"),
    # --- the em-dash trap: the name itself contains an em-dash ---
    ("Legal Mind — Legal Constitution, Lawyer Review Version L1.5 "
     "(docs/02-legal-domain/LEGAL_CONSTITUTION_L1.5.md; owner ruling 2026-09-08: "
     "governs company positions)",
     "Legal Mind — Legal Constitution, Lawyer Review Version L1.5"),
    # --- em-dash after the name, and no em-dash at all ---
    ("Leapswitch Networks Terms of Service (26 February 2026) — TOS-leapswitch.pdf",
     "Leapswitch Networks Terms of Service (26 February 2026)"),
    ("Leapswitch Networks Terms of Service (26 February 2026)",
     "Leapswitch Networks Terms of Service (26 February 2026)"),
    # --- the counterparty note (AM-30 t4: never egresses, never displays) ---
    ("Executed Non-Disclosure Agreement, 17 June 2026 — NDA.pdf at "
     "LEGALMIND_SOURCE_MATERIAL_DIR (counterparty deliberately not named in this "
     "repository)",
     "Executed Non-Disclosure Agreement, 17 June 2026"),
    # --- a legitimate parenthetical is NOT collateral damage ---
    ("Leapswitch MSA, Version 2 (July 2025)", "Leapswitch MSA, Version 2 (July 2025)"),
    ("MSA (v2 (July 2025)) — MSA.pdf", "MSA (v2 (July 2025))"),
    # --- empty ---
    ("", ""),
])
def test_the_public_name_keeps_the_paper_and_drops_the_locator(raw, expected):
    assert public_source_name(raw) == expected


@pytest.mark.parametrize("value", [None, 7, 3.5, {"a": 1}, ["x"], True])
def test_malformed_metadata_returns_empty_rather_than_raising(value):
    """A belt for the brace in `chunk_ratified_standards`: whatever a future file
    carries, this never raises out of the chunker with a TypeError."""
    assert public_source_name(value) == ""


# --------------------------------------------------------------------------
# The real corpus — both properties, over every ratified standard
# --------------------------------------------------------------------------
def test_no_ratified_standard_leaks_an_internal_locator_to_the_reader():
    leaked: list[tuple[str, str]] = []
    for payload in _ratified():
        content = _compose_content(payload).lower()
        for token in FORBIDDEN:
            if token in content:
                leaked.append((payload["requirement_code"], token))
    assert leaked == [], f"internal locator reached the composed chunk: {leaked}"


def test_every_ratified_standard_still_names_its_source_document():
    """The inverse failure: over-aggressive stripping that erases the paper's name.
    An empty citation is a different defect from a leaking one, not a fix for it."""
    anonymous = [p["requirement_code"] for p in _ratified()
                 if not public_source_name(p["source_document"]).strip()]
    assert anonymous == [], f"source document name erased for: {anonymous}"


def test_the_ratified_quote_survives_byte_identical():
    """`AM-32` r4: Domain A output is the ratified text quoted verbatim. The sanitizer
    touches `source_document` only — it must never truncate or reshape legal text."""
    for payload in _ratified():
        assert payload["source_quote"] in _compose_content(payload), \
            f"{payload['requirement_code']}: source_quote is not verbatim in the chunk"


def test_the_sanitised_name_is_what_gets_indexed():
    """The chunk text IS the lexical index (`content_tsv` is generated from it), so a
    leaked path also inflated the two-lexeme floor with `docs`, `pdf` and `md`.
    Fixing the disclosure fixes the retrieval noise in the same edit."""
    for payload in _ratified():
        content = _compose_content(payload)
        assert public_source_name(payload["source_document"]) in content
        assert payload["source_document"] not in content or \
            payload["source_document"] == public_source_name(payload["source_document"])


# --------------------------------------------------------------------------
# The DB round trip — the sanitizer is a WRITE-TIME fix, so the thing that
# actually matters is what lands in position_chunks and what comes back out
# --------------------------------------------------------------------------
def test_the_real_corpus_chunks_into_the_database_carrying_no_locator(db, user):
    """Chunk the REAL 40 ratified standards and read the rows back.

    `_compose_content` is unit-tested above, but the defect shipped through
    persistence: the leaked string lived in `position_chunks.content` and was rendered
    from there. A fix proven only on the composer would still leave that untested, and
    re-chunking is the step that actually removes the stale rows — so this exercises
    chunk -> store -> read and asserts on what a reader would receive.
    """
    import tools.import_ratified_standards as imp
    from legalmind.assist.positions import (
        RATIFIED_STANDARDS_DIR,
        chunk_ratified_standards,
    )
    from tools.import_ratified_standards import import_standards

    original = imp.RATIFIED_STANDARDS_DIR
    imp.RATIFIED_STANDARDS_DIR = RATIFIED_STANDARDS_DIR
    try:
        import_standards(db, actor_email=user.email)
    finally:
        imp.RATIFIED_STANDARDS_DIR = original
    chunk_ratified_standards(db)

    rows = db.execute(sql_text(
        f'SELECT standard_code, content FROM "{config.assist_schema()}".position_chunks'
    )).all()
    assert len(rows) >= 40, f"expected the whole corpus, chunked {len(rows)}"

    leaked = [(code, tok) for code, content in rows
              for tok in FORBIDDEN if tok in content.lower()]
    assert leaked == [], f"internal locator persisted into position_chunks: {leaked[:5]}"

    # And the counterparty note, which `AM-30` t4 would forbid egressing under AM-67.
    assert not [c for c, content in rows if "not named in" in content.lower()]


def test_the_leaked_tokens_are_no_longer_searchable(db, user):
    """The chunk text IS the lexical index (`content_tsv` is generated from it), so the
    leak also inflated the two-shared-lexeme floor: `docs`, `pdf` and `md` were matchable
    words. A question about repositories should now reach no company position at all."""
    import tools.import_ratified_standards as imp
    from legalmind.assist.positions import (
        RATIFIED_STANDARDS_DIR,
        chunk_ratified_standards,
        search_positions,
    )
    from legalmind.security import permissions as P
    from tools.import_ratified_standards import import_standards

    original = imp.RATIFIED_STANDARDS_DIR
    imp.RATIFIED_STANDARDS_DIR = RATIFIED_STANDARDS_DIR
    try:
        import_standards(db, actor_email=user.email)
    finally:
        imp.RATIFIED_STANDARDS_DIR = original
    chunk_ratified_standards(db)

    perms = frozenset({P.ASSIST_ASK, P.CONFIGURATION_VIEW})
    # ONLY the removed tokens. An earlier draft of this test used "docs legal
    # constitution md" and failed — correctly: "legal" and "constitution" are part of
    # the document's real public name ("Legal Constitution, Lawyer Review Version
    # L1.10") and MUST stay searchable. The claim is narrow — the internal locator is
    # gone from the index — not that the source document became invisible.
    for query in ("docs md pdf",
                  "legalmind_source_material_dir",
                  "repository docs md"):
        hits = search_positions(db, query=query, permissions=perms, limit=5,
                                embed_query=lambda _q: None)
        assert hits == [], f"{query!r} still retrieves a position: {[h.standard_code for h in hits]}"
