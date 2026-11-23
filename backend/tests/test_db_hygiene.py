"""P3 "database hygiene" (full-stack audit 2026-11-23): the indexes migration d340ac8e60fd
(DB-2, DB-5) and the comparison-choice lookup (DB-10)."""
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from legalmind import config
from legalmind.db import models as M

INDEXES = {  # name -> table, in this run's private schemas (conftest F-4)
    "ix_unmatched_provisions_evidence_id": "unmatched_provisions",
    "ix_evaluation_evidence_evidence_id": "evaluation_evidence",
    "ix_finding_evidence_evidence_id": "finding_evidence",
    "ix_audit_events_action_entity_id_timestamp": "audit_events",
    "ix_obligation_extractions_evidence_id": "obligation_extractions",
    "ix_conversation_evidence_chunk_id": "conversation_evidence",
}


def test_every_index_is_built_valid_and_the_models_declare_the_locked_ones(db):
    """A concurrent build that fails leaves an INVALID index the planner ignores; the
    migration refuses to finish with one, and this is the same check after `upgrade`."""
    assist = config.assist_schema()
    for name, table in INDEXES.items():
        qualified = name if table in M.Base.metadata.tables else f'"{assist}".{name}'
        assert db.execute(text("SELECT indisvalid FROM pg_index WHERE indexrelid = "
                               "to_regclass(:n)"), {"n": qualified}).scalar() is True, name
        if table in M.Base.metadata.tables:     # else autogenerate would propose a drop
            assert name in {i.name for i in M.Base.metadata.tables[table].indexes}, name


def test_set_role_survives_the_autocommit_block(engine):
    """`alembic/env.py` SETs ROLE once per session (55.2); the concurrent builds run in an
    autocommit block. The role must hold inside the block and after it — a reset session
    would build as the runtime role and write `alembic_version` as it (2026-10-06)."""
    from alembic.runtime.migration import MigrationContext

    from legalmind.db.migrate_role import set_role
    role = text("SELECT current_setting('role')")
    with engine.connect() as c:
        me = c.execute(text("SELECT current_user")).scalar()
        set_role(c, me)
        ctx = MigrationContext.configure(c)
        with ctx.begin_transaction():
            with ctx.autocommit_block():
                assert ctx.connection is not None
                assert ctx.connection.execute(role).scalar() == me
            assert ctx.connection.execute(role).scalar() == me


def test_the_current_choice_lookup_uses_every_column_of_the_unique_index(db, review, user):
    """DB-10: `_current_choice` names the key columns' NULLs (implied by the `right_side` /
    `left_side` CHECKs), so with a pair's choices in the hundreds the lookup is an equality
    on the unique index's columns in order, not a filter over the whole right version."""
    from legalmind.api.routers import negotiation

    ours = review._document_version
    theirs = M.DocumentVersion(
        contract_id=ours.contract_id, version_number=2, original_filename="msa-2.pdf",
        mime_type="application/pdf", file_size_bytes=1, file_hash="def",
        storage_key="s3://k2", processing_status=ours.processing_status,
        uploaded_by=user.id)
    db.add(theirs)
    db.flush()
    db.add_all(M.ComparisonChoice(left_version_id=ours.id, right_version_id=theirs.id,
                                  row_key=f"N|MODIFIED|{n}|{n}", choice="ours",
                                  decided_by=user.id) for n in range(300))
    db.flush()
    db.execute(text("ANALYZE comparison_choices"))
    statements = []

    class _Guard:
        class db:
            @staticmethod
            def execute(stmt):
                statements.append(stmt)
                return db.execute(stmt)
    choice = negotiation._current_choice(_Guard, ours, theirs, "N|MODIFIED|7|7")
    assert choice is not None and choice.row_key == "N|MODIFIED|7|7"
    assert negotiation._current_choice(_Guard, None, theirs, "N|MODIFIED|7|7") is None
    for stmt, left in zip(statements, ("left_key IS NULL", "left_version_id IS NULL"),
                          strict=True):
        sql = str(stmt.compile(dialect=postgresql.dialect(),
                               compile_kwargs={"literal_binds": True}))
        plan = "\n".join(db.execute(text("EXPLAIN " + sql)).scalars())
        assert "uq_comparison_choices_pair_row_version" in plan, plan
        cond = next(line for line in plan.splitlines() if "Index Cond" in line)
        assert "right_key IS NULL" in cond and left in cond and "row_key" in cond, plan
