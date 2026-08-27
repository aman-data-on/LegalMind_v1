"""Domain A — position chunks (`AM-32` r3–r5).

What these tests pin, each to its locked rule:

  r3  chunks FK-reference the published standard version; re-chunking deletes the
      old chunks (a superseded version's text never keeps answering); a standard
      with no imported row REFUSES rather than skips.
  r4  this module never touches generation — the import boundary is asserted, the
      same discipline `AM-28` r2 applies to the guardrails.
  r5  retrieval requires assist.ask AND configuration.view, and the refusal shape
      is [] — indistinguishable from an empty corpus (`AM-25` r6/r7).

The chunk content is composed of the ratified file's own verbatim fields only —
missing fields refuse (rule 21), never invent.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text as sql_text

from legalmind import config
from legalmind.assist import positions
from legalmind.security import permissions as P
from tools.import_ratified_standards import import_standards


@pytest.fixture
def ratified_dir(tmp_path):
    """Two synthetic ratified files in the real file shape. Synthetic-by-name:
    positions here are inert test values, never a real legal position."""
    a = {
        "requirement_code": "TESTPOS-MSA-001",
        "ratified": "2026-08-27",
        "source_document": "Synthetic MSA for tests",
        "source_clause": "9.9 Widget Handling",
        "source_quote": "Widgets shall be handled with care at all times.",
        "configuration": {"document_type": "MSA", "expected_presence": "PRESENT",
                          "scope_key": "WIDGETS", "applicability": "REQUIRED"},
        "evaluator_type": "PRESENCE",
    }
    b = {**a, "requirement_code": "TESTPOS-TOS-001",
         "source_clause": "2.2 Gadget Returns",
         "source_quote": "Gadgets may be returned within thirty synthetic days.",
         "configuration": {**a["configuration"], "document_type": "TOS"}}
    for payload in (a, b):
        (tmp_path / f"{payload['requirement_code']}.json").write_text(
            json.dumps(payload))
    return tmp_path


def _import_from(db, user, directory):
    """Import the synthetic files so published version rows exist."""
    import tools.import_ratified_standards as imp
    original = imp.RATIFIED_STANDARDS_DIR
    imp.RATIFIED_STANDARDS_DIR = directory
    try:
        import_standards(db, actor_email=user.email)
    finally:
        imp.RATIFIED_STANDARDS_DIR = original


def _chunk_rows(db):
    schema = config.assist_schema()
    return db.execute(sql_text(
        f'SELECT standard_code, standard_version_id, content, ordinal '
        f'FROM "{schema}".position_chunks ORDER BY standard_code')).all()


def test_chunks_reference_the_published_version_row(db, user, ratified_dir):
    _import_from(db, user, ratified_dir)
    report = positions.chunk_ratified_standards(db, directory=ratified_dir)
    assert len(report) == 2
    rows = _chunk_rows(db)
    assert [r.standard_code for r in rows] == ["TESTPOS-MSA-001", "TESTPOS-TOS-001"]
    # Every chunk carries a real FK target (the insert would have failed
    # otherwise; assert the join to make the property visible, not implied).
    schema = config.assist_schema()
    orphans = db.execute(sql_text(f"""
        SELECT count(*) FROM "{schema}".position_chunks pc
        LEFT JOIN company_standard_versions v ON v.id = pc.standard_version_id
        WHERE v.id IS NULL""")).scalar()
    assert orphans == 0


def test_content_is_composed_of_the_files_verbatim_fields(db, user, ratified_dir):
    _import_from(db, user, ratified_dir)
    positions.chunk_ratified_standards(db, directory=ratified_dir)
    (msa, _tos) = _chunk_rows(db)
    assert "TESTPOS-MSA-001" in msa.content
    assert "9.9 Widget Handling" in msa.content
    assert "Widgets shall be handled with care at all times." in msa.content
    assert "(MSA)" in msa.content


def test_rechunking_replaces_rather_than_accumulates(db, user, ratified_dir):
    _import_from(db, user, ratified_dir)
    positions.chunk_ratified_standards(db, directory=ratified_dir)
    positions.chunk_ratified_standards(db, directory=ratified_dir)
    assert len(_chunk_rows(db)) == 2


def test_an_unimported_standard_refuses_rather_than_skips(db, ratified_dir):
    with pytest.raises(positions.PositionChunkingRefused) as exc:
        positions.chunk_ratified_standards(db, directory=ratified_dir)
    assert "no imported" in str(exc.value)


def test_a_file_missing_its_verbatim_fields_refuses(db, user, ratified_dir, tmp_path):
    broken = json.loads((ratified_dir / "TESTPOS-MSA-001.json").read_text())
    del broken["source_quote"]
    only = tmp_path / "only"
    only.mkdir()
    (only / "TESTPOS-MSA-001.json").write_text(json.dumps(broken))
    with pytest.raises(positions.PositionChunkingRefused) as exc:
        positions.chunk_ratified_standards(db, directory=only)
    assert "source_quote" in str(exc.value)


# ---------------------------------------------------------------- retrieval, r5

BOTH = frozenset({P.ASSIST_ASK, P.CONFIGURATION_VIEW})


def _indexed(db, user, ratified_dir):
    _import_from(db, user, ratified_dir)
    positions.chunk_ratified_standards(db, directory=ratified_dir)


def test_search_finds_a_position_by_its_own_words(db, user, ratified_dir):
    _indexed(db, user, ratified_dir)
    hits = positions.search_positions(db, query="widget handling care",
                                      permissions=BOTH)
    assert hits and hits[0].standard_code == "TESTPOS-MSA-001"
    assert hits[0].source_clause == "9.9 Widget Handling"
    assert hits[0].score > 0


def test_without_configuration_view_the_result_is_an_empty_corpus(db, user,
                                                                  ratified_dir):
    _indexed(db, user, ratified_dir)
    for perms in (frozenset({P.ASSIST_ASK}),
                  frozenset({P.CONFIGURATION_VIEW}),
                  frozenset()):
        assert positions.search_positions(db, query="widget handling care",
                                          permissions=perms) == []


def test_the_refusal_shape_is_byte_identical_to_a_genuine_miss(db, user,
                                                               ratified_dir):
    """`AM-25` r6/r7: an authorization exclusion and an empty corpus are the
    same shape — []."""
    _indexed(db, user, ratified_dir)
    denied = positions.search_positions(db, query="widget handling care",
                                        permissions=frozenset({P.ASSIST_ASK}))
    miss = positions.search_positions(db, query="zebra xylophone quantum",
                                      permissions=BOTH)
    assert denied == miss == []


def test_positions_module_never_imports_generation():
    """`AM-32` r4 / `AM-30` t3: Domain A is extractive-only. The module that
    produces position content must be incapable of egressing it — the same
    import-boundary discipline `AM-28` r2 applies to the guardrails."""
    import ast
    from pathlib import Path

    import legalmind.assist.positions as mod
    tree = ast.parse(Path(mod.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    forbidden = {name for name in imported
                 if "generation" in name or "urllib" in name}
    assert not forbidden, f"positions.py imports egress-capable code: {forbidden}"
