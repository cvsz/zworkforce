# Contributing

1. Create a feature branch from `main`.
2. Run `make check`. For PostgreSQL changes, also set
   `ZWORKFORCE_TEST_POSTGRES_URL` to a real PostgreSQL service and run
   `make postgres-test`.
3. Add tests for behavior changes, including failure/recovery paths.
4. Keep mutations behind policy and approval controls.
5. Document new environment variables and migration behavior.
6. Open a focused PR and call out security/operational impact.

The project favors small auditable primitives over implicit autonomous behavior.

## Protected main

The desired-state contract in `.github/rulesets/main.json` requires:

- A pull request and at least one independent approving review from someone
  other than the pull request author.
- CODEOWNERS review for protected paths and approval after the latest push.
- Dismissal of stale approvals and resolution of all review threads.
- Strict required status checks and no bypass actors.

This JSON file does not change GitHub's server-side settings. A live read-back
on 2026-10-30 found that ruleset `20988030` still reports
`required_approving_review_count: 0`, `require_code_owner_review: false`,
and `require_last_push_approval: false`, with a `RepositoryRole` bypass actor
using `bypass_mode: always`.

Until an authorized repository administrator applies the desired policy and
verifies the effective server-side ruleset through the GitHub API, independent
approval, CODEOWNERS enforcement, last-push approval, and restricted bypass
must be treated as **NOT ENFORCED**. Do not merge security-sensitive or
production-impacting changes solely because this file, the desired-state JSON,
or CI checks pass. Require a genuine independent review manually and keep
release/production changes blocked until administrator read-back confirms the
effective policy.
