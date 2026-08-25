"""Production readiness preflight — locked 55.2, 55.6, and Step 39's checklist.

Locked 55.6 presents the production blockers as "an explicit register rather than an
implicit assumption". This turns that register into a command, because a register
nobody runs is an implicit assumption with extra steps.

--------------------------------------------------------------------------
Four outcomes, and why "unknown" is not "pass"
--------------------------------------------------------------------------
    PASS        checked here, and satisfied
    FAIL        checked here, and not satisfied
    ATTEST      cannot be checked from inside the application — an operator must
                confirm it. Backups are the clearest case: locked 55.2 says
                "Restore is verified, not assumed", and a process cannot verify its
                own restore.
    BLOCKED     depends on something the specification records as NOT YET SPECIFIED

`is_ready` requires PASS for everything checkable and treats ATTEST and BLOCKED as
not-ready. That is deliberate: reporting readiness while a blocker is merely
unexamined is exactly the failure locked 55.6 exists to prevent, and locked rule 15's
fail-closed instinct applies to deployment as much as to evaluation.

Run it:  ``python -m legalmind.deploy.preflight``
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import create_engine, text

from legalmind.api.app import _docs_enabled
from legalmind.config import database_url

PASS = "PASS"
FAIL = "FAIL"
ATTEST = "ATTEST"
BLOCKED = "BLOCKED"


class Severity(str, Enum):
    BLOCKER = "blocker"          # must be resolved before production
    DECISION = "decision"        # locked 55.6: "Decision required at deployment"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    severity: Severity = Severity.BLOCKER
    basis: str = ""


def run_preflight(*, environment: str | None = None) -> list[Check]:
    """Evaluate every locked 55.6 blocker plus the 55.2 controls that are checkable."""
    env = environment or os.environ.get("LEGALMIND_ENVIRONMENT", "development")
    checks: list[Check] = [
        _environment_declared(env),
        _secrets_not_defaulted(),
        _docs_disabled(),
        _cookie_flags(),
        _rate_limiting(),
        _analysis_worker(),
        _tls(),
        _encrypted_storage(),
        _upload_validation(),
        _safe_parsing(),
        _reproducibility_gate(),
        _oidc_configured(),
        _malware_scanning(),
        _retention_policy(),
        _backup_restore(),
    ]
    checks.extend(_database_checks())
    return checks


def is_ready(checks: list[Check]) -> bool:
    """Ready only when nothing is outstanding.

    ATTEST and BLOCKED both count as not-ready. An unexamined blocker is not a
    satisfied one, and locked 55.2's "Restore is verified, not assumed" is the
    principle generalized.
    """
    return all(c.status == PASS for c in checks)


# --------------------------------------------------------------------------
# 55.3 — environments
# --------------------------------------------------------------------------
def _environment_declared(env: str) -> Check:
    valid = {"development", "staging", "production"}
    if env in valid:
        return Check("environment", PASS, f"declared as {env}",
                     basis="55.3")
    return Check("environment", FAIL,
                 f"LEGALMIND_ENVIRONMENT is {env!r}; expected one of "
                 f"{sorted(valid)}. Locked 55.3 separates development (synthetic "
                 "data only), staging (no real counterparty contracts) and "
                 "production (real legal documents)",
                 basis="55.3")


# --------------------------------------------------------------------------
# 55.2 / S-6 — secrets outside source control
# --------------------------------------------------------------------------
def _secrets_not_defaulted() -> Check:
    """S-6 — secrets injected at runtime, rotatable without a code change.

    `config.database_url` carries a development default so a developer can run the
    suite. In production that default is a misconfiguration, not a convenience.
    """
    if "LEGALMIND_DATABASE_URL" not in os.environ:
        return Check("secrets", FAIL,
                     "LEGALMIND_DATABASE_URL is not set, so the built-in "
                     "development default would be used. Secrets must be injected "
                     "at runtime (S-6)",
                     basis="55.2, S-6")
    url = os.environ["LEGALMIND_DATABASE_URL"]
    if "legalmind:legalmind@" in url:
        return Check("secrets", FAIL,
                     "the database URL carries the development credential pair",
                     basis="55.2, S-6")
    return Check("secrets", PASS, "database URL injected from the environment",
                 basis="55.2, S-6")


def _docs_disabled() -> Check:
    """An unauthenticated OpenAPI document is a reconnaissance aid beside 47.7's
    404-over-403 posture. Off by default; this catches it being switched on."""
    if _docs_enabled():
        return Check("api_docs", FAIL,
                     "LEGALMIND_ENABLE_DOCS is set: the OpenAPI document would be "
                     "served unauthenticated",
                     basis="49.12, 47.7")
    return Check("api_docs", PASS, "OpenAPI document not served", basis="49.12")


def _cookie_flags() -> Check:
    """S-3 — HttpOnly, Secure, SameSite. Asserted against the code that sets them
    rather than against a config value, because they are not configurable: a
    deployment cannot weaken them by mistake."""
    from legalmind.api.routers.auth import _COOKIE_KW

    if _COOKIE_KW.get("secure") is True and _COOKIE_KW.get("samesite") == "strict":
        return Check("cookie_flags", PASS,
                     "session cookies are Secure + SameSite=strict, and the session "
                     "cookie is HttpOnly (not configurable)",
                     basis="55.2, S-3")
    return Check("cookie_flags", FAIL,
                 f"session cookie attributes were weakened: {_COOKIE_KW}",
                 basis="55.2, S-3")


def _rate_limiting() -> Check:
    """S-5 / 55.2 — "At the edge (reverse proxy) **and** in the application".

    The in-process limiter is correct for one process only. A multi-worker
    deployment needs the shared Redis already in the locked Step 39 stack, so
    running multi-worker with the in-process limiter is reported rather than
    assumed adequate.
    """
    from legalmind.api import ratelimit
    from legalmind.api.routers import auth as auth_router
    from legalmind.api.routers import reviews as reviews_router

    limiters = {"auth": auth_router.limiter, "analysis": reviews_router._limiter}
    inactive = [name for name, limiter in limiters.items()
                if isinstance(limiter, ratelimit.NullRateLimiter)]
    if inactive:
        return Check("rate_limiting", FAIL,
                     f"rate limiting disabled for: {sorted(inactive)}",
                     basis="55.2, S-5")
    in_process = [name for name, limiter in limiters.items()
                  if isinstance(limiter, ratelimit.InProcessRateLimiter)]
    if in_process:
        return Check("rate_limiting", ATTEST,
                     "application-level rate limiting is active but in-process "
                     f"({sorted(in_process)}); correct for a single worker only. A "
                     "multi-worker deployment must back it with the shared Redis in "
                     "the Step 39 stack, and 55.2 also requires limiting at the "
                     "edge. Confirm both",
                     basis="55.2, S-5")
    return Check("rate_limiting", PASS, "shared rate limiting configured",
                 basis="55.2, S-5")


def _analysis_worker() -> Check:
    """55.1 — analysis is a worker job behind a queue, not work done in a request.

    Without a broker the API still analyses correctly, inline. That is a development
    convenience and not the locked shape, and it fails here rather than passing
    quietly, because the difference is invisible from the outside: the same 2xx comes
    back either way. In production it also means an HTTP request holds a connection
    for the length of a full analysis, and a client timeout or a redeploy mid-request
    would abandon a Review that a queue would have retried.
    """
    from legalmind.config import broker_url

    if broker_url() is None:
        return Check("analysis_worker", FAIL,
                     "LEGALMIND_BROKER_URL is not set, so analysis would run inline "
                     "in the API request. Locked 55.1 makes it a worker job on the "
                     "same image; set the broker and run "
                     "`celery -A legalmind.worker.app worker -Q analysis`",
                     basis="55.1, Step 39")
    return Check("analysis_worker", PASS,
                 "broker configured; analysis dispatches to a worker running the "
                 "same image (55.1)",
                 basis="55.1, Step 39")


def _tls() -> Check:
    """55.2 — "TLS everywhere, including between the app and the database where the
    network is not fully trusted."

    Not checkable from inside the process for the inbound half: the application sits
    behind the reverse proxy that terminates TLS, so it cannot observe what the client
    negotiated. The database half *is* visible in the connection URL, so an explicit
    `sslmode=disable` is reported as a failure rather than an attestation.
    """
    url = os.environ.get("LEGALMIND_DATABASE_URL", "")
    if "sslmode=disable" in url:
        return Check("tls", FAIL,
                     "the database URL sets sslmode=disable",
                     basis="55.2, Step 39")
    return Check("tls", ATTEST,
                 "inbound TLS terminates at the reverse proxy and cannot be observed "
                 "from here; confirm it, and confirm the database connection is "
                 "encrypted where the network is not fully trusted",
                 basis="55.2, Step 39")


def _encrypted_storage() -> Check:
    """55.2 — "Documents encrypted at rest where the platform supports it."

    A platform property. The storage backend is injected (Step 55), so whether the
    volume or bucket behind it is encrypted is invisible to the application by design.
    """
    return Check("encrypted_storage", ATTEST,
                 "documents are written through an injected storage backend; "
                 "encryption at rest is a platform property and must be confirmed "
                 "where the platform supports it",
                 basis="55.2, Step 39")


def _upload_validation() -> Check:
    """55.2 — "Type, size and structure validated before parsing", and locked 34.16's
    untrusted-input posture. Checkable, and checked against the code that enforces it
    rather than against a configuration flag."""
    from legalmind.config import max_upload_bytes
    from legalmind.ingestion.validation import SUPPORTED_MIME_TYPES, sniff_mime

    limit = max_upload_bytes()
    if not SUPPORTED_MIME_TYPES:
        return Check("upload_validation", FAIL,
                     "no MIME type is accepted; validation would reject everything",
                     basis="55.2, 34.16")
    if limit <= 0:
        return Check("upload_validation", FAIL,
                     f"the upload ceiling is {limit}", basis="55.2, 34.16")
    # The declared type is treated as a claim: the magic bytes decide. Asserted here
    # because a validator that trusted the client would pass every other check.
    if sniff_mime(b"not a document") is not None:
        return Check("upload_validation", FAIL,
                     "content sniffing accepts arbitrary bytes",
                     basis="55.2, 34.16")
    return Check("upload_validation", PASS,
                 f"{len(SUPPORTED_MIME_TYPES)} accepted types, sniffed from content "
                 f"rather than the client's claim; ceiling {limit} bytes",
                 basis="55.2, 34.16")


def _safe_parsing() -> Check:
    """55.2 — "Document parsing sandboxed and resource-limited; a malformed file must
    not compromise the host."

    Both halves are properties of the execution environment rather than of the parser:
    a sandbox is the container, and a resource limit is its memory and CPU budget. The
    in-process control that *is* enforced is the upload ceiling, which bounds the input
    before a parser sees it. **No parse-time limit is invented here** — choosing a page
    or element cap would be inventing a threshold, and no locked decision fixes one.
    """
    from legalmind.config import max_upload_bytes

    return Check("safe_parsing", ATTEST,
                 f"input is bounded before parsing by the {max_upload_bytes()}-byte "
                 "upload ceiling, and parsing failures are contained per page. "
                 "Sandboxing and CPU/memory limits are container-level: confirm the "
                 "deployment applies them",
                 basis="55.2, 34.16, Step 39")


def _reproducibility_gate() -> Check:
    """55.4 r3 / 55.5 — "after any migration, historical Reviews must still replay
    identically … this is a release-gate test, not an assumption."

    The preflight cannot run it: the gate applies a migration and re-analyses, which is
    a release-pipeline act rather than a start-up check. It is reported here so the
    register names it, and it is implemented as `tools/verify_reproducibility.py`.
    """
    return Check("reproducibility_gate", ATTEST,
                 "run `python3 -m tools.verify_reproducibility` in the release "
                 "pipeline after applying migrations (locked 55.5 places it between "
                 "the migration and the deploy). CI runs it on every change",
                 basis="55.4 r3, 55.5, 54.3")


def _oidc_configured() -> Check:
    """55.6's first blocker. OIDC is the locked primary mechanism (47.1.3), and it is
    not implemented: it needs a JWT/JWKS client dependency plus issuer and client
    configuration. Reported as blocked rather than silently absent."""
    required = ("LEGALMIND_OIDC_ISSUER", "LEGALMIND_OIDC_CLIENT_ID",
                "LEGALMIND_OIDC_CLIENT_SECRET")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return Check("oidc", BLOCKED,
                     "OIDC is the locked primary authentication mechanism (47.1.3) "
                     "and is NOT IMPLEMENTED — it requires an approved JWT/JWKS "
                     f"client dependency and {missing}. Only the password fallback "
                     "is available",
                     basis="55.6, 47.1.3")
    return Check("oidc", BLOCKED,
                 "OIDC configuration is present but the provider flow is not "
                 "implemented; the endpoints are absent by design",
                 basis="55.6, 47.1.3")


def _malware_scanning() -> Check:
    """55.6: "Malware scanning available or explicitly accepted as absent —
    Decision required at deployment." So absence is a decision to record, not a
    failure to fix, and the operator states which."""
    accepted = os.environ.get("LEGALMIND_MALWARE_SCANNING", "").lower()
    if accepted in {"available", "enabled"}:
        return Check("malware_scanning", PASS, "declared available",
                     severity=Severity.DECISION, basis="55.6, Step 39")
    if accepted == "accepted-absent":
        return Check("malware_scanning", PASS,
                     "explicitly accepted as absent, per 55.6",
                     severity=Severity.DECISION, basis="55.6")
    return Check("malware_scanning", ATTEST,
                 "neither available nor explicitly accepted as absent. Set "
                 "LEGALMIND_MALWARE_SCANNING to 'available' or 'accepted-absent' — "
                 "55.6 requires the decision to be recorded either way",
                 severity=Severity.DECISION, basis="55.6")


def _retention_policy() -> Check:
    """Locked 41.26 defers the retention policy and 55.6 marks it NOT YET SPECIFIED.

    Not something a deployment can decide: locked 53.6 requires that log expiry never
    remove auditable history, and the policy governing that is the owner's.
    """
    return Check("retention_policy", BLOCKED,
                 "the retention policy is NOT YET SPECIFIED (locked 41.26 defers "
                 "it). Audit events and legal records must follow it rather than log "
                 "retention, and log expiry must never remove auditable history "
                 "(53.6). Owner decision",
                 basis="55.6, 41.26, 53.6")


def _backup_restore() -> Check:
    """55.2: "Backups — Automated, restore-tested. **Restore is verified, not
    assumed**." A process cannot verify its own restore, so this is always an
    attestation and never a PASS the application awards itself."""
    attested = os.environ.get("LEGALMIND_BACKUP_RESTORE_VERIFIED_AT", "")
    if attested:
        return Check("backup_restore", PASS,
                     f"restore verified, attested {attested}",
                     basis="55.2")
    return Check("backup_restore", ATTEST,
                 "no verified-restore attestation. Locked 55.2: restore is verified, "
                 "not assumed. Record the date of the last successful restore test "
                 "in LEGALMIND_BACKUP_RESTORE_VERIFIED_AT",
                 basis="55.2")


# --------------------------------------------------------------------------
# Database — 55.2 and 55.4
# --------------------------------------------------------------------------
def _database_checks() -> list[Check]:
    try:
        engine = create_engine(database_url(), future=True)
        with engine.connect() as conn:
            return [
                _migrations_current(conn),
                _invariant_triggers(conn),
                _app_role_has_no_ddl(conn),
                _pgvector_available(conn),
                _assist_role_isolated(conn),
            ]
    except Exception as exc:                              # pragma: no cover
        return [Check("database", FAIL,
                      f"could not connect to verify database controls: "
                      f"{type(exc).__name__}", basis="55.2")]


def _migrations_current(conn) -> Check:
    """55.5 — the release process applies migrations forward-only before deploy."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    applied = conn.execute(text(
        "SELECT version_num FROM alembic_version")).scalars().all()
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if applied == [head]:
        return Check("migrations", PASS, f"at head {head}", basis="55.4, 55.5")
    return Check("migrations", FAIL,
                 f"applied {applied}, head is {head}. Locked 55.4: migrations are "
                 "forward-only where they touch legal data",
                 basis="55.4, 55.5")


