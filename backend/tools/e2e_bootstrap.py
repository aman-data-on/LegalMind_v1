"""Prepare a database for the browser suite — the one thing the API cannot do.

Locked 47.1.3 r3: **"LegalMind never self-provisions an account."** `POST /users`
deliberately cannot set a credential, so the first administrator has to be created
outside the API — exactly as a real installation would. That is all this script
provisions. Everything else the browser suite needs — contracts, documents,
Requirements, configuration versions, snapshots, Reviews — is built *through the real
endpoints* by the specs, so the suite exercises the API rather than a fixture loader.

**Nothing here is a legal position.** It provisions three accounts and emits one
`STRUCTURAL` fixture — a synthetic document and a configuration whose numbers,
phrases, units and outcomes exist solely to exercise the algorithm. None of it is the
organization's Company Standard, none of it is a legal requirement, and no expected
output here is a legal conclusion (rule 21; locked 54.6 permits "synthetic or cleared"
text and forbids real counterparty contracts entering the repository — the generated
`.docx` is gitignored besides).

The fixture is emitted as *description*, not applied: the specs POST it through the
real endpoints, so the browser suite exercises the configuration API rather than a
loader. It lives here because the document text and the mapping phrases have to agree,
and one definition cannot disagree with itself.

The three accounts exist because the properties under test are about *authority*:

```text
admin     SUPER_ADMIN + LEGAL_ADMIN + USER   builds the fixture through the API
owner     USER                               NO legal_position.view — the
                                             confidentiality subject (LEGAL-02)
counsel   LEGAL_REVIEWER + LEGAL_DECISION_AUTHORITY + USER
                                             the only one who may decide (SEC-02)
```

Note what is *not* granted: `admin` holds neither `legal.decision` nor
`legal_position.view`, so a super-role holder deciding by any route stays impossible
here too (SEC-02, ROLE-05) rather than being quietly enabled for convenience.

**Why `counsel` also holds `USER`.** Not for access — locked `REC-09` settled that.
`counsel` reaches another user's Review through **Legal scope**, which is what
`legal-access.spec.ts` exercises and what `F-6` was about. `USER` is here only so
`counsel` can *build its own* fixture in the specs that compare two callers over
equivalent Reviews (`confidentiality.spec.ts`, `decision.spec.ts`), where the property
under test is the permission difference rather than the access path.

Historical note, because it is the reason this suite exists: before `REC-09` a Legal
Reviewer could reach **no Review at all**, and the backend suite could not see it —
nine of its test sites insert `review_assignments` rows with `db.add()`, so every
Legal-workflow test ran against a state the product had no way to produce. A browser
cannot fake a database row.

Run from `backend/`:

    python3 -m tools.e2e_bootstrap --recreate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import sessionmaker

from legalmind.config import database_url
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security.passwords import hash_password
from legalmind.security.seed import bootstrap

#: A local test credential for a synthetic account, never a secret and never used
#: anywhere real (55.3: development is synthetic data only; S-6 keeps real secrets in
#: the environment). Named so it cannot be mistaken for one.
DEFAULT_PASSWORD = "e2e-not-a-secret"

# ==========================================================================
# The STRUCTURAL fixture — carries NO legal meaning (rule 21, locked 54.6)
# ==========================================================================
# Synthetic text. "24 months" is not a position the organization holds; it is a number
# larger than the configured acceptable maximum below, chosen so the evaluation reaches
# APPROVAL_REQUIRED and therefore produces an Evaluation that *requires a decision* —
# which is what the confidentiality and no-optimistic-UI specs need to exercise.
STRUCTURAL_PARAGRAPHS = [
    "1. Limitation of Liability",
    "Liability shall not exceed 24 months of fees paid.",
    "2. Governing Law",
    "This agreement is governed by the laws of the jurisdiction stated in Schedule A.",
]

# Mapping rules target BOTH the heading and the substantive sentence: each DOCX
# paragraph is its own evidence row, and rules matching only the heading would confirm
# a clause containing no cap. That is the mapping layer working as locked, and it is
# why real rules must target substantive text.
STRUCTURAL_CONFIGURATION: dict[str, object] = {
    "requirement_code": "STRUCTURAL-E2E-001",
    "name": "Structural liability cap (no legal meaning)",
    "description": "STRUCTURAL fixture for the browser suite. Not a legal position.",
    "evaluator_type": "NUMERIC_COMPARISON",
    "company_standard": {
        # Step 28 scoping (owner Q2/Q3, 2026-08-19): publish refuses an untyped
        # standard. MSA matches the type the suite declares on its contracts.
        "document_type": "MSA",
        "applicability": "REQUIRED",
        "preferred": 6,
        "unit": "months",
        "basis": "BASIS_FEES",
        "scope_key": "GENERAL",
        "extraction": {
            "cap_phrases": ["shall not exceed"],
            "unlimited_phrases": ["shall not be limited"],
            "units": ["months"],
            "bases": {"BASIS_FEES": ["fees paid"]},
            "exceptions": [],
        },
    },
    "mapping_rules": {
        "exact_phrases": ["limitation of liability", "shall not exceed"],
        "keyword_groups": [["liability", "shall not exceed"]],
        "section_heading_terms": ["liability"],
        # D-1 — REQUIRED, with no default anywhere. The value is structural; a real
        # threshold is Step 35.10 calibration against representative contracts.
        "confirm_threshold": 5,
    },
    "evaluation_rules": {},
    "legal_rule": {
        "rule_type": "THRESHOLD",
        "configuration": {
            "acceptable_max": 12,
            "approval_required_above": 12,
            "unlimited_outcome": "UNACCEPTABLE",
            "rule_configuration": {
                "scope_required": True,
                "comparable_scopes": ["GENERAL"],
                "comparable_bases": ["BASIS_FEES"],
            },
        },
    },
}

ACCOUNTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "admin": ("admin@e2e.test", ("SUPER_ADMIN", "LEGAL_ADMIN", "USER")),
    "owner": ("owner@e2e.test", ("USER",)),
    # `USER` is present only because of `F-6` — see the module docstring.
    "counsel": ("counsel@e2e.test",
                ("LEGAL_REVIEWER", "LEGAL_DECISION_AUTHORITY", "USER")),
}


def _server_url(url: str) -> tuple[str, str]:
    """Split a database URL into (server URL against `postgres`, database name)."""
    parts = urlsplit(url)
    database = parts.path.lstrip("/")
    return urlunsplit(parts._replace(path="/postgres")), database


def recreate_database(url: str) -> str:
    """Drop and recreate the target database.

    Only ever run against the e2e database the caller names. A browser suite needs a
    known-empty starting point; sharing the development database would let one run's
    Reviews change another's assertions — the `F-4` failure class.
    """
    server_url, database = _server_url(url)
    engine = create_engine(server_url, future=True, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{database}"'))
    engine.dispose()
    return database


def migrate(url: str) -> None:
    """Run the REAL migrations, never `create_all`.

    The invariant triggers (EV-MIN, append-only) exist only in the migrations, so a
    metadata-created schema would silently drop the guarantees the suite relies on
    (55.4 r4).
    """
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    # configparser treats `%` as interpolation; a URL may contain one.
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def provision(db: DBSession, password: str) -> dict[str, dict[str, str]]:
    bootstrap(db)

    roles = {r.code: r for r in db.execute(select(M.Role)).scalars()}
    missing = {code for _, codes in ACCOUNTS.values() for code in codes} - set(roles)
    if missing:
        raise SystemExit(f"canonical roles absent after bootstrap: {sorted(missing)}")

    encoded = hash_password(password)
    out: dict[str, dict[str, str]] = {}
    for label, (email, role_codes) in ACCOUNTS.items():
        user = db.execute(
            select(M.User).where(M.User.email == email)).scalars().first()
        if user is None:
            user = M.User(email=email, name=label.title(),
                          status=E.UserStatus.ACTIVE)
            db.add(user)
            db.flush()

        identity = db.execute(
            select(M.UserIdentity).where(
                M.UserIdentity.user_id == user.id,
                M.UserIdentity.provider == E.IdentityProvider.PASSWORD)
        ).scalars().first()
        if identity is None:
            db.add(M.UserIdentity(user_id=user.id,
                                  provider=E.IdentityProvider.PASSWORD,
                                  provider_subject=email,
                                  credential_hash=encoded))
        else:
            identity.credential_hash = encoded

        held = set(db.execute(
            select(M.Role.code).join(M.UserRole, M.UserRole.role_id == M.Role.id)
            .where(M.UserRole.user_id == user.id)).scalars().all())
        for code in role_codes:
            if code not in held:
                db.add(M.UserRole(user_id=user.id, role_id=roles[code].id))

        out[label] = {"email": email, "password": password,
                      "user_id": str(user.id), "roles": list(role_codes)}

    db.flush()
    return out


def write_structural_document(path: Path) -> Path:
    """Write the synthetic DOCX the specs upload.

    Generated rather than committed: `.docx` is gitignored and CI job 8 rejects the
    extension outright, both enforcing locked 54.6. Generating it also keeps the text
    beside the mapping phrases that must match it.
    """
    import docx

    path.parent.mkdir(parents=True, exist_ok=True)
    document = docx.Document()
    for paragraph in STRUCTURAL_PARAGRAPHS:
        document.add_paragraph(paragraph)
    document.save(str(path))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true",
                        help="drop and recreate the database, then migrate")
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--document", default=".e2e/structural.docx",
                        help="where to write the synthetic STRUCTURAL document")
    args = parser.parse_args(argv)

    url = database_url()
    if args.recreate:
        recreate_database(url)
        migrate(url)

    engine = create_engine(url, future=True)
    with sessionmaker(bind=engine, future=True)() as db:
        accounts = provision(db, args.password)
        db.commit()
    engine.dispose()

    document = write_structural_document(Path(args.document).resolve())

    # stdout is the contract with Playwright's global setup.
    print(json.dumps({
        "database_url": url,
        "accounts": accounts,
        "provenance": "STRUCTURAL — carries no legal meaning (rule 21, 54.6)",
        "document": {
            "path": str(document),
            "filename": "structural.docx",
            "mime": ("application/vnd.openxmlformats-officedocument"
                     ".wordprocessingml.document"),
            "paragraphs": STRUCTURAL_PARAGRAPHS,
        },
        "configuration": STRUCTURAL_CONFIGURATION,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
