"""Create a development login — the 47.1.3 r3 bootstrap path, for a developer machine.

Locked 47.1.3 r3: LegalMind never self-provisions an account, so the first user on any
installation is created OUTSIDE the API — production does it deliberately, the e2e
suite does it in `e2e_bootstrap.py`, and this tool is the same act for a developer's
own database. It seeds the permission catalogue and canonical roles first (idempotent,
never re-grants what an admin trimmed — see `legalmind.security.seed`), then creates
or updates one password-fallback account.

**Refuses to run when `LEGALMIND_ENVIRONMENT=production`.** A convenience password
must not be creatable on the environment that holds real documents (55.3); production
account bootstrap is a deliberate operator act, not this script.

Granting multiple roles is the sanctioned way to see every screen: SUPER_ADMIN still
holds neither `legal.decision` nor `legal_position.view` (SEC-02, ROLE-05) — legal
authority comes only from the legal roles granted alongside, exactly as in the e2e
fixture's `counsel`.

Run from `backend/`:

    python3 -m tools.dev_account --email admin@leapswitch.com --password admin123
    python3 -m tools.dev_account --email you@example.com --password secret \
        --roles USER                      # an ordinary-user view instead
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from legalmind.config import database_url
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security.passwords import hash_password
from legalmind.security.seed import bootstrap

ALL_ROLES = ("SUPER_ADMIN", "LEGAL_ADMIN", "LEGAL_REVIEWER",
             "LEGAL_DECISION_AUTHORITY", "USER")


def ensure_account(db: Session, email: str, password: str,
                   role_codes: tuple[str, ...]) -> dict:
    bootstrap(db)
    roles = {r.code: r for r in db.execute(select(M.Role)).scalars()}
    missing = set(role_codes) - set(roles)
    if missing:
        raise SystemExit(f"unknown role codes: {sorted(missing)}")

    user = db.execute(select(M.User).where(M.User.email == email)).scalar_one_or_none()
    if user is None:
        user = M.User(email=email, name=email.split("@")[0].title(),
                      status=E.UserStatus.ACTIVE)
        db.add(user)
        db.flush()

    identity = db.execute(select(M.UserIdentity).where(
        M.UserIdentity.user_id == user.id,
        M.UserIdentity.provider == E.IdentityProvider.PASSWORD,
    )).scalar_one_or_none()
    if identity is None:
        db.add(M.UserIdentity(user_id=user.id,
                              provider=E.IdentityProvider.PASSWORD,
                              provider_subject=email,
                              credential_hash=hash_password(password)))
    else:
        identity.credential_hash = hash_password(password)

    granted = set(db.execute(
        select(M.Role.code).join(M.UserRole, M.UserRole.role_id == M.Role.id)
        .where(M.UserRole.user_id == user.id)).scalars())
    for code in role_codes:
        if code not in granted:
            db.add(M.UserRole(user_id=user.id, role_id=roles[code].id))
    db.flush()
    return {"user_id": str(user.id), "email": email,
            "roles": sorted(granted | set(role_codes))}


def main(argv: list[str] | None = None) -> int:
    if os.environ.get("LEGALMIND_ENVIRONMENT", "development") == "production":
        print("refusing: dev_account never runs against production (55.3)",
              file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--roles", nargs="*", default=list(ALL_ROLES),
                        help=f"role codes to grant (default: {' '.join(ALL_ROLES)})")
    args = parser.parse_args(argv)

    engine = create_engine(database_url(), future=True)
    with Session(engine) as db:
        result = ensure_account(db, args.email, args.password, tuple(args.roles))
        db.commit()
    print(f"ready: {result['email']}  roles: {', '.join(result['roles'])}")
    print(f"database: {database_url().rsplit('@', 1)[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
