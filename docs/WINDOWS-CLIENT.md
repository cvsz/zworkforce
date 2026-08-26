# zWorkforce Windows 11 client

`ZWorkforceClient` is a native C# WinUI 3 packaged desktop client for the
existing zWorkforce REST control plane. It does not run workers, providers, or
model calls locally. API keys, tenant authorization, policy, approvals, and
durable state remain server-side.

## Supported environment

The checked-in client targets Windows 11 22H2/build 22621 or later and uses:

- .NET 10 SDK;
- Visual Studio 2026 with the **WinUI application development** workload, or
  the supported .NET CLI path;
- Windows SDK 10.0.26100.0 or newer;
- stable Windows App SDK 2.3.1 through NuGet;
- Developer Mode enabled for local package deployment and launch;
- Git for Windows; GitHub CLI is optional for repository operations.

Visual Studio is the recommended IDE path. GitHub CI and scripted builds use
the .NET CLI path, so Visual Studio is not required on a headless build host.
Microsoft's current setup guidance is the source of truth for machine
installation:

- [WinUI setup overview](https://learn.microsoft.com/windows/apps/get-started/winui-get-started-overview)
- [Create a WinUI 3 app](https://learn.microsoft.com/windows/apps/windows-app-sdk/set-up-your-development-environment)
- [Windows App SDK downloads](https://learn.microsoft.com/windows/apps/windows-app-sdk/downloads)
- [Windows SDK component IDs](https://learn.microsoft.com/visualstudio/install/workload-component-id-vs-build-tools)

From an elevated PowerShell prompt, the supported automated setup is:

```powershell
winget configure -f https://aka.ms/winui-config
```

The repository audit script does not install anything unless `-Install` is
explicitly supplied:

```powershell
Set-Location .\ZWorkforceClient
.\build\windows\Install-Prerequisites.ps1 -CheckOnly
.\build\windows\Install-Prerequisites.ps1 -Install
```

After setup, restart the terminal/Visual Studio and verify:

```powershell
dotnet --version
dotnet new list winui
```

## Build and test

From the repository root on Windows:

```powershell
Set-Location .\ZWorkforceClient
.\build\windows\Build-Client.ps1 -Configuration Release -Platform x64
.\build\windows\Test-Client.ps1 -Configuration Release
.\build\windows\Package-Client.ps1 -Configuration Release -Platform x64
```

For a versioned package, pass the three- or four-part release version. The
script temporarily applies the version to the package manifest and restores
the source file before it exits:

```powershell
.\build\windows\Package-Client.ps1 -Configuration Release -Platform x64 -Version 3.0.4
```

The project is a packaged app. The normal IDE launch path is Visual Studio F5,
which builds, signs with the development certificate, registers the MSIX, and
launches it. The CLI build/package path is also supported on a Windows host
with the .NET 10 SDK, Windows SDK, and WinUI template. The scripted smoke path
is:

```powershell
.\build\windows\Test-Client.ps1 -Configuration Release -LaunchSmoke
```

Run that command from an elevated PowerShell session. The smoke check
temporarily adds the test certificate to the machine `Trusted People` store so
Windows package deployment can validate it, then removes the certificate and
package in its cleanup phase. Visual Studio F5 uses its normal development
certificate path.

The smoke check proves that the packaged launch process stays alive; it does
not claim a live server connection. Use the Connection page to connect to a
server after launch.

## Connect to a local server

Start zWorkforce in the repository's normal development environment:

```bash
python -m pip install .
python -m zworkforce doctor
python -m zworkforce serve
```

Then enter the following in the Windows client:

```text
Server URL: http://localhost:9569
Tenant ID:  default
API key:    the server-generated API key
```

The client first checks `/health` and `/ready`, then calls the authenticated
`/api/v1/*` routes with `Authorization: Bearer ...` and `X-Tenant-ID`. Writes
include an `Idempotency-Key`. A server error displays its request ID when one
is returned.

For the deployed Workforce control plane, use:

```text
Server URL: https://zwf.zeaz.dev
Tenant ID:  the assigned tenant
API key:    the operator API key
```

The public hostname must be served through HTTPS. The client refuses to send
credentials to non-local HTTP endpoints.

## Credentials and privacy

- API keys are held in memory only for the active session.
- When **Remember** is selected, the key is stored in Windows
  `PasswordVault`/Credential Manager under a server-and-tenant-specific entry.
- The base URL, tenant ID, and theme are stored in packaged application local
  settings; the API key is not.
- Logs, diagnostics, issue reports, and screenshots must not contain API keys,
  bearer tokens, or private tenant data.
- Use HTTPS for every non-local server. Plain HTTP is intended only for local
  development.

## Project layout

```text
ZWorkforceClient/
  src/ZWorkforceClient.Core/       platform-neutral REST client
  src/ZWorkforceClient/            packaged WinUI 3 shell and pages
  tests/ZWorkforceClient.Core.Tests/ API contract tests without a live server
  build/windows/                   PowerShell environment/build/package tools
```

The core service covers the documented health, overview, tasks, agents,
workflow, evaluation, memory, artifact, FinOps/SLO, identity, audit, and
provider route groups. The UI exposes operator pages and delegates every
authorization decision to the server.

## GitHub checks

`.github/workflows/windows-client.yml` runs on Windows for client changes. It
audits the runner, restores, builds, tests, packages, and runs the launch
smoke check. The workflow uploads MSIX artifacts on success and `bin`/`obj`
diagnostics on failure.

Require the **Windows client / build-test-package** check in branch protection
alongside the existing Python CI, security, CodeQL, and dependency checks.
Release automation builds the versioned package from the same protected version
tag, signs the exact unsigned MSIX with Azure Artifact Signing through GitHub
Actions OIDC, verifies the signature and timestamp, runs the install smoke
test against that exact file, generates a SHA-256 checksum, and uploads the
package, public signer certificate, and checksum to the GitHub Release. The
tag must be created only after the required Windows check is green.

A production release should additionally record the exact Windows check URL,
artifact name, trusted publisher/signature state, deployed HTTPS endpoint, and
functional smoke result in `docs/PRODUCTION-EVIDENCE.md` or the immutable
release record.

Before tag creation, run the manual `Windows signed candidate` workflow with
the full 40-character commit SHA already merged into `main`. It is the safe
pre-tag signing path: it requires the protected release environment, refuses
unmerged or moving refs, and uploads a candidate-bound signed package,
certificate, checksum, metadata, and run record without publishing a release.
Use those outputs to complete Stage H; the tag workflow signs the immutable
release artifact again after GO.

## Package signing

`Package-Client.ps1` produces a self-contained, versioned MSIX so a clean Windows 11 host
does not need a separately installed Windows App SDK runtime. Local builds use
a development certificate suitable for sideloading on the developer machine;
the scripted smoke check installs that package for the current user, launches
the registered app, verifies the real client process remains alive, and removes
the package and temporary certificate afterward.

The checked-in pull-request path uses a short-lived development certificate
for test and sideload artifacts; the uploaded `.cer` is public and is not a
production trust anchor. For production, call
`Package-Client.ps1 -Unsigned -Publisher <publisher>`, then use
`azure/login@v3` with OIDC and `azure/artifact-signing-action@v2` to sign the
artifact with SHA-256 and an RFC 3161 timestamp. The release verifier requires
an Authenticode-valid signature, trusted certificate chain, Code Signing EKU,
expected publisher/version, timestamp, and MSIX signature entries before
installation. Never commit a private certificate, PFX, password, API key, or
signing token. The package output is under `ZWorkforceClient/out/` and is
intentionally ignored by Git.
