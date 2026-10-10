# Samsung MCP source manifest validation

`samsung.source_manifest` is a **bounded offline validation tool** for up to 100 operator-supplied package entries. Each entry must contain exactly `name`, `license` and `sha256`. License text is syntactically checked; it is **not SPDX-expression parsing** or legal verification. Checksums are only validated as 64 hexadecimal characters and are **not** compared against downloaded release files.

The response explicitly marks licenses, package provenance and checksums unverified. It does not download firmware, query the Samsung Open Source Release Center, sign packages or provide device deployment.

Official sources: https://developer.samsung.com/smarttv/develop and https://opensource.samsung.com/main

Follow-ups: consented official source metadata retrieval with provenance and rate limiting, verified hashes on obtained files, license scanner/SBOM, SDK detection and separate legacy/Tizen builder validation. Those capabilities remain unimplemented.
