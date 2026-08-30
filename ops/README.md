# LegalMind — production operations guide

**Status: 📁 DERIVED — an operator runbook. It decides nothing.** Prepared 2026-08-27.
The authoritative register of what a deployment owes is the code, not this page:

```bash
cd backend && python3 -m legalmind.deploy.preflight     # 23 checks; expect NOT READY until done
```

Every step below corresponds to a named preflight row. When you finish a step, re-run
the preflight — a row you satisfied should change, and `READY` is the finish line, not
a judgment call. ATTEST rows are things the application cannot see from inside; doing
them and *attesting* them is the operator's job, and an unexamined ATTEST is not a
pass.

---

## 1 · Database (rows: `database`, `migrations`, `database_roles`, `invariant_triggers`, `pgvector`, `assist_role`)

```sql
-- As a superuser, once per database (the app role must never hold superuser, 55.2):
CREATE EXTENSION IF NOT EXISTS vector SCHEMA extensions;

-- The restricted assist-lane role — SELECT-only on authoritative tables,
-- no INSERT/UPDATE anywhere legal/configuration data lives (AM-25 r2):
CREATE ROLE legalmind_assist LOGIN PASSWORD '<from the secret store>';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO legalmind_assist;
-- Grant write ONLY on the assist schema's own tables.
```

Then `python3 -m alembic upgrade head` as the application role. The preflight's
`assist_role` row verifies the grants for you — it FAILs if the role holds any write
grant on an authoritative table.

## 2 · Network egress (row: `egress_allow_list`)

`AM-30` t8/t10, deny-by-default:

* Document-processing services (db, queue, both workers): **no route out at all** —
  the reference `docker-compose.yml` already places them on the internal `data`
  network; reproduce that posture in the production firewall/security groups.
* `api`: outbound allowed to `generativelanguage.googleapis.com:443` **only**.
* Prove it with a network-level test from inside each service (a blocked probe from a
  worker; a permitted probe from api to the one endpoint; a blocked probe from api to
  anything else). Configuration review alone does not satisfy t8.

## 3 · TLS, cookies, edge (rows: `tls`, `cookie_flags`, `rate_limiting`)

TLS terminates at the edge with a valid certificate; the app then sets `Secure`
session cookies. Rate limiting: the in-process limiter is per-worker — a multi-worker
deployment needs the shared Redis limiter configured **and** limiting at the edge
(55.2 requires both).

## 4 · Storage, uploads, backups (rows: `encrypted_storage`, `upload_validation`, `safe_parsing`, `malware_scanning`, `backup_restore`)

Encrypted volumes for the document store and database. Malware scanning on upload is
an ATTEST integration. Backups: schedule them, and attest a **tested restore** — an
unrestored backup is a hope, not a control.

## 5 · Identity (row: `oidc`) — BLOCKED, honestly

OIDC/RIAAS needs the IdP's details and a rule-19 dependency approval; password login
is the working interim. The row stays BLOCKED until both exist — do not work around
it.

## 6 · Retention (row: `retention_policy`) — BLOCKED on an owner decision

Locked 41.26 defers the policy; log expiry must never remove auditable history
(53.6). Nothing to configure until the owner rules.

## 7 · Generation (rows: `assist_generation_gate`, `secrets`)

Follow [docs/09-implementation/GEMINI_ACTIVATION_RUNBOOK.md](../docs/09-implementation/GEMINI_ACTIVATION_RUNBOOK.md)
end to end — key in the environment (`LEGALMIND_GEMINI_API_KEY`), then
`python3 -m tools.verify_gemini_connection --environment staging --live`. The gate
row reads ATTEST while `AM-31` is CLOSED; that is correct until the owner's written
confirmation is recorded.

## 8 · Release-pipeline gates (rows: `reproducibility_gate`, `tier2_quality_gate`)

Run on every release, where the documents and model live (they are never in CI —
locked 54.6):

```bash
python3 -m tools.verify_reproducibility      # 55.4 r3 / 55.5 — must pass post-migration
python3 -m tools.verify_assist_quality       # AM-28 — blocks on a worsened wrongly-answered rate
```

## 9 · Live-instance scans (deployment pipeline, decision #143)

OpenVAS and ZAP scan a *running* staging copy — point them at staging after each
deploy there. They are deliberately not per-commit CI: CI does not stand up the full
system.

## 10 · The worker (row: `analysis_worker`)

Production analysis must run through the queue: set `LEGALMIND_BROKER_URL` (Redis) and
run the worker from the same image/version as the API — a version-skewed worker
refuses jobs by design (55.1).

---

**Order that works:** 1 → 2 → 3 → 4 → 10 → 7 → 8, with 5/6 whenever their inputs
arrive and 9 after the first staging deploy. After each: re-run the preflight.
