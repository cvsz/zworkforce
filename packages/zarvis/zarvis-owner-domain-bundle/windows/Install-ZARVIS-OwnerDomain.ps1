[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._:-]+$')]
    [string]$ServerHost,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9._-]*$')]
    [string]$SshUser,

    [ValidateRange(1, 65535)]
    [int]$SshPort = 22,

    [string]$IdentityFile = ""
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', "`"$PSCommandPath`"",
        '-ServerHost', "`"$ServerHost`"",
        '-SshUser', "`"$SshUser`"",
        '-SshPort', "$SshPort"
    )
    if ($IdentityFile) {
        $arguments += @('-IdentityFile', "`"$IdentityFile`"")
    }
    Start-Process powershell.exe -Verb RunAs -ArgumentList ($arguments -join ' ')
    exit
}

$ssh = Join-Path $env:WINDIR 'System32\OpenSSH\ssh.exe'
$sshKeygen = Join-Path $env:WINDIR 'System32\OpenSSH\ssh-keygen.exe'
if (-not (Test-Path $ssh) -or -not (Test-Path $sshKeygen)) {
    throw 'Windows OpenSSH Client is required. Install OpenSSH.Client~~~~0.0.1.0 first.'
}

$sourceCa = Join-Path $PSScriptRoot 'zarvis-owner-ca.crt'
if (-not (Test-Path $sourceCa)) {
    throw "Missing certificate: $sourceCa"
}

$installDir = Join-Path $env:LOCALAPPDATA 'ZARVIS\OwnerDomain'
$sshDir = Join-Path $env:USERPROFILE '.ssh'
New-Item $installDir -ItemType Directory -Force | Out-Null
New-Item $sshDir -ItemType Directory -Force | Out-Null

if (-not $IdentityFile) {
    $IdentityFile = Join-Path $sshDir 'zarvis_owner_ed25519'
}
$IdentityFile = [IO.Path]::GetFullPath($IdentityFile)

if (-not (Test-Path $IdentityFile)) {
    Write-Host 'Generating a dedicated Windows SSH key...'
    & $sshKeygen -q -t ed25519 -f $IdentityFile -N '""' -C "zarvis-owner@$env:COMPUTERNAME"
    if ($LASTEXITCODE -ne 0) {
        throw 'ssh-keygen failed.'
    }
}

function Test-KeyAuthentication {
    & $ssh `
        -o BatchMode=yes `
        -o ConnectTimeout=8 `
        -o StrictHostKeyChecking=accept-new `
        -p $SshPort `
        -i $IdentityFile `
        "$SshUser@$ServerHost" `
        'true'
    return $LASTEXITCODE -eq 0
}

if (-not (Test-KeyAuthentication)) {
    Write-Host ''
    Write-Host 'The dedicated key is not authorized yet.'
    Write-Host 'Enter the Linux SSH password once to install the public key.'
    $publicKey = Get-Content "$IdentityFile.pub" -Raw
    $encodedKey = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($publicKey.Trim()))
    $remote = "umask 077; mkdir -p ~/.ssh; printf '%s' '$encodedKey' | base64 -d >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
    & $ssh `
        -o StrictHostKeyChecking=accept-new `
        -p $SshPort `
        "$SshUser@$ServerHost" `
        $remote
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not authorize the dedicated SSH key.'
    }
}

if (-not (Test-KeyAuthentication)) {
    throw 'Dedicated SSH key authentication still fails.'
}

$certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new($sourceCa)
$store = [Security.Cryptography.X509Certificates.X509Store]::new(
    [Security.Cryptography.X509Certificates.StoreName]::Root,
    [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
)
$store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
try {
    $existing = $store.Certificates | Where-Object Thumbprint -eq $certificate.Thumbprint
    if (-not $existing) {
        $store.Add($certificate)
    }
}
finally {
    $store.Close()
}

$hostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$hostsText = Get-Content $hostsPath -Raw
$blockPattern = '(?ms)^# BEGIN ZARVIS OWNER DOMAIN\r?\n.*?^# END ZARVIS OWNER DOMAIN\r?\n?'
$hostsText = [Regex]::Replace($hostsText, $blockPattern, '')
$hostsBlock = @"
# BEGIN ZARVIS OWNER DOMAIN
127.0.0.1 zarvis.zeaz.dev action.zarvis.zeaz.dev proactive.zarvis.zeaz.dev
# END ZARVIS OWNER DOMAIN
"@
$updatedHosts = $hostsText.TrimEnd() + [Environment]::NewLine + $hostsBlock + [Environment]::NewLine
[IO.File]::WriteAllText($hostsPath, $updatedHosts, [Text.Encoding]::ASCII)
ipconfig /flushdns | Out-Null

$installedCa = Join-Path $installDir 'zarvis-owner-ca.crt'
Copy-Item $sourceCa $installedCa -Force

$config = [ordered]@{
    server_host = $ServerHost
    ssh_user = $SshUser
    ssh_port = $SshPort
    identity_file = $IdentityFile
    ca_thumbprint = $certificate.Thumbprint
    primary_url = 'https://zarvis.zeaz.dev'
    proactive_url = 'https://proactive.zarvis.zeaz.dev'
}
$config | ConvertTo-Json | Set-Content (Join-Path $installDir 'config.json') -Encoding UTF8

$startScript = @'
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$installDir = Join-Path $env:LOCALAPPDATA 'ZARVIS\OwnerDomain'
$config = Get-Content (Join-Path $installDir 'config.json') -Raw | ConvertFrom-Json
$pidPath = Join-Path $installDir 'ssh.pid'
$logPath = Join-Path $installDir 'ssh.log'
$ssh = Join-Path $env:WINDIR 'System32\OpenSSH\ssh.exe'

if (Test-Path $pidPath) {
    $oldPid = [int](Get-Content $pidPath -Raw)
    $oldProcess = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($oldProcess) {
        try {
            $health = Invoke-RestMethod -Uri 'https://zarvis.zeaz.dev/healthz' -TimeoutSec 3
            if ($health.status -eq 'ok' -and $health.local_only -eq $true) {
                exit 0
            }
        }
        catch {
            Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        }
    }
}

$existing443 = Get-NetTCPConnection -LocalPort 443 -State Listen -ErrorAction SilentlyContinue
if ($existing443) {
    throw 'TCP port 443 is already in use. Stop the conflicting local service first.'
}

$args = @(
    '-N',
    '-T',
    '-o', 'BatchMode=yes',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3',
    '-o', 'StrictHostKeyChecking=accept-new',
    '-p', [string]$config.ssh_port,
    '-i', ('"' + [string]$config.identity_file + '"'),
    '-L', '127.0.0.1:443:127.0.0.1:8443',
    "$($config.ssh_user)@$($config.server_host)"
)

$process = Start-Process $ssh `
    -ArgumentList $args `
    -WindowStyle Hidden `
    -RedirectStandardError $logPath `
    -PassThru
$process.Id | Set-Content $pidPath -Encoding ASCII

for ($attempt = 1; $attempt -le 40; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($process.HasExited) {
        throw "SSH tunnel exited. See $logPath"
    }
    try {
        $action = Invoke-RestMethod -Uri 'https://zarvis.zeaz.dev/healthz' -TimeoutSec 3
        $proactive = Invoke-RestMethod -Uri 'https://proactive.zarvis.zeaz.dev/healthz' -TimeoutSec 3
        if (
            $action.status -eq 'ok' -and
            $action.local_only -eq $true -and
            $action.secrets_exposed -eq $false -and
            $proactive.status -eq 'ok' -and
            $proactive.local_only -eq $true -and
            $proactive.secrets_exposed -eq $false
        ) {
            exit 0
        }
    }
    catch {
        if ($attempt -eq 40) {
            throw
        }
    }
}

throw 'Z.A.R.V.I.S. owner domain health verification timed out.'
'@

$startPath = Join-Path $installDir 'Start-ZARVIS-OwnerDomain.ps1'
$startScript | Set-Content $startPath -Encoding UTF8

$taskName = 'ZARVIS Owner Domain'
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startPath`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Description 'Owner-only SSH tunnel for zarvis.zeaz.dev' `
    -Force | Out-Null

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $startPath

$health = Invoke-RestMethod -Uri 'https://zarvis.zeaz.dev/healthz' -TimeoutSec 5
if ($health.status -ne 'ok' -or $health.local_only -ne $true -or $health.secrets_exposed -ne $false) {
    throw 'Final Z.A.R.V.I.S. owner-domain health verification failed.'
}

Write-Host ''
Write-Host 'Z.A.R.V.I.S. Owner Domain is ready:'
Write-Host '  https://zarvis.zeaz.dev'
Write-Host '  https://proactive.zarvis.zeaz.dev'
Start-Process 'https://zarvis.zeaz.dev'
