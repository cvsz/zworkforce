#!/usr/bin/env bash
set -euo pipefail
EMAIL="${1:?Usage: $0 <email>}"
NAME="${2:-$(git config user.name || echo "AI Coder")}"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
GIT_CONFIG_GLOBAL="${GIT_CONFIG_GLOBAL:-${GPG_LOOPBACK_GIT_CONFIG:-$REPO_ROOT/.cache/z-platform-gitconfig}}"

mkdir -p "$(dirname "$GIT_CONFIG_GLOBAL")"
touch "$GIT_CONFIG_GLOBAL"
chmod 600 "$GIT_CONFIG_GLOBAL"
export GIT_CONFIG_GLOBAL

OLD_KEY_ID=$(git config --global user.signingkey || echo "")
[[ -n "$OLD_KEY_ID" ]] && echo "🔄 Current key: $OLD_KEY_ID" || echo "ℹ️  No current signing key"
echo "🔑 Generating new GPG key..."
gpg --batch --gen-key <<GNUPG
%no-protection
Key-Type: ed25519
Key-Curve: ed25519
Key-Usage: sign
Subkey-Type: ed25519
Subkey-Curve: ed25519
Subkey-Usage: sign
Name-Real: $NAME
Name-Email: $EMAIL
Expire-Date: 2y
%commit
GNUPG
NEW_KEY_ID=$(gpg --list-secret-keys --keyid-format long 2>/dev/null | grep -B1 "$EMAIL" | grep sec | awk '{print $2}' | cut -d/ -f2 | tail -1)
echo "✅ New key: $NEW_KEY_ID"
git config --global user.signingkey "$NEW_KEY_ID"
gpg --armor --export "$NEW_KEY_ID" > "gpg-public-key-$(date +%Y%m%d).asc"
echo "📤 Exported new public key"
echo "✅ Rotation complete. Upload new .asc to GitHub."
