#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/cloudflare-terraform-env.sh
source "$SCRIPT_DIR/lib/cloudflare-terraform-env.sh"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/cloudflare-import-dns.sh [--check] [--all] [resource ...]

Safely discovers existing Cloudflare DNS records and imports them into the
Terraform state. No DNS record is created, updated, or deleted by this script.

Default resources:
  zai auth zdash

ZEAZ One tunnel DNS resources:
  zeaz-one zeaz-one-support

The shared api.zeaz.dev record is deliberately not imported or changed; ZEAZ
One uses a path-specific Workers route on that existing hostname.

Options:
  --check   Show matching records without changing Terraform state.
  --all     Reconcile every enabled DNS resource managed by this stack.
  -h, --help
USAGE
}

mode="import"
use_all=false
declare -a requested=()

while (($#)); do
  case "$1" in
    --check) mode="check" ;;
    --all) use_all=true ;;
    -h|--help) usage; exit 0 ;;
    --*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) requested+=("$1") ;;
  esac
  shift
done

cloudflare_require_command curl
cloudflare_require_command jq
cloudflare_load_terraform_env
cloudflare_terraform_init

declare -A resources=(
  [moopiew]="cloudflare_dns_record.moopiew"
  [arin]="cloudflare_dns_record.arin"
  [zttshop]="cloudflare_dns_record.zttshop"
  [qwen]="cloudflare_dns_record.qwen"
  [chat]="cloudflare_dns_record.chat"
  [piewdash]="cloudflare_dns_record.piewdash"
  [zdash]="cloudflare_dns_record.zdash"
  [zerp]="cloudflare_dns_record.zerp"
  [cmeerp]="cloudflare_dns_record.cmeerp"
  [zai]="cloudflare_dns_record.zai"
  [auth]="cloudflare_dns_record.auth"
  [zwf]="cloudflare_dns_record.zwf"
  [zwf-api]="cloudflare_dns_record.zwf_api"
  [studio]="cloudflare_dns_record.studio"
  [zarvis]="cloudflare_dns_record.zarvis"
  [zider]="cloudflare_dns_record.zider"
  [zany]="cloudflare_dns_record.zany"
  [zslog]="cloudflare_dns_record.zslog"
  [zeaz-one]="cloudflare_dns_record.zeaz_one[0]"
  [zeaz-one-support]="cloudflare_dns_record.zeaz_one_support[0]"
)

declare -A hostnames=(
  [moopiew]="${MOOPIEW_HOSTNAME:-moopiew.zeaz.dev}"
  [arin]="${ARIN_HOSTNAME:-arin.zeaz.dev}"
  [zttshop]="${ZTTSHOP_HOSTNAME:-zttshop.zeaz.dev}"
  [qwen]="${QWEN_HOSTNAME:-qwen.zeaz.dev}"
  [chat]="${CHAT_HOSTNAME:-chat.zeaz.dev}"
  [piewdash]="${PIEWDASH_HOSTNAME:-piewdash.zeaz.dev}"
  [zdash]="${ZDASH_HOSTNAME:-zdash.zeaz.dev}"
  [zerp]="${ZERP_HOSTNAME:-zerp.zeaz.dev}"
  [cmeerp]="${CMEERP_HOSTNAME:-cme.zeaz.dev}"
  [zai]="${ZAI_HOSTNAME:-zai.zeaz.dev}"
  [auth]="${AUTH_HOSTNAME:-auth.zeaz.dev}"
  [zwf]="${ZWF_HOSTNAME:-zwf.zeaz.dev}"
  [zwf-api]="${ZWF_API_HOSTNAME:-zwf-api.zeaz.dev}"
  [studio]="${STUDIO_HOSTNAME:-studio.zeaz.dev}"
  [zarvis]="${ZARVIS_HOSTNAME:-zarvis.zeaz.dev}"
  [zider]="${ZIDER_HOSTNAME:-zider.zeaz.dev}"
  [zany]="${ZANY_HOSTNAME:-zany.zeaz.dev}"
  [zslog]="${ZSLOG_HOSTNAME:-zslog.zeaz.dev}"
  [zeaz-one]="${ZEAZ_ONE_HOSTNAME:-one.zeaz.dev}"
  [zeaz-one-support]="${ZEAZ_ONE_SUPPORT_HOSTNAME:-support.zeaz.dev}"
)

