#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

PREFIX="${ZEAZ_INSTALL_PREFIX:-$HOME/.local/share/zeaz-provider}"
MANIFEST_URL="${ZEAZ_UPDATE_MANIFEST_URL:-}"
SIGNATURE_URL="${ZEAZ_UPDATE_SIGNATURE_URL:-${MANIFEST_URL:+${MANIFEST_URL}.sig}}"
PUBLIC_KEY="${ZEAZ_UPDATE_PUBLIC_KEY:-}"
ACTION="--check"

log() { printf '%s level=%s msg=%q\n' "$(date --iso-8601=seconds)" "$1" "$2"; }
die() { log error "$1"; exit 1; }
trap 'log error "update failed at line $LINENO"' ERR

usage() {
  cat <<'EOF'
Usage: bash scripts/update.sh [--check|--apply]

Requires ZEAZ_UPDATE_MANIFEST_URL pointing to an HTTPS JSON manifest and
ZEAZ_UPDATE_PUBLIC_KEY pointing to an Ed25519 public key in PEM format:
{"version":"0.3.0","url":"https://.../release.zip","sha256":"..."}

The detached signature defaults to <manifest-url>.sig. Override it with
ZEAZ_UPDATE_SIGNATURE_URL, which must also use HTTPS.
--check is the default. --apply also requires CONFIRM_UPDATE=yes.
EOF
}

case "${1:---check}" in
  --check|--apply) ACTION="${1:---check}" ;;
  --help) usage; exit 0 ;;
  *) usage; exit 2 ;;
esac
[[ "$MANIFEST_URL" == https://* ]] || die "ZEAZ_UPDATE_MANIFEST_URL must use HTTPS"
[[ "$SIGNATURE_URL" == https://* ]] || die "ZEAZ_UPDATE_SIGNATURE_URL must use HTTPS"
[[ "$PUBLIC_KEY" == /* && -f "$PUBLIC_KEY" && -r "$PUBLIC_KEY" ]] ||
  die "ZEAZ_UPDATE_PUBLIC_KEY must be an absolute readable file"
command -v curl >/dev/null || die "curl is required"
command -v openssl >/dev/null || die "openssl is required"

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --max-filesize 65536 \
  "$MANIFEST_URL" -o "$tmp/manifest.json"
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --max-filesize 4096 \
  "$SIGNATURE_URL" -o "$tmp/manifest.sig"
[[ "$(wc -c <"$tmp/manifest.sig")" -eq 64 ]] || die "manifest signature has invalid size"
openssl pkeyutl -verify -pubin -inkey "$PUBLIC_KEY" -rawin \
  -in "$tmp/manifest.json" -sigfile "$tmp/manifest.sig" >/dev/null 2>&1 ||
  die "manifest signature verification failed"

readarray -t manifest < <(python3 - "$tmp/manifest.json" <<'PY'
import json, re, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
version, url, digest = value["version"], value["url"], value["sha256"]
assert re.fullmatch(r"\d+\.\d+\.\d+", version)
assert url.startswith("https://")
assert re.fullmatch(r"[a-f0-9]{64}", digest)
print(version); print(url); print(digest)
PY
)
version="${manifest[0]}"
url="${manifest[1]}"
digest="${manifest[2]}"
current="$("$PREFIX/current/bin/python" -c 'import zeaz_provider; print(zeaz_provider.__version__)' 2>/dev/null || true)"

if [[ "$current" == "$version" ]]; then
  log info "already current at $current"
  exit 0
fi
log info "update available current=${current:-not-installed} target=$version"
[[ "$ACTION" == "--apply" ]] || exit 0
[[ "${CONFIRM_UPDATE:-no}" == "yes" ]] || die "set CONFIRM_UPDATE=yes"
command -v unzip >/dev/null || die "unzip is required"
command -v sha256sum >/dev/null || die "sha256sum is required"

archive="$tmp/release.zip"
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$url" -o "$archive"
printf '%s  %s\n' "$digest" "$archive" | sha256sum -c -
unzip -q "$archive" -d "$tmp/release"
installer="$(find "$tmp/release" -type f -path '*/scripts/install.sh' -print -quit)"
[[ -n "$installer" ]] || die "release installer is missing"
release_root="$(cd "$(dirname "$installer")/.." && pwd)"
bash "$release_root/scripts/install.sh" --apply --prefix "$PREFIX"
"$PREFIX/current/bin/python" -c 'import zeaz_provider'
log info "updated to $version"
