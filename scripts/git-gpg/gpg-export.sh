#!/usr/bin/env bash
set -euo pipefail
EMAIL="${1:?Usage: $0 <email>}"
KEY_ID=$(gpg --list-secret-keys --keyid-format long 2>/dev/null | grep -B1 "$EMAIL" | grep sec | awk '{print $2}' | cut -d/ -f2)
if [[ -z "$KEY_ID" ]]; then
    echo "❌ No GPG key found for: $EMAIL"
    exit 1
fi
OUTPUT="${2:-gpg-public-key.asc}"
echo "📤 Exporting public key: $KEY_ID"
gpg --armor --export "$KEY_ID" > "$OUTPUT"
echo "✅ Saved to: $OUTPUT"
