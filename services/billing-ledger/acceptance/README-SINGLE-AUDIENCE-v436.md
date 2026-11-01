# Financial JWT Single-Audience Admission (candidate v436)

## Risk and decision
A signature-valid JWT whose `aud` includes both the financial API and an unrelated service was previously accepted by the billing tenant resolver. A verified signature alone does not prove that a multi-service token was minted for the financial action. Without an issuer-specific authorized-party contract, this creates a cross-service token substitution risk.

## Narrow fix
- Accept `aud: "zeaz-financial"` or `aud: ["zeaz-financial"]` when the configured audience is `zeaz-financial`.
- Reject multi-valued `aud` arrays (including duplicates), missing or unrelated audiences, and malformed arrays **before membership lookup**.
- Keep signature, issuer, scope, expiry, JWKS, authoritative membership, and tenant-RLS checks unchanged.
- No production OIDC/JWKS activation, HTTP mutation, payment execution, migration, or deployment.

## Verification
```bash
node --check services/billing-ledger/tenant-identity.mjs
node --test services/billing-ledger/test/tenant-identity-v430.test.mjs services/billing-ledger/test/tenant-identity-clock-v430.test.mjs
```
The test uses generated RSA keys and synthetic claims. It does not verify a real customer IdP.

## Compatibility and operator gates
Issuers that currently mint multiple audiences must issue a financial-only access token before enabling this candidate. Do not relax the rule or infer `azp` without a reviewed issuer-specific contract and negative tests. Confirm production OIDC discovery, JWKS rotation, authoritative membership, revocation, cross-service E2E, exact-head CI, independent approval, and release gates before merge/deployment.

## Rollback
Revert the isolated source/test/documentation commits through a reviewed PR if the issuer contract changes. Do not enable financial HTTP mutations as part of rollback.
