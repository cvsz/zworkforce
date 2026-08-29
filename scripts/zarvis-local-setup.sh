#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.zarvis.local"
COMPOSE_FILE="${ROOT_DIR}/compose.zarvis-local.yml"

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "docker compose plugin is required" >&2; exit 1; }
command -v openssl >/dev/null 2>&1 || { echo "openssl is required" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "compose.zarvis-local.yml uses host networking and requires Linux/Ubuntu." >&2
  echo "On Windows/macOS, run the Node services directly from their README files." >&2
  exit 1
fi

umask 077
touch "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

ensure_value() {
  local name="$1" value="$2"
  grep -q "^${name}=" "${ENV_FILE}" || printf '%s=%s\n' "${name}" "${value}" >>"${ENV_FILE}"
}

ensure_value ZARVIS_ACTION_PORT 8098
ensure_value ZARVIS_ACTION_WORKER_INTERVAL_MS 1000
ensure_value ZARVIS_PROACTIVE_PORT 8099
ensure_value ZARVIS_PROACTIVE_WORKER_INTERVAL_MS 60000
ensure_value ZARVIS_PROACTIVE_CHECK_TIMEOUT_MS 3000
ensure_value ZARVIS_LOCAL_OWNER_TOKEN "$(openssl rand -hex 32)"
ensure_value ZARVIS_ACTION_WORKER_TOKEN "$(openssl rand -hex 32)"
ensure_value ZARVIS_PROACTIVE_WORKER_TOKEN "$(openssl rand -hex 32)"

read_setting() {
  sed -n "s/^$1=//p" "${ENV_FILE}" | tail -n 1
}

ACTION_PORT="$(read_setting ZARVIS_ACTION_PORT)"; ACTION_PORT="${ACTION_PORT:-8098}"
PROACTIVE_PORT="$(read_setting ZARVIS_PROACTIVE_PORT)"; PROACTIVE_PORT="${PROACTIVE_PORT:-8099}"
for item in "ACTION:${ACTION_PORT}" "PROACTIVE:${PROACTIVE_PORT}"; do
  name="${item%%:*}"; value="${item#*:}"
  if [[ ! "${value}" =~ ^[0-9]+$ ]] || (( value < 1024 || value > 65535 )); then
    echo "${name} port must be an integer between 1024 and 65535." >&2
    exit 1
  fi
done
if [[ "${ACTION_PORT}" == "${PROACTIVE_PORT}" ]]; then
  echo "Action and proactive ports must be different." >&2
  exit 1
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d

for _ in $(seq 1 45); do
  if curl --fail --silent "http://127.0.0.1:${ACTION_PORT}/healthz" >/dev/null \
    && curl --fail --silent "http://127.0.0.1:${PROACTIVE_PORT}/healthz" >/dev/null; then
    echo "Z.A.R.V.I.S. Local Action Console: http://127.0.0.1:${ACTION_PORT}"
    echo "Z.A.R.V.I.S. Proactive Console: http://127.0.0.1:${PROACTIVE_PORT}"
    echo "Use ZARVIS_LOCAL_OWNER_TOKEN from .env.zarvis.local to unlock both consoles."
    exit 0
  fi
  sleep 1
done

echo "Z.A.R.V.I.S. local services did not become healthy." >&2
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs --no-color
exit 1
