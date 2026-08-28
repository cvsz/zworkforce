#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="2.0.0"
DRY_RUN=0
DO_DOCKER=0
DO_DOCKER_ALL=0
DO_SNAP=0
DO_USER_CACHE=0
VACUUM_DAYS="${CLEAN_OS_VACUUM_DAYS:-7}"
ORIGINAL_ARGS=("$@")

log(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok(){ printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }

usage(){
cat <<EOF
clean-os $VERSION
Safe Ubuntu/Debian cleanup utility.

Usage:
  clean-os [options]

Options:
  --dry-run
  --docker
  --docker-all
  --snap
  --user-cache
  --deep
  --vacuum DAYS
  --version
  -h, --help
EOF
}

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo --preserve-env=PATH,CLEAN_OS_VACUUM_DAYS bash "$0" "${ORIGINAL_ARGS[@]}"
fi

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --docker) DO_DOCKER=1 ;;
    --docker-all) DO_DOCKER=1; DO_DOCKER_ALL=1 ;;
    --snap) DO_SNAP=1 ;;
    --user-cache) DO_USER_CACHE=1 ;;
    --deep) DO_DOCKER=1; DO_SNAP=1; DO_USER_CACHE=1 ;;
    --vacuum)
      shift
      [[ ${1:-} =~ ^[0-9]+$ ]] || { echo "--vacuum requires number of days" >&2; exit 2; }
      VACUUM_DAYS="$1"
      ;;
    --version) echo "clean-os $VERSION"; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

ORIGINAL_USER="${SUDO_USER:-${USER:-root}}"
if [[ "$ORIGINAL_USER" == root ]]; then
  USER_HOME="/root"
else
  USER_HOME="$(getent passwd "$ORIGINAL_USER" | cut -d: -f6)"
fi

run(){
  if ((DRY_RUN)); then
    printf '[dry-run] '; printf '%q ' "$@"; printf '\n'
  else
    "$@"
  fi
}

log "Before cleanup"
df -hT / || true
du -xhd1 /var 2>/dev/null | sort -h | tail -n 15 || true
ps -eo pid,user,%cpu,%mem,comm,args --sort=-%cpu | head -n 16 || true
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
  ok "Journal retention: ${VACUUM_DAYS} days"
fi

log "Temporary files"
command -v systemd-tmpfiles >/dev/null 2>&1 && run systemd-tmpfiles --clean || true
if [[ -d /tmp ]]; then
  if ((DRY_RUN)); then
    echo "[dry-run] remove stale /tmp files older than 7 days"
  else
    find /tmp -xdev -type f -atime +7 -delete 2>/dev/null || true
    find /tmp -xdev -type d -empty -mtime +7 -delete 2>/dev/null || true
  fi
fi

log "Crash reports and rotated logs"
if ((DRY_RUN)); then
  echo "[dry-run] clean /var/crash and old rotated logs"
else
  find /var/crash -mindepth 1 -maxdepth 1 -type f -delete 2>/dev/null || true
  find /var/log -xdev -type f \( -name '*.gz' -o -name '*.[0-9]' \) -mtime +14 -delete 2>/dev/null || true
fi

if ((DO_SNAP)) && command -v snap >/dev/null 2>&1; then
  log "Disabled Snap revisions"
  run snap set system refresh.retain=2
  while read -r snapname revision; do
    [[ -n "$snapname" && -n "$revision" ]] || continue
    run snap remove "$snapname" --revision="$revision"
  done < <(snap list --all 2>/dev/null | awk 'NR>1 && $NF=="disabled"{print $1,$3}')
fi

if ((DO_USER_CACHE)); then
  log "User caches"
  clean_dir(){
    local d="$1"
    [[ -d "$d" ]] || return 0
    if ((DRY_RUN)); then echo "[dry-run] clean $d"
    else find "$d" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + 2>/dev/null || true
    fi
  }
  clean_dir "$USER_HOME/.cache/pip"
  clean_dir "$USER_HOME/.npm/_cacache"
  clean_dir "$USER_HOME/.cache/yarn"
  clean_dir "$USER_HOME/.cache/pnpm"
  clean_dir "$USER_HOME/.cache/uv"
  clean_dir "$USER_HOME/.cache/thumbnails"
fi

if ((DO_DOCKER)) && command -v docker >/dev/null 2>&1; then
  log "Docker cleanup"
  docker system df || true
  run docker container prune -f
  run docker network prune -f
  run docker builder prune -af
  if ((DO_DOCKER_ALL)); then
    run docker image prune -af
  else
    run docker image prune -f
  fi
  ok "Docker cleanup complete; volumes were NOT removed"
fi

log "After cleanup"
df -hT / || true
command -v docker >/dev/null 2>&1 && docker system df 2>/dev/null || true
du -xhd1 /var 2>/dev/null | sort -h | tail -n 15 || true
du -xhd1 "$USER_HOME/.cache" 2>/dev/null | sort -h | tail -n 15 || true

cat <<'EOF'

Safety:
  - Docker volumes are never pruned.
  - MicroK8s state is not reset.
  - Ollama models are not deleted.
  - PostgreSQL/database directories are not touched directly.
  - SSH/networking/application processes are not killed.
EOF
