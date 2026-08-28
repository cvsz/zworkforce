#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:---dry-run}"
MANIFEST_URL="${ZEAZ_UPDATE_MANIFEST_URL:-}"
SIGNATURE_URL="${ZEAZ_UPDATE_SIGNATURE_URL:-${MANIFEST_URL:+${MANIFEST_URL}.sig}}"
PUBLIC_KEY="${ZEAZ_UPDATE_PUBLIC_KEY:-}"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

usage() {
  printf '%s\n' \
    "Usage: CONFIRM_AUTO_UPDATE=yes ZEAZ_UPDATE_MANIFEST_URL=https://... ZEAZ_UPDATE_PUBLIC_KEY=/absolute/key.pub bash scripts/install-auto-update.sh --apply" \
    "Dry-run is the default. Installs a user timer that applies only signature- and checksum-verified releases."
}

[[ "$ACTION" == "--help" ]] && { usage; exit 0; }
[[ "$ACTION" =~ ^--(dry-run|apply)$ ]] || { usage; exit 2; }
[[ "$MANIFEST_URL" == https://* ]] || { echo "HTTPS ZEAZ_UPDATE_MANIFEST_URL is required" >&2; exit 2; }
[[ "$SIGNATURE_URL" == https://* ]] || { echo "HTTPS ZEAZ_UPDATE_SIGNATURE_URL is required" >&2; exit 2; }
[[ "$PUBLIC_KEY" == /* && -f "$PUBLIC_KEY" && -r "$PUBLIC_KEY" ]] ||
  { echo "Absolute readable ZEAZ_UPDATE_PUBLIC_KEY is required" >&2; exit 2; }
if [[ "$ACTION" == "--dry-run" ]]; then
  printf 'Would install daily auto-update timer using manifest %s\n' "$MANIFEST_URL"
  exit 0
fi
[[ "${CONFIRM_AUTO_UPDATE:-no}" == "yes" ]] || { echo "Set CONFIRM_AUTO_UPDATE=yes" >&2; exit 2; }
command -v systemctl >/dev/null || { echo "systemctl is required" >&2; exit 1; }
install -d -m 700 "$UNIT_DIR"
sed \
  -e "s|@UPDATE_SCRIPT@|$ROOT/scripts/update.sh|g" \
  -e "s|@MANIFEST_URL@|$MANIFEST_URL|g" \
  -e "s|@SIGNATURE_URL@|$SIGNATURE_URL|g" \
  -e "s|@PUBLIC_KEY@|$PUBLIC_KEY|g" \
  "$ROOT/deploy/systemd/zeaz-provider-update.service" >"$UNIT_DIR/zeaz-provider-update.service"
install -m 600 "$ROOT/deploy/systemd/zeaz-provider-update.timer" \
  "$UNIT_DIR/zeaz-provider-update.timer"
systemctl --user daemon-reload
systemctl --user enable --now zeaz-provider-update.timer
printf '%s\n' "Daily ZeaZ Provider auto-update timer enabled."
