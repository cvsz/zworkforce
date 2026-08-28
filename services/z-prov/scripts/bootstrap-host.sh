#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Prepares an Ubuntu host before the unprivileged application install. This script
# is deliberately dry-run first because it changes package sources and firewall policy.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="--dry-run"
HOST_ROOT="/"
MODE="auto"
INSTALL_USER=""
OS_RELEASE="/etc/os-release"
SSH_PORT="22"
UPDATE_MANIFEST_URL="${ZEAZ_UPDATE_MANIFEST_URL:-}"
UPDATE_SIGNATURE_URL="${ZEAZ_UPDATE_SIGNATURE_URL:-}"
UPDATE_PUBLIC_KEY="${ZEAZ_UPDATE_PUBLIC_KEY:-}"

log() { printf '%s level=%s msg=%q\n' "$(date --iso-8601=seconds)" "$1" "$2"; }
die() { log error "$1"; exit 1; }
host_path() { [[ "$HOST_ROOT" == "/" ]] && printf '%s\n' "$1" || printf '%s%s\n' "$HOST_ROOT" "$1"; }

usage() {
  cat <<'EOF'
Usage: sudo bash scripts/bootstrap-host.sh [--dry-run|--apply] [options]

Prepare Ubuntu 26.04 for ZeaZ Provider. Dry-run is the default; --apply must
run as root and requires --install-user USER so the gateway remains unprivileged.

Options:
  --mode auto|nvidia|amd|cpu-only  Override read-only GPU detection (default: auto)
  --install-user USER              Non-root account that receives the gateway service
  --ssh-port PORT                  Preserve this TCP SSH port in UFW (default: 22)
  --update-manifest-url URL        Enable verified auto-updates from this HTTPS manifest
  --update-signature-url URL       Optional HTTPS detached-signature URL
  --update-public-key PATH         Absolute Ed25519 public-key path for auto-updates
  --os-release PATH                os-release path, for deterministic validation tests
  --root PATH                      Alternate filesystem root, intended only for tests
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dry-run|--apply) ACTION="$1" ;;
    --mode) shift; MODE="${1:-}" ;;
    --install-user) shift; INSTALL_USER="${1:-}" ;;
    --ssh-port) shift; SSH_PORT="${1:-}" ;;
    --update-manifest-url) shift; UPDATE_MANIFEST_URL="${1:-}" ;;
    --update-signature-url) shift; UPDATE_SIGNATURE_URL="${1:-}" ;;
    --update-public-key) shift; UPDATE_PUBLIC_KEY="${1:-}" ;;
    --os-release) shift; OS_RELEASE="${1:-}" ;;
    --root) shift; HOST_ROOT="${1:-}" ;;
    --help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

