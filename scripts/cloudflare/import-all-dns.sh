#!/usr/bin/env bash
set -Eeo pipefail
umask 077

ROOT_DIR="$(git rev-parse --show-toplevel)"
CLOUDFLARE_ENV_FILE="$ROOT_DIR/.env.cloudflare"
CLOUDFLARE_STACK="$ROOT_DIR/infrastructure/terraform/cloudflare"

[[ -f "$CLOUDFLARE_ENV_FILE" ]] || {
  echo "ERROR: $CLOUDFLARE_ENV_FILE not found" >&2
  exit 1
}

# Source env without -u to avoid errors on placeholder values
set +u
source "$CLOUDFLARE_ENV_FILE"
set -u

export TF_VAR_cloudflare_api_token="$CLOUDFLARE_API_TOKEN"
export TF_VAR_cloudflare_account_id="$CLOUDFLARE_ACCOUNT_ID"
export TF_VAR_cloudflare_zone_id="$CLOUDFLARE_ZONE_ID"
export TF_VAR_cloudflare_tunnel_id="$CLOUDFLARE_TUNNEL_ID"
export TF_VAR_piewdash_access_allowed_emails="$PIEWDASH_ACCESS_ALLOWED_EMAILS"

# DNS records to import: resource_name hostname
DNS_RESOURCES=(
  "ai_dbc ai-dbc.zeaz.dev"
  "arin arin.zeaz.dev"
  "auth auth.zeaz.dev"
  "autoc autoc.zeaz.dev"
  "cmeerp cme.zeaz.dev"
  "coin zcoin.zeaz.dev"
  "core core.zeaz.dev"
  "dbc dbc.zeaz.dev"
  "ha_a ha-a.zeaz.dev"
  "ha_b ha-b.zeaz.dev"
  "laps laps.zeaz.dev"
  "license license.zeaz.dev"
  "llmwiki llmwiki.zeaz.dev"
  "mcp mcp.zeaz.dev"
  "moopiew moopiew.zeaz.dev"
  "piewdash piewdash.zeaz.dev"
  "prod prod.zeaz.dev"
  "qwen qwen.zeaz.dev"
  "studio studio.zeaz.dev"
  "zaffiliate zaffiliate.zeaz.dev"
  "zai zai.zeaz.dev"
  "zany zany.zeaz.dev"
  "zarvis zarvis.zeaz.dev"
  "zksato zksato.zeaz.dev"
  "zksato_api zksato-api.zeaz.dev"
  "zksato_dash zksato-dash.zeaz.dev"
  "zmovie zmovie.zeaz.dev"
  "zneon zneon.zeaz.dev"
  "zsme zsme.zeaz.dev"
  "zttato zttato.zeaz.dev"
  "zttshop zttshop.zeaz.dev"
  "zwf_api zwf-api.zeaz.dev"
  "zworkforce zworkforce.zeaz.dev"
)

# Zero Trust Access Applications to import: resource_name domain
ACCESS_APPS=(
  "ai_dbc ai-dbc.zeaz.dev"
  "autoc autoc.zeaz.dev"
  "coin zcoin.zeaz.dev"
  "dbc dbc.zeaz.dev"
  "piewdash piewdash.zeaz.dev"
  "prod prod.zeaz.dev"
  "zany zany.zeaz.dev"
  "zdash zdash.zeaz.dev"
  "zsme zsme.zeaz.dev"
)

import_dns_record() {
  local res_name="$1"
  local hostname="$2"
  echo "==> Importing cloudflare_dns_record.$res_name ($hostname)..."
  local record_id
  record_id="$(curl -s --fail \
    "https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/dns_records?name=${hostname}" \
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')")"
  if [[ -z "$record_id" ]]; then
    echo "WARNING: No DNS record found for $hostname, skipping."
    return 0
  fi
  terraform -chdir="$CLOUDFLARE_STACK" import -lock=false \
    "cloudflare_dns_record.$res_name" "${CLOUDFLARE_ZONE_ID}/${record_id}" 2>&1 || true
}

import_access_app() {
  local res_name="$1"
  local domain="$2"
  echo "==> Importing cloudflare_zero_trust_access_application.$res_name ($domain)..."
  local app_id
  app_id="$(curl -s --fail \
    "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/access/apps?domain=${domain}" \
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')")"
  if [[ -z "$app_id" ]]; then
    echo "WARNING: No Access app found for $domain, skipping."
    return 0
  fi
  terraform -chdir="$CLOUDFLARE_STACK" import -lock=false \
    "cloudflare_zero_trust_access_application.$res_name" "$app_id" 2>&1 || true
}

echo "=== Importing DNS records ==="
for entry in "${DNS_RESOURCES[@]}"; do
  set -- $entry
  import_dns_record "$1" "$2"
done

echo ""
echo "=== Importing Zero Trust Access Applications ==="
for entry in "${ACCESS_APPS[@]}"; do
  set -- $entry
  import_access_app "$1" "$2"
done

echo ""
echo "=== All imports done. Current state: ==="
terraform -chdir="$CLOUDFLARE_STACK" state list 2>&1
