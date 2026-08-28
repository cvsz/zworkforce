#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOSITORY="${ZARVIS_GITHUB_REPOSITORY:-cvsz/z-platform}"
WORKFLOW="zarvis-windows.yml"
VERSION="0.1.0"
PUBLISH_PUBLIC_RELEASE=false
REQUIRE_SIGNED=false
SKIP_SERVER_HEALTH=false
STAGE_ROOT="${ZARVIS_WINDOWS_RELEASE_DIR:-${ROOT_DIR}/zarvis-windows-releases}"

log()  { printf '[ZARVIS-WINDOWS] %s\n' "$*"; }
pass() { printf '[ZARVIS-WINDOWS][PASS] %s\n' "$*"; }
warn() { printf '[ZARVIS-WINDOWS][WARN] %s\n' "$*" >&2; }
die()  { printf '[ZARVIS-WINDOWS][ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Z.A.R.V.I.S. Windows build, verification, and server staging

Usage:
  bash scripts/zarvis-windows-release.sh [version] [options]

Options:
  --publish-public-release  Publish a GitHub Release. The repository is public,
                            so the release and binaries will be public.
  --require-signed          Fail unless Authenticode signing was enabled.
  --skip-server-health      Skip local Action/Proactive health verification.
  --stage-dir PATH          Server directory for verified Windows artifacts.
  -h, --help                Show this help.

Default behavior:
  - dispatch version 0.1.0 through GitHub Actions;
  - do not publish a public GitHub Release;
  - wait for Windows tests/build/installer packaging;
  - download the Actions artifact to zeaz-platform;
  - verify every SHA-256 checksum and release-manifest invariant;
  - generate a one-click PowerShell installer next to the artifact;
  - print the exact SCP command for Windows 11.
USAGE
}

if [[ $# -gt 0 && "$1" != -* ]]; then
  VERSION="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --publish-public-release)
      PUBLISH_PUBLIC_RELEASE=true
      shift
      ;;
    --require-signed)
      REQUIRE_SIGNED=true
      shift
      ;;
    --skip-server-health)
      SKIP_SERVER_HEALTH=true
      shift
      ;;
    --stage-dir)
      [[ $# -ge 2 ]] || die "--stage-dir requires a path"
      STAGE_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$ ]] ||
  die "Version must be SemVer-like, for example 0.1.0"

for command in git gh node curl sha256sum find awk sed; do
  command -v "$command" >/dev/null 2>&1 || die "$command is required"
done

gh auth status >/dev/null 2>&1 || die "GitHub CLI is not authenticated; run: gh auth login"

cd "$ROOT_DIR"
[[ -d .git ]] || die "Not a Git repository: $ROOT_DIR"
git diff --quiet || die "Tracked working-tree changes must be committed or reverted"
git diff --cached --quiet || die "Staged changes must be committed or reverted"

git fetch origin --prune --tags
git switch main
git pull --ff-only origin main

visibility="$(gh api "repos/${REPOSITORY}" --jq '.visibility')"
[[ "$visibility" == "public" || "$visibility" == "private" || "$visibility" == "internal" ]] ||
  die "Could not determine repository visibility"

if [[ "$PUBLISH_PUBLIC_RELEASE" == true && "$visibility" == "public" ]]; then
  warn "Publishing is enabled and ${REPOSITORY} is public; binaries will be public."
fi

if [[ "$SKIP_SERVER_HEALTH" != true ]]; then
  action_port="$(sed -n 's/^ZARVIS_ACTION_PORT=//p' .env.zarvis.local 2>/dev/null | tail -n 1)"
  proactive_port="$(sed -n 's/^ZARVIS_PROACTIVE_PORT=//p' .env.zarvis.local 2>/dev/null | tail -n 1)"
  action_port="${action_port:-8098}"
  proactive_port="${proactive_port:-8099}"

  for endpoint in \
    "http://127.0.0.1:${action_port}/healthz" \
    "http://127.0.0.1:${proactive_port}/healthz"; do
    payload="$(curl -fsS --max-time 5 "$endpoint")" || die "Server health failed: $endpoint"
    node -e '
      const payload = JSON.parse(process.argv[1]);
      if (payload.status !== "ok" || payload.local_only !== true || payload.secrets_exposed !== false) {
        throw new Error("health invariant failed");
      }
    ' "$payload" || die "Server health invariant failed: $endpoint"
  done
  pass "Local server health and loopback invariants"
