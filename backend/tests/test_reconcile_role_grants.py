"""The grant-reconciliation tool — the fix for the 2026-09-02 seeding-chronology drift.

The defect it exists for: `seed_default_grants` skips any role already holding
permissions, so `export.generate` (owner directive 2026-08-31, decision #232) and
`contract.delete` (locked AB-10 r6) never reached roles seeded before those grants
were added to `DEFAULT_ROLE_GRANTS`. Export and Delete therefore worked only for
DEVELOPER — the one role seeded after both grants existed.

What is pinned here, in order of importance:

  1. the drifted database is REPAIRED — a user holding USER regains exactly the
     decided permissions, through `effective_permissions`, the value every request
     resolves (S-1);
  2. the tool NEVER removes anything — a grant beyond the defaults survives, so
     reconciliation can never become authority reduction;
  3. the tool REFUSES to apply once any `admin.permission_changed` audit event
     exists — from that point the database reflects administrator decisions, not
     seeding history, and reconciliation belongs to the audited PATCH /roles API;
  4. dry-run writes nothing.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from legalmind.db import models as M
from legalmind.security import permissions as P
from legalmind.security.audit import ADMIN_PERMISSION_CHANGED
from legalmind.security.authorization import effective_permissions
from tests.conftest import grant_role
from tools.reconcile_role_grants import (
    admin_ever_changed_permissions,
    compute_drift,
    reconcile,
)

# The two grants stranded on the development instance, exactly as found there.
STRANDED = (
    ("USER", P.EXPORT_GENERATE),
    ("USER", P.CONTRACT_DELETE),
    ("LEGAL_REVIEWER", P.EXPORT_GENERATE),
    ("LEGAL_ADMIN", P.EXPORT_GENERATE),
)


def _strip(db, role_code: str, permission: str) -> None:
    """Recreate the pre-drift state: the row simply never existed."""
    role = db.execute(select(M.Role).where(M.Role.code == role_code)).scalar_one()
    perm = db.execute(select(M.Permission)
                      .where(M.Permission.name == permission)).scalar_one()
    db.execute(delete(M.RolePermission)
               .where(M.RolePermission.role_id == role.id,
                      M.RolePermission.permission_id == perm.id))
    db.flush()


@pytest.fixture
def drifted(db, seeded):
    """A database in the live instance's observed state: fully seeded, minus the
    four rows that post-date those roles' first seeding."""
    for role, permission in STRANDED:
        _strip(db, role, permission)
    return db


# =====================================================================
# 1 — the repair, observed where it matters: effective permissions
# =====================================================================
def test_a_drifted_database_is_repaired_and_the_user_regains_the_decided_grants(
        drifted, db, user):
    grant_role(db, user, "USER")
    before = effective_permissions(db, user.id)
    assert P.EXPORT_GENERATE not in before, "the drift fixture must reproduce the defect"
    assert P.CONTRACT_DELETE not in before

    drift, added = reconcile(db, apply=True)
    assert added == len(STRANDED)
    assert {(d.role, m) for d in drift for m in d.missing} == set(STRANDED)

    after = effective_permissions(db, user.id)
    assert P.EXPORT_GENERATE in after     # decision #232
    assert P.CONTRACT_DELETE in after     # locked AB-10 r6
    # Nothing beyond the decided defaults arrived with it.
    assert after == set(P.DEFAULT_ROLE_GRANTS["USER"])
    assert compute_drift(db) == []


def test_the_deliberate_exclusions_stay_excluded(drifted, db):
    """AB-10 r6 grants contract.delete to ROLE_USER and the code deliberately
    withholds it from Legal Admin and Super Admin (Step 24 r8/r9); export stays
    off SUPER_ADMIN for the same separation. Reconciliation must not blur that."""
    reconcile(db, apply=True)
    matrix = {}
    for code, name in db.execute(
            select(M.Role.code, M.Permission.name)
            .join(M.RolePermission, M.RolePermission.role_id == M.Role.id)
            .join(M.Permission, M.Permission.id == M.RolePermission.permission_id)):
        matrix.setdefault(code, set()).add(name)
    assert P.CONTRACT_DELETE not in matrix["LEGAL_ADMIN"]
    assert P.CONTRACT_DELETE not in matrix["SUPER_ADMIN"]
    assert P.EXPORT_GENERATE not in matrix["SUPER_ADMIN"]


# =====================================================================
# 2 — additive only: nothing is ever removed
# =====================================================================
def test_a_grant_beyond_the_defaults_survives_reconciliation(drifted, db):
    """Reported as `extra`, never touched: removing it would be authority
    reduction, which this tool must be structurally incapable of."""
    role = db.execute(select(M.Role).where(M.Role.code == "LEGAL_REVIEWER")).scalar_one()
    beyond = db.execute(select(M.Permission)
                        .where(M.Permission.name == P.AUDIT_VIEW)).scalar_one()
    db.add(M.RolePermission(role_id=role.id, permission_id=beyond.id))
    db.flush()

    drift, _ = reconcile(db, apply=True)
    extras = {(d.role, e) for d in drift for e in d.extra}
    assert ("LEGAL_REVIEWER", P.AUDIT_VIEW) in extras

    still = db.execute(select(M.RolePermission).where(
        M.RolePermission.role_id == role.id,
        M.RolePermission.permission_id == beyond.id)).first()
    assert still is not None, "reconciliation removed a grant — it must never"


# =====================================================================
# 3 — the refusal: administrator decisions are not second-guessed
# =====================================================================
def test_it_refuseses_to_apply_once_an_admin_has_changed_role_permissions(drifted, db):
    db.add(M.AuditEvent(id=uuid.uuid4(), action=ADMIN_PERMISSION_CHANGED,
                        entity_type="role", entity_id=uuid.uuid4(),
                        before_state={"permissions": []},
                        after_state={"permissions": ["report.view"]}))
    db.flush()
    assert admin_ever_changed_permissions(db) == 1
    with pytest.raises(SystemExit, match=r"admin\.permission_changed"):
        reconcile(db, apply=True)
    # And nothing was written before the refusal.
    assert any(d.missing for d in compute_drift(db))


def test_the_refusal_only_bites_when_there_is_something_to_apply(db, seeded):
    """An audited admin change on an already-consistent database is fine — the
    tool reports and exits; the guard exists to protect writes, not reads."""
    db.add(M.AuditEvent(id=uuid.uuid4(), action=ADMIN_PERMISSION_CHANGED,
                        entity_type="role", entity_id=uuid.uuid4()))
    db.flush()
    drift, added = reconcile(db, apply=True)
    assert added == 0 and not any(d.missing for d in drift)


# =====================================================================
# 4 — dry run writes nothing
# =====================================================================
def test_dry_run_reports_and_changes_nothing(drifted, db, user):
    grant_role(db, user, "USER")
    drift, added = reconcile(db, apply=False)
    assert added == 0
    assert {(d.role, m) for d in drift for m in d.missing} == set(STRANDED)
    assert P.EXPORT_GENERATE not in effective_permissions(db, user.id)
