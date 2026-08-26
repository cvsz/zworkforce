# Verify-MSIXSignature.ps1 validates a production-signed MSIX before release.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedPublisher,
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^\d+\.\d+\.\d+\.\d+$")]
    [string]$ExpectedVersion,
    [string]$ExpectedSha256 = "",
    [string]$SignerCertificateOutputPath
)

$ErrorActionPreference = "Stop"

function Assert-TrustedCertificateChain {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $chain = [System.Security.Cryptography.X509Certificates.X509Chain]::new()
    try {
        $chain.ChainPolicy.RevocationMode = [System.Security.Cryptography.X509Certificates.X509RevocationMode]::Online
        $chain.ChainPolicy.RevocationFlag = [System.Security.Cryptography.X509Certificates.X509RevocationFlag]::EntireChain
        $chain.ChainPolicy.VerificationFlags = [System.Security.Cryptography.X509Certificates.X509VerificationFlags]::NoFlag
        if (-not $chain.Build($Certificate)) {
            $statuses = @($chain.ChainStatus | ForEach-Object { $_.Status.ToString() }) -join ","
            throw "$Description certificate chain is not trusted: $statuses"
        }
    } finally {
        $chain.Dispose()
    }
}

function Get-PackageIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [xml]$Manifest
    )

    $identity = $Manifest.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Identity']")
    if ($null -eq $identity) {
        $identity = $Manifest.SelectSingleNode("/*[local-name()='Bundle']/*[local-name()='Identity']")
    }
    if ($null -eq $identity) {
        throw "MSIX manifest does not contain a package identity."
    }
    return $identity
}

function Get-ZipEntryByName {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.Compression.ZipArchive]$Archive,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $entry = $Archive.GetEntry($Name)
    if ($null -eq $entry) {
        $entry = $Archive.Entries |
            Where-Object { [IO.Path]::GetFileName($_.FullName) -eq $Name } |
            Select-Object -First 1
    }
    return $entry
}

$package = Get-Item -LiteralPath $PackagePath -ErrorAction Stop
if ($package.PSIsContainer) {
    throw "MSIX package path is a directory: $PackagePath"
}
if ($package.Extension -notin @(".msix", ".msixbundle")) {
    throw "Expected an .msix or .msixbundle artifact, received $($package.Extension)."
}

$expectedPublisher = $ExpectedPublisher.Trim()
if ([string]::IsNullOrWhiteSpace($expectedPublisher)) {
    throw "ExpectedPublisher must not be empty."
}
if ([string]::IsNullOrWhiteSpace($ExpectedSha256) -eq $false -and
    $ExpectedSha256 -notmatch "^[0-9A-Fa-f]{64}$") {
    throw "ExpectedSha256 must be a 64-character SHA-256 value when supplied."
}

$hash = (Get-FileHash -LiteralPath $package.FullName -Algorithm SHA256).Hash.ToUpperInvariant()
if (-not [string]::IsNullOrWhiteSpace($ExpectedSha256) -and
    $hash -ne $ExpectedSha256.ToUpperInvariant()) {
    throw "MSIX SHA-256 does not match the expected release artifact hash."
}

$signature = Get-AuthenticodeSignature -LiteralPath $package.FullName
if ($signature.Status -ne "Valid") {
    $statusMessage = if ([string]::IsNullOrWhiteSpace([string]$signature.StatusMessage)) {
        "no status message"
    } else {
        [string]$signature.StatusMessage
    }
    throw "MSIX Authenticode signature is not valid: $($signature.Status) ($statusMessage)."
}

$signer = $signature.SignerCertificate
if ($null -eq $signer) {
    throw "MSIX signature did not expose a signer certificate."
}
if ($signer.Subject -ne $expectedPublisher) {
    throw "MSIX signer subject does not match the expected publisher."
}
if ($signer.Subject -eq $signer.Issuer) {
    throw "MSIX signer certificate is self-signed; a trusted production certificate is required."
}
if ($signer.NotAfter -le (Get-Date)) {
    throw "MSIX signer certificate is expired."
}

