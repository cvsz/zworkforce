<#
.SYNOPSIS
    Automated Windows 11 / Windows Server Installer for ZEAZ Provider & PowerShell 7.

.DESCRIPTION
    Checks Python 3.11+ prerequisite, creates an isolated virtual environment,
    installs the ZEAZ Provider wheel package, configures local provider settings,
    and sets up PowerShell wrapper CMD and PS1 entrypoints.

.PARAMETER Apply
    Applies changes to the system. Default is dry-run mode.

.PARAMETER DryRun
    Simulates installation without modifying files.

.PARAMETER Prefix
    Target installation directory. Defaults to "$env:LOCALAPPDATA\zeaz-provider".
#>

[CmdletBinding(DefaultParameterSetName = 'DryRun')]
param (
    [Parameter(ParameterSetName = 'Apply')]
    [switch]$Apply,

    [Parameter(ParameterSetName = 'DryRun')]
    [switch]$DryRun,

    [string]$Prefix = "$env:LOCALAPPDATA\zeaz-provider",
    [string]$BinDir = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
)

$ErrorActionPreference = 'Stop'

function Write-ZeazLog {
    param(
        [string]$Level,
        [string]$Message
    )
    $timestamp = (Get-Date).ToString("o")
    Write-Host "$timestamp level=$Level msg=`"$Message`""
}

$Root = Resolve-Path "$PSScriptRoot\.."
$PyProject = Get-Content "$Root\pyproject.toml" -Raw
if ($PyProject -match 'version = "(.*?)"') {
    $Version = $Matches[1]
} else {
    $Version = "0.4.0rc1"
}

$IsApply = $PSCmdlet.ParameterSetName -eq 'Apply'
Write-ZeazLog -Level "INFO" -Message "Windows 11 Installer for ZEAZ Provider v$Version (ApplyMode=$IsApply)"

# Prerequisite Checks
$Python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command python3.exe -ErrorAction SilentlyContinue
}

if (-not $Python) {
    Write-ZeazLog -Level "ERROR" -Message "Python 3.11+ is required but python.exe was not found in PATH."
    Write-Host "Please install Python 3.11+ from the Microsoft Store or https://www.python.org/ and retry." -ForegroundColor Red
    exit 1
}

$TargetVersionDir = Join-Path $Prefix "versions\$Version"
$CurrentDir = Join-Path $Prefix "current"
$ConfigDir = Join-Path $Prefix "config"
$ConfigFile = Join-Path $ConfigDir "providers.yaml"

if (-not $IsApply) {
    Write-ZeazLog -Level "INFO" -Message "[DRY-RUN] Would create isolated environment at: $TargetVersionDir"
    Write-ZeazLog -Level "INFO" -Message "[DRY-RUN] Would link active version to: $CurrentDir"
    Write-ZeazLog -Level "INFO" -Message "[DRY-RUN] Would generate Windows wrapper scripts in: $BinDir"
    exit 0
}

# Create Directory Hierarchy
New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "versions") | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Prefix "backups") | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

# Build Virtual Environment if missing
if (-not (Test-Path $TargetVersionDir)) {
    Write-ZeazLog -Level "INFO" -Message "Creating Python virtual environment at $TargetVersionDir..."
    & $Python.Source -m venv $TargetVersionDir

    $VenvPip = Join-Path $TargetVersionDir "Scripts\pip.exe"
    $VenvPython = Join-Path $TargetVersionDir "Scripts\python.exe"

    $Wheel = Get-ChildItem -Path "$Root\dist" -Filter "zeaz_provider-*-py3-none-any.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Wheel) {
        Write-ZeazLog -Level "INFO" -Message "Installing package wheel: $($Wheel.FullName)"
        & $VenvPip install --disable-pip-version-check $Wheel.FullName
    } else {
        Write-ZeazLog -Level "INFO" -Message "Installing zeaz-provider in editable mode from $Root..."
        & $VenvPip install --disable-pip-version-check -e $Root
    }
}

# Initialize Configuration if missing
$ExampleConfig = Join-Path $Root "config\providers.example.yaml"
if ((-not (Test-Path $ConfigFile)) -and (Test-Path $ExampleConfig)) {
    Copy-Item $ExampleConfig $ConfigFile
    Write-ZeazLog -Level "INFO" -Message "Initialized default configuration at $ConfigFile"
}

# Create Junction/Symlink for 'current'
if (Test-Path $CurrentDir) {
    Remove-Item -Recurse -Force $CurrentDir
}
New-Item -ItemType Junction -Path $CurrentDir -Target $TargetVersionDir | Out-Null

# Create Windows Batch and PowerShell Launcher Wrappers
$CmdLauncher = Join-Path $BinDir "zeaz-provider.cmd"
$PsLauncher = Join-Path $BinDir "zeaz-provider.ps1"
$TargetExecutable = Join-Path $CurrentDir "Scripts\zeaz-provider.exe"

$CmdContent = @"
@echo off
setlocal
if not defined ZEAZ_CONFIG set "ZEAZ_CONFIG=$ConfigFile"
"$TargetExecutable" %*
endlocal
"@

$PsContent = @"
if (-not `$env:ZEAZ_CONFIG) { `$env:ZEAZ_CONFIG = "$ConfigFile" }
& "$TargetExecutable" `@args
"@

Set-Content -Path $CmdLauncher -Value $CmdContent -Encoding ASCII
Set-Content -Path $PsLauncher -Value $PsContent -Encoding ASCII

Write-ZeazLog -Level "INFO" -Message "Successfully installed ZEAZ Provider v$Version for Windows 11."
Write-ZeazLog -Level "INFO" -Message "Wrappers created: $CmdLauncher"
