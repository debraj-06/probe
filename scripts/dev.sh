#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PROBE — start every process needed for a full local run.
#
#   ./scripts/dev.sh              API + web dashboard + demo shop
#   ./scripts/dev.sh --no-demo    API + web only (inspect a real URL)
#   ./scripts/dev.sh --mock       force the built-in simulator (no Chromium)
#
# Ports: API 8000 · dashboard 5173 · demo shop 5174
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

START_DEMO=1
BROWSER_MODE="${PROBE_BROWSER_MODE:-auto}"

for arg in "$@"; do
  case "$arg" in
    --no-demo) START_DEMO=0 ;;
    --mock)    BROWSER_MODE="mock" ;;
    -h|--help)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

# pnpm and uv are usually installed per-user, so make sure they are on PATH.
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"

log()  { printf '\033[1;36m▶\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

PIDS=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${PIDS[@]:-}"; do
    [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  log "all processes stopped"
}
trap cleanup INT TERM EXIT

# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------
command -v pnpm >/dev/null || die "pnpm not found — npm i -g pnpm"
command -v uv   >/dev/null || die "uv not found — https://docs.astral.sh/uv/"

if [ ! -d "$ROOT/services/api/.venv" ]; then
  log "installing backend dependencies"
  (cd "$ROOT/services/api" && uv sync)
fi

if [ ! -d "$ROOT/apps/web/node_modules" ] || [ ! -d "$ROOT/demoshop/node_modules" ]; then
  log "installing frontend dependencies"
  pnpm install || warn "pnpm install reported errors — continuing (esbuild ships prebuilt)"
fi

if [ "$BROWSER_MODE" != "mock" ] && [ ! -d "$HOME/.cache/ms-playwright" ]; then
  warn "no Playwright browsers found — installing Chromium"
  (cd "$ROOT/services/api" && uv run playwright install chromium) \
    || warn "Chromium install failed; PROBE will fall back to the simulator"
fi

[ -f "$ROOT/.env" ] || { cp "$ROOT/.env.example" "$ROOT/.env"; log "created .env from .env.example"; }

# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
log "starting API on http://127.0.0.1:8000"
(cd "$ROOT/services/api" && PROBE_BROWSER_MODE="$BROWSER_MODE" uv run uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 --log-level info >"$ROOT/data/api.log" 2>&1) &
PIDS+=($!)

# --------------------------------------------------------------------------
# dashboard
# --------------------------------------------------------------------------
log "starting dashboard on http://127.0.0.1:5173"
(cd "$ROOT/apps/web" && pnpm dev >"$ROOT/data/web.log" 2>&1) &
PIDS+=($!)

# --------------------------------------------------------------------------
# demo shop (the app PROBE inspects)
# --------------------------------------------------------------------------
if [ "$START_DEMO" = "1" ]; then
  log "starting demo shop on http://127.0.0.1:5174"
  (cd "$ROOT/demoshop" && pnpm dev >"$ROOT/data/demoshop.log" 2>&1) &
  PIDS+=($!)
fi

# --------------------------------------------------------------------------
# wait for the API, then print the playbook
# --------------------------------------------------------------------------
log "waiting for the API to come up"
for _ in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 0.5
done

if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  log "API healthy — $(curl -s http://127.0.0.1:8000/api/health)"
else
  warn "API did not answer — see data/api.log"
fi

cat <<EOF

$(printf '\033[1m')  PROBE is running$(printf '\033[0m')

  dashboard   http://127.0.0.1:5173
  API docs    http://127.0.0.1:8000/docs
$(if [ "$START_DEMO" = "1" ]; then printf '  demo shop  http://127.0.0.1:5174   (inspect this one)\n'; fi)

  browser mode: $BROWSER_MODE
  logs:         data/{api,web$(if [ "$START_DEMO" = "1" ]; then printf ',demoshop'; fi)}.log

  Ctrl-C stops everything.

EOF

wait
