#!/usr/bin/env bash
set -euo pipefail
KEY_ID="${1:?Usage: $0 <key-id>}"
echo "⚠️  WARNING: This will PERMANENTLY revoke key: $KEY_ID"
read -rp "   Type 'REVOKE' to confirm: " confirm
if [[ "$confirm" != "REVOKE" ]]; then echo "❌ Cancelled"; exit 1; fi
REVOKED_ASC="revoked-${KEY_ID}.asc"
gpg --output "$REVOKED_ASC" --gen-revoke "$KEY_ID" <<GNUPG
y
1
Key rotation
0
y
GNUPG
echo "✅ Revocation cert saved: $REVOKED_ASC"
