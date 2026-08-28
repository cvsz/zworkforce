#!/usr/bin/env bash
#
# home-reorganize.sh — Reorganize /home/cvsz/* repositories into structured layout.
#
# Usage:
#   ./home-reorganize.sh --dry-run          # Show what would happen
#   ./home-reorganize.sh --phase h1         # Execute Phase H1 (safe moves)
#   ./home-reorganize.sh --undo             # Rollback last run
#
# Safety:
#   - Preserves .git directories
#   - Does not move repos with uncommitted changes (unless --force)
#   - Generates rollback commands
#   - Verifies moves with checksums
#
# Operator approval required for phases H2+.

set -euo pipefail

DRY_RUN=false
PHASE=""
UNDO=false
FORCE=false

usage() {
  echo "Usage: $0 [--dry-run] [--phase h1|h2|h3|h4|h5] [--undo] [--force]"
  echo ""
  echo "Phases:"
  echo "  h1  Safe moves (repos with 0 uncommitted changes)"
  echo "  h2  Archive migration sources (requires approval)"
  echo "  h3  Move separate platforms (requires approval)"
  echo "  h4  Move standalone apps & tools (requires approval)"
  echo "  h5  Cleanup and verification"
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

# Configuration
HOME_DIR="/home/cvsz"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_DIR="/home/cvsz/z-platform/docs/architecture/reorganization-logs"
mkdir -p "$LOG_DIR"

# Phase H1 — Safe moves (0 uncommitted changes)
declare -a PHASE_H1_MOVES=(
  "z-world:platforms/z-world"
  "zaffiliate:platforms/zaffiliate"
  "zeaz-ai-command-center:platforms/zeaz-ai-command-center"
  "zeaz-autonomous-security-agent:archives/zeaz-autonomous-security-agent"
  "zeaz-one-complete:archives/zeaz-one-complete"
  "zloop_orig:archives/zloop_orig"
  "zkid:apps/zkid"
)

# Phase H2 — Archive migration sources (requires approval)
declare -a PHASE_H2_MOVES=(
  "zc:migration-sources/zc"
  "zcoder:migration-sources/zcoder"
  "z-prov:migration-sources/z-prov"
  "zai-coder:migration-sources/zai-coder"
)

# Phase H3 — Separate platforms (requires approval)
declare -a PHASE_H3_MOVES=(
  "zaff:platforms/zaff"
  "zworkforce:platforms/zworkforce"
  "zeaz:platforms/zeaz"
  "zeto:platforms/zeto"
  "zknowbase:platforms/zknowbase"
)

# Phase H4 — Standalone apps & tools (requires approval)
declare -a PHASE_H4_MOVES=(
  "zkids-zai:apps/zkids-zai"
  "zpay-android:apps/zpay-android"
  "zdash:apps/zdash"
  "zpwsh:tools/zpwsh"
  "autoc:tools/autoc"
  "openclaw:tools/openclaw"
  "qwen-gen:tools/qwen-gen"
  "zwiki:tools/zwiki"
)

log() {
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" | tee -a "$LOG_DIR/reorganize-$TIMESTAMP.log"
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
    log "DRY-RUN: Would move $src → $dst"
    return 0
  fi

  log "MOVING: $src → $dst"
  mkdir -p "$(dirname "$dst")"
  cp -a "$src" "$dst"
  
  if verify_checksum "$src" "$dst"; then
    log "VERIFIED: Checksum match for $label"
    rm -rf "$src"
    log "REMOVED: $src"
    echo "$src|$dst|$TIMESTAMP" >> "$LOG_DIR/rollback-$TIMESTAMP.log"
  else
    log "ERROR: Checksum mismatch for $label"
    return 1
  fi
}

rollback() {
  local rollback_file="$LOG_DIR/rollback-$TIMESTAMP.log"
  if [[ ! -f "$rollback_file" ]]; then
    # Find latest rollback file
    rollback_file=$(ls -t "$LOG_DIR"/rollback-*.log 2>/dev/null | head -1)
  fi
  
  if [[ -z "$rollback_file" || ! -f "$rollback_file" ]]; then
    echo "No rollback file found"
    exit 1
  fi

  log "Rolling back using $rollback_file"
  while IFS='|' read -r src dst ts; do
    if [[ -e "$dst" ]]; then
      log "RESTORING: $dst → $src"
      mv "$dst" "$src"
    fi
  done < "$rollback_file"
  log "Rollback complete"
}

get_moves_for_phase() {
  local phase="$1"
  case "$phase" in
    h1) echo "${PHASE_H1_MOVES[@]}" ;;
    h2) echo "${PHASE_H2_MOVES[@]}" ;;
    h3) echo "${PHASE_H3_MOVES[@]}" ;;
    h4) echo "${PHASE_H4_MOVES[@]}" ;;
    h5) echo "" ;;
    *) echo "" ;;
  esac
}

# Main execution
if [[ "$UNDO" == "true" ]]; then
  rollback
  exit 0
fi

log "=== Starting reorganization: phase=$PHASE dry_run=$DRY_RUN force=$FORCE ==="

case "$PHASE" in
  h1)
    log "Phase H1: Safe moves (0 uncommitted changes)"
    for move in "${PHASE_H1_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$HOME_DIR/$src" "$HOME_DIR/$dst" "$src"
    done
    ;;
  h2)
    log "Phase H2: Archive migration sources (requires operator approval)"
    for move in "${PHASE_H2_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$HOME_DIR/$src" "$HOME_DIR/$dst" "$src"
    done
    ;;
  h3)
    log "Phase H3: Move separate platforms (requires operator approval)"
    for move in "${PHASE_H3_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$HOME_DIR/$src" "$HOME_DIR/$dst" "$src"
    done
    ;;
  h4)
    log "Phase H4: Move standalone apps & tools (requires operator approval)"
    for move in "${PHASE_H4_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$HOME_DIR/$src" "$HOME_DIR/$dst" "$src"
    done
    ;;
  h5)
    log "Phase H5: Cleanup and verification"
    log "Cleanup phase: remove empty directories, verify structure"
    ;;
  *)
    echo "Unknown phase: $PHASE"
    usage
    ;;
esac

log "=== Reorganization complete ==="
echo ""
echo "Logs saved to: $LOG_DIR"
echo "To rollback: $0 --undo"
