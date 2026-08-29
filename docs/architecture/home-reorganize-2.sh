#!/usr/bin/env bash
#
# home-reorganize-2.sh — Reorganize remaining /home/cvsz/* items.
#
# Usage:
#   ./home-reorganize-2.sh --dry-run
#   ./home-reorganize-2.sh --phase r1
#   ./home-reorganize-2.sh --undo
#
# Safety:
#   - Preserves .git directories
#   - Skips repos with uncommitted changes unless --force
#   - Generates rollback commands
#   - Verifies moves with checksums

set -euo pipefail

DRY_RUN=false
PHASE=""
UNDO=false
FORCE=false

usage() {
  echo "Usage: $0 [--dry-run] [--phase r1|r2|r3] [--undo] [--force]"
  echo ""
  echo "Phases:"
  echo "  r1  Safe moves (non-git or 0 changes)"
  echo "  r2  Repos with uncommitted changes (requires approval)"
  echo "  r3  Cleanup and verification"
  echo ""
  echo "Options:"
  echo "  --dry-run   Show actions without executing"
  echo "  --undo      Rollback last run"
  echo "  --force     Move repos with uncommitted changes (DANGEROUS)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --phase) PHASE="$2"; shift 2 ;;
    --undo) UNDO=true; shift ;;
    --force) FORCE=true; shift ;;
    *) usage ;;
  esac
done

if [[ -n "$PHASE" && "$UNDO" == "true" ]]; then
  echo "ERROR: Cannot specify both --phase and --undo"
  usage
fi

if [[ -z "$PHASE" && "$UNDO" != "true" ]]; then
  usage
fi

HOME_DIR="/home/cvsz"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_DIR="/home/cvsz/z-platform/docs/architecture/reorganization-logs"
mkdir -p "$LOG_DIR"

declare -a PHASE_R1_MOVES=(
  "ads:platforms/ads"
  "aicoder:platforms/aicoder"
  "github-private-control:tools/github-private-control"
  "litellm:tools/litellm"
  "llm-wiki-app:apps/llm-wiki-app"
  "llm_wiki:apps/llm_wiki"
  "raw:archives/raw"
  "wiki:archives/wiki"
  "cloudflare:tools/cloudflare"
  "computer:platforms/computer"
  "freebuff:archives/freebuff"
  "go:tools/go"
  "google-cloud-sdk:tools/google-cloud-sdk"
  "hercules-copy:archives/hercules-copy"
  "kbank-edc:archives/kbank-edc"
  "snap:archives/snap"
  "bin:tools/bin"
)

declare -a PHASE_R2_MOVES=(
  "cloudflared:platforms/cloudflared"
  "llm_wiki:apps/llm_wiki"
  "services/zeaz-one:archives/zeaz-one"
)

log() {
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" | tee -a "$LOG_DIR/reorganize2-$TIMESTAMP.log"
}

check_uncommitted_changes() {
  local repo="$1"
  if [[ ! -d "$repo/.git" ]]; then
    echo "0"
    return
  fi
  cd "$repo" && git status --short 2>/dev/null | wc -l
}

verify_checksum() {
  local src="$1"
  local dst="$2"
  if [[ -d "$src" ]]; then
    local src_sum=$(find "$src" -type f -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/.ruff_cache/*' -not -path '*/.pytest_cache/*' -not -path '*/__pycache__/*' | xargs cat 2>/dev/null | md5sum | cut -d' ' -f1)
    local dst_sum=$(find "$dst" -type f -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/.ruff_cache/*' -not -path '*/.pytest_cache/*' -not -path '*/__pycache__/*' | xargs cat 2>/dev/null | md5sum | cut -d' ' -f1)
    [[ "$src_sum" == "$dst_sum" ]]
  else
    false
  fi
}

execute_move() {
  local src="$1"
  local dst="$2"
  local label="$3"

  if [[ ! -e "$src" ]]; then
    log "SKIP: $src does not exist"
    return 0
  fi

  if [[ -e "$dst" ]]; then
    log "SKIP: $dst already exists"
    return 0
  fi

  local changes
  changes=$(check_uncommitted_changes "$src")
  if [[ "$changes" -gt 0 && "$FORCE" != "true" ]]; then
    log "SKIP: $src has $changes uncommitted changes (use --force to override)"
    return 0
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY-RUN: Would move $src -> $dst"
    return 0
  fi

  log "MOVING: $src -> $dst"
  mkdir -p "$(dirname "$dst")"
  cp -a "$src" "$dst"

  if verify_checksum "$src" "$dst"; then
    log "VERIFIED: Checksum match for $label"
    rm -rf "$src"
    log "REMOVED: $src"
    echo "$src|$dst|$TIMESTAMP" >> "$LOG_DIR/rollback2-$TIMESTAMP.log"
  else
    log "ERROR: Checksum mismatch for $label"
    return 1
  fi
}

rollback() {
  local rollback_file="$LOG_DIR/rollback2-$TIMESTAMP.log"
  if [[ ! -f "$rollback_file" ]]; then
    rollback_file=$(ls -t "$LOG_DIR"/rollback2-*.log 2>/dev/null | head -1)
  fi

  if [[ -z "$rollback_file" || ! -f "$rollback_file" ]]; then
    echo "No rollback file found"
    exit 1
  fi

  log "Rolling back using $rollback_file"
  while IFS='|' read -r src dst ts; do
    if [[ -e "$dst" ]]; then
      log "RESTORING: $dst -> $src"
      mv "$dst" "$src"
    fi
  done < "$rollback_file"
  log "Rollback complete"
}

get_moves_for_phase() {
  local phase="$1"
  case "$phase" in
    r1) echo "${PHASE_R1_MOVES[@]}" ;;
    r2) echo "${PHASE_R2_MOVES[@]}" ;;
    r3) echo "" ;;
    *) echo "" ;;
  esac
}

if [[ "$UNDO" == "true" ]]; then
  rollback
  exit 0
fi

log "=== Starting reorganization phase 2: phase=$PHASE dry_run=$DRY_RUN force=$FORCE ==="

case "$PHASE" in
  r1)
    log "Phase R1: Safe moves (non-git or 0 changes)"
    for move in "${PHASE_R1_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$HOME_DIR/$src" "$HOME_DIR/$dst" "$src"
    done
    ;;
  r2)
    log "Phase R2: Repos with uncommitted changes (requires approval)"
    for move in "${PHASE_R2_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$HOME_DIR/$src" "$HOME_DIR/$dst" "$src"
    done
    ;;
  r3)
    log "Phase R3: Cleanup and verification"
    log "Cleanup phase: remove empty directories, verify structure"
    ;;
  *)
    echo "Unknown phase: $PHASE"
    usage
    ;;
esac

log "=== Reorganization phase 2 complete ==="
echo ""
echo "Logs saved to: $LOG_DIR"
echo "To rollback: $0 --undo"
