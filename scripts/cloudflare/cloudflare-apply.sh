#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
# shellcheck source=scripts/lib/cloudflare-terraform-env.sh
source "$SCRIPT_DIR/lib/cloudflare-terraform-env.sh"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/cloudflare-apply.sh [plan options]
  ./scripts/cloudflare-apply.sh --apply --plan-file PATH --approved-plan-sha256 SHA256

Creates and displays a saved Terraform plan by default. Apply mode consumes the
existing saved plan only; it never imports DNS records or creates a new plan.
Plan files may contain sensitive values and are kept mode 0600.

Plan options:
  --skip-import    Do not run DNS import/reconciliation.
  --all-dns        Reconcile all enabled managed DNS records before planning.
  --zeaz-one       Enable ZEAZ One, its shared-API path route and its tunnel DNS.
  --plan-file PATH Save the plan at PATH. Default: Terraform stack/tfplan.

Apply options:
  --apply                          Apply an existing saved plan.
  --approved-plan-sha256 SHA256    Required digest approved by an authorized operator.
  --plan-file PATH                 Saved plan to apply; defaults to Terraform stack/tfplan.

After reviewing the plan and its target environment, an authorized operator
must explicitly run the apply command with the exact SHA-256 printed by plan mode.
USAGE
}

apply_plan=false
reconcile_dns=true
skip_import_requested=false
all_dns=false
zeaz_one=false
plan_file=""
approved_plan_sha256=""

while (($#)); do
  case "$1" in
    --apply) apply_plan=true ;;
    --skip-import)
      reconcile_dns=false
      skip_import_requested=true
      ;;
    --all-dns) all_dns=true ;;
    --zeaz-one) zeaz_one=true ;;
    --plan-file)
      shift
      [[ $# -gt 0 ]] || { echo "--plan-file requires a path" >&2; exit 2; }
      plan_file="$1"
      ;;
    --approved-plan-sha256)
      shift
      [[ $# -gt 0 ]] || { echo "--approved-plan-sha256 requires a SHA-256 digest" >&2; exit 2; }
      approved_plan_sha256="$1"
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
if [[ "$apply_plan" == true ]]; then
  [[ "$skip_import_requested" != true && "$all_dns" != true && "$zeaz_one" != true ]] || {
    echo "DNS reconciliation options can only be used while creating a plan." >&2
    exit 2
  }
  [[ "$approved_plan_sha256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "--apply requires --approved-plan-sha256 with a 64-character lowercase SHA-256 digest." >&2
    exit 2
  }
else
  [[ -z "$approved_plan_sha256" ]] || {
    echo "--approved-plan-sha256 can only be used with --apply." >&2
    exit 2
  }
fi

if [[ "$zeaz_one" == true ]]; then
  export FORCE_ENABLE_ZEAZ_ONE=true
  export FORCE_ENABLE_ZEAZ_ONE_API_ROUTE=true
fi

cloudflare_require_command curl
cloudflare_require_command jq
cloudflare_require_command sha256sum
cloudflare_require_command awk
cloudflare_load_terraform_env
cloudflare_terraform_init

if [[ -z "$plan_file" ]]; then
  plan_file="$CLOUDFLARE_STACK/tfplan"
elif [[ "$plan_file" != /* ]]; then
  plan_file="$CLOUDFLARE_ROOT/$plan_file"
fi

run_post_apply_checks() {
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
}

if [[ "$apply_plan" == true ]]; then
  [[ -f "$plan_file" && ! -L "$plan_file" ]] || {
    echo "Saved plan must be a regular, non-symlink file: $plan_file" >&2
    exit 1
  }
  plan_mode="$(stat -c '%a' "$plan_file")"
  (( (8#$plan_mode & 8#077) == 0 )) || {
    echo "Saved plan must not be group/world accessible: $plan_file" >&2
    exit 1
  }

  apply_snapshot="$(mktemp "$CLOUDFLARE_STACK/tfplan.approved.XXXXXX")"
  trap 'rm -f -- "$apply_snapshot"' EXIT
  chmod 600 "$apply_snapshot"
  cp -- "$plan_file" "$apply_snapshot"
  actual_plan_sha256="$(sha256sum -- "$apply_snapshot" | awk '{print $1}')"
  [[ "$actual_plan_sha256" == "$approved_plan_sha256" ]] || {
    echo "Saved plan digest does not match the approved SHA-256; refusing to apply." >&2
    exit 1
  }
  chmod 400 "$apply_snapshot"

  terraform_workspace="$("$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" workspace show)"
  echo "Cloudflare target: account=$CLOUDFLARE_ACCOUNT_ID zone=$CLOUDFLARE_ZONE_ID workspace=$terraform_workspace backend=${TERRAFORM_BACKEND_TYPE:-local}"
  echo "Approved plan SHA-256: $actual_plan_sha256"
  echo
  echo "================ Approved Terraform plan ================"
  "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" show -no-color "$apply_snapshot"
  echo "=========================================================="
  echo "Applying the exact saved Terraform plan..."
  "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" apply "$apply_snapshot"
  echo
  echo "Cloudflare apply completed."
  run_post_apply_checks
  exit 0
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
[[ ! -e "$plan_file" && ! -L "$plan_file" ]] || {
  echo "Refusing to overwrite an existing plan file: $plan_file" >&2
  echo "Choose a new path with --plan-file." >&2
  exit 1
}
"$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" plan -out="$plan_file"
[[ -f "$plan_file" && ! -L "$plan_file" ]] || {
  echo "Terraform did not create a regular saved plan file: $plan_file" >&2
  exit 1
}
chmod 600 "$plan_file"
plan_sha256="$(sha256sum -- "$plan_file" | awk '{print $1}')"
terraform_workspace="$("$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" workspace show)"

echo
echo "Cloudflare target: account=$CLOUDFLARE_ACCOUNT_ID zone=$CLOUDFLARE_ZONE_ID workspace=$terraform_workspace backend=${TERRAFORM_BACKEND_TYPE:-local}"
echo "================ Terraform plan ================"
"$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" show -no-color "$plan_file"
echo "=================================================="
echo "Saved plan: $plan_file"
echo "Plan SHA-256: $plan_sha256"
echo "Plan only. Review the target and every resource change. After approval by an authorized operator, apply only this plan with:"
printf '  ./scripts/cloudflare-apply.sh --apply --plan-file %q --approved-plan-sha256 %s\n' "$plan_file" "$plan_sha256"
