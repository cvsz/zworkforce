#!/usr/bin/env bash
set -Eeuo pipefail

OWNER="${ZEAZ_REPO_OWNER:-cvsz}"
ZONE="${ZEAZ_ZONE:-zeaz.dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ZEAZ_CLOUDFLARE_TF_DIR:-${ROOT_DIR}/infrastructure/terraform/cloudflare}"
OUT_FILE="${ZEAZ_REPO_FALLBACK_TFVARS:-${TF_DIR}/repo-fallback.auto.tfvars.json}"
ENABLE_WILDCARD_DNS=false
APPLY=false

log(){ printf '[zeaz repo routing] %s\n' "$*"; }
fail(){ printf '[zeaz repo routing] ERROR: %s\n' "$*" >&2; exit 1; }

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=true ;;
    --wildcard-dns) ENABLE_WILDCARD_DNS=true ;;
    --help|-h)
      cat <<'EOF'
Usage: scripts/cloudflare/reconcile-repo-sites.sh [--wildcard-dns] [--apply]

Discovers active cvsz product repositories, maps them to *.zeaz.dev hostnames,
checks current public reachability, and writes Terraform variables that route
only offline hostnames to the repo-aware Under Construction Worker.

--wildcard-dns  Also manage a proxied *.zeaz.dev CNAME to the existing tunnel.
                Exact DNS records still take precedence. Review the plan first.
--apply         Apply only the fallback Worker/route/DNS resources. Requires
                ZEAZ_REPO_FALLBACK_APPLY=YES.
EOF
      exit 0
      ;;
    *) fail "unknown argument: $arg" ;;
  esac
done

for cmd in gh python3 curl terraform; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done
gh auth status >/dev/null 2>&1 || fail "GitHub CLI is not authenticated"
[[ -d "$TF_DIR" ]] || fail "Terraform directory not found: $TF_DIR"

repos_json="$(mktemp)"
candidates_tsv="$(mktemp)"
results_tsv="$(mktemp)"
trap 'rm -f "$repos_json" "$candidates_tsv" "$results_tsv"' EXIT

log "discovering active repositories owned by ${OWNER}"
gh repo list "$OWNER" --limit 1000 \
  --json name,isArchived,isFork,homepageUrl,url \
  > "$repos_json"

python3 - "$repos_json" "$ZONE" > "$candidates_tsv" <<'PY'
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

repos = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
zone = sys.argv[2].strip().lower().rstrip('.')

# Aliases keep existing ZeaZDev host naming aligned with the owning repository.
aliases = {
    'zworkforce': ['zwf', 'zwf-api', 'zslog', 'zarvis', 'autoc', 'laps'],
    'zsp-aitool': ['studio', 'zider'],
    'open-webui': ['chat'],
    'qwen-gen': ['qwen'],
    'zeaz-ai-command-center': ['zai'],
    'zttshop-php': ['zttshop'],
    'cmeerp': ['cme'],
    'zanything': ['zany'],
}
explicit_non_z = {'stremdbc', 'cmeerp', 'open-webui', 'qwen-gen'}

def safe_label(name: str) -> str:
    value = name.strip().lower().replace('_', '-').replace('.', '-')
    value = re.sub(r'[^a-z0-9-]+', '-', value)
    value = re.sub(r'-+', '-', value).strip('-')
    return value

rows = set()
for repo in repos:
    if repo.get('isArchived') or repo.get('isFork'):
        continue
    name = str(repo.get('name') or '').strip()
    if not name:
        continue
    lowered = name.lower()
    homepage = str(repo.get('homepageUrl') or '').strip()
    homepage_host = ''
    if homepage:
        try:
            homepage_host = (urlparse(homepage).hostname or '').lower().rstrip('.')
        except ValueError:
            homepage_host = ''
    if homepage_host.endswith('.' + zone):
        rows.add((homepage_host, name))

    # Product repositories follow the z*/zeaz* naming convention. Tool/library
    # forks outside that convention are intentionally not assigned public sites.
    if lowered.startswith('z') or lowered.startswith('zeaz') or lowered in explicit_non_z:
        label = safe_label(name)
        if label:
            rows.add((f'{label}.{zone}', name))
    for alias in aliases.get(lowered, []):
        rows.add((f'{alias}.{zone}', name))

