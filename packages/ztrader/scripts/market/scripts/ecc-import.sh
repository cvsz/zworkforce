#!/usr/bin/env bash
set -Eeuo pipefail

# Safe local-only importer for affaan-m/ECC.
# This script clones or updates ECC under .vendor/ECC and does not commit ECC source.

ECC_REPO_URL="${ECC_REPO_URL:-https://github.com/affaan-m/ECC.git}"
ECC_REF="${ECC_REF:-main}"
ECC_DIR="${ECC_DIR:-.vendor/ECC}"
REPORT_DIR="${REPORT_DIR:-reports/ecc}"
DRY_RUN="${DRY_RUN:-0}"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
}

run() {
  log "+ $*"
  if [[ "$DRY_RUN" != "1" ]]; then
    "$@"
  fi
}

require_clean_worktree() {
  if [[ "${ALLOW_DIRTY:-0}" == "1" ]]; then
    return
  fi
  if ! git diff --quiet || ! git diff --cached --quiet; then
    log "ERROR: worktree has uncommitted changes. Commit/stash first or set ALLOW_DIRTY=1."
    git status --short
    exit 1
  fi
}

main() {
  log "ECC safe import starting"
  log "repo=$ECC_REPO_URL ref=$ECC_REF dir=$ECC_DIR dry_run=$DRY_RUN"

  command -v git >/dev/null 2>&1 || { log "ERROR: git missing"; exit 1; }
  require_clean_worktree

  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY RUN: no clone, fetch, checkout, pull, or report writes will be performed."
    if [[ -d "$ECC_DIR/.git" ]]; then
      log "Existing local ECC clone detected."
      git -C "$ECC_DIR" remote get-url origin || true
      git -C "$ECC_DIR" rev-parse --abbrev-ref HEAD || true
      git -C "$ECC_DIR" rev-parse HEAD || true
    else
      log "No local ECC clone found at $ECC_DIR."
    fi
    exit 0
  fi

  mkdir -p "$(dirname "$ECC_DIR")" "$REPORT_DIR"

  if [[ -d "$ECC_DIR/.git" ]]; then
    run git -C "$ECC_DIR" fetch --tags --prune origin
  else
    run git clone --filter=blob:none "$ECC_REPO_URL" "$ECC_DIR"
  fi

  run git -C "$ECC_DIR" checkout "$ECC_REF"
  run git -C "$ECC_DIR" pull --ff-only origin "$ECC_REF" || true

  ECC_SHA="$(git -C "$ECC_DIR" rev-parse HEAD)"
  ECC_BRANCH="$(git -C "$ECC_DIR" rev-parse --abbrev-ref HEAD)"
  ECC_REMOTE="$(git -C "$ECC_DIR" remote get-url origin)"

  cat > "$REPORT_DIR/ecc-lock.json" <<JSON
{
  "repository": "$ECC_REMOTE",
  "ref": "$ECC_REF",
  "branch": "$ECC_BRANCH",
  "commit": "$ECC_SHA",
  "local_dir": "$ECC_DIR",
  "import_mode": "local-only clone; source is ignored by git",
  "license": "MIT",
  "updated_at": "$(date -Is)"
}
JSON

  cat > "$REPORT_DIR/ecc-summary.txt" <<TXT
ECC local import complete.

Repository: $ECC_REMOTE
Ref:        $ECC_REF
Branch:     $ECC_BRANCH
Commit:     $ECC_SHA
Local dir:  $ECC_DIR

This project intentionally keeps ECC source local-only. Do not commit .vendor/ECC.
TXT

  log "ECC import complete: $ECC_SHA"
  log "Report: $REPORT_DIR/ecc-lock.json"
}

main "$@"
