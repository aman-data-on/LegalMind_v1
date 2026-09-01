"""Production preflight — locked 55.2, 55.6, 55.4.

The rule under test is that **"unknown" is never reported as "ready"**. Locked 55.6
presents the production blockers as "an explicit register rather than an implicit
assumption", and locked 55.2 says of backups that "Restore is verified, not assumed".
A preflight that awarded itself a pass for anything it could not check would recreate
the assumption the register exists to remove.
"""

from __future__ import annotations

import pytest

from legalmind.deploy.preflight import (
    ATTEST,
    BLOCKED,
    FAIL,
    PASS,
    Check,
    Severity,
    format_report,
    is_ready,
    run_preflight,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Each test states its own environment, so none inherits the developer's."""
    for name in ("LEGALMIND_ENVIRONMENT", "LEGALMIND_DATABASE_URL",
                 "LEGALMIND_ENABLE_DOCS", "LEGALMIND_OIDC_ISSUER",
                 "LEGALMIND_OIDC_CLIENT_ID", "LEGALMIND_OIDC_CLIENT_SECRET",
                 "LEGALMIND_MALWARE_SCANNING", "LEGALMIND_BROKER_URL",
                 "LEGALMIND_BACKUP_RESTORE_VERIFIED_AT"):
        monkeypatch.delenv(name, raising=False)


def by_name(checks):
    return {c.name: c for c in checks}


# =====================================================================
# The governing rule
# =====================================================================
def test_unknown_is_never_ready():
    """ATTEST and BLOCKED both count as not-ready.

    This is the whole point of the module. An operator reading "ready" while a
    blocker sits unexamined is precisely what locked 55.6 replaces.
    """
    for status in (ATTEST, BLOCKED, FAIL):
        assert is_ready([Check("x", PASS, ""), Check("y", status, "")]) is False
    assert is_ready([Check("x", PASS, ""), Check("y", PASS, "")]) is True


def test_a_development_checkout_is_not_production_ready():
    checks = run_preflight()
    assert is_ready(checks) is False
    # And the report says so in as many words, rather than listing green ticks.
    report = format_report(checks)
    assert "NOT READY" in report
    assert "an unexamined blocker is not a satisfied one" in report


# =====================================================================
# 55.2 / S-6 — secrets
# =====================================================================
def test_an_unset_database_url_is_a_failure():
    """S-6 — secrets injected at runtime. The development default existing for
    convenience must not silently become a production credential."""
    assert by_name(run_preflight())["secrets"].status == FAIL


def test_the_development_credential_pair_is_rejected(monkeypatch):
    monkeypatch.setenv("LEGALMIND_DATABASE_URL",
                       "postgresql+psycopg2://legalmind:legalmind@db/legalmind")
    check = by_name(run_preflight())["secrets"]
    assert check.status == FAIL
    assert "development credential" in check.detail


def test_an_injected_url_passes(monkeypatch):
    monkeypatch.setenv("LEGALMIND_DATABASE_URL",
                       "postgresql+psycopg2://app:from-vault@db/legalmind")
    assert by_name(run_preflight())["secrets"].status == PASS


# =====================================================================
# 47.7 / 49.12 — the schema document
# =====================================================================
def test_serving_the_openapi_document_is_a_failure(monkeypatch):
    """An unauthenticated schema document sits oddly beside 47.7's 404-over-403
    posture, so switching it on is caught rather than assumed intentional."""
    monkeypatch.setenv("LEGALMIND_ENABLE_DOCS", "1")
    assert by_name(run_preflight())["api_docs"].status == FAIL


# =====================================================================
# S-3 — cookie flags are not weakenable by configuration
# =====================================================================
def test_cookie_flags_pass_because_they_are_not_configurable():
    check = by_name(run_preflight())["cookie_flags"]
    assert check.status == PASS
    assert "not configurable" in check.detail


def test_weakened_cookie_flags_would_be_caught(monkeypatch):
    """Guards the guard: if a future change made the flags configurable and someone
    turned Secure off, the preflight must fail rather than keep passing."""
    from legalmind.api.routers import auth as auth_router

    monkeypatch.setitem(auth_router._COOKIE_KW, "secure", False)
    assert by_name(run_preflight())["cookie_flags"].status == FAIL


# =====================================================================
# S-5 / 55.2 — rate limiting
# =====================================================================
def test_in_process_rate_limiting_is_an_attestation_not_a_pass():
    """55.2 requires limiting "at the edge (reverse proxy) **and** in the
    application". The in-process limiter is correct for one worker only, and the
    edge cannot be verified from here — so this is ATTEST, never PASS."""
    check = by_name(run_preflight())["rate_limiting"]
    assert check.status == ATTEST
    assert "in-process" in check.detail
    assert "edge" in check.detail


def test_disabled_rate_limiting_is_a_failure(monkeypatch):
    from legalmind.api import ratelimit
    from legalmind.api.routers import auth as auth_router

    monkeypatch.setattr(auth_router, "limiter", ratelimit.NullRateLimiter())
    check = by_name(run_preflight())["rate_limiting"]
    assert check.status == FAIL
    assert "auth" in check.detail


# =====================================================================
# 55.6 — the blockers that are not ours to close
# =====================================================================
def test_oidc_is_blocked_when_unconfigured():
    """BLOCKED, because it is not ours to close: the flow is implemented (2026-09-01)
    but 47.1.3's primary mechanism needs the deployment's own IdP registration,
    which is locked 55.6's first blocker."""
    check = by_name(run_preflight())["oidc"]
    assert check.status == BLOCKED
    assert "NOT CONFIGURED" in check.detail


def _configure_oidc(monkeypatch, redirect="https://x.example/api/v1/auth/oidc/callback"):
    monkeypatch.setenv("LEGALMIND_OIDC_ISSUER", "https://accounts.google.com")
    monkeypatch.setenv("LEGALMIND_OIDC_CLIENT_ID", "cid")
    monkeypatch.setenv("LEGALMIND_OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("LEGALMIND_OIDC_REDIRECT_URI", redirect)


def test_oidc_passes_once_the_deployment_configures_it(monkeypatch):
    _configure_oidc(monkeypatch)
    assert by_name(run_preflight())["oidc"].status == PASS


def test_oidc_without_a_domain_restriction_says_so(monkeypatch):
    """Not a failure — no domain restriction is a legitimate deployment choice, and
    the account-must-already-exist rule still gates it. But the operator must be
    told, because it is the difference between "our staff" and "anyone with a
    Google account for whom an admin happened to create a user"."""
    _configure_oidc(monkeypatch)
    monkeypatch.delenv("LEGALMIND_OIDC_ALLOWED_DOMAIN", raising=False)
    detail = by_name(run_preflight())["oidc"].detail
    assert "NO email-domain restriction" in detail
    assert "no just-in-time provisioning" in detail


def test_oidc_refuses_a_plaintext_redirect_uri(monkeypatch):
    """The authorization code is delivered to this URL. Over http it is disclosed."""
    _configure_oidc(monkeypatch, redirect="http://x.example/api/v1/auth/oidc/callback")
    assert by_name(run_preflight())["oidc"].status == FAIL


def test_oidc_refuses_a_redirect_uri_that_is_not_the_served_route(monkeypatch):
    """A redirect URI that does not match the route we serve means every sign-in
    404s at the IdP's callback — caught before deployment, not after."""
    _configure_oidc(monkeypatch, redirect="https://x.example/auth/callback")
    assert by_name(run_preflight())["oidc"].status == FAIL


def test_retention_policy_is_blocked_on_the_owner():
    """Locked 41.26 defers it; 53.6 requires that log expiry never remove auditable
    history. Not a deployment choice."""
    check = by_name(run_preflight())["retention_policy"]
    assert check.status == BLOCKED
    assert "NOT YET SPECIFIED" in check.detail


def test_malware_scanning_is_a_recorded_decision(monkeypatch):
    """55.6: "available or explicitly accepted as absent — Decision required at
    deployment." Absence is a decision to record, not a defect to fix — but it must
    be recorded, so silence is ATTEST."""
    check = by_name(run_preflight())["malware_scanning"]
    assert check.status == ATTEST
    assert check.severity is Severity.DECISION

    monkeypatch.setenv("LEGALMIND_MALWARE_SCANNING", "accepted-absent")
    accepted = by_name(run_preflight())["malware_scanning"]
    assert accepted.status == PASS
    assert "accepted as absent" in accepted.detail


def test_backup_restore_is_always_an_attestation_until_declared(monkeypatch):
    """55.2 — "Restore is verified, not assumed." A process cannot verify its own
    restore, so the application never awards itself this pass."""
    check = by_name(run_preflight())["backup_restore"]
    assert check.status == ATTEST
    assert "not assumed" in check.detail

    monkeypatch.setenv("LEGALMIND_BACKUP_RESTORE_VERIFIED_AT", "2026-08-17")
    assert by_name(run_preflight())["backup_restore"].status == PASS


# =====================================================================
# 55.4 — database controls, verified rather than trusted
# =====================================================================
def test_invariant_triggers_are_verified_not_assumed(db):
    """55.4 r4 — "Deferred constraint triggers (EV-MIN) must be created with their
    tables; a backfill cannot bypass them." Includes the `F-1` removal-path
    triggers, so a regression that dropped them would fail the preflight."""
    checks = by_name(run_preflight())
    if "invariant_triggers" not in checks:      # no database reachable
        pytest.skip("database not reachable from this environment")
    check = checks["invariant_triggers"]
    assert check.status == PASS
    assert "delete" in check.detail and "re-parent" in check.detail


def test_migrations_must_be_at_head(db):
    checks = by_name(run_preflight())
    if "migrations" not in checks:
        pytest.skip("database not reachable from this environment")
    assert checks["migrations"].status == PASS


def test_environment_must_be_declared(monkeypatch):
    monkeypatch.setenv("LEGALMIND_ENVIRONMENT", "prod")     # not one of the three
    check = by_name(run_preflight())["environment"]
    assert check.status == FAIL
    assert "55.3" in check.basis

    monkeypatch.setenv("LEGALMIND_ENVIRONMENT", "production")
    assert by_name(run_preflight())["environment"].status == PASS


def test_every_check_cites_its_basis():
    """A blocker without a citation is folklore. Each must name the locked rule it
    enforces, so a reader can check the preflight against the specification."""
    for check in run_preflight():
        assert check.basis, check.name


# =====================================================================
# 55.2's remaining checklist rows, and 55.4 r3's release gate
# =====================================================================
def test_tls_is_an_attestation_but_a_disabled_database_ssl_is_a_failure(monkeypatch):
    """55.2 — "TLS everywhere, including between the app and the database where the
    network is not fully trusted."

    The inbound half terminates at the reverse proxy and is invisible from here; the
    database half is visible in the URL, so switching it off is caught rather than
    attested away.
    """
    assert by_name(run_preflight())["tls"].status == ATTEST

    monkeypatch.setenv("LEGALMIND_DATABASE_URL",
                       "postgresql+psycopg2://app:x@db/legalmind?sslmode=disable")
    check = by_name(run_preflight())["tls"]
    assert check.status == FAIL
    assert "sslmode=disable" in check.detail


def test_upload_validation_is_checked_against_the_validator(monkeypatch):
    """55.2 / 34.16 — "type, size and structure validated before parsing", asserted
    against the code that enforces it rather than a configuration flag. The declared
    type is a claim; the magic bytes decide."""
    check = by_name(run_preflight())["upload_validation"]
    assert check.status == PASS
    assert "rather than the client's claim" in check.detail

    monkeypatch.setenv("LEGALMIND_MAX_UPLOAD_BYTES", "0")
    assert by_name(run_preflight())["upload_validation"].status == FAIL


def test_safe_parsing_invents_no_limit(monkeypatch):
    """55.2 — "parsing sandboxed and resource-limited".

    Both halves are properties of the execution environment, so this is an attestation
    naming the in-process bound that does exist (the upload ceiling). **No parse-time
    page or element cap is invented**: no locked decision fixes one, and choosing a
    number would be inventing a threshold.
    """
    check = by_name(run_preflight())["safe_parsing"]
    assert check.status == ATTEST
    assert "upload ceiling" in check.detail
    assert "container-level" in check.detail


def test_encrypted_storage_is_a_platform_attestation():
    check = by_name(run_preflight())["encrypted_storage"]
    assert check.status == ATTEST
    assert check.basis.startswith("55.2")


def test_the_register_names_the_reproducibility_gate():
    """55.4 r3 / 55.5 — the gate is a release-pipeline act, not a start-up check, so
    the preflight names it rather than pretending to run it. `is_ready` still counts it
    as outstanding, which is the point: an unexamined gate is not a satisfied one."""
    check = by_name(run_preflight())["reproducibility_gate"]
    assert check.status == ATTEST
    assert "tools.verify_reproducibility" in check.detail
    assert "55.4 r3" in check.basis


def test_the_register_names_the_tier2_quality_gate():
    """`AM-28`'s gate is a release-pipeline act for the same reason the
    reproducibility gate is: it needs the source documents and the model, both of
    which 54.6 keeps out of the repository and CI. The register names the runner and
    is honest that the faithfulness half stays unmeasurable while AM-31 is closed."""
    check = by_name(run_preflight())["tier2_quality_gate"]
    assert check.status == ATTEST
    assert "tools.verify_assist_quality" in check.detail
    assert "wrongly-answered" in check.detail
    assert "AM-28" in check.basis
    assert "AM-31 m4" in check.basis


def test_the_register_names_the_egress_allow_list():
    """`AM-30` t8 — the allow-list is network infrastructure the application cannot
    inspect, and t8 itself says the posture is asserted by a network-level test, not
    by configuration review. So the row is ATTEST — the register may never award
    itself a PASS for a firewall it cannot see."""
    check = by_name(run_preflight())["egress_allow_list"]
    assert check.status == ATTEST
    assert "generativelanguage.googleapis.com" in check.detail
    assert "deny-by-default" in check.detail
    assert "AM-30 t8" in check.basis
