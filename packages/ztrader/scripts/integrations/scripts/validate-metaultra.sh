#!/usr/bin/env bash
# Simple validation: ensure metaultra docs and example modules exist
set -euo pipefail
FILES=(
  "docs/metaultra/_index.md"
  "docs/metaultra/overview.md"
  "tools/metaultra/example_module.py"
  "tools/metaultra/example_module.ts"
)

missing=0
for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "MISSING: $f"
    missing=1
  else
    echo "OK: $f"
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "Validation failed: some files are missing" >&2
  exit 2
fi

echo "Validation passed: all required files exist"
