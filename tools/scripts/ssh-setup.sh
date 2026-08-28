#!/usr/bin/env bash
# ==============================================================================
# OMEGA SSH BOOTSTRAP
# ==============================================================================
# Hardened, idempotent per-host Ed25519 SSH key manager / bootstrapper
#
# Features
# ------------------------------------------------------------------------------
# - Dedicated Ed25519 key per host
# - Inventory-driven host management
# - Safe/idempotent re-runs
# - Existing private-key validation
# - Automatic missing .pub recovery
# - Managed ~/.ssh/config sections
# - Timestamped config backups
# - Config rollback on validation failure
# - Idempotent authorized_keys deployment
# - Passwordless authentication verification
# - Public-key-only verification
# - TCP/22 reachability preflight
# - Optional known_hosts scanning
# - Strict host-key mode
# - Selective --host execution
# - --dry-run
# - --force
# - Safe key rotation
# - Old-key backup
# - Rotation verifies new key BEFORE removing old key
# - Optional old remote key cleanup
# - Serial bootstrap by default
# - Optional parallel non-interactive verification
# - Structured per-host summary
# - Predictable exit codes
#
# Designed for:
#   Linux / Bash 4+
#
# Example:
#   ./omega-ssh.sh
#   ./omega-ssh.sh --dry-run
#   ./omega-ssh.sh --host core
#   ./omega-ssh.sh --host ha-node-a --host ha-node-b
#   ./omega-ssh.sh --scan-known-hosts
#   ./omega-ssh.sh --strict-host-key
#   ./omega-ssh.sh --rotate --host core --yes
#   ./omega-ssh.sh --parallel 3
#
# IMPORTANT
# ------------------------------------------------------------------------------
# Initial password-based ssh-copy-id deployment is intentionally SERIAL.
# Parallel mode is most useful after passwordless access already exists.
# ==============================================================================

set -Eeuo pipefail

PROGRAM_NAME="${0##*/}"

# ==============================================================================
# Configuration
# ==============================================================================

REMOTE_USER="cvsz"

SSH_DIR="${HOME}/.ssh"
SSH_CONFIG="${SSH_DIR}/config"
KNOWN_HOSTS="${SSH_DIR}/known_hosts"
BACKUP_DIR="${SSH_DIR}/omega-backups"

CONNECT_TIMEOUT=5
SERVER_ALIVE_INTERVAL=30
SERVER_ALIVE_COUNT_MAX=3
CONTROL_PERSIST="10m"

SSH_PORT=22

# Default host-key policy.
#
# accept-new:
#   First connection is trusted automatically, but changed keys fail.
#
# strict:
#   Host must already exist in known_hosts.
#
HOST_KEY_MODE="accept-new"

# ==============================================================================
# Inventory
# ==============================================================================
#
# Format:
#
#   "FQDN|SHORTNAME|IP|PORT"
#
# Add hosts here.
#
HOSTS=(
    "ha-a.zeaz.dev|ha-node-a|192.168.74.134|22"
    "ha-b.zeaz.dev|ha-node-b|192.168.74.135|22"
    "core.zeaz.dev|core|192.168.74.130|22"
)

# ==============================================================================
# Runtime options
# ==============================================================================

DRY_RUN=0
FORCE=0
ROTATE=0
YES=0

SCAN_KNOWN_HOSTS=0
STRICT_HOST_KEY=0

DEPLOY_KEYS=1
TEST_CONNECTIONS=1
REMOVE_OLD_REMOTE_KEY=1

PARALLEL=1

SELECTED_HOSTS=()

# ==============================================================================
# Runtime state
# ==============================================================================

declare -A REACHABILITY_STATUS=()
declare -A KEY_STATUS=()
declare -A CONFIG_STATUS=()
declare -A DEPLOY_STATUS=()
declare -A AUTH_STATUS=()
declare -A ROTATION_STATUS=()

CURRENT_CONFIG_BACKUP=""

# ==============================================================================
# Logging
# ==============================================================================

timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log() {
    printf '%s\n' "$*"
}

info() {
    printf '[*] %s\n' "$*"
}

ok() {
    printf '[+] %s\n' "$*"
}

warn() {
    printf '[!] %s\n' "$*" >&2
}

error() {
    printf '[ERROR] %s\n' "$*" >&2
}

die() {
    error "$*"
    exit 1
}

section() {
    printf '\n'
    printf '%s\n' "======================================================================"
    printf ' %s\n' "$1"
    printf '%s\n' "======================================================================"
}

run() {
    if (( DRY_RUN )); then
        printf '[DRY-RUN] '

        printf '%q ' "$@"

        printf '\n'
        return 0
    fi

    "$@"
}

# ==============================================================================
# CLI
# ==============================================================================

