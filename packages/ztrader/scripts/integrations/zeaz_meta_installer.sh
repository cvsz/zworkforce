#!/usr/bin/env bash
# zeaz_meta_installer.sh — Simple, safe generator/installer for MetaUltra
# Usage: ./scripts/zeaz_meta_installer.sh [--preview|--generate|--install|--release|--help] [--verbose]

set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
BUILD_DIR="$ROOT_DIR/build/metaultra"
VERBOSE=0
ACTION="preview"

log() {
  if [ "$VERBOSE" -eq 1 ]; then
    echo "[meta-installer] $*"
  fi
}

usage() {
  cat <<EOF
Usage: $0 [--preview|--generate|--install|--release] [--verbose]

Options:
  --preview    Show planned changes (default)
  --generate   Generate artifacts in $BUILD_DIR
  --install    Install generated artifacts into repository (idempotent)
  --release    Create a release tarball in $BUILD_DIR
  --dry-run    Alias for --preview
  --verbose    Enable verbose logs
  --help       Show this help
EOF
}

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --preview|--dry-run) ACTION=preview; shift ;;
    --generate) ACTION=generate; shift ;;
    --install) ACTION=install; shift ;;
    --release) ACTION=release; shift ;;
    --verbose) VERBOSE=1; shift ;;
    --help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 2 ;;
  esac
done

# planned file list
FILES=(
  "docs/metaultra/_index.md"
  "docs/metaultra/overview.md"
  "docs/metaultra/features.md"
  "docs/metaultra/options.md"
  "docs/metaultra/functions.md"
  "docs/metaultra/algorithms.md"
  "docs/metaultra/source-logic.md"
  "docs/metaultra/source-code.md"
  "docs/metaultra/data-structures.md"
  "docs/metaultra/modular-architecture.md"
  "tools/metaultra/example_module.py"
  "tools/metaultra/example_module.ts"
  "scripts/validate-metaultra.sh"
)

plan() {
  echo "Planned actions for: $ACTION"
  printf '%s\n' "${FILES[@]}" | sed 's/^/ - /'
}

generate() {
  log "Creating build dir: $BUILD_DIR"
  rm -rf "$BUILD_DIR"
  mkdir -p "$BUILD_DIR/docs/metaultra" "$BUILD_DIR/tools/metaultra"
  cp -R docs/metaultra "$BUILD_DIR/docs/"
  cp -R tools/metaultra "$BUILD_DIR/tools/"
  cp scripts/validate-metaultra.sh "$BUILD_DIR/"
  echo "Generated artifacts in $BUILD_DIR"
}

install_files() {
  for f in "${FILES[@]}"; do
    if [ -f "$f" ]; then
      log "Skipping existing: $f"
    else
      log "Missing: $f — will copy from build if available"
      src="$BUILD_DIR/$f"
      if [ -f "$src" ]; then
        mkdir -p "$(dirname "$f")"
        cp "$src" "$f"
        echo "Installed: $f"
      else
        echo "ERROR: Source "$src" not found; run --generate first" >&2
        return 2
      fi
    fi
  done
}

release() {
  generate
  pushd "$BUILD_DIR" >/dev/null
  TAR="metaultra-release-$(date +%Y%m%d%H%M%S).tar.gz"
  tar -czf "$TAR" .
  echo "Created release: $BUILD_DIR/$TAR"
  popd >/dev/null
}

case "$ACTION" in
  preview)
    plan
    ;;
  generate)
    generate
    ;;
  install)
    if [ ! -d "$BUILD_DIR" ]; then
      echo "Build directory not found. Running --generate first." && generate
    fi
    install_files
    ;;
  release)
    release
    ;;
  *)
    usage
    exit 2
    ;;
esac

exit 0
