# Production configuration — state, and what is still outstanding

**Recorded 2026-09-14.** Measured against `python3 -m legalmind.deploy.preflight` on the
live host, not inferred. Build state stays
[IMPLEMENTATION_STATUS.md](../../docs/00-project/IMPLEMENTATION_STATUS.md)'s alone.

## What the live service actually runs

`legalmind-api.service` → `uvicorn` from `/root/Legalmind.v1/backend`, environment from
`/root/.legalmind.env` (mode 600, backed up to `/root/.legalmind.env.bak-2026-09-14`).
`legalmind-frontend.service` serves `.next` from the same tree.

## Applied 2026-09-14

| Change | Why | Verification |
|---|---|---|
| `LEGALMIND_ENVIRONMENT=production` | The service declared none, so it ran as `development` while serving real legal documents — locked 55.3's separation was not in force. | Preflight `environment` BLOCKED → PASS. No runtime behaviour changed: the only consumer is the `AM-31` egress gate, and that gate is RELEASED, confirmed before the restart. |
| `legalmind_assist` PostgreSQL role | `AM-25` r2 requires the assist lane's inability to write legal tables to be enforced by the catalogue, "not by convention". | Preflight `assist_role` BLOCKED → PASS. Holds SELECT on `public`, full DML on `assist`, and **no INSERT or UPDATE on any of the ten authoritative tables** — asserted table by table. `NOLOGIN`, so it creates no credential. |
| `redis-server` enabled and started | Installed but inactive; it is the locked Step 39 broker. | `redis-cli ping` → PONG. Listening on `127.0.0.1:6379` and `[::1]` only, `protected-mode yes` — no credential, because it is not reachable off-host. |
| Verified backup + restore | Locked 55.2: "restore is verified, not assumed." | `pg_dump -Fc` of the live database (21 MB, 429 archive entries) restored into a scratch database; **12 tables matched row-for-row across both schemas**, including `findings` (580) and `assist.chunks` (7,567). Scratch database dropped; the live database was never written to. Recorded in `LEGALMIND_BACKUP_RESTORE_VERIFIED_AT`. |

Preflight moved from **11 PASS / 1 BLOCKED / 3 FAIL** to **13 PASS / 0 BLOCKED / 3 FAIL**.

## Outstanding — and who has to act

### 1. `analysis_worker` (FAIL) — analysis runs inline in the API request

Everything is prepared: Redis runs, Celery 5.6.3 is installed, and the unit file is
[`legalmind-worker.service`](legalmind-worker.service) in this directory. Installing a
new always-on system service needs an operator.

**Order matters** — install and start the worker FIRST, confirm it is consuming, and only
then add `LEGALMIND_BROKER_URL=redis://127.0.0.1:6379/0` and restart the API. Reversed,
every analysis enqueues and nothing runs it.

```bash
sudo cp ops/production/legalmind-worker.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now legalmind-worker
systemctl status legalmind-worker --no-pager            # must be active
sudo -u root celery -A legalmind.worker.app inspect ping    # must answer
# only now:
echo 'LEGALMIND_BROKER_URL=redis://127.0.0.1:6379/0' | sudo tee -a /root/.legalmind.env
sudo systemctl restart legalmind-api
# then upload one document and confirm the Review acquires Findings.
```

Rollback: remove the `LEGALMIND_BROKER_URL` line, `systemctl restart legalmind-api` —
the API returns to inline analysis immediately.

### 2. `secrets` (FAIL) — the database URL is not injected

`LEGALMIND_DATABASE_URL` is unset, so the built-in development default is used and the
live data sits in a database named `legalmind_v1_dev`. The check also refuses the
`legalmind:legalmind` credential pair, so **setting the variable is not enough** — the
role needs a real password. That is a secret rotation and an owner decision.

Two separable questions, and the first does not require the second:

* **Set a password on the `legalmind` role and inject the URL.** Closes the check.
  Requires a brief API restart and the password never entering chat.
* **Rename the database to something not called `_dev`.** Cosmetic, and a live-data
  operation. Not required by any locked decision; recommended only for clarity.

### 3. `database_roles` (FAIL) — the application role can run DDL

`legalmind` holds CREATE on both schemas **and owns all 49 tables**, so revoking schema
CREATE alone would make the check pass while the role could still `ALTER`/`DROP` what it
owns. Reporting that plainly rather than taking the cosmetic win: satisfying 55.2
honestly means a separate owner/migration role, which is a planned maintenance operation.

### 4. Nine ATTEST rows — operator sign-off

TLS termination, encryption at rest, parsing sandbox limits, the egress allow-list,
in-process rate limiting (single-worker only), pgvector 0.6.0's ANN caveat, and the two
release-pipeline gates (`verify_reproducibility`, `verify_assist_quality`). Each is a
statement about the platform that the application cannot observe from inside itself.
`malware_scanning` needs only a recorded decision: set `LEGALMIND_MALWARE_SCANNING` to
`available` or `accepted-absent`.

## Not a blocker, contrary to an earlier report

**OIDC is configured and working.** Provider is Google; the redirect URI is registered
and validated; six accounts have signed in through SSO, most recently 2026-09-11. An
earlier report listed it as blocking; that was an error made by reading the code path
instead of running the check.

## Housekeeping

Disk is at **85%** (4.4 GB free). The backup directory is `/var/backups/legalmind`
(mode 700, dumps mode 600) and is **not yet rotated or scheduled** — one verified dump
exists. Scheduling and off-host copies are outstanding.
