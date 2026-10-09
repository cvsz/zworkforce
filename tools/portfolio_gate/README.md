# Portfolio release attestation verifier (candidate)

This module is a **read-only, non-executing building block** for an evidence-based release gate. It does not merge, deploy, move money, change DNS, or authorize production traffic. No production-ready claim is made.

## Trust boundary

- A verifier and a separate operator must sign different domain-separated canonical JSON payloads using distinct pinned Ed25519 public keys.
- The verifier receipt binds the exact snapshot and evidence-manifest SHA-256 digests, the target repository/main SHA, issue time, expiry (maximum 24 hours), and a verified verdict.
- The operator approval binds the signed verifier receipt digest and exact target SHA. The trust store must come from independently controlled configuration, never from the receipt or the repository under evaluation.
- Missing, expired, untrusted, tampered, or mismatched input fails closed. Signatures only authenticate the supplied claims; they do **not** prove that production-equivalent tests actually happened.
- The module must be composed with existing CI, branch/ruleset, review, artifact-byte integrity, security, DR, payment and external evidence checks before it can participate in a release decision.
- Never commit private keys, credentials, or real customer data. Never treat synthetic tests as production evidence.

## Required integration work

1. Pin the direct `cryptography` dependency in the owning environment and verify supported Python versions.
2. Add positive and negative signature fixtures using ephemeral test-only keys, plus malformed input/fuzz tests.
3. Integrate with a trusted, independent verifier and operator approval source, enforcing key rotation and revocation.
4. Bind the verified receipt to the existing fail-closed portfolio gate, artifact byte hashing, and fresh GitHub check results.
5. Run exact-head CI/security scanning, obtain review, and rehearse rollback before any deployment.

Current status: **implementation candidate only**; no CI, approval, deployment, or external operator evidence is asserted.
