# Signed agent plugins

Plugins belong exclusively to `zeaz-agent`. The provider gateway never imports,
loads, extracts, or executes plugin content.

## Package contract

A plugin is a ZIP archive accompanied by a raw 64-byte Ed25519 signature and a
trusted signing-key identifier. The signature covers the exact archive bytes
and is verified before ZIP or manifest parsing. `plugin.json` uses schema
version `1` and identifies the plugin name, semantic version, description, and
the exact size and SHA-256 digest of every payload file.

The archive reader rejects:

- missing, invalid, or untrusted signatures;
- absolute, traversal, hidden, backslash, non-normalized, duplicate, and
  case-colliding paths;
- symbolic links, devices, FIFOs, directories, encryption, and unsupported
  compression;
- undeclared files and manifest size or digest mismatches;
- excessive archive bytes, file bytes, entry count, expanded bytes, or
  per-entry expansion ratio.

Only regular files are materialized. Installed payload permissions are `0600`
and directory permissions are `0700`; archive executable bits are discarded.

## Registry lifecycle

The registry is rooted in a private, non-symlink directory and serialized by
an owner-only lock. A verified package is written and fsynced in a private
staging directory on the same filesystem, then renamed atomically to:

`plugins/<name>/versions/<version>`

New versions enter the SQLite registry disabled. Enabling is explicit and at
most one version of a plugin may be enabled. An enabled version cannot be
removed. Removal atomically moves a disabled version into `.trash`, records a
recovery identifier, and can be reversed with `restore`. Install, state change,
removal, and restoration append correlated events to the agent audit ledger.

Signature verification uses a fixed absolute OpenSSL executable with fixed
argv, an empty environment, no shell, a deadline, and trusted public-key bytes.
It never executes archive content.
