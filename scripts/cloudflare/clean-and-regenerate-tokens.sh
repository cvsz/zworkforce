#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

API_BASE="${CLOUDFLARE_API_BASE:-https://api.cloudflare.com/client/v4}"
AUDIT_LOG="${AUDIT_LOG:-./.cloudflare-token-audit.log}"
BACKUP_DIR="${BACKUP_DIR:-./.cloudflare-backups}"
CACHE_DIR="${CACHE_DIR:-./.cache/cloudflare-permissions}"
DEFAULT_OUT="${DEFAULT_OUT:-.env.cloudflare}"
TOKEN_QUOTA="${TOKEN_QUOTA:-50}"
PRESERVE_TOKEN_NAME_REGEX="${PRESERVE_TOKEN_NAME_REGEX:-(^|[-_])(audit|ai[-_]?gateway|bootstrap|admin)([-_]|$)}"

NAME_FILTER=""
NAME_REGEX_FILTER=""
UNUSED_DAYS=0
KEEP_MOST=1
DO_BACKUP=false
DRY_RUN=false
ASSUME_YES=false
REGENERATE=false
TYPES_CSV=""
OUT_FILE="$DEFAULT_OUT"
PERM_ID_OVERRIDE=""
REFRESH_PERMISSIONS=false
OFFLINE=false

usage(){
  cat <<USAGE
Usage: CLOUDFLARE_ACCOUNT_ID=<id> CLOUDFLARE_BOOTSTRAP_TOKEN=<token> $0 [options]

Cleaning:
  --name <token-name>    Restrict cleanup to an exact token name
  --name-regex <regex>   Restrict cleanup to token names matching regex
  --unused-days <N>      Revoke tokens inactive for more than N days; 0 disables
  --keep-most <N>        Keep N newest tokens per name; revoke older duplicates

Safety:
  --backup               Save token list before mutations
  --dry-run              Preview only; no API mutations
  --yes                  Required for live revocation/regeneration

Regeneration:
  --regenerate           Create replacement account tokens for --types
  --types <csv|all>      dns,zt,workers,pages,waf,tunnel,r2,d1 or all
  --write <file>         Write generated tokens to env file
  --perm-id <id>         Override permission-group ID for every generated token
  --refresh-permissions  Refresh permission-group cache before regeneration
  --offline              Do not call Cloudflare APIs; use cache or empty previews

Notes:
  Canonical env names use CLOUDFLARE_*.
  CLOUDFLARE_AUDIT_TOKEN and CLOUDFLARE_AI_GATEWAY_TOKEN are optional.
  Bootstrap/audit/AI-gateway tokens are never revoked by default.

  --help, -h             Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) shift; NAME_FILTER="${1:-}"; shift || true ;;
    --name-regex) shift; NAME_REGEX_FILTER="${1:-}"; shift || true ;;
    --unused-days) shift; UNUSED_DAYS="${1:-0}"; shift || true ;;
    --keep-most) shift; KEEP_MOST="${1:-1}"; shift || true ;;
    --backup) DO_BACKUP=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --yes) ASSUME_YES=true; shift ;;
    --regenerate) REGENERATE=true; shift ;;
    --types) shift; TYPES_CSV="${1:-}"; shift || true ;;
    --write) shift; OUT_FILE="${1:-$DEFAULT_OUT}"; shift || true ;;
    --perm-id) shift; PERM_ID_OVERRIDE="${1:-}"; shift || true ;;
    --refresh-permissions) REFRESH_PERMISSIONS=true; shift ;;
    --offline) OFFLINE=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "WARN: unknown option: $1" >&2; shift ;;
  esac
done

