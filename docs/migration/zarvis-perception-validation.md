# Z.A.R.V.I.S. Perception Validation

Date: 2026-08-06
Epic: #148
Issue: #153
Branch: `feat/zarvis-consent-perception`

## Focused coverage

- strict 32-byte encryption key validation;
- exact consent digest/nonce and pending-only activation;
- rejection before activation, after stop, after expiry, and outside consented modalities;
- strict canonical base64 and 5 MiB media limit;
- PII/token redaction and prompt-injection neutralization;
- fixed `policy_effect: none`, empty tool grants, and no raw-media retention;
- PNG dimension/provenance analysis;
- encrypted journal with no raw or redacted plaintext;
- full session event compaction deletion;
- retention-worker purge;
- owner-only static/API routes and independent worker auth;
- startup failure without all required secrets.

## Required gates

- [ ] `services/zarvis-perception` tests pass.
- [ ] perception contract tests pass.
- [ ] all existing Node workspace tests pass.
- [ ] CI, validate, CodeQL Advanced, operations, and deployed-smoke pass.
- [ ] no unresolved review thread.

External provider, browser-device compatibility, origin isolation, key rotation, and release-infrastructure evidence remain tracked in #156.