usage() {
    cat <<EOF
${PROGRAM_NAME} - Omega SSH Bootstrap

Usage:
  ${PROGRAM_NAME} [OPTIONS]

Host selection:
  --host NAME
      Only process one host.
      Can be specified multiple times.

Key management:
  --rotate
      Safely rotate dedicated host SSH keys.

  --yes
      Required for unattended destructive rotation operations.

  --keep-old-remote-key
      After successful rotation, leave the old public key in
      authorized_keys.

Execution:
  --dry-run
      Show intended actions without modifying anything.

  --force
      Reapply configuration/deployment where appropriate.

  --no-deploy
      Generate/configure locally but do not deploy keys.

  --no-test
      Skip final SSH authentication tests.

  --parallel N
      Parallelize final passwordless verification.

      Initial password-based deployment remains serial.

Host-key management:
  --scan-known-hosts
      Fetch SSH host keys using ssh-keyscan.

      WARNING:
      ssh-keyscan does NOT authenticate the host.
      Verify fingerprints through a trusted channel.

  --strict-host-key
      Require hosts to already exist in known_hosts.

General:
  -h, --help
      Show this help.

Examples:

  ${PROGRAM_NAME}

  ${PROGRAM_NAME} --dry-run

  ${PROGRAM_NAME} --host core

  ${PROGRAM_NAME} --host ha-node-a --host ha-node-b

  ${PROGRAM_NAME} --scan-known-hosts

  ${PROGRAM_NAME} --strict-host-key

  ${PROGRAM_NAME} --rotate --host core --yes

  ${PROGRAM_NAME} --parallel 3
EOF
}

while (( $# > 0 )); do
    case "$1" in
        --host)
            [[ $# -ge 2 ]] || die "--host requires a value"
            SELECTED_HOSTS+=("$2")
            shift 2
            ;;

        --rotate)
            ROTATE=1
            shift
            ;;

        --yes)
            YES=1
            shift
            ;;

        --dry-run)
            DRY_RUN=1
            shift
            ;;

        --force)
            FORCE=1
            shift
            ;;

        --scan-known-hosts)
            SCAN_KNOWN_HOSTS=1
            shift
            ;;

        --strict-host-key)
            STRICT_HOST_KEY=1
            HOST_KEY_MODE="strict"
            shift
            ;;

        --no-deploy)
            DEPLOY_KEYS=0
            shift
            ;;

        --no-test)
            TEST_CONNECTIONS=0
            shift
            ;;

        --keep-old-remote-key)
            REMOVE_OLD_REMOTE_KEY=0
            shift
            ;;

        --parallel)
            [[ $# -ge 2 ]] || die "--parallel requires a number"

            [[ "$2" =~ ^[1-9][0-9]*$ ]] ||
                die "Invalid --parallel value: $2"

            PARALLEL="$2"

            shift 2
            ;;

        -h|--help)
            usage
            exit 0
            ;;

        *)
            die "Unknown argument: $1"
            ;;
    esac
done

# ==============================================================================
# Utility functions
# ==============================================================================

require_command() {
    command -v "$1" >/dev/null 2>&1 ||
        die "Required command not found: $1"
}

