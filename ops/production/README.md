# Production configuration — state, and what is still outstanding

**Last verified 2026-09-14** against `python3 -m legalmind.deploy.preflight` on the live
host. Build state stays [IMPLEMENTATION_STATUS.md](../../docs/00-project/IMPLEMENTATION_STATUS.md)'s
alone.

**Preflight: 17 PASS · 8 ATTEST · 0 FAIL · 0 BLOCKED** (was 11 PASS · 3 FAIL · 1 BLOCKED).
Every remaining row is an attestation about the platform that the application cannot
observe from inside itself.

## What the live service runs

`legalmind-api` (uvicorn) and `legalmind-worker` (Celery) from `/root/Legalmind.v1/backend`,
`legalmind-frontend` serving `.next` from the same tree, `nginx` terminating TLS,
`redis-server` as the broker, PostgreSQL 16 with pgvector. Environment for all three
LegalMind units comes from `/root/.legalmind.env` (mode 600).

## Applied 2026-09-14

| Change | Why | Verified by |
|---|---|---|
| `LEGALMIND_ENVIRONMENT=production` | The service declared none, so it ran as `development` while serving real legal documents. | `environment` PASS. No behaviour change: the only consumer is the `AM-31` egress gate, and it is RELEASED — checked before and after. |
| **Database credential rotated** and `LEGALMIND_DATABASE_URL` injected | The built-in development default was in use, carrying the `legalmind:legalmind` pair (S-6). | `secrets` PASS. New credential authenticates; **the old one is confirmed dead**; app reads 580 findings and 7,567 chunks. |
| **Role separation** — `legalmind_migrate` owns the schema, `legalmind` holds DML only | 55.2: the application role holds no DDL. Revoking `CREATE` alone would have been cosmetic — an owner keeps full rights over what it owns. | `database_roles` PASS. Rehearsed on a restored copy first: `SELECT`/`INSERT` work, `CREATE TABLE`, `DROP findings` and `ALTER findings` all refused, and the append-only audit trigger still refuses an `UPDATE`. |
| `legalmind_assist` role | `AM-25` r2 — enforced by the catalogue, not by convention. | `assist_role` PASS. `NOLOGIN`, so no credential exists. No `INSERT`/`UPDATE` on any of the ten authoritative tables. |
| **Worker + broker** | 55.1: analysis is a worker job, not inline in the request. | `analysis_worker` PASS. Worker installed and started **before** the broker URL was set. `inspect ping` answers; it consumes `analysis` and `assist`; a dispatched task was **transported through Redis and executed in the worker process** — it logged the request id. |
| **Five security headers** in nginx | All six were absent. | Live response carries HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` — and `always` means they are present on error responses too, confirmed on a 405. |
| **Service isolation** on API and worker | Both ran as root with none. They parse attacker-supplied PDFs and shell out to OCR. | `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `PrivateDevices`, `MemoryMax=3G`, `TasksMax=512` — confirmed in force, and a real PDF still parses to 235 segments COMPLETE. |
| **Verified backup + nightly retention** | 55.2: "restore is verified, not assumed." | `backup_restore` PASS. A dump was restored into a scratch database and **12 tables matched row-for-row**. `/usr/local/sbin/legalmind-backup` runs 02:30 daily, verifies each archive, keeps 14 days; its log rotates weekly. |
| **Malware scanning: `accepted-absent`** | A decision 55.6 requires recorded either way. | `malware_scanning` PASS. Reasoning and residual risk below. |
| **Disk 85% → 67%** | 4.4 GB free was one incident from an outage. | 5 GB reclaimed from stale VS Code server versions, the npm cache and apt caches. Journal capped at 500 MB with 30-day retention (was 1.6 GB, uncapped). |

## The malware-scanning decision, and its residual risk

No scanner is installed. Installing ClamAV was assessed and **rejected on evidence**:

1. It adds a service outside the locked Step 39 stack — rule 19 puts that behind approval.
2. `freshclam` needs recurring outbound access, contradicting the locked egress allow-list
   where the API reaches exactly one endpoint and document-processing has no route out.
3. **Decisively, it does not address the actual threat.** Uploads are PDF/DOCX that are
   parsed by PyMuPDF and shelled out to tesseract, never executed and never served back as
   active content. The realistic attack is *parser exploitation*, which a signature scanner
   does not catch.

