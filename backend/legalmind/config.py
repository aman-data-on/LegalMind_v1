"""Runtime configuration. Secrets come from the environment, never source (S-6)."""

from __future__ import annotations

import os
from pathlib import Path


def database_url() -> str:
    return os.environ.get(
        "LEGALMIND_DATABASE_URL",
        "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_dev",
    )


def test_database_url() -> str:
    return os.environ.get(
        "LEGALMIND_TEST_DATABASE_URL",
        "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_test",
    )


def assist_schema() -> str:
    """The database schema holding the assist-lane tables — locked `AM-27` r1.

    `AM-27` r1: *"Assist-lane tables live in a database schema separate from the
    locked tables."* This is a **name**, not a toggle: there is no mode in which the
    assist tables share a schema with the locked ones.

    Configurable for one specific reason. The test harness builds the locked tables
    in a private per-process schema (``t_<epoch>_<random>``, the `F-4` isolation
    fix), and a hardcoded ``assist`` would put every concurrent run's assist tables
    in one shared schema — reintroducing exactly the cross-run collision `F-4`
    fixed. `conftest` therefore derives ``<run_schema>_assist`` per run. Production
    uses the default and never sets this.
    """
    return os.environ.get("LEGALMIND_ASSIST_SCHEMA", "assist")


def storage_root() -> str:
    """Local write-once document store.

    Production uses S3-compatible object storage (locked Step 39); the backend is
    injected, so which one is a deployment choice (Step 55) rather than a code
    change.
    """
    return os.environ.get("LEGALMIND_STORAGE_ROOT", "/var/lib/legalmind/documents")


def source_material_dir() -> str:
    """Where the organization's own legal source documents live (untracked).

    Locked 54.6: *"golden fixtures use synthetic or cleared contract text. Real
    counterparty contracts do not enter the repository."* Owner ruling 2026-08-19:
    the documents live INSIDE the project at ``legal-docs/`` for convenience, but
    the directory is gitignored and must never be tracked — "the repository" means
    version control, and nothing sensitive is ever committed.
    ``tests/test_source_material.py`` enforces both halves.

    Absence is normal and must never be an error: CI has no source material and the
    document-level corpus fixtures skip when it is missing. A missing directory
    means "those fixtures cannot run here", never "evaluate with less material".

    Owner ruling, 2026-08-18: the six documents named in CLAUDE.md § Source material
    are the ONLY source material for this project. Other document collections exist
    elsewhere on this machine and belong to a different project; do not read from
    them or use them to populate this directory.
    """
    return os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR",
                          str(Path(__file__).resolve().parents[2] / "legal-docs"))


def environment() -> str:
    """Which of locked 55.3's three environments this process is running as.

    Not a security control on its own — every check that matters is enforced in code
    regardless — but the preflight reports against it, and 55.3's separation (real
    contracts never leave production) is stated in terms of it.
    """
    return os.environ.get("LEGALMIND_ENVIRONMENT", "development")


def broker_url() -> str | None:
    """The Celery broker — locked Step 39 (Celery + Redis) and locked 55.1.

    ``None`` means no queue is configured, and analysis then runs **inline in the
    request** instead of as a worker job. That is a development convenience and is
    not the locked deployment shape: 55.1's diagram has a worker behind a queue, so
    the production preflight fails a deployment configured this way rather than
    letting an inline fallback pass silently.
    """
    return os.environ.get("LEGALMIND_BROKER_URL") or None


def queue_enabled() -> bool:
    return broker_url() is not None


def analysis_time_limit_seconds() -> int:
    """Hard ceiling on one analysis job.

    An operational guard, not a specified value: nothing locked fixes a duration.
    It exists because a pathological document must not hold a worker slot for ever,
    and because a job killed by the time limit rolls its transaction back — so the
    Review returns to its pre-analysis state rather than being left half-analysed.
    """
    return int(os.environ.get("LEGALMIND_ANALYSIS_TIME_LIMIT", 30 * 60))