declare -a all_targets=(moopiew arin zttshop qwen chat piewdash zdash zerp cmeerp zai auth zwf zwf-api studio zarvis zider zany zslog)
if [[ "${ZEAZ_ONE_ENABLED:-false}" == "true" ]]; then
  all_targets+=(zeaz-one zeaz-one-support)
fi

declare -a targets=()
if [[ "$use_all" == true ]]; then
  targets=("${all_targets[@]}")
elif ((${#requested[@]})); then
  targets=("${requested[@]}")
else
  targets=(zai auth zdash)
fi

for target in "${targets[@]}"; do
  [[ -n "${resources[$target]:-}" ]] || {
    echo "Unknown DNS resource key: $target" >&2
    echo "Valid keys: ${!resources[*]}" >&2
    exit 2
  }
  if [[ "$target" == zeaz-one* && "${ZEAZ_ONE_ENABLED:-false}" != "true" ]]; then
    echo "ZEAZ One Terraform resources are disabled. Set ZEAZ_ONE_ENABLED=true or use scripts/zeaz-one-sync.sh." >&2
    exit 2
  fi
done

state_backup=""
if [[ "$mode" == "import" ]]; then
  backup_dir="$CLOUDFLARE_ROOT/backups/cloudflare"
  mkdir -p "$backup_dir"
  state_backup="$backup_dir/terraform-state-before-dns-import-$(date -u +%Y%m%dT%H%M%SZ).json"
  "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" state pull >"$state_backup"
  chmod 600 "$state_backup"
  echo "Terraform state backup: $state_backup"
fi

state_list="$($CLOUDFLARE_TF_BIN -chdir="$CLOUDFLARE_STACK" state list 2>/dev/null || true)"
failures=0
imports=0
skipped=0

for target in "${targets[@]}"; do
  resource="${resources[$target]}"
  hostname="${hostnames[$target]}"

  echo
  echo "==> $resource ($hostname)"

  if grep -Fxq "$resource" <<<"$state_list"; then
    echo "Already managed in Terraform state; skipping."
    ((skipped += 1))
    continue
  fi

  response="$({
    curl --fail-with-body --silent --show-error --get \
      "https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/dns_records" \
      --header "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
      --header "Content-Type: application/json" \
      --data-urlencode "name=${hostname}" \
      --data-urlencode "per_page=100"
  })" || {
    echo "Cloudflare DNS lookup failed for $hostname" >&2
    ((failures += 1))
    continue
  }

  if ! jq -e '.success == true' >/dev/null <<<"$response"; then
    jq -r '.errors[]? | "Cloudflare API error \(.code): \(.message)"' <<<"$response" >&2
    ((failures += 1))
    continue
  fi

  records="$(jq --arg hostname "$hostname" '[.result[] | select((.name | ascii_downcase) == ($hostname | ascii_downcase))]' <<<"$response")"
  count="$(jq 'length' <<<"$records")"
  jq -r '.[] | "Found id=\(.id) type=\(.type) name=\(.name) content=\(.content) proxied=\(.proxied)"' <<<"$records"

  case "$count" in
    0)
      echo "No existing exact-name record found. Terraform may create this resource during apply."
      ((skipped += 1))
      ;;
    1)
      if [[ "$mode" == "check" ]]; then
        echo "Check mode: import would use ${CLOUDFLARE_ZONE_ID}/$(jq -r '.[0].id' <<<"$records")"
        continue
      fi
      record_id="$(jq -r '.[0].id' <<<"$records")"
      record_type="$(jq -r '.[0].type' <<<"$records")"
      if [[ "$record_type" != "CNAME" ]]; then
        echo "NOTICE: Existing type is $record_type; Terraform declares CNAME."
        echo "Review the next Terraform plan carefully before applying the type change."
      fi
      "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" import "$resource" "${CLOUDFLARE_ZONE_ID}/${record_id}"
      state_list+=$'\n'"$resource"
      ((imports += 1))
      ;;
    *)
      echo "Refusing automatic import: $count exact-name records were returned for $hostname." >&2
      echo "Resolve the ambiguity manually; this script never deletes DNS records." >&2
      ((failures += 1))
      ;;
  esac
done

echo
printf 'DNS reconciliation summary: imported=%d skipped=%d failures=%d mode=%s\n' "$imports" "$skipped" "$failures" "$mode"
((failures == 0)) || exit 1
[[ "$mode" != "import" ]] || echo "Next: ./scripts/cloudflare-apply.sh"
