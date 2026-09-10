"""The locked tables' exact shape — `AM-27` r2's stated evidence, made real.

`AM-27` r2 (AB-3, locked 2026-08-24) says:

    "The 30 existing tables are not altered. No column, constraint, index or enum on any
     locked table is added, changed or removed by this batch, and the existing schema
     invariant tests continue to pass unmodified. **That is the evidence that this record
     leaves the locked model intact.**"

That evidence did not exist when this file was written. `test_schema_invariants.py` asserts
trigger behaviour, EV-MIN, append-only enforcement and enum *label counts* — all valuable, and
none of it sensitive to a column. Adding a column to `document_versions`, or quietly widening
`evaluations`, passed all twenty-one of those tests. So the sentence `AM-27` r2 relies on was
true and yet proved nothing.

This file closes that gap, and it is deliberately the dullest test in the suite: a frozen
snapshot of every table and every column name. It has no cleverness to go wrong.

**How to read a failure.** This test failing is not a bug in the test. It means the locked
schema changed, and exactly one of two things is true:

* An assist-lane migration touched a locked table. That is an `AM-27` r2 violation — revert it.
  The assist tables live in a **separate schema** (r1) and nothing there needs a locked column.
* A locked table genuinely changed under an approved amendment. Then update the snapshot in the
  same commit as the migration and the lock record, and say so in the message. Editing the
  snapshot alone, to make a red test green, converts an unrecorded schema change into a silent
  one — the precise failure `AM-27` r2 exists to prevent.

**Why the live database and not `Base.metadata`.** Metadata is what the models *say*; the
database is what the migrations *did*. A migration adding a column the ORM never declared is
invisible to a metadata check, and that is the more dangerous direction — the schema drifts
ahead of the code with nothing to notice. Both are asserted here, against each other.

`information_schema` is scoped to `current_schema()` throughout, for the reason recorded in
`test_schema_invariants.py`: the suite runs in a private per-process schema (`F-4`), and an
unscoped catalogue query sums across concurrent runs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from legalmind.db.base import Base

# --------------------------------------------------------------------------
# The snapshot. 29 application tables, 196 columns.
#
# 196, not the originally locked 195: `contracts.archived_at` was added on
# 2026-09-01 under the owner-approved contract-deletion amendment, recorded in
# the same change as its migration and its lock record — the one procedure the
# docstring above permits for moving this snapshot.
#
# `alembic_version` is deliberately absent: it is Alembic's own bookkeeping, not part of the
# locked domain model. It is, however, the most likely explanation for `AM-27` r2's "30" —
# 29 application tables plus Alembic's own — and that discrepancy is registered as a conflict
# rather than silently corrected here, because `all_lock.md` wins over a derived document.
# --------------------------------------------------------------------------
LOCKED_SCHEMA: dict[str, tuple[str, ...]] = {
    "audit_events": ('action', 'actor_id', 'after_state', 'before_state', 'entity_id', 'entity_type', 'id', 'metadata', 'timestamp'),
    "company_standard_versions": ('configuration', 'created_at', 'created_by', 'id', 'requirement_version_id', 'version_number'),
    "configuration_snapshot_items": ('company_standard_version_id', 'evaluation_rule_version_id', 'legal_rule_version_id', 'mapping_rule_version_id', 'requirement_version_id', 'snapshot_id'),
    "configuration_snapshots": ('created_at', 'created_by', 'id', 'snapshot_hash'),
    # `archived_at` — added as `deleted_at` on 2026-09-01 (AM-37), renamed by
    # AB-12 on 2026-09-05 when archive replaced deletion. Recorded here in the
    # same change as the migration and the lock record, which is the only way
    # this snapshot may ever move.
    "contracts": ('archived_at', 'contract_type', 'counterparty_id', 'created_at', 'id', 'name', 'owner_id', 'status', 'updated_at'),
    # AB-13 r1 created this table with seven columns. Twelve more were added on
    # 2026-09-10 under the owner's Client Profiles instruction (migration
    # e9f2b6c4a173) — the profile fields a client page shows, all nullable but
    # `status`, none backfilled. Recorded here in the same change as the
    # migration and the model, which is the only way this snapshot may move.
    "counterparties": ('account_owner_id', 'city', 'country', 'created_at', 'created_by', 'id', 'industry', 'legal_contact_email', 'legal_contact_name', 'legal_name', 'name', 'primary_contact_email', 'primary_contact_name', 'primary_contact_phone', 'relationship_notes', 'state_region', 'status', 'updated_at', 'website'),
    "departments": ('code', 'created_at', 'id', 'name'),
    "document_evidence": ('content', 'created_at', 'document_version_id', 'end_offset', 'id', 'metadata', 'page_number', 'processing_run_id', 'section_number', 'section_title', 'source_type', 'start_offset'),
    "document_processing_runs": ('completed_at', 'created_at', 'document_version_id', 'error_code', 'error_message', 'id', 'metadata', 'processor_version', 'run_type', 'started_at', 'status'),
    "document_versions": ('contract_id', 'created_at', 'extraction_status', 'file_hash', 'file_size_bytes', 'id', 'metadata', 'mime_type', 'original_filename', 'processing_status', 'storage_key', 'uploaded_by', 'version_number'),
    "escalations": ('created_at', 'finding_id', 'id', 'raised_by', 'reason', 'withdrawn_at'),
    "evaluation_evidence": ('evaluation_id', 'evidence_id', 'relationship_type'),
    "evaluation_rule_versions": ('created_at', 'created_by', 'evaluator_type', 'id', 'requirement_version_id', 'rules', 'version_number'),
    "evaluations": ('actual_value', 'classification', 'created_at', 'evaluation_kind', 'evaluator_type', 'evaluator_version', 'expected_value', 'finding_id', 'id', 'legal_rule_version_id', 'operator', 'result', 'rule_outcome', 'rule_version_id', 'scope_key', 'scope_label'),
    "finding_evidence": ('evidence_id', 'finding_id', 'relationship_type'),
    "findings": ('classification', 'created_at', 'id', 'requirement_version_id', 'review_id', 'status', 'updated_at'),
    "legal_decisions": ('created_at', 'decided_by', 'decision_type', 'evaluation_id', 'finding_id', 'id', 'justification', 'version_number'),
    "legal_rule_versions": ('configuration', 'created_at', 'created_by', 'id', 'requirement_version_id', 'rule_type', 'version_number'),
    "mapping_rule_versions": ('created_at', 'created_by', 'id', 'requirement_version_id', 'rules', 'version_number'),
    "permissions": ('created_at', 'description', 'id', 'name', 'permission_group'),
    "requirement_versions": ('created_at', 'created_by', 'description', 'evaluator_type', 'id', 'name', 'requirement_id', 'version_number'),
    "requirements": ('code', 'created_at', 'id', 'status', 'updated_at'),
    "review_assignments": ('assigned_by', 'created_at', 'id', 'review_id', 'revoked_at', 'user_id'),
    "reviews": ('completed_at', 'configuration_snapshot_id', 'contract_id', 'created_at', 'created_by', 'document_version_id', 'id', 'started_at', 'status'),
    "role_permissions": ('permission_id', 'role_id'),
    "roles": ('code', 'id', 'name'),
    "sessions": ('created_at', 'expires_at', 'id', 'last_seen_at', 'revoked_at', 'revoked_reason', 'user_id'),
    "unmatched_provisions": ('created_at', 'evidence_id', 'id', 'review_id'),
    "user_identities": ('created_at', 'credential_hash', 'id', 'last_used_at', 'provider', 'provider_subject', 'user_id'),
    "user_roles": ('role_id', 'user_id'),
    # `department_id` added by AB-12 (2026-09-05), nullable.
    "users": ('created_at', 'department_id', 'email', 'id', 'name', 'status', 'updated_at'),
}

# Alembic's bookkeeping table, present in the database and absent from the domain model.
_NON_DOMAIN_TABLES = frozenset({"alembic_version"})


def _live_columns(db) -> dict[str, tuple[str, ...]]:
    """Every table and column the database actually has, in this run's private schema."""
    rows = db.execute(text("""
        SELECT table_name, column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
    """)).all()
    out: dict[str, list[str]] = {}
    for table, column in rows:
        if table in _NON_DOMAIN_TABLES:
            continue
        out.setdefault(table, []).append(column)
    return {t: tuple(sorted(c)) for t, c in out.items()}