def max_upload_bytes() -> int:
    """Upload size ceiling — locked 34.16 (untrusted input) and Step 39's
    upload-validation checklist item. A deployment limit, not a specified one."""
    return int(os.environ.get("LEGALMIND_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))


# ──────────────────────────────────────────────────────────────────────────
# OIDC — Step 47 §47.1.3 / OD-9, "corporate SSO via OIDC is primary"
# ──────────────────────────────────────────────────────────────────────────
# The provider and its client registration are a DEPLOYMENT prerequisite
# (locked 55.6's first blocker), which is why they are read from the
# environment and nothing here carries a default that would work. There is no
# fallback issuer on purpose: a mistyped variable must disable SSO, never
# silently authenticate against somewhere else.
#
# S-6 — the client secret is a secret and lives only in the environment.


def oidc_issuer() -> str | None:
    """The IdP's issuer identifier, e.g. ``https://accounts.google.com``.

    Discovery is performed against ``<issuer>/.well-known/openid-configuration``
    and the document's own ``issuer`` must equal this value, so a wrong host
    fails rather than being trusted.
    """
    return os.environ.get("LEGALMIND_OIDC_ISSUER") or None


def oidc_client_id() -> str | None:
    return os.environ.get("LEGALMIND_OIDC_CLIENT_ID") or None


def oidc_client_secret() -> str | None:
    return os.environ.get("LEGALMIND_OIDC_CLIENT_SECRET") or None


def oidc_redirect_uri() -> str | None:
    """Must match the value registered with the IdP **byte for byte**.

    Not derived from the inbound request: `Host` is attacker-controllable, and a
    redirect_uri built from it is the classic way an authorization code is
    delivered somewhere else.
    """
    return os.environ.get("LEGALMIND_OIDC_REDIRECT_URI") or None


def oidc_allowed_domain() -> str | None:
    """Restrict sign-in to one email domain — a corporate-SSO deployment control.

    Google's ``hd`` claim is *advisory*; this is enforced against the verified
    email address server-side as well. ``None`` means no domain restriction, in
    which case the account-must-already-exist rule is the only gate.
    """
    value = os.environ.get("LEGALMIND_OIDC_ALLOWED_DOMAIN", "").strip().lower()
    return value.lstrip("@") or None


# Must stay equal to where the password path sends a signed-in user
# (`frontend/src/app/login/page.tsx`'s `router.push`). The two mechanisms landing
# in different places would be a bug nobody notices until SSO is the primary one.
POST_LOGIN_PATH_DEFAULT = "/documents"


def oidc_post_login_path() -> str:
    """Where a successful SSO sign-in lands. A path, never a full URL — an
    open redirect is not a feature we are adding to the login flow."""
    path = os.environ.get("LEGALMIND_OIDC_POST_LOGIN_PATH",
                          POST_LOGIN_PATH_DEFAULT)
    if path.startswith("/") and not path.startswith("//"):
        return path
    return POST_LOGIN_PATH_DEFAULT


def oidc_configured() -> bool:
    """All four required values present. Checked before the routes do anything,
    and reported by the deployment preflight (55.6)."""
    return all((oidc_issuer(), oidc_client_id(), oidc_client_secret(),
                oidc_redirect_uri()))


# JIT provisioning — owner instruction, 2026-09-01.
#
# ⚠️ This REVERSES implementation decision 262 of the same day, which had refused
# to auto-create accounts. The owner asked for JIT explicitly, and no locked
# decision forbids it: `all_lock.md`'s Step 47 record locks the session model, the
# identity contract and S-7, but says nothing about who may create a User row.
# (`tools/dev_account.py` cites "locked 47.1.3 r3 — LegalMind never
# self-provisions"; §47.1.3 has no r3 and no such sentence. That mis-citation is
# reported, not relied on.)
#
# What DOES still bind, and shapes the default below: locked Step 23's role
# summary, `SEC-02`/`ROLE-05` (no super-role reaches `legal.decision`), and S-8.
# So a provisioned account gets ROLE_USER — ordinary contract and review work, and
# none of `legal.decision`, `legal_position.view`, `user.manage` or `audit.view`.
# An identity provider must never be able to hand out legal authority.
JIT_ROLES_DEFAULT = "USER"


def oidc_jit_roles() -> tuple[str, ...]:
    """Roles granted to an account created on first SSO sign-in.

    ``DISABLED`` turns JIT off entirely and restores the refuse-unknown-identity
    behaviour. An empty value provisions the account with **no** roles, which is
    the most conservative form that still creates the user: they can sign in and
    see nothing until an administrator grants something.
    """
    raw = os.environ.get("LEGALMIND_OIDC_JIT_ROLES", JIT_ROLES_DEFAULT).strip()
    if raw.upper() == "DISABLED":
        return ()
    return tuple(code.strip().upper() for code in raw.split(",") if code.strip())


def oidc_jit_enabled() -> bool:
    return os.environ.get("LEGALMIND_OIDC_JIT_ROLES",
                          JIT_ROLES_DEFAULT).strip().upper() != "DISABLED"