That threat was mitigated directly instead, the same day, with the service isolation above.

**Compensating controls, all verified:** content sniffed from magic bytes and required to
match the declared MIME; two accepted types only; a 25 MiB ceiling at both nginx and the
application; per-page parse containment; `nosniff`.

**Residual risk, stated plainly:** a document that exploits PyMuPDF or tesseract is not
detected before parsing. Isolation bounds the blast radius; it does not prevent the exploit.
**Follow-up:** scan at the storage or network boundary, where signature updates need no
egress from this host.

## Consequence for developers — read this before running the suite

The rotated credential means the built-in test default no longer authenticates, and the
production broker must not be visible to a test run. Both are correct, and both bite once:

```bash
set -a && . /root/.legalmind.env && set +a
unset LEGALMIND_BROKER_URL          # tests assume inline analysis; the worker uses a different DB
export LEGALMIND_TEST_DATABASE_URL="${LEGALMIND_DATABASE_URL/legalmind_v1_dev/legalmind_v1_test}"
export LEGALMIND_SOURCE_MATERIAL_DIR=/root/Legalmind.v1/legal-docs
python3 -m pytest tests -q
```

Verified 2026-09-14: **1,765 passed, 0 failed.**

## Outstanding — and who has to act

### Requires the infrastructure owner, not this host

* **Egress allow-list** (ATTEST). Allow outbound from the API to
  `generativelanguage.googleapis.com:443` only, deny-by-default elsewhere, and prove it with
  probes from inside each service. This is a firewall/security-group setting at the hosting
  provider — it cannot be set or observed from inside the machine.
* **Encryption at rest** (ATTEST). A platform property of the volume.
* **TLS confirmation** (ATTEST). The certificate, redirect, TLS 1.2/1.3-only posture and
  `certbot.timer` are all verified here; what cannot be observed from inside is whether the
  database connection is encrypted where the network is not fully trusted.
* **Off-host backup copies.** Backups exist and are verified, but only on the machine they
  protect. That is not a backup against losing the machine.

### Requires a decision, then a maintenance window

* **The deployment lives under `/root`.** That is why `ProtectHome` cannot be set and why
  both services still run as root. Relocating to `/opt/legalmind` with a dedicated
  `legalmind` system user is the real fix; it is a planned migration, not a live edit.
* **The production database is named `legalmind_v1_dev`.** Cosmetic, required by no locked
  decision, and a rename is a live-data operation.
* **Content-Security-Policy.** Deliberately not set: Next.js ships an inline bootstrap
  script, so a correct policy needs per-request nonces from the application, and a wrong
  one breaks the app silently. The next security step, and a code change rather than a
  config one.
* **pgvector 0.6.0 → 0.8.0+** before relying on an ANN index over a large pre-filtered set.
* **Rate limiting is in-process**, correct for a single worker only. A multi-worker
  deployment needs the shared Redis behind it — Redis is now running, so this is a small
  change when a second worker appears.

## Files and rollback

| Artifact | Purpose |
|---|---|
| `/root/.legalmind.env` | Live configuration, mode 600. Backups: `.bak-2026-09-14`, `.bak-pre-dbcred-*`. |
| `/root/nginx-legalmind.bak-*` | nginx config before the headers were added. |
| `/var/backups/legalmind/*.dump` | Verified dumps, mode 600, 14-day retention. |
| `ops/production/role_sep.sql` · `role_sep_rollback.sql` | The role separation and its reversal. |
| `ops/production/legalmind-worker.service` | The worker unit, installed at `/etc/systemd/system/`. |
| `/etc/systemd/system/legalmind-{api,worker}.service.d/10-hardening.conf` | Service isolation. Delete and `daemon-reload` to revert. |

**One correction worth recording.** `REASSIGN OWNED` also moves *shared* objects, so it
reassigned all 21 `legalmind*` databases cluster-wide, not just the production one's
objects. Production was and is correct; the test and scratch databases lost rights their
tooling expects, which surfaced as a failing suite. Ownership of every non-production
database was returned to `legalmind` and the suite passes. Anyone repeating this should
scope it deliberately.
