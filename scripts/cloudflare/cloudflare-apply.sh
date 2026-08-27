#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
# shellcheck source=scripts/lib/cloudflare-terraform-env.sh
source "$SCRIPT_DIR/lib/cloudflare-terraform-env.sh"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/cloudflare-apply.sh [options]

Creates a reviewed Cloudflare Terraform plan. DNS records that already exist
are imported into state before planning. The default mode never applies.

Options:
  --apply          Apply the saved plan after it is displayed.
  --skip-import    Do not run DNS import/reconciliation.
  --all-dns        Reconcile all enabled managed DNS records.
  --zeaz-one       Enable ZEAZ One, its shared-API path route and its tunnel DNS.
  --plan-file PATH Save the plan at PATH. Default: Terraform stack/tfplan.
  -h, --help
USAGE
}

apply_plan=false
reconcile_dns=true
all_dns=false
zeaz_one=false
plan_file=""

while (($#)); do
  case "$1" in
    --apply) apply_plan=true ;;
    --skip-import) reconcile_dns=false ;;
    --all-dns) all_dns=true ;;
    --zeaz-one) zeaz_one=true ;;
    --plan-file)
      shift
      [[ $# -gt 0 ]] || { echo "--plan-file requires a path" >&2; exit 2; }
      plan_file="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ "$all_dns" != true || "$zeaz_one" != true ]] || {
  echo "--all-dns and --zeaz-one are mutually exclusive." >&2
  exit 2
}
if [[ "$zeaz_one" == true ]]; then
  export FORCE_ENABLE_ZEAZ_ONE=true
  export FORCE_ENABLE_ZEAZ_ONE_API_ROUTE=true
fi

cloudflare_require_command curl
cloudflare_require_command jq
cloudflare_load_terraform_env
cloudflare_terraform_init

if [[ -z "$plan_file" ]]; then
  plan_file="$CLOUDFLARE_STACK/tfplan"
elif [[ "$plan_file" != /* ]]; then
  plan_file="$CLOUDFLARE_ROOT/$plan_file"
fi

if [[ "$reconcile_dns" == true ]]; then
  if [[ "$all_dns" == true ]]; then
    "$SCRIPT_DIR/cloudflare-import-dns.sh" --all
  elif [[ "$zeaz_one" == true ]]; then
    FORCE_ENABLE_ZEAZ_ONE=true "$SCRIPT_DIR/cloudflare-import-dns.sh" zeaz-one zeaz-one-support
  else
    "$SCRIPT_DIR/cloudflare-import-dns.sh" zai auth zdash
  fi
fi

# Check only Terraform source files. Operator-managed *.tfvars files may contain
# local values and are intentionally outside the repository formatting contract.
while IFS= read -r -d '' terraform_file; do
  "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" fmt -check "$(basename "$terraform_file")"
done < <(find "$CLOUDFLARE_STACK" -maxdepth 1 -type f -name '*.tf' -print0)
"$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" validate

if [[ "${MANAGE_TUNNEL_CONFIG:-false}" == "true" ]]; then
  if ! "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" state list 2>/dev/null |
    grep -Fxq 'cloudflare_zero_trust_tunnel_cloudflared_config.moopiew[0]'; then
    cat >&2 <<'GUARD'
Refusing to manage the tunnel configuration because the existing remote tunnel
configuration is not present in Terraform state.

Import and review the live tunnel configuration first, or set:
  MANAGE_TUNNEL_CONFIG=false

This guard prevents unrelated ingress routes from being replaced.
GUARD
    exit 1
  fi
fi

backup_dir="$CLOUDFLARE_ROOT/backups/cloudflare"
mkdir -p "$backup_dir"
state_backup="$backup_dir/terraform-state-before-plan-$(date -u +%Y%m%dT%H%M%SZ).json"
"$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" state pull >"$state_backup"
chmod 600 "$state_backup"
echo "Terraform state backup: $state_backup"

mkdir -p "$(dirname "$plan_file")"
rm -f "$plan_file"
"$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" plan -out="$plan_file"
chmod 600 "$plan_file"

echo
echo "================ Terraform plan ================"
"$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" show -no-color "$plan_file"
echo "=================================================="
echo "Saved plan: $plan_file"

if [[ "$apply_plan" != true ]]; then
  echo
  echo "Plan only. Review it, then run the same command with --apply."
  exit 0
fi

echo
echo "Applying the saved Terraform plan..."
"$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" apply "$plan_file"
echo
echo "Cloudflare apply completed."

zdash_origin="${ZDASH_ORIGIN:-http://127.0.0.1:18080}"
zdash_hostname="${ZDASH_HOSTNAME:-zdash.zeaz.dev}"
if curl --fail --silent --show-error "$zdash_origin/gateway-health" >/dev/null; then
  echo "zDash origin healthy: $zdash_origin/gateway-health"
else
  echo "WARNING: zDash origin health check failed: $zdash_origin/gateway-health" >&2
fi

remote_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --head "https://$zdash_hostname" || true)"
[[ -z "$remote_status" ]] || echo "Remote zDash HTTP status: $remote_status"

if [[ "${ZEAZ_ONE_ENABLED:-false}" == "true" ]]; then
  declare -a checks=(
    "${ZEAZ_ONE_ORIGIN:-http://127.0.0.1:18081}/"
    "${ZEAZ_ONE_API_ORIGIN:-http://127.0.0.1:18084}/health"
    "${ZEAZ_ONE_SUPPORT_ORIGIN:-http://127.0.0.1:18083}/zeaz-one/"
  )
  for endpoint in "${checks[@]}"; do
    if curl --fail --silent --show-error "$endpoint" >/dev/null; then
      echo "ZEAZ One origin healthy: $endpoint"
    else
      echo "WARNING: ZEAZ One origin health check failed: $endpoint" >&2
    fi
  done

  declare -a urls=(
    "https://${ZEAZ_ONE_HOSTNAME:-one.zeaz.dev}/"
    "https://${ZEAZ_ONE_API_HOSTNAME:-api.zeaz.dev}/v1/products/zeaz-one"
    "https://${ZEAZ_ONE_SUPPORT_HOSTNAME:-support.zeaz.dev}/zeaz-one/"
  )
  for url in "${urls[@]}"; do
    status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --head "$url" || true)"
    [[ -z "$status" ]] || echo "Remote $url HTTP status: $status"
  done
fi
