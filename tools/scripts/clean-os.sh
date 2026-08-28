#!/usr/bin/env bash
set -Eeuo pipefail

# clean-os.sh
# Safe Ubuntu/Debian cleanup with optional deeper cleanup.
#
# Default:
#   - apt cache + autoremove
#   - journal/vacuum logs
#   - tmp/cache cleanup
#   - old disabled Snap revisions
#   - package-manager caches
#   - report disk/process/service usage
#
# Optional flags:
#   --docker       prune unused Docker build cache/images/networks (NOT volumes)
#   --docker-all   prune all unused Docker images + build cache (NOT volumes)
#   --snap         remove disabled/old Snap revisions
#   --user-cache   clean selected user caches
#   --deep         enables --docker --snap --user-cache
#   --vacuum DAYS  journal retention days (default: 7)
#   --dry-run      print destructive commands without executing them
#
# Intentionally NEVER:
#   - kills arbitrary processes
#   - removes Docker volumes
#   - resets MicroK8s
#   - deletes Ollama models
#   - deletes databases/project directories
#   - disables SSH/network/systemd services

DRY_RUN=0
DO_DOCKER=0
DO_DOCKER_ALL=0
DO_SNAP=0
DO_USER_CACHE=0
VACUUM_DAYS=7

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }

run() {
  if (( DRY_RUN )); then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

need_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo --preserve-env=PATH bash "$0" "$@"
  fi
}

usage() {
  sed -n '2,31p' "$0" | sed 's/^# \{0,1\}//'
}

while (( $# )); do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --docker) DO_DOCKER=1 ;;
    --docker-all) DO_DOCKER=1; DO_DOCKER_ALL=1 ;;
    --snap) DO_SNAP=1 ;;
    --user-cache) DO_USER_CACHE=1 ;;
    --deep) DO_DOCKER=1; DO_SNAP=1; DO_USER_CACHE=1 ;;
    --vacuum)
      shift
      [[ ${1:-} =~ ^[0-9]+$ ]] || { echo "--vacuum requires number of days"; exit 2; }
      VACUUM_DAYS="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
  shift
done

ORIGINAL_USER="${SUDO_USER:-${USER:-root}}"
if [[ "$ORIGINAL_USER" == "root" ]]; then
  USER_HOME="/root"
else
  USER_HOME="$(getent passwd "$ORIGINAL_USER" | cut -d: -f6)"
fi

need_root "$@"

log "Before cleanup"
df -hT / || true
printf '\nLargest /var consumers:\n'
du -xhd1 /var 2>/dev/null | sort -h | tail -n 15 || true

printf '\nTop CPU processes:\n'
ps -eo pid,user,%cpu,%mem,comm,args --sort=-%cpu | head -n 16 || true

printf '\nTop memory processes:\n'
ps -eo pid,user,%cpu,%mem,rss,comm,args --sort=-rss | head -n 16 || true

log "APT cleanup"
if command -v apt-get >/dev/null 2>&1; then
  run apt-get clean
  run apt-get autoclean
  run apt-get autoremove --purge -y
  ok "APT cleanup complete"
fi

log "systemd journal cleanup"
if command -v journalctl >/dev/null 2>&1; then
  run journalctl --rotate
  run journalctl --vacuum-time="${VACUUM_DAYS}d"
  ok "Journal retention set to ${VACUUM_DAYS} days"
fi

log "Temporary files"
if command -v systemd-tmpfiles >/dev/null 2>&1; then
  run systemd-tmpfiles --clean
fi

# Only stale files. Do not blindly rm /tmp while services are running.
if [[ -d /tmp ]]; then
  if (( DRY_RUN )); then
    echo "[dry-run] find /tmp -xdev -type f -atime +7 -delete"
    echo "[dry-run] find /tmp -xdev -type d -empty -mtime +7 -delete"
  else
    find /tmp -xdev -type f -atime +7 -delete 2>/dev/null || true
    find /tmp -xdev -type d -empty -mtime +7 -delete 2>/dev/null || true
  fi
fi
ok "Stale temporary files processed"

log "Crash reports and rotated logs"
if [[ -d /var/crash ]]; then
  if (( DRY_RUN )); then
    echo "[dry-run] remove files under /var/crash"
  else
    find /var/crash -mindepth 1 -maxdepth 1 -type f -delete 2>/dev/null || true
  fi
