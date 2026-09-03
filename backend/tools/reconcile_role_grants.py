"""Reconcile role grants with the code's DEFAULT_ROLE_GRANTS — additively, never removing.

Why this exists (2026-09-02). `seed_default_grants` deliberately skips any role that
already holds permissions (`only_if_role_empty=True`), so that re-running a bootstrap
never restores a grant an administrator has since removed. The cost of that guard is
seeding chronology: a grant ADDED to `DEFAULT_ROLE_GRANTS` after a role was first
seeded never reaches an existing database. Two owner-decided grants were stranded
exactly this way on the development instance:

    export.generate   -> USER, LEGAL_REVIEWER, LEGAL_ADMIN   (owner directive
                         2026-08-31; AUTO_MODE_DECISIONS #232)
    contract.delete   -> USER                                (locked AB-10 r6,
                         owner approval 2026-09-01)

Both features worked only for the DEVELOPER role, which happened to be seeded after
the grants existed.

**When the guard's concern is real, this tool must not run.** The application's only
runtime path that changes a role's permission set is `PATCH /roles/{id}` (S-10,
locked 43.26), and every use of it writes an `admin.permission_changed` audit event
with the before/after sets. So the question "was this absence an administrator's
deliberate removal?" is answerable from the audit trail, and this tool answers it:
it REFUSES to apply while any `admin.permission_changed` event exists, because from
that point on the database's permission state reflects administrator intent rather
than seeding history, and reconciliation belongs to an administrator through the
audited API instead.

What it never does: remove a grant, touch a role the catalogue does not know,
grant anything beyond `DEFAULT_ROLE_GRANTS`, or invent a permission. It is a
caller for the additive mode `seed_default_grants` has carried all along.

Run from `backend/` — dry-run by default, `--apply` to write:

    python3 -m tools.reconcile_role_grants                # report only
    python3 -m tools.reconcile_role_grants --apply        # add the missing rows
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from legalmind.config import database_url
from legalmind.db import models as M
from legalmind.security import permissions as P
from legalmind.security.audit import ADMIN_PERMISSION_CHANGED
from legalmind.security.seed import seed_default_grants


@dataclass
class Drift:
    """Per-role difference between the live grants and the code's defaults."""

    role: str
    missing: tuple[str, ...]   # in DEFAULT_ROLE_GRANTS, absent from the database
    extra: tuple[str, ...]     # in the database, absent from DEFAULT_ROLE_GRANTS


def _grant_matrix(db: Session) -> dict[str, set[str]]:
    rows = db.execute(
        select(M.Role.code, M.Permission.name)
        .join(M.RolePermission, M.RolePermission.role_id == M.Role.id)
        .join(M.Permission, M.Permission.id == M.RolePermission.permission_id)
    ).all()
    matrix: dict[str, set[str]] = {
        code: set() for code in db.execute(select(M.Role.code)).scalars()
    }
    for code, name in rows:
        matrix.setdefault(code, set()).add(name)
    return matrix


def compute_drift(db: Session) -> list[Drift]:
    """Every role's difference from the defaults, both directions.

    `extra` is reported but never acted on: a permission beyond the defaults was
    either granted by an administrator (audited) or belongs to a bespoke role,
    and removing it is authority reduction this tool must never perform.
    """
    matrix = _grant_matrix(db)
    drift = []
    for code in sorted(set(matrix) | set(P.DEFAULT_ROLE_GRANTS)):
        want = set(P.DEFAULT_ROLE_GRANTS.get(code, ()))
        have = matrix.get(code, set())
        missing = tuple(sorted(want - have))
        extra = tuple(sorted(have - want))
        if missing or extra:
            drift.append(Drift(role=code, missing=missing, extra=extra))
    return drift


def admin_ever_changed_permissions(db: Session) -> int:
    """How many audited role-permission changes exist.

    Zero means every grant and every absence is seeding history, so an additive
    reconciliation cannot contradict any administrator's decision. Non-zero means
    it might, and the tool refuses (see the module docstring).
    """
    return db.execute(text(
        "SELECT count(*) FROM audit_events WHERE action = :a"
    ), {"a": ADMIN_PERMISSION_CHANGED}).scalar_one()


def reconcile(db: Session, *, apply: bool) -> tuple[list[Drift], int]:
    """Report the drift; with ``apply``, add the missing default grants.

    Returns (drift-before, rows-added). Removal is structurally impossible: the
    write path is `seed_default_grants(only_if_role_empty=False)`, which only
    ever INSERTs missing default rows.
    """
    drift = compute_drift(db)
    added = 0
    if apply and any(d.missing for d in drift):
        changed = admin_ever_changed_permissions(db)
        if changed:
            raise SystemExit(
                f"refusing: {changed} admin.permission_changed audit event(s) exist, "
                "so this database's permission state reflects administrator "
                "decisions, not just seeding history. Reconcile through the "
                "audited PATCH /roles API instead.")
        added = seed_default_grants(db, only_if_role_empty=False)
    return drift, added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the missing default grants (default: report only)")
    args = parser.parse_args(argv)

    url = database_url()
    environment = os.environ.get("LEGALMIND_ENVIRONMENT", "development")
    print(f"database:    {url.rsplit('@', 1)[-1]}")
    print(f"environment: {environment}")

    engine = create_engine(url, future=True)
    with Session(engine) as db:
        drift, added = reconcile(db, apply=args.apply)
        if not drift:
            print("no drift: every role matches DEFAULT_ROLE_GRANTS exactly.")
            return 0
        for d in drift:
            if d.missing:
                print(f"{d.role}: missing default grant(s): {', '.join(d.missing)}")
            if d.extra:
                print(f"{d.role}: holds beyond the defaults (kept, never removed): "
                      f"{', '.join(d.extra)}")
        if args.apply:
            db.commit()
            remaining = [d for d in compute_drift(db) if d.missing]
            print(f"added {added} grant row(s); "
                  f"{'all default grants now present' if not remaining else 'STILL MISSING: ' + str(remaining)}")
        else:
            would = sum(len(d.missing) for d in drift)
            print(f"dry run: would add {would} grant row(s). Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
