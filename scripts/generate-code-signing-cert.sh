#!/usr/bin/env bash
# Generate a self-signed code-signing certificate for local/dev MSIX signing.
# Replaces Azure Artifact Signing dependency (Stage H).
# NEVER commit the private key or its password. Commit only the .cer public cert.
set -euo pipefail

OUT_DIR="${1:-build/windows-certs}"
SUBJECT="${2:-CN=ZEAZDEV Code Signing Test, O=ZEAZDEV COMPANY LIMITED}"

if [[ -z "${CODE_SIGNING_PFX_PASSWORD:-}" || -z "${CODE_SIGNING_PFX_PASSWORD//[[:space:]]/}" ]]; then
  printf '%s\n' "CODE_SIGNING_PFX_PASSWORD must be set before generating the PFX." >&2
  exit 2
fi

# Keep generated private material owner-readable only.
umask 077
mkdir -p "$OUT_DIR"

# Self-signed code-signing certificate (RSA 4096, 10y, codeSigning EKU 1.3.6.1.5.5.7.3.3)
OPENSSL_CONF=/dev/null openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout "$OUT_DIR/code-signing.key" \
  -out "$OUT_DIR/code-signing.cer" \
  -subj "$SUBJECT" \
  -addext "keyUsage=critical,digitalSignature" \
  -addext "extendedKeyUsage=critical,codeSigning" \
  -addext "basicConstraints=critical,CA:FALSE"

# Build an install-trustable PFX using the environment passphrase source.
# This avoids placing the password in the OpenSSL process argument list.
OPENSSL_CONF=/dev/null openssl pkcs12 -export \
  -out "$OUT_DIR/code-signing.pfx" \
  -inkey "$OUT_DIR/code-signing.key" \
  -in "$OUT_DIR/code-signing.cer" \
  -name "ZEAZDEV Code Signing Test" \
  -passout "env:CODE_SIGNING_PFX_PASSWORD"

echo "Generated:"
echo "  public cert: $OUT_DIR/code-signing.cer"
echo "  PFX bundle:  $OUT_DIR/code-signing.pfx"
echo "  private key: $OUT_DIR/code-signing.key (DO NOT COMMIT)"
echo
echo "Expected publisher for MSIX: extract from cert with:"
echo "  openssl x509 -in $OUT_DIR/code-signing.cer -noout -subject"
