#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly ZWORKFORCE_VERSION="${ZWORKFORCE_VERSION:-3.0.4}"
readonly ZWORKFORCE_IMAGE="${ZWORKFORCE_IMAGE:-ghcr.io/cvsz/zworkforce:v${ZWORKFORCE_VERSION}}"
readonly INSTALL_PYTHON_PACKAGE="${INSTALL_PYTHON_PACKAGE:-1}"
readonly INSTALL_ZARVIS_WORKSPACE="${INSTALL_ZARVIS_WORKSPACE:-1}"
readonly PULL_ZWORKFORCE_IMAGE="${PULL_ZWORKFORCE_IMAGE:-0}"

log() {
    printf '%s\n' "$*"
}

log "========================================="
log "=== Initializing zWorkforce Environment"
log "========================================="
log "Version: $ZWORKFORCE_VERSION"
log "Image:   $ZWORKFORCE_IMAGE"

if command -v apt-get &> /dev/null; then
    log "--> Installing system package dependencies..."
    sudo apt-get update -y
    sudo apt-get install -y --no-install-recommends \
        curl wget git jq build-essential ca-certificates gnupg unzip htop net-tools
fi

if [ -n "${GIT_AUTHOR_NAME:-}" ] && [ -n "${GIT_AUTHOR_EMAIL:-}" ]; then
    log "--> Configuring Git identity..."
    git config --global user.name "$GIT_AUTHOR_NAME"
    git config --global user.email "$GIT_AUTHOR_EMAIL"
fi
git config --global init.defaultBranch main
git config --global pull.rebase false

if command -v npm &> /dev/null; then
    log "--> Setting up Node package managers..."
    npm install -g pnpm yarn --quiet
fi

if [ "$INSTALL_PYTHON_PACKAGE" = "1" ] && command -v python3 &> /dev/null; then
    log "--> Installing zWorkforce from $REPOSITORY_ROOT..."
    python3 -m pip install --upgrade pip setuptools wheel --quiet
    python3 -m pip install "$REPOSITORY_ROOT" --quiet
elif [ "$INSTALL_PYTHON_PACKAGE" = "1" ]; then
    log "--> Skipping Python package install: python3 is not available."
fi

if [ "$INSTALL_ZARVIS_WORKSPACE" = "1" ] && [ -f "$REPOSITORY_ROOT/packages/zarvis/pnpm-lock.yaml" ] && command -v pnpm &> /dev/null; then
    log "--> Installing ZARVIS workspace dependencies..."
    pnpm --dir "$REPOSITORY_ROOT/packages/zarvis" install --frozen-lockfile
elif [ "$INSTALL_ZARVIS_WORKSPACE" = "1" ] && [ -f "$REPOSITORY_ROOT/packages/zarvis/pnpm-lock.yaml" ]; then
    log "--> Skipping ZARVIS workspace install: pnpm is not available."
fi

if [ "$PULL_ZWORKFORCE_IMAGE" = "1" ]; then
    if command -v docker &> /dev/null; then
        log "--> Pulling zWorkforce container image..."
        docker pull "$ZWORKFORCE_IMAGE"
    else
        log "--> Skipping container image pull: docker is not available."
    fi
fi

log "========================================="
log "=== zWorkforce Environment Ready"
log "========================================="
