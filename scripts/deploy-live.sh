#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "--- Generating new secrets for .env ---"
    POSTGRES_PWD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    
    cat <<EOF > "$ENV_FILE"
ZWORKFORCE_POSTGRES_PASSWORD=$POSTGRES_PWD
ZWORKFORCE_API_KEYS=$API_KEY:superadmin:default:bootstrap:*
ZWORKFORCE_IMAGE=ghcr.io/cvsz/zworkforce:v3.0.4
EOF
    chmod 600 "$ENV_FILE"
    echo "--- Secrets generated and saved to $ENV_FILE ---"
else
    echo "--- Using existing .env file ---"
fi

echo "--- Bringing zWorkforce production stack online ---"
docker compose up -d

echo "--- Services Status ---"
docker compose ps