fi

# Remove only old compressed/rotated logs, preserving current logs.
if [[ -d /var/log ]]; then
  if (( DRY_RUN )); then
    echo "[dry-run] find /var/log -type f \\( -name '*.gz' -o -name '*.[0-9]' \\) -mtime +14 -delete"
  else
    find /var/log -xdev -type f \( -name '*.gz' -o -name '*.[0-9]' \) -mtime +14 -delete 2>/dev/null || true
  fi
fi
ok "Old crash/rotated logs processed"

if (( DO_SNAP )) && command -v snap >/dev/null 2>&1; then
  log "Old disabled Snap revisions"
  # Keep fewer revisions in future.
  run snap set system refresh.retain=2

  while read -r snapname revision; do
    [[ -n "$snapname" && -n "$revision" ]] || continue
    run snap remove "$snapname" --revision="$revision"
  done < <(
    snap list --all 2>/dev/null |
      awk 'NR>1 && $NF=="disabled" {print $1, $3}'
  )
  ok "Disabled Snap revisions processed"
fi

if (( DO_USER_CACHE )); then
  log "Selected user caches for ${ORIGINAL_USER}"

  clean_dir_contents() {
    local dir="$1"
    [[ -d "$dir" ]] || return 0
    if (( DRY_RUN )); then
      echo "[dry-run] clean contents: $dir"
    else
      find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + 2>/dev/null || true
    fi
  }

  clean_dir_contents "$USER_HOME/.cache/pip"
  clean_dir_contents "$USER_HOME/.npm/_cacache"
  clean_dir_contents "$USER_HOME/.cache/yarn"
  clean_dir_contents "$USER_HOME/.cache/pnpm"
  clean_dir_contents "$USER_HOME/.cache/thumbnails"

  # npm's own cache verifier safely removes corrupt/unused cache entries.
  if command -v npm >/dev/null 2>&1; then
    if (( DRY_RUN )); then
      echo "[dry-run] sudo -u $ORIGINAL_USER npm cache verify"
    elif [[ "$ORIGINAL_USER" != root ]]; then
      sudo -u "$ORIGINAL_USER" npm cache verify >/dev/null 2>&1 || true
    else
      npm cache verify >/dev/null 2>&1 || true
    fi
  fi
  ok "Selected user caches processed"
fi

if (( DO_DOCKER )) && command -v docker >/dev/null 2>&1; then
  log "Docker cleanup"
  echo "Current Docker disk usage:"
  docker system df || true

  # Never use --volumes here: databases may live in Docker volumes.
  run docker container prune -f
  run docker network prune -f
  run docker builder prune -af

  if (( DO_DOCKER_ALL )); then
    # Deletes images not used by any container, including untagged and tagged unused images.
    run docker image prune -af
  else
    # Safer default: dangling images only.
    run docker image prune -f
  fi
  ok "Docker cleanup complete; volumes were NOT removed"
fi

log "Package/cache diagnostics"
if command -v snap >/dev/null 2>&1; then
  snap list --all 2>/dev/null | awk 'NR==1 || $NF=="disabled"' || true
fi

printf '\nDocker usage:\n'
if command -v docker >/dev/null 2>&1; then
  docker system df 2>/dev/null || true
fi

printf '\nLargest user cache directories:\n'
du -xhd1 "$USER_HOME/.cache" 2>/dev/null | sort -h | tail -n 15 || true

printf '\nLargest /var directories after cleanup:\n'
du -xhd1 /var 2>/dev/null | sort -h | tail -n 15 || true

log "After cleanup"
df -hT / || true

cat <<'EOF'

Safety notes:
  * Docker volumes were not deleted.
  * MicroK8s state was not reset or pruned.
  * Ollama models were not deleted.
  * PostgreSQL/data directories were not touched.
  * Caddy, PM2, SSH, networking, and application processes were not killed.

Useful modes:
  sudo ./clean-os.sh --dry-run
  sudo ./clean-os.sh
  sudo ./clean-os.sh --snap --user-cache
  sudo ./clean-os.sh --docker
  sudo ./clean-os.sh --deep
  sudo ./clean-os.sh --docker-all   # more aggressive image cleanup
EOF
