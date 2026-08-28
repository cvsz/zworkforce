[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList (
        "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    )
    exit
}

$installDir = Join-Path $env:LOCALAPPDATA 'ZARVIS\OwnerDomain'
$configPath = Join-Path $installDir 'config.json'
$pidPath = Join-Path $installDir 'ssh.pid'

Unregister-ScheduledTask -TaskName 'ZARVIS Owner Domain' -Confirm:$false -ErrorAction SilentlyContinue

if (Test-Path $pidPath) {
    $pidValue = [int](Get-Content $pidPath -Raw)
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
}

if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    if ($config.ca_thumbprint) {
        $store = [Security.Cryptography.X509Certificates.X509Store]::new(
            [Security.Cryptography.X509Certificates.StoreName]::Root,
            [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
        )
        $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        try {
            foreach ($certificate in @($store.Certificates | Where-Object Thumbprint -eq $config.ca_thumbprint)) {
                $store.Remove($certificate)
            }
        }
        finally {
            $store.Close()
        }
    }
}

$hostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$hostsText = Get-Content $hostsPath -Raw
$blockPattern = '(?ms)^# BEGIN ZARVIS OWNER DOMAIN\r?\n.*?^# END ZARVIS OWNER DOMAIN\r?\n?'
$hostsText = [Regex]::Replace($hostsText, $blockPattern, '')
[IO.File]::WriteAllText($hostsPath, $hostsText.TrimEnd() + [Environment]::NewLine, [Text.Encoding]::ASCII)
ipconfig /flushdns | Out-Null

Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Z.A.R.V.I.S. Owner Domain integration removed.'
