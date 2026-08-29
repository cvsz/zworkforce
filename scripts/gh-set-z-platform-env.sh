#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${GH_REPO:-cvsz/z-platform}"
ENVIRONMENT="${1:-staging}"
ENV_FILE="${2:-.env}"

case "$ENVIRONMENT" in
  staging|production) ;;
  *) echo "error: environment must be staging or production" >&2; exit 2 ;;
esac

command -v gh >/dev/null || { echo "error: GitHub CLI (gh) is required" >&2; exit 3; }
gh auth status >/dev/null
[[ -f "$ENV_FILE" ]] || { echo "error: environment file not found: $ENV_FILE" >&2; exit 2; }

declare -A VALUES=()
trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

while IFS= read -r raw || [[ -n "$raw" ]]; do
  raw="${raw%$'\r'}"
  line="$(trim "$raw")"
  [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
  [[ "$line" == export\ * ]] && line="${line#export }"
  [[ "$line" == *=* ]] || continue
  key="$(trim "${line%%=*}")"
  value="$(trim "${line#*=}")"
  if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
    value="${value:1:${#value}-2}"
  fi
  [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || { echo "error: invalid dotenv key: $key" >&2; exit 2; }
  VALUES["$key"]="$value"
done < "$ENV_FILE"

KNOWN_UNSAFE_SAMPLE_TOKEN="894d39b03373ff2306fb3d4d720372fc9d44ca3a099c61ec5905096915e81930"
if [[ "${VALUES[Z_PLATFORM_SERVICE_TOKEN]:-}" == "$KNOWN_UNSAFE_SAMPLE_TOKEN" || -z "${VALUES[Z_PLATFORM_SERVICE_TOKEN]:-}" ]]; then
  command -v openssl >/dev/null || { echo "error: openssl is required" >&2; exit 3; }
  VALUES[Z_PLATFORM_SERVICE_TOKEN]="$(openssl rand -hex 32)"
  echo "generated a fresh Z_PLATFORM_SERVICE_TOKEN" >&2
fi

SECRET_KEYS=(
  Z_PLATFORM_SERVICE_TOKEN NVIDIA_NIM_API_KEY GROQ_API_KEY CEREBRAS_API_KEY
  SAMBANOVA_API_KEY OPENROUTER_API_KEY GITHUB_MODELS_TOKEN MISTRAL_API_KEY
  CODESTRAL_API_KEY SCALEWAY_API_KEY GEMINI_API_KEY ZAI_API_KEY
  DASHSCOPE_API_KEY CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN
  OVHCLOUD_API_KEY OPENCODE_API_KEY DEEPSEEK_API_KEY KIMI_API_KEY
  WAFER_API_KEY FIREWORKS_API_KEY AI_GATEWAY_PROVIDER_TOKEN
  UPSTREAM_PROVIDERS_JSON
)

VARIABLE_KEYS=(
  NVIDIA_NIM_BASE_URL GROQ_BASE_URL CEREBRAS_BASE_URL SAMBANOVA_BASE_URL
  OPENROUTER_BASE_URL GITHUB_MODELS_BASE_URL MISTRAL_BASE_URL
  CODESTRAL_BASE_URL SCALEWAY_BASE_URL GEMINI_BASE_URL ZAI_BASE_URL
  ZAI_ANTHROPIC_BASE_URL DASHSCOPE_BASE_URL DASHSCOPE_INTL_BASE_URL
  CLOUDFLARE_WORKERS_AI_BASE_URL OVHCLOUD_BASE_URL OPENCODE_ZEN_BASE_URL
  OPENCODE_GO_BASE_URL DEEPSEEK_BASE_URL DEEPSEEK_ANTHROPIC_BASE_URL
  KIMI_BASE_URL KIMI_ANTHROPIC_BASE_URL WAFER_MESSAGES_URL FIREWORKS_BASE_URL
  LM_STUDIO_BASE_URL LLAMACPP_BASE_URL OLLAMA_BASE_URL OLLAMA_NATIVE_BASE_URL
  UPSTREAM_BASE_URL UPSTREAM_PROVIDER ZCHAT_PORT ZWALLET_PORT AI_GATEWAY_PORT
  AGENT_ORCHESTRATOR_PORT WORKSPACE_RUNTIME_PORT BILLING_LEDGER_PORT
  AGENT_PROVIDER_PORT ZCHAT_SESSION_TTL_SECONDS AGENT_TEST_FAILURE_INJECTION
  BILLING_LEDGER_URL AGENT_JOB_STORE_URL AGENT_QUEUE_URL AGENT_AUDIT_URL
  AGENT_IDENTITY_URL AGENT_SANDBOX_URL STAGING_SMOKE_ZCHAT_URL
  STAGING_SMOKE_ZWALLET_URL STAGING_SMOKE_AI_GATEWAY_URL
  STAGING_SMOKE_AGENT_ORCHESTRATOR_URL STAGING_SMOKE_WORKSPACE_RUNTIME_URL
  STAGING_SMOKE_BILLING_LEDGER_URL STAGING_SMOKE_AGENT_PROVIDER_URL
  STAGING_SMOKE_TEST_FAILURE_RETRY
)

set_secret() {
  local key="$1" value="${VALUES[$1]:-}"
  [[ -n "$value" ]] || return 0
  printf '%s' "$value" | gh secret set "$key" --repo "$REPO" --env "$ENVIRONMENT" --body -
  echo "set secret: $key"
}

set_variable() {
  local key="$1" value="${VALUES[$1]:-}"
  [[ -n "$value" ]] || return 0
  if [[ "$value" == *'{'*'}'* ]]; then
    echo "skip variable $key: unresolved template value" >&2
    return 0
  fi
  if [[ "$ENVIRONMENT" == "production" && "$value" =~ ^https?://(localhost|127\.0\.0\.1) ]]; then
    echo "skip variable $key: loopback URL is invalid for production" >&2
    return 0
  fi
  gh variable set "$key" --repo "$REPO" --env "$ENVIRONMENT" --body "$value"
  echo "set variable: $key"
}

for key in "${SECRET_KEYS[@]}"; do set_secret "$key"; done
for key in "${VARIABLE_KEYS[@]}"; do set_variable "$key"; done

cat <<INFO

Configured:
  gh secret list   --repo "$REPO" --env "$ENVIRONMENT"
  gh variable list --repo "$REPO" --env "$ENVIRONMENT"

Phase 6 readiness values not present in .env.example:
  Secrets: STAGING_READINESS_MANIFEST_JSON, STAGING_BEARER_TOKEN, STAGING_DECISION_RECORD_JSON
  Variables: STAGING_REVIEWER, INCIDENT_OWNER, ESCALATION_ROUTE, WATCH_WINDOW
  Production variable: PRODUCTION_APPROVER
INFO