# --------------------------------------------------------------------------
# The table set
# --------------------------------------------------------------------------
def test_the_locked_table_set_is_exactly_as_recorded(db):
    """`AM-27` r2 — no locked table is added or removed.

    A NEW table appearing here is the specific thing `AM-27` r1 forbids: assist tables belong
    in a separate schema, so one showing up beside the locked tables means the separation was
    not implemented, whatever the migration intended.
    """
    live = set(_live_columns(db))
    expected = set(LOCKED_SCHEMA)
    assert live - expected == set(), f"table(s) added to the locked schema: {sorted(live - expected)}"
    assert expected - live == set(), f"locked table(s) missing: {sorted(expected - live)}"


def test_the_locked_table_count_is_thirty_one(db):
    """Pinned as a number as well as a set, because the number is what documents quote.

    31 application tables since AB-13 added `counterparties` (2026-09-06). 30 after
    AB-12 added `departments`; before it, 29 — and `AM-27` r2's "30" was reconciled by
    `alembic_version` (C-14). Neither coincidence resolves C-14 (AB-13 r10): the table
    AM-27 counted was not any of these.
    """
    assert len(_live_columns(db)) == 31


# --------------------------------------------------------------------------
# The columns
# --------------------------------------------------------------------------
@pytest.mark.parametrize("table", sorted(LOCKED_SCHEMA), ids=sorted(LOCKED_SCHEMA))
def test_locked_table_columns_are_exactly_as_recorded(db, table):
    """One test per table, so a failure names the table that drifted rather than the suite."""
    live = _live_columns(db)
    assert table in live, f"{table} is missing from the database"
    added = set(live[table]) - set(LOCKED_SCHEMA[table])
    removed = set(LOCKED_SCHEMA[table]) - set(live[table])
    assert not added, f"{table}: column(s) ADDED to a locked table: {sorted(added)}"
    assert not removed, f"{table}: column(s) REMOVED from a locked table: {sorted(removed)}"


