#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PROBE — pack the source tree into a small archive you can copy elsewhere.
#
#   ./scripts/package.sh                 # probe-<version>.tar.gz
#   ./scripts/package.sh --with-data     # also bundle past inspection results
#
# Everything that can be regenerated is left out: node_modules, .venv, build
# output, caches and runtime data. The result is a few hundred kilobytes.
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WITH_DATA=0
for arg in "$@"; do
  case "$arg" in
    --with-data) WITH_DATA=1 ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

VERSION="$(python3 -c "import json;print(json.load(open('package.json'))['version'])" 2>/dev/null || echo dev)"
OUT="${ROOT}/probe-${VERSION}.tar.gz"

EXCLUDES=(
  --exclude='*/node_modules'
  --exclude='*/.venv'
  --exclude='*/dist'
  --exclude='*/__pycache__'
  --exclude='*/.pytest_cache'
  --exclude='*/.ruff_cache'
  --exclude='*/.mypy_cache'
  --exclude='*.pyc'
  --exclude='*.tsbuildinfo'
  --exclude='.env'
  --exclude='*.log'
  --exclude='probe-*.tar.gz'
)

if [ "$WITH_DATA" = "0" ]; then
  EXCLUDES+=( --exclude='services/api/data' )
fi

# stop the servers first so nothing is mid-write
if [ -f /tmp/probe-running ]; then :; fi

tar -czf "$OUT" "${EXCLUDES[@]}" \
  README.md ARCHITECTURE.md .env.example .gitignore \
  package.json pnpm-lock.yaml pnpm-workspace.yaml \
  apps demoshop services scripts

SIZE="$(du -h "$OUT" | cut -f1)"
FILES="$(tar -tzf "$OUT" | grep -vc '/$')"

printf '\n\033[1;32m✓\033[0m %s\n' "$OUT"
printf '  %s · %s files\n' "$SIZE" "$FILES"
printf '\n  On the other machine:\n'
printf '    tar -xzf %s && cd probe\n' "$(basename "$OUT")"
printf '    ./scripts/dev.sh\n\n'
