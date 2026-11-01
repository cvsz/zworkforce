# Financial JWT Duplicate JSON Member Admission — v437

## Risk

JSON.parse silently accepts repeated member names and keeps the last value. A
signed JWT with duplicate `aud`, `sub`, `tenant_id`, `scope`, `exp`, or
header `kid` can be interpreted differently by independent identity gateways,
auditors, and financial services. Signature validity does not remove the
cross-parser ambiguity.

## Candidate change

- Parse the compact JWT header and payload with a bounded, duplicate-member
  rejecting scanner after JSON syntax validation and before any JWKS retrieval
  or membership lookup.
- Compare decoded property names, including Unicode-escaped aliases, at every
  object nesting level.
- Preserve existing RS256, exact-audience, issuer, membership, and PostgreSQL
  tenant authorization requirements. Valid unique-member JWTs remain accepted.
- Fail closed with the existing 403 response for ambiguous JWTs.
- Do not activate financial HTTP mutations, real payments, migrations, or
  production traffic.

## Verification

```bash
node --check services/billing-ledger/strict-json.mjs
node --check services/billing-ledger/tenant-identity.mjs
node --test services/billing-ledger/test/strict-json-v437.test.mjs services/billing-ledger/test/tenant-identity-duplicate-json-v437.test.mjs
node --test services/billing-ledger/test/*.test.mjs
```

Only disposable/synthetic credentials are used. Full hosted CI, PostgreSQL
membership admission, independent security review and exact-head checks must
be completed before merge. This change is not proof of production OIDC/JWKS
or customer membership integration.

## Rollback

Revert this candidate's isolated commits on the draft branch after verifying
the baseline. Keep financial HTTP writes disabled. Do not restore acceptance
of ambiguous signed JWTs in a production authorization path.
