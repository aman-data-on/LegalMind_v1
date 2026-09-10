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


def test_without_a_position_permission_the_result_is_an_empty_corpus(db, user,
                                                                     ratified_dir):
    """`AM-32` r5 as amended by `AM-44`: assist.ask AND (configuration.view OR
    legal_position.view). Anything less is an empty corpus."""
    _indexed(db, user, ratified_dir)
    for perms in (frozenset({P.ASSIST_ASK}),
                  frozenset({P.CONFIGURATION_VIEW}),
                  frozenset({P.LEGAL_POSITION_VIEW}),
                  frozenset()):
        assert positions.search_positions(db, query="widget handling care",
                                          permissions=perms) == []


def test_a_department_user_with_legal_position_view_reaches_positions(db, user,
                                                                       ratified_dir):
    """AB-12 r7 grants a Department User legal_position.view so they can see WHY a
    Finding is what it is — the standard. `AM-44` lets them retrieve that same
    published standard by asking for it."""
    _indexed(db, user, ratified_dir)
    hits = positions.search_positions(
        db, query="widget handling care",
        permissions=frozenset({P.ASSIST_ASK, P.LEGAL_POSITION_VIEW}))
    assert hits and hits[0].standard_code == "TESTPOS-MSA-001"


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


# ==========================================================================
# The vector increment (2026-09-09) — `AM-32`'s `position_chunk_embeddings`, filled.
# Deterministic: planted unit vectors and an injected query embedder, so the test
# pins the MECHANISM (gate, floor, fusion, authorization) and never a model's number.
# ==========================================================================
def _plant(db, chunk_id, axis: int):
    from legalmind.assist import store
    schema = config.assist_schema()
    model_id = store.register_embedding_model(db, name="planted", version="t",
                                              dimensions=384, checksum="x")
    vec = [0.0] * 384
    vec[axis] = 1.0
    db.execute(sql_text(f"""
        INSERT INTO "{schema}".position_chunk_embeddings
            (id, position_chunk_id, embedding_model_id, embedding)
        VALUES (gen_random_uuid(), :c, :m, CAST(:v AS {store.vector_type(db)}))
    """), {"c": chunk_id, "m": model_id, "v": "[" + ",".join(map(str, vec)) + "]"})


def _axis(n):
    vec = [0.0] * 384
    vec[n] = 1.0
    return lambda _q: (vec, "planted@t")


def _ids(db):
    schema = config.assist_schema()
    return dict(db.execute(sql_text(
        f'SELECT standard_code, id FROM "{schema}".position_chunks')).all())


def test_a_paraphrase_with_no_shared_word_reaches_a_position_through_its_vector(
        db, user, ratified_dir):
    _indexed(db, user, ratified_dir)
    ids = _ids(db)
    _plant(db, ids["TESTPOS-MSA-001"], 0)
    _plant(db, ids["TESTPOS-TOS-001"], 1)
    # Not one lexeme in common with either standard: lexical retrieval is empty.
    question = "Is there a rule about treating things gently?"
    assert positions.search_positions(db, query=question, permissions=BOTH,
                                      embed_query=lambda q: None) == []
    hits = positions.search_positions(db, query=question, permissions=BOTH,
                                      embed_query=_axis(0))
    # cosine 1.0 to the MSA position opens the calibrated gate; the TOS position
    # sits at 0.0, below the evidence floor, and is never admitted as evidence.
    assert [h.standard_code for h in hits] == ["TESTPOS-MSA-001"]
    assert hits[0].score == pytest.approx(1.0)


def test_a_vector_far_from_every_position_keeps_the_gate_shut(db, user, ratified_dir):
    _indexed(db, user, ratified_dir)
    ids = _ids(db)
    _plant(db, ids["TESTPOS-MSA-001"], 0)
    _plant(db, ids["TESTPOS-TOS-001"], 1)
    assert positions.search_positions(db, query="zorbulated framblewitz",
                                      permissions=BOTH, embed_query=_axis(7)) == []


def test_the_vector_increment_respects_the_same_authorization(db, user, ratified_dir):
    _indexed(db, user, ratified_dir)
    _plant(db, _ids(db)["TESTPOS-MSA-001"], 0)
    assert positions.search_positions(db, query="treating things gently",
                                      permissions=frozenset({P.ASSIST_ASK}),
                                      embed_query=_axis(0)) == []


def test_a_lexical_hit_and_a_vector_hit_fuse_into_one_deterministic_ranking(
        db, user, ratified_dir):
    _indexed(db, user, ratified_dir)
    ids = _ids(db)
    _plant(db, ids["TESTPOS-MSA-001"], 0)
    _plant(db, ids["TESTPOS-TOS-001"], 1)
    # Lexically the GADGET standard matches ("gadgets", "returned"); the vector points
    # at the WIDGET standard. Both are evidence; the ranking is fixed and repeatable.
    a = positions.search_positions(db, query="gadgets returned", permissions=BOTH,
                                   embed_query=_axis(0))
    b = positions.search_positions(db, query="gadgets returned", permissions=BOTH,
                                   embed_query=_axis(0))
    assert {h.standard_code for h in a} == {"TESTPOS-MSA-001", "TESTPOS-TOS-001"}
    assert [h.standard_code for h in a] == [h.standard_code for h in b]


def test_chunking_embeds_every_position_when_the_model_is_available(db, user, ratified_dir):
    from legalmind.assist import embedding_runtime
    embedding_runtime.reset_for_tests()
    if not embedding_runtime.available():
        pytest.skip("embedding model not present in this environment")
    _indexed(db, user, ratified_dir)
    schema = config.assist_schema()
    chunks, vectors = db.execute(sql_text(f"""
        SELECT (SELECT count(*) FROM "{schema}".position_chunks),
               (SELECT count(*) FROM "{schema}".position_chunk_embeddings)""")).one()
    assert chunks == vectors == 2
