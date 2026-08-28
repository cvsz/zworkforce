# Z.A.R.V.I.S. Perception Privacy Threat Model

| Threat | Control |
|---|---|
| Hidden/continuous capture | One owner-triggered frame; browser stops all tracks immediately; no loop or background service |
| Modality escalation | Exact consent binds allowed modalities; mismatched submissions return 403 |
| Consent replay/tampering | SHA-256 digest, one-time nonce, pending-only activation, short expiry |
| Oversized/malformed media | Strict canonical base64, 5 MiB cap, signature and dimension validation |
| Prompt injection | Extracted text marked untrusted and instruction phrases neutralized before persistence |
| PII/credential leakage | Email, phone, token, bearer, and private-key patterns redacted |
| Policy/tool escalation | Persisted result fixes `policy_effect: none`, empty grants, untrusted content |
| Raw media exposure | Raw bytes never written; in-memory buffer overwritten after analysis |
| Plaintext disk exposure | AES-256-GCM encrypted fixed-path journal; key external to repository |
| Request-controlled path | One operator-controlled journal path only |
| Cross-user access | Immutable owner ID and trusted-edge secret; caller tenant/user ignored |
| Incomplete deletion | Session deletion compacts proposal, activation, analysis, and stop events |
| Expired analysis retention | Retrieval remains session-scoped; authenticated worker physically purges expired sessions |
| Biometric surveillance | No face recognition, identity matching, or biometric templates |

Provider-backed vision must not receive unredacted secrets and must never treat media text as instructions. Any future model adapter requires a separate security review and provenance-preserving contract tests.
