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
    upload-validation checklist item. A deployment limit, not a specified one.
    Default lowered 50 → 25 MB on owner instruction, 2026-09-02."""
    return int(os.environ.get("LEGALMIND_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))


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
#
# ⚠️ That is exactly what happened on 2026-09-01: the Documents page was renamed
# to Dashboard, `router.push("/dashboard")` was updated, and THIS was not — so a
# Google sign-in landed on a 404 while password login worked fine. `/documents`
# returned 404 on the live site and nothing failed loudly.
# `tests/test_oidc.py::test_the_post_login_path_points_at_a_route_that_exists`
# now compares this against the frontend's own route directory.
POST_LOGIN_PATH_DEFAULT = "/dashboard"


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
# An identity provider must never be able to hand out legal authority — and since
# AB-12 r11 that is ENFORCED in `security.oidc._provision`, not merely hoped: a
# configured JIT role carrying legal authority or platform administration
# (`permissions.NEVER_PROVISIONED_BY_IDP`) is refused at provisioning time.
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


def capability_route_enabled() -> bool:
    """Whether the `AM-68` capability question route is live. ON since 2026-09-15.

    `AM-68` was approved that day, with the owner choosing option (b): the manifest is
    rendered directly and no generation call is made. The route was built behind this
    flag while the amendment was pending and is now on by default.

    The flag stays rather than being deleted, because it is the rollback: the route can
    be turned off with an environment variable and a restart, without a deploy. Set
    `LEGALMIND_CAPABILITY_ROUTE=off` to return to searching the corpora for a question
    about the product.
    """
    value = os.environ.get("LEGALMIND_CAPABILITY_ROUTE", "on")
    return value.lower() in {"1", "true", "on"}


def position_synthesis_enabled() -> bool:
    """Whether `AM-67`'s Domain A reading aid is live. OFF by default.

    `AM-67` r7 is a PREREQUISITE, not a preference: 8 of the 40 ratified standards
    carried a counterparty note and 24 an environment path inside `source_document`,
    composed into the chunk text. Egressing those would breach `AM-30` t4 and t5 on the
    first call. The record forbids enabling r1 in any environment until THAT
    environment's position corpus has been re-chunked and verified locator-free.

    A deploy does not satisfy that — a re-chunk does, and it is a separate operation on
    live data. So this stays off until an operator turns it on, after running
    `tools.chunk_standards` and confirming zero locators. `positions.screen_for_egress`
    is the second line: even with this on, a chunk carrying a locator is refused rather
    than sent.
    """
    value = os.environ.get("LEGALMIND_POSITION_SYNTHESIS", "")
    return value.lower() in {"1", "true", "on"}


def general_knowledge_generation_enabled() -> bool:
    """Whether a general-knowledge question may be ANSWERED by the model. OFF.

    `AM-25` r5: "No answer reaches a user unless every claim in it resolves to retrieved
    evidence." A general explanation of what an NDA is resolves to no retrieved evidence
    at all — it is the model's own knowledge — so generating one is exactly what r5
    forbids. That is a locked safety decision and it is not mine to set aside.

    What ships without it: the question is recognised and NOT answered from Company
    Standards, which is the defect. The reader is told plainly what this system can and
    cannot answer instead of being handed three unrelated standards.

    Turning this on requires the amendment drafted as `AM-72` (renumbered from
    `AM-71`, which is now the locked `AB-23` record on retired standards).
    """
    value = os.environ.get("LEGALMIND_GENERAL_KNOWLEDGE", "")
    return value.lower() in {"1", "true", "on"}


def query_planner_enabled() -> bool:
    """Whether a question is PLANNED before retrieval — `assist/planner.py`. OFF.

    One provider call that returns what the question is about (a Constitution Appendix-B
    topic, a subject, up to three reformulated search phrases). It aims retrieval; it
    decides nothing: routing, the comparison screen, the gate and every guardrail run
    exactly as without it, and on any failure the plan is None and retrieval is the
    pre-planner path. The payload is the question and the prior questions `AM-58`
    already admits — a subset of what generation sends.

    OFF by default after measurement (2026-09-17, ratified 77-question set, production
    path, 75 of 77 questions planned): the call takes 2.4–8.0 s from this provider and
    the ask's total p50 went 5.9 s → 10.6 s (p95 13.4 → 17.1 s), Gemini calls per question
    1.23 → 2.25, while MRR (0.701 → 0.728), gold@3 (0.797 → 0.828) and hit@1 (0.594 →
    0.609) each moved by about one question of 64 — inside the rescue's run-to-run swing —
    and the share of gold chunks handed to generation FELL (0.390 → 0.358) as the
    reformulations widened the evidence. The
    plans themselves are accurate — topic right in every spot check, reformulations a
    lawyer would use — but by design they cannot open the gate (`AM-25`'s calibrated
    refusal decides on the question's own scores), so on this corpus they buy ranking
    at best, and they did not. Wrongly-answered (1/13) and faithfulness (1.0) held.

    `LEGALMIND_QUERY_PLANNER=on` enables it — a restart, no deploy — for an environment
    with a faster planner, or once the reranker exists to make use of the wider
    candidate pool. The Tier-2 gate records the flag in its pipeline block so a
    planner-off run is never compared against a planner-on bar.
    """
    value = os.environ.get("LEGALMIND_QUERY_PLANNER", "off")
    return value.lower() in {"1", "true", "on"}


def evidence_rescue_enabled() -> bool:
    """Whether a gate refusal gets a second look from the model. OFF by default.

    Measured 2026-09-16: the gate refuses 21 of 64 answerable questions and 15 of those
    already have the gold chunk retrieved, so recall 0.625 could reach 0.859 by fixing
    the decision alone. No threshold, no second similarity feature and no alternative
    embedding model separates those 15 from the 13 genuinely unanswerable questions —
    all three were measured, and `assist/rescue.py` records the numbers.

    ON since 2026-09-16, on the owner's approval after the measurement below.

    Measured against the ratified 77-question set with the real model, calling the
    judge on the 33 questions the gate refuses:

        baseline   retained 43/64   recall 0.625   wrongly answered 1/13
        rescued    13 correct        0 wrongly opened
        result     recall 0.828      wrongly answered 1/13 — UNCHANGED

    The judge refused all twelve genuinely unanswerable questions it was shown, which
    is the property that matters: the owner's 2026-09-14 rule is that recall may only
    improve WITHOUT a rise in wrongly-answered, and this is the first lever measured
    that does it.

    The flag stays as the rollback: `LEGALMIND_EVIDENCE_RESCUE=off` restores the
    pre-rescue behaviour with a restart and no deploy. One extra provider call per
    REFUSED question — roughly a third of questions, none on the answered path.
    """
    value = os.environ.get("LEGALMIND_EVIDENCE_RESCUE", "on")
    return value.lower() in {"1", "true", "on"}
