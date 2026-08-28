#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

PREFIX="${ZEAZ_INSTALL_PREFIX:-$HOME/.local/share/zeaz-provider}"
BIN_DIR="${ZEAZ_BIN_DIR:-$HOME/.local/bin}"
JSON=false

usage() {
  cat <<'EOF'
Usage: bash scripts/doctor.sh [--json]

Checks the local ZeaZ installation, wrapper, version target, and user-service
files without mutating the host.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --json) JSON=true ;;
    --help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

current="$PREFIX/current"
wrapper="$BIN_DIR/zeaz-provider"
service_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service_file="$service_dir/zeaz-provider.service"
update_service="$service_dir/zeaz-provider-update.service"
update_timer="$service_dir/zeaz-provider-update.timer"

version="unknown"
status="degraded"
if [[ -x "$current/bin/python" ]]; then
  version="$("$current/bin/python" -c 'import zeaz_provider; print(zeaz_provider.__version__)' 2>/dev/null || true)"
fi
if [[ -L "$current" && -x "$wrapper" && -f "$service_file" ]]; then
  status="healthy"
fi

if $JSON; then
  python3 - "$current" "$wrapper" "$service_file" "$update_service" "$update_timer" "$version" "$status" <<'PY'
import json
import sys
from pathlib import Path

current, wrapper, service_file, update_service, update_timer, version, status = sys.argv[1:]
print(
    json.dumps(
        {
            "current": Path(current).is_symlink(),
            "wrapper": Path(wrapper).exists(),
            "service_file": Path(service_file).exists(),
            "update_service": Path(update_service).exists(),
            "update_timer": Path(update_timer).exists(),
            "version": version,
            "status": status,
        },
        sort_keys=True,
    )
)
PY
  exit 0
fi

printf 'status=%s version=%s current=%s wrapper=%s service=%s update_timer=%s\n' \
  "$status" "$version" "$current" "$wrapper" "$service_file" "$update_timer"
[[ "$status" == "healthy" ]] || exit 1
