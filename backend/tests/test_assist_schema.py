"""The assist-lane schema — locked `AM-27`, and `AM-29` r2's separation.

These assert the *record*, not the implementation's convenience. There is no assist
application code yet, so everything here is raw SQL and catalogue inspection — the
house style of `test_schema_invariants.py`, and appropriate for the same reason:
the properties being checked are structural, and a behavioural test cannot show that
a column is absent.

What `AM-27` r2's evidence sentence needs is in a different file. It says the existing
schema invariant tests must "continue to pass unmodified", and
`test_locked_schema_columns.py` is what makes that mechanically true — it snapshots
the locked tables and is expected to pass across this migration untouched. Nothing
here duplicates it.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.db import models as M
from legalmind.domain import enums as E

# `AM-27`'s permitted nine (all present since 2026-08-26) plus `AM-32`'s permitted
# five (AB-5, owner-approved 2026-08-27). AM-32's sixth slot — a judgments registry —
# is RESERVED, not authorized: its absence from this list is deliberate, and a
# judgments table appearing before its own further record fails here.
EXPECTED_TABLES = frozenset({
    # AM-27
    "chunks",
    "chunk_embeddings",
    "embedding_models",
    "conversations",
    "messages",
    "retrieval_runs",
    "ai_answers",
    "answer_citations",
    "prompt_versions",
    # AM-32
    "position_chunks",
    "position_chunk_embeddings",
    "statutes",
    "statute_chunks",
    "statute_chunk_embeddings",
})

# The nine values `AM-29` r2 forbids an assist-lane state from reusing.
FORBIDDEN_STATE_VALUES = frozenset({
    "UNABLE_TO_EVALUATE", "NOT_APPLICABLE", "AMBIGUOUS", "MATCH", "DEVIATION",
    "MISSING", "CONFLICT", "ACCEPTABLE", "UNACCEPTABLE",
})

# The enum type names belonging to the five legal axes. `AM-29` r1: the sixth axis
# "never shares a field, a column, an enum or a name with any of the five".
LEGAL_AXIS_ENUMS = frozenset({
    "mapping_state", "finding_classification", "rule_outcome", "decision_type",
    "review_status", "finding_status",
})


@pytest.fixture
def assist(db):
    """The assist schema name for this run, with the schema asserted to exist."""
    schema = config.assist_schema()
    found = db.execute(text(
        "SELECT nspname FROM pg_namespace WHERE nspname = :s"), {"s": schema}).scalar()
    assert found == schema, f"assist schema {schema!r} was not created"
    return schema


def _tables(db, schema: str) -> set[str]:
    return set(db.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = :s"
    ), {"s": schema}).scalars().all())


def _columns(db, schema: str, table: str) -> dict[str, tuple[str, str]]:
    rows = db.execute(text("""
        SELECT column_name, data_type, is_nullable
          FROM information_schema.columns
         WHERE table_schema = :s AND table_name = :t
    """), {"s": schema, "t": table}).all()
    return {r[0]: (r[1], r[2]) for r in rows}


# ==========================================================================
# AM-27 r1 — a separate schema, and only the authorized tables in it
# ==========================================================================
def test_the_assist_schema_is_not_the_locked_schema(db, assist):
    """`AM-27` r1 — the two never share a schema.

    Asserted rather than assumed because the whole isolation argument rests on it:
    the database role in `AM-25` r2, the untouched locked columns in r2, and the
    import boundary in `test_import_boundaries.py` all describe a separation that is
    meaningless if the tables sit together.
    """
    locked = db.execute(text("SELECT current_schema()")).scalar()
    assert assist != locked
    assert assist.endswith("_assist"), (
        "in a test run the assist schema must be derived per run, or concurrent "
        "suites share one and F-4's collision returns")


def test_only_authorized_tables_exist_in_the_assist_schema(db, assist):
    """`AM-27`: nine tables permitted, *"No other table is authorized by this record."*

    A table here that `AM-27` does not name is not a design question — it is
    unauthorized, and the record is closed.
    """
    found = _tables(db, assist)
    unauthorized = found - EXPECTED_TABLES
    assert not unauthorized, (
        f"unauthorized table(s) in the assist schema: {sorted(unauthorized)}. "
        "AM-27 permits nine and closes with 'No other table is authorized'.")
    missing = EXPECTED_TABLES - found
    assert not missing, f"expected assist table(s) missing: {sorted(missing)}"


def test_chunk_embeddings_dimension_matches_the_selected_model(db, assist):
    """The ninth table exists, and its dimension is the MEASURED one.

    Until 2026-08-26 a tripwire test here asserted this table's absence, because its
    vector width is a property of an embedding model and `AM-26` r2 selects that model
    by measurement — pinning a dimension first would have settled by DDL what the
    record settles by evidence. The measurement happened (owner-ratified 77-question
    set, four candidates, smallest-that-passes): all-MiniLM-L6-v2, 384 dimensions.

    This asserts the DDL literal and the calibration module agree — the two places the
    number lives. A different model with a different width is a NEW migration, never a
    config change, so stored vectors can never silently become incomparable with fresh
    query vectors.
    """
    from legalmind.assist.calibration import EMBEDDING_DIMENSIONS

    atttypmod = db.execute(text("""
        SELECT a.atttypmod FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = :s AND c.relname = 'chunk_embeddings'
           AND a.attname = 'embedding'
    """), {"s": assist}).scalar()
    assert atttypmod == EMBEDDING_DIMENSIONS, (
        f"vector({atttypmod}) in DDL vs {EMBEDDING_DIMENSIONS} in calibration.py")


def test_a_chunk_embedding_dies_with_its_chunk(db, assist, user):
    """`AM-27` r5 extends to embeddings: deleting a document hard-deletes them.

    The chain is chunk_embeddings -> chunks -> document_evidence, each ON DELETE
    CASCADE, exercised with real rows and a real DELETE.
    """
    contract = M.Contract(name="embedding cascade probe", owner_id=user.id,
                          contract_type="MSA", status=E.ContractStatus.DRAFT)
    db.add(contract)
    db.flush()
    dv = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="p.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=10, file_hash="j" * 64, storage_key="k3",
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=user.id)
    db.add(dv)
    db.flush()
    run = M.DocumentProcessingRun(
        document_version_id=dv.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run)
    db.flush()
    ev = M.DocumentEvidence(
        document_version_id=dv.id, processing_run_id=run.id,
        content="A clause about notice periods for termination.",
        source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(ev)
    db.flush()

    chunk_id, model_id, emb_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{assist}".chunks
            (id, document_version_id, evidence_id, ordinal, content,
             chunking_algorithm_version)
        VALUES (:c, :dv, :ev, 0, 'A clause about notice periods.', 'test-v1')
    """), {"c": chunk_id, "dv": dv.id, "ev": ev.id})
    db.execute(text(f"""
        INSERT INTO "{assist}".embedding_models (id, name, version, dimensions, checksum)
        VALUES (:m, 'test-model', 'v1', 384, :ck)
    """), {"m": model_id, "ck": "0" * 64})
    from legalmind.assist.store import vector_type

    vector_literal = "[" + ",".join(["0.05"] * 384) + "]"
    db.execute(text(f"""
        INSERT INTO "{assist}".chunk_embeddings (id, chunk_id, embedding_model_id, embedding)
        VALUES (:e, :c, :m, CAST(:v AS {vector_type(db)}))
    """), {"e": emb_id, "c": chunk_id, "m": model_id, "v": vector_literal})

    db.execute(text("DELETE FROM document_evidence WHERE id = :i"), {"i": ev.id})
    remaining = db.execute(text(
        f'SELECT count(*) FROM "{assist}".chunk_embeddings WHERE id = :e'),
        {"e": emb_id}).scalar()
    assert remaining == 0, "the embedding survived its chunk's evidence row"



