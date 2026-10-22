"""Grant the FIRST designated reviewer — the one-time, audited bootstrap of AB-100.

S-8 lets only a holder of `legal.decision` grant it, and an installation where nobody
holds it can therefore never get one through the Admin screen. This tool makes that
first grant outside the API — the same deliberate operator act as 47.1.3 r3's first
account — and only then:

* the person exists, is ACTIVE, and is named by email;
* NOBODY active holds `legal.decision` yet — or `--authorised-by` names an ACTIVE holder
  of it who asked for this grant (S-8: authority flows only from someone who holds it),
  recorded as the audit event's actor;
* the operator names themself (`--operator`); the audit trail records it.

It grants Legal Reviewer + Legal Decision Authority — the two roles a person a Review
is sent to must hold (AB-100). Without `--yes` it only says what it would do. On
production it is run ONLY with the owner's explicit go (owner, 2026-10-21).

    python3 -m tools.grant_legal_authority --email reviewer@leapswitch.com \\
        --operator "name of the person running it" [--yes]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from legalmind.config import database_url
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.guards import count_legal_authorities
from legalmind.security.resolver import has_permission

ROLES = (P.ROLE_LEGAL_REVIEWER, P.ROLE_LEGAL_DECISION_AUTHORITY)


def grant_first(db: Session, email: str, operator: str,
                authorised_by: str | None = None) -> list[str]:
    """The roles granted, or SystemExit with the reason nothing was."""
    if not operator.strip():
        raise SystemExit("refusing: --operator must name the person running this")
    user = db.execute(select(M.User).where(M.User.email == email)).scalar_one_or_none()
    if user is None or user.status is not E.UserStatus.ACTIVE:
        raise SystemExit(f"refusing: no active user {email}")
    actor = None
    if authorised_by:
        actor = db.execute(select(M.User).where(M.User.email == authorised_by)
                           ).scalar_one_or_none()
        if (actor is None or actor.status is not E.UserStatus.ACTIVE
                or not has_permission(db, actor.id, P.LEGAL_DECISION)):
            raise SystemExit(f"refusing: {authorised_by} does not hold legal.decision (S-8)")
        if actor.id == user.id:
            raise SystemExit("refusing: nobody authorises a grant to themselves")
    elif count_legal_authorities(db):
        raise SystemExit("refusing: someone already holds legal.decision — name them with "
                         "--authorised-by, or grant it on Admin → Users")
    roles = {r.code: r for r in db.execute(select(M.Role).where(
        M.Role.code.in_(ROLES))).scalars()}
    held = set(db.execute(select(M.UserRole.role_id)
                          .where(M.UserRole.user_id == user.id)).scalars())
    granted = []
    for code in ROLES:
        if roles[code].id not in held:
            db.add(M.UserRole(user_id=user.id, role_id=roles[code].id))
            granted.append(code)
            A.record(db, action=A.ADMIN_LEGAL_AUTHORITY_GRANTED, entity_type="user",
                     entity_id=user.id, actor_id=actor.id if actor else None,
                     after={"role": code, "operator": operator.strip(),
                            **({"authorised_by": actor.email} if actor else {}),
                            "via": "tools.grant_legal_authority (AB-100)"})
    db.flush()
    return granted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--authorised-by", help="email of an active legal.decision holder "
                        "who asked for this grant")
    parser.add_argument("--yes", action="store_true", help="make the grant")
    args = parser.parse_args(argv)
    with Session(create_engine(database_url(), future=True)) as db:
        granted = grant_first(db, args.email, args.operator, args.authorised_by)
        if args.yes:
            db.commit()
        else:
            db.rollback()
    print(("granted" if args.yes else "would grant") + f": {args.email} "
          f"{', '.join(granted) or '(already holds both roles)'}")
    print(f"database: {database_url().rsplit('@', 1)[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
