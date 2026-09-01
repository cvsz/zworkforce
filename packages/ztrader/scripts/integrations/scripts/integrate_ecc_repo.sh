#!/usr/bin/env bash
set -euo pipefail

ECC_REPO_URL="${ECC_REPO_URL:-git@github.com:cvsz/everything-claude-code.git}"
ECC_TARGET_DIR="${ECC_TARGET_DIR:-external/everything-claude-code}"

if [[ -d "$ECC_TARGET_DIR/.git" ]]; then
  echo "[ECC] Repository already exists at $ECC_TARGET_DIR"
  echo "[ECC] Pulling latest changes..."
  git -C "$ECC_TARGET_DIR" pull --ff-only
else
  echo "[ECC] Cloning $ECC_REPO_URL into $ECC_TARGET_DIR"
  mkdir -p "$(dirname "$ECC_TARGET_DIR")"
  git clone "$ECC_REPO_URL" "$ECC_TARGET_DIR"
fi

echo "[ECC] Integration complete: $ECC_TARGET_DIR"
