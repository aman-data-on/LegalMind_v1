#!/usr/bin/env bash
#
# Set the Gemini generation credential on the SERVER and verify it end to end.
#
# WHY THIS EXISTS. On 2026-09-01 the key was set three times and worked none of
# them: once it was masked to `***` by a command written back over the env file,
# once it went into the project `.env` (which no service reads), and once it was
# read off a commented template line that had no value. Each attempt looked done.
#
# One command, the right file, and it tells you whether the provider accepts it —
# so "I set the key" and "generation works" stop being different facts.
#
# Usage:
#   bash tools/set_gemini_key.sh                 # prompts, does not echo the key
#   bash tools/set_gemini_key.sh --verify-only   # just re-check what is set
set -euo pipefail

ENV_FILE=/root/.legalmind.env
SERVICE=legalmind-api
VAR=LEGALMIND_GEMINI_API_KEY

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

if [[ "${1:-}" != "--verify-only" ]]; then
  # -s so the key never appears on screen, in the scrollback, or in shell history.
  read -rsp "Paste the Gemini API key (input hidden), then Enter: " KEY
  echo
  KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"

  if [[ -z "$KEY" ]]; then echo "Nothing entered; leaving $ENV_FILE alone." >&2; exit 1; fi
  # The same placeholder rule the application applies, so this cannot write the
  # very thing the application will refuse.
  if [[ ${#KEY} -lt 8 || "$KEY" =~ ^[*x.X_-]+$ ]]; then
    echo "That looks like a placeholder (${#KEY} chars), not a credential. Nothing written." >&2
    exit 1
  fi

  say "Writing $VAR to $ENV_FILE (mode 600)"
  if grep -q "^$VAR=" "$ENV_FILE"; then
    # A temp file + mv, never sed -i on a live secrets file: an interrupted
    # in-place edit is how a file ends up half-written.
    tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
    awk -v v="$KEY" -v n="$VAR" '$0 ~ "^" n "=" {print n "=" v; next} {print}' "$ENV_FILE" > "$tmp"
    cat "$tmp" > "$ENV_FILE"
  else
    printf '%s=%s\n' "$VAR" "$KEY" >> "$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"
  unset KEY

  say "Restarting $SERVICE"
  systemctl restart "$SERVICE"
  sleep 4
fi

say "What is actually set (shape only)"
set -a; . "$ENV_FILE"; set +a
python3 - <<'PY'
import os
from legalmind.assist.generation import is_placeholder_credential
raw = os.environ.get("LEGALMIND_GEMINI_API_KEY", "")
print(f"  length={len(raw)}  placeholder={is_placeholder_credential(raw)}")
PY

say "Preflight row"
python3 - <<'PY'
from legalmind.deploy.preflight import run_preflight
c = {r.name: r for r in run_preflight()}["generation_credential"]
print(f"  {c.status}: {c.detail[:150]}")
PY

say "Does the provider accept it, and does the model pin resolve?"
python3 -m tools.verify_gemini_connection || echo "  (see the output above — the key or the model pin is the problem)"
