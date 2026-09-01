#!/usr/bin/env bash
set -Eeuo pipefail

if [[ -d alembic ]]; then
  alembic upgrade head
else
  echo "Alembic environment not initialized yet; skipping migrations"
fi
