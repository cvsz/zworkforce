# Phase 6 Verification Commands

Run these commands only against operator-approved staging endpoints. Never paste secret values into issue comments or committed files.

## Local deployed smoke

```bash
set -a
source .env
set +a
unset STAGING_SMOKE_AI_GATEWAY_URL STAGING_SMOKE_AGENT_ORCHESTRATOR_URL \
  STAGING_SMOKE_WORKSPACE_RUNTIME_URL STAGING_SMOKE_BILLING_LEDGER_URL \
  STAGING_SMOKE_AGENT_PROVIDER_URL
node scripts/staging-smoke.mjs | tee staging-smoke-result.json
jq . staging-smoke-result.json
```

## Main provenance

```bash
gh run list --repo cvsz/z-platform --branch main --workflow validate.yml --limit 10
gh run view --repo cvsz/z-platform <run-id>
gh attestation verify --repo cvsz/z-platform <downloaded-sbom-path>
```

Record the run URL, attestation URL, subject digest, verifier identity, and verification result.

## Browser credential inspection

```bash
# Build each production browser application according to its package manifest.
# Then scan generated assets for prohibited names and recognizable token forms.
grep -RInE 'Z_PLATFORM_SERVICE_TOKEN|UPSTREAM_API_KEY|AI_GATEWAY_PROVIDER_TOKEN|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}' \
  apps/*/dist apps/*/.next apps/*/build 2>/dev/null && exit 1 || true
```

Use browser developer tools to export a HAR and verify that no provider credential or internal service token appears in request URLs, headers, bodies, responses, local storage, session storage, cookies accessible to JavaScript, or source maps.

## AI provider verification

For each approved provider, record:

1. Model catalog response and selected allowlisted model.
2. Non-streaming completion.
3. Streaming completion with at least two data frames and a terminal frame.
4. Upload/file request when supported by the provider contract.
5. Quota exhaustion behavior.
6. Timeout behavior.
7. Primary-provider failure and approved fallback behavior.
8. Sanitized gateway logs proving that provider credentials were not logged.

## External backup and restore

1. Export an authenticated backup.
2. Encrypt it with the approved key-management service.
3. Upload to the approved immutable backup destination.
4. Restore into an isolated staging namespace.
5. Verify jobs, idempotency indexes, queue state, audit events, and workspace metadata.
6. Record RPO/RTO measurements and object version/digest.

## Human sign-off

Record only identities and timestamps appropriate for the repository:

- Staging reviewer
- Production approving operator
- Incident owner
- Escalation route
- Watch-window start/end
- Rollback authority and selected rollback SHA
