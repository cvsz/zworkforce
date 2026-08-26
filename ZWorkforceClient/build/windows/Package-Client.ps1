[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [ValidateSet("x64", "ARM64")]
    [string]$Platform = "x64",
    [ValidatePattern("^v?\d+\.\d+\.\d+(\.\d+)?$")]
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$appProject = Join-Path $root "src\ZWorkforceClient\ZWorkforceClient.csproj"
$manifestPath = Join-Path $root "src\ZWorkforceClient\Package.appxmanifest"
$output = Join-Path $root "out\$Configuration-$Platform"
$temporaryPfxPath = Join-Path $output "zworkforce-client-temporary.pfx"
$cerPath = Join-Path $output "zworkforce-client-temporary.cer"
$normalizedVersion = $Version.TrimStart("v")
$signingPfxPath = $env:ZWORKFORCE_MSIX_SIGNING_PFX_PATH
$signingPfxPassword = $env:ZWORKFORCE_MSIX_SIGNING_PFX_PASSWORD
$signingPublisher = $env:ZWORKFORCE_MSIX_SIGNING_PUBLISHER
$requireTrustedSigning = $env:ZWORKFORCE_MSIX_REQUIRE_TRUSTED_SIGNING -in @("1", "true", "TRUE", "True")
$packageVersion = if ($normalizedVersion.Split(".").Count -eq 3) {
    "$normalizedVersion.0"
} else {
    $normalizedVersion
}

if ($packageVersion.Split(".") | Where-Object { [int]$_ -gt 65535 }) {
    throw "The MSIX version must use four numeric components, each no greater than 65535: $packageVersion"
}

New-Item -ItemType Directory -Force -Path $output | Out-Null

$certificate = $null
$generatedSigningCertificate = $false
$importedSigningCertificateThumbprints = @()
$certificatePassword = $null
$pfxPath = $null
$signingCertificateThumbprint = $null
$originalManifestBytes = [IO.File]::ReadAllBytes($manifestPath)
try {
    Get-ChildItem -LiteralPath $output -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    $manifestText = [Text.Encoding]::UTF8.GetString($originalManifestBytes)
    $hasSigningPfxPath = -not [string]::IsNullOrWhiteSpace($signingPfxPath)
    $hasSigningPfxPassword = -not [string]::IsNullOrWhiteSpace($signingPfxPassword)
    if ($hasSigningPfxPath -xor $hasSigningPfxPassword) {
        throw "Both ZWORKFORCE_MSIX_SIGNING_PFX_PATH and ZWORKFORCE_MSIX_SIGNING_PFX_PASSWORD are required for an external MSIX signing identity."
    }
    if ($requireTrustedSigning -and -not $hasSigningPfxPath) {
        throw "Trusted MSIX signing is required for this build, but no signing PFX was supplied. Configure the release signing secrets."
    }
    $identityPattern = '(<Identity\b[^>]*\bVersion=")[^"]+(")'
    if (-not [regex]::Match($manifestText, $identityPattern).Success) {
        throw "Could not locate the package Identity Version in $manifestPath."
    }
    $versionedManifest = [regex]::Replace(
        $manifestText,
        $identityPattern,
        ('${1}' + $packageVersion + '${2}'),
        1
    )
    if ($hasSigningPfxPath) {
        if (-not (Test-Path -LiteralPath $signingPfxPath -PathType Leaf)) {
            throw "The configured MSIX signing PFX was not found at $signingPfxPath."
        }
        try {
            $certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
                $signingPfxPath,
                $signingPfxPassword,
                [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet)
        } catch {
            throw "The configured MSIX signing PFX could not be opened: $($_.Exception.Message)"
        }
        if (-not $certificate.HasPrivateKey) {
            throw "The configured MSIX signing PFX does not contain a private key."
        }
        if ($certificate.NotAfter -le (Get-Date)) {
            throw "The configured MSIX signing certificate is expired."
        }
        $signingCertificateThumbprint = $certificate.Thumbprint.Replace(' ', '').ToUpperInvariant()
        $existingSigningCertificate = Get-ChildItem -LiteralPath "Cert:\CurrentUser\My" -ErrorAction SilentlyContinue |
            Where-Object { $_.Thumbprint.Replace(' ', '').ToUpperInvariant() -eq $signingCertificateThumbprint } |
            Select-Object -First 1
        if ($null -ne $existingSigningCertificate -and -not $existingSigningCertificate.HasPrivateKey) {
            throw "The configured MSIX signing certificate already exists in the current user store without a private key; refusing to replace it automatically."
        }
        if ($null -eq $existingSigningCertificate) {
            $securePfxPassword = ConvertTo-SecureString $signingPfxPassword -AsPlainText -Force
            $importedStoreCertificates = @(Import-PfxCertificate `
                -FilePath $signingPfxPath `
                -Password $securePfxPassword `
                -CertStoreLocation "Cert:\CurrentUser\My")
            $importedSigningCertificateThumbprints = @(
                $importedStoreCertificates |
                    ForEach-Object { $_.Thumbprint.Replace(' ', '').ToUpperInvariant() } |
                    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                    Select-Object -Unique
            )
            $importedStoreCertificate = $importedStoreCertificates |
                Where-Object { $_.Thumbprint.Replace(' ', '').ToUpperInvariant() -eq $signingCertificateThumbprint } |
                Select-Object -First 1
            if ($null -eq $importedStoreCertificate) {
                throw "The configured MSIX signing PFX did not import its signing certificate into the current user store."
            }
        }
        $pfxPath = $signingPfxPath
        $certificatePassword = $signingPfxPassword
        Export-Certificate -Cert $certificate -FilePath $cerPath -Force | Out-Null
    } else {
        $certificate = New-SelfSignedCertificate `
            -Type CodeSigningCert `
            -Subject "CN=cvsz" `
            -FriendlyName "zWorkforce Client temporary package signing" `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -KeyExportPolicy Exportable `
            -NotAfter (Get-Date).AddDays(7)
        $generatedSigningCertificate = $true
        $signingCertificateThumbprint = $certificate.Thumbprint.Replace(' ', '').ToUpperInvariant()
        $certificatePassword = [Guid]::NewGuid().ToString("N")
        $secureCertificatePassword = ConvertTo-SecureString $certificatePassword -AsPlainText -Force
        Export-PfxCertificate -Cert $certificate -FilePath $temporaryPfxPath -Password $secureCertificatePassword | Out-Null
        Export-Certificate -Cert $certificate -FilePath $cerPath -Force | Out-Null
        $pfxPath = $temporaryPfxPath
    }

    $publisher = if ([string]::IsNullOrWhiteSpace($signingPublisher)) {
        $certificate.Subject
    } else {
        $signingPublisher.Trim()
    }
    if ([string]::IsNullOrWhiteSpace($publisher)) {
        throw "The MSIX signing certificate does not provide a publisher subject."
    }
    $identityPublisherPattern = '(<Identity\b[^>]*\bPublisher=")[^"]+(")'
    if (-not [regex]::Match($versionedManifest, $identityPublisherPattern).Success) {
        throw "Could not locate the package Identity Publisher in $manifestPath."
    }
    $versionedManifest = [regex]::Replace(
        $versionedManifest,
        $identityPublisherPattern,
        ('${1}' + $publisher + '${2}'),
        1
    )
    [IO.File]::WriteAllText($manifestPath, $versionedManifest, [Text.UTF8Encoding]::new($false))

    $publishArguments = @(
        "publish", $appProject,
        "--configuration", $Configuration,
        "--property:Platform=$Platform",
        "--property:RuntimeIdentifier=win-$($Platform.ToLowerInvariant())",
        "--property:WindowsAppSDKSelfContained=true",
        "--property:SelfContained=true",
        "--property:ApplicationDisplayVersion=$normalizedVersion",
        "--property:AppxPackageVersion=$packageVersion",
        "--property:GenerateAppxPackageOnBuild=true",
        "--property:AppxPackageSigningEnabled=true",
        "--property:PackageCertificateKeyFile=$pfxPath",
        "--property:PackageCertificatePassword=$certificatePassword",
        "--property:PackageCertificateThumbprint=$($certificate.Thumbprint)",
        "--property:AppxBundle=Never",
        "--property:AppxPackageDir=$output\",
        "--no-restore"
    )
    & dotnet @publishArguments
    if ($LASTEXITCODE -ne 0) { throw "The packaged client publish failed with exit code $LASTEXITCODE." }
}
finally {
    [IO.File]::WriteAllBytes($manifestPath, $originalManifestBytes)
    foreach ($thumbprint in $importedSigningCertificateThumbprints) {
        Remove-Item -LiteralPath "Cert:\CurrentUser\My\$thumbprint" -Force -ErrorAction SilentlyContinue
    }
    if ($generatedSigningCertificate -and $null -ne $certificate) {
        Remove-Item -LiteralPath "Cert:\CurrentUser\My\$($certificate.Thumbprint)" -Force -ErrorAction SilentlyContinue
    }
    if ($generatedSigningCertificate) {
        Remove-Item -LiteralPath $temporaryPfxPath -Force -ErrorAction SilentlyContinue
    }
}

$package = Get-ChildItem -LiteralPath $output -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Extension -in @(".msix", ".msixbundle") -and
        $_.FullName -notmatch '\\obj\\' -and
        $_.Name -match ("_" + [regex]::Escape($packageVersion) + "_")
    } |
    Sort-Object LastWriteTimeUtc |
    Select-Object -Last 1
if ($null -eq $package) {
    throw "The publish completed without producing an MSIX artifact for version $packageVersion."
}

$certificateSource = Get-ChildItem -LiteralPath $package.Directory.FullName -File -Filter "*.cer" -ErrorAction SilentlyContinue |
    Where-Object BaseName -eq $package.BaseName |
    Select-Object -First 1
if ($null -eq $certificateSource) {
    $certificateSource = Get-Item -LiteralPath $cerPath
}

$packageDestination = Join-Path $output $package.Name
if ([IO.Path]::GetFullPath($package.FullName) -ne [IO.Path]::GetFullPath($packageDestination)) {
    Copy-Item -LiteralPath $package.FullName -Destination $packageDestination -Force
}
$certificateDestination = Join-Path $output $certificateSource.Name
if ([IO.Path]::GetFullPath($certificateSource.FullName) -ne [IO.Path]::GetFullPath($certificateDestination)) {
    Copy-Item -LiteralPath $certificateSource.FullName -Destination $certificateDestination -Force
}
if ([IO.Path]::GetFullPath($certificateSource.FullName) -ne [IO.Path]::GetFullPath($cerPath)) {
    Remove-Item -LiteralPath $cerPath -Force -ErrorAction SilentlyContinue
}

Write-Host "Windows client package artifacts:"
Write-Host "  Package version: $packageVersion"
Get-ChildItem -LiteralPath $output -File |
    Where-Object { $_.Extension -in @(".msix", ".msixbundle", ".cer") } |
    ForEach-Object { Write-Host "  $($_.FullName)" }
