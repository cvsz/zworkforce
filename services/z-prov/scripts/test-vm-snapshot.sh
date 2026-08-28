#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Exercises I1 against a user-provided clean VMware snapshot. It is intentionally
# remote and opt-in: no SSH connection or host mutation occurs in dry-run mode.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="--dry-run"
HOST=""
INSTALL_USER=""
UPDATE_MANIFEST_URL="${ZEAZ_UPDATE_MANIFEST_URL:-}"
UPDATE_SIGNATURE_URL="${ZEAZ_UPDATE_SIGNATURE_URL:-}"
UPDATE_PUBLIC_KEY="${ZEAZ_UPDATE_PUBLIC_KEY:-}"
IDENTITY_FILE="${ZEAZ_VM_IDENTITY_FILE:-}"
SUDO_MODE="noninteractive"
KEEP_REMOTE_WORKDIR=false

log() { printf '%s level=%s msg=%q\n' "$(date --iso-8601=seconds)" "$1" "$2"; }
die() { log error "$1"; exit 1; }
on_error() {
  local status="$?"
  trap - ERR
  log error "snapshot deployment failed exit_code=$status"
  exit "$status"
}

usage() {
  cat <<'EOF'
Usage: bash scripts/test-vm-snapshot.sh [--dry-run|--apply] --host USER@HOST --install-user USER [options]

Runs the I1 clean-install, reboot, and optional signed-upgrade acceptance test
on a manually created, fresh Ubuntu 26.04 VMware snapshot. --apply transfers
only release source and artifacts; it excludes local configuration and secrets.

Options:
  --host USER@HOST                SSH target for the clean VMware snapshot
  --install-user USER             Unprivileged remote account for ZeaZ Provider
  --update-manifest-url URL       HTTPS signed update manifest, to exercise upgrade
  --update-signature-url URL      Optional detached-signature URL
  --update-public-key PATH        Local absolute public-key path for the upgrade
  --identity-file PATH            Local absolute SSH private key for the VM
  --sudo-mode MODE                noninteractive (default) or interactive
  --keep-remote-workdir           Preserve the secret-excluded transfer on apply failure
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dry-run|--apply) ACTION="$1" ;;
    --host) shift; HOST="${1:-}" ;;
    --install-user) shift; INSTALL_USER="${1:-}" ;;
    --update-manifest-url) shift; UPDATE_MANIFEST_URL="${1:-}" ;;
    --update-signature-url) shift; UPDATE_SIGNATURE_URL="${1:-}" ;;
    --update-public-key) shift; UPDATE_PUBLIC_KEY="${1:-}" ;;
    --identity-file) shift; IDENTITY_FILE="${1:-}" ;;
    --sudo-mode) shift; SUDO_MODE="${1:-}" ;;
    --keep-remote-workdir) KEEP_REMOTE_WORKDIR=true ;;
    --help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

