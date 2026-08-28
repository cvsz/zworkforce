#!/usr/bin/env bash
set -Eeuo pipefail

# Lossless convenience wrapper around apikey-manager.sh.
#
# This command preserves comments, blank lines, duplicate assignments,
# unsupported variables, and malformed lines. It only normalizes matching
# *_*_KEY assignments after removing balanced outer quote pairs.

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if (( $# > 1 )); then
  printf 'Usage: %s [credential-file]\n' "${0##*/}" >&2
  exit 2
fi

if (( $# == 1 )); then
  export APIKEY_FILE="$1"
fi

exec "$SCRIPT_DIR/apikey-manager.sh" organize