# ==========================================================================
# AM-27 r3 — the 42.1 design rules, "in full and without exception"
# ==========================================================================
@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_primary_key_is_a_uuid(db, assist, table):
    """42.1 via `AM-27` r3 — UUID primary keys."""
    cols = _columns(db, assist, table)
    assert "id" in cols, f"{table} has no id column"
    assert cols["id"][0] == "uuid", f"{table}.id is {cols['id'][0]}, not uuid"


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_timestamps_carry_a_timezone(db, assist, table):
    """42.1 via `AM-27` r3 — UTC timestamps.

    `timestamp without time zone` is the failure this catches: it stores a wall-clock
    reading whose meaning depends on the session that wrote it.
    """
    for name, (dtype, _) in _columns(db, assist, table).items():
        if name.endswith("_at"):
            assert dtype == "timestamp with time zone", (
                f"{table}.{name} is {dtype!r}; 42.1 requires UTC timestamps")


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES - {"embedding_models", "prompt_versions"}))
def test_every_reference_is_a_real_foreign_key(db, assist, table):
    """42.1 via `AM-27` r3 — real foreign keys, not loose id columns.

    Every `*_id` column must be backed by a constraint. The two registry tables are
    excluded because they reference nothing; `retrieval_runs.results` holds chunk ids
    inside JSONB by necessity and is covered separately.
    """
    id_columns = {n for n in _columns(db, assist, table) if n.endswith("_id")}
    constrained = set(db.execute(text("""
        SELECT kcu.column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON kcu.constraint_name = tc.constraint_name
           AND kcu.table_schema = tc.table_schema
         WHERE tc.table_schema = :s AND tc.table_name = :t
           AND tc.constraint_type = 'FOREIGN KEY'
    """), {"s": assist, "t": table}).scalars().all())
    unbacked = id_columns - constrained
    assert not unbacked, f"{table}: id column(s) with no foreign key: {sorted(unbacked)}"


