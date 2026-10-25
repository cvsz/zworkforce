# AI Pull Request Automation for zWorkforce

## Status

**Design contract / implementation backlog.** This document does not claim that a GitHub App, webhook endpoint, review worker, patch runner, or merge bot is deployed or enabled.

The objective is to extend zWorkForce's existing durable workflow runtime into a governed PR automation platform inspired by the workflow pattern described by Mergestorm: review a PR, validate findings, optionally prepare a patch, re-run checks, and merge only under repository policy.

## Product surfaces

- **ZReview** — commit-SHA-bound, diff-aware review producing structured findings and GitHub Check Run annotations.
- **ZFix** — optional patch generation for explicitly eligible findings, executed in an isolated workspace. It may update only the PR head branch when write access has been explicitly granted.
- **ZCI** — orchestrates repository-owned checks and records their immutable run identifiers and conclusions.
- **ZMerge** — evaluates merge eligibility but does not replace GitHub branch protection, required reviews, rulesets, or merge queue semantics.

These are logical capabilities, not separate schedulers. Reuse the existing zWorkforce durable tasks, workflows, event triggers, worker leases, policy-as-code, audit chain, tenant boundaries, artifact store, model router, and FinOps accounting. Do not introduce a parallel scheduler or bypass the existing control plane.

## Target architecture

1. GitHub App sends pull_request and check_suite/check_run webhooks to a dedicated webhook ingress.
2. Ingress validates X-Hub-Signature-256 against the raw request bytes using constant-time comparison, validates the event/action, enforces a body-size limit, and deduplicates by delivery ID.
3. An accepted delivery is persisted before acknowledgement and converted into a durable zWorkforce task/workflow run. A retry must not create duplicate runs.
4. The orchestrator captures repository identity, PR number, base SHA, head SHA, installation ID, delivery ID, and policy version. Credentials are resolved server-side only.
5. ZReview reads the PR diff and bounded repository context at the captured SHA. Its structured finding schema includes stable finding ID, path, line/range, severity, category, evidence, rationale, confidence, and suggested remediation.
6. Deterministic tools (tests, linters, type checks, dependency/security scanners) corroborate findings where available. LLM output is untrusted data and cannot issue tools or permissions.
7. ZFix is disabled by default. When enabled by repository/tenant policy, it runs in a disposable sandbox with no production secrets, restricted network egress, resource/time/output ceilings, and a narrowly scoped write credential. It must verify that the PR head SHA has not changed before writing.
8. ZCI records check status for the exact candidate SHA. A new commit invalidates earlier review and check evidence and starts a bounded new iteration.
9. ZMerge only reports eligibility or requests a merge through GitHub's supported mechanism when all independent policy conditions pass. GitHub branch protection/rulesets remain authoritative.

## Initial rollout and permissions

### Stage 0 — read-only review

- Install as a GitHub App with least-privilege repository metadata and pull-request read permissions.
- Subscribe only to required PR lifecycle events.
- Post results through Check Runs only after check-write permission is deliberately enabled; otherwise persist a report artifact for operator review.
- Do not request Contents write, Administration, Actions write, or merge permission for the read-only stage.
- Do not execute code from untrusted forks on privileged/self-hosted runners.

### Stage 1 — validated comments and checks

- Enable Checks write only for selected repositories.
- Anchor all output to the captured head SHA; reject stale results.
- Use bounded diff/context retrieval and redact credentials/PII from logs and artifacts.
- Use deterministic checks and duplicate suppression to control false positives.

### Stage 2 — opt-in patch generation

- Require explicit tenant/repository policy and per-job authorization.
- Use ephemeral isolated workspaces; do not expose provider tokens, GitHub App private keys, or internal network access to untrusted code.
- Patch only the PR head branch; never push directly to the default/protected branch.
- Validate patch size, changed paths, generated/binary files, tests, and security checks before pushing.
- Limit attempts and model cost; stop after a configured iteration ceiling.

### Stage 3 — governed merge

