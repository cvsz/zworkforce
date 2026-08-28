# Cloudflare Access Service Policies

Production deployment is blocked until an operator maps these logical policies to the selected Cloudflare account, zones, service tokens, and identity provider.

## Service-to-service rules

| Caller | Target | Required Policy |
|---|---|---|
| ZAI Coder Web | AI Gateway | Service token, tenant header, gateway allowlist |
| ZChat | AI Gateway | Service token, tenant header, gateway allowlist |
| AI Gateway | Billing Ledger | Service token, private route, usage-only path allowlist |
| ZWallet Adapter | Billing Ledger | Service token, invoice/credits path allowlist |
| Agent Orchestrator | Provider adapters | Service token, private route, tool-scope allowlist |
| ZOW | Workspace Runtime | Service token, runtime path allowlist |

## Deny rules

- Deny browser access to upstream provider URLs.
- Deny browser access to service tokens.
- Deny wallet signing, card, KYC, MPC, swap, and production infrastructure routes from AI services.
- Deny deployment and shell routes unless an approval grant is present.

## Required operator inputs

- Cloudflare account and zone IDs.
- Access team domain.
- Service token issuer/rotation policy.
- Identity provider and tenant-claim mapping.
- Secret storage location.
- The approved identity-provider and claim-mapping snapshot is tracked in `scripts/staging-decision-record.json` and validated by `scripts/validate-staging-decision-record.mjs`.
