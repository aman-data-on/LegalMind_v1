---
name: local-stack
description: Run LegalMind locally end to end without touching production — scratch Postgres DB, API on a spare port, a Next.js build pointed at that API, and a real-browser check with Playwright from node. Use when asked to run, start, screenshot or click through the app, verify a change in a real browser, run the e2e/Playwright suite, or brief an agent that will do any of these.
---

# Local stack — scratch DB, API, UI, browser

Production is `:8000` (API) and `:3000` (UI) from `/root/Legalmind.v1`. Never touch them, the
deploy tree, or another session's ports/DBs. Never `pg_dump` production without the owner.

## 0. Pick your names first

- Ports: list what is taken with `ss -ltnp | grep -E ':(3|8)[0-9]{3} '`. Reserved: `8000/3000`
  production; `8399/3399` the owner's CLM test copy; `8395/3395` the CLM audit stack. Choose a
  free pair, e.g. `84NN/34NN`.
- DB: a NEW name, e.g. `legalmind_<task>_<date>`. Check `psql -lqt` first. **Never point anything
  at `legalmind_clm_e2e`, `legalmind_clm_demo`, `legalmind_v1_tier2_gate`, `legalmind_prod_rehearsal`
  or another session's DB.**

## 1. Database

Credentials come from `/root/.legalmind-test.env` (role `legalmind_test`); never copy a password
into the repo, a record or a brief — reference the file.

```bash
set -a && . /root/.legalmind-test.env && set +a          # gives the role/host
# empty DB, migrated + first accounts (prints a JSON fixture with logins):
cd <worktree>/backend
LEGALMIND_DATABASE_URL=<url-with-your-db> python3 -m tools.e2e_bootstrap --recreate
# or clone a curated DB instead of bootstrapping (dump it first if anyone writes to it):
pg_dump -Fc -d <source_db> -f <scratchpad>/src.dump && createdb <your_db> && pg_restore -d <your_db> <scratchpad>/src.dump
```

`--recreate` DROPS the target. It is safe only on a DB you just named yourself. The Playwright
suite (`npm run test:e2e`) calls `e2e_bootstrap --recreate` on `LEGALMIND_E2E_DATABASE_URL` —
**always set that variable to your own DB** (on 2026-11-06 the default collided with the curated
`legalmind_clm_e2e` and wiped it).

A fresh DB has no published standards snapshot, so no Review runs: import and publish with
`python3 -m tools.import_ratified_standards --publish --actor-email <a Department Lead login>`.

## 2. API

Copy an env file into your scratchpad and edit it — never `source /root/.legalmind.env` (it points
at the production DB). The CLM template is `/root/legalmind-clm-local/api8399.env`; change
`LEGALMIND_DATABASE_URL` to your DB and `LEGALMIND_STORAGE_ROOT`/`LEGALMIND_MAIL_SINK_DIR` to
scratch dirs. Needed only for paid-model features: export the single key line you need, after
stating the cost (paid-model guard in `.claude/rules/ask-rag.md`).

```bash
set -a && . <scratchpad>/api.env && set +a
cd <worktree>/backend && nohup python3 -m uvicorn legalmind.api.app:app \
  --host 127.0.0.1 --port <api_port> > <scratchpad>/api.log 2>&1 &
echo $! > <scratchpad>/api.pid
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:<api_port>/health
```

## 3. UI

```bash
cd <worktree>/frontend && npm ci              # not a symlinked node_modules (Turbopack fails)
LEGALMIND_NEXT_DIST=.next-<task> LEGALMIND_API_ORIGIN=http://127.0.0.1:<api_port> npx next build
grep -c 8000 .next-<task>/routes-manifest.json   # must be 0, or it proxies to production
LEGALMIND_NEXT_DIST=.next-<task> nohup npx next start --port <ui_port> > <scratchpad>/ui.log 2>&1 &
git checkout -- tsconfig.json next-env.d.ts   # the build edits them (your own worktree only)
```

Never `next build` in `/root/Legalmind.v1`. Long analysis (~90 s inline) outlives the Next dev
rewrite's ~30 s timeout: put a private nginx (`proxy_read_timeout 300s`, `/api/v1/` → API, `/` → UI)
in front and browse that port.

## 4. Browser

The Playwright MCP cannot launch Chromium as root. Use `@playwright/test` from a node script:

```js
const { chromium } = require('@playwright/test');
const browser = await chromium.launch({ args: ['--no-sandbox'] });   // or { chromiumSandbox: false }
```

Screenshots go to your scratchpad. The session cookie is `Secure`: a Python client over http must
send it as a raw `Cookie` header.

## 5. Tear down

Kill by PID (`kill $(cat <scratchpad>/api.pid)`) — `pkill -f`/`pgrep -f | kill` match your own
shell and kill it. Drop only DBs you created. Report the ports, DB name and logins you used.

## Brief template for an agent that runs the stack

> Worktree `<path>` (yours alone). DB `<name>` — created by you; never `--recreate` or write to any
> other DB (`legalmind_clm_e2e`, `legalmind_clm_demo` especially). Ports `<api>/<ui>` only; never
> `8000/3000/8399/3399`. Env: copy `<template>` to your scratchpad and change the DB URL; never
> source `/root/.legalmind.env`. Browser: node + `chromium.launch({args:['--no-sandbox']})`.
> Kill by PID. No commit, push or deploy.