[[ "$HOST_ROOT" == /* ]] || die "--root must be absolute"
[[ "$OS_RELEASE" == /* ]] || die "--os-release must be absolute"
[[ "$MODE" =~ ^(auto|nvidia|amd|cpu-only)$ ]] || die "--mode must be auto, nvidia, amd, or cpu-only"
if ! [[ "$SSH_PORT" =~ ^[1-9][0-9]{0,4}$ ]] || (( SSH_PORT > 65535 )); then
  die "--ssh-port must be 1-65535"
fi
if [[ -n "$UPDATE_MANIFEST_URL$UPDATE_SIGNATURE_URL$UPDATE_PUBLIC_KEY" ]]; then
  [[ "$UPDATE_MANIFEST_URL" == https://* ]] || die "--update-manifest-url must use HTTPS"
  [[ -n "$UPDATE_PUBLIC_KEY" ]] || die "--update-public-key is required with auto-updates"
  [[ "$UPDATE_PUBLIC_KEY" == /* && -r "$UPDATE_PUBLIC_KEY" ]] || die "update public key must be absolute and readable"
  [[ -z "$UPDATE_SIGNATURE_URL" || "$UPDATE_SIGNATURE_URL" == https://* ]] ||
    die "--update-signature-url must use HTTPS"
fi

if [[ "$MODE" == "auto" ]]; then
  if [[ -r "$(host_path /proc/driver/nvidia/version)" ]] && command -v nvidia-smi >/dev/null; then
    MODE="nvidia"
  else
    MODE="cpu-only"
    for vendor_file in "$(host_path /sys/class/drm)"/card*/device/vendor; do
      [[ -r "$vendor_file" ]] || continue
      if grep -qx '0x1002' "$vendor_file"; then
        MODE="amd"
        break
      fi
    done
  fi
fi

[[ -r "$OS_RELEASE" ]] || die "os-release is unreadable: $OS_RELEASE"
# shellcheck disable=SC1090
source "$OS_RELEASE"
[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "26.04" ]] || die "Ubuntu 26.04 is required"
[[ -n "${VERSION_CODENAME:-}" ]] || die "Ubuntu version codename is required"

log info "action=$ACTION mode=$MODE root=$HOST_ROOT install_user=${INSTALL_USER:-none}"
if [[ "$ACTION" == "--dry-run" ]]; then
  log info "would install Docker Engine from Docker's official APT repository"
  log info "would remove distribution Docker packages that conflict with Docker Engine"
  [[ "$MODE" == "nvidia" ]] && log info "would install NVIDIA Container Toolkit from NVIDIA's official APT repository"
  [[ -r "$(host_path /sys/class/dmi/id/sys_vendor)" ]] && grep -qi 'vmware' "$(host_path /sys/class/dmi/id/sys_vendor)" && log info "would install open-vm-tools and retain host time synchronization"
  log info "would write persistent sysctl, nofile, Docker, and UFW policy with gateway ports closed"
  [[ -n "$INSTALL_USER" ]] && log info "would install and enable user services for $INSTALL_USER"
  [[ -n "$UPDATE_MANIFEST_URL" ]] && log info "would install verified auto-update timer"
  exit 0
fi

test_root_allowed=false
if [[ "$HOST_ROOT" != "/" && "${ZEAZ_BOOTSTRAP_TEST_ROOT:-}" == "1" ]]; then
  test_root_allowed=true
fi
if [[ "$EUID" -ne 0 && "$test_root_allowed" != true ]]; then
  die "--apply must run as root"
fi
[[ -n "$INSTALL_USER" ]] || die "--apply requires --install-user USER"
if [[ "$HOST_ROOT" != "/" && "${ZEAZ_BOOTSTRAP_TEST_ROOT:-}" != "1" ]]; then
  die "--root is limited to dry-run outside the bootstrap test harness"
fi
id "$INSTALL_USER" >/dev/null 2>&1 || die "install user does not exist: $INSTALL_USER"
command -v apt-get >/dev/null || die "apt-get is required"

install -d -m 755 "$(host_path /etc/apt/keyrings)" "$(host_path /etc/apt/sources.list.d)"
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg python3-venv
command -v curl >/dev/null || die "curl installation failed"
command -v gpg >/dev/null || die "gnupg installation failed"
# A failed earlier package transaction can leave Docker components unpacked but
# unconfigured. Continue recovery after removing the conflicting distro stack.
if ! dpkg --configure -a; then
  log warning "continuing Docker conflict recovery after incomplete dpkg configuration"
fi
apt-get remove -y docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc
apt-get -f install -y
curl --fail --silent --show-error --location https://download.docker.com/linux/ubuntu/gpg |
  gpg --dearmor --yes --output "$(host_path /etc/apt/keyrings/docker.gpg)"
chmod 644 "$(host_path /etc/apt/keyrings/docker.gpg)"
printf '%s\n' \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  >"$(host_path /etc/apt/sources.list.d/docker.list)"

apt-get update
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin ufw

if [[ "$MODE" == "nvidia" ]]; then
  command -v nvidia-smi >/dev/null || die "NVIDIA mode requires a working nvidia-smi driver"
  curl --fail --silent --show-error --location https://nvidia.github.io/libnvidia-container/gpgkey |
    gpg --dearmor --yes --output "$(host_path /etc/apt/keyrings/nvidia-container-toolkit.gpg)"
  chmod 644 "$(host_path /etc/apt/keyrings/nvidia-container-toolkit.gpg)"
  curl --fail --silent --show-error --location \
    https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#^deb https://#deb [signed-by=/etc/apt/keyrings/nvidia-container-toolkit.gpg] https://#' \
      >"$(host_path /etc/apt/sources.list.d/nvidia-container-toolkit.list)"
  apt-get update
  apt-get install -y --no-install-recommends nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
fi

if [[ -r "$(host_path /sys/class/dmi/id/sys_vendor)" ]] && grep -qi 'vmware' "$(host_path /sys/class/dmi/id/sys_vendor)"; then
  apt-get install -y --no-install-recommends open-vm-tools
  systemctl enable --now open-vm-tools.service 2>/dev/null || true
fi

install -d -m 755 "$(host_path /etc/sysctl.d)" "$(host_path /etc/security/limits.d)" "$(host_path /etc/docker)"
cat >"$(host_path /etc/sysctl.d/99-zeaz-provider.conf)" <<'EOF'
# Conservative gateway host defaults. Applied at boot by systemd-sysctl.
fs.file-max = 2097152
net.core.somaxconn = 1024
vm.max_map_count = 262144
vm.swappiness = 10
EOF
cat >"$(host_path /etc/security/limits.d/99-zeaz-provider.conf)" <<'EOF'
# Permit the unprivileged gateway service to sustain bounded concurrent requests.
* soft nofile 65536
* hard nofile 65536
EOF
cat >"$(host_path /etc/docker/daemon.json)" <<'EOF'
{"live-restore":true,"log-driver":"local","log-opts":{"max-size":"10m","max-file":"3"}}
EOF
sysctl --system
systemctl enable --now docker.service

# Gateway ports are intentionally never opened here. SSH is retained to avoid
# locking an administrator out while applying the default-deny firewall policy.
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp" comment 'ZeaZ administration SSH'
ufw --force enable

user_home="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
[[ -n "$user_home" && "$user_home" == /* ]] || die "could not resolve home for $INSTALL_USER"
user_uid="$(id -u "$INSTALL_USER")"
loginctl enable-linger "$INSTALL_USER"
systemctl start "user@${user_uid}.service"
runtime_dir="/run/user/$user_uid"
if [[ "${ZEAZ_BOOTSTRAP_TEST_ROOT:-}" != "1" ]]; then
  for ((attempt = 1; attempt <= 10; attempt++)); do
    [[ -S "$runtime_dir/bus" ]] && break
    sleep 1
  done
  [[ -S "$runtime_dir/bus" ]] || die "user systemd bus did not start for $INSTALL_USER"
fi
user_service_env=(
  HOME="$user_home"
  XDG_CONFIG_HOME="$user_home/.config"
  XDG_RUNTIME_DIR="$runtime_dir"
  DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime_dir/bus"
)
runuser -u "$INSTALL_USER" -- env "${user_service_env[@]}" \
  bash "$ROOT/scripts/install.sh" --apply --systemd-user
if [[ -n "$UPDATE_MANIFEST_URL" ]]; then
  runuser -u "$INSTALL_USER" -- env "${user_service_env[@]}" \
    CONFIRM_AUTO_UPDATE=yes ZEAZ_UPDATE_MANIFEST_URL="$UPDATE_MANIFEST_URL" \
    ZEAZ_UPDATE_SIGNATURE_URL="$UPDATE_SIGNATURE_URL" ZEAZ_UPDATE_PUBLIC_KEY="$UPDATE_PUBLIC_KEY" \
    bash "$ROOT/scripts/install-auto-update.sh" --apply
else
  log warning "verified auto-update timer not installed; provide release manifest and public key to enable it"
fi

log info "host bootstrap complete; gateway ports remain closed by UFW"
