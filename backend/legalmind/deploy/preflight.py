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
