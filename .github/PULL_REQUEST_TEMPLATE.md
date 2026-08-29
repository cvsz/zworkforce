## Summary

Describe the smallest complete change in this pull request.

## Requirement Or Migration Reference

Reference the relevant requirement ID, migration manifest item, runbook, issue, or release record.

## Security And Boundary Checks

- [ ] No secrets, provider keys, service tokens, wallet keys, MPC shares, card data, KYC payloads, or production identifiers are committed.
- [ ] Browser clients do not receive upstream provider credentials or service tokens.
- [ ] AI provider access stays behind `services/ai-gateway`.
- [ ] Mutating agent jobs remain behind explicit approval state and scoped tool grants.
- [ ] Workspace shell or deployment changes require explicit `shell` or `deploy` approval grants.
- [ ] ZWallet remains limited to billing-ledger adapter behavior and rejects signing, cards, KYC, MPC, and swaps.
- [ ] Production infrastructure or traffic changes include operator approval recorded outside automated agent execution.

## Validation

List the exact commands, workflow runs, artifacts, or manual checks used to validate this PR.

## Documentation

- [ ] Requirements, architecture, migration, operations, security, or provider docs were updated when behavior changed.
- [ ] Release evidence is tied to the exact commit or image digest being proposed.

## Production Readiness

- [ ] This PR does not affect production traffic.
- [ ] If it affects production, `docs/operations/production-master.md`, `docs/operations/staging-readiness.md`, and `docs/requirements/master-requirements.md` have been reviewed and the operator approval path is documented.