def test_the_total_locked_column_count_is_unchanged(db):
    """A single number a reviewer can eyeball against a migration diff.

    196 after 2026-09-01 (`contracts.deleted_at`, AM-37). 201 after 2026-09-05
    (AB-12): that column renamed `archived_at`, `users.department_id` added, and
    the four-column `departments` table added — alongside migration `b7c3d9e1f2a4`
    and the AB-12 lock record. 209 after 2026-09-06 (AB-13): the seven-column
    `counterparties` table and `contracts.counterparty_id`, alongside migration
    `c8e4a1b7d2f6` and the AB-13 lock record. 221 after 2026-09-10: twelve
    profile columns on `counterparties` under the owner's Client Profiles
    instruction, alongside migration `e9f2b6c4a173`. No table was added — the
    client profile IS the counterparty row, and a client's documents ARE its
    contracts, so nothing beyond that one table changed.
    """
    live = _live_columns(db)
    assert sum(len(c) for c in live.values()) == 221


# --------------------------------------------------------------------------
# Model/database agreement
# --------------------------------------------------------------------------
def test_the_orm_and_the_database_agree(db):
    """Neither may drift ahead of the other.

    The dangerous direction is a migration adding a column the models never declared: the ORM
    keeps working, nothing references the column, and no metadata-only check can see it. Both
    directions are asserted, so either kind of drift fails here.
    """
    live = _live_columns(db)
    orm = {name: tuple(sorted(c.name for c in table.columns))
           for name, table in Base.metadata.tables.items()}
    assert set(orm) == set(live), (
        f"ORM-only tables: {sorted(set(orm) - set(live))}; "
        f"database-only tables: {sorted(set(live) - set(orm))}")
    for name in sorted(orm):
        assert orm[name] == live[name], (
            f"{name}: models declare {orm[name]}, database has {live[name]}")