fi

mkdir -p "$STAGE_ROOT"
if [[ -f .git/info/exclude ]] && ! grep -qxF '/zarvis-windows-releases/' .git/info/exclude; then
  printf '/zarvis-windows-releases/\n' >> .git/info/exclude
fi

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
publish_input=false
[[ "$PUBLISH_PUBLIC_RELEASE" == true ]] && publish_input=true

log "Dispatching Windows build ${VERSION} (publish_release=${publish_input})"
gh workflow run "$WORKFLOW" \
  --repo "$REPOSITORY" \
  --ref main \
  -f version="$VERSION" \
  -f publish_release="$publish_input"

run_id=""
for _ in $(seq 1 60); do
  run_id="$(
    gh run list \
      --repo "$REPOSITORY" \
      --workflow "$WORKFLOW" \
      --branch main \
      --event workflow_dispatch \
      --limit 30 \
      --json databaseId,createdAt \
      --jq ".[] | select(.createdAt >= \"${started_at}\") | .databaseId" |
      head -n 1
  )"
  [[ -n "$run_id" ]] && break
  sleep 2
done
[[ -n "$run_id" ]] || die "Could not resolve the dispatched workflow run"

log "Watching workflow run ${run_id}"
gh run watch "$run_id" --repo "$REPOSITORY" --exit-status
pass "Windows tests, publish, installer, manifest, and artifact workflow"

stage_dir="${STAGE_ROOT}/${VERSION}"
rm -rf "$stage_dir"
mkdir -p "$stage_dir"

log "Downloading workflow artifact to ${stage_dir}"
gh run download "$run_id" --repo "$REPOSITORY" --dir "$stage_dir"

sum_file="$(find "$stage_dir" -type f -name SHA256SUMS.txt -print -quit)"
manifest_file="$(find "$stage_dir" -type f -name release-manifest.json -print -quit)"
installer="$(find "$stage_dir" -type f -name 'ZARVIS-Setup-*-win-x64.exe' -print -quit)"
portable="$(find "$stage_dir" -type f -name 'ZARVIS-*-win-x64.exe' ! -name 'ZARVIS-Setup-*' -print -quit)"

[[ -f "$sum_file" ]] || die "SHA256SUMS.txt is missing from the artifact"
[[ -f "$manifest_file" ]] || die "release-manifest.json is missing from the artifact"
[[ -f "$installer" ]] || die "Windows installer is missing from the artifact"
[[ -f "$portable" ]] || die "Portable ZARVIS.exe artifact is missing"

artifact_dir="$(dirname "$sum_file")"
(
  cd "$artifact_dir"
  sha256sum -c SHA256SUMS.txt
)
pass "Artifact SHA-256 checksums"

manifest_result="$(node - "$manifest_file" "$VERSION" <<'NODE'
const fs = require('node:fs');
const [path, expectedVersion] = process.argv.slice(2);
const manifest = JSON.parse(fs.readFileSync(path, 'utf8'));
if (manifest.schema_version !== 'zarvis.windows-release.v1') throw new Error('unexpected schema');
if (manifest.version !== expectedVersion) throw new Error('version mismatch');
if (manifest.architecture !== 'win-x64') throw new Error('architecture mismatch');
if (manifest.self_contained !== true) throw new Error('client is not self-contained');
if (manifest.transport !== 'windows-openssh-local-forward') throw new Error('transport mismatch');
if (manifest.server_public_ingress !== false) throw new Error('public ingress invariant failed');
if (!Array.isArray(manifest.files) || manifest.files.length < 2) throw new Error('manifest files missing');
process.stdout.write(JSON.stringify({ signed: manifest.signed === true, source_sha: manifest.source_sha }));
NODE
)"

signed="$(node -e 'process.stdout.write(String(JSON.parse(process.argv[1]).signed))' "$manifest_result")"
source_sha="$(node -e 'process.stdout.write(JSON.parse(process.argv[1]).source_sha)' "$manifest_result")"

