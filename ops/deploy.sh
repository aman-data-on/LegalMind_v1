#!/usr/bin/env bash
#
# Full-stack deploy, in dependency order: BACKEND FIRST, then frontend.
#
# WHY THE ORDER IS LOAD-BEARING (2026-09-02). The API rejects any request field
# it does not recognise (schemas.Body: extra="forbid" — a deliberate control, not
# to be weakened). A frontend that sends a newly-added field therefore breaks the
# moment it is served against an API that has not been restarted: every Ask
# question returned "The request could not be validated." until the API restart.
# The reverse order is safe — an API that ACCEPTS a field no frontend sends yet
# is exactly what an optional, additive field means.
#
# Backend "deploy" here is what the architecture already is (Step 55.1): the
# systemd unit runs uvicorn straight from this working tree, so deploying the
# backend means migrate → sanity-check the import → restart → probe. There is no
# build artifact to stage, and rollback is `git checkout` + restart.
#
# Usage:  bash scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."   # repository root

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# ONE DEPLOY AT A TIME. Two overlapping deploys are not a slow deploy, they are a
# broken one: both build the frontend into the same staging directory and both
# swap it into place, so what ends up live is a mixture of two builds and the
# `.next-previous` rollback copy points at neither. Backend-side, two
# `alembic upgrade head` runs race on the version table.
#
# This became reachable on 2026-09-16, when `sudo legalmind-deploy` let a
# developer deploy without an administrator present. Before that one person
# deployed and serialisation was luck, not design. The lock is taken on the whole
# script rather than inside that wrapper so every caller is covered: the wrapper,
# an administrator running this directly, and CI.
#
# Fail rather than queue — a deploy that waits silently looks hung, and the second
# caller almost always wants to know someone else is already shipping.
exec {_deploy_lock}> /var/lock/legalmind-deploy.lock
if ! flock -n "$_deploy_lock"; then
    echo "REFUSING: another deploy is already running (/var/lock/legalmind-deploy.lock)." >&2
    echo "Wait for it to finish, then run this again." >&2
    exit 1
fi

# --- backend -----------------------------------------------------------------
say "Backend: import sanity check (a syntax error must fail HERE, not in systemd)"
(cd backend && python3 -c "import legalmind.api.app" )

say "Backend: migrations (idempotent — ops/README.md §DB)"
(
  cd backend
  # The unit's EnvironmentFile, when present, so migrations see the same
  # configuration the API loads. `if` rather than `&&`: under `set -e` a failing
  # `[ -f … ] && …` list would abort the deploy on a host with no env file.
  if [ -f /root/.legalmind.env ]; then set -a; . /root/.legalmind.env; set +a; fi
  python3 -m alembic upgrade head
)

say "Backend: restarting legalmind-api"
systemctl restart legalmind-api
for i in $(seq 1 20); do
  sleep 1
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true)"
  [[ "$code" == "200" ]] && break
done
if [[ "${code:-}" != "200" ]]; then
  echo "Backend health probe failed after restart (last: ${code:-none})." >&2
  echo "The previous process is gone — diagnose with: journalctl -u legalmind-api -n 50" >&2
  exit 1
fi
say "Backend healthy (200)"

# The worker runs the SAME code from the SAME tree, and Celery loads it once at
# startup — so without this it keeps serving the previous revision after every
# deploy, silently. Restarting it was a manual step nobody had written down
# until a deploy on 2026-09-14 needed it; a step that lives only in a person's
# head is a step that gets skipped. Restarted AFTER the API is healthy, so a
# backend that cannot start never takes the worker down with it.
say "Backend: restarting legalmind-worker"
systemctl restart legalmind-worker
for i in $(seq 1 20); do
  sleep 1
  systemctl is-active --quiet legalmind-worker && break
done
if ! systemctl is-active --quiet legalmind-worker; then
  echo "Worker failed to start after restart." >&2
  echo "Diagnose with: journalctl -u legalmind-worker -n 50" >&2
  exit 1
fi
say "Worker active"

# --- frontend ----------------------------------------------------------------
# The API was restarted above, so the stale-API preflight inside this script
# passes by construction. The script builds to staging, verifies BUILD_ID, swaps
# atomically, probes, and rolls the frontend back on failure.
say "Frontend: staged build + atomic swap"
bash frontend/scripts/deploy-frontend.sh

# --- edge --------------------------------------------------------------------
# The nginx site config is deployed FROM THE REPOSITORY, like everything else.
# Until 2026-09-22 it lived only in /etc: unversioned, unreviewed, and only
# backed up by hand into /root/nginx-legalmind.bak-*. That is how a rate limit
# meant for password guessing came to be applied to the whole /api/v1/auth/
# prefix — including the session read every page render issues — and refused
# readers at sign-in with a bare 503 for days without anyone being able to
# diff it.
#
# Test AFTER installing and roll the file back if it fails: nginx -t validates a
# whole configuration tree, not a loose file, so the candidate has to be in
# place to be checked. Nothing is live until the reload, and a reload is
# zero-downtime — old workers finish their requests.
say "Edge: nginx site config"
NGINX_SITE=/etc/nginx/sites-available/legalmind.lsnw.io
if [ -f "$NGINX_SITE" ] && ! cmp -s ops/production/nginx-legalmind.lsnw.io.conf "$NGINX_SITE"; then
  cp "$NGINX_SITE" "$NGINX_SITE.bak-$(date +%Y%m%dT%H%M%S)"
  install -m 644 ops/production/nginx-legalmind.lsnw.io.conf "$NGINX_SITE"
  if ! nginx -t; then
    cp "$(ls -t "$NGINX_SITE".bak-* | head -1)" "$NGINX_SITE"
    echo "nginx config from the repository is invalid; /etc restored, nothing reloaded." >&2
    exit 1
  fi
  systemctl reload nginx
  say "Edge: nginx reloaded"
else
  say "Edge: nginx config already current"
fi

# Static, no upstream — it is what nginx serves when an upstream is the thing
# that failed, so it cannot be fetched through the app.
install -D -m 644 ops/production/unavailable.html /usr/share/legalmind/__unavailable.html

say "Deployed: backend, frontend and edge, in order."