log(){ printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
warn(){ log "WARN: $*" >&2; }
die(){ log "ERROR: $*" >&2; exit 1; }
log_err(){ log "$*" >&2; }
has(){ command -v "$1" >/dev/null 2>&1; }

has jq || die "jq is required"
if ! $OFFLINE; then
  has curl || die "curl is required"
fi
[[ "$UNUSED_DAYS" =~ ^[0-9]+$ ]] || die "--unused-days must be a non-negative integer"
[[ "$KEEP_MOST" =~ ^[0-9]+$ ]] || die "--keep-most must be a non-negative integer"
[[ "$TOKEN_QUOTA" =~ ^[0-9]+$ ]] || die "TOKEN_QUOTA must be a non-negative integer"

if $OFFLINE; then
  : "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID must be exported}"
else
  : "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID must be exported}"
  : "${CLOUDFLARE_BOOTSTRAP_TOKEN:?CLOUDFLARE_BOOTSTRAP_TOKEN must be exported}"
fi

cf_request(){
  local method="$1" endpoint="$2" payload="${3:-}" body_file err_file http_code curl_rc body err ok
  body_file="$(mktemp)"
  err_file="$(mktemp)"

  set +e
  if [[ -n "$payload" ]]; then
    http_code="$(curl -sS -o "$body_file" -w '%{http_code}' \
      -X "$method" "${API_BASE}${endpoint}" \
      -H "Authorization: Bearer ${CLOUDFLARE_BOOTSTRAP_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "$payload" 2>"$err_file")"
  else
    http_code="$(curl -sS -o "$body_file" -w '%{http_code}' \
      -X "$method" "${API_BASE}${endpoint}" \
      -H "Authorization: Bearer ${CLOUDFLARE_BOOTSTRAP_TOKEN}" \
      -H "Content-Type: application/json" 2>"$err_file")"
  fi
  curl_rc=$?
  set -e

  body="$(cat "$body_file")"
  err="$(cat "$err_file")"
  rm -f "$body_file" "$err_file"

  if [[ "$curl_rc" -ne 0 ]]; then
    die "Cloudflare curl failed: method=$method endpoint=$endpoint rc=$curl_rc http=${http_code:-000} stderr=${err:-<empty>}"
  fi
  if [[ -z "$body" ]]; then
    die "Cloudflare API returned empty body: method=$method endpoint=$endpoint http=${http_code:-000}"
  fi
  if [[ ! "$http_code" =~ ^2[0-9][0-9]$ ]]; then
    if printf '%s' "$body" | jq -e . >/dev/null 2>&1; then
      die "Cloudflare API HTTP $http_code: $(printf '%s' "$body" | jq -c '{errors:(.errors // []),messages:(.messages // [])}')"
    fi
    die "Cloudflare API HTTP $http_code: $body"
  fi

  ok="$(printf '%s' "$body" | jq -r '.success // false' 2>/dev/null || printf 'false')"
  [[ "$ok" == "true" ]] || die "Cloudflare API error: $(printf '%s' "$body" | jq -c '.errors // []' 2>/dev/null || printf '%s' "$body")"
  printf '%s' "$body"
}

fetch_token_list(){
  cf_request GET "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens"
}

permission_cache_file(){
  mkdir -p "$CACHE_DIR"
  printf '%s/account-token-permission-groups.%s.json' "$CACHE_DIR" "$CLOUDFLARE_ACCOUNT_ID"
}

fetch_permission_groups(){
  local cache script_dir
  cache="$(permission_cache_file)"
  if $OFFLINE; then
    if [[ ! -s "$cache" ]]; then
      printf '{"success":true,"result":[]}\n' > "$cache"
      chmod 600 "$cache"
      warn "offline mode: permission-group cache missing; using empty cache at $cache"
    fi
    printf '%s' "$cache"
    return 0
  fi
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local opts=()
  [[ "$REFRESH_PERMISSIONS" == "true" ]] && opts+=(--refresh)
  bash "${script_dir}/discover-permission-groups.sh" "${opts[@]}" >/dev/null || die "Permission-group discovery failed"
  [[ -s "$cache" ]] || printf '{"success":true,"result":[]}\n' > "$cache"
  printf '%s' "$cache"
}

resolve_permission_id(){
  local token_type="$1" cache pattern env_key explicit
  case "$token_type" in
    dns) env_key="CLOUDFLARE_DNS_PERMISSION_GROUP_ID"; pattern='(?i)^dns write\b' ;;
    zt) env_key="CLOUDFLARE_ZT_PERMISSION_GROUP_ID"; pattern='(?i)\bZero Trust\b.*Write' ;;
    workers) env_key="CLOUDFLARE_WORKERS_PERMISSION_GROUP_ID"; pattern='(?i)\bWorkers Scripts?\b.*Write' ;;
    pages) env_key="CLOUDFLARE_PAGES_PERMISSION_GROUP_ID"; pattern='(?i)^Pages Write\b' ;;
    waf) env_key="CLOUDFLARE_WAF_PERMISSION_GROUP_ID"; pattern='(?i)(waf.*(write|edit)|rulesets.*(write|edit)|firewall.*(write|edit))' ;;
    tunnel) env_key="CLOUDFLARE_TUNNEL_PERMISSION_GROUP_ID"; pattern='(?i)(tunnel.*(write|edit)|cloudflare tunnel.*(write|edit))' ;;
    r2) env_key="CLOUDFLARE_R2_PERMISSION_GROUP_ID"; pattern='(?i)\bR2 Storage\b.*Write' ;;
    d1) env_key="CLOUDFLARE_D1_PERMISSION_GROUP_ID"; pattern='(?i)(d1.*(write|edit))' ;;
    *) return 1 ;;
  esac

  explicit="${!env_key:-}"
  [[ -n "$explicit" ]] && { printf '%s' "$explicit"; return 0; }
  [[ -n "$PERM_ID_OVERRIDE" ]] && { printf '%s' "$PERM_ID_OVERRIDE"; return 0; }

  cache="$(fetch_permission_groups)"
  [[ -f "$cache" ]] || die "permission-group cache file not found: $cache"
  jq -r --arg re "$pattern" '
    (.result // [])
    | map(select(([.name // "", .description // "", .scope // "", (.scopes // [] | tostring), (.resource_groups // [] | tostring)] | join(" ")) | test($re)))
    | .[0].id // empty
  ' "$cache"
}

resolve_workers_routes_permission_id(){
  local cache explicit
  explicit="${CLOUDFLARE_WORKERS_ROUTES_PERMISSION_GROUP_ID:-}"
  [[ -n "$explicit" ]] && { printf '%s' "$explicit"; return 0; }

  cache="$(fetch_permission_groups)"
  [[ -f "$cache" ]] || die "permission-group cache file not found: $cache"
  jq -r '
    (.result // [])
    | map(select((.name // "") | test("(?i)^Workers Routes Write$")))
    | .[0].id // empty
  ' "$cache"
}

backup_json(){
  local json="$1" label="${2:-tokens}" ts file
  mkdir -p "$BACKUP_DIR"
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  file="$BACKUP_DIR/${label}.${ts}.json"
  printf '%s\n' "$json" > "$file"
  chmod 600 "$file"
  log "backup saved: $file"
}

audit(){
  local name="$1" id="$2" action="$3"; shift 3
  touch "$AUDIT_LOG"
  chmod 600 "$AUDIT_LOG"
  printf '%s\tname:%s\tid:%s\taction:%s%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$name" "$id" "$action" "${*:+ $*}" >> "$AUDIT_LOG"
}

env_file_value(){
  local file="$1" key="$2"
  [[ -f "$file" ]] || return 0
  awk -F= -v k="$key" '$1 == k {v=$0; sub(/^[^=]*=/, "", v); gsub(/^"|"$/, "", v); print v}' "$file" | tail -n 1
}

write_optional_env(){
  local key="$1" value="$2"
  [[ -n "${value//[[:space:]]/}" ]] || return 0
  printf '%s="%s"\n' "$key" "$value"
}

redact_env_stream(){
  awk '
    /^[[:space:]]*(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*=/ {
      assignment = $0
      key = assignment
      sub(/^[[:space:]]*(export[[:space:]]+)?/, "", key)
      sub(/=.*/, "", key)
      normalized = toupper(key)
      if (normalized ~ /(TOKEN|SECRET|PASSWORD|PRIVATE_KEY|ACCESS_KEY|API_KEY|AUTHORIZATION|CREDENTIAL)/) {
        prefix = assignment
        sub(/=.*/, "=", prefix)
        print prefix "\"<redacted>\""
        next
      }
    }
    { print }
  '
}

epoch_of(){
  local ts="${1:-}"
  [[ -z "$ts" || "$ts" == "null" ]] && { echo 0; return; }
  date -u -d "$ts" +%s 2>/dev/null || echo 0
}

log "fetching token list"
if $OFFLINE; then
  token_cache="${CACHE_DIR}/account-tokens.${CLOUDFLARE_ACCOUNT_ID}.json"
  if [[ -s "$token_cache" ]]; then
    TOKEN_LIST_JSON="$(cat "$token_cache")"
    log "offline mode: using cached token list at $token_cache"
  else
    TOKEN_LIST_JSON='{"success":true,"result":[]}'
    warn "offline mode: no cached token list found; using empty preview"
  fi
else
  TOKEN_LIST_JSON="$(fetch_token_list)"
  $DO_BACKUP && backup_json "$TOKEN_LIST_JSON" tokens
  mkdir -p "$CACHE_DIR"
  printf '%s\n' "$TOKEN_LIST_JSON" > "${CACHE_DIR}/account-tokens.${CLOUDFLARE_ACCOUNT_ID}.json"
  chmod 600 "${CACHE_DIR}/account-tokens.${CLOUDFLARE_ACCOUNT_ID}.json" 2>/dev/null || true
fi

mapfile -t ALL_TOKENS < <(
  printf '%s' "$TOKEN_LIST_JSON" | jq -r '(.result // [])[] | [(.id // ""), (.name // ""), (.created_at // ""), (.last_used_at // "")] | @tsv'
)

now_epoch="$(date -u +%s)"
cutoff_epoch=0
if [[ "$UNUSED_DAYS" -gt 0 ]]; then
  cutoff_epoch=$(( now_epoch - UNUSED_DAYS * 24 * 3600 ))
fi

declare -a CANDIDATES=()
declare -a TO_REVOKE=()

for line in "${ALL_TOKENS[@]}"; do
  IFS=$'\t' read -r id name created last_used <<< "$line"
  [[ -z "$id" ]] && continue
  [[ -n "$NAME_FILTER" && "$name" != "$NAME_FILTER" ]] && continue
  [[ -n "$NAME_REGEX_FILTER" && ! "$name" =~ $NAME_REGEX_FILTER ]] && continue
  if [[ -n "$name" ]] && [[ "$name" =~ $PRESERVE_TOKEN_NAME_REGEX ]]; then
    log "preserving token from cleanup by name policy: $name"
    continue
  fi
  last_epoch=0
  [[ -n "$last_used" && "$last_used" != "null" ]] && last_epoch="$(epoch_of "$last_used")"
  [[ "$last_epoch" -eq 0 && -n "$created" && "$created" != "null" ]] && last_epoch="$(epoch_of "$created")"
  CANDIDATES+=("$id|$name|$last_epoch|$created|$last_used")
done

if [[ "${#CANDIDATES[@]}" -gt 0 ]]; then
  mapfile -t NAMES < <(printf '%s\n' "${CANDIDATES[@]}" | awk -F'|' '{print $2}' | sort -u)
else
  NAMES=()
fi

for name in "${NAMES[@]}"; do
  mapfile -t sorted_ids < <(
    printf '%s\n' "${CANDIDATES[@]}" | awk -F'|' -v name="$name" '$2 == name { print $3 "\t" $1 }' | sort -k1,1rn | awk -F'\t' '{print $2}'
  )
  idx=0
  for rid in "${sorted_ids[@]}"; do
    [[ "$idx" -ge "$KEEP_MOST" ]] && TO_REVOKE+=("$rid")
    idx=$((idx + 1))
  done
done

if [[ "$cutoff_epoch" -gt 0 ]]; then
  for entry in "${CANDIDATES[@]}"; do
    IFS='|' read -r id name last_epoch created last_used <<< "$entry"
    [[ "$last_epoch" -gt 0 && "$last_epoch" -lt "$cutoff_epoch" ]] && TO_REVOKE+=("$id")
  done
fi

declare -A seen=()
declare -a FINAL_REVOKE=()
for id in "${TO_REVOKE[@]}"; do
  [[ -z "$id" ]] && continue
  if [[ -z "${seen[$id]:-}" ]]; then
    FINAL_REVOKE+=("$id")
    seen[$id]=1
  fi
done

token_field(){
  printf '%s' "$TOKEN_LIST_JSON" | jq -r --arg ID "$1" --arg F "$2" '(.result // [])[] | select(.id == $ID) | .[$F] // ""'
}

if $DRY_RUN; then
  log "DRY-RUN: ${#FINAL_REVOKE[@]} token(s) would be revoked"
  for id in "${FINAL_REVOKE[@]}"; do
    printf '  %-38s name=%-30s created=%s last_used=%s\n' "$id" "$(token_field "$id" name)" "$(token_field "$id" created_at)" "$(token_field "$id" last_used_at)"
  done
else
  if [[ "${#FINAL_REVOKE[@]}" -gt 0 ]]; then
    log "${#FINAL_REVOKE[@]} token(s) selected for revocation"
    for id in "${FINAL_REVOKE[@]}"; do
      printf '  %-38s name=%-30s created=%s last_used=%s\n' "$id" "$(token_field "$id" name)" "$(token_field "$id" created_at)" "$(token_field "$id" last_used_at)"
    done
    [[ "$ASSUME_YES" == "true" ]] || die "refusing live revocation without --yes"
    $DO_BACKUP && backup_json "$TOKEN_LIST_JSON" tokens.pre-revoke
    for id in "${FINAL_REVOKE[@]}"; do
      name="$(token_field "$id" name)"
      cf_request DELETE "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/${id}" >/dev/null
      log "revoked $id ($name)"
      audit "$name" "$id" revoked
    done
  else
    log "no tokens matched revocation criteria"
  fi
fi

$REGENERATE || { log "done"; exit 0; }
[[ -n "$TYPES_CSV" ]] || { warn "--regenerate set but --types missing; skipping"; exit 0; }
[[ "$ASSUME_YES" == "true" || "$DRY_RUN" == "true" ]] || die "refusing token regeneration without --yes"

if [[ "$TYPES_CSV" == "all" ]]; then
  TYPES_CSV="dns,zt,workers,pages,waf,tunnel,r2,d1"
fi

declare -A TOKEN_NAME_MAP=(
  [dns]="zeaz-dns-token"
  [zt]="zeaz-zt-token"
  [workers]="zeaz-workers-token"
  [pages]="zeaz-pages-token"
  [waf]="zeaz-waf-token"
  [tunnel]="zeaz-tunnel-token"
  [r2]="zeaz-r2-token"
  [d1]="zeaz-d1-token"
  [audit]="zeaz-audit-token"
  [ai_gateway]="zeaz-ai-gateway-token"
)

declare -A RESOURCE_MAP=(
  [dns]="com.cloudflare.api.account.zone.${CLOUDFLARE_ZONE_ID:-}"
  [waf]="com.cloudflare.api.account.zone.${CLOUDFLARE_ZONE_ID:-}"
  [zt]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
  [workers]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
  [pages]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
  [tunnel]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
  [r2]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
  [d1]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
  [audit]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
  [ai_gateway]="com.cloudflare.api.account.${CLOUDFLARE_ACCOUNT_ID}"
)

declare -A ENV_KEY_MAP=(
  [dns]="CLOUDFLARE_DNS_TOKEN"
  [zt]="CLOUDFLARE_ZT_TOKEN"
  [workers]="CLOUDFLARE_WORKERS_TOKEN"
  [pages]="CLOUDFLARE_PAGES_TOKEN"
  [waf]="CLOUDFLARE_WAF_TOKEN"
  [tunnel]="CLOUDFLARE_TUNNEL_TOKEN"
  [r2]="CLOUDFLARE_R2_TOKEN"
  [d1]="CLOUDFLARE_D1_TOKEN"
  [audit]="CLOUDFLARE_AUDIT_TOKEN"
  [ai_gateway]="CLOUDFLARE_AI_GATEWAY_TOKEN"
)

IFS=',' read -r -a TYPES_ARR <<< "$TYPES_CSV"
declare -A GENERATED=()

for t in "${TYPES_ARR[@]}"; do
  t="${t// /}"
  [[ -z "$t" ]] && continue
  [[ -n "${TOKEN_NAME_MAP[$t]:-}" ]] || { warn "unknown token type: $t"; continue; }

  if [[ "$t" == "dns" || "$t" == "waf" ]]; then
    [[ -n "${CLOUDFLARE_ZONE_ID:-}" ]] || die "CLOUDFLARE_ZONE_ID is required for $t token"
  fi

  perm="$(resolve_permission_id "$t")"
  [[ -n "$perm" ]] || { warn "could not resolve permission-group ID for $t; skipping. Set CLOUDFLARE_${t^^}_PERMISSION_GROUP_ID or pass --perm-id."; continue; }

  current_count="$(printf '%s' "$TOKEN_LIST_JSON" | jq '(.result // []) | length')"
  [[ "$current_count" -lt "$TOKEN_QUOTA" ]] || die "token quota reached ($current_count/$TOKEN_QUOTA)"

  if [[ "$t" == "workers" ]]; then
    route_perm="$(resolve_workers_routes_permission_id)"
    [[ -n "$route_perm" ]] || { warn "could not resolve Workers Routes Write permission-group ID; zeaz-workers-token will not be able to update routes"; }
    if [[ -n "$route_perm" ]]; then
      payload="$(jq -n \
        --arg name "${TOKEN_NAME_MAP[$t]}" \
        --arg script_resource "${RESOURCE_MAP[$t]}" \
        --arg route_resource "com.cloudflare.api.account.zone.${CLOUDFLARE_ZONE_ID:-}" \
        --arg script_perm "$perm" \
        --arg route_perm "$route_perm" \
        '{name:$name, policies:[
          {effect:"allow", resources:{($script_resource):"*"}, permission_groups:[{id:$script_perm}]},
          {effect:"allow", resources:{($route_resource):"*"}, permission_groups:[{id:$route_perm}]}
        ]}')"
    else
      payload="$(jq -n --arg name "${TOKEN_NAME_MAP[$t]}" --arg resource "${RESOURCE_MAP[$t]}" --arg perm "$perm" '{name:$name, policies:[{effect:"allow", resources:{($resource):"*"}, permission_groups:[{id:$perm}]}]}')"
    fi
  else
    payload="$(jq -n --arg name "${TOKEN_NAME_MAP[$t]}" --arg resource "${RESOURCE_MAP[$t]}" --arg perm "$perm" '{name:$name, policies:[{effect:"allow", resources:{($resource):"*"}, permission_groups:[{id:$perm}]}]}')"
  fi

  if $DRY_RUN; then
    log "DRY-RUN: would create ${TOKEN_NAME_MAP[$t]} with permission_group=$perm resource=${RESOURCE_MAP[$t]}"
    GENERATED[$t]=""
    continue
  fi

  resp="$(cf_request POST "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens" "$payload")"
  value="$(printf '%s' "$resp" | jq -r '.result.value // empty')"
  [[ -n "$value" ]] || die "token creation succeeded but no value was returned for ${TOKEN_NAME_MAP[$t]}"
  GENERATED[$t]="$value"
  audit "${TOKEN_NAME_MAP[$t]}" "$(printf '%s' "$resp" | jq -r '.result.id // "unknown"')" created "type:$t"
  log "created ${TOKEN_NAME_MAP[$t]}"
done

[[ -n "$OUT_FILE" ]] || { log "no output file requested"; exit 0; }

tmp="$(mktemp "${OUT_FILE}.XXXXXX")"
chmod 600 "$tmp"

MANAGED_KEYS=(CLOUDFLARE_DNS_TOKEN CLOUDFLARE_ZT_TOKEN CLOUDFLARE_WORKERS_TOKEN CLOUDFLARE_PAGES_TOKEN CLOUDFLARE_WAF_TOKEN CLOUDFLARE_TUNNEL_TOKEN CLOUDFLARE_R2_TOKEN CLOUDFLARE_D1_TOKEN CLOUDFLARE_AUDIT_TOKEN CLOUDFLARE_AI_GATEWAY_TOKEN CLOUDFLARE_AI_GATEWAY_SLUG)
if [[ -f "$OUT_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    key="$(printf '%s' "$line" | sed -E 's/^([A-Za-z0-9_]+)=.*/\1/')"
    skip=false
    for k in "${MANAGED_KEYS[@]}"; do [[ "$key" == "$k" ]] && skip=true && break; done
    $skip || printf '%s\n' "$line" >> "$tmp"
  done < "$OUT_FILE"
fi

{
  printf 'CLOUDFLARE_ACCOUNT_ID="%s"\n' "${CLOUDFLARE_ACCOUNT_ID:-$(env_file_value "$OUT_FILE" CLOUDFLARE_ACCOUNT_ID)}"
  printf 'CLOUDFLARE_ZONE_ID="%s"\n' "${CLOUDFLARE_ZONE_ID:-$(env_file_value "$OUT_FILE" CLOUDFLARE_ZONE_ID)}"
  printf 'CLOUDFLARE_AI_GATEWAY_SLUG="%s"\n' "${CLOUDFLARE_AI_GATEWAY_SLUG:-$(env_file_value "$OUT_FILE" CLOUDFLARE_AI_GATEWAY_SLUG || true)}" | sed 's/=""$/="zeaz"/'
  printf '\n'
} >> "$tmp"

for t in dns zt workers pages waf tunnel r2 d1; do
  key="${ENV_KEY_MAP[$t]}"
  val="${GENERATED[$t]:-}"
  if [[ -n "$val" ]]; then
    printf '%s="%s"\n' "$key" "$val" >> "$tmp"
  else
    existing="${!key:-$(env_file_value "$OUT_FILE" "$key")}"
    printf '%s="%s"\n' "$key" "$existing" >> "$tmp"
  fi
done

write_optional_env CLOUDFLARE_AUDIT_TOKEN "${CLOUDFLARE_AUDIT_TOKEN:-$(env_file_value "$OUT_FILE" CLOUDFLARE_AUDIT_TOKEN)}" >> "$tmp"
write_optional_env CLOUDFLARE_AI_GATEWAY_TOKEN "${CLOUDFLARE_AI_GATEWAY_TOKEN:-$(env_file_value "$OUT_FILE" CLOUDFLARE_AI_GATEWAY_TOKEN)}" >> "$tmp"

if $DRY_RUN; then
  log "DRY-RUN: preview of $OUT_FILE"
  redact_env_stream < "$tmp"
  rm -f "$tmp"
  exit 0
fi

mv "$tmp" "$OUT_FILE"
chmod 600 "$OUT_FILE"
bash scripts/cloudflare/clean-env-empty-values.sh "$OUT_FILE"
log "wrote $OUT_FILE"
log "done"
