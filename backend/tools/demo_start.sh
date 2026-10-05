#!/usr/bin/env bash
# Demo instance for LegalMind Ask (demo mission, 2026-10-04). NOT production:
# scratch database legalmind_v1_demo, agent mode on in THIS process only, the Gemini
# key read from a private env file (never from this script).
#   backend/tools/demo_start.sh        -> API :8299, web :3299 (http://127.0.0.1:3299)
set -euo pipefail
here="$(cd "$(dirname "$0")/../.." && pwd)"
set -a
. /root/.legalmind-test.env                            # scratch DB credentials only
set +a
# The owner's paid key (2026-10-05) — the KEY LINE ONLY: sourcing that file whole points
# the database at production. Falls back to the free key when it has none.
paid="$(grep -oP '^LEGALMIND_GEMINI_API_KEY=\K.*' /root/.legalmind.env 2>/dev/null || true)"
if [ -n "$paid" ]; then
    export LEGALMIND_GEMINI_API_KEY="$paid"
else
    set -a; . /root/.legalmind/gemini-dev.env; set +a  # LEGALMIND_GEMINI_API_KEY only
fi
export LEGALMIND_DATABASE_URL="${LEGALMIND_TEST_DATABASE_URL%/*}/legalmind_v1_demo"
export LEGALMIND_STORAGE_ROOT=/root/.legalmind/demo/objects
export LEGALMIND_ENVIRONMENT=development LEGALMIND_ASK_AGENT_MODE=on \
       LEGALMIND_ASK_ATTACHMENTS=on LEGALMIND_OBLIGATIONS_EXTRACTION=off
case "$LEGALMIND_DATABASE_URL" in *legalmind_v1_demo) ;; *) echo "not the demo DB"; exit 1;; esac
cd "$here/backend"
nohup python3 -m uvicorn legalmind.api.app:app --host 127.0.0.1 --port 8299 \
    > /root/.legalmind/demo/api.log 2>&1 &
echo "api pid $!"
cd "$here/frontend"
LEGALMIND_NEXT_DIST=.next-demo LEGALMIND_API_ORIGIN=http://127.0.0.1:8299 \
    nohup npx next start --port 3299 > /root/.legalmind/demo/web.log 2>&1 &
echo "web pid $! — open http://127.0.0.1:3299 (login: /root/.legalmind/demo/login.txt)"
