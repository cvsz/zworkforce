#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="2.0.0"
ENABLE_WEEKLY=0
RUN_NOW=0
DRY_RUN_INSTALL=0
ORIG_ARGS=("$@")

log(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok(){ printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo bash "$0" "${ORIG_ARGS[@]}"
fi

while (($#)); do
  case "$1" in
    --enable-weekly) ENABLE_WEEKLY=1 ;;
    --run) RUN_NOW=1 ;;
    --dry-run-install) DRY_RUN_INSTALL=1 ;;
    -h|--help)
      cat <<EOF
Usage:
  sudo bash install-clean-os.sh [--enable-weekly] [--run] [--dry-run-install]
EOF
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/clean-os-v2.sh"
TARGET="/usr/local/sbin/clean-os"
LINK="/usr/local/bin/clean-os"

[[ -f "$SOURCE" ]] || { echo "ERROR: clean-os-v2.sh must be beside installer" >&2; exit 2; }

log "Install clean-os"
if ((DRY_RUN_INSTALL)); then
  echo "[dry-run] install -m 0755 $SOURCE $TARGET"
  echo "[dry-run] ln -sfn $TARGET $LINK"
else
  install -m 0755 "$SOURCE" "$TARGET"
  mkdir -p /usr/local/bin
  ln -sfn "$TARGET" "$LINK"
fi
ok "Installed command: clean-os"

log "Install configuration"
if ((DRY_RUN_INSTALL)); then
  echo "[dry-run] create /etc/clean-os.conf"
else
  [[ -f /etc/clean-os.conf ]] || cat >/etc/clean-os.conf <<'EOF'
# clean-os defaults
# CLEAN_OS_VACUUM_DAYS=7
EOF
fi

log "Install systemd service/timer"
if ((DRY_RUN_INSTALL)); then
  echo "[dry-run] install clean-os.service and clean-os.timer"
else
  cat >/etc/systemd/system/clean-os.service <<'EOF'
[Unit]
Description=Safe OS cleanup
After=local-fs.target

[Service]
Type=oneshot
EnvironmentFile=-/etc/clean-os.conf
ExecStart=/usr/local/sbin/clean-os --snap --user-cache
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

  cat >/etc/systemd/system/clean-os.timer <<'EOF'
[Unit]
Description=Weekly safe OS cleanup

[Timer]
OnCalendar=Sun *-*-* 04:30:00
Persistent=true
RandomizedDelaySec=15m

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
fi

if ((ENABLE_WEEKLY)); then
  log "Enable weekly timer"
  if ((DRY_RUN_INSTALL)); then
    echo "[dry-run] systemctl enable --now clean-os.timer"
  else
    systemctl enable --now clean-os.timer
  fi
else
  echo "Weekly timer installed but not enabled."
fi

if ((RUN_NOW)); then
  log "First cleanup"
  if ((DRY_RUN_INSTALL)); then
    echo "[dry-run] clean-os --snap --user-cache"
  else
    "$TARGET" --snap --user-cache
  fi
fi

cat <<EOF

Installed:
  /usr/local/sbin/clean-os
  /usr/local/bin/clean-os
  /etc/clean-os.conf
  /etc/systemd/system/clean-os.service
  /etc/systemd/system/clean-os.timer

Commands:
  clean-os --dry-run
  clean-os
  clean-os --snap --user-cache
  clean-os --docker
  clean-os --deep
  clean-os --docker-all

Enable weekly:
  sudo systemctl enable --now clean-os.timer
EOF

ok "Installation complete"
