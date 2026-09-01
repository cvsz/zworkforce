#!/usr/bin/env bash
# // ZeaZDev [Prisma Client Generation Script] //
# // Project: Auto Bot Trader i18n //
# // Version: 1.0.0 //
# // Author: ZeaZDev Meta-Intelligence (Generated) //
# // --- DO NOT EDIT HEADER --- //

set -euo pipefail

# Support custom schema path or use default
SCHEMA_PATH="${1:-${PRISMA_SCHEMA_PATH:-/app/prisma/schema.prisma}}"

echo "[*] Generating Prisma Python client..."
echo "[*] Schema path: $SCHEMA_PATH"

# Check if schema exists
if [ ! -f "$SCHEMA_PATH" ]; then
    echo "[!] ERROR: Prisma schema not found at $SCHEMA_PATH"
    echo "[!] Checked paths:"
    echo "    - /app/prisma/schema.prisma"
    echo "    - /app/apps/backend/prisma/schema.prisma"
    exit 1
fi

# Generate Prisma client
echo "[*] Running: prisma generate --schema $SCHEMA_PATH"
prisma generate --schema "$SCHEMA_PATH"

echo "[✓] Prisma client generation completed successfully"