# ==========================================================================
# AM-29 — the sixth axis, kept apart from the five
# ==========================================================================
def test_the_answer_state_enum_reuses_no_legal_state_value(db, assist):
    """`AM-29` r2 — the nine forbidden values, checked mechanically.

    `test_schema_invariants.py::test_each_axis_has_its_own_enum_type` is scoped to
    `current_schema()` and therefore cannot see anything in the assist schema. That
    gap is why this test exists: without it, nothing at all would stop an assist enum
    from reusing `AMBIGUOUS` or `MATCH`, and `AM-29` r2 would be a sentence rather
    than a constraint.
    """
    values = set(db.execute(text("""
        SELECT e.enumlabel FROM pg_enum e
          JOIN pg_type t ON t.oid = e.enumtypid
          JOIN pg_namespace n ON n.oid = t.typnamespace
         WHERE n.nspname = :s
    """), {"s": assist}).scalars().all())
    assert values, "no assist enum found; the answer-state axis should exist"
    collisions = values & FORBIDDEN_STATE_VALUES
    assert not collisions, (
        f"assist enum reuses value(s) {sorted(collisions)} from a legal axis — "
        "AM-29 r2 forbids exactly this, and calls it 'a route to adding a fifth "
        "RuleOutcome value by another name'")


def test_the_answer_state_enum_shares_no_name_with_a_legal_axis(db, assist):
    """`AM-29` r1 — "never shares a field, a column, an enum or a name"."""
    names = set(db.execute(text("""
        SELECT t.typname FROM pg_type t
          JOIN pg_namespace n ON n.oid = t.typnamespace
         WHERE n.nspname = :s AND t.typtype = 'e'
    """), {"s": assist}).scalars().all())
    assert names == {"assist_answer_state"}, f"unexpected assist enum types: {names}"
    assert not (names & LEGAL_AXIS_ENUMS)


def test_the_answer_state_records_the_three_causes_separately(db, assist):
    """`AM-29` r3 — three outcomes, "different causes and different remedies".

    Collapsing them into one refusal value would lose the distinction the record
    requires: nothing retrievable, versus retrieved-but-too-weak (where the model is
    never called), versus the model answered and a claim failed verification.
    """
    values = set(db.execute(text("""
        SELECT e.enumlabel FROM pg_enum e
          JOIN pg_type t ON t.oid = e.enumtypid
          JOIN pg_namespace n ON n.oid = t.typnamespace
         WHERE n.nspname = :s AND t.typname = 'assist_answer_state'
    """), {"s": assist}).scalars().all())
    assert values == {"ANSWERED", "NO_EVIDENCE_RETRIEVED",
                      "EVIDENCE_INSUFFICIENT", "CLAIM_UNSUPPORTED"}


def test_no_assist_table_carries_a_confidence_column(db, assist):
    """`AI-03` locked item 16 — *"The system does not use generic AI confidence scores."*

    Also rule 12, which forbids an "AI confidence" percentage on a Finding. The
    sanctioned signal is the answer state plus per-citation retrieval scores, and a
    retrieval score is never rendered as legal confidence. A column called
    `confidence` is how that distinction gets lost.
    """
    offenders = db.execute(text("""
        SELECT table_name, column_name FROM information_schema.columns
         WHERE table_schema = :s AND (column_name LIKE '%confidence%'
                                   OR column_name LIKE '%certainty%')
    """), {"s": assist}).all()
    assert not offenders, f"confidence-style column(s): {offenders}"


