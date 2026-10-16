# LegalMind — production operations guide


## Deploying

`bash ops/deploy.sh` — the full-stack deploy, in dependency order: backend import
sanity check → `alembic upgrade head` → restart `legalmind-api` → `/health` probe →
staged frontend build + atomic swap (`frontend/scripts/deploy-frontend.sh`).
Backend first is load-bearing: the API rejects unrecognised request fields
(`extra="forbid"`), so a frontend shipped ahead of the API breaks any request that
gained a field. The frontend script refuses that ordering on its own
(`LEGALMIND_ALLOW_STALE_API=1` overrides for a deliberate frontend-only deploy).

**Deploy from `/root/Legalmind.v1` on a clean `main`, and from nowhere else.** The
systemd units serve straight out of that one working tree, so a deploy ships whatever
is in it at that instant. On 2026-09-04 a deploy run from a tree carrying another
session's *uncommitted* Reviews/Report work put that unreviewed work in front of the
owner in production. `deploy-frontend.sh` now refuses when `src`, `public`,
`package.json`, `next.config.ts` or `backend/legalmind` carry uncommitted changes — a
deploy ships a commit, not a desk. `LEGALMIND_ALLOW_DIRTY_TREE=1` overrides it, and
wanting CI to go green is not a reason to use it.

Do feature work in your own worktree (`git worktree add`, see CLAUDE.md § *Working
alongside other sessions*) so the deploy tree stays clean and deployable.

### Deploying without an administrator — `sudo legalmind-deploy`

**Owner decision, 2026-09-16.** A developer ships their own merged work without an
administrator present for every change. Members of group `legalmind-dev` may run
exactly one command as root:

```bash
sudo legalmind-deploy       # takes no arguments, and accepts none
```

It fast-forwards `/root/Legalmind.v1` to `origin/main` and runs `ops/deploy.sh`. It
refuses a dirty deploy tree, logs the invoking account to
`/var/log/legalmind-deploy.log`, and deploys nothing but `origin/main` — the caller
cannot point it at a branch, commit, tag or directory. So the only route onto the
live site is still a reviewed pull request whose CI passed.

Its source is [production/legalmind-deploy](production/legalmind-deploy) (in the
repository since 2026-10-14). It takes the deploy lock **before** it fetches or
fast-forwards, and hands it down to `ops/deploy.sh` and `deploy-frontend.sh`
([deploy-lock.sh](deploy-lock.sh)). Installing it is an administrator's step:
`install -o root -g root -m 755 ops/production/legalmind-deploy /usr/local/sbin/`.

⚠️ **The grant's safety rests entirely on one thing: `/root/Legalmind.v1` and
`/usr/local/sbin/legalmind-deploy` are writable by root ONLY.** Anyone who can write
either can execute arbitrary code as root through it — `.git/config` alone is enough,
via `core.hooksPath`. When the grant was made, **13,480 paths in the deploy tree were
group-writable** by `legalmind-dev`, which would have turned a deploy-only rule into
full root; group write was removed in the same change. Group **read** is kept
deliberately, so a developer can still read the tree they deploy.

**Do not re-add group write to the deploy tree**, and do not widen the sudoers rule to
a directory, a wildcard or a second command. If a developer needs something else as
root, that is a new owner decision, not an edit to this one.

Rollback remains an administrator's job: `git checkout <sha>` in the deploy tree, then
`bash ops/deploy.sh`.

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

## After a deploy that changes Domain A chunking

`ops/deploy.sh` does not rebuild the position index. When `positions.CHUNKING_ALGORITHM_VERSION`
changes (last: `positions-verbatim-2`, 2026-09-18 — provenance text removed from the searchable
chunk), run once on the deployed tree:

    cd /root/Legalmind.v1/backend && python3 -m tools.chunk_standards

It is idempotent, re-chunks every ratified standard from its file and re-embeds (`embed_positions`
is called inside). Until it runs, the live index still matches on the old boilerplate.

## After a deploy that adds or changes the Constitution source model (`AM-79`)

Migration `f4c1e8a2b7d9` creates `knowledge_sources` / `knowledge_items`; `alembic upgrade head`
leaves them empty. Populate once (idempotent — an unchanged file is left alone):

    cd /root/Legalmind.v1/backend && python3 -m tools.ingest_constitution

## After a deploy that changes the Constitution version (`AM-115` — L1.11, C-25)

`ops/deploy.sh` migrates and restarts; it does **not** reload the Constitution. Until this
runs, production keeps answering from L1.10 — the pre-2023 IT Act penalties (s. 70B(7) ₹1
lakh; s. 72A three years / ₹5 lakh) — while the new code labels citations "L1.11". Run it
immediately after the deploy, from the deploy tree, with the API's own environment (as
`deploy.sh` loads it for migrations):

    cd /root/Legalmind.v1/backend && ( set -a; . /root/.legalmind.env; set +a; python3 -m tools.ingest_constitution )