- Require current head SHA, successful required checks, required independent human approvals, resolved review threads where policy requires them, and no merge conflicts.
- Do not treat an AI approval as a required human review.
- Do not bypass branch protection, rulesets, merge queues, CODEOWNERS, or repository policy.
- Default to advisory eligibility until the repository explicitly enables the supported merge workflow.

## Required durable records

Persist at least:

- GitHub installation/repository identity and tenant binding.
- Delivery ID, event/action, received timestamp, payload digest, and processing outcome.
- PR number, base/head SHA, workflow/run ID, policy version, model/provider route, and cost.
- Finding IDs and evidence references, test/check run IDs, patch digest, changed paths, and result.
- Authorization/approval actor, scope, expiry, decision digest, audit correlation ID, and merge outcome if applicable.

Do not persist webhook secrets, private keys, bearer tokens, or complete unredacted payloads unless a reviewed retention policy explicitly requires a minimized subset.

## State machine

received -> verified -> deduplicated -> queued -> reviewing -> validated -> (reported | patch_pending) -> patching -> checks_pending -> checks_passed -> merge_eligible -> merged

Terminal/error states include rejected, stale_sha, policy_denied, failed, cancelled, and dead_letter. Transitions must be durable, idempotent, observable, and tenant-scoped. No state transition alone grants mutation authority.

## Security invariants

- Verify webhook signatures over raw bytes before parsing JSON.
- Treat PR titles, descriptions, issue text, source files, diffs, test output, and model output as untrusted input and possible prompt injection.
- Never use pull_request_target to check out or execute untrusted PR code with privileged credentials.
- Separate review credentials from patch-write credentials and merge authority.
- Use GitHub App installation tokens with minimal repository scope and short lifetimes.
- Prevent SSRF and exfiltration from the sandbox using DNS/IP-aware egress enforcement, not hostname allowlists alone.
- Enforce tenant isolation in every query and artifact reference.
- Record tamper-evident audit events for authorization, findings, patch attempts, check outcomes, and merge decisions.
- Fail closed when signatures, repository mapping, policy, SHA freshness, checks, approvals, or authorization evidence are missing.
- Never claim production readiness from unit tests alone; external isolation and GitHub permission evidence must be recorded separately.

## Acceptance criteria

1. Invalid/missing webhook signatures are rejected; valid signatures are verified against the raw payload.
2. Duplicate delivery IDs do not create duplicate durable workflow runs.
3. Oversized and malformed payloads are rejected without leaking payload contents.
4. Delivery replay, cross-tenant repository mapping, unsupported actions, and stale SHA results are denied.
5. Findings and reports are deterministic-schema validated and anchored to the exact head SHA.
6. Read-only mode cannot write contents or merge; patching and merging are off by default.
7. Patch mode cannot access production secrets, protected branches, or unrestricted network egress.
8. A changed head SHA invalidates prior review/check eligibility.
9. Merge eligibility fails closed if any required check, independent approval, policy decision, or current-SHA evidence is missing.
10. Tests cover SQLite and PostgreSQL persistence/idempotency where persistence is added, plus security regression cases.
11. CI, security scanning, operational runbooks, retention policy, rollback, and external sandbox evidence are complete before production admission.

## Repository integration plan

Implement in small reviewed PRs:

1. **Contracts and ingress:** settings, signature verification, webhook event schema, delivery dedupe, durable enqueue, tests.
2. **Read-only review workflow:** GitHub App client, bounded diff fetch, review finding schema, artifact/report output, Check Run adapter.
3. **Validation and observability:** deterministic checks, status transitions, audit events, metrics, cost ceilings, stale-SHA handling.
4. **Isolated patch workflow:** ephemeral sandbox adapter, path/size limits, explicit authorization, compare-and-set against current head SHA.
5. **Merge eligibility:** read-only policy evaluator first; optional merge adapter only after independent governance and branch-protection verification.

Each PR must preserve existing public API contracts, SQLite compatibility, PostgreSQL transaction semantics, tenant isolation, policy-as-code, and the current GitHub governance process.