if [[ "$signed" != true ]]; then
  if [[ "$REQUIRE_SIGNED" == true ]]; then
    die "Artifact is unsigned; configure WINDOWS_SIGNING_CERT_PFX_BASE64 and WINDOWS_SIGNING_CERT_PASSWORD"
  fi
  warn "Artifact is unsigned. Windows SmartScreen may display a warning."
else
  pass "Authenticode signing recorded in release manifest"
fi

installer_name="$(basename "$installer")"
installer_hash="$(sha256sum "$installer" | awk '{print $1}')"

cat >"${artifact_dir}/Install-ZARVIS.ps1" <<EOF_PS
[CmdletBinding()]
param()
\$ErrorActionPreference = 'Stop'
\$directory = Split-Path -Parent \$MyInvocation.MyCommand.Path
\$installer = Join-Path \$directory '${installer_name}'
if (-not (Test-Path \$installer)) { throw 'Installer is missing.' }
\$expected = '${installer_hash}'
\$actual = (Get-FileHash \$installer -Algorithm SHA256).Hash.ToLowerInvariant()
if (\$actual -ne \$expected) { throw 'Z.A.R.V.I.S. installer SHA-256 mismatch.' }
Write-Host 'SHA-256 verified. Installing Z.A.R.V.I.S. ${VERSION}...'
\$process = Start-Process \$installer -Wait -PassThru
if (\$process.ExitCode -ne 0) { throw "Installer exited with code \$(\$process.ExitCode)." }
Write-Host 'Z.A.R.V.I.S. installation completed.'
EOF_PS

host_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
host_ip="${host_ip:-SERVER_IP}"
remote_dir="$artifact_dir"

cat >"${artifact_dir}/DEPLOY-TO-WINDOWS.txt" <<EOF_DEPLOY
Z.A.R.V.I.S. Windows ${VERSION}
Source SHA: ${source_sha}
Signed: ${signed}

Run in Windows PowerShell:

  New-Item -ItemType Directory -Force \"\$env:USERPROFILE\\Downloads\\ZARVIS-${VERSION}\" | Out-Null
  scp -r ${USER}@${host_ip}:${remote_dir}/\* \"\$env:USERPROFILE\\Downloads\\ZARVIS-${VERSION}\\\"
  powershell -ExecutionPolicy Bypass -File \"\$env:USERPROFILE\\Downloads\\ZARVIS-${VERSION}\\Install-ZARVIS.ps1\"

The installer contains no Owner Token, worker token, provider credential, or SSH private key.
EOF_DEPLOY

ln -sfn "$VERSION" "${STAGE_ROOT}/latest"
chmod -R go-rwx "$stage_dir" 2>/dev/null || true

if [[ "$PUBLISH_PUBLIC_RELEASE" == true ]]; then
  tag="zarvis-windows-v${VERSION}"
  gh release view "$tag" --repo "$REPOSITORY" >/dev/null ||
    die "Workflow passed but public release ${tag} was not found"
  pass "Public GitHub Release ${tag}"
fi

cat <<EOF_SUMMARY

============================================================
 Z.A.R.V.I.S. WINDOWS ARTIFACT: VERIFIED AND STAGED
============================================================
 Version:       ${VERSION}
 Workflow run:  ${run_id}
 Source SHA:    ${source_sha}
 Signed:        ${signed}
 Repository:    ${visibility}
 Public release:${PUBLISH_PUBLIC_RELEASE}
 Artifact:      ${artifact_dir}
 Installer:     ${installer_name}

Windows PowerShell:
  New-Item -ItemType Directory -Force \"\$env:USERPROFILE\\Downloads\\ZARVIS-${VERSION}\" | Out-Null
  scp -r ${USER}@${host_ip}:${remote_dir}/\* \"\$env:USERPROFILE\\Downloads\\ZARVIS-${VERSION}\\\"
  powershell -ExecutionPolicy Bypass -File \"\$env:USERPROFILE\\Downloads\\ZARVIS-${VERSION}\\Install-ZARVIS.ps1\"
============================================================
EOF_SUMMARY
