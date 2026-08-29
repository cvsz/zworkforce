#!/usr/bin/env bash
set -Eeuo pipefail

DRY_RUN=0
DO_COMPOSE=1
COMPOSE_ROOT="/home"

log(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok(){ printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err(){ printf '\033[1;31m[ERR]\033[0m %s\n' "$*" >&2; }

run(){
  if ((DRY_RUN)); then printf '[dry-run] '; printf '%q ' "$@"; printf '\n'; else "$@"; fi
}

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --no-compose) DO_COMPOSE=0 ;;
    --compose-root) shift; COMPOSE_ROOT="${1:-}"; [[ -n "$COMPOSE_ROOT" ]] || { err "--compose-root requires path"; exit 2; } ;;
    -h|--help) echo "Usage: sudo bash oneclick-docker-recovery.sh [--dry-run] [--no-compose] [--compose-root PATH]"; exit 0 ;;
    *) err "Unknown option: $1"; exit 2 ;;
  esac
  shift
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo bash "$0" "$@"
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="/root/docker-recovery-$STAMP"
REPORT="$BACKUP_ROOT/recovery-report.txt"
mkdir -p "$BACKUP_ROOT"
touch "$REPORT"
exec > >(tee -a "$REPORT") 2>&1

log "Preflight"
df -hT / || true

if findmnt -rn /var/lib/containerd >/dev/null 2>&1; then
  err "/var/lib/containerd is still mounted. Remove stale bind mount first."
  findmnt /var/lib/containerd || true
  exit 2
fi

if grep -Eq '^[[:space:]]*/mnt/lib/containerd[[:space:]]+/var/lib/containerd[[:space:]]+none[[:space:]]+bind' /etc/fstab; then
  cp -a /etc/fstab "$BACKUP_ROOT/fstab.before"
  sed -i '\|^[[:space:]]*/mnt/lib/containerd[[:space:]]\+/var/lib/containerd[[:space:]]\+none[[:space:]]\+bind|d' /etc/fstab
  ok "Removed stale fstab bind entry"
fi

log "Stop Docker/containerd"
run systemctl stop docker.service || true
run systemctl stop docker.socket || true
run systemctl stop containerd.service || true

log "Backup Docker volumes and metadata"
if [[ -d /var/lib/docker/volumes ]]; then
  du -sh /var/lib/docker/volumes || true
  if ((DRY_RUN)); then
    echo "[dry-run] backup /var/lib/docker/volumes"
  else
    tar --xattrs --acls --numeric-owner -C /var/lib/docker -cpf "$BACKUP_ROOT/docker-volumes.tar" volumes
  fi
  ok "Docker volumes backed up"
else
  warn "/var/lib/docker/volumes not found"
fi

for p in /etc/docker /var/lib/docker/network /var/lib/docker/containers /var/lib/docker/image; do
  if [[ -e "$p" && $DRY_RUN -eq 0 ]]; then
    b="$(basename "$p")"
    tar --xattrs --acls --numeric-owner -C "$(dirname "$p")" -cpf "$BACKUP_ROOT/${b}.tar" "$b" 2>/dev/null || true
  fi
done

log "Initialize clean containerd root"
SIZE_KB=0
[[ -d /var/lib/containerd ]] && SIZE_KB="$(du -s /var/lib/containerd 2>/dev/null | awk '{print $1}')"
if ((SIZE_KB > 10240)); then
  warn "Existing containerd data found; quarantining"
  run mv /var/lib/containerd "/var/lib/containerd.pre-recovery-$STAMP"
fi
run mkdir -p /var/lib/containerd
run chmod 700 /var/lib/containerd

log "Start containerd"
run systemctl start containerd.service
if ((DRY_RUN==0)); then
  sleep 2
  systemctl is-active --quiet containerd || { journalctl -u containerd -n 100 --no-pager; exit 2; }
fi
ok "containerd active"

log "Start Docker"
run systemctl start docker.service
if ((DRY_RUN==0)); then
  sleep 3
  systemctl is-active --quiet docker || { journalctl -u docker -n 150 --no-pager; exit 2; }
fi
ok "Docker active"

log "Docker diagnostics"
docker info || true
docker ps -a || true
docker volume ls || true

log "Discover Compose files"
mapfile -t COMPOSE_FILES < <(
  find "$COMPOSE_ROOT" /opt /srv -xdev -type f \
    \( -name compose.yaml -o -name compose.yml -o -name docker-compose.yml -o -name docker-compose.yaml \) \
    2>/dev/null | sort -u
)
printf '%s\n' "${COMPOSE_FILES[@]:-}" | tee "$BACKUP_ROOT/compose-files.txt"

if ((DO_COMPOSE)) && ((${#COMPOSE_FILES[@]})); then
  log "Recreate Compose projects"
  for file in "${COMPOSE_FILES[@]}"; do
    dir="$(dirname "$file")"
    echo "--- $file"
    if ! (cd "$dir" && docker compose -f "$file" config >/dev/null 2>&1); then
      warn "Skipping unresolved compose: $file"
      continue
    fi
    if ((DRY_RUN)); then
      echo "[dry-run] cd '$dir' && docker compose -f '$file' pull"
      echo "[dry-run] cd '$dir' && docker compose -f '$file' up -d --remove-orphans"
    else
      (cd "$dir" && docker compose -f "$file" pull || true)
      (cd "$dir" && docker compose -f "$file" up -d --remove-orphans || true)
    fi
  done
fi

log "Final report"
docker ps -a || true
docker volume ls || true
docker system df || true
df -hT / || true
du -sh /var/lib/containerd /var/lib/docker 2>/dev/null || true

echo
echo "Backup: $BACKUP_ROOT"
echo "Safety: Docker volumes preserved; MicroK8s untouched; no volume prune executed."
ok "Recovery completed"
