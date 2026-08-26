[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [ValidatePattern("^\d+\.\d+\.\d+\.\d+$")]
    [string]$ExpectedVersion,
    [string]$PackagePath,
    [switch]$LaunchSmoke,
    [switch]$InteractiveSmokeWorker,
    [string]$InteractiveSmokeResultPath,
    [switch]$SkipCoreTests,
    [switch]$SkipCertificateTrust,
    [switch]$SkipCertificateCleanup
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$solution = Join-Path $root "ZWorkforceClient.sln"
$appProject = Join-Path $root "src\ZWorkforceClient\ZWorkforceClient.csproj"
$scriptPath = (Resolve-Path $PSCommandPath).Path

function Remove-ClientPackage([string]$PackageFullName) {
    if ([string]::IsNullOrWhiteSpace($PackageFullName)) {
        return
    }

    try {
        Remove-AppxPackage -Package $PackageFullName -ForceApplicationShutdown -ErrorAction Stop
    } catch {
        Write-Warning "Could not remove packaged client ${PackageFullName}: $($_.Exception.Message)"
    }
}

function Find-ClientPackage {
    return Get-AppxPackage -Name "cvsz.ZWorkforceClient" -ErrorAction SilentlyContinue |
        Sort-Object Version -Descending |
        Select-Object -First 1 PackageFullName, PackageFamilyName, Version
}

function Import-TemporaryPackageCertificate([string]$CertificatePath) {
    if ([string]::IsNullOrWhiteSpace($CertificatePath)) {
        return $null
    }

    $certificateDetails = Get-PfxCertificate -FilePath $CertificatePath
    if ($null -eq $certificateDetails -or [string]::IsNullOrWhiteSpace($certificateDetails.Thumbprint)) {
        throw "Could not read the package certificate thumbprint from $CertificatePath."
    }
    $thumbprint = $certificateDetails.Thumbprint.Replace(' ', '').ToUpperInvariant()
    $existing = @(Get-ChildItem -LiteralPath "Cert:\LocalMachine\TrustedPeople" -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint.Replace(' ', '').ToUpperInvariant() -eq $thumbprint })
    if ($existing.Count -eq 0) {
        Import-Certificate -FilePath $CertificatePath -CertStoreLocation "Cert:\LocalMachine\TrustedPeople" | Out-Null
        return $thumbprint
    }
    return $null
}

function Remove-TemporaryPackageCertificate([string]$Thumbprint) {
    if ([string]::IsNullOrWhiteSpace($Thumbprint)) {
        return
    }

    Remove-Item -LiteralPath "Cert:\LocalMachine\TrustedPeople\$Thumbprint" -Force -ErrorAction Stop
    $remaining = @(Get-ChildItem -LiteralPath "Cert:\LocalMachine\TrustedPeople" -ErrorAction Stop |
        Where-Object { $_.Thumbprint.Replace(' ', '').ToUpperInvariant() -eq $Thumbprint })
    if ($remaining.Count -ne 0) {
        throw "The temporary package certificate $Thumbprint is still present in the machine Trusted People store."
    }
    Write-Host "Removed the temporary package certificate from the machine Trusted People store."
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "The packaged launch smoke check requires an elevated PowerShell session because it temporarily trusts the MSIX certificate in the machine Trusted People store."
    }
}

function ConvertTo-PowerShellLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-ActiveInteractiveSessionId {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $explorers = @(Get-Process -Name "explorer" -IncludeUserName -ErrorAction SilentlyContinue |
        Where-Object { $_.SessionId -gt 0 -and $_.UserName -eq $currentUser })
    $sessionIds = @($explorers | Select-Object -ExpandProperty SessionId -Unique)
    if ($sessionIds.Count -eq 0) {
        throw "The packaged launch smoke check requires an active desktop session for $currentUser; SSH session 0 cannot deploy an AppX package."
    }
    if ($sessionIds.Count -ne 1) {
        throw "The packaged launch smoke check found multiple active desktop sessions for $currentUser; use one unambiguous console session."
    }
    return [int]$sessionIds[0]
}

function Invoke-LaunchSmokeCore {
    param(
        [switch]$SkipTrust,
        [switch]$SkipCleanup
    )

    if (-not $SkipTrust) {
        Assert-Administrator
    }
    if ((Get-Process -Id $PID).SessionId -eq 0) {
        throw "The packaged launch smoke worker is running in session 0; rerun it from the active Windows desktop session."
    }

    $packageDirectory = Join-Path $root "out\$Configuration-x64"
    if (-not [string]::IsNullOrWhiteSpace($PackagePath)) {
        $package = Get-Item -LiteralPath $PackagePath -ErrorAction Stop
        if ($package.PSIsContainer -or $package.Extension -notin @(".msix", ".msixbundle")) {
            throw "PackagePath must point to an .msix or .msixbundle file."
        }
    } else {
        $package = Get-ChildItem -LiteralPath $packageDirectory -File |
            Where-Object { $_.Extension -in @(".msix", ".msixbundle") } |
            Sort-Object LastWriteTimeUtc |
            Select-Object -Last 1
        if ($null -eq $package) {
            throw "The packaged launch smoke check requires an MSIX under $packageDirectory. Run Package-Client.ps1 first."
        }
    }

    $certificate = Get-ChildItem -LiteralPath $package.Directory.FullName -File -Filter "*.cer" -ErrorAction SilentlyContinue |
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

        if ($null -ne $certificate -and -not $SkipTrust) {
            Write-Host "Trusting the temporary package certificate for this smoke check."
            $importedCertificateThumbprint = Import-TemporaryPackageCertificate $certificate.FullName
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
            Where-Object { $_.SessionId -eq (Get-Process -Id $PID).SessionId } |
            Select-Object -First 1
        if ($null -eq $process) {
            throw "The packaged client did not remain running after launch."
        }
        Write-Host "Windows client launch smoke check is alive (PID $($process.Id))."
    } finally {
        Get-Process -Name "ZWorkforceClient" -ErrorAction SilentlyContinue |
            Where-Object { $_.SessionId -eq (Get-Process -Id $PID).SessionId } |
            Stop-Process -Force -ErrorAction SilentlyContinue
        if ($null -ne $installedPackage) {
            Remove-ClientPackage $installedPackage.PackageFullName
        }
        if ($null -ne $importedCertificateThumbprint -and -not $SkipCleanup) {
            Remove-TemporaryPackageCertificate $importedCertificateThumbprint
        }
    }
}

