#!/usr/bin/env bash
#
# home-reorganize-3.sh — Reorganize remaining loose files in /home/cvsz/.
#
# Usage:
#   ./home-reorganize-3.sh --dry-run
#   ./home-reorganize-3.sh --phase f1
#   ./home-reorganize-3.sh --undo
#
# Safety:
#   - Skips sensitive key material unless --cleanse-secrets is explicitly set
#   - Generates rollback commands
#   - Verifies copies with checksums

set -euo pipefail

DRY_RUN=false
PHASE=""
UNDO=false
FORCE=false
CLEANSE_SECRETS=false

usage() {
  echo "Usage: $0 [--dry-run] [--phase f1|f2|f3] [--undo] [--force] [--cleanse-secrets]"
  echo ""
  echo "Phases:"
  echo "  f1  Safe file moves (non-sensitive)"
  echo "  f2  Reports, docs, images, archives"
  echo "  f3  Cleanup and verification"
  echo ""
  echo "Options:"
  echo "  --dry-run          Show actions without executing"
  echo "  --undo             Rollback last run"
  echo "  --force            Override safety checks"
  echo "  --cleanse-secrets  REMOVE extracted_keys.txt and scan_keys.py (DANGEROUS)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --phase) PHASE="$2"; shift 2 ;;
    --undo) UNDO=true; shift ;;
    --force) FORCE=true; shift ;;
    --cleanse-secrets) CLEANSE_SECRETS=true; shift ;;
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

# Sensitive files that require explicit --cleanse-secrets
declare -a SENSITIVE_FILES=(
  "/home/cvsz/extracted_keys.txt"
  "/home/cvsz/scan_keys.py"
)

# Phase F1 — Scripts and tools
declare -a PHASE_F1_MOVES=(
  "/home/cvsz/clean-os.sh:tools/scripts/clean-os.sh"
  "/home/cvsz/clean-os-v2.sh:tools/scripts/clean-os-v2.sh"
  "/home/cvsz/freedns_update.sh:tools/scripts/freedns_update.sh"
  "/home/cvsz/g-cvsz.sh:tools/scripts/g-cvsz.sh"
  "/home/cvsz/install_dashscope.sh:tools/scripts/install_dashscope.sh"
  "/home/cvsz/install-clean-os.sh:tools/scripts/install-clean-os.sh"
  "/home/cvsz/migrate-zarvis-to-sdb.sh:tools/scripts/migrate-zarvis-to-sdb.sh"
  "/home/cvsz/omega-core-ssh-repair.sh:tools/scripts/omega-core-ssh-repair.sh"
  "/home/cvsz/omega-ssh-linux.sh:tools/scripts/omega-ssh-linux.sh"
  "/home/cvsz/oneclick-docker-recovery.sh:tools/scripts/oneclick-docker-recovery.sh"
  "/home/cvsz/scan-stack-duplicates.sh:tools/scripts/scan-stack-duplicates.sh"
  "/home/cvsz/ssh-setup.sh:tools/scripts/ssh-setup.sh"
  "/home/cvsz/sync-z-world.sh:tools/scripts/sync-z-world.sh"
  "/home/cvsz/trace-usdt.sh:tools/scripts/trace-usdt.sh"
  "/home/cvsz/uv.sh:tools/scripts/uv.sh"
  "/home/cvsz/zarvis-compose.sh:tools/scripts/zarvis-compose.sh"
  "/home/cvsz/zarvis-oneclick.sh:tools/scripts/zarvis-oneclick.sh"
  "/home/cvsz/zarvis-oneclick.sh.old.20260806-211920:tools/scripts/zarvis-oneclick.sh.old.20260806-211920"
  "/home/cvsz/find_26de_outgoing_fast.py:tools/scripts/find_26de_outgoing_fast.py"
  "/home/cvsz/trace_26de_usdt.py:tools/scripts/trace_26de_usdt.py"
)