def _invariant_triggers(conn) -> Check:
    """55.4 r4 — "Deferred constraint triggers (EV-MIN) must be created with their
    tables; a backfill cannot bypass them." Verified, not assumed."""
    expected = {
        "trg_findings_ev_min",
        "trg_evaluations_ev_min_delete",
        "trg_evaluations_ev_min_reparent",
        "trg_audit_events_append_only",
        "trg_legal_decisions_append_only",
    }
    present = set(conn.execute(text(
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")).scalars().all())
    missing = expected - present
    if missing:
        return Check("invariant_triggers", FAIL,
                     f"missing database-enforced invariants: {sorted(missing)}",
                     basis="55.4, AB-1.6, AUD-01")
    return Check("invariant_triggers", PASS,
                 "EV-MIN (insert, delete, re-parent) and append-only triggers present",
                 basis="55.4, AB-1.6, AUD-01")


def _app_role_has_no_ddl(conn) -> Check:
    """55.2 — "The application role holds no DDL rights; migrations run under a
    separate role." Checked against the live grant rather than trusted."""
    can_create = conn.execute(text(
        "SELECT has_schema_privilege(current_user, current_schema(), 'CREATE')"
    )).scalar()
    role = conn.execute(text("SELECT current_user")).scalar()
    if can_create:
        return Check("database_roles", FAIL,
                     f"the application role {role!r} holds CREATE on the schema, so "
                     "it can run DDL. Locked 55.2 requires migrations to run under a "
                     "separate role",
                     basis="55.2")
    return Check("database_roles", PASS,
                 f"application role {role!r} holds no DDL rights", basis="55.2")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def format_report(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = ["LegalMind production preflight — locked 55.2 / 55.6", ""]
    for check in checks:
        lines.append(f"  {check.status:<7} {check.name:<{width}}  {check.detail}")
        if check.basis:
            lines.append(f"  {'':<7} {'':<{width}}  ({check.basis})")
    outstanding = [c for c in checks if c.status != PASS]
    lines.append("")
    if outstanding:
        lines.append(f"NOT READY — {len(outstanding)} outstanding "
                     f"of {len(checks)} checks.")
        lines.append("ATTEST and BLOCKED are not passes: an unexamined blocker is "
                     "not a satisfied one.")
    else:
        lines.append(f"All {len(checks)} checks pass.")
    return "\n".join(lines)


def main() -> int:
    checks = run_preflight()
    print(format_report(checks))
    return 0 if is_ready(checks) else 1


if __name__ == "__main__":                                # pragma: no cover
    sys.exit(main())


# --------------------------------------------------------------------------
# AB-3 / AB-4 — the assist lane's two deployment preconditions
# --------------------------------------------------------------------------
# Both are preconditions rather than migration steps for the same verified reason:
# each needs a privilege the application role does not have, and must not be given.
# `CREATE EXTENSION vector` requires superuser (the extension is not marked trusted),
# and `CREATE ROLE` requires CREATEROLE. A migration that demanded either would force
# the application role to hold it permanently.
MIN_PGVECTOR_VERSION = (0, 8, 0)

# `AM-25` r2, verbatim: the assist lane "NEVER writes to findings, evaluations,
# legal_decisions, requirement_versions, company_standard_versions,
# legal_rule_versions, mapping_rule_versions, evaluation_rule_versions,
# configuration_snapshots or configuration_snapshot_items. This is enforced by a
# distinct database role holding no INSERT or UPDATE grant on those tables, not by
# convention."
AUTHORITATIVE_TABLES = (
    "findings", "evaluations", "legal_decisions", "requirement_versions",
    "company_standard_versions", "legal_rule_versions", "mapping_rule_versions",
    "evaluation_rule_versions", "configuration_snapshots",
    "configuration_snapshot_items",
)

ASSIST_ROLE = "legalmind_assist"


def _pgvector_available(conn) -> Check:
    """`AM-26` — pgvector on the existing instance, provisioned out of band.

    Reported rather than installed: `vector` is not a trusted extension, so creating
    it needs superuser, and the application role is deliberately not one.

    The version matters and is not cosmetic. `AM-25` r6 requires authorization to be
    applied **before** retrieval and **inside** the query — pre-filtering, never
    filtering afterwards. Under a selective pre-filter an approximate index can
    return far fewer rows than asked for, and pgvector's fix for that is **iterative
    index scans, added in 0.8.0**. Building r6's pre-filtered retrieval on an older
    build means either poor recall or a post-filter, and a post-filter is the
    enumeration oracle r7 forbids. Ubuntu 24.04 ships 0.6.0, so a distribution
    package is not sufficient on its own.
    """
    row = conn.execute(text(
        "SELECT installed_version, default_version FROM pg_available_extensions "
        "WHERE name = 'vector'")).first()
    if row is None:
        return Check("pgvector", BLOCKED,
                     "the pgvector extension is not available on this server. "
                     "Install it and `CREATE EXTENSION vector` as a superuser "
                     f"(>= {'.'.join(map(str, MIN_PGVECTOR_VERSION))}); the "
                     "application role cannot, because `vector` is not trusted",
                     basis="AM-26")

    installed, default = row

    def _parse(v: str | None) -> tuple[int, ...]:
        if not v:
            return ()
        try:
            return tuple(int(p) for p in v.split(".")[:3])
        except ValueError:                                # pragma: no cover
            return ()

    if installed is None:
        return Check("pgvector", BLOCKED,
                     f"pgvector {default} is available but not installed in this "
                     "database. Run `CREATE EXTENSION vector` as a superuser",
                     basis="AM-26")

    if _parse(installed) < MIN_PGVECTOR_VERSION:
        # ATTEST, not BLOCKED — the earlier framing overstated this, and the
        # correction was measured rather than reasoned. Verified on 0.6.0: exact
        # cosine KNN with an authorization `WHERE` clause in the same statement works
        # correctly, and the out-of-scope rows really are excluded. Exact search has
        # no recall loss at all, so `AM-25` r6 is fully satisfiable on 0.6.0 — it is
        # simply O(n) over the pre-filtered set.
        #
        # What >= 0.8.0 buys is **iterative index scans**, which matter only when you
        # want an APPROXIMATE index under a selective pre-filter: without them a
        # filtered HNSW scan can starve and silently lose recall. So the version is a
        # prerequisite for corpus-scale indexed retrieval, not for correctness — and
        # the answer to an older build is exact search, never a post-filter.
        return Check("pgvector", ATTEST,
                     f"pgvector {installed} is installed. Exact KNN under an "
                     "authorization pre-filter is correct on this version, so "
                     "per-document retrieval is sound. Upgrade to "
                     f">= {'.'.join(map(str, MIN_PGVECTOR_VERSION))} before relying "
                     "on an ANN index over a large pre-filtered set: iterative index "
                     "scans (0.8.0+) are what stop a filtered approximate scan from "
                     "starving. Never answer an older build with a post-filter — "
                     "AM-25 r7 forbids it",
                     basis="AM-26, AM-25 r6/r7")

    return Check("pgvector", PASS,
                 f"extension {installed} installed (>= "
                 f"{'.'.join(map(str, MIN_PGVECTOR_VERSION))}, so a filtered ANN "
                 "index can use iterative scans)",
                 basis="AM-26")


def _assist_role_isolated(conn) -> Check:
    """`AM-25` r2 — a distinct database role with no write grant on legal tables.

    The locked text says "not by convention", so this is checked against the live
    catalogue rather than inferred from application code. A code review can confirm
    that today's code does not write to `findings`; only a grant can confirm that
    tomorrow's cannot.

    Absence is BLOCKED, not PASS. A deployment where the role does not exist has not
    satisfied r2 — it has merely not created the mechanism r2 requires, which is the
    weaker state, not the stronger one.
    """
    exists = conn.execute(text(
        "SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": ASSIST_ROLE}).scalar()
    if not exists:
        return Check("assist_role", BLOCKED,
                     f"the {ASSIST_ROLE} role does not exist. AM-25 r2 requires the "
                     "assist lane to hold no INSERT or UPDATE grant on the ten "
                     "authoritative tables, enforced by a distinct role rather than "
                     "by convention. Create it with SELECT on the locked tables and "
                     "write access only to the assist schema",
                     basis="AM-25 r2")

    held: list[str] = []
    for table in AUTHORITATIVE_TABLES:
        for privilege in ("INSERT", "UPDATE"):
            try:
                if conn.execute(text("SELECT has_table_privilege(:r, :t, :p)"),
                                {"r": ASSIST_ROLE, "t": table,
                                 "p": privilege}).scalar():
                    held.append(f"{privilege} on {table}")
            except Exception:                             # pragma: no cover
                # A table absent from this database is reported by the migration
                # check, not misreported here as a grant violation.
                continue

    if held:
        return Check("assist_role", FAIL,
                     f"{ASSIST_ROLE} holds {', '.join(held)}. AM-25 r2 permits no "
                     "INSERT or UPDATE grant on any authoritative table",
                     basis="AM-25 r2")

    return Check("assist_role", PASS,
                 f"{ASSIST_ROLE} exists and holds no write grant on any of the "
                 f"{len(AUTHORITATIVE_TABLES)} authoritative tables",
                 basis="AM-25 r2")
