# Security Gate Remediation Record - 2026-07-15

## Scope

- Baseline `main`: `2db36e428fa95457e0559dabc224b7d8ff10d289`
- Branch: `fix/codeql-security-alerts`
- Environment: repository-local and isolated Compose
- Production traffic: **DISABLED**
- External traffic: **DISABLED**

This slice addresses CodeQL alerts 1-5 and Dependabot alert 1 without changing authentication, authorization, approval, idempotency, audit, provider-credential, or production gates.

## Implementation status

| Finding | Status | Repository evidence | Missing evidence |
|---|---|---|---|
| Workspace path expressions | IMPLEMENTED | Canonical root containment rejects traversal and absolute paths; success and denial tests pass. | PR-head CodeQL result. |
| AI Gateway rate limiting | IMPLEMENTED | Authenticated API boundary has a validated, fail-closed limiter; deterministic 429 and invalid-configuration tests pass. | PR-head CodeQL and deployed-smoke results. |
| AI Gateway CORS | IMPLEMENTED | Browser access defaults to no origins; wildcard and malformed origins are rejected; allowlist tests pass. | PR-head CodeQL and deployed-smoke results. |
| Cloudflare installer log exposure | IMPLEMENTED | Command logs omit every argument while subprocess execution retains the injected values; regression tests verify the token and header name are absent. | PR-head CodeQL result. |
| PostCSS advisory | IMPLEMENTED | Workspace override resolves PostCSS `8.5.19`; `pnpm audit --audit-level moderate` reports no known vulnerabilities. | PR-head dependency policy result and Dependabot rescan. |

## Local validation

The branch head at the time of this record is not promoted to **VERIFIED** by local evidence. Commands completed successfully:

```text
npm test --prefix services/ai-gateway
npm test --prefix apps/zaicoder/web
python -m unittest tools/z-platform-cloudflare-py-installer/test_install_cloudflare_terraform.py
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm audit --audit-level moderate
npm audit --prefix services/ai-gateway --audit-level=moderate --omit=dev
docker compose config --quiet
docker compose up -d --build --wait
node scripts/staging-smoke.mjs
```

The isolated smoke result covered seven-service health, authenticated and denied requests, workspace approval denial, billing idempotency, agent lifecycle/cancellation/failure/retry/audit, persistence, backup/restore, metrics, ZWallet prohibited-capability rejection, and ZChat static checks. An integration probe also observed no CORS allow header for an unapproved origin and statuses `401`, `401`, `429` with a temporary two-request limit.

## Limitations

- **BLOCKED** - The exact PR head is not **VERIFIED** until GitHub Actions and CodeQL complete for that SHA and immutable artifact identifiers and digests are recorded.
- **PENDING_EXTERNAL** - No external staging account, endpoint, provider, browser bundle, HAR, alert receiver, backup target, or managed service was exercised.
- **PENDING_OPERATOR** - No staging reviewer, incident owner, production approver, or production decision is recorded.

## Rollback

Rollback is the baseline commit `2db36e428fa95457e0559dabc224b7d8ff10d289`. Reverting this slice restores the vulnerable baseline, so rollback requires the security findings to remain **BLOCKED** and must not be used to approve a release.

```bash
git revert <security-remediation-commit>
docker compose down -v
docker compose up -d --build --wait
```

Production and external traffic remain **DISABLED** after either forward deployment or rollback.
