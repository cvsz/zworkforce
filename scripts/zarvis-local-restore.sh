#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-./zarvis-local-backup}"
BACKUP_DIR="$(cd "${BACKUP_DIR}" && pwd)"
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 1; }

manifest="${BACKUP_DIR}/zarvis-local-backup-manifest.json"
[[ -f "${manifest}" ]] || { echo "backup manifest is missing" >&2; exit 1; }

restore_volume() {
  local volume="$1"
  local archive="${volume}.tgz"
  local expected actual
  [[ -f "${BACKUP_DIR}/${archive}" ]] || { echo "${archive} is missing" >&2; exit 1; }
  expected="$(node -e "const m=require(process.argv[1]);const a=m.archives.find(x=>x.file===process.argv[2]);if(!a)process.exit(2);process.stdout.write(a.sha256)" "${manifest}" "${archive}")"
  actual="$(sha256sum "${BACKUP_DIR}/${archive}" | awk '{print $1}')"
  [[ "${expected}" == "${actual}" ]] || { echo "checksum mismatch for ${archive}" >&2; exit 1; }
  docker volume create "${volume}" >/dev/null
  docker run --rm \
    -v "${volume}:/data" \
    -v "${BACKUP_DIR}:/backup:ro" \
    alpine:3.22 \
    sh -eu -c "find /data -mindepth 1 -delete; tar -C /data -xzf /backup/${archive}"
}

restore_volume zarvis_action_data
restore_volume zarvis_proactive_data

printf '{"schema_version":"zarvis.local-restore-operation.v1","restored":true,"contains_secrets":false,"volumes":["zarvis_action_data","zarvis_proactive_data"]}\n'
