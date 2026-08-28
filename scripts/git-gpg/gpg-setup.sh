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

echo "🪪 Setting up GPG for Git"
echo "   Email: $EMAIL"
echo "   Name:  $NAME"
echo ""
EXISTING_KEY=$(gpg --list-secret-keys --keyid-format long 2>/dev/null | grep -B1 "$EMAIL" | grep sec | awk '{print $2}' | cut -d/ -f2 || true)
if [[ -n "$EXISTING_KEY" ]]; then
    echo "✅ Found existing GPG key: $EXISTING_KEY"
    KEY_ID="$EXISTING_KEY"
else
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
    KEY_ID=$(gpg --list-secret-keys --keyid-format long 2>/dev/null | grep -B1 "$EMAIL" | grep sec | awk '{print $2}' | cut -d/ -f2)
    echo "✅ Generated new GPG key: $KEY_ID"
fi
git config --global user.signingkey "$KEY_ID"
git config --global commit.gpgsign true
git config --global tag.gpgsign true
git config --global gpg.program gpg
echo ""
echo "✅ Done. All future commits and tags will be signed."
