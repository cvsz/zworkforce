#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ZTRADER="$ROOT/apps/ztrader"
REPORT_DIR="$ZTRADER/reports/merge"
DRY_RUN="${DRY_RUN:-true}"
APPLY_DELETE_SOURCE="${APPLY_DELETE_SOURCE:-false}"
OVERWRITE_EXISTING="${OVERWRITE_EXISTING:-false}"

resolve_source_dir() {
  local candidate
  for candidate in "$@"; do
    if [ -d "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  printf '%s\n' "$1"
}

relpath() {
  local path="$1"
  printf '%s\n' "${path#$ROOT/}"
}

ABTP="$(resolve_source_dir "$ROOT/.ops/ABTPi18n" "$ROOT/.ops/backups/ABTPi18n" "$ROOT/apps/ABTPi18n")"
ZKB="$(resolve_source_dir "$ROOT/.ops/zkbtrader" "$ROOT/.ops/backups/zkbtrader" "$ROOT/apps/zkbtrader")"

list_files() {
  local src="$1"
  local out="$2"
  if [ ! -d "$src" ]; then
    : > "$out"
    return 0
  fi
  find "$(relpath "$src")" \
    \( \
      -path '*/.git/*' \
      -o -path '*/node_modules/*' \
      -o -path '*/.venv/*' \
      -o -path '*/venv/*' \
      -o -path '*/__pycache__/*' \
      -o -path '*/.pytest_cache/*' \
      -o -path '*/.ruff_cache/*' \
      -o -path '*/.mypy_cache/*' \
      -o -path '*/.vendor/*' \
    \) -prune -o -type f \
    ! -name '.env' \
    ! -name '.env.*' \
    ! -name '.coverage' \
    ! -name '*.pyc' \
    ! -name '*.pyo' \
    -print | sort > "$out"
}

diff_sources() {
  local src="$1"
  local out="$2"
  if [ ! -d "$src" ]; then
    : > "$out"
    return 0
  fi
  diff -qr \
    -x '.git' \
    -x 'node_modules' \
    -x '.venv' \
    -x 'venv' \
    -x '__pycache__' \
    -x '.pytest_cache' \
    -x '.ruff_cache' \
    -x '.mypy_cache' \
    -x '.vendor' \
    -x '.env' \
    -x '.env.*' \
    "$(relpath "$src")" apps/ztrader > "$out" 2>/dev/null || true
}

copy_dir() {
  local src="$1"
  local dst="$2"
  if [ ! -e "$src" ]; then
    echo "SKIP missing: $(relpath "$src")"
    return 0
  fi
  echo "MAP $(relpath "$src") -> $(relpath "$dst")"
  if [ "$DRY_RUN" = "true" ]; then
    return 0
  fi
  mkdir -p "$dst"
  local rsync_args=(
    -a
    --exclude '.git'
    --exclude 'node_modules'
    --exclude '.venv'
    --exclude 'venv'
    --exclude '__pycache__'
    --exclude '.pytest_cache'
    --exclude '.ruff_cache'
  )
  if [ "$OVERWRITE_EXISTING" != "true" ]; then
    rsync_args+=(--ignore-existing)
  fi
  rsync "${rsync_args[@]}" "$src"/ "$dst"/
}

copy_file() {
  local src="$1"
  local dst="$2"
  if [ ! -f "$src" ]; then
    echo "SKIP missing: $(relpath "$src")"
    return 0
  fi
  echo "MAP $(relpath "$src") -> $(relpath "$dst")"
  if [ "$DRY_RUN" = "true" ]; then
    return 0
  fi
  mkdir -p "$(dirname "$dst")"
  if [ "$OVERWRITE_EXISTING" != "true" ] && [ -f "$dst" ]; then
    echo "KEEP existing: $(relpath "$dst")"
    return 0
  fi
  cp -p "$src" "$dst"
}

write_report() {
  mkdir -p "$REPORT_DIR"
  {
    echo "# zTrader Source Merge Report"
    echo
    echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Dry run: $DRY_RUN"
    echo
    echo "## Source stacks"
    echo
    echo "- $(relpath "$ABTP")"
    echo "- $(relpath "$ZKB")"
    echo
    echo "## Target stack"
    echo
    echo "- apps/ztrader"
    echo
    echo "## Policy"
    echo
    echo "Source apps are retained by default. Set APPLY_DELETE_SOURCE=true only after validation and owner approval."
  } > "$REPORT_DIR/ztrader-source-merge-report.md"
}

main() {
  cd "$ROOT"
  mkdir -p "$REPORT_DIR"

  echo "zTrader source merge"
  echo "ROOT=$ROOT"
  echo "ABTP_SOURCE=$(relpath "$ABTP")"
  echo "ZKB_SOURCE=$(relpath "$ZKB")"
  echo "DRY_RUN=$DRY_RUN"
  echo "APPLY_DELETE_SOURCE=$APPLY_DELETE_SOURCE"
  echo "OVERWRITE_EXISTING=$OVERWRITE_EXISTING"
  echo

  list_files "$ABTP" "$REPORT_DIR/platform-files.txt"
  list_files "$ZKB" "$REPORT_DIR/market-files.txt"
  list_files "$ZTRADER" "$REPORT_DIR/ztrader-files-before.txt"
  diff_sources "$ABTP" "$REPORT_DIR/platform-vs-ztrader.diff"
  diff_sources "$ZKB" "$REPORT_DIR/market-vs-ztrader.diff"

  # Platform archive mapping
  copy_dir "$ABTP/configs" "$ZTRADER/config/integrations"
  copy_dir "$ABTP/core" "$ZTRADER/backend/src/ztrader/abt/core"
  copy_dir "$ABTP/strategies" "$ZTRADER/backend/src/ztrader/strategies/external"
  copy_dir "$ABTP/monitoring" "$ZTRADER/backend/src/ztrader/monitoring/trading"
  copy_dir "$ABTP/scripts" "$ZTRADER/scripts/integrations"
  copy_dir "$ABTP/tests" "$ZTRADER/backend/tests/integrations"
  copy_dir "$ABTP/tools" "$ZTRADER/backend/src/ztrader/abt/tools"
  copy_dir "$ABTP/apps/backend/src" "$ZTRADER/backend/src/ztrader/abt"
  copy_file "$ABTP/package.json" "$ZTRADER/merge-sources/platform/package.json"
  copy_file "$ABTP/pyproject.toml" "$ZTRADER/merge-sources/platform/pyproject.toml"
  copy_file "$ABTP/verify.sh" "$ZTRADER/scripts/integrations/verify.sh"
  copy_file "$ABTP/validate-release.sh" "$ZTRADER/scripts/integrations/validate-release.sh"
  copy_file "$ABTP/release.sh" "$ZTRADER/scripts/integrations/release.sh"

  # Market archive mapping
  copy_dir "$ZKB/src/zkbtrader" "$ZTRADER/backend/src/ztrader/market"
  copy_dir "$ZKB/src/zkbtrader.egg-info" "$ZTRADER/merge-sources/market-python-package-info"
  copy_dir "$ZKB/harness" "$ZTRADER/harness/trading"
  copy_dir "$ZKB/tests" "$ZTRADER/backend/tests/market"
  copy_dir "$ZKB/reports" "$ZTRADER/reports/trading"
  copy_dir "$ZKB/scripts" "$ZTRADER/scripts/market"
  copy_dir "$ZKB/alembic" "$ZTRADER/backend/alembic/source"
  copy_file "$ZKB/alembic.ini" "$ZTRADER/backend/alembic/source/alembic.ini"
  copy_file "$ZKB/Dockerfile.api" "$ZTRADER/merge-sources/market/Dockerfile.api"
  copy_file "$ZKB/Dockerfile.worker" "$ZTRADER/merge-sources/market/Dockerfile.worker"
  copy_file "$ZKB/pyproject.toml" "$ZTRADER/merge-sources/market/pyproject.toml"
  copy_file "$ZKB/Makefile" "$ZTRADER/merge-sources/market/Makefile"

  # Keep runtime safety default aligned with compose.
  if [ "$DRY_RUN" != "true" ]; then
    python3 - <<'PY'
from pathlib import Path
p = Path('apps/ztrader/backend/src/ztrader/core/config.py')
if p.exists():
    s = p.read_text()
    s = s.replace('GLOBAL_KILL_SWITCH: bool = False', 'GLOBAL_KILL_SWITCH: bool = True')
    p.write_text(s)
PY
  fi

  list_files "$ZTRADER" "$REPORT_DIR/ztrader-files-after.txt"
  write_report

  echo
  echo "Report directory: ${REPORT_DIR#$ROOT/}"
  echo "Next validation:"
  echo "  cd apps/ztrader"
  echo "  make validate-local"
  echo "  make merge-report"

  if [ "$APPLY_DELETE_SOURCE" = "true" ]; then
    echo "Source cleanup requested but not performed by this script. Use the final validated cleanup command in the merge plan."
  fi
}

main "$@"
