# Incident Runbook

## Severity triggers

- Provider credential exposure.
- Browser receives upstream provider secret.
- Wallet signing, card data, KYC payload, MPC share, or swap route reaches AI/billing paths.
- Billing ledger idempotency failure.
- Unauthorized shell/deploy execution.
- Failed CI gate on protected branch.

## First response

1. Stop external traffic at Cloudflare Access or ingress.
2. Preserve logs and audit events.
3. Rotate affected service tokens or credentials.
4. Disable provider adapters involved in the incident.
5. Confirm no destructive infrastructure action occurred.
6. Document timeline, impact, and rollback.

## Rollback

Rollback must identify:

- commit SHA
- service version
- data migration status
- operator approval
- verification commands
- follow-up prevention item
