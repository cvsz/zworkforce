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

ค่าเริ่มต้นจะสร้างและแสดง saved Terraform plan ส่วน apply mode ใช้เฉพาะ saved
plan ที่มีอยู่แล้ว โดยจะไม่ import DNS หรือสร้าง plan ใหม่ plan และ manifest
target/feature อาจมีข้อมูล sensitive และเก็บด้วย mode 0600 approval digest
จะผูก bytes ของ plan เข้ากับ manifest

Plan options:
  --skip-import    ข้าม DNS import/reconciliation
  --all-dns        ทำ reconciliation ให้ DNS records ที่จัดการก่อนสร้าง plan
  --zeaz-one       เปิด ZEAZ One, shared-API path route และ tunnel DNS
  --plan-file PATH บันทึก plan ไปที่ PATH (ค่าเริ่มต้น: Terraform stack/tfplan)

Apply options:
  --apply                          apply saved plan ที่มีอยู่
  --approved-plan-sha256 SHA256    approval digest ที่ authorized operator อนุมัติ
  --plan-file PATH                 saved plan ที่จะ apply (ค่าเริ่มต้น: stack/tfplan)

หลัง review plan และ target environment แล้ว authorized operator ต้องเรียก
apply command พร้อม SHA-256 เดียวกับที่ plan mode พิมพ์ออกมา
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
cloudflare_require_command python3
cloudflare_load_terraform_env

if [[ -z "$plan_file" ]]; then
  plan_file="$CLOUDFLARE_STACK/tfplan"
