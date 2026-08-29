# Z.A.R.V.I.S. Local Proactive Validation

Date: 2026-08-06  
Epic: #148  
Issue: #155  
Branch: `feat/zarvis-local-proactive-scheduler`

## Focused coverage

- immutable single-owner policy and schedule state;
- IANA timezone and server-side quiet hours;
- daily delivered-notification budget;
- confidence threshold, deduplication, and cooldown;
- owner-defined read-only allowlisted schedule;
- revocation and idempotent active subscription creation;
- missed-run skip and run-once semantics;
- restart recovery of policy, next run, last status, notification, feedback, and handoff;
- useful, irrelevant, and false-positive feedback;
- loopback-only health target validation and redirect denial;
- owner/worker credential separation;
- approval-only action handoff with `executed: false`;
- no autonomous mutation route or action credential.

## Required gates

- [ ] proactive service tests pass;
- [ ] proactive contract tests pass;
- [ ] all existing Node workspace tests pass;
- [ ] local Compose configuration validates;
- [ ] both ports are loopback-only;
- [ ] proactive schedule → signal → policy decision → notification → feedback → handoff smoke passes;
- [ ] handoff evidence confirms owner approval required and no execution;
- [ ] CI, validate, CodeQL Advanced, operations, and ZARVIS Local pass;
- [ ] no unresolved review thread;
- [ ] PR is squash-merged as one complete vertical slice.
