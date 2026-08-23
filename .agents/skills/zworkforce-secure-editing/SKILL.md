---
name: zworkforce-secure-editing
description: Implement scoped zWorkforce changes with production-grade security, tests, docs, rollback notes, and validation. Use when editing Python service code, CLI/API behavior, policy/approval/tooling logic, workflows, deployment files, Windows client code, or packages/zarvis while preserving tenant and secret boundaries.
---

# zWorkforce Secure Editing

Make the smallest complete change that satisfies the request and preserves the
platform security model.

## Workflow

1. Read `AGENTS.md`, `.codex/AGENTS.md`, and any nested `AGENTS.md` in the
   changed package.
2. Locate the runtime boundary before editing: API, database mixin, worker,
   CLI, static UI, Windows client, deployment, or Z.A.R.V.I.S. package.
3. Preserve fail-closed behavior for auth, tenant IDs, approvals, policy,
   secrets, shell execution, HTTP egress, and audit events.
4. Add or update focused tests in `tests/` or the package-local test suite.
5. Update docs/examples when behavior, configuration, commands, or operational
   expectations change.
6. Run the narrowest relevant test first, then broader validation when the
   change crosses runtime boundaries.

## Validation Defaults

Use these commands when relevant:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q zworkforce tests
python3 scripts/verify_release.py --expected 3.0.2
git diff --check
```

For Windows client changes, validate from `ZWorkforceClient/`. For
Z.A.R.V.I.S. changes, use package-local scripts and docs under
`packages/zarvis/`.

## Completion Note

Report files changed, tests run, tests not run, and any residual production
risk. Never claim remote CI, package publication, or deployment happened unless
verified from GitHub or the target system.
