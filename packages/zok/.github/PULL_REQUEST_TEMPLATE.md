## Summary
Describe the change, why it is needed, and the release/implementation item it addresses.

Fixes # (issue number, if applicable)

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Security hardening
- [ ] Infrastructure / workflow
- [ ] Documentation / release-control update
- [ ] Breaking change

## Scope and risk
- Affected components:
- Security impact:
- Data/schema impact:
- Deployment/migration impact:
- Rollback plan:

## Verification
- [ ] `npm test`
- [ ] `npm run lint`
- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] `npm audit --omit=dev --audit-level=high`
- [ ] Additional runtime/provider/security evidence attached when required

## Release-control synchronization
- [ ] `CHANGELOG.md` updated when the change is notable
- [ ] `exec-planing.md` updated when execution status/order/evidence changes
- [ ] `IMPLEMENTATION-CHECKLIST.md` updated when implementation status changes
- [ ] README/deployment/security documentation updated when behavior or operations change

## Evidence
Link tests, logs, screenshots, provider sandbox results, benchmarks, migration output, or other evidence supporting completion.

## Final check
- [ ] No mock/demo/UI-only behavior is presented as a production capability.
- [ ] No secrets or sensitive disclosure material are included in this PR.
- [ ] Residual risks and environment-dependent verification are documented.
