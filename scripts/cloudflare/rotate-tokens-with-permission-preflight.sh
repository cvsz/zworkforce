#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cloudflare/lib/env-scope.sh
source "$SCRIPT_DIR/lib/env-scope.sh"
cf_load_cloudflare_env_scope
cd "$PROJECT_ROOT"

CACHE_DIR="${CACHE_DIR:-./.cache/cloudflare-permissions}"
REFRESH=false
OFFLINE=false

log(){ cf_env_log "$*"; }
warn(){ cf_env_warn "$*"; }
die(){ cf_env_die "$*"; }

contains_arg(){
  local wanted="$1"; shift
  local arg
  for arg in "$@"; do [[ "$arg" == "$wanted" ]] && return 0; done
  return 1
}

for arg in "$@"; do
  [[ "$arg" == "--refresh-permissions" ]] && REFRESH=true
  [[ "$arg" == "--offline" ]] && OFFLINE=true
done

if ! contains_arg --regenerate "$@"; then
  exec bash scripts/cloudflare/run-token-rotation.sh "$@"
fi

command -v jq >/dev/null 2>&1 || die "jq is required"
if $OFFLINE; then
  cf_require_env CLOUDFLARE_ACCOUNT_ID || exit 1
else
  cf_require_env CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_BOOTSTRAP_TOKEN || exit 1
fi

cache="$CACHE_DIR/account-token-permission-groups.${CLOUDFLARE_ACCOUNT_ID}.json"
mkdir -p "$CACHE_DIR"

if $OFFLINE; then
  if [[ ! -s "$cache" ]]; then
    warn "offline preflight: no cached permission-group data at $cache"
    printf '{"success":true,"result":[]}\n' > "$cache"
  fi
  log "offline preflight: using cached permission-group data"
else
  command -v curl >/dev/null 2>&1 || die "curl is required"
  log "Running discover-permission-groups.sh preflight check..."
  opts=()
  $REFRESH && opts+=(--refresh)
  bash "$SCRIPT_DIR/discover-permission-groups.sh" "${opts[@]}" >/dev/null || die "Permission-group discovery preflight failed."
  [[ -f "$cache" ]] || die "Preflight completed but cache file not found at $cache"
fi

pick_permission(){
  local kind="$1"
  jq -r --arg kind "$kind" '
    def txt: ([.name // "", .description // "", .scope // "", (.scopes // [] | tostring), (.resource_groups // [] | tostring)] | join(" "));
    def has($re): (txt | test($re));
    def named($re): ((.name // "") | test($re));
    def score($k):
      if $k == "dns" then
        if named("(?i)^DNS Write$") then 0
        elif named("(?i)^DNS View Write$") then 1
        elif has("(?i)dns.*(write|edit)") and (has("(?i)settings") | not) and (has("(?i)(dns firewall|account)") | not) then 10
        else 999 end
      elif $k == "waf" then
        if has("(?i)^Account WAF Write$") or has("(?i)^Zone.*WAF.*Write$") then 0
        elif has("(?i)(waf|web application firewall|rulesets?).*(write|edit)") then 1
        else 999 end
      elif $k == "zt" then
        if has("(?i)^Access: Apps and Policies Write$") then 0
        elif has("(?i)(Zero Trust|Access:).*(write|edit)") and (has("(?i)(Report|Read|PII|Resilience|Seats)") | not) then 1
        else 999 end
      elif $k == "workers" then
        if has("(?i)^Workers Scripts Write$") and (has("(?i)(AI|CI|KV|Containers|Observability|Routes|Tail|Websearch|R2)") | not) then 0
        elif has("(?i)(Workers Scripts|Workers).*(write|edit)") and (has("(?i)(AI|CI|KV|Containers|Observability|Routes|Tail|Websearch|R2)") | not) then 1
        else 999 end
      elif $k == "workers_routes" then if named("(?i)^Workers Routes Write$") then 0 else 999 end
      elif $k == "pages" then if named("(?i)^Pages Write$") then 0 else 999 end
      elif $k == "tunnel" then if named("(?i)^Cloudflare Tunnel Write$") then 0 else 999 end
      elif $k == "r2" then if named("(?i)^Workers R2 Storage Write$") then 0 else 999 end
      elif $k == "d1" then if named("(?i)^D1 Write$") then 0 else 999 end
      elif $k == "audit" then if named("(?i)^AI Audit Write$") then 0 else 999 end
      elif $k == "ai_gateway" then if named("(?i)^AI Gateway Write$") then 0 else 999 end
      else 999 end;
    (.result // [])
    | map(. + {__score: score($kind)})
    | map(select(.__score < 999))
    | sort_by(.__score, .name)
    | .[0].id // empty
  ' "$cache"
}

export_if_missing(){
  local key="$1" val="$2" label="$3"
  if [[ -z "${!key:-}" && -n "$val" ]]; then
    export "$key=$val"
    log "resolved $label permission-group override: $val"
  elif [[ -n "${!key:-}" ]]; then
    log "using existing $key override"
  else
    warn "could not resolve $label permission-group override"
  fi
}

export_if_missing CLOUDFLARE_DNS_PERMISSION_GROUP_ID "$(pick_permission dns)" dns
export_if_missing CLOUDFLARE_ZT_PERMISSION_GROUP_ID "$(pick_permission zt)" zt
export_if_missing CLOUDFLARE_WORKERS_PERMISSION_GROUP_ID "$(pick_permission workers)" workers
export_if_missing CLOUDFLARE_WORKERS_ROUTES_PERMISSION_GROUP_ID "$(pick_permission workers_routes)" workers-routes
export_if_missing CLOUDFLARE_PAGES_PERMISSION_GROUP_ID "$(pick_permission pages)" pages
export_if_missing CLOUDFLARE_WAF_PERMISSION_GROUP_ID "$(pick_permission waf)" waf
export_if_missing CLOUDFLARE_TUNNEL_PERMISSION_GROUP_ID "$(pick_permission tunnel)" tunnel
export_if_missing CLOUDFLARE_R2_PERMISSION_GROUP_ID "$(pick_permission r2)" r2
export_if_missing CLOUDFLARE_D1_PERMISSION_GROUP_ID "$(pick_permission d1)" d1
export_if_missing CLOUDFLARE_AUDIT_PERMISSION_GROUP_ID "$(pick_permission audit)" audit
export_if_missing CLOUDFLARE_AI_GATEWAY_PERMISSION_GROUP_ID "$(pick_permission ai_gateway)" ai-gateway

exec bash scripts/cloudflare/run-token-rotation.sh "$@"
