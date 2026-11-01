#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY_ROOT="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd
)"

readonly ZWORKFORCE_VERSION="${ZWORKFORCE_VERSION:-3.0.4}"
readonly ZWORKFORCE_IMAGE="${ZWORKFORCE_IMAGE:-ghcr.io/cvsz/zworkforce:v${ZWORKFORCE_VERSION}}"
readonly INSTALL_PYTHON_PACKAGE="${INSTALL_PYTHON_PACKAGE:-1}"
readonly INSTALL_ZARVIS_WORKSPACE="${INSTALL_ZARVIS_WORKSPACE:-1}"
readonly PULL_ZWORKFORCE_IMAGE="${PULL_ZWORKFORCE_IMAGE:-0}"
readonly ZWORKFORCE_VENV="${ZWORKFORCE_VENV:-${REPOSITORY_ROOT}/.venv}"

log() {
    printf '%s\n' "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

on_error() {
    local exit_code=$?
    printf 'ERROR: Bootstrap failed at line %s (exit code %s).\n' \
        "${BASH_LINENO[0]:-unknown}" "$exit_code" >&2
    exit "$exit_code"
}

trap on_error ERR

validate_boolean() {
    local name="$1"
    local value="$2"

    case "$value" in
        0|1) ;;
        *) die "$name must be 0 or 1; received: $value" ;;
    esac
}

validate_boolean INSTALL_PYTHON_PACKAGE "$INSTALL_PYTHON_PACKAGE"
validate_boolean INSTALL_ZARVIS_WORKSPACE "$INSTALL_ZARVIS_WORKSPACE"
validate_boolean PULL_ZWORKFORCE_IMAGE "$PULL_ZWORKFORCE_IMAGE"

log "========================================="
log "=== Initializing zWorkforce Environment"
log "========================================="
log "Version: $ZWORKFORCE_VERSION"
log "Image:   $ZWORKFORCE_IMAGE"
log "Repo:    $REPOSITORY_ROOT"

# ---------------------------------------------------------
# 1. System dependencies
# ---------------------------------------------------------

if command -v apt-get >/dev/null 2>&1; then
    log "--> Installing system package dependencies..."

    command -v sudo >/dev/null 2>&1 ||
        die "sudo is required to install system packages."

    APT_PACKAGES=(
        curl wget git jq build-essential ca-certificates
        gnupg unzip htop net-tools
    )

    if [[ "$INSTALL_PYTHON_PACKAGE" == "1" ]] &&
       command -v python3 >/dev/null 2>&1; then
        APT_PACKAGES+=(python3-venv)
    fi

    sudo apt-get update
    sudo apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}"
fi

# ---------------------------------------------------------
# 2. Git configuration
# ---------------------------------------------------------

if [[ -n "${GIT_AUTHOR_NAME:-}" &&
      -n "${GIT_AUTHOR_EMAIL:-}" ]]; then
    log "--> Configuring Git identity..."
    git config --global user.name "$GIT_AUTHOR_NAME"
    git config --global user.email "$GIT_AUTHOR_EMAIL"
fi

git config --global init.defaultBranch main
git config --global pull.rebase false

# ---------------------------------------------------------
# 3. Node package managers
# ---------------------------------------------------------

if command -v npm >/dev/null 2>&1; then
    log "--> Setting up Node package managers..."

    # Preserve the existing global installation approach.
    # Any installation failure must stop the bootstrap.
    npm install -g pnpm yarn --quiet
else
    log "--> Skipping Node package managers: npm is not available."
fi

# ---------------------------------------------------------
# 4. Python package installation in an isolated venv
# ---------------------------------------------------------

if [[ "$INSTALL_PYTHON_PACKAGE" == "1" ]]; then
    if ! command -v python3 >/dev/null 2>&1; then
        die "Python installation requested, but python3 is unavailable."
    fi

    log "--> Creating Python virtual environment..."
    log "    Environment: $ZWORKFORCE_VENV"

    if [[ -e "$ZWORKFORCE_VENV" &&
          ! -f "$ZWORKFORCE_VENV/pyvenv.cfg" ]]; then
        die "Venv path exists but is not a Python virtual environment: $ZWORKFORCE_VENV"
    fi

    mkdir -p "$(dirname -- "$ZWORKFORCE_VENV")"

    if [[ ! -f "$ZWORKFORCE_VENV/pyvenv.cfg" ]]; then
        python3 -m venv "$ZWORKFORCE_VENV"
    fi

    readonly VENV_PYTHON="$ZWORKFORCE_VENV/bin/python"

    [[ -x "$VENV_PYTHON" ]] ||
        die "Virtual environment Python not found: $VENV_PYTHON"

    log "--> Preparing Python build tools..."
    "$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

    log "--> Installing zWorkforce from $REPOSITORY_ROOT..."
    "$VENV_PYTHON" -m pip install "$REPOSITORY_ROOT"

    log "--> Verifying Python installation..."
    "$VENV_PYTHON" -m pip check

    log "Python environment ready: $ZWORKFORCE_VENV"
else
    log "--> Skipping Python package installation (disabled)."
fi

# ---------------------------------------------------------
# 5. ZARVIS workspace dependencies
# ---------------------------------------------------------

if [[ "$INSTALL_ZARVIS_WORKSPACE" == "1" &&
      -f "$REPOSITORY_ROOT/packages/zarvis/pnpm-lock.yaml" ]]; then

    command -v pnpm >/dev/null 2>&1 ||
        die "ZARVIS dependencies require pnpm, but pnpm is unavailable."

    log "--> Installing ZARVIS workspace dependencies..."

    pnpm --dir "$REPOSITORY_ROOT/packages/zarvis" \
        install --frozen-lockfile
else
    log "--> Skipping ZARVIS workspace installation."
fi

# ---------------------------------------------------------
# 6. Optional container image pull
# ---------------------------------------------------------

if [[ "$PULL_ZWORKFORCE_IMAGE" == "1" ]]; then
    command -v docker >/dev/null 2>&1 ||
        die "Container image pull requested, but Docker is unavailable."

    log "--> Pulling zWorkforce container image..."
    docker pull "$ZWORKFORCE_IMAGE"
fi

# ---------------------------------------------------------
# 7. Final verification
# ---------------------------------------------------------

log "========================================="
log "=== zWorkforce Environment Ready"
log "========================================="

if [[ "$INSTALL_PYTHON_PACKAGE" == "1" ]]; then
    log "Python: $ZWORKFORCE_VENV/bin/python"
fi
```