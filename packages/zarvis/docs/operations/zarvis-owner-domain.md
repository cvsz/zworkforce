# Z.A.R.V.I.S. Public Gateway and Owner-Only Consoles

## Canonical deployment modes

Z.A.R.V.I.S. has two distinct ingress contracts that must not be conflated:

1. **Public governed gateway** — `https://zarvis.zeaz.dev` is a Cloudflare-published alias for the zWorkforce control-plane/voice BFF on loopback origin `http://127.0.0.1:9570`. Public reachability does not grant mutation authority; zWorkforce authentication, tenant scope, approval policy, and short-lived voice-session tokens remain authoritative.
2. **Owner-only Action/Proactive consoles** — the local Action (`127.0.0.1:8098`) and Proactive (`127.0.0.1:8099`) services remain loopback-only. They are reached from the owner's Windows machine through the dedicated SSH-forward/private-CA bundle and are never exposed directly through Cloudflare, router forwarding, or a public reverse proxy.

The public gateway is defined by `deploy/cloudflare/tunnel-ingress.yml` and `infrastructure/terraform/cloudflare/zworkforce.tf`. Production Cloudflare apply must finish with `scripts/verify-zarvis-online.sh` passing.

## Owner-only security boundary

The private console path deliberately does **not** expose ports 8098, 8099, or 8443 to a LAN or the public Internet.

```text
Windows browser
  private owner console hostname
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

The owner token remains mandatory. The private CA key remains on the Ubuntu host with mode `0600`; only its public root certificate is copied to the owner's Windows certificate store.

## Public gateway verification

After the reviewed Cloudflare production apply:

```bash
cd ~/zworkforce
git pull --ff-only origin main
bash scripts/verify-zarvis-online.sh
```

On the origin host, also verify the governed loopback origin before publishing it:

```bash
ZARVIS_CHECK_LOCAL_ORIGIN=1 bash scripts/verify-zarvis-online.sh
```

A PASS means DNS resolves, TLS/HTTPS succeeds, `/health` succeeds, and the public application route answers. It does not by itself prove provider, voice-device, browser microphone, or mutation approval behavior.

## Deploy the owner-only local consoles

```bash
cd ~/zworkforce/packages/zarvis
git pull --ff-only origin main
bash scripts/zarvis-owner-domain-live.sh --confirm-live
```

The command performs actual-host validation, backup/restore, credential rotation, starts the owner HTTPS gateway, verifies loopback-only listeners, and creates:

```text
zarvis-owner-domain-bundle/zarvis-owner-domain-windows.zip
```

The setup script prefers the server's Tailscale IPv4 address when available. Use `--server-host` to override it. The live wrapper passes the actual Linux UID/GID into Compose so nginx runs as the owner and can read the private key without widening its `0600` permissions.

## Install on the owner's Windows 11 machine

Copy the ZIP using the exact SCP command printed by the server, extract it, and run:

```text
Install-ZARVIS-OwnerDomain.cmd
```

The installer elevates for the local hosts-file mapping, generates a dedicated Ed25519 SSH key, imports the private owner root CA, creates the local SSH-forward task, and verifies the Action and Proactive health invariants.

If a local hosts-file mapping uses `zarvis.zeaz.dev`, that workstation intentionally shadows the public DNS name while the owner-only tunnel is active. Remove that local override to test the public Cloudflare gateway.

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

Do not:

- expose Action/Proactive ports 8098/8099 directly to the Internet or LAN;
- use Cloudflare Tunnel as the authorization boundary;
- bypass zWorkforce authentication/tenant/approval policy on the public gateway;
- publish owner, worker, provider, database, or service credentials to browser code or artifacts;
- treat public `/health` success as production voice/provider/mutation evidence.
