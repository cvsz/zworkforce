#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

PREFIX="${ZEAZ_INSTALL_PREFIX:-$HOME/.local/share/zeaz-provider}"
BIN_DIR="${ZEAZ_BIN_DIR:-$HOME/.local/bin}"
ACTION="--dry-run"
PURGE=false

log() { printf '%s level=%s msg=%q\n' "$(date --iso-8601=seconds)" "$1" "$2"; }
die() { log error "$1"; exit 1; }
trap 'log error "uninstall failed at line $LINENO"' ERR

usage() {
  cat <<'EOF'
Usage: bash scripts/uninstall.sh [--dry-run|--apply] [--purge] [--prefix PATH]

Dry-run is the default. The standard uninstall removes the wrapper, current
symlink, and systemd user units while keeping the versioned install tree and
configuration unless --purge is supplied.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dry-run|--apply) ACTION="$1" ;;
    --purge) PURGE=true ;;
    --prefix) shift; PREFIX="${1:-}"; [[ -n "$PREFIX" ]] || die "--prefix requires a path" ;;
    --help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

[[ "$PREFIX" == /* ]] || die "install prefix must be absolute"
install_root="$PREFIX"
wrapper="$BIN_DIR/zeaz-provider"
service_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service_file="$service_dir/zeaz-provider.service"
update_service="$service_dir/zeaz-provider-update.service"
update_timer="$service_dir/zeaz-provider-update.timer"
current_target=""
if [[ -L "$install_root/current" ]]; then
  current_target="$(readlink "$install_root/current")"
fi

if [[ "$ACTION" == "--dry-run" ]]; then
  log info "would disable user services under $service_dir"
  log info "would remove $wrapper and $install_root/current"
  $PURGE && log info "would remove $install_root/versions $install_root/config $install_root/backups"
  exit 0
fi

if command -v systemctl >/dev/null; then
  systemctl --user disable --now zeaz-provider.service >/dev/null 2>&1 || true
  systemctl --user disable --now zeaz-provider-update.timer >/dev/null 2>&1 || true
fi

rm -f -- "$wrapper" "$install_root/current" "$install_root/current.new" "$install_root/current.rollback"
rm -f -- "$service_file" "$update_service" "$update_timer"

if $PURGE; then
  rm -rf -- "$install_root/versions" "$install_root/config" "$install_root/backups"
  log warning "purged versioned install state"
else
  install -d -m 700 "$install_root/backups"
  {
    printf 'previous=%s\n' "${current_target:-}"
    printf 'uninstalled=%s\n' "$(date --iso-8601=seconds)"
  } >"$install_root/backups/last-uninstall"
fi

log info "ZeaZ Provider uninstalled"
