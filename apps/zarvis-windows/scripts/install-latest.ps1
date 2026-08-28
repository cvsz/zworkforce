[CmdletBinding()]
param(
    [string]$Repository = 'cvsz/z-platform',
    [switch]$IncludePrerelease
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI is required. Install it with: winget install GitHub.cli'
}

gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'GitHub CLI is not authenticated. Run: gh auth login'
}

$releaseJson = & gh release list --repo $Repository --limit 100 `
    --json tagName,isDraft,isPrerelease,publishedAt
if ($LASTEXITCODE -ne 0) {
    throw "GitHub release listing failed with exit code $LASTEXITCODE."
}

$release = $releaseJson |
    ConvertFrom-Json |
    Where-Object {
        -not $_.isDraft -and
        $_.tagName -like 'zarvis-windows-v*' -and
        ($IncludePrerelease -or -not $_.isPrerelease)
    } |
    Sort-Object { [DateTimeOffset]$_.publishedAt } -Descending |
    Select-Object -First 1

if (-not $release) {
    throw 'No matching Z.A.R.V.I.S. Windows release was found.'
}

$temp = Join-Path $env:TEMP "zarvis-update-$([Guid]::NewGuid())"
New-Item $temp -ItemType Directory -Force | Out-Null

try {
    & gh release download $release.tagName --repo $Repository --dir $temp `
        --pattern 'ZARVIS-Setup-*-win-x64.exe' `
        --pattern 'SHA256SUMS.txt'
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub release download failed with exit code $LASTEXITCODE."
    }

    $installer = Get-ChildItem $temp -Filter 'ZARVIS-Setup-*-win-x64.exe' |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $installer) {
        throw "No installer was found in release $($release.tagName)."
    }

    $sumFile = Join-Path $temp 'SHA256SUMS.txt'
    $expectedLine = Get-Content $sumFile |
        Where-Object { $_ -match "\s+$([Regex]::Escape($installer.Name))$" } |
        Select-Object -First 1
    if (-not $expectedLine) {
        throw "Checksum for $($installer.Name) is missing."
    }

    $expected = ($expectedLine -split '\s+')[0].ToLowerInvariant()
    $actual = (Get-FileHash $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -ne $actual) {
        throw "Checksum mismatch for $($installer.Name)."
    }

    Write-Host "Installing $($release.tagName) from verified SHA-256 artifact."
    Start-Process $installer.FullName -Wait
}
finally {
    Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
}