function Invoke-InteractiveLaunchSmoke {
    param(
        [switch]$SkipTrust,
        [switch]$SkipCleanup
    )

    if (-not $SkipTrust) {
        Assert-Administrator
    }
    $activeSessionId = Get-ActiveInteractiveSessionId
    $packageDirectory = Join-Path $root "out\$Configuration-x64"
    $certificate = $null
    if (-not $SkipTrust) {
        $certificateDirectory = $packageDirectory
        if (-not [string]::IsNullOrWhiteSpace($PackagePath)) {
            $certificateDirectory = (Get-Item -LiteralPath $PackagePath -ErrorAction Stop).Directory.FullName
        }
        $certificate = Get-ChildItem -LiteralPath $certificateDirectory -File -Filter "*.cer" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc |
            Select-Object -Last 1
    }
    $taskName = "zworkforce-client-smoke-$([Guid]::NewGuid().ToString('N'))"
    $resultPath = Join-Path $env:TEMP "$taskName.result"
    $temporaryCertificateThumbprint = $null
    try {
        if ($null -ne $certificate -and -not $SkipTrust) {
            Write-Host "Trusting the temporary package certificate for the interactive smoke worker."
            $temporaryCertificateThumbprint = Import-TemporaryPackageCertificate $certificate.FullName
        }

        $workerArguments = @(
            "-Configuration $(ConvertTo-PowerShellLiteral $Configuration)",
            "-LaunchSmoke",
            "-InteractiveSmokeWorker",
            "-InteractiveSmokeResultPath $(ConvertTo-PowerShellLiteral $resultPath)",
            "-SkipCoreTests",
            "-SkipCertificateTrust",
            "-SkipCertificateCleanup"
        )
        if (-not [string]::IsNullOrWhiteSpace($ExpectedVersion)) {
            $workerArguments += "-ExpectedVersion $(ConvertTo-PowerShellLiteral $ExpectedVersion)"
        }
        if (-not [string]::IsNullOrWhiteSpace($PackagePath)) {
            $workerArguments += "-PackagePath $(ConvertTo-PowerShellLiteral $PackagePath)"
        }
        $workerCommand = "& $(ConvertTo-PowerShellLiteral $scriptPath) " + ($workerArguments -join " ")
        $encodedWorkerCommand = [Convert]::ToBase64String(
            [Text.Encoding]::Unicode.GetBytes($workerCommand))
        $pwsh = (Get-Command pwsh.exe -ErrorAction Stop).Source
        $action = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -NonInteractive -EncodedCommand $encodedWorkerCommand"
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
        $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
        Write-Host "Running interactive launch smoke worker in session $activeSessionId."
        Start-ScheduledTask -TaskName $taskName

        for ($i = 0; $i -lt 300 -and -not (Test-Path -LiteralPath $resultPath); $i++) {
            Start-Sleep -Seconds 1
        }
        if (-not (Test-Path -LiteralPath $resultPath)) {
            $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
            $lastResult = if ($null -eq $taskInfo) { "unknown" } else { $taskInfo.LastTaskResult }
            throw "Interactive launch smoke worker did not finish; Task Scheduler result: $lastResult."
        }
        $result = (Get-Content -LiteralPath $resultPath -Raw).Trim()
        if ($result -notlike "PASS*") {
            throw "Interactive launch smoke worker failed: $result"
        }
    } finally {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
        if ($null -ne $temporaryCertificateThumbprint -and -not $SkipCleanup) {
            Remove-TemporaryPackageCertificate $temporaryCertificateThumbprint
        }
    }
}

if (-not $SkipCoreTests) {
    & dotnet test $solution --configuration $Configuration --property:Platform=x64 --no-restore
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($LaunchSmoke) {
    if ($InteractiveSmokeWorker) {
        if ([string]::IsNullOrWhiteSpace($InteractiveSmokeResultPath)) {
            throw "InteractiveSmokeResultPath is required for the interactive launch smoke worker."
        }
        try {
            Invoke-LaunchSmokeCore -SkipTrust:$SkipCertificateTrust -SkipCleanup:$SkipCertificateCleanup
            [IO.File]::WriteAllText($InteractiveSmokeResultPath, "PASS")
        } catch {
            [IO.File]::WriteAllText($InteractiveSmokeResultPath, "FAIL=$($_.Exception.Message)")
            throw
        }
    } elseif ((Get-Process -Id $PID).SessionId -eq 0) {
        Invoke-InteractiveLaunchSmoke -SkipTrust:$SkipCertificateTrust -SkipCleanup:$SkipCertificateCleanup
    } else {
        Invoke-LaunchSmokeCore -SkipTrust:$SkipCertificateTrust -SkipCleanup:$SkipCertificateCleanup
    }
}
