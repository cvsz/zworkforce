#!/usr/bin/env bash
set -Eeuo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is not installed; install it for full secret scanning"
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="$ROOT_DIR/.gitleaks.toml"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "missing gitleaks config at $CONFIG_PATH"
  exit 1
fi

SCAN_CANDIDATES=(
  src
  tests
  alembic
  .github
  .codex
  .agents
  docs
  Dockerfile.api
  Dockerfile.worker
  docker-compose.yml
  pyproject.toml
  Makefile
  README.md
  SECURITY.md
  AGENTS.md
  .env.example
)

TMP_SCAN_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_SCAN_DIR"' EXIT

for relative_path in "${SCAN_CANDIDATES[@]}"; do
  source_path="$ROOT_DIR/$relative_path"
  target_path="$TMP_SCAN_DIR/$relative_path"
  if [[ ! -e "$source_path" ]]; then
    continue
  fi
  mkdir -p "$(dirname "$target_path")"
  if [[ -d "$source_path" ]]; then
    cp -R "$source_path" "$target_path"
  else
    cp "$source_path" "$target_path"
  fi
done

gitleaks detect --source "$TMP_SCAN_DIR" --no-git --redact --config "$CONFIG_PATH"
