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

$hostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$hostsText = Get-Content $hostsPath -Raw
$blockPattern = '(?ms)^# BEGIN ZARVIS OWNER DOMAIN\r?\n.*?^# END ZARVIS OWNER DOMAIN\r?\n?'
$hostsText = [Regex]::Replace($hostsText, $blockPattern, '')
$hostsBlock = @"
# BEGIN ZARVIS OWNER DOMAIN
127.0.0.1 zarvis.zeaz.dev action.zarvis.zeaz.dev proactive.zarvis.zeaz.dev voice.zarvis.zeaz.dev
# END ZARVIS OWNER DOMAIN
"@
$updated = $hostsText.TrimEnd() + [Environment]::NewLine + $hostsBlock + [Environment]::NewLine
[IO.File]::WriteAllText($hostsPath, $updated, [Text.Encoding]::ASCII)
ipconfig /flushdns | Out-Null

Start-ScheduledTask -TaskName 'ZARVIS Owner Domain' -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

$health = Invoke-RestMethod -Uri 'https://voice.zarvis.zeaz.dev/health' -TimeoutSec 15
if (
    $health.status -ne 'ok' -or
    $health.zarvis_owner_mode -ne $true -or
    $health.anonymous_access -ne $false -or
    $health.local_conversation_configured -ne $true -or
    $health.local_llm_only -ne $true
) {
    throw 'Owner-local Z.A.R.V.I.S. voice health verification failed.'
}

Write-Host ''
Write-Host 'Z.A.R.V.I.S. Local Conversation Mode is ready:'
Write-Host '  https://voice.zarvis.zeaz.dev'
Write-Host "  Local model: $($health.local_llm_model)"
Start-Process 'https://voice.zarvis.zeaz.dev'
