#!/usr/bin/env bash
# One FlareCheck loop tick: health + smoke. Exit non-zero on failure.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

API="${FLARECHECK_API:-http://127.0.0.1:8080}"

if ! curl -sf "$API/health" >/tmp/flarecheck_health.json; then
  echo "LOOP_TICK_FAIL api_down"
  exit 1
fi
python scripts/smoke_flarecheck.py "$API"
echo "LOOP_TICK_OK $(date -u +%Y-%m-%dT%H:%M:%SZ)"
