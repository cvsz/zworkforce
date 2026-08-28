#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

usage() {
  printf '%s\n' \
    "Usage: bash scripts/sign-update-manifest.sh MANIFEST PRIVATE_KEY [SIGNATURE]" \
    "Signs the exact manifest bytes with an Ed25519 private key." >&2
}

[[ "$#" -ge 2 && "$#" -le 3 ]] || { usage; exit 2; }
manifest="$1"
private_key="$2"
signature="${3:-${manifest}.sig}"

[[ -f "$manifest" && -r "$manifest" ]] || { printf 'Manifest is not readable.\n' >&2; exit 1; }
[[ -f "$private_key" && -r "$private_key" ]] ||
  { printf 'Private key is not readable.\n' >&2; exit 1; }
command -v openssl >/dev/null || { printf 'openssl is required.\n' >&2; exit 1; }

python3 - "$manifest" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    value = json.load(source)
if set(value) != {"version", "url", "sha256"}:
    raise SystemExit("manifest must contain exactly version, url, and sha256")
if not re.fullmatch(r"\d+\.\d+\.\d+", value["version"]):
    raise SystemExit("invalid manifest version")
if not value["url"].startswith("https://"):
    raise SystemExit("manifest release URL must use HTTPS")
if not re.fullmatch(r"[a-f0-9]{64}", value["sha256"]):
    raise SystemExit("invalid manifest SHA-256")
PY

tmp_signature="$(mktemp "${signature}.XXXXXX")"
trap 'rm -f -- "$tmp_signature"' EXIT
openssl pkeyutl -sign -inkey "$private_key" -rawin -in "$manifest" -out "$tmp_signature"
[[ "$(wc -c <"$tmp_signature")" -eq 64 ]] ||
  { printf 'Signing did not produce an Ed25519 signature.\n' >&2; exit 1; }
mv -f -- "$tmp_signature" "$signature"
trap - EXIT
printf 'Signed manifest: %s\n' "$signature"
