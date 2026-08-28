# Z.A.R.V.I.S. Owner-Only Domain

## Goal

Provide the owner with:

- `https://zarvis.zeaz.dev` — Action Console
- `https://proactive.zarvis.zeaz.dev` — Proactive Console

without creating public HTTP ingress.

## Security boundary

The design deliberately does **not** publish DNS records or expose ports 443,
8098, 8099, or 8443 to a LAN or the public Internet.

```text
Windows browser
  https://zarvis.zeaz.dev:443
           |
           | Windows hosts file -> 127.0.0.1
           | owner SSH key
           v
Windows OpenSSH local forward 127.0.0.1:443
           |
           | encrypted SSH over LAN or Tailscale
           v
Ubuntu 127.0.0.1:8443 nginx TLS gateway
       |                         |
       v                         v
127.0.0.1:8098 Action      127.0.0.1:8099 Proactive
```

The existing owner token remains mandatory. The private CA key remains on the
Ubuntu host with mode `0600`; only its public root certificate is copied to the
owner's Windows certificate store.

## Deploy

```bash
cd ~/z-platform
git pull --ff-only origin main
bash scripts/zarvis-owner-domain-live.sh --confirm-live
```

The command performs actual-host validation, backup/restore, credential
rotation, starts the owner HTTPS gateway, verifies loopback-only listeners, and
creates:

```text
zarvis-owner-domain-bundle/zarvis-owner-domain-windows.zip
```

The setup script prefers the server's Tailscale IPv4 address when available.
Use `--server-host` to override it. The live wrapper passes the actual Linux
UID/GID into Compose so nginx runs as the owner and can read the private key
without widening its `0600` permissions.

## Install on the owner's Windows 11 machine

Copy the ZIP using the exact SCP command printed by the server, extract it, and
double-click:

```text
Install-ZARVIS-OwnerDomain.cmd
```

The installer:

1. elevates for the hosts-file change;
2. generates a dedicated Ed25519 SSH key;
3. asks for the Linux SSH password once when key authorization is needed;
4. imports the private owner root CA into `CurrentUser\Root`;
5. maps the three private names to Windows loopback;
6. creates a hidden logon scheduled task for the SSH local forward;
7. verifies Action and Proactive health invariants;
8. opens `https://zarvis.zeaz.dev`.

## Rotate the private CA

```bash
ZARVIS_OWNER_UID="$(id -u)" \
ZARVIS_OWNER_GID="$(id -g)" \
bash scripts/zarvis-owner-domain-setup.sh --rotate-ca
```

Reinstall the newly generated Windows bundle afterward.

## Remove from Windows

Run as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File .\Uninstall-ZARVIS-OwnerDomain.ps1
```

## Prohibited deployment changes

Do not add:

- public A/AAAA/CNAME records intended to expose the service;
- router port forwarding;
- Cloudflare Tunnel as the authorization boundary;
- a public reverse proxy;
- provider, owner, or worker credentials in browser code or artifacts.
