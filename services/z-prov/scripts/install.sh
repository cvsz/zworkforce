#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
PREFIX="${ZEAZ_INSTALL_PREFIX:-$HOME/.local/share/zeaz-provider}"
BIN_DIR="${ZEAZ_BIN_DIR:-$HOME/.local/bin}"
ACTION="--dry-run"
SYSTEMD_USER=false
stage=""
tmp_wrapper=""
previous=""
switched=false

log() { printf '%s level=%s msg=%q\n' "$(date --iso-8601=seconds)" "$1" "$2"; }
die() { log error "$1"; exit 1; }
trap 'log error "installation failed at line $LINENO"' ERR

cleanup() {
  status="$?"
  trap - EXIT
  set +e
  [[ -z "$stage" || ! -e "$stage" ]] || rm -rf -- "$stage"
  [[ -z "$tmp_wrapper" || ! -e "$tmp_wrapper" ]] || rm -f -- "$tmp_wrapper"
  if [[ "$status" -ne 0 && "$switched" == true ]]; then
    if [[ -n "$previous" ]]; then
      ln -sfn "$previous" "$PREFIX/current.rollback"
      mv -Tf "$PREFIX/current.rollback" "$PREFIX/current"
    else
      rm -f -- "$PREFIX/current"
    fi
    log warning "restored previous installation after failed update"
  fi
  [[ "$status" -eq 0 ]] || rm -f -- "$PREFIX/current.new" "$PREFIX/current.rollback"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM

usage() {
  cat <<'EOF'
Usage: bash scripts/install.sh [--dry-run|--apply] [--prefix PATH] [--systemd-user]

Dry-run is the default. --apply installs an isolated versioned virtual
environment and atomically switches the current version. Existing config is
retained. --systemd-user also installs and enables a user service.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dry-run|--apply) ACTION="$1" ;;
    --prefix) shift; PREFIX="${1:-}"; [[ -n "$PREFIX" ]] || die "--prefix requires a path" ;;
    --systemd-user) SYSTEMD_USER=true ;;
    --help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

[[ "$PREFIX" == /* ]] || die "install prefix must be absolute"
command -v python3 >/dev/null || die "python3 is required"
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' ||
  die "Python 3.11 or newer is required"
wheel="$ROOT/dist/zeaz_provider-${VERSION}-py3-none-any.whl"
[[ -f "$wheel" ]] || die "release wheel is missing: $wheel"
target="$PREFIX/versions/$VERSION"

log info "version=$VERSION prefix=$PREFIX systemd_user=$SYSTEMD_USER action=$ACTION"
if [[ "$ACTION" == "--dry-run" ]]; then
  log info "would create isolated runtime at $target"
  log info "would switch $PREFIX/current and install $BIN_DIR/zeaz-provider"
  $SYSTEMD_USER && log info "would install and enable zeaz-provider.service"
  exit 0
fi

install -d -m 700 "$PREFIX/versions" "$PREFIX/config" "$PREFIX/backups"
if [[ ! -d "$target" ]]; then
  # A Python virtual environment records its absolute path in console-script
  # shebangs.  Do not create it in a temporary directory and then rename it:
  # that leaves every entry point pointing at a deleted interpreter.  The
  # active `current` symlink is only switched after this target validates, so
  # creating the inactive version in place preserves rollback safety.
  stage="$target"
  python3 -m venv "$stage"
  "$stage/bin/pip" install --disable-pip-version-check "$wheel"
  "$stage/bin/python" -c 'import zeaz_provider'
  stage=""
fi
"$target/bin/python" -c 'import zeaz_provider'

if [[ ! -f "$PREFIX/config/providers.yaml" ]]; then
  install -m 600 "$ROOT/config/providers.example.yaml" "$PREFIX/config/providers.yaml"
fi

if [[ -L "$PREFIX/current" ]]; then
  previous="$(readlink "$PREFIX/current")"
fi
ln -sfn "$target" "$PREFIX/current.new"
switched=true
mv -Tf "$PREFIX/current.new" "$PREFIX/current"

install -d -m 755 "$BIN_DIR"
wrapper="$BIN_DIR/zeaz-provider"
tmp_wrapper="$(mktemp "$BIN_DIR/.zeaz-provider.XXXXXX")"
printf '%s\n' '#!/usr/bin/env bash' \
  "export ZEAZ_CONFIG=\"\${ZEAZ_CONFIG:-$PREFIX/config/providers.yaml}\"" \
  "exec \"$PREFIX/current/bin/zeaz-provider\" \"\$@\"" >"$tmp_wrapper"
chmod 755 "$tmp_wrapper"
mv -f "$tmp_wrapper" "$wrapper"
tmp_wrapper=""

if $SYSTEMD_USER; then
  command -v systemctl >/dev/null || die "systemctl is required for --systemd-user"
  unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  install -d -m 700 "$unit_dir"
  sed \
    -e "s|@BIN@|$wrapper|g" \
    -e "s|@CONFIG@|$PREFIX/config/providers.yaml|g" \
    "$ROOT/deploy/systemd/zeaz-provider.service" >"$unit_dir/zeaz-provider.service"
  systemctl --user daemon-reload
  systemctl --user enable --now zeaz-provider.service
fi

printf 'previous=%s\ninstalled=%s\n' "$previous" "$VERSION" >"$PREFIX/backups/last-install"
switched=false
log info "ZeaZ Provider $VERSION installed"
