#!/usr/bin/env bash
set -Eeuo pipefail

exec bash "$HOME/z-platform/scripts/zarvis-complete-all.sh" "$@"