for host, repo in sorted(rows):
    print(f'{host}\t{repo}')
PY

: > "$results_tsv"
count=0
while IFS=$'\t' read -r host repo; do
  [[ -n "$host" && -n "$repo" ]] || continue
  count=$((count + 1))
  code="$(curl --silent --show-error --location \
    --connect-timeout 3 --max-time 8 \
    --output /dev/null --write-out '%{http_code}' \
    "https://${host}/" 2>/dev/null || printf '000')"

  # 2xx/3xx are live. Auth/rate-limit responses also prove a deployed edge.
  online=false
  if [[ "$code" =~ ^[23][0-9][0-9]$ ]] || [[ "$code" == "401" || "$code" == "403" || "$code" == "405" || "$code" == "429" ]]; then
    online=true
  fi

  if $online; then
    printf 'live\t%s\t%s\t%s\n' "$host" "$repo" "$code" >> "$results_tsv"
    log "LIVE     ${host} -> ${OWNER}/${repo} (HTTP ${code})"
  else
    printf 'fallback\t%s\t%s\t%s\n' "$host" "$repo" "$code" >> "$results_tsv"
    log "FALLBACK ${host} -> ${OWNER}/${repo} (HTTP ${code})"
  fi
done < "$candidates_tsv"

[[ "$count" -gt 0 ]] || fail "no candidate repo hostnames were discovered"

python3 - "$results_tsv" "$OUT_FILE" "$ENABLE_WILDCARD_DNS" <<'PY'
import json
import sys
from pathlib import Path

results = Path(sys.argv[1])
out = Path(sys.argv[2])
wildcard = sys.argv[3].lower() == 'true'
fallback = {}
live = []
for raw in results.read_text(encoding='utf-8').splitlines():
    if not raw.strip():
        continue
    state, host, repo, code = raw.split('\t', 3)
    if state == 'fallback':
        fallback[host] = repo
    else:
        live.append({'hostname': host, 'repository': repo, 'http_status': code})

payload = {
    'enable_repo_fallback': True,
    'enable_repo_fallback_wildcard_dns': wildcard,
    'repo_fallback_sites': dict(sorted(fallback.items())),
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
summary = out.with_name('repo-fallback-status.json')
summary.write_text(json.dumps({
    'live_count': len(live),
    'fallback_count': len(fallback),
    'live': live,
    'fallback': [{'hostname': h, 'repository': r} for h, r in sorted(fallback.items())],
}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(f'wrote {out}')
print(f'wrote {summary}')
print(f'live={len(live)} fallback={len(fallback)}')
PY

log "generated ${OUT_FILE}"
log "offline hostnames only will receive exact Under Construction Worker routes"

cd "$TF_DIR"
terraform fmt -check repo-fallback.tf >/dev/null
terraform validate >/dev/null
log "Terraform formatting and validation passed"

plan_file="tfplan.repo-fallback"
terraform plan \
  -target=cloudflare_workers_script.repo_under_construction \
  -target=cloudflare_workers_route.repo_under_construction \
  -target=cloudflare_dns_record.repo_fallback_wildcard \
  -out="$plan_file"

if ! $APPLY; then
  log "PLAN ONLY: inspect ${TF_DIR}/${plan_file}; rerun with --apply after review"
  exit 0
fi

[[ "${ZEAZ_REPO_FALLBACK_APPLY:-}" == "YES" ]] || \
  fail "--apply requires ZEAZ_REPO_FALLBACK_APPLY=YES"

terraform apply "$plan_file"
rm -f "$plan_file"
log "PASS: offline repo hostnames now use the repo-aware Under Construction Worker"