# ==========================================================================
# AM-27 r4, r5, r6 — provenance, hard delete, and no second text store
# ==========================================================================
def test_a_chunk_cannot_exist_without_its_evidence_row(db, assist):
    """`AM-27` r4 — a chunk "references the Document Evidence row it came from".

    Enforced as NOT NULL plus a foreign key, so a chunk with no traceable origin is
    unrepresentable rather than merely discouraged. Rule 11's evidence-traceability
    requirement is the reason.
    """
    cols = _columns(db, assist, "chunks")
    assert cols["evidence_id"] == ("uuid", "NO"), (
        "chunks.evidence_id must be NOT NULL uuid")
    assert cols["document_version_id"] == ("uuid", "NO")


def test_a_chunk_does_not_duplicate_evidence_provenance(db, assist):
    """`AM-27` r4 — a chunk "carries no independent provenance".

    Page, section number, section title and source type live on the evidence row and
    are reached by join. A copy here would be a second, divergeable record of where
    the text came from, and a stale copy is the standard way a derived store starts
    lying about its source.
    """
    cols = set(_columns(db, assist, "chunks"))
    duplicated = cols & {"page_number", "section_number", "section_title",
                         "source_type", "processing_run_id"}
    assert not duplicated, (
        f"chunks duplicates evidence provenance column(s) {sorted(duplicated)}; "
        "join to document_evidence instead")