elif [[ "$plan_file" != /* ]]; then
  plan_file="$CLOUDFLARE_ROOT/$plan_file"
fi
manifest_file="${plan_file}.manifest.json"
manifest_helper="$SCRIPT_DIR/cloudflare-plan-manifest.py"
terraform_backend_type="${TERRAFORM_BACKEND_TYPE:-local}"

terraform_backend_identity() {
  case "$terraform_backend_type" in
    local)
      [[ ! -e "$CLOUDFLARE_STACK/backend.tf" && ! -L "$CLOUDFLARE_STACK/backend.tf" ]] || {
        echo "A backend.tf is present while TERRAFORM_BACKEND_TYPE=local; refusing an ambiguous backend." >&2
        return 1
      }
      local stack_root
      stack_root="$(cd "$CLOUDFLARE_STACK" && pwd -P)"
      printf 'local:%s/terraform.tfstate' "$stack_root"
      ;;
    r2)
      [[ -n "${TERRAFORM_STATE_BUCKET:-}" && -n "${CLOUDFLARE_S3_API_ENDPOINT:-}" ]] || {
        echo "R2 backend identity requires its bucket and S3 endpoint." >&2
        return 1
      }
      [[ ! -L "$CLOUDFLARE_STACK/backend.tf" ]] || {
        echo "R2 backend configuration must not be a symlink." >&2
        return 1
      }
      printf 's3:%s:zeaz/cloudflare/terraform.tfstate:%s' \
        "$TERRAFORM_STATE_BUCKET" "${CLOUDFLARE_S3_API_ENDPOINT%/}"
      ;;
    *)
      echo "Unsupported Terraform backend type: $terraform_backend_type" >&2
      return 1
      ;;
  esac
}

terraform_workspace_hint() {
  if [[ -n "${TF_WORKSPACE:-}" ]]; then
    printf '%s' "$TF_WORKSPACE"
    return
  fi

  local workspace_file="$CLOUDFLARE_STACK/.terraform/environment"
  if [[ -e "$workspace_file" || -L "$workspace_file" ]]; then
    [[ -f "$workspace_file" && ! -L "$workspace_file" ]] || {
      echo "Terraform workspace selection must be a regular file." >&2
      return 1
    }
    local workspace
    IFS= read -r workspace < "$workspace_file" || true
    [[ -n "$workspace" ]] || {
      echo "Terraform workspace selection is empty." >&2
      return 1
    }
    printf '%s' "$workspace"
  else
    printf 'default'
  fi
}

verify_plan_manifest() {
  local workspace="$1"
  python3 "$manifest_helper" verify \
    --plan "$plan_file" \
    --manifest "$manifest_file" \
    --expected-approval-sha256 "$approved_plan_sha256" \
    --configuration-dir "$CLOUDFLARE_STACK" \
    --environment-file "$CLOUDFLARE_ENV_FILE" \
    --expected-account-id "$CLOUDFLARE_ACCOUNT_ID" \
    --expected-zone-id "$CLOUDFLARE_ZONE_ID" \
    --expected-tunnel-id "$CLOUDFLARE_TUNNEL_ID" \
    --workspace "$workspace" \
    --backend-type "$terraform_backend_type" \
    --backend-identity "$backend_identity"
}

backend_identity="$(terraform_backend_identity)"

if [[ "$apply_plan" == true ]]; then
  workspace_hint="$(terraform_workspace_hint)"
  verified_manifest_json="$(verify_plan_manifest "$workspace_hint")"
else
  plan_directory="$(dirname "$plan_file")"
  mkdir -p "$plan_directory"
  [[ -d "$plan_directory" && -w "$plan_directory" ]] || {
    echo "Plan output directory must exist and be writable: $plan_directory" >&2
    exit 1
  }
  [[ ! -e "$plan_file" && ! -L "$plan_file" ]] || {
    echo "Refusing to overwrite an existing plan file: $plan_file" >&2
    echo "Choose a new path with --plan-file." >&2
    exit 1
  }
  [[ ! -e "$manifest_file" && ! -L "$manifest_file" ]] || {
    echo "Refusing to overwrite an existing plan manifest: $manifest_file" >&2
    echo "Choose a new path with --plan-file." >&2
    exit 1
  }
fi

cloudflare_terraform_init
terraform_workspace="$("$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" workspace show)"
if [[ "$apply_plan" == true ]]; then
  verified_manifest_json="$(verify_plan_manifest "$terraform_workspace")"
fi

run_post_apply_checks() {
  local zeaz_one_enabled="$1"
  local zeaz_one_api_route_enabled="$2"
  local zeaz_one_origin="$3"
  local zeaz_one_hostname="$4"
  local zeaz_one_api_origin="$5"
  local zeaz_one_api_hostname="$6"
  local zeaz_one_support_origin="$7"
  local zeaz_one_support_hostname="$8"

  curl --fail --silent --show-error --max-time 20 \
    https://zwf.zeaz.dev/health >/dev/null
  echo "HA-A public health check passed: https://zwf.zeaz.dev/health"
  bash "$SCRIPT_DIR/verify-zarvis-online.sh"

  zdash_origin="${ZDASH_ORIGIN:-http://127.0.0.1:18080}"
  zdash_hostname="${ZDASH_HOSTNAME:-zdash.zeaz.dev}"
  if curl --fail --silent --show-error "$zdash_origin/gateway-health" >/dev/null; then
    echo "zDash origin healthy: $zdash_origin/gateway-health"
  else
    echo "WARNING: zDash origin health check failed: $zdash_origin/gateway-health" >&2
  fi

  remote_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --head "https://$zdash_hostname" || true)"
  [[ -z "$remote_status" ]] || echo "Remote zDash HTTP status: $remote_status"

  if [[ "$zeaz_one_enabled" == "true" ]]; then
    declare -a checks=(
      "${zeaz_one_origin%/}/"
      "${zeaz_one_support_origin%/}/zeaz-one/"
    )
    for endpoint in "${checks[@]}"; do
      if curl --fail --silent --show-error "$endpoint" >/dev/null; then
        echo "ZEAZ One origin healthy: $endpoint"
      else
        echo "WARNING: ZEAZ One origin health check failed: $endpoint" >&2
      fi
    done

    declare -a urls=(
      "https://${zeaz_one_hostname}/"
      "https://${zeaz_one_support_hostname}/zeaz-one/"
    )
    for url in "${urls[@]}"; do
      status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --head "$url" || true)"
      [[ -z "$status" ]] || echo "Remote $url HTTP status: $status"
    done
  fi

  if [[ "$zeaz_one_api_route_enabled" == "true" ]]; then
    api_origin="${zeaz_one_api_origin%/}/health"
    api_url="https://${zeaz_one_api_hostname}/v1/products/zeaz-one"
    if curl --fail --silent --show-error "$api_origin" >/dev/null; then
      echo "ZEAZ One API origin healthy: $api_origin"
    else
      echo "WARNING: ZEAZ One API origin health check failed: $api_origin" >&2
    fi
    api_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --head "$api_url" || true)"
    [[ -z "$api_status" ]] || echo "Remote $api_url HTTP status: $api_status"
  fi
}

if [[ "$apply_plan" == true ]]; then
  apply_snapshot="$(mktemp "$CLOUDFLARE_STACK/tfplan.approved.XXXXXX")"
  trap 'rm -f -- "$apply_snapshot"' EXIT
  chmod 600 "$apply_snapshot"
  cp -- "$plan_file" "$apply_snapshot"
  actual_plan_sha256="$(sha256sum -- "$apply_snapshot" | awk '{print $1}')"
  verified_manifest_json="$(verify_plan_manifest "$terraform_workspace")"
  expected_plan_sha256="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_sha256"])' <<< "$verified_manifest_json")"
  [[ "$actual_plan_sha256" == "$expected_plan_sha256" ]] || {
    echo "Private saved-plan copy differs from its approval manifest; refusing to apply." >&2
    exit 1
  }
  chmod 400 "$apply_snapshot"

  mapfile -t plan_features < <(
    python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d["features"]["zeaz_one_enabled"]).lower()); print(str(d["features"]["zeaz_one_api_route_enabled"]).lower()); [print(d["health_checks"][key]) for key in ("zeaz_one_origin", "zeaz_one_hostname", "zeaz_one_api_origin", "zeaz_one_api_hostname", "zeaz_one_support_origin", "zeaz_one_support_hostname")]' \
      <<< "$verified_manifest_json"
  )
  echo "Cloudflare target: account=$CLOUDFLARE_ACCOUNT_ID zone=$CLOUDFLARE_ZONE_ID workspace=$terraform_workspace backend=$terraform_backend_type"
  echo "Approved plan SHA-256: $actual_plan_sha256"
  echo "Approval SHA-256: $approved_plan_sha256"
  echo "Approved target/feature manifest: $manifest_file"
  echo
  echo "================ Approved Terraform plan ================"
  "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" show -no-color "$apply_snapshot"
  echo "=========================================================="
  echo "Applying the exact saved Terraform plan..."
  "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" apply "$apply_snapshot"
  echo
  echo "Cloudflare apply completed."
  run_post_apply_checks \
    "${plan_features[0]}" "${plan_features[1]}" \
    "${plan_features[2]}" "${plan_features[3]}" \
    "${plan_features[4]}" "${plan_features[5]}" \
    "${plan_features[6]}" "${plan_features[7]}"
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
approval_sha256="$(
  # JSON จาก Terraform มีค่า sensitive; helper ส่งออกเฉพาะ digest ของ metadata ที่เลือกไว้
  "$CLOUDFLARE_TF_BIN" -chdir="$CLOUDFLARE_STACK" show -json "$plan_file" |
    python3 "$manifest_helper" create \
      --plan "$plan_file" \
      --manifest "$manifest_file" \
      --configuration-dir "$CLOUDFLARE_STACK" \
      --environment-file "$CLOUDFLARE_ENV_FILE" \
      --expected-account-id "$CLOUDFLARE_ACCOUNT_ID" \
      --expected-zone-id "$CLOUDFLARE_ZONE_ID" \
      --expected-tunnel-id "$CLOUDFLARE_TUNNEL_ID" \
      --workspace "$terraform_workspace" \
      --backend-type "$terraform_backend_type" \
      --backend-identity "$backend_identity"
)"

echo "Plan SHA-256: $plan_sha256"
echo "Saved plan manifest: $manifest_file"
echo "Manifest feature flags: zeaz_one=${TF_VAR_enable_zeaz_one:-false} zeaz_one_api_route=${TF_VAR_enable_zeaz_one_api_route:-false}"
echo "Approval SHA-256: $approval_sha256"
echo "Plan only. Review the target, manifest feature flags, and every resource change. After approval by an authorized operator, apply only this plan with:"
printf '  ./scripts/cloudflare-apply.sh --apply --plan-file %q --approved-plan-sha256 %s\n' "$plan_file" "$approval_sha256"
