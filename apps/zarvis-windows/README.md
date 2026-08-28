# Z.A.R.V.I.S. Windows 11 Client

Native owner-only Windows client for the local Z.A.R.V.I.S. runtime.

## Security model

- The Ubuntu server remains bound to `127.0.0.1`.
- The client creates two local SSH forwards with Windows OpenSSH.
- No public HTTP listener, reverse proxy, router forwarding, or browser credential is introduced.
- The client stores server address, SSH user, key path, and ports only.
- `ZARVIS_LOCAL_OWNER_TOKEN` is retrieved only after an explicit click, copied to the clipboard, never written to disk, and cleared after 60 seconds.
- SSH runs in `BatchMode=yes`; use an SSH key or Windows SSH agent.
- Host keys use the Windows OpenSSH known-hosts store and `StrictHostKeyChecking=accept-new`.

## Development

```powershell
cd apps\zarvis-windows
dotnet restore .\src\ZARVIS.Windows\ZARVIS.Windows.csproj
dotnet test .\tests\ZARVIS.Windows.Tests\ZARVIS.Windows.Tests.csproj -c Release
dotnet run --project .\src\ZARVIS.Windows\ZARVIS.Windows.csproj
```

## Build

```powershell
.\scripts\build.ps1 -Version 0.1.0
```

GitHub Actions produces:

- `ZARVIS.exe` — self-contained `win-x64` single-file application
- `ZARVIS-Setup-<version>-win-x64.exe` — per-user installer
- `SHA256SUMS.txt`
- `release-manifest.json`

Code signing is applied when the repository secrets
`WINDOWS_SIGNING_CERT_PFX_BASE64` and `WINDOWS_SIGNING_CERT_PASSWORD` are set.
Unsigned artifacts remain suitable for owner testing but Windows SmartScreen may warn.

## Release visibility

`cvsz/z-platform` is currently a public repository. Workflow artifacts require
GitHub access, but a GitHub Release published from this repository is public.
The Windows binaries contain no Owner Token, worker token, provider credential,
or private SSH key. Server authorization remains permanently enforced by the
owner-only local runtime.

The initial supported release line is `0.1.x` for Windows 11 x64. Every build
must pass Windows runner tests, single-file publication, installer creation,
SHA-256 manifest generation, and provenance artifact upload.
