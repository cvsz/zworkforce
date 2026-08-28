#!/usr/bin/env bash
# Shared Cloudflare Terraform environment loader.
# This file is intended to be sourced by scripts in ../.

set -Eeuo pipefail

cloudflare_require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Required command not found: $command_name" >&2
    return 1
  }
}

cloudflare_load_terraform_env() {
  CLOUDFLARE_ROOT="${CLOUDFLARE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
  CLOUDFLARE_ENV_FILE="${CLOUDFLARE_ENV_FILE:-$CLOUDFLARE_ROOT/.env.cloudflare}"
  CLOUDFLARE_STACK="${CLOUDFLARE_STACK:-$CLOUDFLARE_ROOT/infrastructure/terraform/cloudflare}"

  [[ -f "$CLOUDFLARE_ENV_FILE" && ! -L "$CLOUDFLARE_ENV_FILE" ]] || {
    echo "Cloudflare environment must be a regular file: $CLOUDFLARE_ENV_FILE" >&2
    return 1
  }

  local mode
  mode="$(stat -c '%a' "$CLOUDFLARE_ENV_FILE")"
  (( (8#$mode & 8#077) == 0 )) || {
    echo "Cloudflare environment must not be group/world accessible: $CLOUDFLARE_ENV_FILE" >&2
    echo "Run: chmod 600 '$CLOUDFLARE_ENV_FILE'" >&2
    return 1
  }

  set -a
  # shellcheck disable=SC1090
  source "$CLOUDFLARE_ENV_FILE"
  set +a

  if [[ "${FORCE_ENABLE_ZEAZ_ONE:-false}" == "true" ]]; then
    ZEAZ_ONE_ENABLED=true
  fi
  if [[ "${FORCE_ENABLE_ZEAZ_ONE_API_ROUTE:-false}" == "true" ]]; then
    ZEAZ_ONE_API_ROUTE_ENABLED=true
  fi

  local key
  for key in \
    CLOUDFLARE_API_TOKEN \
    CLOUDFLARE_ACCOUNT_ID \
    CLOUDFLARE_ZONE_ID \
    CLOUDFLARE_TUNNEL_ID; do
    [[ -n "${!key:-}" ]] || {
      echo "Missing $key in $CLOUDFLARE_ENV_FILE" >&2
      return 1
    }
  done

  [[ -n "${PIEWDASH_ACCESS_ALLOWED_EMAILS:-}" ]] || {
    echo "Missing PIEWDASH_ACCESS_ALLOWED_EMAILS JSON array in $CLOUDFLARE_ENV_FILE" >&2
    return 1
  }

  CLOUDFLARE_TF_BIN="${TERRAFORM_BIN:-}"
  if [[ -z "$CLOUDFLARE_TF_BIN" ]]; then
    if [[ -x "$CLOUDFLARE_ROOT/tools/bin/terraform" ]]; then
      CLOUDFLARE_TF_BIN="$CLOUDFLARE_ROOT/tools/bin/terraform"
    elif command -v terraform >/dev/null 2>&1; then
      CLOUDFLARE_TF_BIN="$(command -v terraform)"
    fi
  fi
  command -v "$CLOUDFLARE_TF_BIN" >/dev/null 2>&1 || {
    echo "Terraform not found. See infrastructure/terraform/cloudflare/README.md" >&2
    return 1
  }

  export TF_IN_AUTOMATION=1
  export TF_INPUT=0
  export TF_VAR_cloudflare_api_token="$CLOUDFLARE_API_TOKEN"
  export TF_VAR_cloudflare_account_id="$CLOUDFLARE_ACCOUNT_ID"
  export TF_VAR_cloudflare_zone_id="$CLOUDFLARE_ZONE_ID"
  export TF_VAR_cloudflare_tunnel_id="$CLOUDFLARE_TUNNEL_ID"
  export TF_VAR_manage_tunnel_config="${MANAGE_TUNNEL_CONFIG:-false}"

  export TF_VAR_moopiew_hostname="${MOOPIEW_HOSTNAME:-moopiew.zeaz.dev}"
  export TF_VAR_moopiew_origin="${MOOPIEW_ORIGIN:-http://127.0.0.1:8080}"
  export TF_VAR_arin_hostname="${ARIN_HOSTNAME:-arin.zeaz.dev}"
  export TF_VAR_arin_origin="${ARIN_ORIGIN:-http://127.0.0.1:8080}"
  export TF_VAR_zttshop_hostname="${ZTTSHOP_HOSTNAME:-zttshop.zeaz.dev}"
  export TF_VAR_zttshop_origin="${ZTTSHOP_ORIGIN:-http://127.0.0.1:8080}"
  export TF_VAR_qwen_hostname="${QWEN_HOSTNAME:-qwen.zeaz.dev}"
  export TF_VAR_qwen_origin="${QWEN_ORIGIN:-http://127.0.0.1:8091}"
  export TF_VAR_chat_hostname="${CHAT_HOSTNAME:-chat.zeaz.dev}"
  export TF_VAR_chat_origin="${CHAT_ORIGIN:-http://127.0.0.1:3080}"
  export TF_VAR_piewdash_hostname="${PIEWDASH_HOSTNAME:-piewdash.zeaz.dev}"
  export TF_VAR_piewdash_origin="${PIEWDASH_ORIGIN:-http://127.0.0.1:80}"
  export TF_VAR_zdash_hostname="${ZDASH_HOSTNAME:-zdash.zeaz.dev}"
  export TF_VAR_zdash_origin="${ZDASH_ORIGIN:-http://127.0.0.1:18080}"
  export TF_VAR_zerp_hostname="${ZERP_HOSTNAME:-zerp.zeaz.dev}"
  export TF_VAR_zerp_origin="${ZERP_ORIGIN:-http://127.0.0.1:80}"
  export TF_VAR_cmeerp_hostname="${CMEERP_HOSTNAME:-cme.zeaz.dev}"
  export TF_VAR_cmeerp_origin="${CMEERP_ORIGIN:-http://127.0.0.1:8001}"
  export TF_VAR_zai_hostname="${ZAI_HOSTNAME:-zai.zeaz.dev}"
  export TF_VAR_zai_origin="${ZAI_ORIGIN:-http://127.0.0.1:8765}"
  export TF_VAR_auth_hostname="${AUTH_HOSTNAME:-auth.zeaz.dev}"
  export TF_VAR_auth_origin="${AUTH_ORIGIN:-http://127.0.0.1:8080}"
  export TF_VAR_zwf_hostname="${ZWF_HOSTNAME:-zwf.zeaz.dev}"
  export TF_VAR_zwf_api_hostname="${ZWF_API_HOSTNAME:-zwf-api.zeaz.dev}"
  export TF_VAR_zslog_hostname="${ZSLOG_HOSTNAME:-zslog.zeaz.dev}"
  export TF_VAR_zslog_origin="${ZSLOG_ORIGIN:-http://127.0.0.1:9581}"
  export TF_VAR_zwf_origin="${ZWF_ORIGIN:-http://127.0.0.1:9570}"
  export TF_VAR_studio_hostname="${STUDIO_HOSTNAME:-studio.zeaz.dev}"
  export TF_VAR_studio_origin="${STUDIO_ORIGIN:-http://127.0.0.1:3005}"
  export TF_VAR_zarvis_hostname="${ZARVIS_HOSTNAME:-zarvis.zeaz.dev}"
  export TF_VAR_zarvis_origin="${ZARVIS_ORIGIN:-http://127.0.0.1:9570}"
  export TF_VAR_zider_hostname="${ZIDER_HOSTNAME:-zider.zeaz.dev}"
  export TF_VAR_zider_origin="${ZIDER_ORIGIN:-http://127.0.0.1:8085}"
  export TF_VAR_piewdash_access_allowed_emails="$PIEWDASH_ACCESS_ALLOWED_EMAILS"

  export TF_VAR_enable_zeaz_one="${ZEAZ_ONE_ENABLED:-false}"
  export TF_VAR_enable_zeaz_one_api_route="${ZEAZ_ONE_API_ROUTE_ENABLED:-false}"
  export TF_VAR_zeaz_one_hostname="${ZEAZ_ONE_HOSTNAME:-one.zeaz.dev}"
  export TF_VAR_zeaz_one_origin="${ZEAZ_ONE_ORIGIN:-http://127.0.0.1:18081}"
  export TF_VAR_zeaz_one_api_hostname="${ZEAZ_ONE_API_HOSTNAME:-api.zeaz.dev}"
  export TF_VAR_zeaz_one_api_origin="${ZEAZ_ONE_API_ORIGIN:-http://127.0.0.1:18084}"
  export TF_VAR_zeaz_one_support_hostname="${ZEAZ_ONE_SUPPORT_HOSTNAME:-support.zeaz.dev}"
  export TF_VAR_zeaz_one_support_origin="${ZEAZ_ONE_SUPPORT_ORIGIN:-http://127.0.0.1:18083}"

  unset TF_VAR_zdash_access_allowed_emails || true
  if [[ -n "${ZDASH_ACCESS_ALLOWED_EMAILS:-}" ]]; then
    export TF_VAR_zdash_access_allowed_emails="$ZDASH_ACCESS_ALLOWED_EMAILS"
  fi

  export CLOUDFLARE_ROOT CLOUDFLARE_ENV_FILE CLOUDFLARE_STACK CLOUDFLARE_TF_BIN
}

cloudflare_terraform_init() {
  if [[ "${TERRAFORM_BACKEND_TYPE:-local}" == "r2" ]]; then
    "$CLOUDFLARE_ROOT/scripts/cloudflare-state.sh" init
  else
    "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" init
  fi
}