# Phase F2 — Documentation, reports, images, archives
declare -a PHASE_F2_MOVES=(
  "/home/cvsz/full-repo-list-cvsz.md:archives/docs/full-repo-list-cvsz.md"
  "/home/cvsz/purpose.md:archives/docs/purpose.md"
  "/home/cvsz/schema.md:archives/docs/schema.md"
  "/home/cvsz/rotate.md:archives/docs/rotate.md"
  "/home/cvsz/ps.txt:archives/logs/ps.txt"
  "/home/cvsz/find_26de_outgoing_fast.log:archives/logs/find_26de_outgoing_fast.log"
  "/home/cvsz/trace_26de_usdt.log:archives/logs/trace_26de_usdt.log"
  "/home/cvsz/stack-duplicate-report-20260812-084755.txt:archives/reports/stack-duplicate-report-20260812-084755.txt"
  "/home/cvsz/loe.jpg:archives/images/loe.jpg"
  "/home/cvsz/loe2.jpg:archives/images/loe2.jpg"
  "/home/cvsz/zeaz-ai-command-center-v3.4.1.zip:archives/zeaz-ai-command-center-v3.4.1.zip"
)

log() {
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" | tee -a "$LOG_DIR/reorganize3-$TIMESTAMP.log"
}

verify_checksum() {
  local src="$1"
  local dst="$2"
  if [[ -f "$src" ]]; then
    local src_sum=$(md5sum "$src" 2>/dev/null | cut -d' ' -f1)
    local dst_sum=$(md5sum "$dst" 2>/dev/null | cut -d' ' -f1)
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
    echo "$src|$dst|$TIMESTAMP" >> "$LOG_DIR/rollback3-$TIMESTAMP.log"
  else
    log "ERROR: Checksum mismatch for $label"
    return 1
  fi
}

execute_remove() {
  local target="$1"
  local label="$2"

  if [[ ! -e "$target" ]]; then
    log "SKIP: $target does not exist"
    return 0
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY-RUN: Would remove $target"
    return 0
  fi

  log "REMOVING: $target"
  rm -rf "$target"
  log "REMOVED: $target"
  echo "REMOVE|$target|$TIMESTAMP" >> "$LOG_DIR/rollback3-$TIMESTAMP.log"
}

rollback() {
  local rollback_file="$LOG_DIR/rollback3-$TIMESTAMP.log"
  if [[ ! -f "$rollback_file" ]]; then
    rollback_file=$(ls -t "$LOG_DIR"/rollback3-*.log 2>/dev/null | head -1)
  fi

  if [[ -z "$rollback_file" || ! -f "$rollback_file" ]]; then
    echo "No rollback file found"
    exit 1
  fi

  log "Rolling back using $rollback_file"
  while IFS='|' read -r action src dst ts; do
    if [[ "$action" == "REMOVE" ]]; then
      log "Cannot restore removed file: $src"
    elif [[ -e "$dst" ]]; then
      log "RESTORING: $dst -> $src"
      mv "$dst" "$src"
    fi
  done < "$rollback_file"
  log "Rollback complete"
}

if [[ "$UNDO" == "true" ]]; then
  rollback
  exit 0
fi

log "=== Starting reorganization phase 3: phase=$PHASE dry_run=$DRY_RUN force=$FORCE cleanse_secrets=$CLEANSE_SECRETS ==="

case "$PHASE" in
  f1)
    log "Phase F1: Scripts and tools"
    for move in "${PHASE_F1_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$src" "$dst" "$src"
    done
    ;;
  f2)
    log "Phase F2: Documentation, reports, images, archives"
    for move in "${PHASE_F2_MOVES[@]}"; do
      IFS=':' read -r src dst <<< "$move"
      execute_move "$src" "$dst" "$src"
    done

    if [[ "$CLEANSE_SECRETS" == "true" ]]; then
      log "Cleansing sensitive files as requested"
      for sensitive in "${SENSITIVE_FILES[@]}"; do
        execute_remove "$sensitive" "$sensitive"
      done
    else
      log "SKIP: Sensitive files require --cleanse-secrets flag:"
      for sensitive in "${SENSITIVE_FILES[@]}"; do
        if [[ -e "$sensitive" ]]; then
          log "  - $sensitive"
        fi
      done
    fi
    ;;
  f3)
    log "Phase F3: Cleanup and verification"
    log "Cleanup phase: verify structure"
    ;;
  *)
    echo "Unknown phase: $PHASE"
    usage
    ;;
esac

log "=== Reorganization phase 3 complete ==="
echo ""
echo "Logs saved to: $LOG_DIR"
echo "To rollback: $0 --undo"
