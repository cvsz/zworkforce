# Phase 6 external verification suite

This suite executes the fourteen external and human-verification gates required by Issue #1. It does not synthesize or infer successful evidence.

## GitHub Environment configuration

The `staging` environment must define:

- Secret `PHASE6_EXTERNAL_SUITE_CONFIG_JSON`: completed configuration based on `docs/operations/phase6-external-suite.example.json`.
- Optional secret `STAGING_BEARER_TOKEN`: bearer credential used by configured HTTPS probes and command verifiers.
- Secrets `STAGING_CF_ACCESS_CLIENT_ID` and `STAGING_CF_ACCESS_CLIENT_SECRET`: Cloudflare Access service-token credentials used together for protected HTTPS probes.
- Variable `STAGING_REVIEWER`: GitHub login of the accountable staging reviewer.
- Secrets `ALERT_TEST_URL` and `ALERT_DELIVERY_STATUS_URL`.
- Secrets `BACKUP_CREATE_COMMAND`, `BACKUP_RESTORE_COMMAND`, and `BACKUP_VERIFY_COMMAND`.
- Secret `AI_UPLOAD_URL`.
- Secret `AI_PROVIDER_ENDPOINTS`: comma-separated approved HTTPS provider verification endpoints.
- Secret `AI_FAILOVER_URL`.
- Secret `BROWSER_BUNDLE_BASE64`: base64-encoded deployed browser bundle.
- Secret `BROWSER_HAR_BASE64`: base64-encoded deployed HAR JSON.

Do not commit the completed configuration when it contains private staging URLs, request bodies, or operational details. Do not place credentials directly in URLs, commands, browser artifacts, or the configuration JSON.
Use `scripts/configure-github-environments.sh` to create or refresh the `staging` and `production` environment protection rules before writing those secrets, passing only the real reviewer selectors approved by the operator.

## Verification modes

- `probe`: performs a real HTTPS request and verifies status and optional response text.
- `command`: executes a repository-controlled verification command. Exit code zero is required. Evidence stores command/output digests, not command output.
- `scan`: reads the configured bundle or HAR files and rejects credential identifiers and configured forbidden patterns.
- `attestation`: accepts an external verification only with an explicit reviewer and a non-placeholder evidence reference.
- Human checks (`zchat.keyboard`, `zchat.screen_reader`, `zchat.responsive`) require reviewer identity, timestamp, evidence reference, and substantive notes.

## Required checks

1. Observability dashboard
2. Distributed traces
3. Alert delivery
4. External backup restore
5. AI streaming
6. AI upload/file proxy
7. Multi-provider
8. Quota/failover
9. Browser bundle scan
10. HAR/network scan
11. Keyboard QA
12. Screen-reader QA
13. Responsive device QA
14. External session-provider QA

## Execution

Set the protected configuration:

```bash
gh secret set PHASE6_EXTERNAL_SUITE_CONFIG_JSON \
  --repo cvsz/z-platform \
  --env staging \
  < /secure/phase6-external-suite.json
```

Set browser evidence without writing encoded values to the repository:

```bash
base64 -w0 artifacts/browser/app.js | \
  gh secret set BROWSER_BUNDLE_BASE64 --repo cvsz/z-platform --env staging

base64 -w0 artifacts/browser/session.har | \
  gh secret set BROWSER_HAR_BASE64 --repo cvsz/z-platform --env staging
```

Set the remaining external inputs using files or standard input where possible:

```bash
printf '%s' "$ALERT_TEST_URL" | gh secret set ALERT_TEST_URL --repo cvsz/z-platform --env staging
printf '%s' "$ALERT_DELIVERY_STATUS_URL" | gh secret set ALERT_DELIVERY_STATUS_URL --repo cvsz/z-platform --env staging
printf '%s' "$BACKUP_CREATE_COMMAND" | gh secret set BACKUP_CREATE_COMMAND --repo cvsz/z-platform --env staging
printf '%s' "$BACKUP_RESTORE_COMMAND" | gh secret set BACKUP_RESTORE_COMMAND --repo cvsz/z-platform --env staging
printf '%s' "$BACKUP_VERIFY_COMMAND" | gh secret set BACKUP_VERIFY_COMMAND --repo cvsz/z-platform --env staging
printf '%s' "$AI_UPLOAD_URL" | gh secret set AI_UPLOAD_URL --repo cvsz/z-platform --env staging
printf '%s' "$AI_PROVIDER_ENDPOINTS" | gh secret set AI_PROVIDER_ENDPOINTS --repo cvsz/z-platform --env staging
printf '%s' "$AI_FAILOVER_URL" | gh secret set AI_FAILOVER_URL --repo cvsz/z-platform --env staging
```

Dispatch against one immutable release SHA:

```bash
gh workflow run phase6-external-suite.yml \
  --repo cvsz/z-platform \
  --ref main \
  -f release_sha="$(git rev-parse origin/main)"
```

The workflow uploads and attests `phase6-external-evidence-<release-sha>`. A successful workflow is valid only for the exact checked-out SHA.

## Safety properties

- HTTPS is mandatory for probes and externally configured verification endpoints.
- Placeholder configuration and evidence are rejected before execution.
- Protected runtime inputs are checked before the suite starts.
- Browser bundle and HAR evidence are materialized only on the ephemeral runner and deleted afterward.
- Probe endpoints are represented in evidence only by an origin fingerprint.
- Command output is represented only by SHA-256 digests.
- Human QA cannot be auto-verified.
- Production traffic and production approval remain separate gates.
