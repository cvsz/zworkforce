#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-./zarvis-local-backup}"
mkdir -p "${BACKUP_DIR}"
BACKUP_DIR="$(cd "${BACKUP_DIR}" && pwd)"
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 1; }

volumes=(zarvis_action_data zarvis_proactive_data)
files=()
for volume in "${volumes[@]}"; do
  docker volume inspect "${volume}" >/dev/null
  file="${volume}.tgz"
  docker run --rm \
    -v "${volume}:/data:ro" \
    -v "${BACKUP_DIR}:/backup" \
    alpine:3.22 \
    sh -eu -c "tar -C /data -czf /backup/${file} ."
  files+=("${file}")
done

manifest="${BACKUP_DIR}/zarvis-local-backup-manifest.json"
{
  printf '{\n  "schema_version": "zarvis.local-backup.v1",\n'
  printf '  "created_at": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '  "contains_secrets": false,\n'
  printf '  "archives": [\n'
  for index in "${!files[@]}"; do
    file="${files[$index]}"
    digest="$(sha256sum "${BACKUP_DIR}/${file}" | awk '{print $1}')"
    size="$(stat -c %s "${BACKUP_DIR}/${file}")"
    comma=','; [[ "${index}" -eq $((${#files[@]} - 1)) ]] && comma=''
    printf '    {"file":"%s","sha256":"%s","bytes":%s}%s\n' "${file}" "${digest}" "${size}" "${comma}"
  done
  printf '  ]\n}\n'
} >"${manifest}"

cat "${manifest}"
