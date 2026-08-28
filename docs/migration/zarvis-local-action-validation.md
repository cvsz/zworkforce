# Z.A.R.V.I.S. Local Action Validation

Date: 2026-08-06  
Epic: #148  
Issue: #154  
Branch: `feat/zarvis-local-action-gateway`

## Focused coverage

- immutable owner identity and local-only status;
- default-deny capability registry;
- confused-deputy rejection;
- exact approval digest and one-time nonce;
- idempotent approval and execution replay;
- compare-and-set stale-preview rejection;
- execution-bound rollback proof and restoration;
- approval expiry before execution;
- emergency-stop persistence, revocation, and exact resume confirmation;
- fixed-path durable reconstruction after restart;
- owner and worker token separation at HTTP boundary;
- startup failure without both independent secrets.

## Required gates

- [ ] local action gateway tests pass;
- [ ] action schema tests pass;
- [ ] all existing Node workspace tests pass;
- [ ] Compose configuration validates;
- [ ] CI, validate, CodeQL Advanced, and operations pass;
- [ ] no unresolved review thread;
- [ ] PR is squash-merged as one complete vertical slice.

## Local deployment acceptance

Production in this project means a single-owner local Ubuntu/Linux deployment. Release acceptance additionally requires proof that port 8098 is loopback-only, LAN access fails, the worker lacks the owner token, backup/restore succeeds, and token rotation invalidates old credentials.
