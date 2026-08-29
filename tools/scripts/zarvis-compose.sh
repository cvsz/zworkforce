#!/usr/bin/env bash
set -Eeuo pipefail

cd "$HOME/z-platform"

export ZARVIS_HOST_UID
export ZARVIS_HOST_GID
ZARVIS_HOST_UID="$(id -u)"
ZARVIS_HOST_GID="$(id -g)"

exec docker compose \
  --env-file .env.zarvis.local \
  -f compose.zarvis-local.yml \
  -f compose.zarvis-owner-domain.yml \
  "$@"
