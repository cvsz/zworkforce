#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workdir="$(mktemp -d)"
trap 'rm -rf -- "$workdir"' EXIT

cat > "$workdir/.apikey" <<'EOF'
# comment must stay

ZETA_SERVICE_KEY='zeta-value'
ALPHA_SERVICE_KEY="alpha-value"
MIXED_SERVICE_KEY='"mixed-value"'
IGNORED_TOKEN="not-a-key"
BROKEN LINE MUST STAY
DUPLICATE_SERVICE_KEY="old-value"
DUPLICATE_SERVICE_KEY='new-value'
EOF

APIKEY_FILE="$workdir/.apikey" "$repo_root/scripts/normalize-apikey.sh"

cat > "$workdir/expected" <<'EOF'
# comment must stay

ZETA_SERVICE_KEY="zeta-value"
ALPHA_SERVICE_KEY="alpha-value"
MIXED_SERVICE_KEY="mixed-value"
IGNORED_TOKEN="not-a-key"
BROKEN LINE MUST STAY
DUPLICATE_SERVICE_KEY="old-value"
DUPLICATE_SERVICE_KEY="new-value"
EOF

diff -u "$workdir/expected" "$workdir/.apikey"
[[ "$(stat -c '%a' "$workdir/.apikey")" == "600" ]]
compgen -G "$workdir/.apikey.backup.*" >/dev/null

# A second pass must be idempotent and must not delete anything.
cp "$workdir/.apikey" "$workdir/before-second-pass"
APIKEY_FILE="$workdir/.apikey" "$repo_root/scripts/normalize-apikey.sh"
diff -u "$workdir/before-second-pass" "$workdir/.apikey"

printf 'lossless normalize-apikey tests passed\n'
