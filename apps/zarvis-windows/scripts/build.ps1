[CmdletBinding()]
param(
    [Parameter()]
    [ValidatePattern('^\d+\.\d+\.\d+([-.][0-9A-Za-z.-]+)?$')]
    [string]$Version = '0.1.0',

    [Parameter()]
    [string]$Configuration = 'Release',

    [Parameter()]
    [string]$OutputDirectory = "$PSScriptRoot\..\artifacts"
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
$project = Join-Path $root 'src\ZARVIS.Windows\ZARVIS.Windows.csproj'
$tests = Join-Path $root 'tests\ZARVIS.Windows.Tests\ZARVIS.Windows.Tests.csproj'
$publish = Join-Path $OutputDirectory 'publish'

Remove-Item $OutputDirectory -Recurse -Force -ErrorAction SilentlyContinue
New-Item $publish -ItemType Directory -Force | Out-Null

dotnet restore $project
dotnet restore $tests
dotnet test $tests -c $Configuration --no-restore
dotnet publish $project -c $Configuration -r win-x64 --self-contained true `
    -p:Version=$Version -p:FileVersion=$Version -p:AssemblyVersion=$Version `
    -o $publish

$exe = Join-Path $publish 'ZARVIS.exe'
if (-not (Test-Path $exe)) {
    throw "ZARVIS.exe was not produced."
}

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  ZARVIS.exe" | Set-Content (Join-Path $OutputDirectory 'SHA256SUMS.txt') -Encoding ascii
Write-Host "Built $exe"