host_selected() {
    local shortname="$1"

    if (( ${#SELECTED_HOSTS[@]} == 0 )); then
        return 0
    fi

    local requested

    for requested in "${SELECTED_HOSTS[@]}"; do
        if [[ "${requested}" == "${shortname}" ]]; then
            return 0
        fi
    done

    return 1
}

inventory_contains_host() {
    local requested="$1"
    local entry fqdn shortname ip port

    for entry in "${HOSTS[@]}"; do
        IFS='|' read -r fqdn shortname ip port <<<"${entry}"

        if [[ "${requested}" == "${shortname}" ]]; then
            return 0
        fi
    done

    return 1
}

validate_selected_hosts() {
    local requested

    for requested in "${SELECTED_HOSTS[@]}"; do
        inventory_contains_host "${requested}" ||
            die "Unknown host requested with --host: ${requested}"
    done
}

validate_ipv4() {
    local ip="$1"
    local octets
    local octet

    [[ "${ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] ||
        return 1

    IFS='.' read -r -a octets <<<"${ip}"

    (( ${#octets[@]} == 4 )) ||
        return 1

    for octet in "${octets[@]}"; do
        [[ "${octet}" =~ ^[0-9]+$ ]] ||
            return 1

        (( 10#${octet} >= 0 && 10#${octet} <= 255 )) ||
            return 1
    done
}

validate_inventory() {
    local entry
    local fqdn shortname ip port

    declare -A seen_names=()
    declare -A seen_ips=()

    for entry in "${HOSTS[@]}"; do
        IFS='|' read -r fqdn shortname ip port <<<"${entry}"

        [[ -n "${fqdn}" ]] ||
            die "Inventory entry has empty FQDN: ${entry}"

        [[ -n "${shortname}" ]] ||
            die "Inventory entry has empty shortname: ${entry}"

        [[ "${fqdn}" =~ ^[A-Za-z0-9.-]+$ ]] ||
            die "Invalid FQDN: ${fqdn}"

        [[ "${shortname}" =~ ^[A-Za-z0-9._-]+$ ]] ||
            die "Invalid host shortname: ${shortname}"

        validate_ipv4 "${ip}" ||
            die "Invalid IPv4 address: ${ip}"

        [[ "${port}" =~ ^[0-9]+$ ]] ||
            die "Invalid SSH port for ${shortname}: ${port}"

        (( port >= 1 && port <= 65535 )) ||
            die "SSH port out of range for ${shortname}: ${port}"

        [[ -z "${seen_names[$shortname]:-}" ]] ||
            die "Duplicate shortname in inventory: ${shortname}"

        [[ -z "${seen_ips[$ip]:-}" ]] ||
            warn "Duplicate IP detected in inventory: ${ip}"

        seen_names["${shortname}"]=1
        seen_ips["${ip}"]=1
    done
}

# ==============================================================================
# SSH directory
# ==============================================================================

prepare_ssh_directory() {
    if (( DRY_RUN )); then
        info "Would prepare ${SSH_DIR}"
        return
    fi

    mkdir -p "${SSH_DIR}"
    chmod 700 "${SSH_DIR}"

    mkdir -p "${BACKUP_DIR}"
    chmod 700 "${BACKUP_DIR}"

    if [[ -e "${SSH_CONFIG}" && ! -f "${SSH_CONFIG}" ]]; then
        die "${SSH_CONFIG} exists but is not a regular file"
    fi

    touch "${SSH_CONFIG}"
    chmod 600 "${SSH_CONFIG}"

    touch "${KNOWN_HOSTS}"
    chmod 600 "${KNOWN_HOSTS}"
}

# ==============================================================================
# Reachability
# ==============================================================================

tcp_check() {
    local ip="$1"
    local port="$2"

    if command -v nc >/dev/null 2>&1; then
        nc -z -w "${CONNECT_TIMEOUT}" "${ip}" "${port}" >/dev/null 2>&1
        return
    fi

    if command -v timeout >/dev/null 2>&1; then
        timeout "${CONNECT_TIMEOUT}" \
            bash -c "exec 3<>/dev/tcp/${ip}/${port}" \
            >/dev/null 2>&1
        return
    fi

    # Last-resort SSH TCP/connect check.
    ssh \
        -o BatchMode=yes \
        -o ConnectTimeout="${CONNECT_TIMEOUT}" \
        -o ConnectionAttempts=1 \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -p "${port}" \
        "${REMOTE_USER}@${ip}" \
        true \
        >/dev/null 2>&1
}

check_reachability() {
    local shortname="$1"
    local ip="$2"
    local port="$3"

    info "Checking TCP ${ip}:${port}"

    if tcp_check "${ip}" "${port}"; then
        REACHABILITY_STATUS["${shortname}"]="UP"
        ok "${shortname}: SSH port reachable"
        return 0
    fi

    REACHABILITY_STATUS["${shortname}"]="DOWN"
    warn "${shortname}: ${ip}:${port} is unreachable"
    return 1
}

# ==============================================================================
# Known hosts
# ==============================================================================

scan_known_host() {
    local fqdn="$1"
    local shortname="$2"
    local ip="$3"
    local port="$4"

    (( SCAN_KNOWN_HOSTS )) || return 0

    require_command ssh-keyscan

    info "Scanning SSH host key for ${shortname}"

    if (( DRY_RUN )); then
        printf '[DRY-RUN] ssh-keyscan -p %q -H %q\n' "${port}" "${ip}"
        return 0
    fi

    local tmp
    tmp="$(mktemp "${SSH_DIR}/known-hosts.XXXXXX")"

    if ! ssh-keyscan \
        -T "${CONNECT_TIMEOUT}" \
        -p "${port}" \
        -H \
        "${ip}" \
        >"${tmp}" 2>/dev/null
    then
        rm -f "${tmp}"
        warn "ssh-keyscan failed for ${shortname}"
        return 1
    fi

    if [[ ! -s "${tmp}" ]]; then
        rm -f "${tmp}"
        warn "No host keys returned for ${shortname}"
        return 1
    fi

    # Remove stale unhashed entries if any.
    ssh-keygen -R "${ip}" -f "${KNOWN_HOSTS}" >/dev/null 2>&1 || true

    if [[ "${port}" != "22" ]]; then
        ssh-keygen \
            -R "[${ip}]:${port}" \
            -f "${KNOWN_HOSTS}" \
            >/dev/null 2>&1 || true
    fi

    cat "${tmp}" >>"${KNOWN_HOSTS}"

    rm -f "${tmp}"

    chmod 600 "${KNOWN_HOSTS}"

    ok "known_hosts updated for ${shortname}"

    warn "Verify the host fingerprint through a trusted channel."
}

host_key_options() {
    if [[ "${HOST_KEY_MODE}" == "strict" ]]; then
        printf '%s\n' \
            "-o" \
            "StrictHostKeyChecking=yes"
    else
        printf '%s\n' \
            "-o" \
            "StrictHostKeyChecking=accept-new"
    fi
}

# ==============================================================================
# Key management
# ==============================================================================

key_path_for() {
    printf '%s/id_ed25519_%s' "${SSH_DIR}" "$1"
}

validate_private_key() {
    local key_path="$1"

    ssh-keygen -y -f "${key_path}" >/dev/null 2>&1
}

generate_key() {
    local fqdn="$1"
    local shortname="$2"

    local key_path
    key_path="$(key_path_for "${shortname}")"

    if [[ -e "${key_path}" && "${FORCE}" -eq 0 ]]; then
        if [[ ! -f "${key_path}" ]]; then
            die "Key path exists but is not a regular file: ${key_path}"
        fi

        chmod 600 "${key_path}" 2>/dev/null || true

        if ! validate_private_key "${key_path}"; then
            die "Existing private key is invalid: ${key_path}"
        fi

        if [[ ! -f "${key_path}.pub" ]]; then
            warn "${shortname}: missing public key; rebuilding"

            if (( ! DRY_RUN )); then
                ssh-keygen -y \
                    -f "${key_path}" \
                    >"${key_path}.pub"

                chmod 644 "${key_path}.pub"
            fi
        fi

        KEY_STATUS["${shortname}"]="EXISTING"
        ok "${shortname}: existing key validated"
        return
    fi

    if [[ -e "${key_path}" && "${FORCE}" -eq 1 ]]; then
        warn "--force does not overwrite private keys."
        warn "Use --rotate for key replacement."

        KEY_STATUS["${shortname}"]="EXISTING"
        return
    fi

    info "Generating dedicated Ed25519 key for ${shortname}"

    if (( DRY_RUN )); then
        printf '[DRY-RUN] ssh-keygen -t ed25519 -f %q\n' "${key_path}"

        KEY_STATUS["${shortname}"]="WOULD-GENERATE"
        return
    fi

    ssh-keygen \
        -t ed25519 \
        -C "${REMOTE_USER}@${fqdn}" \
        -f "${key_path}" \
        -N "" \
        -q

    chmod 600 "${key_path}"
    chmod 644 "${key_path}.pub"

    KEY_STATUS["${shortname}"]="GENERATED"

    ok "${shortname}: key generated"
}

# ==============================================================================
# SSH config backup
# ==============================================================================

backup_config() {
    [[ -s "${SSH_CONFIG}" ]] || return 0

    local stamp
    stamp="$(date '+%Y%m%d-%H%M%S')"

    CURRENT_CONFIG_BACKUP="${BACKUP_DIR}/config.${stamp}.$$"

    if (( DRY_RUN )); then
        info "Would backup config to ${CURRENT_CONFIG_BACKUP}"
        return
    fi

    cp -p "${SSH_CONFIG}" "${CURRENT_CONFIG_BACKUP}"

    chmod 600 "${CURRENT_CONFIG_BACKUP}"

    ok "SSH config backup: ${CURRENT_CONFIG_BACKUP}"
}

restore_config() {
    [[ -n "${CURRENT_CONFIG_BACKUP}" ]] || return 0
    [[ -f "${CURRENT_CONFIG_BACKUP}" ]] || return 0

    warn "Restoring SSH config from backup"

    cp -p "${CURRENT_CONFIG_BACKUP}" "${SSH_CONFIG}"

    chmod 600 "${SSH_CONFIG}"
}

# ==============================================================================
# Managed SSH config blocks
# ==============================================================================

remove_managed_block() {
    local shortname="$1"

    local begin="# >>> OMEGA_SSH_${shortname} >>>"
    local end="# <<< OMEGA_SSH_${shortname} <<<"

    local tmp
    tmp="$(mktemp "${SSH_DIR}/omega-config.XXXXXX")"

    awk \
        -v begin="${begin}" \
        -v end="${end}" '
            $0 == begin {
                managed = 1
                next
            }

            managed && $0 == end {
                managed = 0
                next
            }

            !managed {
                print
            }
        ' "${SSH_CONFIG}" >"${tmp}"

    chmod 600 "${tmp}"

    mv "${tmp}" "${SSH_CONFIG}"
}

write_host_config() {
    local fqdn="$1"
    local shortname="$2"
    local ip="$3"
    local port="$4"

    local key_path
    key_path="$(key_path_for "${shortname}")"

    if (( DRY_RUN )); then
        info "Would create managed SSH config block for ${shortname}"

        CONFIG_STATUS["${shortname}"]="WOULD-CONFIGURE"
        return
    fi

    remove_managed_block "${shortname}"

    cat >>"${SSH_CONFIG}" <<EOF

# >>> OMEGA_SSH_${shortname} >>>
Host ${shortname} ${fqdn}
    HostName ${ip}
    Port ${port}
    User ${REMOTE_USER}

    IdentityFile ${key_path}
    IdentitiesOnly yes
    PubkeyAuthentication yes

    ConnectTimeout ${CONNECT_TIMEOUT}

    ServerAliveInterval ${SERVER_ALIVE_INTERVAL}
    ServerAliveCountMax ${SERVER_ALIVE_COUNT_MAX}

    ForwardAgent no

    ControlMaster auto
    ControlPath ${SSH_DIR}/cm-%C
    ControlPersist ${CONTROL_PERSIST}
# <<< OMEGA_SSH_${shortname} <<<
EOF

    chmod 600 "${SSH_CONFIG}"

    CONFIG_STATUS["${shortname}"]="CONFIGURED"

    ok "${shortname}: SSH config updated"
}

validate_ssh_config() {
    local entry
    local fqdn shortname ip port

    for entry in "${HOSTS[@]}"; do
        IFS='|' read -r fqdn shortname ip port <<<"${entry}"

        host_selected "${shortname}" || continue

        if ! ssh -G "${shortname}" >/dev/null 2>&1; then
            error "SSH config validation failed for ${shortname}"

            restore_config

            die "Invalid generated SSH configuration"
        fi
    done

    ok "SSH configuration validation passed"
}

# ==============================================================================
# Key deployment
# ==============================================================================

deploy_with_copy_id() {
    local ip="$1"
    local port="$2"
    local pub="$3"

    local strict_option

    if [[ "${HOST_KEY_MODE}" == "strict" ]]; then
        strict_option="yes"
    else
        strict_option="accept-new"
    fi

    ssh-copy-id \
        -i "${pub}" \
        -p "${port}" \
        -o ConnectTimeout="${CONNECT_TIMEOUT}" \
        -o StrictHostKeyChecking="${strict_option}" \
        "${REMOTE_USER}@${ip}"
}

deploy_with_fallback() {
    local ip="$1"
    local port="$2"
    local pub="$3"

    local strict_option

    if [[ "${HOST_KEY_MODE}" == "strict" ]]; then
        strict_option="yes"
    else
        strict_option="accept-new"
    fi

    cat "${pub}" |
        ssh \
            -p "${port}" \
            -o ConnectTimeout="${CONNECT_TIMEOUT}" \
            -o StrictHostKeyChecking="${strict_option}" \
            "${REMOTE_USER}@${ip}" \
            '
                set -eu

                umask 077

                mkdir -p "$HOME/.ssh"
                chmod 700 "$HOME/.ssh"

                touch "$HOME/.ssh/authorized_keys"
                chmod 600 "$HOME/.ssh/authorized_keys"

                IFS= read -r incoming_key

                if ! grep -qxF \
                    "$incoming_key" \
                    "$HOME/.ssh/authorized_keys"
                then
                    printf "%s\n" \
                        "$incoming_key" \
                        >>"$HOME/.ssh/authorized_keys"
                fi
            '
}

deploy_key() {
    local shortname="$1"
    local ip="$2"
    local port="$3"

    local key
    key="$(key_path_for "${shortname}")"

    local pub="${key}.pub"

    if (( ! DEPLOY_KEYS )); then
        DEPLOY_STATUS["${shortname}"]="SKIPPED"
        return 0
    fi

    if (( DRY_RUN )); then
        info "Would deploy ${pub} to ${REMOTE_USER}@${ip}:${port}"

        DEPLOY_STATUS["${shortname}"]="WOULD-DEPLOY"
        return 0
    fi

    [[ -f "${pub}" ]] ||
        {
            DEPLOY_STATUS["${shortname}"]="FAILED"
            error "Missing public key: ${pub}"
            return 1
        }

    info "Deploying key to ${shortname}"

    if command -v ssh-copy-id >/dev/null 2>&1; then
        if deploy_with_copy_id \
            "${ip}" \
            "${port}" \
            "${pub}"
        then
            DEPLOY_STATUS["${shortname}"]="SUCCESS"

            ok "${shortname}: key deployed"
            return 0
        fi

        warn "${shortname}: ssh-copy-id failed; trying fallback"
    fi

    if deploy_with_fallback \
        "${ip}" \
        "${port}" \
        "${pub}"
    then
        DEPLOY_STATUS["${shortname}"]="SUCCESS"

        ok "${shortname}: key deployed through fallback"
        return 0
    fi

    DEPLOY_STATUS["${shortname}"]="FAILED"

    error "${shortname}: key deployment failed"

    return 1
}

# ==============================================================================
# Authentication testing
# ==============================================================================

verify_key_direct() {
    local ip="$1"
    local port="$2"
    local key="$3"

    local strict_option

    if [[ "${HOST_KEY_MODE}" == "strict" ]]; then
        strict_option="yes"
    else
        strict_option="accept-new"
    fi

    ssh \
        -i "${key}" \
        -p "${port}" \
        -o IdentitiesOnly=yes \
        -o BatchMode=yes \
        -o PasswordAuthentication=no \
        -o KbdInteractiveAuthentication=no \
        -o PreferredAuthentications=publickey \
        -o StrictHostKeyChecking="${strict_option}" \
        -o ConnectTimeout="${CONNECT_TIMEOUT}" \
        "${REMOTE_USER}@${ip}" \
        true
}

verify_alias() {
    local shortname="$1"

    if (( ! TEST_CONNECTIONS )); then
        AUTH_STATUS["${shortname}"]="SKIPPED"
        return 0
    fi

    if (( DRY_RUN )); then
        AUTH_STATUS["${shortname}"]="WOULD-TEST"
        return 0
    fi

    if ssh \
        -o BatchMode=yes \
        -o PasswordAuthentication=no \
        -o KbdInteractiveAuthentication=no \
        -o PreferredAuthentications=publickey \
        -o ConnectTimeout="${CONNECT_TIMEOUT}" \
        "${shortname}" \
        true
    then
        AUTH_STATUS["${shortname}"]="SUCCESS"

        ok "${shortname}: passwordless authentication verified"

        return 0
    fi

    AUTH_STATUS["${shortname}"]="FAILED"

    error "${shortname}: passwordless authentication failed"

    return 1
}

# ==============================================================================
# Safe key rotation
# ==============================================================================

remove_remote_old_key() {
    local ip="$1"
    local port="$2"
    local new_key="$3"
    local old_pub_file="$4"

    [[ -f "${old_pub_file}" ]] || return 0

    local old_key

    old_key="$(cat "${old_pub_file}")"

    # Authenticate using the NEW key.
    #
    # Send old key over stdin. Do not interpolate it into remote shell code.
    #
    printf '%s\n' "${old_key}" |
        ssh \
            -i "${new_key}" \
            -p "${port}" \
            -o IdentitiesOnly=yes \
            -o BatchMode=yes \
            -o PasswordAuthentication=no \
            -o KbdInteractiveAuthentication=no \
            "${REMOTE_USER}@${ip}" \
            '
                set -eu

                IFS= read -r key_to_remove

                file="$HOME/.ssh/authorized_keys"

                [ -f "$file" ] || exit 0

                tmp="${file}.omega.$$"

                grep -vxF \
                    "$key_to_remove" \
                    "$file" \
                    >"$tmp" || true

                chmod 600 "$tmp"

                mv "$tmp" "$file"
            '
}

rotate_host_key() {
    local fqdn="$1"
    local shortname="$2"
    local ip="$3"
    local port="$4"

    local key
    key="$(key_path_for "${shortname}")"

    if [[ ! -f "${key}" ]]; then
        warn "${shortname}: no old key exists; generating normally"

        generate_key "${fqdn}" "${shortname}"

        ROTATION_STATUS["${shortname}"]="NOT-NEEDED"

        return
    fi

    if (( ! YES && ! DRY_RUN )); then
        die "--rotate requires --yes for safety"
    fi

    local stamp
    stamp="$(date '+%Y%m%d-%H%M%S')"

    local temp_key="${key}.new.${stamp}"
    local backup_key="${BACKUP_DIR}/$(basename "${key}").${stamp}"
    local backup_pub="${backup_key}.pub"

    info "${shortname}: generating replacement key"

    if (( DRY_RUN )); then
        info "Would generate ${temp_key}"
        info "Would deploy and verify replacement key"
        info "Would backup old key to ${backup_key}"
        info "Would activate replacement only after successful verification"

        ROTATION_STATUS["${shortname}"]="WOULD-ROTATE"

        return
    fi

    ssh-keygen \
        -t ed25519 \
        -C "${REMOTE_USER}@${fqdn}" \
        -f "${temp_key}" \
        -N "" \
        -q

    chmod 600 "${temp_key}"
    chmod 644 "${temp_key}.pub"

    # --------------------------------------------------------------------------
    # Step 1: deploy new public key while old key remains valid
    # --------------------------------------------------------------------------

    info "${shortname}: deploying replacement public key"

    if command -v ssh-copy-id >/dev/null 2>&1; then
        if ! ssh-copy-id \
            -i "${temp_key}.pub" \
            -p "${port}" \
            -o ConnectTimeout="${CONNECT_TIMEOUT}" \
            "${REMOTE_USER}@${ip}"
        then
            rm -f "${temp_key}" "${temp_key}.pub"

            ROTATION_STATUS["${shortname}"]="FAILED-DEPLOY"

            error "${shortname}: replacement key deployment failed"

            return 1
        fi
    else
        if ! deploy_with_fallback \
            "${ip}" \
            "${port}" \
            "${temp_key}.pub"
        then
            rm -f "${temp_key}" "${temp_key}.pub"

            ROTATION_STATUS["${shortname}"]="FAILED-DEPLOY"

            return 1
        fi
    fi

    # --------------------------------------------------------------------------
    # Step 2: verify the NEW key directly
    # --------------------------------------------------------------------------

    info "${shortname}: verifying replacement key"

    if ! verify_key_direct \
        "${ip}" \
        "${port}" \
        "${temp_key}"
    then
        error "${shortname}: new key verification FAILED"
        warn "Old key remains untouched."

        rm -f "${temp_key}" "${temp_key}.pub"

        ROTATION_STATUS["${shortname}"]="FAILED-VERIFY"

        return 1
    fi

    ok "${shortname}: replacement key verified"

    # --------------------------------------------------------------------------
    # Step 3: backup old key
    # --------------------------------------------------------------------------

    cp -p "${key}" "${backup_key}"

    if [[ -f "${key}.pub" ]]; then
        cp -p "${key}.pub" "${backup_pub}"
    else
        ssh-keygen -y \
            -f "${key}" \
            >"${backup_pub}"
    fi

    chmod 600 "${backup_key}"
    chmod 644 "${backup_pub}"

    # --------------------------------------------------------------------------
    # Step 4: activate new key locally
    # --------------------------------------------------------------------------

    mv "${temp_key}" "${key}"
    mv "${temp_key}.pub" "${key}.pub"

    chmod 600 "${key}"
    chmod 644 "${key}.pub"

    # --------------------------------------------------------------------------
    # Step 5: verify normal configured alias
    # --------------------------------------------------------------------------

    if ! verify_alias "${shortname}"; then
        error "${shortname}: activated key failed through SSH config"

        warn "Restoring previous local key"

        cp -p "${backup_key}" "${key}"
        cp -p "${backup_pub}" "${key}.pub"

        chmod 600 "${key}"
        chmod 644 "${key}.pub"

        ROTATION_STATUS["${shortname}"]="ROLLED-BACK"

        return 1
    fi

    # --------------------------------------------------------------------------
    # Step 6: optionally delete old remote public key
    # --------------------------------------------------------------------------

    if (( REMOVE_OLD_REMOTE_KEY )); then
        info "${shortname}: removing old key from remote authorized_keys"

        if remove_remote_old_key \
            "${ip}" \
            "${port}" \
            "${key}" \
            "${backup_pub}"
        then
            ok "${shortname}: old remote key removed"
        else
            warn "${shortname}: unable to remove old remote key"
            warn "New key remains functional."
        fi
    else
        warn "${shortname}: old remote key retained by request"
    fi

    ROTATION_STATUS["${shortname}"]="SUCCESS"

    KEY_STATUS["${shortname}"]="ROTATED"

    ok "${shortname}: key rotation completed"

    ok "Old key backup: ${backup_key}"
}

# ==============================================================================
# Summary
# ==============================================================================

print_summary() {
    section "OMEGA SSH SUMMARY"

    printf '%-16s %-8s %-12s %-12s %-12s %-12s %-14s\n' \
        "HOST" \
        "PORT" \
        "NETWORK" \
        "KEY" \
        "CONFIG" \
        "DEPLOY" \
        "AUTH"

    printf '%-16s %-8s %-12s %-12s %-12s %-12s %-14s\n' \
        "----------------" \
        "--------" \
        "------------" \
        "------------" \
        "------------" \
        "------------" \
        "--------------"

    local entry
    local fqdn shortname ip port
    local failures=0

    for entry in "${HOSTS[@]}"; do
        IFS='|' read -r fqdn shortname ip port <<<"${entry}"

        host_selected "${shortname}" || continue

        local network="${REACHABILITY_STATUS[$shortname]:-N/A}"
        local key="${KEY_STATUS[$shortname]:-N/A}"
        local config="${CONFIG_STATUS[$shortname]:-N/A}"
        local deploy="${DEPLOY_STATUS[$shortname]:-N/A}"
        local auth="${AUTH_STATUS[$shortname]:-N/A}"

        printf '%-16s %-8s %-12s %-12s %-12s %-12s %-14s\n' \
            "${shortname}" \
            "${port}" \
            "${network}" \
            "${key}" \
            "${config}" \
            "${deploy}" \
            "${auth}"

        if [[ "${network}" == "DOWN" ||
              "${deploy}" == "FAILED" ||
              "${auth}" == "FAILED" ]]
        then
            failures=$((failures + 1))
        fi
    done

    if (( ROTATE )); then
        printf '\n'
        printf '%-16s %-20s\n' "HOST" "ROTATION"
        printf '%-16s %-20s\n' "----------------" "--------------------"

        for entry in "${HOSTS[@]}"; do
            IFS='|' read -r fqdn shortname ip port <<<"${entry}"

            host_selected "${shortname}" || continue

            printf '%-16s %-20s\n' \
                "${shortname}" \
                "${ROTATION_STATUS[$shortname]:-N/A}"
        done
    fi

    printf '\n'

    if (( failures == 0 )); then
        ok "Omega SSH bootstrap completed successfully."

        printf '\n'
        printf '%s\n' "SSH aliases:"
        printf '%s\n' "  ssh core"
        printf '%s\n' "  ssh ha-node-a"
        printf '%s\n' "  ssh ha-node-b"

        return 0
    fi

    error "${failures} host(s) reported failures."

    return 1
}

# ==============================================================================
# Preflight
# ==============================================================================

section "OMEGA SSH BOOTSTRAP"

printf 'Started: %s\n' "$(timestamp)"
printf 'User:    %s\n' "${REMOTE_USER}"
printf 'SSH dir: %s\n' "${SSH_DIR}"

require_command ssh
require_command ssh-keygen
require_command awk
require_command grep
require_command chmod
require_command mktemp
require_command date
require_command cp
require_command mv

[[ -n "${HOME:-}" ]] ||
    die "HOME environment variable is not set"

[[ "${HOME}" != "/" ]] ||
    die "Refusing to operate with HOME=/"

validate_inventory
validate_selected_hosts

prepare_ssh_directory

# ==============================================================================
# Phase 1: Network discovery
# ==============================================================================

section "[1/6] NETWORK DISCOVERY"

for ENTRY in "${HOSTS[@]}"; do
    IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

    host_selected "${SHORTNAME}" || continue

    check_reachability \
        "${SHORTNAME}" \
        "${IP}" \
        "${PORT}" || true
done

# ==============================================================================
# Phase 2: known_hosts
# ==============================================================================

section "[2/6] HOST KEY MANAGEMENT"

if (( SCAN_KNOWN_HOSTS )); then
    warn "ssh-keyscan discovers host keys but does not authenticate them."
    warn "Verify fingerprints independently before trusting new hosts."

    for ENTRY in "${HOSTS[@]}"; do
        IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

        host_selected "${SHORTNAME}" || continue

        [[ "${REACHABILITY_STATUS[$SHORTNAME]:-DOWN}" == "UP" ]] ||
            continue

        scan_known_host \
            "${FQDN}" \
            "${SHORTNAME}" \
            "${IP}" \
            "${PORT}" || true
    done
else
    info "known_hosts scan not requested"
fi

# ==============================================================================
# Phase 3: Keys
# ==============================================================================

section "[3/6] SSH KEY MANAGEMENT"

if (( ROTATE )); then
    info "Rotation mode enabled."
    info "Existing keys remain active until replacements are verified."
else
    for ENTRY in "${HOSTS[@]}"; do
        IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

        host_selected "${SHORTNAME}" || continue

        generate_key \
            "${FQDN}" \
            "${SHORTNAME}"
    done
fi

# ==============================================================================
# Phase 4: SSH config
# ==============================================================================

section "[4/6] SSH CLIENT CONFIGURATION"

backup_config

for ENTRY in "${HOSTS[@]}"; do
    IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

    host_selected "${SHORTNAME}" || continue

    write_host_config \
        "${FQDN}" \
        "${SHORTNAME}" \
        "${IP}" \
        "${PORT}"
done

if (( ! DRY_RUN )); then
    validate_ssh_config
else
    info "Dry-run: SSH config validation skipped because no changes were written."
fi

# ==============================================================================
# Phase 5: Deployment / rotation
# ==============================================================================

section "[5/6] KEY DEPLOYMENT"

for ENTRY in "${HOSTS[@]}"; do
    IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

    host_selected "${SHORTNAME}" || continue

    if [[ "${REACHABILITY_STATUS[$SHORTNAME]:-DOWN}" != "UP" ]]; then
        warn "${SHORTNAME}: skipping deployment because SSH port is unreachable"

        DEPLOY_STATUS["${SHORTNAME}"]="SKIPPED"
        AUTH_STATUS["${SHORTNAME}"]="SKIPPED"

        continue
    fi

    printf '\n'
    printf '%s\n' "----------------------------------------------------------------------"
    printf ' Host: %s\n' "${SHORTNAME}"
    printf ' FQDN: %s\n' "${FQDN}"
    printf ' IP:   %s\n' "${IP}"
    printf ' Port: %s\n' "${PORT}"
    printf '%s\n' "----------------------------------------------------------------------"

    if (( ROTATE )); then
        rotate_host_key \
            "${FQDN}" \
            "${SHORTNAME}" \
            "${IP}" \
            "${PORT}" || true

        if [[ "${ROTATION_STATUS[$SHORTNAME]:-}" == "SUCCESS" ]]; then
            DEPLOY_STATUS["${SHORTNAME}"]="SUCCESS"
        fi

        continue
    fi

    deploy_key \
        "${SHORTNAME}" \
        "${IP}" \
        "${PORT}" || true
done

# ==============================================================================
# Phase 6: Authentication verification
# ==============================================================================

section "[6/6] PASSWORDLESS AUTHENTICATION VERIFICATION"

if (( ROTATE )); then
    info "Rotation workflow already performed replacement-key verification."

elif (( PARALLEL <= 1 )); then

    for ENTRY in "${HOSTS[@]}"; do
        IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

        host_selected "${SHORTNAME}" || continue

        if [[ "${DEPLOY_STATUS[$SHORTNAME]:-}" == "FAILED" ]]; then
            AUTH_STATUS["${SHORTNAME}"]="SKIPPED"
            continue
        fi

        verify_alias "${SHORTNAME}" || true
    done

else

    info "Running authentication verification with up to ${PARALLEL} workers"

    # --------------------------------------------------------------------------
    # Parallel verification
    #
    # Authentication tests are already BatchMode=yes and therefore will never
    # prompt for passwords.
    # --------------------------------------------------------------------------

    running=0

    declare -a PIDS=()
    declare -A PID_HOST=()

    for ENTRY in "${HOSTS[@]}"; do
        IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

        host_selected "${SHORTNAME}" || continue

        if [[ "${DEPLOY_STATUS[$SHORTNAME]:-}" == "FAILED" ]]; then
            AUTH_STATUS["${SHORTNAME}"]="SKIPPED"
            continue
        fi

        status_file="${SSH_DIR}/.omega-auth-${SHORTNAME}.$$"

        (
            if ssh \
                -o BatchMode=yes \
                -o PasswordAuthentication=no \
                -o KbdInteractiveAuthentication=no \
                -o PreferredAuthentications=publickey \
                -o ConnectTimeout="${CONNECT_TIMEOUT}" \
                "${SHORTNAME}" \
                true \
                >/dev/null 2>&1
            then
                printf '%s\n' "SUCCESS" >"${status_file}"
            else
                printf '%s\n' "FAILED" >"${status_file}"
            fi
        ) &

        pid=$!

        PIDS+=("${pid}")
        PID_HOST["${pid}"]="${SHORTNAME}"

        running=$((running + 1))

        if (( running >= PARALLEL )); then
            first_pid="${PIDS[0]}"

            wait "${first_pid}" || true

            running=$((running - 1))

            PIDS=("${PIDS[@]:1}")
        fi
    done

    for pid in "${PIDS[@]}"; do
        wait "${pid}" || true
    done

    for ENTRY in "${HOSTS[@]}"; do
        IFS='|' read -r FQDN SHORTNAME IP PORT <<<"${ENTRY}"

        host_selected "${SHORTNAME}" || continue

        status_file="${SSH_DIR}/.omega-auth-${SHORTNAME}.$$"

        if [[ -f "${status_file}" ]]; then
            AUTH_STATUS["${SHORTNAME}"]="$(cat "${status_file}")"

            rm -f "${status_file}"
        fi
    done
fi

# ==============================================================================
# Final summary
# ==============================================================================

if print_summary; then
    exit 0
fi

exit 1