Expected output: `{'source_id': '…', 'changed': True, 'items': 701, 'embedded': 404}`. It
demotes L1.10 to SUPERSEDED (effective_to 2026-10-06, its items kept as history and never
searched) and writes L1.11 as CURRENT. Idempotent: a second run prints `'changed': False`.
Verify (read-only):

    SELECT version, status, effective_to, left(file_sha256, 12) FROM assist.knowledge_sources ORDER BY effective_from;
    -- L1.5  SUPERSEDED 2026-09-13
    -- L1.10 SUPERSEDED 2026-10-06 d53c0a6eebd9
    -- L1.11 CURRENT    (null)     5b4e645ba0bd

Rehearsed 2026-10-06 on a scratch copy of the same starting state (L1.10 CURRENT, 701 items,
migration head `a9e4c2f7b1d3` — the state production was read to be in, read-only, that day):
retrieval benchmark identical before and after. **Rollback** (only together with reverting
the code): `UPDATE assist.knowledge_sources SET status = 'CURRENT', effective_to = NULL
WHERE version = 'L1.10'; DELETE FROM assist.knowledge_sources WHERE version = 'L1.11';`
(cascades to L1.11's items) — the L1.10 items were never deleted.

## After the deploy of AB-74 (`AM-129` L1.12, `AM-130` published policies)

Three steps, from the deploy tree, with the API's own environment. Until they run, Ask
answers from L1.11 (10/25/50 SLA credits, 30-day claim window) and has no published
policies, while the evaluator still holds the 2026-09-08 standards.

1. The Constitution — demotes L1.11, writes L1.12 CURRENT (idempotent):

       cd /root/Legalmind.v1/backend && ( set -a; . /root/.legalmind.env; set +a; python3 -m tools.ingest_constitution )

2. The published policies — first load from the copies read on 2026-10-09 (no network), then
   install the daily refresh:

       cd /root/Legalmind.v1/backend && ( set -a; . /root/.legalmind.env; set +a; python3 -m tools.refresh_published_policies --from /root/Legalmind.v1/legal-docs/published/2026-10-09 )
       sudo cp /root/Legalmind.v1/ops/production/legalmind-published-policies.{service,timer} /etc/systemd/system/
       sudo systemctl daemon-reload && sudo systemctl enable --now legalmind-published-policies.timer
       sudo systemctl start legalmind-published-policies.service && journalctl -u legalmind-published-policies -n 12

   Expected: eight lines, `CHANGED` on the first load, `unchanged` on the fetch after it.
   A line with an error leaves that policy's last version answering; nothing else is affected.

3. The three standards (`CLAIM-WINDOW-SLA-001` 60 days, `DATA-RETRIEVAL-TOS-001` 7 days,
   `LATE-FEE-TOS-001` 5%) — import and publish as every standard change is, with the
   ops-publish account. Reviews already run keep their snapshots (rule 16). **Then
   rebuild Ask's position index, or Ask keeps quoting the old 30 days / 30 days / 2%**
   (found in the 2026-10-09 rehearsal):

       cd /root/Legalmind.v1/backend && ( set -a; . /root/.legalmind.env; set +a; python3 -m tools.chunk_standards )

Verify (read-only):

    SELECT source_type, version, status FROM assist.knowledge_sources ORDER BY source_type, effective_from;
    -- COMPANY_CONSTITUTION L1.11 SUPERSEDED · L1.12 CURRENT · PUBLISHED_<DOC>_<BRAND> ×8 CURRENT

**Rollback** (with the code): `systemctl disable --now legalmind-published-policies.timer`;
`DELETE FROM assist.knowledge_sources WHERE source_type LIKE 'PUBLISHED_%' OR version = 'L1.12';`
`UPDATE assist.knowledge_sources SET status = 'CURRENT', effective_to = NULL WHERE version = 'L1.11';`
and re-import the three standards from the previous commit.

## After the deploy of AB-92 (`AM-151`–`AM-154` — clause polarity, pillars, two angles)

**There is no schema migration in this release.** The CATEGORICAL location validator's only
schema change — the enum value in migration `a3c8e1f5d7b9` — shipped with AB-91 (PR #210) and is
already applied in production. Everything AB-92 adds is configuration inside existing JSONB
(`nli_hypothesis`, `waiver_patterns`, `waiver_conditions`, `breadth_patterns`,
`breadth_scope`, `breadth_negatives`, `commercial_pillar`, `requires_fixed_term`) and string values in existing JSONB result fields (`WAIVED`,
`TOO_BROAD`, `WORKING_DAYS`). The NLI safety restatement (`nli_hypothesis`) is read only by
the tripwire and is never shown, stored as a finding or sent to a model.

1. Deploy as usual — `sudo legalmind-deploy`. `ops/deploy.sh` still runs
   `alembic upgrade head`, which is a no-op here. Confirm the version did not move
   (read-only):

       SELECT version_num FROM alembic_version;   -- a3c8e1f5d7b9, unchanged

2. Import and publish the standards with the ops-publish account (73 active, unchanged
   count; 18 files carry new versions). Until this runs, production keeps reviewing with
   snapshot `e437ea04` and none of the new behaviour is live:

       cd /root/Legalmind.v1/backend && ( set -a; . /root/.legalmind.env; set +a; \
         python3 -m tools.import_ratified_standards --actor-email ops-publish@leapswitch.com && \
         python3 -m tools.publish_payload -o /root/publish-73.json )
       # then POST /api/v1/configuration/publish with /root/publish-73.json, signed in as
       # ops-publish (credentials in /root/.legalmind-publish.env, never printed)

3. Rebuild Ask's position index so Ask quotes the new versions:

       cd /root/Legalmind.v1/backend && ( set -a; . /root/.legalmind.env; set +a; python3 -m tools.chunk_standards )

4. Optional: `LEGALMIND_REVIEW_MODEL=deepseek|bonsai` in `/root/.legalmind.env` and restart
   `legalmind-api` and `legalmind-worker`. Default `gemini` needs nothing.

5. Smoke test: `GET /api/v1/reviews/{id}/angles` on any Review returns 200 with `commercial`,
   `business`, `legal` and `counter_proposals`. Reviews already run keep their snapshot
   (rule 16); a document must be re-analysed (or re-uploaded) to be read by the new
   standards.

**Container rollout (`docker-compose.yml`).** The same steps inside the running `api`
container: `docker compose build && docker compose up -d`, then
`docker compose exec api python -m alembic upgrade head` (a no-op, as above),
`docker compose exec api python -m tools.import_ratified_standards --actor-email
ops-publish@leapswitch.com`, `docker compose exec api python -m tools.publish_payload -o
/tmp/publish-73.json` (publish that file's codes as in step 2), and
`docker compose exec api python -m tools.chunk_standards`. The NLI tripwire needs the NLI
weights, provisioned on the HOST with `tools.provision_model` and mounted read-only at
`LEGALMIND_MODEL_DIR` (never downloaded inside a container); without them the tripwire is
skipped and the selected model's verdict stands alone, as on any host with no models.

**Rollback:** redeploy the previous commit and re-import + publish its standards; no data to
undo.

## After a deploy that changes the statute chunker (`AM-80`, `section-4`)

Migration `a7d3e9b1c5f2` adds `statutes.status` and backfills it. The corpus itself is
re-chunked only by the ingest tool — until it runs, production still serves the old
chunks. Run once; it prints one line per Act, and an Act failing integrity is REFUSED
(expected today: the Income-tax Act 1961 print):

    cd /root/Legalmind.v1/backend && python3 -m tools.ingest_statutes

Citations recorded against old chunks are re-pointed by text (`_replace_statute_chunks`).

## After a deploy that adds Constitution retrieval records (`AM-82`)

Migration `b8e2f6a4d1c3` adds `knowledge_items.breadcrumb` and `knowledge_item_embeddings`.
`tools.ingest_constitution` writes both, but skips an unchanged Constitution file — so
where the source model was ingested BEFORE this migration, delete the L1.10 source row
(`DELETE FROM <assist>.knowledge_sources WHERE version = 'L1.10'`, cascading to its items)
and re-run the tool. Nothing cites a knowledge item yet, so nothing is lost.

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

**Backups are implemented and documented in
[production/README.md](production/README.md#backups-and-disaster-recovery)**: local 14 days
(plaintext, fast recovery) plus off-server 90 days (GPG AES-256 before upload) to the private
CloudPe bucket `legalmind-production-backups` in `S3-INWEST2`, run nightly at 02:30 by
`production/backup.sh` with `production/s3_object.py`. Since 2026-10-16 the run also backs up the
**uploaded documents** (`/var/lib/legalmind/documents`, outside the database) the same way, every
file hash-checked against its name. Restore was verified end to end on 2026-09-14 and again on
2026-10-16 — database and documents — into scratch copies. The off-server upload is **credential-gated** and those
credentials are still outstanding — see that document for the exact variable names.

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

> **Installed and verified 2026-09-14** (this note said "not installed" until
> 2026-09-29 — stale): the unit at
> [`production/legalmind-worker.service`](production/legalmind-worker.service) runs, a
> dispatched task was transported through Redis and executed in the worker, and the
> broker URL was set only after that. Keep that order on any new host: the worker
> BEFORE `LEGALMIND_BROKER_URL`, or every analysis enqueues with nothing consuming it.
> Current production configuration: [`production/README.md`](production/README.md).

Production analysis must run through the queue: set `LEGALMIND_BROKER_URL` (Redis) and
run the worker from the same image/version as the API — a version-skewed worker
refuses jobs by design (55.1).

---

**Order that works:** 1 → 2 → 3 → 4 → 10 → 7 → 8, with 5/6 whenever their inputs
arrive and 9 after the first staging deploy. After each: re-run the preflight.
