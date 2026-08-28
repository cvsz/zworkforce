# Z.A.R.V.I.S. Windows Client Operations

## Purpose

`ZARVIS.exe` is a native Windows 11 control client for the single-owner local
Z.A.R.V.I.S. deployment. It does not convert the Ubuntu services into public
services. It manages Windows OpenSSH local forwarding and opens the existing
Action and Proactive web consoles on Windows loopback.

## Supported topology

```text
Windows 11 ZARVIS.exe
  127.0.0.1:8098 ─┐
  127.0.0.1:8099 ─┴─ encrypted SSH ─> Ubuntu/VM 127.0.0.1:8098/8099
```

The Ubuntu host remains owner-bound to GitHub numeric ID `4076926`.

## Prerequisites

Server:

- healthy Action and Proactive services on loopback
- GitHub CLI authenticated as the repository owner
- repository `main` synchronized and no tracked local changes

Windows:

- Windows 11 x64
- Windows OpenSSH Client
- SSH key or Windows `ssh-agent`
- network reachability to the Ubuntu SSH port

Install OpenSSH when absent:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

## Build, verify, and stage on the Ubuntu server

Run one owner-authenticated command:

```bash
cd "$HOME/z-platform"
bash scripts/zarvis-windows-release.sh 0.1.0
```

Default behavior is intentionally non-public. The command:

1. verifies both local-only server health endpoints;
2. dispatches `ZARVIS Windows Client` through authenticated GitHub CLI;
3. waits for Windows tests, self-contained publish, and installer creation;
4. downloads the Actions artifact to
   `zarvis-windows-releases/0.1.0/`;
5. verifies `SHA256SUMS.txt` and `release-manifest.json`;
6. creates a checksum-enforcing `Install-ZARVIS.ps1`;
7. prints the exact SCP and installation commands for Windows.

`cvsz/z-platform` is currently public. Publishing a GitHub Release therefore
makes the binaries public. Public publication is opt-in only:

```bash
bash scripts/zarvis-windows-release.sh 0.1.0 --publish-public-release
```

Require Authenticode signing as a hard release gate:

```bash
bash scripts/zarvis-windows-release.sh 0.1.0 --require-signed
```

## Install the staged artifact on Windows

The server command prints exact values. The resulting pattern is:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Downloads\ZARVIS-0.1.0" | Out-Null
scp -r cvsz@SERVER_IP:/home/cvsz/z-platform/zarvis-windows-releases/0.1.0/zarvis-windows-*/\* "$env:USERPROFILE\Downloads\ZARVIS-0.1.0\"
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\ZARVIS-0.1.0\Install-ZARVIS.ps1"
```

When a repository release exists, the authenticated updater selects only tags
matching `zarvis-windows-v*`, verifies SHA-256, and runs the installer:

```powershell
winget install GitHub.cli
gh auth login
pwsh .\apps\zarvis-windows\scripts\install-latest.ps1
```

## Credential handling

- Do not put the Owner Token into `settings.json`.
- Do not add the Owner Token to Windows environment variables.
- Do not include it in screenshots or support logs.
- The Copy Owner Token action performs one SSH command and clears the clipboard
  after 60 seconds when the clipboard still contains the same token.
- Rotate server credentials after suspected clipboard, SSH, or desktop compromise.

## Code signing

Trusted production distribution requires an Authenticode certificate. Configure:

- `WINDOWS_SIGNING_CERT_PFX_BASE64`
- `WINDOWS_SIGNING_CERT_PASSWORD`

The workflow signs both `ZARVIS.exe` and the installer when these secrets are
available. Without them, the release manifest records `signed: false` and the
server command warns that Windows SmartScreen may display a warning.

## Rollback

Install a previously verified staged version or an earlier
`zarvis-windows-v*` repository release. Client rollback does not modify server
durable state. Stop the tunnel before replacing the client binary.
