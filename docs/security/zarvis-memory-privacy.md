# Z.A.R.V.I.S. Memory Privacy Threat Model

## Threats and controls

| Threat | Control |
|---|---|
| Silent long-term memory write | Proposal state has no retrieval effect; exact owner confirmation is mandatory |
| Proposal changed after review | SHA-256 digest binds content, classification, reason, confidence, retention, expiry, and provenance |
| Approval replay | One proposal confirms once; replay returns the same snapshot without another write |
| Stale correction | Revision must be greater than the current confirmed revision |
| Secret persistence | Private-key, token, credential, bearer, and card-like patterns rejected before encryption |
| Plaintext disk exposure | AES-256-GCM encrypted journal; mode 0600; key external to repository and journal |
| Request-controlled path | One fixed journal filename under operator-controlled root |
| Cross-user access | Immutable owner `github:4076926`; trusted edge assertion; no user-supplied tenant |
| Expired memory leakage | Retrieval hides expired records immediately; authenticated worker compacts them |
| Incomplete deletion | Delete compacts every proposal and confirmed revision for the memory; no separate local index |
| Search-index residue | First adapter has no persisted plaintext/vector index |
| Tampering | GCM authentication fails decryption of altered events |
| Key leakage | Key supplied only by secret manager; never returned in health, API, logs, or browser code |

## Sensitive vault rule

The memory store is not a secret manager. Provider credentials, private keys, API tokens, passwords, payment card data, and signing material are rejected. Procedural memory may store a reference such as a secret-manager entry name, but not the secret value.

## Prompt injection boundary

Content sourced from documents, integrations, sessions, or tasks is untrusted data. A memory record cannot grant tools, change owner identity, alter system policy, approve an action, or create automation. Provenance is required so future consumers can apply source-specific trust policies.

## Key rotation

This slice requires an offline decrypt/re-encrypt migration to rotate the memory master key. Production rotation tooling and evidence remain part of #156. Until then, rotation must occur during a controlled outage with encrypted backup, integrity verification, and rollback plan.
