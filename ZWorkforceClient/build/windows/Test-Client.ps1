[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [ValidatePattern("^\d+\.\d+\.\d+\.\d+$")]
    [string]$ExpectedVersion,
    [switch]$LaunchSmoke
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$solution = Join-Path $root "ZWorkforceClient.sln"
$appProject = Join-Path $root "src\ZWorkforceClient\ZWorkforceClient.csproj"

function Remove-ClientPackage([string]$PackageFullName) {
    if ([string]::IsNullOrWhiteSpace($PackageFullName)) {
        return
    }

    $removalJob = Start-Job -ScriptBlock {
        param($FullName)
        Remove-AppxPackage -Package $FullName -ForceApplicationShutdown -ErrorAction SilentlyContinue
    } -ArgumentList $PackageFullName
    try {
        if ($null -eq (Wait-Job -Job $removalJob -Timeout 30)) {
            Write-Warning "Timed out removing packaged client $PackageFullName; the ephemeral runner will discard it."
            Stop-Job -Job $removalJob -ErrorAction SilentlyContinue
        } else {
            Receive-Job -Job $removalJob -ErrorAction SilentlyContinue | Out-Null
        }
    } finally {
        Remove-Job -Job $removalJob -Force -ErrorAction SilentlyContinue
    }
}

function Find-ClientPackage {
    $queryJob = Start-Job -ScriptBlock {
        Get-AppxPackage -Name "cvsz.ZWorkforceClient" -ErrorAction SilentlyContinue |
            Sort-Object Version -Descending |
            Select-Object -First 1 PackageFullName, PackageFamilyName, Version
    }
    try {
        if ($null -eq (Wait-Job -Job $queryJob -Timeout 30)) {
            Write-Warning "Timed out querying the packaged client; continuing without a stale-package cleanup."
            Stop-Job -Job $queryJob -ErrorAction SilentlyContinue
            return $null
        }
        return Receive-Job -Job $queryJob -ErrorAction SilentlyContinue |
            Select-Object -First 1
    } finally {
        Remove-Job -Job $queryJob -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-Certutil([string[]]$Arguments) {
    $process = Start-Process -FilePath "certutil.exe" -ArgumentList $Arguments -NoNewWindow -PassThru
    if (-not $process.WaitForExit(60 * 1000)) {
        $process.Kill()
        throw "certutil.exe timed out while updating the machine certificate store."
    }
    if ($process.ExitCode -ne 0) {
        throw "certutil.exe failed with exit code $($process.ExitCode)."
    }
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "The packaged launch smoke check requires an elevated PowerShell session because it temporarily trusts the MSIX certificate in the machine Trusted People store."
    }
}

& dotnet test $solution --configuration $Configuration --property:Platform=x64 --no-restore
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($LaunchSmoke) {
    Assert-Administrator
    $packageDirectory = Join-Path $root "out\$Configuration-x64"
    $package = Get-ChildItem -LiteralPath $packageDirectory -File -Filter "*.msix" |
        Sort-Object LastWriteTimeUtc |
        Select-Object -Last 1
    if ($null -eq $package) {
        throw "The packaged launch smoke check requires an MSIX under $packageDirectory. Run Package-Client.ps1 first."
    }

    $certificate = Get-ChildItem -LiteralPath $packageDirectory -File -Filter "*.cer" |
        Sort-Object LastWriteTimeUtc |
        Select-Object -Last 1
    $importedCertificateThumbprint = $null
    $installedPackage = $null
    try {
        Write-Host "Checking for a previous packaged client installation."
        $previousPackage = Find-ClientPackage
        if ($null -ne $previousPackage) {
            Remove-ClientPackage $previousPackage.PackageFullName
        }

        if ($null -ne $certificate) {
            Write-Host "Trusting the temporary package certificate for this smoke check."
            $certificateDetails = Get-PfxCertificate -FilePath $certificate.FullName
            if ($null -eq $certificateDetails -or [string]::IsNullOrWhiteSpace($certificateDetails.Thumbprint)) {
                throw "Could not read the temporary package certificate thumbprint from $($certificate.FullName)."
            }
            $quotedCertificatePath = '"' + $certificate.FullName + '"'
            Invoke-Certutil @("-f", "-addstore", "TrustedPeople", $quotedCertificatePath)
            $importedCertificateThumbprint = $certificateDetails.Thumbprint.Replace(' ', '').ToUpperInvariant()
        }

        Write-Host "Installing the packaged client."
        Add-AppxPackage -Path $package.FullName -ForceApplicationShutdown -ErrorAction Stop

        Write-Host "Resolving the installed package identity."
        $installedPackage = Find-ClientPackage
        if ($null -eq $installedPackage) {
            throw "The MSIX installed without a discoverable cvsz.ZWorkforceClient package."
        }
        if (-not [string]::IsNullOrWhiteSpace($ExpectedVersion) -and
            $installedPackage.Version.ToString() -ne $ExpectedVersion) {
            throw "The installed MSIX version $($installedPackage.Version) does not match expected $ExpectedVersion."
        }

        $appShellId = "shell:AppsFolder\$($installedPackage.PackageFamilyName)!App"
        Start-Process -FilePath "explorer.exe" -ArgumentList $appShellId | Out-Null
        Start-Sleep -Seconds 8
        $process = Get-Process -Name "ZWorkforceClient" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -eq $process) {
            throw "The packaged client did not remain running after launch."
        }
        Write-Host "Windows client launch smoke check is alive (PID $($process.Id))."
    } finally {
        Get-Process -Name "ZWorkforceClient" -ErrorAction SilentlyContinue |
            Stop-Process -Force -ErrorAction SilentlyContinue
        if ($null -ne $installedPackage) {
            Remove-ClientPackage $installedPackage.PackageFullName
        }
        if ($null -ne $importedCertificateThumbprint) {
            try {
                Invoke-Certutil @("-delstore", "TrustedPeople", $importedCertificateThumbprint)
                $remainingCertificates = @(Get-ChildItem -Path "Cert:\LocalMachine\TrustedPeople" -ErrorAction Stop |
                    Where-Object { $_.Thumbprint.Replace(' ', '').ToUpperInvariant() -eq $importedCertificateThumbprint })
                if ($remainingCertificates.Count -ne 0) {
                    throw "The temporary package certificate $importedCertificateThumbprint is still present in the machine Trusted People store."
                }
                Write-Host "Removed the temporary package certificate from the machine Trusted People store."
            } catch {
                throw "Could not remove the temporary package certificate: $($_.Exception.Message)"
            }
        }
    }
}
