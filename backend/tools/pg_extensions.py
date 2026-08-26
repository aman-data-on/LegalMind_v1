"""Best-effort pgvector provisioning for FRESH harness databases — and only those.

The `c4a91f6e2d87` migration deliberately refuses to `CREATE EXTENSION vector`: the
extension is untrusted, so creating it needs superuser, and a migration demanding that
would force the application role to hold it permanently (55.2). In deployed
environments the preflight reports the precondition and an operator satisfies it once.

Test harnesses are the one place that stance breaks down: they create BRAND-NEW
databases on every run (the e2e bootstrap, the reproducibility and invariant verifiers,
the retrieval benchmarks) or migrate into a container-fresh database (CI, where the
service image's POSTGRES_USER is a superuser by the official image's design). A fresh
database has no extension, the migration raises, and the harness dies before testing
anything — which is how the browser suite silently broke the day the migration landed
and no fresh-database run happened to follow it.

So: harnesses TRY, and losing is fine. `CREATE EXTENSION IF NOT EXISTS` succeeds
wherever the connecting role is superuser (every CI container) and is a no-op wherever
the extension already exists (the long-lived local databases). Where the role lacks the
privilege AND the extension is absent, this prints the one-time operator step and
returns False — and the migration's own error follows with the authoritative message.
Nothing here runs in production; the application never imports `tools`.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

OPERATOR_STEP = ("this role cannot create the pgvector extension (it is untrusted, "
                 "so that needs superuser). One-time operator step for this "
                 "database:  CREATE EXTENSION vector;  — or install it in template1 "
                 "so every future local database inherits it")


def ensure_vector_extension(url: str) -> bool:
    """Create pgvector in the database at ``url`` if it is absent and we may.

    Returns True when the extension is present afterwards, False when it stays
    absent (insufficient privilege, or pgvector not installed on the server).
    """
    engine = create_engine(url, isolation_level="AUTOCOMMIT", future=True)
    try:
        with engine.connect() as conn:
            if conn.execute(text(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar():
                return True
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                return True
            except Exception as exc:
                print(f"  note: {OPERATOR_STEP} ({type(exc).__name__})")
                return False
    finally:
        engine.dispose()
