#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="${ZARVIS_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONFIRM_LIVE=false
DOMAIN_ARGS=()

usage() {
  cat <<'USAGE'
Complete actual-host validation and deploy owner-only zarvis.zeaz.dev

Usage:
  bash scripts/zarvis-owner-domain-live.sh --confirm-live [domain options]

Domain options:
  --server-host HOST
  --ssh-user USER
  --ssh-port PORT
  --rotate-ca
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm-live)
      CONFIRM_LIVE=true
      shift
      ;;
    --server-host|--ssh-user|--ssh-port)
      [[ $# -ge 2 ]] || { echo "$1 requires a value" >&2; exit 1; }
      DOMAIN_ARGS+=("$1" "$2")
      shift 2
      ;;
    --rotate-ca)
      DOMAIN_ARGS+=("$1")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

[[ "$CONFIRM_LIVE" == true ]] || {
  echo "--confirm-live is required because live validation performs backup/restore and credential rotation" >&2
  exit 1
}

cd "$ROOT_DIR"
git fetch origin --prune --tags
git switch main
git pull --ff-only origin main

bash scripts/zarvis-live-complete.sh --confirm-live

export ZARVIS_OWNER_UID="$(id -u)"
export ZARVIS_OWNER_GID="$(id -g)"
bash scripts/zarvis-owner-domain-setup.sh "${DOMAIN_ARGS[@]}"
