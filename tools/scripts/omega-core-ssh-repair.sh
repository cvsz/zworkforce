#!/usr/bin/env bash
set -Eeuo pipefail

REMOTE_USER="cvsz"
CORE_IP="192.168.74.130"
CORE_PORT="22"
SSH_DIR="${HOME}/.ssh"
CORE_KEY="${SSH_DIR}/id_ed25519_core"
CORE_PUB="${CORE_KEY}.pub"
RELAYS=("ha-node-a" "ha-node-b")

log(){ printf '%s\n' "$*"; }
info(){ printf '[*] %s\n' "$*"; }
ok(){ printf '[+] %s\n' "$*"; }
warn(){ printf '[!] %s\n' "$*" >&2; }

test_direct_core() {
  ssh -F /dev/null \
    -i "$CORE_KEY" \
    -p "$CORE_PORT" \
    -o IdentityAgent=none \
    -o IdentitiesOnly=yes \
    -o BatchMode=yes \
    -o PasswordAuthentication=no \
    -o KbdInteractiveAuthentication=no \
    -o PreferredAuthentications=publickey \
    -o ConnectionAttempts=1 \
    -o ConnectTimeout=5 \
    -o StrictHostKeyChecking=accept-new \
    "${REMOTE_USER}@${CORE_IP}" true >/dev/null 2>&1
}

test_relay() {
  local relay="$1"
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$relay" \
    "ssh -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new ${REMOTE_USER}@${CORE_IP} true" \
    >/dev/null 2>&1
}

repair_via_relay() {
  local relay="$1"
  local pub
  pub="$(cat "$CORE_PUB")"

  {
    printf '%s\n' "$pub"
    cat <<'EOS'
set -eu
USER_NAME="cvsz"
IFS= read -r PUB_KEY

if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  sudo -n apt-get update
  sudo -n apt-get install -y openssh-server
elif command -v dnf >/dev/null 2>&1; then
  sudo -n dnf install -y openssh-server
elif command -v yum >/dev/null 2>&1; then
  sudo -n yum install -y openssh-server
else
  echo "Unsupported package manager" >&2
  exit 70
fi

HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
[ -n "$HOME_DIR" ] || exit 71

sudo -n install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "$HOME_DIR/.ssh"
sudo -n touch "$HOME_DIR/.ssh/authorized_keys"
sudo -n chown "$USER_NAME:$USER_NAME" "$HOME_DIR/.ssh/authorized_keys"
sudo -n chmod 600 "$HOME_DIR/.ssh/authorized_keys"

if ! sudo -n -u "$USER_NAME" grep -qxF "$PUB_KEY" "$HOME_DIR/.ssh/authorized_keys"; then
  printf "%s\n" "$PUB_KEY" | sudo -n tee -a "$HOME_DIR/.ssh/authorized_keys" >/dev/null
fi

if [ -d /etc/ssh/sshd_config.d ]; then
  printf '%s\n' \
    'PubkeyAuthentication yes' \
    'AuthorizedKeysFile .ssh/authorized_keys' \
    | sudo -n tee /etc/ssh/sshd_config.d/90-omega-core-repair.conf >/dev/null
fi

sudo -n sshd -t
if command -v systemctl >/dev/null 2>&1; then
  if systemctl list-unit-files | grep -q '^ssh\.service'; then
    sudo -n systemctl enable --now ssh
    sudo -n systemctl restart ssh
  else
    sudo -n systemctl enable --now sshd
    sudo -n systemctl restart sshd
  fi
else
  sudo -n service ssh restart || sudo -n service sshd restart
fi
sudo -n sshd -t
EOS
  } | ssh "$relay" "ssh -o StrictHostKeyChecking=accept-new ${REMOTE_USER}@${CORE_IP} 'bash -s'"
}

main() {
  [[ -f "$CORE_KEY" && -f "$CORE_PUB" ]] || {
    warn "Missing $CORE_KEY or $CORE_PUB"
    exit 2
  }

  if test_direct_core; then
    ok "core dedicated key already works"
    exit 0
  fi

  local relay
  for relay in "${RELAYS[@]}"; do
    info "Testing relay $relay -> core"
    if test_relay "$relay"; then
      ok "$relay can authenticate to core"
      repair_via_relay "$relay"
      sleep 2
      if test_direct_core; then
        ok "core SSH repaired and dedicated key verified"
        exit 0
      fi
    fi
  done

  warn "No authenticated relay path to core."
  warn "Use the core VM console to reinstall openssh-server and add:"
  cat "$CORE_PUB"
  exit 1
}

main "$@"