def test_deleting_a_document_version_hard_deletes_its_chunks(db, assist, user):
    """`AM-27` r5 — *"A soft-deleted document whose chunks remain retrievable is a
    defect, not a state."*

    Exercised against real rows and a real DELETE rather than by reading the
    catalogue, because the property that matters is the observable one.

    Deliberately on a document version with **no Review**. `reviews.document_version_id`
    carries no cascade, so a reviewed document version cannot be deleted at all — which
    is correct (a Review must stay reproducible) and is worth knowing: `AM-27` r5
    describes what happens *when* a document is deleted, and the locked schema
    currently has no path that deletes a reviewed one. That gap is recorded as an open
    retention question, not papered over here.
    """
    contract = M.Contract(name="cascade probe", owner_id=user.id,
                          contract_type="MSA", status=E.ContractStatus.DRAFT)
    db.add(contract)
    db.flush()
    dv = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="p.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=10, file_hash="h" * 64, storage_key="k",
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=user.id)
    db.add(dv)
    db.flush()
    run = M.DocumentProcessingRun(
        document_version_id=dv.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run)
    db.flush()
    ev = M.DocumentEvidence(
        document_version_id=dv.id, processing_run_id=run.id,
        content="The Provider's total liability shall not exceed the fees paid.",
        source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(ev)
    db.flush()

    chunk_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{assist}".chunks
            (id, document_version_id, evidence_id, ordinal, content,
             chunking_algorithm_version)
        VALUES (:id, :dv, :ev, 0, :content, 'test-v1')
    """), {"id": chunk_id, "dv": dv.id, "ev": ev.id, "content": ev.content})

    assert db.execute(text(f'SELECT count(*) FROM "{assist}".chunks WHERE id = :i'),
                      {"i": chunk_id}).scalar() == 1

    # Deleted at the evidence row, which is where the chunk's own cascade is defined.
    # Deleting the document version itself is not possible at all — see the next test.
    db.execute(text("DELETE FROM document_evidence WHERE id = :i"), {"i": ev.id})

    assert db.execute(text(f'SELECT count(*) FROM "{assist}".chunks WHERE id = :i'),
                      {"i": chunk_id}).scalar() == 0, (
        "the chunk survived its evidence row — AM-27 r5 requires a hard delete")


def test_the_locked_schema_has_no_delete_path_for_a_document_version(db, user):
    """`AM-27` r5's premise cannot currently arise, and that is worth pinning.

    r5 says *"Deleting a document hard-deletes its chunks and embeddings."* The assist
    cascade that implements it is verified above. But the locked schema has no path
    that deletes a document version in the first place: every child references it
    without a cascade, so the delete is refused outright.

    This is not a defect to fix here — a Review must stay reproducible, so a document
    version a Review points at should be hard to remove. It is recorded because the
    retention and deletion policy is genuinely undecided, and because **if someone
    later adds cascades to the locked schema, this test fails** and forces them to
    revisit what r5 then implies about legal records. A silent change here would be a
    change to whether historical Reviews remain reproducible.
    """
    contract = M.Contract(name="delete probe", owner_id=user.id,
                          contract_type="MSA", status=E.ContractStatus.DRAFT)
    db.add(contract)
    db.flush()
    dv = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="p.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=10, file_hash="i" * 64, storage_key="k2",
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=user.id)
    db.add(dv)
    db.flush()
    db.add(M.DocumentProcessingRun(
        document_version_id=dv.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED))
    db.flush()

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM document_versions WHERE id = :i"), {"i": dv.id})


def test_the_generated_tsvector_cannot_disagree_with_the_content(db, assist, review):
    """The keyword index is derived, not written.

    A generated column cannot drift from `content`; an application-maintained one
    can, and a stale search index over legal text is a silent correctness problem
    rather than a visible failure.
    """
    dv = review._document_version
    run = M.DocumentProcessingRun(
        document_version_id=dv.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run)
    db.flush()
    ev = M.DocumentEvidence(
        document_version_id=dv.id, processing_run_id=run.id,
        content="Termination for convenience requires ninety days notice.",
        source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(ev)
    db.flush()
    db.execute(text(f"""
        INSERT INTO "{assist}".chunks
            (id, document_version_id, evidence_id, ordinal, content,
             chunking_algorithm_version)
        VALUES (:id, :dv, :ev, 0, :content, 'test-v1')
    """), {"id": uuid.uuid4(), "dv": dv.id, "ev": ev.id, "content": ev.content})

    # The stem of "requires" matches "require"; the index is doing real linguistic
    # work rather than substring matching.
    hit = db.execute(text(f"""
        SELECT count(*) FROM "{assist}".chunks
         WHERE content_tsv @@ to_tsquery('english', 'terminate & require')
    """)).scalar()
    assert hit == 1

    generated = db.execute(text("""
        SELECT is_generated FROM information_schema.columns
         WHERE table_schema = :s AND table_name = 'chunks'
           AND column_name = 'content_tsv'
    """), {"s": assist}).scalar()
    assert generated == "ALWAYS", "content_tsv must be generated, not written"


def test_retrieval_and_answer_records_hold_no_document_text_column(db, assist):
    """`AM-27` r6 — they "do not duplicate document text into a second store".

    `retrieval_runs.query_text` is the requester's own question, not document text,
    and `messages.content` is the turn itself. What must not appear is a copy of the
    retrieved passage: the text stays reachable through the chunk reference, by a
    reader already authorized to read that document.
    """
    for table in ("retrieval_runs", "ai_answers", "answer_citations"):
        cols = set(_columns(db, assist, table))
        offending = cols & {"content", "chunk_content", "text", "excerpt",
                            "passage", "snippet", "evidence_content"}
        assert not offending, (
            f"{table} carries document-text column(s) {sorted(offending)}; "
            "AM-27 r6 keeps the text reachable through the chunk reference only")


def test_an_answer_can_record_that_the_model_was_never_called(db, assist):
    """`AM-29` r3 — `EVIDENCE_INSUFFICIENT` means "the model is not called at all".

    So `model_identity` and `prompt_version_id` must be nullable. A NOT NULL column
    would force a placeholder, and a placeholder model identity on an answer that
    never reached a model is a fabricated record of an external call.
    """
    cols = _columns(db, assist, "ai_answers")
    assert cols["model_identity"][1] == "YES"
    assert cols["prompt_version_id"][1] == "YES"
    assert cols["answer_state"][1] == "NO", "the answer state itself is never null"


# ==========================================================================
# AM-25 r2 — the database role
# ==========================================================================
def test_the_assist_role_holds_no_write_grant_on_any_authoritative_table(db):
    """`AM-25` r2 — enforced "by a distinct database role holding no INSERT or UPDATE
    grant on those tables, not by convention".

    The role is a **deployment precondition**: creating one needs `CREATEROLE`, which
    the application role does not and must not have. So this test asserts the property
    conditionally and `legalmind.deploy.preflight` asserts the role's existence — the
    split is deliberate, and skipping here would hide a real violation in an
    environment where the role *does* exist.
    """
    role = db.execute(text(
        "SELECT rolname FROM pg_roles WHERE rolname = 'legalmind_assist'")).scalar()
    if role is None:
        pytest.skip("legalmind_assist role is a deployment precondition; "
                    "preflight asserts its existence")

    forbidden = [
        "findings", "evaluations", "legal_decisions", "requirement_versions",
        "company_standard_versions", "legal_rule_versions", "mapping_rule_versions",
        "evaluation_rule_versions", "configuration_snapshots",
        "configuration_snapshot_items",
    ]
    for table in forbidden:
        for privilege in ("INSERT", "UPDATE"):
            granted = db.execute(text(
                "SELECT has_table_privilege('legalmind_assist', :t, :p)"
            ), {"t": table, "p": privilege}).scalar()
            assert granted is False, (
                f"legalmind_assist holds {privilege} on {table} — AM-25 r2 forbids "
                "any INSERT or UPDATE grant on the authoritative tables")
