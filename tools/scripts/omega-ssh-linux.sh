#!/usr/bin/env bash
# Omega SSH Bundle v5 - self-deploy transport-key fallback
set -Eeuo pipefail
REMOTE_USER="cvsz"
SSH_DIR="${HOME}/.ssh"
SSH_CONFIG="${SSH_DIR}/config"
BACKUP_DIR="${SSH_DIR}/omega/backups"
CONNECT_TIMEOUT=5
HOSTS=(
  "core.zeaz.dev|core|192.168.74.130|22"
  "ha-a.zeaz.dev|ha-node-a|192.168.74.134|22"
  "ha-b.zeaz.dev|ha-node-b|192.168.74.135|22"
)
TUNNELS=(
  "core-postgres|core|15432|127.0.0.1|5432"
  "core-redis|core|16379|127.0.0.1|6379"
  "core-http|core|18080|127.0.0.1|80"
  "core-https|core|18443|127.0.0.1|443"
  "ha-a-http|ha-node-a|18081|127.0.0.1|80"
  "ha-a-https|ha-node-a|18441|127.0.0.1|443"
  "ha-b-http|ha-node-b|18082|127.0.0.1|80"
  "ha-b-https|ha-node-b|18442|127.0.0.1|443"
)
DRY_RUN=0; START_TUNNELS=0; STOP_TUNNELS=0; STATUS=0; SOCKS=0; SOCKS_PORT=1080
while (($#)); do case "$1" in --dry-run) DRY_RUN=1;; --start-tunnels) START_TUNNELS=1;; --stop-tunnels) STOP_TUNNELS=1;; --status) STATUS=1;; --start-socks) SOCKS=1;; --socks-port) shift; SOCKS_PORT="$1";; -h|--help) echo "Usage: $0 [--dry-run|--start-tunnels|--stop-tunnels|--status|--start-socks]"; exit 0;; *) echo "Unknown arg: $1" >&2; exit 2;; esac; shift; done
log(){ printf '%s\n' "$*"; }; ok(){ printf '[+] %s\n' "$*"; }; warn(){ printf '[!] %s\n' "$*" >&2; }
mkdir -p "$SSH_DIR" "$BACKUP_DIR"; chmod 700 "$SSH_DIR" "$BACKUP_DIR"; touch "$SSH_CONFIG"; chmod 600 "$SSH_CONFIG"
key_path(){ printf '%s/id_ed25519_%s' "$SSH_DIR" "$1"; }
ensure_key(){ local fqdn="$1" alias="$2" key; key="$(key_path "$alias")"; if [[ -f "$key" ]]; then ssh-keygen -y -f "$key" >/dev/null || return 1; [[ -f "$key.pub" ]] || ssh-keygen -y -f "$key" > "$key.pub"; ok "$alias key verified"; else ssh-keygen -t ed25519 -C "$REMOTE_USER@$fqdn" -f "$key" -N '' -q; ok "$alias key generated"; fi; chmod 600 "$key"; chmod 644 "$key.pub"; }
write_config(){ local fqdn="$1" alias="$2" ip="$3" port="$4" key tmp; key="$(key_path "$alias")"; tmp="$(mktemp)"; awk -v b="# >>> OMEGA_SSH_${alias} >>>" -v e="# <<< OMEGA_SSH_${alias} <<<" '$0==b{skip=1;next} skip&&$0==e{skip=0;next} !skip{print}' "$SSH_CONFIG" > "$tmp"; mv "$tmp" "$SSH_CONFIG"; cat >> "$SSH_CONFIG" <<EOF
# >>> OMEGA_SSH_${alias} >>>
Host ${alias} ${fqdn}
    HostName ${ip}
    Port ${port}
    User ${REMOTE_USER}
    IdentityFile ${key}
    IdentitiesOnly yes
    PubkeyAuthentication yes
    ConnectTimeout ${CONNECT_TIMEOUT}
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ForwardAgent no
# <<< OMEGA_SSH_${alias} <<<
EOF
chmod 600 "$SSH_CONFIG"; }
key_works(){ local alias="$1" ip="$2" port="$3" key; key="$(key_path "$alias")"; timeout 8 ssh -F /dev/null -i "$key" -p "$port" -o IdentitiesOnly=yes -o IdentityAgent=none -o BatchMode=yes -o NumberOfPasswordPrompts=0 -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o PreferredAuthentications=publickey -o ConnectionAttempts=1 -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new "$REMOTE_USER@$ip" true >/dev/null 2>&1; }
transport_key_works(){ local key="$1" ip="$2" port="$3"; timeout 8 ssh -F /dev/null -i "$key" -p "$port" -o IdentitiesOnly=yes -o IdentityAgent=none -o BatchMode=yes -o NumberOfPasswordPrompts=0 -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o PreferredAuthentications=publickey -o ConnectionAttempts=1 -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new "$REMOTE_USER@$ip" true >/dev/null 2>&1; }
install_via_transport(){ local alias="$1" ip="$2" port="$3" transport="$4" pub; pub="$(key_path "$alias").pub"; cat "$pub" | timeout 10 ssh -F /dev/null -i "$transport" -p "$port" -o IdentitiesOnly=yes -o IdentityAgent=none -o BatchMode=yes -o NumberOfPasswordPrompts=0 -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o PreferredAuthentications=publickey -o ConnectionAttempts=1 -o ConnectTimeout="$CONNECT_TIMEOUT" -o StrictHostKeyChecking=accept-new "$REMOTE_USER@$ip" 'set -eu; umask 077; mkdir -p ~/.ssh; chmod 700 ~/.ssh; touch ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys; IFS= read -r k; grep -qxF "$k" ~/.ssh/authorized_keys || printf "%s\n" "$k" >> ~/.ssh/authorized_keys'; }
find_transport_key(){ local alias="$1" ip="$2" port="$3" dedicated candidate; dedicated="$(key_path "$alias")"; for candidate in "$SSH_DIR/id_ed25519" "$SSH_DIR/id_ecdsa" "$SSH_DIR/id_rsa" "$SSH_DIR/id_dsa" "$SSH_DIR"/id_*; do [[ -f "$candidate" ]] || continue; [[ "$candidate" == *.pub || "$candidate" == *.cert ]] && continue; [[ "$candidate" == "$dedicated" ]] && continue; case "$(basename "$candidate")" in id_ed25519_core|id_ed25519_ha-node-a|id_ed25519_ha-node-b) continue;; esac; ssh-keygen -y -f "$candidate" >/dev/null 2>&1 || continue; if transport_key_works "$candidate" "$ip" "$port"; then printf '%s\n' "$candidate"; return 0; fi; done; return 1; }
deploy_auto(){ local alias="$1" ip="$2" port="$3" transport; if key_works "$alias" "$ip" "$port"; then return 0; fi; if transport="$(find_transport_key "$alias" "$ip" "$port")"; then ok "$alias using transport key $(basename "$transport")"; if install_via_transport "$alias" "$ip" "$port" "$transport" && key_works "$alias" "$ip" "$port"; then ok "$alias dedicated key self-installed"; return 0; fi; fi; warn "$alias no working transport key; trying password bootstrap if permitted"; deploy_key "$alias" "$ip" "$port" && key_works "$alias" "$ip" "$port"; }
deploy_key(){ local alias="$1" ip="$2" port="$3" pub; pub="$(key_path "$alias").pub"; if command -v ssh-copy-id >/dev/null 2>&1; then ssh-copy-id -i "$pub" -p "$port" -o StrictHostKeyChecking=accept-new "$REMOTE_USER@$ip"; else cat "$pub" | ssh -p "$port" -o StrictHostKeyChecking=accept-new "$REMOTE_USER@$ip" 'set -eu; umask 077; mkdir -p ~/.ssh; chmod 700 ~/.ssh; touch ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys; IFS= read -r k; grep -qxF "$k" ~/.ssh/authorized_keys || printf "%s\n" "$k" >> ~/.ssh/authorized_keys'; fi; }
if ((START_TUNNELS)); then for t in "${TUNNELS[@]}"; do IFS='|' read -r name via lp rh rp <<< "$t"; ssh -fNT -L "127.0.0.1:${lp}:${rh}:${rp}" -o ExitOnForwardFailure=yes "$via" && ok "$name started" || warn "$name failed"; done; exit 0; fi
if ((SOCKS)); then ssh -fNT -D "127.0.0.1:${SOCKS_PORT}" -o ExitOnForwardFailure=yes core && ok "SOCKS5 started on 127.0.0.1:${SOCKS_PORT}"; exit 0; fi
if ((STOP_TUNNELS)); then pkill -f 'ssh .* -[LD] ' || true; ok "SSH tunnels stopped"; exit 0; fi
if ((STATUS)); then for e in "${HOSTS[@]}"; do IFS='|' read -r fqdn alias ip port <<< "$e"; if key_works "$alias" "$ip" "$port"; then echo "$alias OK"; else echo "$alias FAIL"; fi; done; exit 0; fi
if [[ -s "$SSH_CONFIG" ]]; then cp -p "$SSH_CONFIG" "$BACKUP_DIR/config.$(date +%Y%m%d-%H%M%S).bak"; fi
fail=0
for e in "${HOSTS[@]}"; do IFS='|' read -r fqdn alias ip port <<< "$e"; ensure_key "$fqdn" "$alias" || { warn "$alias key failed"; fail=1; continue; }; write_config "$fqdn" "$alias" "$ip" "$port"; if key_works "$alias" "$ip" "$port"; then ok "$alias dedicated key already authorized"; continue; fi; if deploy_auto "$alias" "$ip" "$port"; then ok "$alias passwordless SSH verified"; else warn "$alias bootstrap failed"; fail=1; fi; done
exit "$fail"