[[ -n "$HOST" ]] || die "--host is required"
[[ "$HOST" != *$'\n'* && "$HOST" != *' '* ]] || die "--host must not contain whitespace"
[[ "$HOST" != -* ]] || die "--host must not start with a dash"
[[ "$INSTALL_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "--install-user is invalid"
[[ "$SUDO_MODE" =~ ^(noninteractive|interactive)$ ]] || die "--sudo-mode must be noninteractive or interactive"
if [[ -n "$IDENTITY_FILE" ]]; then
  [[ "$IDENTITY_FILE" == /* && -f "$IDENTITY_FILE" && -r "$IDENTITY_FILE" ]] ||
    die "--identity-file must be an absolute readable file"
fi
if [[ -n "$UPDATE_MANIFEST_URL$UPDATE_SIGNATURE_URL$UPDATE_PUBLIC_KEY" ]]; then
  [[ "$UPDATE_MANIFEST_URL" == https://* ]] || die "--update-manifest-url must use HTTPS"
  [[ "$UPDATE_MANIFEST_URL" != *"'"* ]] || die "--update-manifest-url contains an unsafe character"
  [[ "$UPDATE_PUBLIC_KEY" == /* && -r "$UPDATE_PUBLIC_KEY" ]] ||
    die "--update-public-key must be absolute and readable"
  [[ -z "$UPDATE_SIGNATURE_URL" || "$UPDATE_SIGNATURE_URL" == https://* ]] ||
    die "--update-signature-url must use HTTPS"
  [[ "$UPDATE_SIGNATURE_URL" != *"'"* ]] || die "--update-signature-url contains an unsafe character"
fi
if [[ "$ACTION" == "--apply" && -z "$UPDATE_MANIFEST_URL" ]]; then
  die "--apply requires a signed update manifest and public key"
fi

if [[ "$ACTION" == "--dry-run" ]]; then
  log info "would verify fresh Ubuntu 26.04 VMware host over SSH at $HOST"
  log info "would transfer source while excluding .env, config, virtual environments, and Git metadata"
  log info "would apply bootstrap, run doctor, reboot, and verify services and firewall persistence"
  [[ -n "$UPDATE_MANIFEST_URL" ]] && log info "would apply and verify signed release upgrade"
  $KEEP_REMOTE_WORKDIR && log info "would retain the secret-excluded remote work directory on apply failure"
  exit 0
fi

command -v ssh >/dev/null || die "ssh is required"
command -v tar >/dev/null || die "tar is required"
command -v scp >/dev/null || die "scp is required for update public key transfer"
command -v base64 >/dev/null || die "base64 is required"
ssh_options=(-o ConnectTimeout=15 -o ConnectionAttempts=3 -o ServerAliveInterval=15 -o ServerAliveCountMax=3)
scp_options=(-o BatchMode=yes -o ConnectTimeout=15 -o ConnectionAttempts=3)
if [[ "$SUDO_MODE" == "interactive" ]]; then
  ssh_options+=(-o BatchMode=no)
else
  ssh_options+=(-o BatchMode=yes)
fi
if [[ -n "$IDENTITY_FILE" ]]; then
  ssh_options+=(-i "$IDENTITY_FILE" -o IdentitiesOnly=yes)
  scp_options+=(-i "$IDENTITY_FILE" -o IdentitiesOnly=yes)
fi
sudo_ssh_options=("${ssh_options[@]}")
[[ "$SUDO_MODE" != "interactive" ]] || sudo_ssh_options+=(-tt)
# Remote command strings interpolate only values validated above or returned by mktemp.
# shellcheck disable=SC2029
remote() { ssh "${ssh_options[@]}" "$HOST" "$@"; }
# shellcheck disable=SC2029
remote_sudo_transport() { ssh "${sudo_ssh_options[@]}" "$HOST" "$@"; }
remote_probe() { ssh "${ssh_options[@]}" -o ConnectTimeout=5 "$HOST" true; }
remote_sudo_as() {
  local user="$1"
  local command="$2"
  local encoded
  encoded="$(printf '%s' "$command" | base64 | tr -d '\n')"
  if [[ "$SUDO_MODE" == "interactive" ]]; then
    remote_sudo_transport "printf %s '$encoded' | base64 -d | sudo -u '$user' /bin/bash"
  else
    remote_sudo_transport "printf %s '$encoded' | base64 -d | sudo -n -u '$user' /bin/bash"
  fi
}
remote_sudo() { remote_sudo_as root "$1"; }
trap on_error ERR

log info "verifying SSH connectivity"
remote true
log info "SSH connectivity verified"
remote_dir="$(remote 'mktemp -d /tmp/zeaz-provider-i1.XXXXXX')"
[[ "$remote_dir" == /tmp/zeaz-provider-i1.* ]] || die "remote temporary directory was unsafe"
cleanup() { remote "rm -rf -- '$remote_dir'" >/dev/null 2>&1 || true; }
if $KEEP_REMOTE_WORKDIR; then
  cleanup() { log warning "retained remote work directory $remote_dir for inspection"; }
fi
trap cleanup EXIT
if [[ "$SUDO_MODE" == "interactive" ]]; then
  remote_sudo_transport 'sudo -v' || die "remote sudo authentication was rejected"
else
  remote 'sudo -n true' || die "remote user requires passwordless sudo for snapshot acceptance"
fi

tar -C "$ROOT" \
  --exclude=.env --exclude=.venv --exclude=.git --exclude=config/providers.yaml \
  --exclude='__pycache__' --exclude='.pytest_cache' -cf - . |
remote "tar -C '$remote_dir' -xf -"
remote "chmod -R a+rX '$remote_dir'"
scp -q "${scp_options[@]}" "$UPDATE_PUBLIC_KEY" "$HOST:$remote_dir/release-public-key.pem"
remote_sudo "install -d -m 755 /etc/zeaz && install -m 644 '$remote_dir/release-public-key.pem' /etc/zeaz/release-public-key.pem"

bootstrap_update_args="--update-manifest-url '$UPDATE_MANIFEST_URL' --update-public-key /etc/zeaz/release-public-key.pem"
if [[ -n "$UPDATE_SIGNATURE_URL" ]]; then
  bootstrap_update_args+=" --update-signature-url '$UPDATE_SIGNATURE_URL'"
fi

remote_sudo "cd '$remote_dir' && bash scripts/bootstrap-host.sh --apply --install-user '$INSTALL_USER' $bootstrap_update_args"
remote_sudo_as "$INSTALL_USER" "bash '$remote_dir/scripts/doctor.sh'"
remote_sudo "systemctl is-active docker.service && ufw status"
remote_sudo 'systemctl reboot' || true

reboot_started=false
for ((attempt = 1; attempt <= 30; attempt++)); do
  if ! remote_probe >/dev/null 2>&1; then
    reboot_started=true
    break
  fi
  sleep 1
done
$reboot_started || die "remote host did not disconnect after reboot request"

# A reboot drops the first connection. Retry with bounded exponential backoff.
sleep_time=1
reboot_complete=false
for ((attempt = 1; attempt <= 30; attempt++)); do
  if remote_probe >/dev/null 2>&1; then
    reboot_complete=true
    break
  fi
  sleep "$sleep_time"
  (( sleep_time < 8 )) && sleep_time=$((sleep_time * 2))
done
if [[ "$reboot_complete" != true ]]; then
  die "remote host did not reconnect after reboot"
fi
remote_sudo_as "$INSTALL_USER" "bash '$remote_dir/scripts/doctor.sh'"
remote_sudo "systemctl is-active docker.service && ufw status"
remote_sudo "if ufw status | grep -Eq '(8080|8000|3000)/tcp'; then exit 1; fi"

remote_sudo_as "$INSTALL_USER" "env CONFIRM_UPDATE=yes \\
  ZEAZ_UPDATE_MANIFEST_URL='$UPDATE_MANIFEST_URL' \\
  ZEAZ_UPDATE_SIGNATURE_URL='$UPDATE_SIGNATURE_URL' \\
  ZEAZ_UPDATE_PUBLIC_KEY=/etc/zeaz/release-public-key.pem \\
  bash '$remote_dir/scripts/update.sh' --apply"
remote_sudo_as "$INSTALL_USER" "bash '$remote_dir/scripts/doctor.sh'"

log info "I1 VMware snapshot acceptance test passed"
