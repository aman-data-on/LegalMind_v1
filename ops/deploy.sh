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

# --- frontend ----------------------------------------------------------------
# The API was restarted above, so the stale-API preflight inside this script
# passes by construction. The script builds to staging, verifies BUILD_ID, swaps
# atomically, probes, and rolls the frontend back on failure.
say "Frontend: staged build + atomic swap"
bash frontend/scripts/deploy-frontend.sh

say "Deployed: backend and frontend, in order."
