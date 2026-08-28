#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.1.0"
CONFIRM_LIVE=false
REMOVE_BACKUP=false
PUBLISH_PUBLIC_RELEASE=false
REQUIRE_SIGNED=false

log()  { printf '[ZARVIS-COMPLETE] %s\n' "$*"; }
pass() { printf '[ZARVIS-COMPLETE][PASS] %s\n' "$*"; }
warn() { printf '[ZARVIS-COMPLETE][WARN] %s\n' "$*" >&2; }
die()  { printf '[ZARVIS-COMPLETE][ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Complete Z.A.R.V.I.S. actual-host and Windows deployment

Usage:
  bash scripts/zarvis-complete-all.sh [version] --confirm-live [options]

Options:
  --confirm-live             Required. Permit backup/destroy/restore/rotation.
  --remove-backup            Remove the verified live-validation backup on pass.
  --publish-public-release   Publish Windows binaries in the public repository.
  --require-signed           Require Authenticode signing secrets and signed output.
  -h, --help                 Show this help.

Default behavior keeps the live backup, builds/stages Windows 0.1.0, and does
not publish a public GitHub Release.
USAGE
}

if [[ $# -gt 0 && "$1" != -* ]]; then
  VERSION="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm-live) CONFIRM_LIVE=true; shift ;;
    --remove-backup) REMOVE_BACKUP=true; shift ;;
    --publish-public-release) PUBLISH_PUBLIC_RELEASE=true; shift ;;
    --require-signed) REQUIRE_SIGNED=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$ ]] ||
  die "Version must be SemVer-like, for example 0.1.0"
[[ "$CONFIRM_LIVE" == true ]] || die "--confirm-live is required"

for command in git docker node npm curl openssl sha256sum ss gh; do
  command -v "$command" >/dev/null 2>&1 || die "$command is required"
done

docker info >/dev/null 2>&1 || die "Docker daemon unavailable or permission denied"
gh auth status >/dev/null 2>&1 || die "GitHub CLI is not authenticated; run: gh auth login"

cd "$ROOT_DIR"
[[ -d .git ]] || die "Not a Git repository: $ROOT_DIR"
git diff --quiet || die "Tracked working-tree changes must be committed or reverted"
git diff --cached --quiet || die "Staged changes must be committed or reverted"

git fetch origin --prune --tags
git switch main
git pull --ff-only origin main

if [[ -f .git/info/exclude ]]; then
  grep -qxF '/zarvis-windows-releases/' .git/info/exclude ||
    printf '/zarvis-windows-releases/\n' >> .git/info/exclude
  grep -qxF '/zarvis-deployment-records/' .git/info/exclude ||
    printf '/zarvis-deployment-records/\n' >> .git/info/exclude
fi

live_args=(--confirm-live)
[[ "$REMOVE_BACKUP" == true ]] && live_args+=(--remove-backup)

log "Running complete actual-host server validation"
bash scripts/zarvis-live-complete.sh "${live_args[@]}"

live_evidence="$(
  find "$ROOT_DIR/zarvis-live-evidence" \
    -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' |
    sort -n |
    tail -n 1 |
    cut -d' ' -f2-
)"
[[ -n "$live_evidence" ]] || die "Live evidence directory was not produced"

node - "$live_evidence/zarvis-actual-host-automated-validation.json" <<'NODE'
const fs = require('node:fs');
const path = process.argv[2];
const record = JSON.parse(fs.readFileSync(path, 'utf8'));
if (record.automated_actual_host_acceptance !== 'passed') {
  throw new Error('actual-host acceptance did not pass');
}
if (record.normal_live_settings_restored !== true) {
  throw new Error('normal live settings were not restored');
}
NODE
pass "Actual-host automated release validation"

windows_args=("$VERSION")
[[ "$PUBLISH_PUBLIC_RELEASE" == true ]] && windows_args+=(--publish-public-release)
[[ "$REQUIRE_SIGNED" == true ]] && windows_args+=(--require-signed)

log "Building, verifying, and staging the Windows client"
bash scripts/zarvis-windows-release.sh "${windows_args[@]}"

windows_manifest="$(
  find "$ROOT_DIR/zarvis-windows-releases/$VERSION" \
    -type f -name release-manifest.json -print -quit
)"
[[ -f "$windows_manifest" ]] || die "Verified Windows release manifest is missing"

record_dir="$ROOT_DIR/zarvis-deployment-records"
record_stamp="$(date +%Y%m%d-%H%M%S)"
record_path="$record_dir/${record_stamp}-zarvis-${VERSION}.json"
mkdir -p "$record_dir"
chmod 700 "$record_dir"

LIVE_EVIDENCE="$live_evidence" \
WINDOWS_MANIFEST="$windows_manifest" \
VERSION_VALUE="$VERSION" \
PUBLIC_RELEASE_VALUE="$PUBLISH_PUBLIC_RELEASE" \
node <<'NODE' >"$record_path"
const fs = require('node:fs');
const live = JSON.parse(fs.readFileSync(
  `${process.env.LIVE_EVIDENCE}/zarvis-actual-host-automated-validation.json`,
  'utf8'
));
const windows = JSON.parse(fs.readFileSync(process.env.WINDOWS_MANIFEST, 'utf8'));
const record = {
  schema_version: 'zarvis.complete-deployment.v1',
  completed_at: new Date().toISOString(),
  owner_github_id: '4076926',
  server: {
    source_sha: live.source_sha,
    automated_actual_host_acceptance: live.automated_actual_host_acceptance,
    normal_live_settings_restored: live.normal_live_settings_restored,
    evidence_directory: process.env.LIVE_EVIDENCE,
  },
  windows: {
    version: process.env.VERSION_VALUE,
    source_sha: windows.source_sha,
    architecture: windows.architecture,
    self_contained: windows.self_contained,
    signed: windows.signed,
    public_release: process.env.PUBLIC_RELEASE_VALUE === 'true',
    manifest: process.env.WINDOWS_MANIFEST,
  },
  manual_owner_device_acceptance: 'pending_windows_install_and_device_test',
};
process.stdout.write(`${JSON.stringify(record, null, 2)}\n`);
NODE
chmod 600 "$record_path"
pass "Complete deployment record"

cat <<EOF_SUMMARY

============================================================
 Z.A.R.V.I.S. SERVER + WINDOWS PIPELINE: COMPLETE
============================================================
 Server evidence:   $live_evidence
 Windows version:   $VERSION
 Windows manifest:  $windows_manifest
 Deployment record: $record_path
 Public release:    $PUBLISH_PUBLIC_RELEASE
 Require signed:    $REQUIRE_SIGNED

The Windows artifact is built, verified, and staged on zeaz-platform.
Run the PowerShell commands printed by zarvis-windows-release.sh to copy and
install it on Windows 11. Manual microphone/camera/screen tests remain owner-only.
============================================================
EOF_SUMMARY