$ekuExtension = $signer.Extensions |
    Where-Object { $_.Oid.Value -eq "2.5.29.37" } |
    Select-Object -First 1
$hasCodeSigningEku = $false
if ($null -ne $ekuExtension) {
    $typedEkuExtension = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ekuExtension
    foreach ($oid in $typedEkuExtension.EnhancedKeyUsages) {
        if ($oid.Value -eq "1.3.6.1.5.5.7.3.3") {
            $hasCodeSigningEku = $true
            break
        }
    }
}
if (-not $hasCodeSigningEku) {
    throw "MSIX signer certificate does not contain the Code Signing EKU."
}

$timestampCertificate = $signature.TimeStamperCertificate
if ($null -eq $timestampCertificate) {
    throw "MSIX signature does not contain an RFC 3161 timestamp certificate."
}

Assert-TrustedCertificateChain -Certificate $signer -Description "MSIX signer"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($package.FullName)
try {
    $signatureEntry = Get-ZipEntryByName -Archive $archive -Name "AppxSignature.p7x"
    $blockMapEntry = Get-ZipEntryByName -Archive $archive -Name "AppxBlockMap.xml"
    $manifestEntry = Get-ZipEntryByName -Archive $archive -Name "AppxManifest.xml"
    if ($null -eq $manifestEntry) {
        $manifestEntry = Get-ZipEntryByName -Archive $archive -Name "AppxBundleManifest.xml"
    }
    if ($null -eq $signatureEntry) {
        throw "MSIX package is missing AppxSignature.p7x."
    }
    if ($null -eq $blockMapEntry) {
        throw "MSIX package is missing AppxBlockMap.xml."
    }
    if ($null -eq $manifestEntry) {
        throw "MSIX package is missing AppxManifest.xml or AppxBundleManifest.xml."
    }

    $manifestReader = [System.IO.StreamReader]::new($manifestEntry.Open())
    try {
        $manifestXml = [xml]$manifestReader.ReadToEnd()
    } finally {
        $manifestReader.Dispose()
    }
    $identity = Get-PackageIdentity -Manifest $manifestXml
    $manifestName = [string]$identity.Name
    $manifestVersion = [string]$identity.Version
    $manifestPublisher = [string]$identity.Publisher
    if ($manifestName -ne "cvsz.ZWorkforceClient") {
        throw "MSIX package identity name does not match cvsz.ZWorkforceClient."
    }
    if ($manifestVersion -ne $ExpectedVersion) {
        throw "MSIX package version $manifestVersion does not match expected $ExpectedVersion."
    }
    if ($manifestPublisher -ne $expectedPublisher) {
        throw "MSIX manifest publisher does not match the expected publisher."
    }
} finally {
    $archive.Dispose()
}

if (-not [string]::IsNullOrWhiteSpace($SignerCertificateOutputPath)) {
    $certificateOutputParent = Split-Path -Parent $SignerCertificateOutputPath
    if (-not [string]::IsNullOrWhiteSpace($certificateOutputParent)) {
        New-Item -ItemType Directory -Force -Path $certificateOutputParent | Out-Null
    }
    Export-Certificate -Cert $signer -FilePath $SignerCertificateOutputPath -Force | Out-Null
}

Write-Output ("PACKAGE=" + $package.Name)
Write-Output ("SHA256=" + $hash)
Write-Output "AUTHENTICODE_STATUS=Valid"
Write-Output ("SIGNER=" + $signer.Subject)
Write-Output ("SIGNER_THUMBPRINT=" + $signer.Thumbprint.Replace(" ", "").ToUpperInvariant())
Write-Output ("TIMESTAMP=" + $timestampCertificate.Subject)
Write-Output ("PUBLISHER=" + $expectedPublisher)
Write-Output "SIGNATURE=MSIX_APPX_SIGNATURE_PRESENT"
